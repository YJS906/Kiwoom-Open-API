"""52-week-high candidate scanner."""

from __future__ import annotations

import logging

from app.models.trading import CandidateStock, ScannerConfig, now_kr
from app.services.condition_search import ConditionSearchService
from app.services.kiwoom_client import KiwoomClientService, normalize_symbol
from app.services.realtime_high52 import RealtimeHigh52Service


class High52Scanner:
    """Build the candidate universe from condition search or safe fallbacks."""

    def __init__(
        self,
        config: ScannerConfig,
        condition_search: ConditionSearchService,
        kiwoom_client: KiwoomClientService,
        realtime_high52: RealtimeHigh52Service | None,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.condition_search = condition_search
        self.kiwoom_client = kiwoom_client
        self.realtime_high52 = realtime_high52
        self.logger = logger.getChild("high52_scanner")
        self.last_source = "uninitialized"

    async def refresh(self, existing: dict[str, CandidateStock]) -> list[CandidateStock]:
        """Refresh the candidate list and preserve durable states when possible."""

        rows = await self._load_rows_by_priority()
        if not rows:
            rows = await self._load_fallback_rows()
            self.last_source = "fallback_symbols"

        refreshed: list[CandidateStock] = []
        now = now_kr()
        for row in rows:
            symbol = normalize_symbol(str(row.get("symbol", "")))
            if not symbol:
                continue
            metadata = await self.kiwoom_client.get_stock_metadata(symbol)
            previous = existing.get(symbol)
            state = previous.state if previous and previous.state in {"ordered", "exited"} else "new"
            name = str(row.get("name") or (metadata.name if metadata else symbol))
            refreshed.append(
                CandidateStock(
                    symbol=symbol,
                    name=name,
                    state=state,
                    source=self.last_source,
                    condition_name=self.config.condition_name if self.last_source == "condition_search" else None,
                    condition_seq=str(row.get("condition_seq", "")) or None,
                    breakout_date=row.get("breakout_date"),
                    breakout_price=row.get("breakout_price"),
                    last_price=row.get("current_price"),
                    change_rate=row.get("change_rate"),
                    market_name=str(row.get("market_name") or (metadata.market_name if metadata else "")) or None,
                    note=str(row.get("note") or "") or None,
                    blocked_reason=previous.blocked_reason if previous and state == "blocked" else None,
                    detected_at=previous.detected_at if previous else now,
                    updated_at=now,
                )
            )

        return sorted(refreshed, key=lambda item: (item.symbol, item.name))

    async def _load_rows_by_priority(self) -> list[dict[str, object]]:
        """Load candidate rows according to the configured source priority."""

        mode = self.config.source_mode
        if mode == "realtime_only":
            rows = await self._load_realtime_rows()
            self.last_source = "realtime_high52" if rows else "realtime_high52_empty"
            return rows

        if mode == "realtime_first":
            realtime_rows = await self._load_realtime_rows()
            if realtime_rows:
                self.last_source = "realtime_high52"
                return realtime_rows
            condition_rows = await self._load_condition_rows()
            if condition_rows:
                self.last_source = "condition_search"
                return condition_rows
            return []

        condition_rows = await self._load_condition_rows()
        if condition_rows:
            self.last_source = "condition_search"
            return condition_rows
        realtime_rows = await self._load_realtime_rows()
        if realtime_rows:
            self.last_source = "realtime_high52"
            return realtime_rows
        return []

    async def _load_condition_rows(self) -> list[dict[str, object]]:
        condition = await self.condition_search.resolve_condition(self.config.condition_name)
        if condition is None:
            self.logger.warning("Condition '%s' was not found. Using fallback symbols.", self.config.condition_name)
            return []

        try:
            rows = await self.condition_search.search_condition_once(condition.seq)
        except Exception as exc:
            self.logger.warning("Condition search failed, using fallback symbols: %s", exc)
            return []
        for row in rows:
            row["condition_seq"] = condition.seq
        return rows

    async def _load_realtime_rows(self) -> list[dict[str, object]]:
        """Load the live 52-week-high universe from ka10016 and cap it for safe scanning."""

        if self.realtime_high52 is None:
            return []

        snapshot = await self.realtime_high52.get_snapshot(self.config.realtime_market)
        if snapshot.status != "ok" or not snapshot.items:
            if snapshot.reason:
                self.logger.info("Realtime 52-week-high universe is unavailable: %s", snapshot.reason)
            return []

        ranked_items = sorted(
            snapshot.items,
            key=lambda item: (item.volume, abs(item.change_rate), item.current_price),
            reverse=True,
        )
        rows: list[dict[str, object]] = []
        for item in ranked_items[: self.config.max_realtime_candidates]:
            rows.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "current_price": item.current_price,
                    "change_rate": item.change_rate,
                    "breakout_price": item.high_price or item.current_price,
                    "market_name": item.market_name,
                    "note": "Loaded from Kiwoom ka10016 realtime 52-week-high feed.",
                }
            )
        return rows

    async def _load_fallback_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for symbol in self.config.fallback_symbols:
            try:
                quote = await self.kiwoom_client.get_stock_quote(symbol)
            except Exception as exc:
                self.logger.warning("Fallback quote lookup failed for %s: %s", symbol, exc)
                continue
            rows.append(
                {
                    "symbol": quote.symbol,
                    "name": quote.name,
                    "current_price": quote.current_price,
                    "change_rate": quote.change_rate,
                    "breakout_price": quote.high_price,
                }
            )
        return rows
