"""Unit tests for the demo strategy."""

from __future__ import annotations

from app.models import DailyCandle, Holding, StockBasicInfo, StrategySettings
from app.strategy import PreviousCloseDemoStrategy


def test_strategy_generates_buy_signal(settings, logger) -> None:
    """The strategy should buy when price breaks above the configured threshold."""

    strategy = PreviousCloseDemoStrategy(settings.strategy, logger)
    quote = StockBasicInfo(
        symbol="005930",
        name="Samsung Electronics",
        exchange="KRX",
        current_price=102000,
        previous_close=100000,
        diff_from_previous_close=2000,
        change_rate=2.0,
        volume=1000,
    )
    candles = [
        DailyCandle(
            trade_date="20260101",
            open_price=99000,
            high_price=101000,
            low_price=98000,
            close_price=100000,
            volume=1000,
            turnover=100000000,
        ),
        DailyCandle(
            trade_date="20260102",
            open_price=100500,
            high_price=102000,
            low_price=100000,
            close_price=101000,
            volume=1200,
            turnover=110000000,
        ),
    ]

    decision = strategy.decide(
        quote=quote,
        candles=candles,
        holding=None,
        default_order_type="limit",
    )

    assert decision.action == "buy"


def test_strategy_generates_sell_signal_for_stop_loss(settings, logger) -> None:
    """The strategy should sell when price breaks below stop loss."""

    strategy = PreviousCloseDemoStrategy(
        StrategySettings(
            buy_above_prev_close_pct=0.01,
            take_profit_pct=0.03,
            stop_loss_pct=0.02,
        ),
        logger,
    )
    quote = StockBasicInfo(
        symbol="005930",
        name="Samsung Electronics",
        exchange="KRX",
        current_price=97000,
        previous_close=100000,
        diff_from_previous_close=-3000,
        change_rate=-3.0,
        volume=1000,
    )
    candles = [
        DailyCandle(
            trade_date="20260101",
            open_price=99000,
            high_price=101000,
            low_price=98000,
            close_price=100000,
            volume=1000,
            turnover=100000000,
        ),
        DailyCandle(
            trade_date="20260102",
            open_price=100500,
            high_price=102000,
            low_price=100000,
            close_price=101000,
            volume=1200,
            turnover=110000000,
        ),
    ]
    holding = Holding(
        symbol="005930",
        name="Samsung Electronics",
        quantity=1,
        available_quantity=1,
        current_price=97000,
        purchase_price=100000,
        evaluation_profit_loss=-3000,
        profit_rate=-3.0,
    )

    decision = strategy.decide(
        quote=quote,
        candles=candles,
        holding=holding,
        default_order_type="limit",
    )

    assert decision.action == "sell"

