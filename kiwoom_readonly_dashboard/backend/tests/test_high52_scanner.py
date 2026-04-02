"""Tests for the 52-week-high scanner source selection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.schemas import RealtimeHigh52Item, RealtimeHigh52Response
from app.models.trading import ScannerConfig
from app.services.high52_scanner import High52Scanner


SEOUL = timezone(timedelta(hours=9))


class StubConditionSearch:
    async def resolve_condition(self, condition_name: str):
        raise AssertionError("Condition search should not run when realtime_high52 already has items.")

    async def search_condition_once(self, seq: str):
        raise AssertionError("Condition search should not run when realtime_high52 already has items.")


class StubKiwoomClient:
    async def get_stock_metadata(self, symbol: str):
        return None

    async def get_stock_quote(self, symbol: str):
        raise AssertionError("Fallback quotes should not be used in the realtime_high52 path.")


class StubRealtimeHigh52:
    async def get_snapshot(self, market: str = "all") -> RealtimeHigh52Response:
        return RealtimeHigh52Response(
            status="ok",
            source="kiwoom_rest",
            environment="production",
            items=[
                RealtimeHigh52Item(
                    symbol="111111",
                    name="Alpha",
                    current_price=10_000,
                    diff_from_previous_close=200,
                    change_rate=2.0,
                    volume=50_000,
                ),
                RealtimeHigh52Item(
                    symbol="222222",
                    name="Beta",
                    current_price=20_000,
                    diff_from_previous_close=500,
                    change_rate=4.0,
                    volume=150_000,
                ),
                RealtimeHigh52Item(
                    symbol="333333",
                    name="Gamma",
                    current_price=30_000,
                    diff_from_previous_close=150,
                    change_rate=1.0,
                    volume=80_000,
                ),
            ],
            updated_at=datetime(2026, 4, 2, 9, 30, tzinfo=SEOUL),
        )


async def test_scanner_prefers_realtime_high52_candidates(logger) -> None:
    scanner = High52Scanner(
        ScannerConfig(source_mode="realtime_first", max_realtime_candidates=2),
        StubConditionSearch(),
        StubKiwoomClient(),
        StubRealtimeHigh52(),
        logger,
    )

    candidates = await scanner.refresh({})

    assert scanner.last_source == "realtime_high52"
    assert [candidate.symbol for candidate in candidates] == ["222222", "333333"]
    assert all(candidate.source == "realtime_high52" for candidate in candidates)
