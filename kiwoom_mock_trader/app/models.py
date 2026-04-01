"""Pydantic models used across the project."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    """Secrets loaded from .env."""

    app_key: str
    secret_key: str
    account_no: str
    account_password: str | None = None


class ApiSettings(BaseModel):
    """REST and WebSocket endpoints."""

    mock_base_url: str = "https://mockapi.kiwoom.com"
    production_base_url: str = "https://api.kiwoom.com"
    mock_websocket_url: str = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
    production_websocket_url: str = "wss://api.kiwoom.com:10000/api/dostk/websocket"
    request_timeout_seconds: int = 15


class TradingSettings(BaseModel):
    """Polling and market window settings."""

    symbol: str = "005930"
    exchange: Literal["KRX", "NXT", "SOR"] = "KRX"
    default_order_type: Literal["limit", "market"] = "limit"
    poll_interval_seconds: int = 30
    market_open_time: str = "09:05"
    market_close_time: str = "15:10"
    timezone: str = "Asia/Seoul"


class SafetySettings(BaseModel):
    """Hard safety defaults."""

    dry_run: bool = True
    use_mock_only: bool = True
    stop_on_error: bool = True
    fail_if_account_mismatch: bool = True


class RiskSettings(BaseModel):
    """Risk limits for the sample bot."""

    max_daily_orders: int = 3
    max_position_count: int = 1
    max_order_amount_krw: int = 100000
    max_daily_loss_krw: int = 30000


class StrategySettings(BaseModel):
    """Parameters for the demo strategy."""

    name: str = "previous_close_demo"
    buy_above_prev_close_pct: float = 0.01
    take_profit_pct: float = 0.03
    stop_loss_pct: float = 0.02


class RuntimeSettings(BaseModel):
    """Files and directories written during runtime."""

    state_dir: str = ".runtime"
    token_cache_file: str = ".runtime/token_mock.json"
    state_file: str = ".runtime/state.json"
    orders_dir: str = ".runtime/orders"


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    directory: str = "logs"
    file_name: str = "bot.log"


class AppSettings(BaseModel):
    """Merged application settings."""

    environment: str = "mock"
    api: ApiSettings = Field(default_factory=ApiSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    credentials: Credentials
    project_root: Path

    @property
    def rest_base_url(self) -> str:
        return (
            self.api.mock_base_url
            if self.environment.lower() == "mock"
            else self.api.production_base_url
        )

    @property
    def websocket_url(self) -> str:
        return (
            self.api.mock_websocket_url
            if self.environment.lower() == "mock"
            else self.api.production_websocket_url
        )


class AccessToken(BaseModel):
    """Cached OAuth access token."""

    token: str
    token_type: str
    expires_dt: str


class StockBasicInfo(BaseModel):
    """Simplified stock quote snapshot."""

    symbol: str
    name: str
    exchange: str
    current_price: int
    previous_close: int
    diff_from_previous_close: int
    change_rate: float
    volume: int
    raw: dict[str, Any] = Field(default_factory=dict)


class DailyCandle(BaseModel):
    """Daily OHLCV candle."""

    trade_date: str
    open_price: int
    high_price: int
    low_price: int
    close_price: int
    volume: int
    turnover: int
    raw: dict[str, Any] = Field(default_factory=dict)


class CashBalance(BaseModel):
    """Deposit summary."""

    deposit_krw: int
    raw: dict[str, Any] = Field(default_factory=dict)


class Holding(BaseModel):
    """Single held stock."""

    symbol: str
    name: str
    quantity: int
    available_quantity: int
    current_price: int
    purchase_price: int
    evaluation_profit_loss: int
    profit_rate: float
    raw: dict[str, Any] = Field(default_factory=dict)


class AccountSnapshot(BaseModel):
    """Account level summary and holdings."""

    total_purchase_amount_krw: int
    total_evaluation_amount_krw: int
    total_profit_loss_krw: int
    total_profit_rate: float
    estimated_assets_krw: int
    holdings: list[Holding] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderRequest(BaseModel):
    """Normalized order request used by the bot."""

    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    order_type: Literal["limit", "market"]
    price: int | None = None
    exchange: Literal["KRX", "NXT", "SOR"] = "KRX"


class OrderResponse(BaseModel):
    """Response saved after order placement."""

    order_no: str
    side: Literal["buy", "sell"]
    symbol: str
    quantity: int
    order_type: Literal["limit", "market"]
    price: int | None = None
    exchange: str
    simulated: bool = False
    requested_at: str
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderStatus(BaseModel):
    """Order and fill status."""

    order_no: str
    symbol: str
    side: str
    order_quantity: int
    filled_quantity: int
    remaining_quantity: int
    order_price: int
    filled_price: int
    accepted_type: str
    filled_at: str | None = None
    exchange: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class StrategyDecision(BaseModel):
    """Strategy output."""

    action: Literal["buy", "sell", "hold"]
    reason: str
    quantity: int | None = None
    order_type: Literal["limit", "market"] = "limit"
    price: int | None = None


class RecentOrderRecord(BaseModel):
    """State entry persisted for daily order counting."""

    order_no: str
    symbol: str
    side: str
    quantity: int
    amount_krw: int
    simulated: bool
    timestamp: str


class TradingState(BaseModel):
    """Persistent state written under .runtime/state.json."""

    trade_date: str = ""
    daily_order_count: int = 0
    daily_baseline_assets_krw: int | None = None
    halted: bool = False
    halt_reason: str | None = None
    recent_orders: list[RecentOrderRecord] = Field(default_factory=list)


class RiskCheckResult(BaseModel):
    """Result of pre-order risk checks."""

    allowed: bool
    reasons: list[str] = Field(default_factory=list)

