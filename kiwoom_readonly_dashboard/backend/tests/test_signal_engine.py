"""Tests for signal generation and manual paper execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.schemas import AccountSummary, HoldingItem, StockQuote, StockSearchItem
from app.models.trading import CandidateStock, ScannerConfig, SessionState, TradeBar, TradingConfig
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
    for index in range(220):
        close = 100 + (index // 5)
        bars.append(
            TradeBar(
                timeframe="daily",
                time=f"2025-01-{(index % 28) + 1:02d}",
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=1100 + (index % 7) * 20,
            )
        )

    staged_closes = [
        138,
        139,
        139,
        140,
        140,
        141,
        141,
        142,
        142,
        143,
        143,
        144,
        144,
        145,
        145,
        146,
        146,
        147,
        147,
        148,
        149,
        149,
        150,
        150,
        151,
        151,
        152,
        152,
        153,
        153,
        154,
        154,
        155,
        155,
        156,
        156,
        157,
        157,
        158,
        158,
    ]

    for offset, close in enumerate(staged_closes):
        absolute_index = 220 + offset
        high = close + 1
        volume = 1300 + (offset % 5) * 30
        if offset == 20:
            high = 150
            close = 149
            volume = 4200
        bars.append(
            TradeBar(
                timeframe="daily",
                time=f"2025-02-{(absolute_index % 28) + 1:02d}",
                open=close - 1,
                high=high,
                low=close - 2,
                close=close,
                volume=volume,
            )
        )
    return bars


def make_60m_bars() -> list[TradeBar]:
    prices = [
        120,
        123,
        126,
        129,
        132,
        136,
        140,
        144,
        148,
        152,
        156,
        160,
        158,
        156,
        154,
        152,
        150,
        149,
        150,
        151,
        152,
        153,
        154,
        155,
    ]
    bars: list[TradeBar] = []
    for index, close in enumerate(prices):
        bars.append(
            TradeBar(
                timeframe="60m",
                time=f"2025-03-31T{9 + (index % 8):02d}:00:00",
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=1500 if index <= 11 else 500,
            )
        )
    return bars


def make_trigger_bars() -> list[TradeBar]:
    closes = [149, 149, 150, 150, 151, 151, 150, 151, 152, 152, 153, 154]
    bars: list[TradeBar] = []
    for index, close in enumerate(closes):
        open_price = close - 1 if index == len(closes) - 1 else close
        bars.append(
            TradeBar(
                timeframe="15m",
                time=f"2025-03-31T10:{index * 5:02d}:00",
                open=open_price,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=220 + index * 10,
            )
        )
    return bars


class StubKiwoomClient:
    def __init__(self, holdings: list[HoldingItem] | None = None) -> None:
        self._holdings = holdings or []

    async def get_account_summary(self) -> AccountSummary:
        return AccountSummary(
            total_evaluation_amount=1_000_000,
            total_profit_loss=0,
            total_profit_rate=0.0,
            holdings_count=len(self._holdings),
            deposit=1_000_000,
            estimated_assets=1_000_000,
            updated_at=datetime(2026, 4, 2, 9, 0, tzinfo=SEOUL),
        )

    async def get_holdings(self):
        return type("Holdings", (), {"items": self._holdings})()

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

    def __init__(self, last_price: int = 151, change_rate: float = 1.2) -> None:
        self.config = ScannerConfig()
        self.last_price = last_price
        self.change_rate = change_rate

    async def refresh(self, existing):
        return [
            CandidateStock(
                symbol="005930",
                name="Samsung Electronics",
                source="test",
                state=existing.get("005930").state if "005930" in existing else "new",
                last_price=self.last_price,
                change_rate=self.change_rate,
            )
        ]


class StubBarBuilder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_bars(self, symbol: str, timeframe: str, limit=None):
        self.calls.append(timeframe)
        if timeframe == "daily":
            return make_daily_bars()
        if timeframe == "60m":
            return make_60m_bars()
        if timeframe in {"15m", "5m"}:
            return make_trigger_bars()
        return []

    async def get_strategy_bundle(self, symbol: str):
        return {
            "daily": await self.get_bars(symbol, "daily"),
            "60m": await self.get_bars(symbol, "60m"),
            "15m": await self.get_bars(symbol, "15m"),
            "5m": await self.get_bars(symbol, "5m"),
            "weekly": make_daily_bars()[-20:],
        }


def build_engine(
    settings,
    logger,
    monkeypatch,
    config: TradingConfig | None = None,
    bar_builder=None,
    kiwoom_client=None,
    scanner=None,
) -> SignalEngine:
    config = config or TradingConfig()
    config.strategy.min_intraday_bars = 20
    config.session.market_open_time = "00:00"
    config.session.market_close_time = "23:59"
    config.risk.no_new_entry_after = "23:59"
    session_guard = SessionGuard(config.session)
    bar_builder = bar_builder or StubBarBuilder()
    kiwoom_client = kiwoom_client or StubKiwoomClient()
    scanner = scanner or StubScanner()
    engine = SignalEngine(
        settings,
        config,
        kiwoom_client,
        scanner,
        bar_builder,
        PullbackStrategyEngine(config.strategy, config.risk),
        RiskManager(config.risk, session_guard),
        OrderExecutor(settings, config.execution, kiwoom_client, PaperBroker(), logger),
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
    engine.state.session = SessionState()
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


async def test_signal_engine_uses_daily_only_bundle_for_breakout_profile(settings, logger, monkeypatch) -> None:
    config = TradingConfig()
    config.strategy.strategy_profile = "high52_breakout"
    config.session.market_open_time = "00:00"
    config.session.market_close_time = "23:59"
    config.risk.no_new_entry_after = "23:59"
    bar_builder = StubBarBuilder()
    engine = build_engine(settings, logger, monkeypatch, config=config, bar_builder=bar_builder)

    snapshot = await engine.refresh_now()

    assert len(snapshot.queued_signals) == 1
    assert bar_builder.calls == ["daily"]


async def test_signal_engine_resets_paper_state_before_mock_order_mode(settings, logger, monkeypatch) -> None:
    config = TradingConfig()
    config.execution.auto_buy_enabled = True
    engine = build_engine(settings, logger, monkeypatch, config=config)
    await engine.refresh_now()

    assert engine.state.positions
    assert engine.state.orders
    assert engine.state.fills

    engine._reset_paper_runtime_state()  # noqa: SLF001

    assert engine.state.positions == {}
    assert engine.state.orders == []
    assert engine.state.fills == []
    assert engine.state.signals == []
    assert engine.state.session.paper_cash_balance_krw == 0
    assert engine.state.session.daily_new_entries == 0


async def test_signal_engine_syncs_mock_account_holding_and_creates_take_profit_exit(
    settings,
    logger,
    monkeypatch,
) -> None:
    config = TradingConfig()
    config.execution.paper_trading = False
    config.execution.auto_buy_enabled = False
    config.risk.take_profit_pct = 0.04
    holding = HoldingItem(
        symbol="005930",
        name="Samsung Electronics",
        quantity=10,
        available_quantity=10,
        average_price=1000,
        current_price=1045,
        evaluation_profit_loss=450,
        profit_rate=4.5,
        market_name="KOSPI",
    )
    engine = build_engine(
        settings,
        logger,
        monkeypatch,
        config=config,
        kiwoom_client=StubKiwoomClient(holdings=[holding]),
        scanner=StubScanner(last_price=1045, change_rate=4.5),
    )

    snapshot = await engine.refresh_now()

    assert "005930" in engine.state.positions
    position = engine.state.positions["005930"]
    assert position.source == "account"
    assert position.target_price == 1040
    assert position.stop_price == 970
    assert any(
        signal.symbol == "005930"
        and signal.signal_type == "exit"
        and signal.explanation == "Take-profit level was reached."
        for signal in snapshot.queued_signals
    )
