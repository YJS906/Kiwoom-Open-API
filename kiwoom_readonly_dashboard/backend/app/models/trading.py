"""Trading domain models for the strategy engine and paper broker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


SEOUL_TZ = timezone(timedelta(hours=9), name="Asia/Seoul")

CandidateState = Literal["new", "watching", "signal_ready", "ordered", "exited", "blocked"]
SignalStatus = Literal["queued", "blocked", "ordered", "filled", "expired", "cancelled", "closed"]
OrderIntentState = Literal["queued", "submitted", "filled", "rejected", "cancelled"]
Side = Literal["buy", "sell"]
ExecutionOrderType = Literal["market", "limit", "stop_limit"]
Timeframe = Literal["daily", "weekly", "60m", "15m", "5m"]


def now_kr() -> datetime:
    """Return timezone-aware Asia/Seoul time."""

    return datetime.now(SEOUL_TZ)


class ScannerConfig(BaseModel):
    """Config for the 52-week-high scanner."""

    condition_name: str = "52주 신고가"
    source_mode: Literal["condition_first", "realtime_first", "realtime_only"] = "realtime_first"
    realtime_market: Literal["all", "kospi", "kosdaq"] = "all"
    max_realtime_candidates: int = 6
    refresh_seconds: int = 45
    candidate_ttl_minutes: int = 240
    min_daily_history: int = 260
    fallback_symbols: list[str] = Field(default_factory=lambda: ["005930"])


class StrategyConfig(BaseModel):
    """Configurable strategy parameters."""

    strategy_profile: Literal["high52_pullback", "high52_breakout", "box_breakout"] = "high52_pullback"
    recent_breakout_days: int = 20
    daily_ma_fast: int = 20
    daily_ma_slow: int = 60
    breakout_volume_multiplier: float = 2.0
    breakout_volume_lookback_days: int = 20
    pullback_min_ratio: float = 0.30
    pullback_max_ratio: float = 0.50
    volume_dryup_ratio: float = 0.70
    support_reference: Literal["breakout", "ma_fast", "either", "both"] = "either"
    support_tolerance_pct: float = 0.02
    trigger_timeframe: Literal["15m", "5m"] = "15m"
    use_vwap: bool = True
    require_bullish_reversal_candle: bool = True
    min_daily_bars: int = 120
    min_intraday_bars: int = 40
    breakout_lookback_bars_60m: int = 18
    rally_window_bars_60m: int = 24
    breakout_entry_buffer_pct: float = 0.002
    box_window_days: int = 20
    box_max_range_pct: float = 0.12
    box_breakout_volume_multiplier: float = 1.5
    box_breakout_buffer_pct: float = 0.001


class RiskConfig(BaseModel):
    """Risk controls for the system."""

    buy_cash_pct_of_remaining: float = 0.20
    max_position_pct: float = 0.25
    max_positions: int = 3
    max_daily_new_entries: int = 2
    max_daily_loss_krw: int = 50_000
    reentry_cooldown_minutes: int = 120
    stop_loss_pct: float = 0.03
    take_profit_mode: Literal["fixed_pct", "breakout_retest_trail", "trend_ma_trail"] = "fixed_pct"
    take_profit_trailing_ma_days: int = 5
    take_profit_trailing_buffer_pct: float = 0.005
    # Legacy field kept for runtime-state compatibility. New logic no longer uses it.
    take_profit_pct: float = 0.05
    no_new_entry_after: str = "14:30"
    block_reentry_after_stop: bool = True
    block_high_volatility: bool = True
    max_intraday_change_pct: float = 18.0
    exclude_trading_halt: bool = True
    exclude_admin_issue: bool = True
    exclude_etf_etn: bool = True


class ExecutionConfig(BaseModel):
    """Execution toggles and order defaults."""

    paper_trading: bool = True
    auto_buy_enabled: bool = False
    use_mock_only: bool = True
    mock_order_enabled: bool = False
    real_order_enabled: bool = False
    order_type: ExecutionOrderType = "market"
    slippage_bps: int = 10
    max_retry_count: int = 1
    fill_poll_seconds: int = 2
    manual_signal_execution: bool = True


class SessionConfig(BaseModel):
    """Trading session window."""

    timezone: str = "Asia/Seoul"
    market_open_time: str = "09:05"
    market_close_time: str = "15:20"
    manage_overnight_positions_on_open: bool = True


class AdminConfig(BaseModel):
    """Dashboard/runtime override options."""

    enable_runtime_overrides: bool = True
    replay_default_days: int = 60


class TradingConfig(BaseModel):
    """Full strategy engine config loaded from config.yaml."""

    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)


class ConditionDefinition(BaseModel):
    """Condition search definition from Kiwoom."""

    seq: str
    name: str


class TradeBar(BaseModel):
    """Normalized OHLCV bar used by the strategy."""

    timeframe: Timeframe
    time: str
    open: int
    high: int
    low: int
    close: int
    volume: int


class PriceLevel(BaseModel):
    """Annotated price used by the strategy UI."""

    label: str
    price: int
    kind: Literal["entry", "stop", "target", "breakout", "support", "resistance"]


class CandidateStock(BaseModel):
    """Scanner output with current workflow state."""

    symbol: str
    name: str
    state: CandidateState = "new"
    source: str
    condition_name: str | None = None
    condition_seq: str | None = None
    breakout_date: str | None = None
    breakout_price: int | None = None
    last_price: int | None = None
    change_rate: float | None = None
    market_name: str | None = None
    note: str | None = None
    blocked_reason: str | None = None
    detected_at: datetime = Field(default_factory=now_kr)
    updated_at: datetime = Field(default_factory=now_kr)


class RiskDecision(BaseModel):
    """Result of entry/exit risk checks."""

    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    blocked_category: str | None = None
    remaining_cash_krw: int = 0
    suggested_order_cash_krw: int = 0
    quantity: int = 0
    checked_at: datetime = Field(default_factory=now_kr)


class StrategyDecision(BaseModel):
    """Result of evaluating the pullback strategy."""

    symbol: str
    passed: bool
    stage: Literal["insufficient_data", "daily_filter", "pullback_filter", "trigger", "buy_signal", "exit_signal", "hold"]
    summary: str
    reasons: list[str] = Field(default_factory=list)
    entry_timeframe: Timeframe | None = None
    entry_price: int | None = None
    stop_price: int | None = None
    target_price: int | None = None
    breakout_price: int | None = None
    pullback_ratio: float | None = None
    rally_volume_avg: float | None = None
    pullback_volume_avg: float | None = None
    vwap: float | None = None
    annotations: list[PriceLevel] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=now_kr)


class SignalEvent(BaseModel):
    """Generated signal waiting for execution or review."""

    id: str
    symbol: str
    name: str
    signal_type: Literal["entry", "exit"]
    status: SignalStatus = "queued"
    candidate_state: CandidateState = "signal_ready"
    trigger_timeframe: Timeframe | None = None
    decision: StrategyDecision
    risk: RiskDecision | None = None
    explanation: str
    created_at: datetime = Field(default_factory=now_kr)
    updated_at: datetime = Field(default_factory=now_kr)
    order_intent_id: str | None = None


class OrderIntent(BaseModel):
    """Normalized order instruction before a fill is created."""

    id: str
    signal_id: str
    symbol: str
    name: str
    side: Side
    quantity: int
    order_type: ExecutionOrderType
    desired_price: int | None = None
    trigger_price: int | None = None
    stop_price: int | None = None
    target_price: int | None = None
    paper: bool = True
    state: OrderIntentState = "queued"
    reason: str | None = None
    created_at: datetime = Field(default_factory=now_kr)
    updated_at: datetime = Field(default_factory=now_kr)


class FillEvent(BaseModel):
    """Fill information generated by the paper broker or real broker."""

    id: str
    order_intent_id: str
    symbol: str
    name: str
    side: Side
    price: int
    quantity: int
    fill_value_krw: int
    paper: bool = True
    reason: str | None = None
    filled_at: datetime = Field(default_factory=now_kr)


class PositionState(BaseModel):
    """Paper position state tracked inside the strategy engine."""

    symbol: str
    name: str
    quantity: int
    avg_price: int
    current_price: int
    market_value_krw: int
    unrealized_pnl_krw: int
    realized_pnl_krw: int = 0
    stop_price: int | None = None
    target_price: int | None = None
    highest_price: int | None = None
    source: Literal["paper", "account"] = "paper"
    opened_at: datetime = Field(default_factory=now_kr)
    last_updated_at: datetime = Field(default_factory=now_kr)
    closed_at: datetime | None = None


class SessionState(BaseModel):
    """Daily runtime state for the strategy engine."""

    trade_date: str = ""
    market_open: bool = False
    can_enter_new_positions: bool = False
    paper_cash_balance_krw: int = 0
    actual_available_cash_krw: int = 0
    actual_holdings_count: int = 0
    daily_new_entries: int = 0
    daily_loss_krw: int = 0
    halted: bool = False
    halt_reason: str | None = None
    recent_stop_loss_symbols: list[str] = Field(default_factory=list)
    cooldown_until: dict[str, str] = Field(default_factory=dict)
    pending_overnight_symbols: list[str] = Field(default_factory=list)
    last_open_management_date: str | None = None
    last_scan_at: datetime | None = None
    last_signal_at: datetime | None = None
    last_order_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime = Field(default_factory=now_kr)


class StrategyRuntimeState(BaseModel):
    """Persisted strategy runtime state stored under runtime/."""

    candidates: dict[str, CandidateStock] = Field(default_factory=dict)
    signals: list[SignalEvent] = Field(default_factory=list)
    orders: list[OrderIntent] = Field(default_factory=list)
    fills: list[FillEvent] = Field(default_factory=list)
    positions: dict[str, PositionState] = Field(default_factory=dict)
    session: SessionState = Field(default_factory=SessionState)


class StrategyStatus(BaseModel):
    """Status shown in the dashboard and health panel."""

    connected: bool
    status: str
    last_updated_at: datetime | None = None
    detail: str | None = None


class StrategyDashboardSnapshot(BaseModel):
    """Aggregated snapshot used by the dashboard strategy panels."""

    candidates: list[CandidateStock]
    watching: list[CandidateStock]
    signal_ready: list[CandidateStock]
    blocked: list[CandidateStock]
    queued_signals: list[SignalEvent]
    orders: list[OrderIntent]
    fills: list[FillEvent]
    positions: list[PositionState]
    session: SessionState
    config: TradingConfig
    status: StrategyStatus
    scanner_source: str = "unknown"
    updated_at: datetime = Field(default_factory=now_kr)


class StrategySymbolDetail(BaseModel):
    """Detailed strategy view for one symbol."""

    symbol: str
    name: str
    candidate: CandidateStock | None = None
    decision: StrategyDecision | None = None
    charts: dict[str, list[TradeBar]] = Field(default_factory=dict)
    levels: list[PriceLevel] = Field(default_factory=list)
    explanation_cards: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=now_kr)


class StrategyChartSeries(BaseModel):
    """Single strategy chart payload loaded on demand by timeframe."""

    symbol: str
    timeframe: Timeframe
    bars: list[TradeBar] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=now_kr)


class ReplayPoint(BaseModel):
    """Single replay/backtest evaluation point."""

    time: str
    close: int
    action: Literal["hold", "entry_ready", "buy_signal", "blocked"]
    summary: str


class ReplayResponse(BaseModel):
    """Minimal replay response used by the admin panel."""

    symbol: str
    timeframe: Timeframe
    points: list[ReplayPoint]
    decision: StrategyDecision | None = None
    updated_at: datetime = Field(default_factory=now_kr)


class AdminConfigPatch(BaseModel):
    """Runtime config patch request."""

    scanner: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    session: dict[str, Any] = Field(default_factory=dict)
