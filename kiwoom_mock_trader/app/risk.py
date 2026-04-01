"""Risk management and runtime state persistence."""

from __future__ import annotations

import logging

from app.exceptions import KiwoomRiskError
from app.models import (
    AppSettings,
    OrderResponse,
    OrderStatus,
    RecentOrderRecord,
    RiskCheckResult,
    TradingState,
)
from app.utils import (
    is_within_time_window,
    load_json_file,
    now_in_timezone,
    resolve_path,
    save_json_file,
)


class RiskManager:
    """Enforce bot-wide risk rules and keep daily state."""

    def __init__(self, settings: AppSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("risk")
        self.state_path = resolve_path(settings.project_root, settings.runtime.state_file)
        self.state = self.load_state()

    def load_state(self) -> TradingState:
        """Load persisted state from disk."""

        payload = load_json_file(self.state_path, default={})
        if not payload:
            return TradingState()
        return TradingState(**payload)

    def save_state(self) -> None:
        """Persist current state."""

        save_json_file(self.state_path, self.state.model_dump())

    def prepare_for_today(self, trade_date: str, baseline_assets_krw: int) -> TradingState:
        """Reset daily counters on a new day and remember the first asset snapshot."""

        if self.state.trade_date != trade_date:
            self.state = TradingState(
                trade_date=trade_date,
                daily_order_count=0,
                daily_baseline_assets_krw=baseline_assets_krw,
                halted=False,
                halt_reason=None,
                recent_orders=[],
            )
            self.save_state()
            return self.state

        if self.state.daily_baseline_assets_krw is None:
            self.state.daily_baseline_assets_krw = baseline_assets_krw
            self.save_state()
        return self.state

    def is_market_open(self) -> bool:
        """Check the configured market window."""

        now = now_in_timezone(self.settings.trading.timezone)
        return is_within_time_window(
            now,
            self.settings.trading.market_open_time,
            self.settings.trading.market_close_time,
        )

    def current_daily_pnl_krw(self, current_assets_krw: int) -> int:
        """Compute current day profit/loss against the startup baseline."""

        baseline = self.state.daily_baseline_assets_krw or current_assets_krw
        return current_assets_krw - baseline

    def calculate_order_quantity(self, current_price: int, available_cash_krw: int) -> int:
        """Convert risk limits into a quantity."""

        if current_price <= 0:
            return 0
        budget = min(self.settings.risk.max_order_amount_krw, max(available_cash_krw, 0))
        return budget // current_price

    def preflight_check(
        self,
        *,
        side: str,
        order_amount_krw: int,
        position_count: int,
        daily_pnl_krw: int,
        open_order_exists: bool,
    ) -> RiskCheckResult:
        """Check hard safety rules before placing an order."""

        reasons: list[str] = []

        if self.state.halted:
            reasons.append(self.state.halt_reason or "Trading has already been halted.")

        if not self.is_market_open():
            reasons.append("Current time is outside the configured trading window.")

        if self.state.daily_order_count >= self.settings.risk.max_daily_orders:
            reasons.append("The maximum number of daily orders has already been reached.")

        if side == "buy" and position_count >= self.settings.risk.max_position_count:
            reasons.append("The maximum allowed position count has already been reached.")

        # Buy-side only, so an exit is never blocked by the per-order cap.
        if side == "buy" and order_amount_krw > self.settings.risk.max_order_amount_krw:
            reasons.append("The requested buy order exceeds max_order_amount_krw.")

        if daily_pnl_krw <= -self.settings.risk.max_daily_loss_krw:
            reasons.append("The daily loss limit has been reached.")

        if open_order_exists:
            reasons.append("A duplicate open order for the same symbol and side already exists.")

        return RiskCheckResult(allowed=not reasons, reasons=reasons)

    def halt(self, reason: str) -> None:
        """Persist a halt state so the bot does not continue blindly."""

        self.state.halted = True
        self.state.halt_reason = reason
        self.save_state()
        self.logger.error("Trading halted: %s", reason)

    def raise_if_daily_loss_hit(self, current_assets_krw: int) -> None:
        """Fail fast when the daily loss limit is breached."""

        daily_pnl = self.current_daily_pnl_krw(current_assets_krw)
        if daily_pnl <= -self.settings.risk.max_daily_loss_krw:
            reason = (
                "Daily loss limit reached. "
                f"current_pnl={daily_pnl} limit={-self.settings.risk.max_daily_loss_krw}"
            )
            self.halt(reason)
            raise KiwoomRiskError(reason)

    def register_order(self, response: OrderResponse, amount_krw: int) -> None:
        """Increment daily counts after a submitted or simulated order."""

        self.state.daily_order_count += 1
        self.state.recent_orders.append(
            RecentOrderRecord(
                order_no=response.order_no,
                symbol=response.symbol,
                side=response.side,
                quantity=response.quantity,
                amount_krw=amount_krw,
                simulated=response.simulated,
                timestamp=response.requested_at,
            )
        )
        self.state.recent_orders = self.state.recent_orders[-30:]
        self.save_state()

    @staticmethod
    def has_open_duplicate(
        statuses: list[OrderStatus],
        *,
        symbol: str,
        side: str,
    ) -> bool:
        """Return True if an open order already exists for the same stock and side."""

        for status in statuses:
            if status.symbol == symbol and status.side == side and status.remaining_quantity > 0:
                return True
        return False

