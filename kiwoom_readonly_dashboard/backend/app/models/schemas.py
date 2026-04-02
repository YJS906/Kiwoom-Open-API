"""Pydantic schemas shared across routers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class ConnectionState(BaseModel):
    connected: bool
    status: str
    last_updated_at: datetime | None = None
    detail: str | None = None


class StatusPanel(BaseModel):
    kiwoom_rest: ConnectionState
    kiwoom_websocket: ConnectionState
    news_provider: ConnectionState
    strategy_engine: ConnectionState | None = None
    last_refresh_at: datetime | None = None
    recent_errors: list[str] = Field(default_factory=list)


class AccountSummary(BaseModel):
    total_evaluation_amount: int
    total_profit_loss: int
    total_profit_rate: float
    holdings_count: int
    deposit: int
    estimated_assets: int
    updated_at: datetime


class HoldingItem(BaseModel):
    symbol: str
    name: str
    quantity: int
    available_quantity: int
    average_price: int
    current_price: int
    evaluation_profit_loss: int
    profit_rate: float
    market_name: str | None = None


class HoldingsResponse(BaseModel):
    items: list[HoldingItem]
    updated_at: datetime


class StockSearchItem(BaseModel):
    symbol: str
    name: str
    market_code: str
    market_name: str
    last_price: int | None = None


class StockSearchResponse(BaseModel):
    items: list[StockSearchItem]
    updated_at: datetime


class StockQuote(BaseModel):
    symbol: str
    name: str
    market_name: str | None = None
    current_price: int
    previous_close: int
    diff_from_previous_close: int
    change_rate: float
    volume: int
    open_price: int
    high_price: int
    low_price: int
    best_ask: int | None = None
    best_bid: int | None = None
    market_phase: str | None = None
    updated_at: datetime


class OrderbookLevel(BaseModel):
    price: int
    quantity: int
    delta: int | None = None


class OrderbookSnapshot(BaseModel):
    symbol: str
    asks: list[OrderbookLevel]
    bids: list[OrderbookLevel]
    total_ask_quantity: int | None = None
    total_bid_quantity: int | None = None
    timestamp: str | None = None
    updated_at: datetime


class StockDetailResponse(BaseModel):
    quote: StockQuote
    orderbook: OrderbookSnapshot | None = None


class RealtimeHigh52Item(BaseModel):
    symbol: str
    name: str
    current_price: int
    diff_from_previous_close: int
    change_rate: float
    volume: int
    best_ask: int | None = None
    best_bid: int | None = None
    high_price: int | None = None
    low_price: int | None = None
    market_name: str | None = None


class RealtimeHigh52Response(BaseModel):
    status: Literal["ok", "unavailable", "error"]
    source: str
    environment: Literal["mock", "production"]
    reason: str | None = None
    items: list[RealtimeHigh52Item]
    updated_at: datetime


class ChartBar(BaseModel):
    time: str
    open: int
    high: int
    low: int
    close: int
    volume: int


class ChartResponse(BaseModel):
    symbol: str
    interval: Literal["day", "minute"]
    range_label: str
    bars: list[ChartBar]
    updated_at: datetime


class NewsItem(BaseModel):
    title: str
    source: str
    published_at: datetime | None = None
    url: str
    summary: str | None = None
    provider: str


class NewsResponse(BaseModel):
    symbol: str
    company_name: str
    provider: str
    items: list[NewsItem]
    updated_at: datetime


class RealtimeEnvelope(BaseModel):
    channel: Literal["quote", "orderbook", "market_status", "status", "error"]
    symbol: str | None = None
    payload: dict[str, Any]
    updated_at: datetime


class WSClientRequest(BaseModel):
    action: Literal["subscribe", "ping"] = "subscribe"
    symbols: list[str] = Field(default_factory=list)
