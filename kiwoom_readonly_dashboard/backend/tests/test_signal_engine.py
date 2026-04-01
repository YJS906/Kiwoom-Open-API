"""Tests for signal generation and manual paper execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.schemas import AccountSummary, HoldingItem, StockQuote, StockSearchItem
from app.models.trading import CandidateStock, ScannerConfig, TradeBar, TradingConfig
from app.services.order_executor import OrderExecutor
from app.services.paper_broker import PaperBroker
from app.services.position_manager import PositionManager
from app.services.pullback_strategy import PullbackStrategyEngine
from app.services.risk_manager import RiskManager
from app.services.session_guard import SessionGuard
from app.services.signal_engine import SignalEngine


SEOUL = timezone(timedelta(hours=9))


def make_daily_bars() -> list[TradeBar]:
    bars: list[TradeBar] = []
    price = 100
    for index in range(260):
        bars.append(
            TradeBar(
                timeframe="daily",
                time=f"2025-01-{(index % 28) + 1:02d}",
                open=price,
                high=price + 4,
                low=price - 2,
                close=price + 2,
                volume=1000 + index * 3,
            )
        )
        price += 1
    return bars


def make_60m_bars() -> list[TradeBar]:
    prices = [
        100,
        104,
        108,
        112,
        118,
        124,
        130,
        138,
        146,
        154,
        160,
        156,
        150,
        144,
        138,
        140,
        142,
        145,
        147,
        149,
        151,
        152,
        153,
        154,
    ]
    bars: list[TradeBar] = []
    for index, close in enumerate(prices):
        bars.append(
            TradeBar(
                timeframe="60m",
                time=f"2025-03-31T{9 + (index % 8):02d}:00:00",
                open=close - 2,
                high=close + 2,
                low=close - 4,
                close=close,
                volume=1200 if index <= 10 else 500,
            )
        )
    return bars


def make_trigger_bars() -> list[TradeBar]:
    closes = [140, 141, 142, 143, 144, 145, 144, 145, 146, 147, 148, 151]
    bars: list[TradeBar] = []
    for index, close in enumerate(closes):
        bars.append(
            TradeBar(
                timeframe="15m",
                time=f"2025-03-31T10:{index * 5:02d}:00",
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=200 + index * 5,
            )
        )
    return bars


class StubKiwoomClient:
    async def get_account_summary(self) -> AccountSummary:
        return AccountSummary(
            total_evaluation_amount=1_000_000,
            total_profit_loss=0,
            total_profit_rate=0.0,
            holdings_count=0,
            deposit=1_000_000,
            estimated_assets=1_000_000,
            updated_at=datetime(2026, 4, 2, 9, 0, tzinfo=SEOUL),
        )

    async def get_holdings(self):
        return type("Holdings", (), {"items": []})()

    async def get_stock_quote(self, symbol: str) -> StockQuote:
        return StockQuote(
            symbol=symbol,
            name="Samsung Electronics",
            current_price=151,
            previous_close=149,
            diff_from_previous_close=2,
            change_rate=1.2,
            volume=100_000,
            open_price=149,
            high_price=152,
            low_price=148,
            updated_at=datetime(2026, 4, 2, 10, 0, tzinfo=SEOUL),
        )

    async def get_stock_metadata(self, symbol: str) -> StockSearchItem:
        return StockSearchItem(
            symbol=symbol,
            name="Samsung Electronics",
            market_code="0",
            market_name="KOSPI",
            last_price=151,
        )

    async def find_company_name(self, symbol: str) -> str:
        return "Samsung Electronics"


class StubScanner:
    last_source = "test"

    def __init__(self) -> None:
        self.config = ScannerConfig()

    async def refresh(self, existing):
        return [
            CandidateStock(
                symbol="005930",
                name="Samsung Electronics",
                source="test",
                state=existing.get("005930").state if "005930" in existing else "new",
                last_price=151,
                change_rate=1.2,
            )
        ]


class StubBarBuilder:
    async def get_strategy_bundle(self, symbol: str):
        return {
            "daily": make_daily_bars(),
            "60m": make_60m_bars(),
            "15m": make_trigger_bars(),
            "5m": make_trigger_bars(),
            "weekly": make_daily_bars()[-20:],
        }


def build_engine(settings, logger, monkeypatch) -> SignalEngine:
    config = TradingConfig()
    config.strategy.min_intraday_bars = 20
    config.session.market_open_time = "00:00"
    config.session.market_close_time = "23:59"
    config.risk.no_new_entry_after = "23:59"
    session_guard = SessionGuard(config.session)
    engine = SignalEngine(
        settings,
        config,
        StubKiwoomClient(),
        StubScanner(),
        StubBarBuilder(),
        PullbackStrategyEngine(config.strategy, config.risk),
        RiskManager(config.risk, session_guard),
        OrderExecutor(settings, config.execution, StubKiwoomClient(), PaperBroker(), logger),
        PositionManager(),
        session_guard,
        logger,
    )
    monkeypatch.setattr(engine, "_save_state", lambda: None)
    engine.state.candidates = {}
    engine.state.signals = []
    engine.state.orders = []
    engine.state.fills = []
    engine.state.positions = {}
    return engine


async def test_candidate_signal_order_state_transition(settings, logger, monkeypatch) -> None:
    engine = build_engine(settings, logger, monkeypatch)

    snapshot = await engine.refresh_now()
    assert len(snapshot.signal_ready) == 1
    assert len(snapshot.queued_signals) == 1
    signal_id = snapshot.queued_signals[0].id

    result = await engine.execute_signal(signal_id)

    assert result["order"]["state"] == "filled"
    assert result["fill"]["symbol"] == "005930"
    assert "005930" in engine.state.positions
    assert engine.state.candidates["005930"].state == "ordered"


async def test_signal_engine_does_not_duplicate_open_entry_signals(settings, logger, monkeypatch) -> None:
    engine = build_engine(settings, logger, monkeypatch)

    first = await engine.refresh_now()
    second = await engine.refresh_now()

    assert len(first.queued_signals) == 1
    assert len(second.queued_signals) == 1
