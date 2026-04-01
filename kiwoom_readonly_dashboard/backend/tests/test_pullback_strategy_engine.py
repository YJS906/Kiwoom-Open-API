"""Tests for the pullback strategy engine."""

from __future__ import annotations

from app.models.trading import RiskConfig, StrategyConfig, TradeBar
from app.services.pullback_strategy import PullbackStrategyEngine


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
        volume = 1200 if index <= 10 else 500
        bars.append(
            TradeBar(
                timeframe="60m",
                time=f"2025-03-31T{9 + (index % 8):02d}:00:00",
                open=close - 2,
                high=close + 2,
                low=close - 4,
                close=close,
                volume=volume,
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


def test_pullback_strategy_generates_buy_signal() -> None:
    engine = PullbackStrategyEngine(StrategyConfig(min_intraday_bars=20), RiskConfig())

    decision = engine.evaluate(
        symbol="005930",
        daily_bars=make_daily_bars(),
        bars_60m=make_60m_bars(),
        trigger_bars=make_trigger_bars(),
    )

    assert decision.passed is True
    assert decision.stage == "buy_signal"
    assert decision.entry_price is not None
    assert decision.stop_price is not None
    assert decision.target_price is not None


def test_pullback_strategy_blocks_when_data_is_short() -> None:
    engine = PullbackStrategyEngine(StrategyConfig(min_intraday_bars=20), RiskConfig())

    decision = engine.evaluate(
        symbol="005930",
        daily_bars=make_daily_bars()[:20],
        bars_60m=make_60m_bars()[:10],
        trigger_bars=make_trigger_bars()[:5],
    )

    assert decision.passed is False
    assert decision.stage == "insufficient_data"
