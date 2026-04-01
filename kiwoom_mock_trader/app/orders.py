"""Order placement and fill-status queries."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from app.client import KiwoomRESTClient
from app.exceptions import KiwoomSafetyError
from app.models import AppSettings, OrderRequest, OrderResponse, OrderStatus
from app.utils import (
    is_mock_url,
    normalize_symbol,
    resolve_path,
    safe_abs_int,
    save_json_file,
    today_yyyymmdd,
)


class OrderService:
    """Place buy and sell orders in the mock environment only."""

    ORDER_PATH = "/api/dostk/ordr"
    ACCOUNT_PATH = "/api/dostk/acnt"

    def __init__(
        self,
        settings: AppSettings,
        client: KiwoomRESTClient,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.client = client
        self.logger = logger.getChild("orders")
        self.orders_dir = resolve_path(settings.project_root, settings.runtime.orders_dir)

    def place_order(self, request: OrderRequest, *, dry_run: bool) -> OrderResponse:
        """Place a single order or simulate it when dry_run is enabled."""

        self._ensure_mock_environment()
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        if dry_run:
            response = OrderResponse(
                order_no=f"DRYRUN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                side=request.side,
                symbol=request.symbol,
                quantity=request.quantity,
                order_type=request.order_type,
                price=request.price,
                exchange=request.exchange,
                simulated=True,
                requested_at=timestamp,
                raw={"message": "dry_run enabled; no actual mock order was submitted."},
            )
            self._save_order_response(response)
            self.logger.info(
                "Dry-run order simulated: side=%s symbol=%s qty=%s price=%s",
                request.side,
                request.symbol,
                request.quantity,
                request.price,
            )
            return response

        api_id = "kt10000" if request.side == "buy" else "kt10001"
        payload: dict[str, str] = {
            "dmst_stex_tp": request.exchange,
            "stk_cd": normalize_symbol(request.symbol),
            "ord_qty": str(request.quantity),
            "trde_tp": "0" if request.order_type == "limit" else "3",
        }
        if request.price is not None and request.order_type == "limit":
            payload["ord_uv"] = str(request.price)

        result = self.client.post(path=self.ORDER_PATH, api_id=api_id, body=payload)
        response = OrderResponse(
            order_no=str(result.body.get("ord_no", "")),
            side=request.side,
            symbol=request.symbol,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            exchange=str(result.body.get("dmst_stex_tp", request.exchange)),
            simulated=False,
            requested_at=timestamp,
            raw=result.body,
        )
        self._save_order_response(response)
        return response

    def get_order_statuses(
        self,
        *,
        exchange: str,
        order_date: str | None = None,
        symbol: str | None = None,
        order_no: str | None = None,
        side: str | None = None,
    ) -> list[OrderStatus]:
        """Fetch today's order and fill state using kt00009."""

        body = {
            "ord_dt": order_date or today_yyyymmdd(self.settings.trading.timezone),
            "stk_bond_tp": "1",
            "mrkt_tp": "0",
            "sell_tp": self._status_side_code(side),
            "qry_tp": "0",
            "stk_cd": normalize_symbol(symbol) if symbol else "",
            "fr_ord_no": order_no or "",
            "dmst_stex_tp": exchange or "%",
        }
        result = self.client.post(path=self.ACCOUNT_PATH, api_id="kt00009", body=body)
        rows = result.body.get("acnt_ord_cntr_prst_array", []) or []
        statuses: list[OrderStatus] = []
        for row in rows:
            order_quantity = safe_abs_int(row.get("ord_qty"))
            filled_quantity = safe_abs_int(row.get("cntr_qty"))
            statuses.append(
                OrderStatus(
                    order_no=str(row.get("ord_no", "")),
                    symbol=str(row.get("stk_cd", "")),
                    side=self._normalize_side(row.get("trde_tp")),
                    order_quantity=order_quantity,
                    filled_quantity=filled_quantity,
                    remaining_quantity=max(order_quantity - filled_quantity, 0),
                    order_price=safe_abs_int(row.get("ord_uv")),
                    filled_price=safe_abs_int(row.get("cntr_uv")),
                    accepted_type=str(row.get("acpt_tp", "")),
                    filled_at=str(row.get("cntr_tm", "")) or None,
                    exchange=str(row.get("dmst_stex_tp", "")) or None,
                    raw=row,
                )
            )
        return statuses

    def has_open_order(
        self,
        *,
        statuses: list[OrderStatus],
        symbol: str,
        side: str,
    ) -> bool:
        """Return True when an open order for the same stock and side exists."""

        normalized_symbol = normalize_symbol(symbol)
        for status in statuses:
            if (
                normalize_symbol(status.symbol) == normalized_symbol
                and status.side == side
                and status.remaining_quantity > 0
            ):
                return True
        return False

    def _ensure_mock_environment(self) -> None:
        """Double safety guard for order submission."""

        if not self.settings.safety.use_mock_only:
            raise KiwoomSafetyError("use_mock_only is disabled. Refusing to submit any order.")
        if not is_mock_url(self.settings.rest_base_url):
            raise KiwoomSafetyError(
                "REST base URL is not the documented mock host. Refusing to submit any order."
            )

    def _save_order_response(self, response: OrderResponse) -> None:
        """Save every order response under .runtime/orders/YYYYMMDD."""

        day_dir = Path(self.orders_dir) / datetime.now().strftime("%Y%m%d")
        filename = f"{response.requested_at.replace(':', '-').replace('T', '_')}_{response.side}_{response.symbol}.json"
        save_json_file(day_dir / filename, response.model_dump())

    @staticmethod
    def _status_side_code(side: str | None) -> str:
        if side == "sell":
            return "1"
        if side == "buy":
            return "2"
        return "0"

    @staticmethod
    def _normalize_side(value: object) -> str:
        text = str(value or "")
        if "매수" in text or text == "2":
            return "buy"
        if "매도" in text or text == "1":
            return "sell"
        return text.lower()
