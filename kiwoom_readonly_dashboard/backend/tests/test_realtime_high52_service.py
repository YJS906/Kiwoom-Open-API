"""Tests for the realtime 52-week-high service."""

from __future__ import annotations

from app.core.config import Settings
from app.services.cache import TTLCache
from app.services.kiwoom_auth import KiwoomAuthService
from app.services.realtime_high52 import RealtimeHigh52Service


async def test_realtime_high52_returns_unavailable_in_mock(settings, logger) -> None:
    service = RealtimeHigh52Service(
        settings,
        auth_service=None,
        cache=TTLCache(),
        logger=logger,
    )

    response = await service.get_snapshot()

    assert response.status == "unavailable"
    assert response.environment == "mock"
    assert response.items == []
    assert response.reason is not None


async def test_realtime_high52_parses_kiwoom_rows(logger) -> None:
    settings = Settings(
        APP_NAME="Test Dashboard",
        APP_ENV="test",
        KIWOOM_ENV="mock",
        KIWOOM_APP_KEY="test-app-key",
        KIWOOM_SECRET_KEY="test-secret-key",
        KIWOOM_ACCOUNT_NO="1234567890",
        KIWOOM_MARKET_ENV="production",
        KIWOOM_MARKET_APP_KEY="live-key",
        KIWOOM_MARKET_SECRET_KEY="live-secret",
        NAVER_CLIENT_ID="",
        NAVER_CLIENT_SECRET="",
    )
    service = RealtimeHigh52Service(
        settings,
        auth_service=KiwoomAuthService(settings, logger),
        cache=TTLCache(),
        logger=logger,
    )

    async def fake_request_new_highs(market: str):
        assert market == "all"
        return [
            service._parse_row(
                {
                    "stk_cd": "KRX:005930",
                    "stk_nm": "삼성전자",
                    "cur_prc": "+76500",
                    "pred_pre": "+1200",
                    "flu_rt": "+1.59",
                    "trde_qty": "1234567",
                    "sel_bid": "76600",
                    "buy_bid": "76500",
                    "high_pric": "77000",
                    "low_pric": "75200",
                }
            )
        ]

    service._request_new_highs = fake_request_new_highs  # type: ignore[method-assign]
    response = await service.get_snapshot()

    assert response.status == "ok"
    assert len(response.items) == 1
    assert response.items[0].symbol == "005930"
    assert response.items[0].current_price == 76500
    assert response.items[0].best_ask == 76600
