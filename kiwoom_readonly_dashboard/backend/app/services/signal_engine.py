"""Strategy engine orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from datetime import timedelta
from typing import Any
from uuid import uuid4

from app.core.config import Settings, save_trading_overrides
from app.models.schemas import AccountSummary, HoldingItem
from app.models.trading import (
    AdminConfigPatch,
    CandidateStock,
    FillEvent,
    OrderIntent,
    PositionState,
    ReplayPoint,
    ReplayResponse,
    SessionState,
    SignalEvent,
    StrategyDashboardSnapshot,
    StrategyChartSeries,
    StrategyDecision,
    StrategyRuntimeState,
    StrategyStatus,
    StrategySymbolDetail,
    TradingConfig,
    now_kr,
)
from app.services.bar_builder import BarBuilderService
from app.services.high52_scanner import High52Scanner
from app.services.kiwoom_client import KiwoomClientService
from app.services.order_executor import OrderExecutor
from app.services.position_manager import PositionManager
from app.services.pullback_strategy import PullbackStrategyEngine
from app.services.risk_manager import RiskManager
from app.services.session_guard import SessionGuard


class SignalEngine:
    """Continuously refresh scanner candidates and generate signals."""

    def __init__(
        self,
        settings: Settings,
        config: TradingConfig,
        kiwoom_client: KiwoomClientService,
        scanner: High52Scanner,
        bar_builder: BarBuilderService,
        strategy: PullbackStrategyEngine,
        risk_manager: RiskManager,
        order_executor: OrderExecutor,
        position_manager: PositionManager,
        session_guard: SessionGuard,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.config = config
        self.kiwoom_client = kiwoom_client
        self.scanner = scanner
        self.bar_builder = bar_builder
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.order_executor = order_executor
        self.position_manager = position_manager
        self.session_guard = session_guard
        self.logger = logger.getChild("signal_engine")
        self.state = self._load_state()
        self._status = StrategyStatus(
            connected=False,
            status="idle",
            detail="Waiting for the first strategy refresh.",
        )
        self._recent_errors: list[str] = []
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._last_decisions: dict[str, StrategyDecision] = {}

    async def start(self) -> None:
        """Start the background refresh loop."""

        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="strategy-signal-engine")

    async def shutdown(self) -> None:
        """Stop the background refresh loop."""

        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def refresh_now(self) -> StrategyDashboardSnapshot:
        """Run one strategy refresh immediately."""

        async with self._lock:
            await self._refresh_once()
            return self._build_snapshot()

    async def get_snapshot(self) -> StrategyDashboardSnapshot:
        """Return the latest snapshot, refreshing lazily if needed."""

        if self.state.session.last_scan_at is None:
            try:
                return await self.refresh_now()
            except Exception as exc:
                # Keep the dashboard usable even when Kiwoom throttles the first scan.
                self._remember_error(str(exc))
                self._status = StrategyStatus(
                    connected=False,
                    status="degraded",
                    last_updated_at=now_kr(),
                    detail=str(exc),
                )
                self.logger.warning(
                    "Returning an empty/stale strategy snapshot because the initial refresh failed: %s",
                    exc,
                )
                return self._build_snapshot()
        return self._build_snapshot()

    async def get_symbol_detail(self, symbol: str, include_charts: bool = False) -> StrategySymbolDetail:
        """Return strategy details and charts for a single symbol."""

        normalized = symbol.strip().upper()[-6:]
        candidate = self.state.candidates.get(normalized)
        charts = (
            await self.bar_builder.get_strategy_bundle(normalized)
            if include_charts
            else {"daily": [], "60m": [], "15m": [], "5m": [], "weekly": []}
        )
        decision = self._last_decisions.get(normalized)
        explanation_cards: list[str] = []
        if decision:
            explanation_cards.append(decision.summary)
            explanation_cards.extend(decision.reasons)
        if candidate and candidate.blocked_reason:
            explanation_cards.append(f"Blocked: {candidate.blocked_reason}")
        return StrategySymbolDetail(
            symbol=normalized,
            name=candidate.name if candidate else (await self.kiwoom_client.find_company_name(normalized)),
            candidate=candidate,
            decision=decision,
            charts=charts,
            levels=decision.annotations if decision else [],
            explanation_cards=explanation_cards,
        )

    async def get_chart_series(self, symbol: str, timeframe: str) -> StrategyChartSeries:
        """Return one strategy timeframe on demand for the chart panel."""

        normalized = symbol.strip().upper()[-6:]
        bars = await self.bar_builder.get_bars(normalized, timeframe, limit=None)  # type: ignore[arg-type]
        return StrategyChartSeries(symbol=normalized, timeframe=timeframe, bars=bars)

    async def replay(self, symbol: str) -> ReplayResponse:
        """Minimal replay endpoint using the daily filter over history."""

        charts = await self.bar_builder.get_strategy_bundle(symbol)
        daily = charts["daily"]
        points: list[ReplayPoint] = []
        start_index = max(60, self.config.strategy.daily_ma_slow)
        for index in range(start_index, len(daily)):
            decision = self.strategy.evaluate(
                symbol=symbol,
                daily_bars=daily[: index + 1],
                bars_60m=charts["60m"],
                trigger_bars=charts[self.config.strategy.trigger_timeframe],
            )
            action = "hold"
            if decision.stage == "trigger":
                action = "entry_ready"
            elif decision.stage == "buy_signal":
                action = "buy_signal"
            elif not decision.passed:
                action = "blocked"
            points.append(
                ReplayPoint(
                    time=daily[index].time,
                    close=daily[index].close,
                    action=action,
                    summary=decision.summary,
                )
            )
        return ReplayResponse(
            symbol=symbol,
            timeframe="daily",
            points=points[-self.config.admin.replay_default_days :],
            decision=self._last_decisions.get(symbol),
        )

    async def execute_signal(self, signal_id: str) -> dict[str, Any]:
        """Manually execute a queued signal."""

        async with self._lock:
            signal = next((item for item in self.state.signals if item.id == signal_id), None)
            if signal is None:
                raise RuntimeError("Signal not found.")
            if signal.status not in {"queued", "blocked"}:
                raise RuntimeError("The signal is no longer executable.")
            return await self._execute_signal_locked(signal)

    async def update_runtime_config(self, patch: AdminConfigPatch) -> TradingConfig:
        """Persist runtime overrides and rebuild the in-memory config."""

        previous_paper_trading = self.config.execution.paper_trading
        merged = save_trading_overrides(self.settings, patch.model_dump(exclude_none=True))
        self.config = merged
        self.strategy = PullbackStrategyEngine(merged.strategy, merged.risk)
        self.session_guard = SessionGuard(merged.session)
        self.risk_manager = RiskManager(merged.risk, self.session_guard)
        self.order_executor.config = merged.execution
        self.scanner.config = merged.scanner
        if previous_paper_trading and not merged.execution.paper_trading:
            self._reset_paper_runtime_state()
            self._save_state()
        return merged

    def get_status(self) -> StrategyStatus:
        """Return engine status for health panels."""

        return deepcopy(self._status)

    def get_recent_errors(self) -> list[str]:
        """Return recent engine errors."""

        return list(self._recent_errors)

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.refresh_now()
            except Exception as exc:
                self._remember_error(str(exc))
                self._status = StrategyStatus(
                    connected=False,
                    status="degraded",
                    last_updated_at=now_kr(),
                    detail=str(exc),
                )
                self.logger.exception("Strategy refresh failed: %s", exc)
            await asyncio.sleep(max(self.config.scanner.refresh_seconds, 5))

    async def _refresh_once(self) -> None:
        summary = await self.kiwoom_client.get_account_summary()
        holdings_response = await self.kiwoom_client.get_holdings()
        self._prepare_session(summary, holdings_response.items)
        self._sync_account_positions(holdings_response.items)
        await self._manage_overnight_positions_on_open()

        refreshed_candidates = await self.scanner.refresh(self.state.candidates)
        quotes_for_positions: dict[str, int] = {}
        seen_symbols = {candidate.symbol for candidate in refreshed_candidates}

        for candidate in refreshed_candidates:
            bundle = await self._load_signal_bundle(candidate.symbol)
            decision = self.strategy.evaluate(
                symbol=candidate.symbol,
                daily_bars=bundle["daily"],
                bars_60m=bundle["60m"],
                trigger_bars=bundle[self.config.strategy.trigger_timeframe],
            )
            self._last_decisions[candidate.symbol] = decision
            quotes_for_positions[candidate.symbol] = candidate.last_price or bundle["daily"][-1].close
            updated_candidate = await self._apply_candidate_decision(
                candidate,
                decision,
                summary,
                holdings_response.items,
            )
            self.state.candidates[updated_candidate.symbol] = updated_candidate

        for symbol in list(self.state.candidates):
            if symbol not in seen_symbols and self.state.candidates[symbol].state not in {"ordered", "exited"}:
                self.state.candidates.pop(symbol, None)

        self.state.positions = self.position_manager.mark_to_market(self.state.positions, quotes_for_positions)
        self._update_daily_loss()
        await self._evaluate_exit_signals()
        self.state.session.last_scan_at = now_kr()
        self.state.session.updated_at = now_kr()
        self.state.session.last_error = None
        self._status = StrategyStatus(
            connected=True,
            status="running",
            last_updated_at=self.state.session.last_scan_at,
            detail=f"Candidates={len(self.state.candidates)} source={self.scanner.last_source}",
        )
        self._trim_state()
        self._save_state()

    async def _load_signal_bundle(self, symbol: str) -> dict[str, list[Any]]:
        """Load only the timeframes required for the active strategy profile."""

        daily = await self.bar_builder.get_bars(symbol, "daily", limit=260)
        profile = self.config.strategy.strategy_profile
        trigger_timeframe = self.config.strategy.trigger_timeframe

        if profile in {"high52_breakout", "box_breakout"}:
            return {
                "daily": daily,
                "60m": [],
                "15m": [],
                "5m": [],
                "weekly": [],
            }

        bars_60m = await self.bar_builder.get_bars(symbol, "60m", limit=80)
        trigger_limit = 160 if trigger_timeframe == "15m" else 200
        trigger_bars = await self.bar_builder.get_bars(symbol, trigger_timeframe, limit=trigger_limit)
        return {
            "daily": daily,
            "60m": bars_60m,
            "15m": trigger_bars if trigger_timeframe == "15m" else [],
            "5m": trigger_bars if trigger_timeframe == "5m" else [],
            "weekly": [],
        }

    def _prepare_session(self, summary: AccountSummary, holdings: list[HoldingItem]) -> None:
        today = self.session_guard.today()
        now = now_kr()
        available_cash = summary.orderable_amount if summary.orderable_amount > 0 else summary.deposit
        if self.state.session.trade_date != today:
            self.state.session = SessionState(
                trade_date=today,
                paper_cash_balance_krw=available_cash,
                actual_available_cash_krw=available_cash,
                actual_holdings_count=len(holdings),
                market_open=self.session_guard.is_market_open(),
                can_enter_new_positions=self.session_guard.can_enter_new_positions(
                    self.config.risk.no_new_entry_after
                ),
                pending_overnight_symbols=[holding.symbol for holding in holdings if holding.quantity > 0],
                updated_at=now,
            )
            return

        session = self.state.session
        session.market_open = self.session_guard.is_market_open()
        session.can_enter_new_positions = self.session_guard.can_enter_new_positions(
            self.config.risk.no_new_entry_after
        )
        session.actual_available_cash_krw = available_cash
        if not self.config.execution.paper_trading:
            # In Kiwoom mock/live order mode, reuse the actual orderable cash so
            # legacy paper state does not cap new entries incorrectly.
            session.paper_cash_balance_krw = available_cash
        session.actual_holdings_count = len(holdings)
        if session.paper_cash_balance_krw <= 0:
            session.paper_cash_balance_krw = available_cash
        session.updated_at = now

    async def _manage_overnight_positions_on_open(self) -> None:
        """Check overnight holdings as soon as the new trading session opens."""

        if self.config.execution.paper_trading:
            return
        if not self.config.session.manage_overnight_positions_on_open:
            return

        session = self.state.session
        if not session.market_open:
            return
        if session.last_open_management_date == session.trade_date:
            return

        overnight_symbols = [
            symbol
            for symbol in session.pending_overnight_symbols
            if symbol in self.state.positions
        ]
        if not overnight_symbols:
            session.last_open_management_date = session.trade_date
            session.pending_overnight_symbols = []
            return

        open_quotes: dict[str, int] = {}
        for symbol in overnight_symbols:
            try:
                quote = await self.kiwoom_client.get_stock_quote(symbol)
            except Exception as exc:
                self.logger.warning(
                    "Opening quote fetch failed for overnight position %s: %s",
                    symbol,
                    exc,
                )
                continue
            if quote.current_price > 0:
                open_quotes[symbol] = quote.current_price

        if open_quotes:
            self.state.positions = self.position_manager.mark_to_market(self.state.positions, open_quotes)

        await self._evaluate_exit_signals(symbols=set(overnight_symbols))
        session.last_open_management_date = session.trade_date
        session.pending_overnight_symbols = []
        session.updated_at = now_kr()

    def _sync_account_positions(self, holdings: list[HoldingItem]) -> None:
        """Mirror actual Kiwoom account holdings into runtime positions for exit logic."""

        if self.config.execution.paper_trading:
            return

        now = now_kr()
        previous_account_positions = {
            symbol: position
            for symbol, position in self.state.positions.items()
            if position.source == "account"
        }
        updated_positions = {
            symbol: position
            for symbol, position in self.state.positions.items()
            if position.source != "account"
        }

        for holding in holdings:
            if holding.quantity <= 0:
                continue

            previous = previous_account_positions.get(holding.symbol)
            updated_positions[holding.symbol] = PositionState(
                symbol=holding.symbol,
                name=holding.name,
                quantity=holding.quantity,
                avg_price=holding.average_price,
                current_price=holding.current_price,
                market_value_krw=holding.current_price * holding.quantity,
                unrealized_pnl_krw=holding.evaluation_profit_loss,
                realized_pnl_krw=previous.realized_pnl_krw if previous else 0,
                stop_price=self._calculate_account_stop_price(holding.average_price, previous.stop_price if previous else None),
                target_price=self._calculate_account_target_price(holding.average_price),
                source="account",
                opened_at=self._resolve_account_opened_at(holding.symbol, previous, now),
                last_updated_at=now,
            )
            self._mark_entry_order_filled_from_account(holding.symbol, now)

        self.state.positions = updated_positions

    async def _apply_candidate_decision(
        self,
        candidate: CandidateStock,
        decision: StrategyDecision,
        summary: AccountSummary,
        holdings: list[HoldingItem],
    ) -> CandidateStock:
        current = candidate.model_copy(deep=True)
        active_position = self.state.positions.get(candidate.symbol)
        if active_position is not None:
            current.state = "ordered"
            current.blocked_reason = None
            return current

        if not decision.passed:
            current.state = "watching" if decision.stage != "insufficient_data" else "new"
            current.blocked_reason = None
            return current

        metadata = await self.kiwoom_client.get_stock_metadata(candidate.symbol)
        quote = await self.kiwoom_client.get_stock_quote(candidate.symbol)
        risk = self.risk_manager.evaluate_entry(
            symbol=candidate.symbol,
            entry_price=decision.entry_price or quote.current_price,
            account_summary=summary,
            actual_holdings=holdings,
            paper_positions=self.state.positions,
            session=self.state.session,
            quote=quote,
            metadata=metadata,
        )
        if not self._has_open_signal(candidate.symbol, "entry"):
            signal = SignalEvent(
                id=f"sig-{uuid4().hex[:12]}",
                symbol=candidate.symbol,
                name=candidate.name,
                signal_type="entry",
                status="queued" if risk.allowed else "blocked",
                candidate_state="signal_ready" if risk.allowed else "blocked",
                trigger_timeframe=decision.entry_timeframe,
                decision=decision,
                risk=risk,
                explanation=decision.summary,
            )
            self.state.signals.insert(0, signal)
            self.state.session.last_signal_at = signal.created_at
            if risk.allowed and self.config.execution.auto_buy_enabled:
                await self._execute_signal_locked(signal)

        current.state = "signal_ready" if risk.allowed else "blocked"
        current.blocked_reason = None if risk.allowed else "; ".join(risk.reasons)
        return current

    async def _evaluate_exit_signals(self, symbols: set[str] | None = None) -> None:
        for symbol, position in list(self.state.positions.items()):
            if symbols is not None and symbol not in symbols:
                continue
            current_price = position.current_price
            reason: str | None = None
            if position.stop_price and current_price <= position.stop_price:
                reason = "Stop-loss level was reached."
            elif position.target_price and current_price >= position.target_price:
                reason = "Take-profit level was reached."
            if reason is None or self._has_open_signal(symbol, "exit"):
                continue
            decision = StrategyDecision(
                symbol=symbol,
                passed=True,
                stage="exit_signal",
                summary=reason,
                reasons=[reason],
                entry_price=current_price,
                stop_price=position.stop_price,
                target_price=position.target_price,
            )
            signal = SignalEvent(
                id=f"sig-{uuid4().hex[:12]}",
                symbol=symbol,
                name=position.name,
                signal_type="exit",
                status="queued",
                candidate_state="ordered",
                decision=decision,
                explanation=reason,
            )
            self.state.signals.insert(0, signal)
            if self.config.execution.auto_buy_enabled:
                await self._execute_signal_locked(signal)

    async def _execute_signal_locked(self, signal: SignalEvent) -> dict[str, Any]:
        candidate = self.state.candidates.get(signal.symbol)
        current_price = candidate.last_price if candidate and candidate.last_price else signal.decision.entry_price
        if not current_price:
            quote = await self.kiwoom_client.get_stock_quote(signal.symbol)
            current_price = quote.current_price

        intent = self._build_intent(signal)
        result = await self.order_executor.execute(signal, intent, current_price)
        self.state.orders.insert(0, result.intent)
        signal.order_intent_id = result.intent.id
        signal.status = "ordered" if result.fill is None else "filled"
        signal.updated_at = now_kr()

        payload: dict[str, Any] = {
            "signal": signal.model_dump(mode="json"),
            "order": result.intent.model_dump(mode="json"),
        }
        if result.fill is not None:
            self.state.fills.insert(0, result.fill)
            self.state.positions, realized = self.position_manager.apply_fill(
                self.state.positions,
                result.fill,
                result.intent,
            )
            self._after_fill(signal, result.intent, result.fill)
            payload["fill"] = result.fill.model_dump(mode="json")
            payload["realized_pnl_krw"] = realized
        self._trim_state()
        self._save_state()
        return payload

    def _build_intent(self, signal: SignalEvent) -> OrderIntent:
        side = "buy" if signal.signal_type == "entry" else "sell"
        quantity = signal.risk.quantity if side == "buy" and signal.risk else 0
        if side == "sell":
            position = self.state.positions.get(signal.symbol)
            quantity = position.quantity if position else 0
        if quantity <= 0:
            raise RuntimeError("Calculated quantity is zero.")
        return OrderIntent(
            id=f"ord-{uuid4().hex[:12]}",
            signal_id=signal.id,
            symbol=signal.symbol,
            name=signal.name,
            side=side,
            quantity=quantity,
            order_type=self.config.execution.order_type,
            desired_price=signal.decision.entry_price,
            trigger_price=signal.decision.breakout_price,
            stop_price=signal.decision.stop_price,
            target_price=signal.decision.target_price,
            paper=self.config.execution.paper_trading,
            state="queued",
            reason=signal.explanation,
        )

    def _after_fill(self, signal: SignalEvent, intent: OrderIntent, fill: FillEvent) -> None:
        if intent.side == "buy":
            self.state.session.paper_cash_balance_krw = max(
                self.state.session.paper_cash_balance_krw - fill.fill_value_krw,
                0,
            )
            self.state.session.daily_new_entries += 1
            self.state.session.last_order_at = fill.filled_at
            candidate = self.state.candidates.get(signal.symbol)
            if candidate:
                candidate.state = "ordered"
                candidate.updated_at = fill.filled_at
            return

        self.state.session.paper_cash_balance_krw += fill.fill_value_krw
        if signal.decision.summary.startswith("Stop-loss"):
            self.state.session.recent_stop_loss_symbols.append(signal.symbol)
            cooldown_until = self.session_guard.now() + timedelta(minutes=self.config.risk.reentry_cooldown_minutes)
            self.state.session.cooldown_until[signal.symbol] = cooldown_until.isoformat()
        candidate = self.state.candidates.get(signal.symbol)
        if candidate:
            candidate.state = "exited"
            candidate.updated_at = fill.filled_at

    def _update_daily_loss(self) -> None:
        total_unrealized = sum(position.unrealized_pnl_krw for position in self.state.positions.values())
        total_realized = sum(position.realized_pnl_krw for position in self.state.positions.values())
        total_pnl = total_realized + total_unrealized
        self.state.session.daily_loss_krw = abs(total_pnl) if total_pnl < 0 else 0

    def _calculate_account_stop_price(self, avg_price: int, preserved_stop_price: int | None) -> int:
        """Calculate a stop price for account-synced positions."""

        fixed_stop = max(min(int(avg_price * (1 - self.config.risk.stop_loss_pct)), avg_price - 1), 1)
        if preserved_stop_price and 0 < preserved_stop_price < avg_price:
            return max(fixed_stop, preserved_stop_price)
        return fixed_stop

    def _calculate_account_target_price(self, avg_price: int) -> int:
        """Calculate the fixed take-profit target for account-synced positions."""

        return max(int(round(avg_price * (1 + self.config.risk.take_profit_pct))), avg_price + 1)

    def _resolve_account_opened_at(
        self,
        symbol: str,
        previous: PositionState | None,
        default_time,
    ):
        """Keep the original open time when possible, otherwise fall back to the buy order time."""

        if previous is not None:
            return previous.opened_at
        for intent in self.state.orders:
            if intent.symbol == symbol and intent.side == "buy":
                return intent.created_at
        return default_time

    def _mark_entry_order_filled_from_account(self, symbol: str, updated_at) -> None:
        """Reflect that a submitted buy order became a live holding in the mock account."""

        for signal in self.state.signals:
            if signal.symbol == symbol and signal.signal_type == "entry" and signal.status == "ordered":
                signal.status = "filled"
                signal.updated_at = updated_at
                break
        for intent in self.state.orders:
            if intent.symbol == symbol and intent.side == "buy" and intent.state == "submitted":
                intent.state = "filled"
                intent.updated_at = updated_at
                break

    def _has_open_signal(self, symbol: str, signal_type: str) -> bool:
        for signal in self.state.signals:
            if signal.symbol == symbol and signal.signal_type == signal_type and signal.status in {
                "queued",
                "ordered",
            }:
                return True
        return False

    def _build_snapshot(self) -> StrategyDashboardSnapshot:
        candidates = list(self.state.candidates.values())
        return StrategyDashboardSnapshot(
            candidates=candidates,
            watching=[item for item in candidates if item.state == "watching"],
            signal_ready=[item for item in candidates if item.state == "signal_ready"],
            blocked=[item for item in candidates if item.state == "blocked"],
            queued_signals=[item for item in self.state.signals if item.status in {"queued", "blocked"}],
            orders=self.state.orders,
            fills=self.state.fills,
            positions=list(self.state.positions.values()),
            session=self.state.session,
            config=self.config,
            status=self._status,
            scanner_source=self.scanner.last_source,
        )

    def _trim_state(self) -> None:
        self.state.signals = self.state.signals[:100]
        self.state.orders = self.state.orders[:100]
        self.state.fills = self.state.fills[:100]

    def _reset_paper_runtime_state(self) -> None:
        """Drop paper-only state before switching to actual Kiwoom mock orders."""

        self.logger.warning(
            "Resetting paper-only runtime state before enabling Kiwoom mock-order execution."
        )
        self.state.positions = {
            symbol: position
            for symbol, position in self.state.positions.items()
            if position.source != "paper"
        }
        self.state.signals = []
        self.state.orders = [intent for intent in self.state.orders if not intent.paper]
        self.state.fills = [fill for fill in self.state.fills if not fill.paper]
        self.state.session.paper_cash_balance_krw = 0
        self.state.session.daily_new_entries = 0
        self.state.session.daily_loss_krw = 0
        self.state.session.last_signal_at = None
        self.state.session.last_order_at = None
        self.state.session.last_error = None
        for candidate in self.state.candidates.values():
            if candidate.state in {"signal_ready", "ordered", "blocked"}:
                candidate.state = "watching"
                candidate.blocked_reason = None

    def _remember_error(self, message: str) -> None:
        self._recent_errors.append(message)
        self._recent_errors = self._recent_errors[-10:]
        self.state.session.last_error = message

    def _load_state(self) -> StrategyRuntimeState:
        path = self.settings.trading_state_file
        if not path.exists():
            return StrategyRuntimeState()
        try:
            return StrategyRuntimeState(**json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            self.logger.warning("Ignoring invalid strategy runtime state: %s", exc)
            return StrategyRuntimeState()

    def _save_state(self) -> None:
        self.settings.trading_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings.trading_state_file.write_text(
            json.dumps(self.state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
