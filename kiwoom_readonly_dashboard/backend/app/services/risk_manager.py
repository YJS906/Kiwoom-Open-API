"""Risk management for signal generation and execution."""

from __future__ import annotations

from datetime import datetime

from app.models.schemas import AccountSummary, HoldingItem, StockQuote, StockSearchItem
from app.models.trading import PositionState, RiskConfig, RiskDecision, SessionState
from app.services.session_guard import SessionGuard


class RiskManager:
    """Evaluate whether a new entry is allowed."""

    def __init__(self, config: RiskConfig, session_guard: SessionGuard) -> None:
        self.config = config
        self.session_guard = session_guard

    def evaluate_entry(
        self,
        *,
        symbol: str,
        entry_price: int,
        account_summary: AccountSummary,
        actual_holdings: list[HoldingItem],
        paper_positions: dict[str, PositionState],
        session: SessionState,
        quote: StockQuote,
        metadata: StockSearchItem | None,
        now: datetime | None = None,
    ) -> RiskDecision:
        """Return a risk decision with explicit block reasons."""

        current = now or self.session_guard.now()
        reasons: list[str] = []
        blocked_category: str | None = None

        session_cash_candidates = [
            account_summary.orderable_amount,
            session.paper_cash_balance_krw if session.paper_cash_balance_krw > 0 else account_summary.orderable_amount,
            session.actual_available_cash_krw if session.actual_available_cash_krw > 0 else account_summary.orderable_amount,
        ]
        positive_cash_candidates = [value for value in session_cash_candidates if value > 0]
        remaining_cash = min(positive_cash_candidates) if positive_cash_candidates else 0
        suggested_cash = int(remaining_cash * self.config.buy_cash_pct_of_remaining)
        position_cap = int(account_summary.estimated_assets * self.config.max_position_pct)
        suggested_cash = max(0, min(suggested_cash, position_cap))
        quantity = suggested_cash // max(entry_price, 1)

        actual_symbols = {item.symbol for item in actual_holdings}
        paper_symbols = {item.symbol for item in paper_positions.values()}
        total_position_count = len(actual_symbols | paper_symbols)

        if session.halted:
            blocked_category = blocked_category or "session"
            reasons.append(session.halt_reason or "Session is halted.")
        if not self.session_guard.can_enter_new_positions(self.config.no_new_entry_after, current=current):
            blocked_category = blocked_category or "session"
            reasons.append("No new entries are allowed at the current time.")
        if total_position_count >= self.config.max_positions:
            blocked_category = blocked_category or "positions"
            reasons.append("The maximum number of positions has already been reached.")
        if session.daily_new_entries >= self.config.max_daily_new_entries:
            blocked_category = blocked_category or "daily_limit"
            reasons.append("The daily maximum for new entries has already been reached.")
        if session.daily_loss_krw >= self.config.max_daily_loss_krw:
            blocked_category = blocked_category or "daily_loss"
            reasons.append("The daily loss limit has been reached.")
        if symbol in actual_symbols or symbol in paper_symbols:
            blocked_category = blocked_category or "duplicate"
            reasons.append("The symbol is already held in the account or paper book.")
        cooldown_raw = session.cooldown_until.get(symbol)
        if cooldown_raw and datetime.fromisoformat(cooldown_raw) > current:
            blocked_category = blocked_category or "cooldown"
            reasons.append("The symbol is still in the re-entry cooldown window.")
        if self.config.block_reentry_after_stop and symbol in session.recent_stop_loss_symbols:
            blocked_category = blocked_category or "cooldown"
            reasons.append("The symbol was recently stopped out and re-entry is blocked.")
        if self.config.block_high_volatility and abs(quote.change_rate) >= self.config.max_intraday_change_pct:
            blocked_category = blocked_category or "volatility"
            reasons.append("The symbol is too volatile for the configured risk profile.")
        if remaining_cash < entry_price:
            blocked_category = blocked_category or "cash"
            reasons.append("Available cash is lower than one share at the entry price.")
        if quantity <= 0:
            blocked_category = blocked_category or "cash"
            reasons.append("Calculated quantity is zero after applying the risk caps.")

        if metadata:
            market_name = (metadata.market_name or "").upper()
            if self.config.exclude_etf_etn and ("ETF" in market_name or "ETN" in market_name):
                blocked_category = blocked_category or "instrument"
                reasons.append("ETF/ETN instruments are excluded by configuration.")
            state = (getattr(metadata, "state", "") or "").upper()
            if self.config.exclude_trading_halt and "정지" in state:
                blocked_category = blocked_category or "trading_halt"
                reasons.append("Trading halt symbols are excluded by configuration.")

        return RiskDecision(
            allowed=not reasons,
            reasons=reasons,
            blocked_category=blocked_category,
            remaining_cash_krw=remaining_cash,
            suggested_order_cash_krw=suggested_cash,
            quantity=max(quantity, 0),
        )
