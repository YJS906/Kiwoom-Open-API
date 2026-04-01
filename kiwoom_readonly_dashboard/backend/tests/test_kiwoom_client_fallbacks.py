"""Kiwoom client fallback and parsing tests."""

from __future__ import annotations

from app.services.cache import TTLCache
from app.services.kiwoom_auth import KiwoomAuthService
from app.services.kiwoom_client import (
    KiwoomClientService,
    KiwoomRequestError,
    KiwoomResponse,
    filter_usable_chart_rows,
    format_intraday,
)


async def test_filter_usable_chart_rows_drops_blank_placeholder_rows() -> None:
    daily_rows = [
        {"dt": "", "cur_prc": ""},
        {"dt": "20260401", "cur_prc": "444500"},
    ]
    minute_rows = [
        {"cntr_tm": "", "cur_prc": ""},
        {"cntr_tm": "20260401153000", "cur_prc": "+444500"},
    ]

    assert filter_usable_chart_rows(daily_rows, "stk_dt_pole_chart_qry") == [daily_rows[1]]
    assert filter_usable_chart_rows(minute_rows, "stk_min_pole_chart_qry") == [minute_rows[1]]


async def test_get_orderbook_supports_rest_th_suffixes(settings, logger) -> None:
    client = KiwoomClientService(settings, KiwoomAuthService(settings, logger), TTLCache(), logger)

    async def fake_post_with_symbol_fallback(*args, **kwargs) -> KiwoomResponse:
        return KiwoomResponse(
            body={
                "sel_1th_pre_bid": "445000",
                "sel_1th_pre_req": "1200",
                "sel_1th_pre_req_pre": "-10",
                "buy_1th_pre_bid": "444500",
                "buy_1th_pre_req": "1500",
                "buy_1th_pre_req_pre": "25",
                "tot_sel_req": "12000",
                "tot_buy_req": "16000",
                "bid_req_base_tm": "153000",
            },
            headers={},
        )

    client._post_with_symbol_fallback = fake_post_with_symbol_fallback  # type: ignore[method-assign]
    snapshot = await client.get_orderbook("009150")

    assert snapshot.asks[0].price == 445000
    assert snapshot.asks[0].quantity == 1200
    assert snapshot.bids[0].price == 444500
    assert snapshot.bids[0].quantity == 1500
    assert snapshot.total_ask_quantity == 12000
    assert snapshot.total_bid_quantity == 16000


async def test_get_daily_bars_uses_stale_cache_after_rate_limit(settings, logger) -> None:
    client = KiwoomClientService(settings, KiwoomAuthService(settings, logger), TTLCache(), logger)
    calls = {"count": 0}

    async def fake_collect(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return [
                {
                    "dt": "20260401",
                    "open_pric": "435000",
                    "high_pric": "451000",
                    "low_pric": "430000",
                    "cur_prc": "444500",
                    "trde_qty": "581173",
                }
            ]
        raise KiwoomRequestError("HTTP error 429 for ka10081")

    client._collect_chart_rows_with_symbol_fallback = fake_collect  # type: ignore[method-assign]

    first = await client.get_daily_bars("009150", limit=5)
    second = await client.get_daily_bars("009150", limit=5)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].close == 444500


def test_format_intraday_supports_full_timestamp_payloads() -> None:
    assert format_intraday("153000") == "15:30"
    assert format_intraday("20260401153000") == "15:30"


def test_parse_minute_rows_uses_date_from_full_timestamp(settings, logger) -> None:
    client = KiwoomClientService(settings, KiwoomAuthService(settings, logger), TTLCache(), logger)

    bars = client._parse_minute_rows(
        [
            {
                "cntr_tm": "20260401153000",
                "open_pric": "+444500",
                "high_pric": "+445000",
                "low_pric": "+444000",
                "cur_prc": "+444500",
                "trde_qty": "18697",
            }
        ],
        base_dt="2026-04-02",
    )

    assert bars[0].time == "2026-04-01T15:30:00"
