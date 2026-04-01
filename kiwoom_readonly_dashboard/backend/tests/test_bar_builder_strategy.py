"""Tests for bar aggregation."""

from __future__ import annotations

from app.models.trading import TradeBar
from app.services.bar_builder import aggregate_bars


def test_aggregate_5m_to_60m_builds_expected_bar() -> None:
    bars = [
        TradeBar(
            timeframe="5m",
            time=f"2026-04-02T09:{minute:02d}:00",
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=100,
        )
        for index, minute in enumerate(range(0, 60, 5))
    ]

    aggregated = aggregate_bars(bars, 60)

    assert len(aggregated) == 1
    assert aggregated[0].open == 100
    assert aggregated[0].close == 111
    assert aggregated[0].high == 112
    assert aggregated[0].low == 99
    assert aggregated[0].volume == 1200

