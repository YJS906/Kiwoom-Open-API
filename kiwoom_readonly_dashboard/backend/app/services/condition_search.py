"""Kiwoom condition-search helpers.

The official condition-search APIs are WebSocket-based (`ka10171`..`ka10174`).
Kiwoom uses a single App Key WebSocket session, so this service avoids opening
another condition-search socket while the main market realtime socket is active.
When that happens it falls back to cached condition results and lets the
scanner use its fallback universe instead of breaking the quote stream.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from app.core.config import Settings
from app.models.trading import ConditionDefinition, now_kr
from app.services.kiwoom_auth import KiwoomAuthService
from app.services.kiwoom_client import normalize_symbol, safe_abs_int, safe_float, safe_int


class ConditionSearchService:
    """Official condition-search client with safe fallbacks."""

    def __init__(
        self,
        settings: Settings,
        auth_service: KiwoomAuthService,
        logger: logging.Logger,
        market_ws_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.auth_service = auth_service
        self.logger = logger.getChild("condition_search")
        self.market_ws_service = market_ws_service
        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None
        self._recent_errors: list[str] = []
        self._cached_conditions: list[ConditionDefinition] = []
        self._cached_rows: list[dict[str, Any]] = []

    async def list_conditions(self) -> list[ConditionDefinition]:
        """Fetch the user's Hero4 condition list using ka10171."""

        if self._ws_conflicts_with_market_stream():
            return list(self._cached_conditions)

        response = await self._send_single_message({"trnm": "CNSRLST"}, expected_trnm="CNSRLST")
        definitions = parse_condition_definitions(response.get("data", []))
        self._cached_conditions = definitions
        self.last_updated_at = now_kr()
        self.last_error = None
        return definitions

    async def resolve_condition(self, condition_name: str) -> ConditionDefinition | None:
        """Resolve a condition name to its sequence number."""

        conditions = await self.list_conditions()
        for item in conditions:
            if item.name == condition_name:
                return item
        return None

    async def search_condition_once(self, seq: str, stex_tp: str = "K") -> list[dict[str, Any]]:
        """Run the official condition-search request (ka10172) once."""

        if self._ws_conflicts_with_market_stream():
            return list(self._cached_rows)

        response = await self._send_single_message(
            {"trnm": "CNSRREQ", "seq": seq, "search_type": "0", "stex_tp": stex_tp},
            expected_trnm="CNSRREQ",
        )
        rows = parse_condition_result_rows(response.get("data", []))
        self._cached_rows = rows
        self.last_updated_at = now_kr()
        self.last_error = None
        return rows

    def get_cached_rows(self) -> list[dict[str, Any]]:
        """Return the most recent condition-search rows."""

        return list(self._cached_rows)

    def get_recent_errors(self) -> list[str]:
        """Return recent condition-search errors."""

        return list(self._recent_errors)

    async def _send_single_message(self, payload: dict[str, Any], expected_trnm: str) -> dict[str, Any]:
        token = await self.auth_service.get_token()
        try:
            async with ws_connect(
                self.settings.kiwoom_ws_url,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=self.settings.kiwoom_timeout_seconds,
            ) as websocket:
                await websocket.send(json.dumps({"trnm": "LOGIN", "token": token}, ensure_ascii=False))
                await self._wait_for_login(websocket)
                await websocket.send(json.dumps(payload, ensure_ascii=False))
                while True:
                    message = json.loads(str(await websocket.recv()))
                    trnm = str(message.get("trnm", ""))
                    if trnm == "PING":
                        await websocket.send(json.dumps(message, ensure_ascii=False))
                        continue
                    if trnm == "SYSTEM":
                        raise RuntimeError(str(message.get("message", "Condition websocket system error.")))
                    if trnm != expected_trnm:
                        continue
                    if str(message.get("return_code", "0")) not in {"0", "None", "null"}:
                        raise RuntimeError(str(message.get("return_msg", "Condition search failed.")))
                    return message
        except Exception as exc:
            self.last_error = str(exc)
            self._recent_errors.append(self.last_error)
            self._recent_errors = self._recent_errors[-10:]
            raise

    async def _wait_for_login(self, websocket: Any) -> None:
        while True:
            message = json.loads(str(await websocket.recv()))
            trnm = str(message.get("trnm", ""))
            if trnm == "PING":
                await websocket.send(json.dumps(message, ensure_ascii=False))
                continue
            if trnm != "LOGIN":
                raise RuntimeError(f"Unexpected condition websocket handshake: {trnm}")
            if str(message.get("return_code", "0")) not in {"0", "None", "null"}:
                raise RuntimeError(str(message.get("return_msg", "Condition websocket login failed.")))
            return

    def _ws_conflicts_with_market_stream(self) -> bool:
        """Avoid opening a second Kiwoom upstream socket while quotes are streaming."""

        if self.market_ws_service is None:
            return False
        connected, status, _, _ = self.market_ws_service.get_connection_state()
        if connected or status not in {"idle", "disconnected"}:
            if self.last_error != "Condition search deferred while market WebSocket is active.":
                self.last_error = "Condition search deferred while market WebSocket is active."
                self._recent_errors.append(self.last_error)
                self._recent_errors = self._recent_errors[-10:]
            return True
        return False


