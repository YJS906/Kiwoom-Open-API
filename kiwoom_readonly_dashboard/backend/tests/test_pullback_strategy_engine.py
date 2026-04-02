"""Tests for the pullback strategy engine."""

from __future__ import annotations

from app.models.trading import RiskConfig, StrategyConfig, TradeBar
from app.services.pullback_strategy import PullbackStrategyEngine


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
    closes = [
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
    for index, close in enumerate(closes):
        volume = 1500 if index <= 11 else 500
        bars.append(
            TradeBar(
                timeframe="60m",
                time=f"2025-03-31T{9 + (index % 8):02d}:00:00",
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=volume,
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


def make_box_breakout_daily_bars() -> list[TradeBar]:
    bars: list[TradeBar] = []
    for index in range(90):
        close = 100 + index
        bars.append(
            TradeBar(
                timeframe="daily",
                time=f"2025-04-{(index % 28) + 1:02d}",
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=1200 + (index % 5) * 30,
            )
        )

    box_closes = [188, 189, 190, 189, 190, 191, 190, 191, 190, 191, 190, 191, 190, 191, 190, 191, 190, 191, 190, 191]
    for index, close in enumerate(box_closes):
        bars.append(
            TradeBar(
                timeframe="daily",
                time=f"2025-05-{(index % 28) + 1:02d}",
                open=close - 1,
                high=192,
                low=187,
                close=close,
                volume=1100 + (index % 3) * 25,
            )
        )

    bars.append(
        TradeBar(
            timeframe="daily",
            time="2025-05-21",
            open=191,
            high=196,
            low=190,
            close=195,
            volume=3200,
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
    assert any(level.kind == "support" for level in decision.annotations)


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


def test_pullback_strategy_blocks_without_breakout_volume() -> None:
    daily_bars = make_daily_bars()
    daily_bars[240].volume = 1400
    engine = PullbackStrategyEngine(StrategyConfig(min_intraday_bars=20), RiskConfig())

    decision = engine.evaluate(
        symbol="005930",
        daily_bars=daily_bars,
        bars_60m=make_60m_bars(),
        trigger_bars=make_trigger_bars(),
    )

    assert decision.passed is False
    assert decision.stage == "daily_filter"
    assert "volume" in " ".join(decision.reasons).lower()


def test_pullback_strategy_blocks_when_support_breaks() -> None:
    deep_pullback = make_60m_bars()
    for index in range(12, 18):
        deep_pullback[index].low -= 6
        deep_pullback[index].close -= 4
        deep_pullback[index].open -= 3

    engine = PullbackStrategyEngine(StrategyConfig(min_intraday_bars=20), RiskConfig())
    decision = engine.evaluate(
        symbol="005930",
        daily_bars=make_daily_bars(),
        bars_60m=deep_pullback,
        trigger_bars=make_trigger_bars(),
    )

    assert decision.passed is False
    assert decision.stage == "pullback_filter"
    assert "support" in decision.summary.lower()


def test_high52_breakout_profile_generates_buy_signal() -> None:
    config = StrategyConfig(strategy_profile="high52_breakout", min_intraday_bars=20)
    engine = PullbackStrategyEngine(config, RiskConfig())

    decision = engine.evaluate(
        symbol="005930",
        daily_bars=make_daily_bars(),
        bars_60m=[],
        trigger_bars=[],
    )

    assert decision.passed is True
    assert decision.stage == "buy_signal"
    assert decision.entry_timeframe == "daily"
    assert decision.breakout_price is not None


def test_box_breakout_profile_generates_buy_signal() -> None:
    config = StrategyConfig(
        strategy_profile="box_breakout",
        min_daily_bars=60,
        box_window_days=20,
        box_max_range_pct=0.05,
        box_breakout_volume_multiplier=1.5,
    )
    engine = PullbackStrategyEngine(config, RiskConfig())

    decision = engine.evaluate(
        symbol="005930",
        daily_bars=make_box_breakout_daily_bars(),
        bars_60m=[],
        trigger_bars=[],
    )

    assert decision.passed is True
    assert decision.stage == "buy_signal"
    assert decision.entry_timeframe == "daily"
    assert any(level.kind == "breakout" for level in decision.annotations)
