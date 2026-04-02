"""Realtime 52-week-high lookup using Kiwoom REST ka10016."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.models.schemas import RealtimeHigh52Item, RealtimeHigh52Response
from app.services.cache import TTLCache
from app.services.kiwoom_auth import KiwoomAuthError, KiwoomAuthService
from app.services.kiwoom_client import now_kr, safe_abs_int, safe_float, safe_int


class RealtimeHigh52Service:
    """Fetch the official 52-week-high universe through ka10016."""

    def __init__(
        self,
        settings: Settings,
        auth_service: KiwoomAuthService | None,
        cache: TTLCache,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.auth_service = auth_service
        self.cache = cache
        self.logger = logger.getChild("realtime_high52")
        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None

    async def get_snapshot(
        self,
        market: Literal["all", "kospi", "kosdaq"] = "all",
    ) -> RealtimeHigh52Response:
        """Return realtime 52-week-high items or a clear availability reason."""

        reason = self._availability_reason()
        if reason is not None:
            return self._response(
                status="unavailable",
                source="kiwoom_rest",
                reason=reason,
                items=[],
            )

        cache_key = f"realtime_high52:{self.settings.kiwoom_market_env}:{market}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            items = await self._request_new_highs(market)
            if not items and self.settings.kiwoom_market_env == "mock":
                response = self._response(
                    status="unavailable",
                    source="kiwoom_rest",
                    reason=(
                        "Current dashboard is using the Kiwoom mock environment. "
                        "The official ka10016 endpoint returned an empty list in mock, "
                        "so it cannot mirror Hero4's live 52-week-high screen."
                    ),
                    items=[],
                )
            elif not items and self._is_pre_market():
                response = self._response(
                    status="ok",
                    source="kiwoom_rest",
                    reason=(
                        f"As of {now_kr().strftime('%Y-%m-%d %H:%M:%S %Z')}, the Korean cash market "
                        "has not opened yet. The realtime 52-week-high list can be empty before "
                        "the session starts."
                    ),
                    items=[],
                )
            else:
                response = self._response(
                    status="ok",
                    source="kiwoom_rest",
                    reason=None,
                    items=items,
                )
            self.cache.set(cache_key, response, 30)
            self.last_error = None
            self.last_updated_at = response.updated_at
            return response
        except Exception as exc:
            self.last_error = str(exc)
            self.last_updated_at = now_kr()
            stale = self.cache.get(cache_key)
            if stale is not None:
                stale.reason = (
                    f"Showing cached 52-week-high list after Kiwoom error: {type(exc).__name__}: {exc}"
                )
                stale.status = "error"
                return stale
            self.logger.warning("Realtime 52-week-high lookup failed: %s", exc)
            return self._response(
                status="error",
                source="kiwoom_rest",
                reason=str(exc),
                items=[],
            )

    def _availability_reason(self) -> str | None:
        """Return a user-facing reason when live market lookup is unavailable."""

        if self.auth_service is None:
            if self.settings.kiwoom_market_env == "production":
                return (
                    "KIWOOM_MARKET_ENV is set to production, but the dedicated read-only "
                    "market credentials are still missing. Add KIWOOM_MARKET_APP_KEY and "
                    "KIWOOM_MARKET_SECRET_KEY in .env."
                )
            return (
                "Live 52-week-high lookup is not configured. "
                "Add KIWOOM_MARKET_ENV=production together with "
                "KIWOOM_MARKET_APP_KEY and KIWOOM_MARKET_SECRET_KEY in .env."
            )

        if self.settings.kiwoom_market_env != "production":
            return (
                "Current dashboard is configured with KIWOOM_MARKET_ENV=mock. "
                "Hero4's live 52-week-high universe requires a production read-only market key."
            )

        return None

    async def _request_new_highs(self, market: Literal["all", "kospi", "kosdaq"]) -> list[RealtimeHigh52Item]:
        """Call the official ka10016 REST API."""

        if self.auth_service is None:
            return []

        token = await self.auth_service.get_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "ka10016",
        }
        body = {
            "mrkt_tp": {"all": "000", "kospi": "001", "kosdaq": "101"}[market],
            "ntl_tp": "1",
            "high_low_close_tp": "1",
            "stk_cnd": "0",
            "trde_qty_tp": "00000",
            "crd_cnd": "0",
            "updown_incls": "0",
            "dt": "250",
            "stex_tp": "1",
        }
        url = f"{self.settings.kiwoom_market_rest_base_url}/api/dostk/stkinfo"
        async with httpx.AsyncClient(timeout=self.settings.kiwoom_timeout_seconds) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError, KiwoomAuthError) as exc:
                raise RuntimeError(f"Kiwoom ka10016 request failed: {exc}") from exc

        if str(payload.get("return_code", "0")) not in {"0", "None", "null"}:
            raise RuntimeError(str(payload.get("return_msg", "Kiwoom ka10016 failed.")))

        rows = payload.get("ntl_pric") or []
        return [self._parse_row(row) for row in rows if str(row.get("stk_cd", "")).strip()]

    def _parse_row(self, row: dict[str, Any]) -> RealtimeHigh52Item:
        """Parse one ka10016 row."""

        return RealtimeHigh52Item(
            symbol=str(row.get("stk_cd", "")).replace("KRX:", "").replace("A", "").strip(),
            name=str(row.get("stk_nm", "")),
            current_price=safe_abs_int(row.get("cur_prc")),
            diff_from_previous_close=safe_int(row.get("pred_pre")),
            change_rate=safe_float(row.get("flu_rt")),
            volume=safe_abs_int(row.get("trde_qty")),
            best_ask=safe_abs_int(row.get("sel_bid")) or None,
            best_bid=safe_abs_int(row.get("buy_bid")) or None,
            high_price=safe_abs_int(row.get("high_pric")) or None,
            low_price=safe_abs_int(row.get("low_pric")) or None,
            market_name=None,
        )

    def _is_pre_market(self) -> bool:
        """Return True before the regular KRX continuous session opens."""

        current = now_kr()
        return (current.hour, current.minute) < (9, 0)

    def _response(
        self,
        *,
        status: Literal["ok", "unavailable", "error"],
        source: str,
        reason: str | None,
        items: list[RealtimeHigh52Item],
    ) -> RealtimeHigh52Response:
        updated_at = now_kr()
        return RealtimeHigh52Response(
            status=status,
            source=source,
            environment=self.settings.kiwoom_market_env,
            reason=reason,
            items=items,
            updated_at=updated_at,
        )