def parse_condition_definitions(values: Iterable[Any]) -> list[ConditionDefinition]:
    """Parse ka10171 response rows into typed definitions."""

    items: list[ConditionDefinition] = []
    for row in values:
        if isinstance(row, dict):
            seq = str(row.get("seq", "")).strip()
            name = str(row.get("name", "")).strip()
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            seq = str(row[0]).strip()
            name = str(row[1]).strip()
        else:
            continue
        if seq and name:
            items.append(ConditionDefinition(seq=seq, name=name))
    return items


def parse_condition_result_rows(values: Iterable[Any]) -> list[dict[str, Any]]:
    """Parse ka10172 search results using the documented output field order."""

    rows: list[dict[str, Any]] = []
    for row in values:
        parsed: dict[str, Any] | None = None
        if isinstance(row, dict):
            parsed = {
                "symbol": normalize_symbol(
                    str(
                        row.get("9001")
                        or row.get("jmcode")
                        or row.get("stk_cd")
                        or row.get("symbol")
                        or ""
                    )
                ),
                "name": str(row.get("302") or row.get("name") or ""),
                "current_price": safe_abs_int(row.get("10") or row.get("cur_prc")),
                "diff_from_previous_close": safe_int(row.get("11") or row.get("pred_pre")),
                "change_rate": safe_float(row.get("12") or row.get("flu_rt")),
                "volume": safe_abs_int(row.get("13") or row.get("trde_qty")),
                "open_price": safe_abs_int(row.get("16") or row.get("open_pric")),
                "high_price": safe_abs_int(row.get("17") or row.get("high_pric")),
                "low_price": safe_abs_int(row.get("18") or row.get("low_pric")),
            }
        elif isinstance(row, (list, tuple)):
            values_list = list(row)
            parsed = {
                "symbol": normalize_symbol(str(values_list[0] if len(values_list) > 0 else "")),
                "name": str(values_list[1] if len(values_list) > 1 else ""),
                "current_price": safe_abs_int(values_list[2] if len(values_list) > 2 else 0),
                "diff_from_previous_close": safe_int(values_list[4] if len(values_list) > 4 else 0),
                "change_rate": safe_float(values_list[5] if len(values_list) > 5 else 0.0),
                "volume": safe_abs_int(values_list[6] if len(values_list) > 6 else 0),
                "open_price": safe_abs_int(values_list[7] if len(values_list) > 7 else 0),
                "high_price": safe_abs_int(values_list[8] if len(values_list) > 8 else 0),
                "low_price": safe_abs_int(values_list[9] if len(values_list) > 9 else 0),
            }
        if parsed and parsed["symbol"]:
            rows.append(parsed)
    return rows

