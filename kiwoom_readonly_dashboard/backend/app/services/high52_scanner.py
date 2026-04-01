"""52-week-high candidate scanner."""

from __future__ import annotations

import logging

from app.models.trading import CandidateStock, ScannerConfig, now_kr
from app.services.condition_search import ConditionSearchService
from app.services.kiwoom_client import KiwoomClientService, normalize_symbol


class High52Scanner:
    """Build the candidate universe from condition search or safe fallbacks."""

    def __init__(
        self,
        config: ScannerConfig,
        condition_search: ConditionSearchService,
        kiwoom_client: KiwoomClientService,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.condition_search = condition_search
        self.kiwoom_client = kiwoom_client
        self.logger = logger.getChild("high52_scanner")
        self.last_source = "uninitialized"

    async def refresh(self, existing: dict[str, CandidateStock]) -> list[CandidateStock]:
        """Refresh the candidate list and preserve durable states when possible."""

        rows = await self._load_condition_rows()
        if not rows:
            rows = await self._load_fallback_rows()
            self.last_source = "fallback_symbols"
        else:
            self.last_source = "condition_search"

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
                    market_name=metadata.market_name if metadata else None,
                    note=None,
                    blocked_reason=previous.blocked_reason if previous and state == "blocked" else None,
                    detected_at=previous.detected_at if previous else now,
                    updated_at=now,
                )
            )

        return sorted(refreshed, key=lambda item: (item.symbol, item.name))

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

