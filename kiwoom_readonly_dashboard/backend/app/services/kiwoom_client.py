"""Kiwoom REST client service."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.models.schemas import (
    AccountSummary,
    ChartBar,
    ChartResponse,
    HoldingItem,
    HoldingsResponse,
    OrderbookLevel,
    OrderbookSnapshot,
    StockQuote,
    StockSearchItem,
)
from app.services.cache import TTLCache
from app.services.kiwoom_auth import KiwoomAuthError, KiwoomAuthService


SEOUL_TZ = timezone(timedelta(hours=9), name="Asia/Seoul")


class KiwoomRequestError(RuntimeError):
    """Raised when Kiwoom REST responds with an error."""


@dataclass
class KiwoomResponse:
    body: dict[str, Any]
    headers: dict[str, str]
    next_key: str | None = None
    continuation: bool = False


class KiwoomClientService:
    """Read-only Kiwoom REST service for dashboard queries."""

    def __init__(
        self,
        settings: Settings,
        auth_service: KiwoomAuthService,
        cache: TTLCache,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.auth_service = auth_service
        self.cache = cache
        self.logger = logger.getChild("kiwoom_client")
        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None
        self._recent_errors: list[str] = []

    async def verify_account(self) -> list[str]:
        """Verify the configured account exists for the current app key."""

        accounts = await self.get_account_numbers()
        if normalize_symbol(self.settings.kiwoom_account_no) not in {
            normalize_symbol(item) for item in accounts
        }:
            raise KiwoomRequestError(
                "Configured KIWOOM_ACCOUNT_NO was not returned by ka00001."
            )
        return accounts

    async def get_account_numbers(self) -> list[str]:
        """Call ka00001."""

        result = await self._post("/api/dostk/acnt", "ka00001", {})
        value = result.body.get("acctNo")
        if not value:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [chunk.strip() for chunk in re.split(r"[;,]", str(value)) if chunk.strip()]

    async def get_account_summary(self) -> AccountSummary:
        """Combine kt00001 and kt00018 into one summary payload."""

        async def _factory() -> AccountSummary:
            deposit_result = await self._post("/api/dostk/acnt", "kt00001", {"qry_tp": "2"})
            snapshot_result = await self._post(
                "/api/dostk/acnt",
                "kt00018",
                {"qry_tp": "1", "dmst_stex_tp": "KRX"},
            )
            holdings = snapshot_result.body.get("acnt_evlt_remn_indv_tot", []) or []
            return AccountSummary(
                total_evaluation_amount=safe_abs_int(snapshot_result.body.get("tot_evlt_amt")),
                total_profit_loss=safe_int(snapshot_result.body.get("tot_evlt_pl")),
                total_profit_rate=safe_float(snapshot_result.body.get("tot_prft_rt")),
                holdings_count=len([row for row in holdings if safe_abs_int(row.get("rmnd_qty")) > 0]),
                deposit=safe_abs_int(deposit_result.body.get("entr")),
                estimated_assets=safe_abs_int(snapshot_result.body.get("prsm_dpst_aset_amt")),
                updated_at=now_kr(),
            )

        return await self.cache.get_or_set(
            "account_summary",
            self.settings.kiwoom_account_cache_ttl_seconds,
            _factory,
        )

    async def get_holdings(self) -> HoldingsResponse:
        """Return holdings table rows from kt00018."""

        async def _factory() -> HoldingsResponse:
            result = await self._post(
                "/api/dostk/acnt",
                "kt00018",
                {"qry_tp": "1", "dmst_stex_tp": "KRX"},
            )
            rows = result.body.get("acnt_evlt_remn_indv_tot", []) or []
            items = [
                HoldingItem(
                    symbol=normalize_symbol(str(row.get("stk_cd", ""))),
                    name=str(row.get("stk_nm", "")),
                    quantity=safe_abs_int(row.get("rmnd_qty")),
                    available_quantity=safe_abs_int(row.get("trde_able_qty")),
                    average_price=safe_abs_int(row.get("pur_pric")),
                    current_price=safe_abs_int(row.get("cur_prc")),
                    evaluation_profit_loss=safe_int(row.get("evltv_prft")),
                    profit_rate=safe_float(row.get("prft_rt")),
                )
                for row in rows
                if safe_abs_int(row.get("rmnd_qty")) > 0
            ]
            return HoldingsResponse(items=items, updated_at=now_kr())

        return await self.cache.get_or_set(
            "account_holdings",
            self.settings.kiwoom_account_cache_ttl_seconds,
            _factory,
        )

    async def get_stock_universe(self) -> list[StockSearchItem]:
        """Fetch a cached stock universe from ka10099."""

        async def _factory() -> list[StockSearchItem]:
            markets = ["0", "10", "8"]
            items: dict[str, StockSearchItem] = {}
            for market_code in markets:
                result = await self._post(
                    "/api/dostk/stkinfo",
                    "ka10099",
                    {"mrkt_tp": market_code},
                )
                for row in result.body.get("list", []) or []:
                    symbol = normalize_symbol(str(row.get("code", "")))
                    if not symbol:
                        continue
                    items[symbol] = StockSearchItem(
                        symbol=symbol,
                        name=str(row.get("name", "")),
                        market_code=str(row.get("marketCode", market_code)),
                        market_name=str(row.get("marketName", "")),
                        last_price=safe_abs_int(row.get("lastPrice")) or None,
                    )
            return sorted(items.values(), key=lambda item: (item.market_name, item.name))

        return await self.cache.get_or_set(
            "stock_universe",
            self.settings.kiwoom_symbol_cache_ttl_seconds,
            _factory,
        )

    async def search_stocks(self, query: str, limit: int = 20) -> list[StockSearchItem]:
        """Filter the cached stock universe by code or name."""

        query_normalized = query.strip().lower()
        if not query_normalized:
            return []
        universe = await self.get_stock_universe()
        matches = [
            item
            for item in universe
            if query_normalized in item.symbol.lower() or query_normalized in item.name.lower()
        ]
        return matches[:limit]

    async def get_stock_metadata(self, symbol: str) -> StockSearchItem | None:
        """Return cached stock metadata for one symbol."""

        normalized = normalize_symbol(symbol)
        universe = await self.get_stock_universe()
        for item in universe:
            if item.symbol == normalized:
                return item
        return None

    async def get_stock_quote(self, symbol: str) -> StockQuote:
        """Fetch current stock details from ka10001."""

        cache_key = f"quote:{normalize_symbol(symbol)}"

        async def _factory() -> StockQuote:
            result = await self._post_with_symbol_fallback(
                "/api/dostk/stkinfo",
                "ka10001",
                symbol,
            )
            body = result.body
            current_price = safe_abs_int(body.get("cur_prc"))
            diff = safe_int(body.get("pred_pre"))
            previous_close = current_price - diff if current_price else safe_abs_int(body.get("base_pric"))
            return StockQuote(
                symbol=normalize_symbol(symbol),
                name=str(body.get("stk_nm", normalize_symbol(symbol))),
                market_name=self._guess_market_name(symbol),
                current_price=current_price,
                previous_close=previous_close,
                diff_from_previous_close=diff,
                change_rate=safe_float(body.get("flu_rt")),
                volume=safe_abs_int(body.get("trde_qty")),
                open_price=safe_abs_int(body.get("open_pric")),
                high_price=safe_abs_int(body.get("high_pric")),
                low_price=safe_abs_int(body.get("low_pric")),
                best_ask=None,
                best_bid=None,
                updated_at=now_kr(),
            )

        return await self.cache.get_or_set(
            cache_key,
            self.settings.kiwoom_quote_cache_ttl_seconds,
            _factory,
        )

    async def get_orderbook(self, symbol: str) -> OrderbookSnapshot:
        """Fetch orderbook from ka10004."""

        cache_key = f"orderbook:{normalize_symbol(symbol)}"

        async def _factory() -> OrderbookSnapshot:
            result = await self._post_with_symbol_fallback(
                "/api/dostk/mrkcond",
                "ka10004",
                symbol,
            )
            body = result.body
            asks: list[OrderbookLevel] = []
            bids: list[OrderbookLevel] = []
            for level in range(1, 6):
                asks.append(
                    OrderbookLevel(
                        price=pick_first_int(
                            body,
                            [
                                f"sel_{ordinal(level)}_pre_bid",
                                f"sel_{level}",
                                f"ask_{level}",
                                f"ask{level}",
                            ],
                        ),
                        quantity=pick_first_int(
                            body,
                            [
                                f"sel_{ordinal(level)}_pre_req",
                                f"sel_{level}_req",
                                f"ask_qty_{level}",
                                f"askqty{level}",
                            ],
                        ),
                        delta=pick_first_optional_int(
                            body,
                            [
                                f"sel_{ordinal(level)}_pre_req_pre",
                                f"sel_{level}_delta",
                                f"ask_delta_{level}",
                            ],
                        ),
                    )
                )
                bids.append(
                    OrderbookLevel(
                        price=pick_first_int(
                            body,
                            [
                                f"buy_{ordinal(level)}_pre_bid",
                                f"buy_{level}",
                                f"bid_{level}",
                                f"bid{level}",
                            ],
                        ),
                        quantity=pick_first_int(
                            body,
                            [
                                f"buy_{ordinal(level)}_pre_req",
                                f"buy_{level}_req",
                                f"bid_qty_{level}",
                                f"bidqty{level}",
                            ],
                        ),
                        delta=pick_first_optional_int(
                            body,
                            [
                                f"buy_{ordinal(level)}_pre_req_pre",
                                f"buy_{level}_delta",
                                f"bid_delta_{level}",
                            ],
                        ),
                    )
                )

            asks = [level for level in asks if level.price > 0]
            bids = [level for level in bids if level.price > 0]
            return OrderbookSnapshot(
                symbol=normalize_symbol(symbol),
                asks=asks,
                bids=bids,
                total_ask_quantity=safe_abs_int(body.get("tot_sel_req")),
                total_bid_quantity=safe_abs_int(body.get("tot_buy_req")),
                timestamp=str(body.get("bid_req_base_tm", "")) or None,
                updated_at=now_kr(),
            )

        return await self.cache.get_or_set(
            cache_key,
            self.settings.kiwoom_quote_cache_ttl_seconds,
            _factory,
        )

    async def get_chart(
        self,
        symbol: str,
        range_label: str = "3m",
        interval: Literal["day", "minute"] = "day",
    ) -> ChartResponse:
        """Fetch chart bars from ka10081 or ka10080."""

        cache_key = f"chart:{normalize_symbol(symbol)}:{range_label}:{interval}"

        async def _factory() -> ChartResponse:
            if interval == "day":
                bars = await self._get_daily_chart_bars(symbol, range_label)
            else:
                bars = await self._get_minute_chart_bars(symbol, range_label)
            return ChartResponse(
                symbol=normalize_symbol(symbol),
                interval=interval,
                range_label=range_label,
                bars=bars,
                updated_at=now_kr(),
            )

        return await self.cache.get_or_set(
            cache_key,
            self.settings.kiwoom_chart_cache_ttl_seconds,
            _factory,
        )

    async def get_daily_bars(self, symbol: str, limit: int = 260) -> list[ChartBar]:
        """Return daily bars from ka10081 with continuation support."""

        rows = await self._collect_chart_rows_with_symbol_fallback(
            "/api/dostk/chart",
            "ka10081",
            symbol,
            {"base_dt": now_kr().strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
            "stk_dt_pole_chart_qry",
        )
        bars = self._parse_daily_rows(rows)
        bars.sort(key=lambda bar: bar.time)
        return bars[-limit:]

    async def get_weekly_bars(self, symbol: str, limit: int = 104) -> list[ChartBar]:
        """Return weekly bars from ka10082."""

        rows = await self._collect_chart_rows_with_symbol_fallback(
            "/api/dostk/chart",
            "ka10082",
            symbol,
            {"base_dt": now_kr().strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
            "stk_stk_pole_chart_qry",
        )
        bars = self._parse_daily_rows(rows)
        bars.sort(key=lambda bar: bar.time)
        return bars[-limit:]

    async def get_minute_bars(
        self,
        symbol: str,
        minutes: int = 1,
        limit: int = 240,
        base_dt: str | None = None,
    ) -> list[ChartBar]:
        """Return minute bars from ka10080."""

        rows = await self._collect_chart_rows_with_symbol_fallback(
            "/api/dostk/chart",
            "ka10080",
            symbol,
            {
                "tic_scope": str(minutes),
                "upd_stkpc_tp": "1",
                "base_dt": base_dt or now_kr().strftime("%Y%m%d"),
            },
            "stk_min_pole_chart_qry",
        )
        bars = self._parse_minute_rows(rows, base_dt=base_dt or now_kr().strftime("%Y-%m-%d"))
        bars.sort(key=lambda bar: bar.time)
        return bars[-limit:]

    async def _get_daily_chart_bars(self, symbol: str, range_label: str) -> list[ChartBar]:
        days_map = {"1m": 22, "3m": 66, "6m": 132, "1y": 260}
        limit = days_map.get(range_label, 66)
        return await self.get_daily_bars(symbol, limit=limit)

    async def _get_minute_chart_bars(self, symbol: str, range_label: str) -> list[ChartBar]:
        scope_map = {"1m": "1", "3m": "3", "6m": "5", "1y": "15"}
        limit_map = {"1m": 120, "3m": 180, "6m": 240, "1y": 240}
        scope = int(scope_map.get(range_label, "5"))
        limit = limit_map.get(range_label, 180)
        return await self.get_minute_bars(symbol, minutes=scope, limit=limit)

    async def _post_with_symbol_fallback(
        self,
        path: str,
        api_id: str,
        symbol: str,
        extra_body: dict[str, str] | None = None,
    ) -> KiwoomResponse:
        """Try the best-known symbol format for the current environment."""

        candidates = stock_code_candidates(normalize_symbol(symbol), self.settings.kiwoom_env)
        last_response: KiwoomResponse | None = None
        for code in candidates:
            response = await self._post(path, api_id, {"stk_cd": code, **(extra_body or {})})
            last_response = response
            if has_market_payload(response.body):
                return response
        if last_response is None:
            raise KiwoomRequestError(f"No response returned for {api_id}")
        return last_response

    async def _post(
        self,
        path: str,
        api_id: str,
        body: dict[str, Any],
        continuation_key: str | None = None,
        retry_on_auth_error: bool = True,
    ) -> KiwoomResponse:
        """Call a Kiwoom REST endpoint."""

        token = await self.auth_service.get_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,
        }
        if continuation_key:
            headers["cont-yn"] = "Y"
            headers["next-key"] = continuation_key

        url = f"{self.settings.kiwoom_rest_base_url}{path}"
        async with httpx.AsyncClient(timeout=self.settings.kiwoom_timeout_seconds) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401 and retry_on_auth_error:
                    await self.auth_service.get_token(force_refresh=True)
                    return await self._post(
                        path,
                        api_id,
                        body,
                        continuation_key=continuation_key,
                        retry_on_auth_error=False,
                    )
                self.last_error = f"HTTP error {exc.response.status_code} for {api_id}"
                self._remember_error(self.last_error)
                raise KiwoomRequestError(self.last_error) from exc
            except (httpx.HTTPError, KiwoomAuthError) as exc:
                self.last_error = str(exc)
                self._remember_error(self.last_error)
                raise KiwoomRequestError(self.last_error) from exc

        try:
            data = response.json()
        except ValueError as exc:
            self.last_error = f"Invalid JSON response for {api_id}"
            self._remember_error(self.last_error)
            raise KiwoomRequestError(self.last_error) from exc
        self.last_updated_at = now_kr()
        if str(data.get("return_code", "0")) not in {"0", "None", "null"}:
            self.last_error = data.get("return_msg", "unknown Kiwoom error")
            self._remember_error(self.last_error)
            raise KiwoomRequestError(self.last_error)

        return KiwoomResponse(
            body=data,
            headers=dict(response.headers),
            continuation=response.headers.get("cont-yn", "N").upper() == "Y",
            next_key=response.headers.get("next-key"),
        )

    async def _collect_chart_rows_with_symbol_fallback(
        self,
        path: str,
        api_id: str,
        symbol: str,
        body: dict[str, Any],
        row_key: str,
        max_pages: int = 6,
    ) -> list[dict[str, Any]]:
        """Collect chart rows across continuation pages and symbol formats."""

        candidates = stock_code_candidates(normalize_symbol(symbol), self.settings.kiwoom_env)
        last_rows: list[dict[str, Any]] = []
        for code in candidates:
            try:
                rows = await self._collect_chart_rows(
                    path,
                    api_id,
                    {"stk_cd": code, **body},
                    row_key,
                    max_pages=max_pages,
                )
            except KiwoomRequestError:
                continue
            if rows:
                return rows
            last_rows = rows
        return last_rows

    async def _collect_chart_rows(
        self,
        path: str,
        api_id: str,
        body: dict[str, Any],
        row_key: str,
        max_pages: int = 6,
    ) -> list[dict[str, Any]]:
        """Collect paged chart rows using cont-yn/next-key."""

        rows: list[dict[str, Any]] = []
        next_key: str | None = None
        for page in range(max_pages):
            response = await self._post(
                path,
                api_id,
                body,
                continuation_key=next_key if page > 0 else None,
            )
            page_rows = response.body.get(row_key, []) or []
            rows.extend(page_rows)
            if not response.continuation or not response.next_key:
                break
            next_key = response.next_key
        return rows

    def _parse_daily_rows(self, rows: list[dict[str, Any]]) -> list[ChartBar]:
        return [
            ChartBar(
                time=format_date(str(row.get("dt", ""))),
                open=safe_abs_int(row.get("open_pric")),
                high=safe_abs_int(row.get("high_pric")),
                low=safe_abs_int(row.get("low_pric")),
                close=safe_abs_int(row.get("cur_prc")),
                volume=safe_abs_int(row.get("trde_qty")),
            )
            for row in rows
            if str(row.get("dt", "")).strip()
        ]

    def _parse_minute_rows(self, rows: list[dict[str, Any]], base_dt: str) -> list[ChartBar]:
        trade_date = base_dt if "-" in base_dt else format_date(base_dt)
        return [
            ChartBar(
                time=f"{trade_date}T{format_intraday(str(row.get('cntr_tm', '')))}:00",
                open=safe_abs_int(row.get("open_pric")),
                high=safe_abs_int(row.get("high_pric")),
                low=safe_abs_int(row.get("low_pric")),
                close=safe_abs_int(row.get("cur_prc")),
                volume=safe_abs_int(row.get("trde_qty")),
            )
            for row in rows
            if str(row.get("cntr_tm", "")).strip()
        ]

    async def health_check(self) -> bool:
        """Cheap readiness check via token + account lookup."""

        try:
            await self.verify_account()
        except Exception as exc:
            self.last_error = str(exc)
            return False
        return True

    async def find_company_name(self, symbol: str) -> str:
        """Return a best-effort company name for news queries."""

        try:
            quote = await self.get_stock_quote(symbol)
            return quote.name
        except Exception:
            universe = await self.get_stock_universe()
            for item in universe:
                if item.symbol == normalize_symbol(symbol):
                    return item.name
            return normalize_symbol(symbol)

    def _guess_market_name(self, symbol: str) -> str | None:
        return "KRX" if normalize_symbol(symbol).isdigit() else None

    def get_recent_errors(self) -> list[str]:
        """Return recent Kiwoom REST errors for the status panel."""

        return list(self._recent_errors)

    def _remember_error(self, message: str) -> None:
        self._recent_errors.append(message)
        self._recent_errors = self._recent_errors[-10:]


def safe_int(value: Any) -> int:
    """Convert Kiwoom numbers to int."""

    if value is None:
        return 0
    text = str(value).strip().replace(",", "").replace("+", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def safe_abs_int(value: Any) -> int:
    """Convert Kiwoom number to non-negative int."""

    return abs(safe_int(value))


def safe_float(value: Any) -> float:
    """Convert Kiwoom numbers to float."""

    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "").replace("+", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def now_kr() -> datetime:
    """Return current Asia/Seoul time."""

    return datetime.now(SEOUL_TZ)


def normalize_symbol(symbol: str) -> str:
    """Normalize symbols like A005930, KRX:005930, 005930_NX to 005930."""

    text = re.sub(r"[^0-9A-Za-z_:]", "", symbol or "").upper()
    text = re.sub(r"^[A-Z]+:", "", text)
    match = re.match(r"^A?(\d{6})(?:_[A-Z]+)?$", text)
    if match:
        return match.group(1)
    return text


def stock_code_candidates(symbol: str, env: str) -> list[str]:
    """Return preferred stock code formats for Kiwoom."""

    normalized = normalize_symbol(symbol)
    if env == "mock":
        return [normalized, f"KRX:{normalized}"]
    return [f"KRX:{normalized}", normalized]


def format_date(raw: str) -> str:
    """Format YYYYMMDD to ISO date."""

    if len(raw) != 8:
        return raw
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def format_intraday(raw: str) -> str:
    """Format HHMMSS to HH:MM."""

    value = raw.zfill(6)
    return f"{value[:2]}:{value[2:4]}"


def ordinal(level: int) -> str:
    """Map 1..10 to 1st..10th field prefixes."""

    mapping = {
        1: "1st",
        2: "2nd",
        3: "3rd",
        4: "4th",
        5: "5th",
        6: "6th",
        7: "7th",
        8: "8th",
        9: "9th",
        10: "10th",
    }
    return mapping[level]


def pick_first_int(body: dict[str, Any], keys: list[str]) -> int:
    """Return the first non-zero integer from a list of possible field names."""

    for key in keys:
        value = safe_abs_int(body.get(key))
        if value > 0:
            return value
    return 0


def pick_first_optional_int(body: dict[str, Any], keys: list[str]) -> int | None:
    """Return the first present integer, preserving sign when available."""

    for key in keys:
        raw = body.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        return safe_int(raw)
    return None


def has_market_payload(body: dict[str, Any]) -> bool:
    """Detect whether a market API response contains usable values."""

    if safe_abs_int(body.get("cur_prc")) > 0:
        return True

    daily = body.get("stk_dt_pole_chart_qry") or []
    if daily and safe_abs_int(daily[0].get("cur_prc")) > 0:
        return True

    minute = body.get("stk_min_pole_chart_qry") or []
    if minute and safe_abs_int(minute[0].get("cur_prc")) > 0:
        return True

    orderbook = body.get("sel_1st_pre_bid") or body.get("buy_1st_pre_bid")
    if safe_abs_int(orderbook) > 0:
        return True

    return False
