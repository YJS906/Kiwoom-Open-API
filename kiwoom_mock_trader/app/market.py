"""Market data services backed by Kiwoom REST API."""

from __future__ import annotations

import logging

from app.client import KiwoomRESTClient
from app.models import DailyCandle, StockBasicInfo
from app.utils import (
    format_quote_symbol,
    normalize_symbol,
    safe_abs_int,
    safe_float,
    safe_int,
    today_yyyymmdd,
)


class MarketService:
    """Read current quote and daily chart data."""

    STOCK_INFO_PATH = "/api/dostk/stkinfo"
    CHART_PATH = "/api/dostk/chart"

    def __init__(self, client: KiwoomRESTClient, logger: logging.Logger) -> None:
        self.client = client
        self.logger = logger.getChild("market")

    def get_basic_info(self, symbol: str, exchange: str) -> StockBasicInfo:
        """Fetch a single stock snapshot using ka10001."""

        result = self._post_market_request(
            path=self.STOCK_INFO_PATH,
            api_id="ka10001",
            symbol=symbol,
            exchange=exchange,
        )
        data = result.body
        current_price = safe_abs_int(data.get("cur_prc"))
        diff = safe_int(data.get("pred_pre"))
        previous_close = current_price - diff if current_price else 0
        return StockBasicInfo(
            symbol=symbol,
            name=data.get("stk_nm", symbol),
            exchange=exchange,
            current_price=current_price,
            previous_close=previous_close,
            diff_from_previous_close=diff,
            change_rate=safe_float(data.get("flu_rt")),
            volume=safe_abs_int(data.get("trde_qty")),
            raw=data,
        )

    def get_daily_candles(
        self,
        symbol: str,
        exchange: str,
        limit: int = 30,
        base_date: str | None = None,
    ) -> list[DailyCandle]:
        """Fetch daily candles using ka10081, following continuation keys when needed."""

        base_date = base_date or today_yyyymmdd(self.client.settings.trading.timezone)
        body = {
            "stk_cd": format_quote_symbol(exchange, symbol),
            "base_dt": base_date,
            "upd_stkpc_tp": "1",
        }

        candles: list[DailyCandle] = []
        next_key: str | None = None
        while len(candles) < limit:
            if next_key:
                result = self.client.post(
                    path=self.CHART_PATH,
                    api_id="ka10081",
                    body=body,
                    continuation_key=next_key,
                )
            else:
                result = self._post_market_request(
                    path=self.CHART_PATH,
                    api_id="ka10081",
                    symbol=symbol,
                    exchange=exchange,
                    extra_body={"base_dt": base_date, "upd_stkpc_tp": "1"},
                )
            rows = result.body.get("stk_dt_pole_chart_qry", []) or []
            if not rows:
                break

            for row in rows:
                candles.append(
                    DailyCandle(
                        trade_date=str(row.get("dt", "")),
                        open_price=safe_abs_int(row.get("open_pric")),
                        high_price=safe_abs_int(row.get("high_pric")),
                        low_price=safe_abs_int(row.get("low_pric")),
                        close_price=safe_abs_int(row.get("cur_prc")),
                        volume=safe_abs_int(row.get("trde_qty")),
                        turnover=safe_abs_int(row.get("trde_prica")),
                        raw=row,
                    )
                )
                if len(candles) >= limit:
                    break

            if not result.cont_yn or not result.next_key:
                break
            next_key = result.next_key

        candles.sort(key=lambda item: item.trade_date)
        return candles[-limit:]

    def _post_market_request(
        self,
        *,
        path: str,
        api_id: str,
        symbol: str,
        exchange: str,
        extra_body: dict[str, str] | None = None,
    ):
        """Call the documented code format first, then retry with a bare KRX code if needed."""

        stock_code = self._select_primary_stock_code(exchange=exchange, symbol=symbol)
        primary_body = {"stk_cd": stock_code, **(extra_body or {})}
        result = self.client.post(path=path, api_id=api_id, body=primary_body)
        if self._has_market_data(result.body):
            return result

        # Inference from actual mock responses: some KRX endpoints return an empty
        # success payload for `KRX:005930` but return data for bare `005930`.
        if exchange == "KRX" and stock_code != normalize_symbol(symbol):
            fallback_body = {"stk_cd": normalize_symbol(symbol), **(extra_body or {})}
            fallback = self.client.post(path=path, api_id=api_id, body=fallback_body)
            if self._has_market_data(fallback.body):
                self.logger.warning(
                    "Market data endpoint %s returned an empty payload for %s and succeeded on bare code fallback.",
                    api_id,
                    primary_body["stk_cd"],
                )
                return fallback
        return result

    @staticmethod
    def _has_market_data(body: dict) -> bool:
        """Detect whether quote/chart responses contain usable values."""

        if safe_abs_int(body.get("cur_prc")) > 0:
            return True
        rows = body.get("stk_dt_pole_chart_qry") or []
        if not rows:
            return False
        first = rows[0]
        return bool(first.get("dt")) and safe_abs_int(first.get("cur_prc")) > 0

    def _select_primary_stock_code(self, *, exchange: str, symbol: str) -> str:
        """Choose the code format that works best for the current environment."""

        if self.client.settings.environment.lower() == "mock" and exchange == "KRX":
            return normalize_symbol(symbol)
        return format_quote_symbol(exchange, symbol)
