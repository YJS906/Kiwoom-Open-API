"""Kiwoom WebSocket relay service.

This service keeps a single upstream Kiwoom WebSocket session and broadcasts
realtime packets to any number of connected browser clients. That avoids the
"same App Key session replaced" disconnect loop that happens when each browser
tab opens its own Kiwoom upstream connection.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from app.core.config import Settings
from app.models.schemas import RealtimeEnvelope
from app.services.kiwoom_auth import KiwoomAuthService
from app.services.kiwoom_client import normalize_symbol, now_kr, safe_float, safe_int


class KiwoomWebSocketService:
    """Share one Kiwoom realtime session across all frontend subscribers."""

    def __init__(self, settings: Settings, auth_service: KiwoomAuthService, logger: logging.Logger) -> None:
        self.settings = settings
        self.auth_service = auth_service
        self.logger = logger.getChild("kiwoom_ws")

        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None
        self.last_connected_at: datetime | None = None
        self.market_phase_label: str | None = None

        self._recent_errors: list[str] = []
        self._connected = False
        self._subscriber_symbols: dict[WebSocket, set[str]] = {}
        self._state_lock = asyncio.Lock()
        self._refresh_event = asyncio.Event()
        self._upstream_task: asyncio.Task[None] | None = None
        self._active_symbols: set[str] = set()

    async def relay(self, websocket: WebSocket) -> None:
        """Accept one browser websocket and register its symbol subscription."""

        await websocket.accept()
        try:
            request = await websocket.receive_json()
            symbols = extract_symbols(request.get("symbols", []))
            if not symbols:
                await websocket.send_json(
                    self._envelope("error", None, {"message": "At least one symbol is required."}).model_dump(
                        mode="json"
                    )
                )
                await websocket.close(code=1008)
                return

            await self._register_subscriber(websocket, symbols)
            await self._ensure_upstream_running()
            await self._broadcast_status_to_one(websocket)

            while True:
                payload = await websocket.receive_json()
                action = str(payload.get("action", "subscribe"))

                if action == "ping":
                    await self._broadcast_status_to_one(websocket)
                    continue

                if action != "subscribe":
                    await websocket.send_json(
                        self._envelope(
                            "error",
                            None,
                            {"message": f"Unsupported websocket action: {action}"},
                        ).model_dump(mode="json")
                    )
                    continue

                new_symbols = extract_symbols(payload.get("symbols", []))
                if not new_symbols:
                    await websocket.send_json(
                        self._envelope("error", None, {"message": "At least one symbol is required."}).model_dump(
                            mode="json"
                        )
                    )
                    continue

                await self._update_subscriber(websocket, new_symbols)
                await self._broadcast_status_to_one(websocket)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            self.logger.warning("Frontend websocket client failed: %s", exc)
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    self._envelope("error", None, {"message": str(exc)}).model_dump(mode="json")
                )
                await websocket.close(code=1011)
        finally:
            await self._remove_subscriber(websocket)

    async def shutdown(self) -> None:
        """Clean up the single upstream task on app shutdown."""

        async with self._state_lock:
            task = self._upstream_task
            self._upstream_task = None
            self._subscriber_symbols.clear()
            self._refresh_event.set()

        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _register_subscriber(self, websocket: WebSocket, symbols: set[str]) -> None:
        async with self._state_lock:
            self._subscriber_symbols[websocket] = symbols
            self._refresh_event.set()

    async def _update_subscriber(self, websocket: WebSocket, symbols: set[str]) -> None:
        async with self._state_lock:
            self._subscriber_symbols[websocket] = symbols
            self._refresh_event.set()

    async def _remove_subscriber(self, websocket: WebSocket) -> None:
        async with self._state_lock:
            removed = self._subscriber_symbols.pop(websocket, None)
            if removed is not None:
                self._refresh_event.set()

    async def _ensure_upstream_running(self) -> None:
        async with self._state_lock:
            if self._upstream_task and not self._upstream_task.done():
                return
            self._upstream_task = asyncio.create_task(self._run_upstream(), name="kiwoom-ws-upstream")

    async def _run_upstream(self) -> None:
        """Run exactly one shared upstream websocket session."""

        try:
            while True:
                desired_symbols = await self._get_desired_symbols()
                if not desired_symbols:
                    self._set_connected(False, None)
                    return

                try:
                    await self._run_upstream_session(desired_symbols)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._remember_error(str(exc))
                    self.logger.warning("Realtime upstream reconnecting after error: %s", exc)
                    await self._broadcast(
                        self._envelope(
                            "status",
                            sorted(desired_symbols)[0] if desired_symbols else None,
                            {"connected": False, "detail": str(exc), "reconnecting": True},
                        )
                    )
                    await asyncio.sleep(3)
        finally:
            self._set_connected(False, None)
            async with self._state_lock:
                self._active_symbols.clear()

    async def _run_upstream_session(self, symbols: set[str]) -> None:
        token = await self.auth_service.get_token()
        async with ws_connect(
            self.settings.kiwoom_ws_url,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=self.settings.kiwoom_timeout_seconds,
        ) as upstream:
            await self._login_upstream(upstream, token)
            await upstream.send(json.dumps(self._build_register_message(symbols), ensure_ascii=False))

            self._set_connected(True, None)
            self.last_connected_at = now_kr()
            self._active_symbols = set(symbols)
            await self._broadcast(
                self._envelope(
                    "status",
                    sorted(symbols)[0] if symbols else None,
                    {"connected": True, "detail": "Realtime stream connected."},
                )
            )

            while True:
                receive_task = asyncio.create_task(upstream.recv())
                refresh_task = asyncio.create_task(self._refresh_event.wait())

                done, pending = await asyncio.wait(
                    {receive_task, refresh_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                if refresh_task in done:
                    self._refresh_event.clear()
                    desired_symbols = await self._get_desired_symbols()
                    if not desired_symbols:
                        await upstream.close(code=1000)
                        return
                    if desired_symbols != self._active_symbols:
                        await upstream.close(code=1000)
                        return
                    continue

                try:
                    raw_message = receive_task.result()
                except ConnectionClosed as exc:
                    self._set_connected(False, f"Kiwoom websocket closed: {exc.code}")
                    raise RuntimeError(f"Kiwoom websocket closed: {exc.code}") from exc

                control_status = await self._handle_control_message(upstream, raw_message)
                if control_status == "ping":
                    continue
                if control_status == "system_close":
                    raise RuntimeError("Kiwoom websocket session was replaced by another App Key session.")

                envelopes = self._parse_message(str(raw_message))
                for envelope in envelopes:
                    await self._broadcast(envelope)

    async def _login_upstream(self, upstream: Any, token: str) -> None:
        """Authenticate using the documented LOGIN packet."""

        await upstream.send(json.dumps({"trnm": "LOGIN", "token": token}, ensure_ascii=False))

        while True:
            raw_message = await asyncio.wait_for(upstream.recv(), timeout=self.settings.kiwoom_timeout_seconds)
            try:
                payload = json.loads(str(raw_message))
            except json.JSONDecodeError as exc:
                raise RuntimeError("Kiwoom websocket returned invalid login payload.") from exc

            trnm = str(payload.get("trnm", ""))
            if trnm == "PING":
                await upstream.send(json.dumps(payload, ensure_ascii=False))
                continue

            if trnm != "LOGIN":
                raise RuntimeError(f"Unexpected websocket handshake message: {trnm or 'unknown'}")

            return_code = str(payload.get("return_code", "0"))
            if return_code not in {"0", "None", "null"}:
                raise RuntimeError(str(payload.get("return_msg", "Kiwoom websocket login failed.")))
            return

    async def _handle_control_message(self, upstream: Any, raw_message: Any) -> str | None:
        """Handle PING and SYSTEM packets before realtime parsing."""

        try:
            payload = json.loads(str(raw_message))
        except json.JSONDecodeError:
            return None

        trnm = str(payload.get("trnm", ""))
        if trnm == "PING":
            await upstream.send(json.dumps(payload, ensure_ascii=False))
            return "ping"

        if trnm == "SYSTEM":
            code = str(payload.get("code", ""))
            message = str(payload.get("message", ""))
            if code == "R10001":
                self._remember_error(message)
                await self._broadcast(self._envelope("error", None, {"message": message}))
                return "system_close"
            await self._broadcast(self._envelope("status", None, {"type": trnm, "detail": message}))
            return "system"

        return None

    def _build_register_message(self, symbols: Iterable[str]) -> dict[str, Any]:
        data: list[dict[str, list[str]]] = [{"item": ["000000"], "type": ["0s"]}]
        for symbol in sorted(set(symbols)):
            data.append({"item": [symbol], "type": ["0B", "0D"]})
        return {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": data,
        }

    def _parse_message(self, text: str) -> list[RealtimeEnvelope]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            self._remember_error("Received invalid realtime JSON payload.")
            return [self._envelope("error", None, {"message": "Invalid realtime payload."})]

        trnm = str(payload.get("trnm", ""))
        if trnm in {"LOGIN", "REG", "PING", "SYSTEM"}:
            return []

        return_code = str(payload.get("return_code", "0"))
        if return_code not in {"0", "None", "null"}:
            message = str(payload.get("return_msg", "unknown websocket error"))
            self._remember_error(message)
            return [self._envelope("error", None, {"message": message})]

        entries = payload.get("data", []) or []
        envelopes: list[RealtimeEnvelope] = []
        for entry in entries:
            type_code = str(entry.get("type", ""))
            symbol = normalize_symbol(str(entry.get("item", "") or "")) or None
            values = entry.get("values", {}) or {}

            if type_code == "0B":
                envelopes.append(self._envelope("quote", symbol, parse_quote_values(values)))
            elif type_code == "0D":
                envelopes.append(self._envelope("orderbook", symbol, parse_orderbook_values(values)))
            elif type_code == "0s":
                market_payload = parse_market_status_values(values)
                self.market_phase_label = str(market_payload.get("label") or "")
                envelopes.append(self._envelope("market_status", symbol, market_payload))
            else:
                envelopes.append(
                    self._envelope(
                        "status",
                        symbol,
                        {"type": type_code, "detail": "Unhandled realtime packet."},
                    )
                )

        self.last_updated_at = now_kr()
        return envelopes

    async def _broadcast(self, envelope: RealtimeEnvelope) -> None:
        payload = envelope.model_dump(mode="json")
        subscribers = await self._subscriber_snapshot()
        stale: list[WebSocket] = []

        for websocket, symbols in subscribers:
            if envelope.channel in {"quote", "orderbook"} and envelope.symbol and envelope.symbol not in symbols:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            await self._remove_subscriber(websocket)

    async def _broadcast_status_to_one(self, websocket: WebSocket) -> None:
        desired_symbols = await self._get_desired_symbols()
        detail = self.last_error
        if not desired_symbols and detail is None:
            detail = "No active realtime subscribers."
        await websocket.send_json(
            self._envelope(
                "status",
                sorted(desired_symbols)[0] if desired_symbols else None,
                {"connected": self._connected, "detail": detail, "subscribers": len(self._subscriber_symbols)},
            ).model_dump(mode="json")
        )

    async def _subscriber_snapshot(self) -> list[tuple[WebSocket, set[str]]]:
        async with self._state_lock:
            return list(self._subscriber_symbols.items())

    async def _get_desired_symbols(self) -> set[str]:
        async with self._state_lock:
            symbols: set[str] = set()
            for subscriber_symbols in self._subscriber_symbols.values():
                symbols.update(subscriber_symbols)
            return symbols

    def get_connection_state(self) -> tuple[bool, str, str | None, datetime | None]:
        if not self._subscriber_symbols:
            return False, "idle", self.last_error or "No active realtime subscribers.", self.last_updated_at
        status = "connected" if self._connected else "reconnecting"
        detail = self.last_error or self.market_phase_label
        return self._connected, status, detail, self.last_updated_at

    def get_recent_errors(self) -> list[str]:
        return list(self._recent_errors)

    def _set_connected(self, connected: bool, detail: str | None) -> None:
        self._connected = connected
        self.last_updated_at = now_kr()
        if detail:
            self.last_error = detail
        elif connected:
            self.last_error = None

    def _remember_error(self, message: str) -> None:
        self.last_error = message
        self.last_updated_at = now_kr()
        self._recent_errors.append(message)
        self._recent_errors = self._recent_errors[-10:]

    def _envelope(self, channel: str, symbol: str | None, payload: dict[str, Any]) -> RealtimeEnvelope:
        return RealtimeEnvelope(
            channel=channel,  # type: ignore[arg-type]
            symbol=symbol,
            payload=payload,
            updated_at=now_kr(),
        )


def extract_symbols(values: Iterable[Any]) -> set[str]:
    """Normalize any inbound symbol list from frontend clients."""

    normalized = {normalize_symbol(str(value)) for value in values if normalize_symbol(str(value))}
    return {symbol for symbol in normalized if symbol}


def parse_quote_values(values: dict[str, Any]) -> dict[str, Any]:
    """Parse realtime stock trade fields for the frontend."""

    return {
        "trade_time": format_hhmmss(values.get("20")),
        "current_price": abs(safe_int(values.get("10"))),
        "diff_from_previous_close": safe_int(values.get("11")),
        "change_rate": safe_float(values.get("12")),
        "volume": abs(safe_int(values.get("15"))),
        "accumulated_volume": abs(safe_int(values.get("13"))),
        "open_price": abs(safe_int(values.get("16"))),
        "high_price": abs(safe_int(values.get("17"))),
        "low_price": abs(safe_int(values.get("18"))),
        "best_ask": abs(safe_int(values.get("27"))),
        "best_bid": abs(safe_int(values.get("28"))),
    }


def parse_orderbook_values(values: dict[str, Any]) -> dict[str, Any]:
    """Parse realtime orderbook values into ask/bid levels."""

    asks: list[dict[str, int]] = []
    bids: list[dict[str, int]] = []
    for index in range(1, 6):
        ask_price_key = str(40 + index)
        bid_price_key = str(50 + index)
        ask_qty_key = str(60 + index)
        bid_qty_key = str(70 + index)
        ask_delta_key = str(80 + index)
        bid_delta_key = str(90 + index)
        asks.append(
            {
                "price": abs(safe_int(values.get(ask_price_key))),
                "quantity": abs(safe_int(values.get(ask_qty_key))),
                "delta": safe_int(values.get(ask_delta_key)),
            }
        )
        bids.append(
            {
                "price": abs(safe_int(values.get(bid_price_key))),
                "quantity": abs(safe_int(values.get(bid_qty_key))),
                "delta": safe_int(values.get(bid_delta_key)),
            }
        )

    return {
        "asks": [item for item in asks if item["price"] > 0],
        "bids": [item for item in bids if item["price"] > 0],
        "total_ask_quantity": abs(safe_int(values.get("121"))),
        "total_bid_quantity": abs(safe_int(values.get("125"))),
        "timestamp": format_hhmmss(values.get("21")),
    }


def parse_market_status_values(values: dict[str, Any]) -> dict[str, Any]:
    """Parse market session state values."""

    code = str(values.get("215", ""))
    return {
        "code": code,
        "label": MARKET_STATUS_LABELS.get(code, "알 수 없음"),
        "time": format_hhmmss(values.get("20")),
        "remaining_seconds": abs(safe_int(values.get("214"))),
    }


def format_hhmmss(raw: Any) -> str | None:
    """Format Kiwoom HHMMSS strings into HH:MM:SS."""

    text = str(raw or "").strip()
    if not text:
        return None
    value = text.zfill(6)
    return f"{value[:2]}:{value[2:4]}:{value[4:6]}"


MARKET_STATUS_LABELS = {
    "0": "장시작 전",
    "2": "장 종료, 동시호가 전",
    "3": "장중",
    "4": "장 종료",
    "8": "장 종료, 시간외종가",
    "9": "장 마감",
    "a": "시간외 단일가 매매 시작",
    "b": "시간외 단일가 매매 종료",
    "c": "장전 시간외 종가",
    "d": "장전 시간외 종가 종료",
    "e": "장후 시간외 종가",
    "f": "장후 시간외 종가 종료",
    "o": "장 시작 예정",
    "s": "장 종료 예정",
    "P": "파생 주간장 시작 전",
    "Q": "파생 주간장 중",
    "R": "파생 주간장 종료",
    "S": "파생 야간장 시작 전",
    "T": "파생 야간장 중",
    "U": "파생 야간장 종료",
    "V": "파생 시장 마감",
}
