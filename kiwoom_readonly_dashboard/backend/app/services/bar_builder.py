"""Normalized multi-timeframe bar builder."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from app.models.trading import Timeframe, TradeBar
from app.services.cache import TTLCache
from app.services.kiwoom_client import KiwoomClientService


class BarBuilderService:
    """Build daily, weekly, 60m, 15m and 5m bars for the strategy engine."""

    def __init__(
        self,
        kiwoom_client: KiwoomClientService,
        cache: TTLCache,
        logger: logging.Logger,
    ) -> None:
        self.kiwoom_client = kiwoom_client
        self.cache = cache
        self.logger = logger.getChild("bar_builder")

    async def get_bars(self, symbol: str, timeframe: Timeframe, limit: int | None = None) -> list[TradeBar]:
        """Fetch one timeframe and normalize it into TradeBar models."""

        cache_key = f"strategy-bars:{symbol}:{timeframe}:{limit or 'default'}"

        async def _factory() -> list[TradeBar]:
            if timeframe == "daily":
                rows = await self.kiwoom_client.get_daily_bars(symbol, limit=limit or 260)
                return [self._to_trade_bar(timeframe, row) for row in rows]
            if timeframe == "weekly":
                rows = await self.kiwoom_client.get_weekly_bars(symbol, limit=limit or 104)
                return [self._to_trade_bar(timeframe, row) for row in rows]
            if timeframe == "15m":
                rows = await self.kiwoom_client.get_minute_bars(symbol, minutes=15, limit=limit or 160)
                return [self._to_trade_bar(timeframe, row) for row in rows]
            if timeframe == "5m":
                rows = await self.kiwoom_client.get_minute_bars(symbol, minutes=5, limit=limit or 320)
                return [self._to_trade_bar(timeframe, row) for row in rows]
            if timeframe == "60m":
                seed_rows = await self.kiwoom_client.get_minute_bars(symbol, minutes=5, limit=(limit or 48) * 12)
                return aggregate_bars([self._to_trade_bar("5m", row) for row in seed_rows], 60)
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return await self.cache.get_or_set(cache_key, 20, _factory)

    async def get_strategy_bundle(self, symbol: str) -> dict[str, list[TradeBar]]:
        """Fetch the bundle used by the pullback strategy and the detail panel."""

        daily = await self._get_optional_bars(symbol, "daily", limit=260)
        bars_60m = await self._get_optional_bars(symbol, "60m", limit=80)
        bars_15m = await self._get_optional_bars(symbol, "15m", limit=160)
        bars_5m = await self._get_optional_bars(symbol, "5m", limit=200)
        weekly = await self._get_optional_bars(symbol, "weekly", limit=60)
        return {
            "daily": daily,
            "60m": bars_60m,
            "15m": bars_15m,
            "5m": bars_5m,
            "weekly": weekly,
        }

    async def _get_optional_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int | None = None,
    ) -> list[TradeBar]:
        """Return one timeframe, but keep the detail panel alive on partial failures."""

        try:
            return await self.get_bars(symbol, timeframe, limit=limit)
        except Exception as exc:
            self.logger.warning(
                "Returning an empty %s chart for %s because the upstream fetch failed: %s",
                timeframe,
                symbol,
                exc,
            )
            return []

    @staticmethod
    def _to_trade_bar(timeframe: Timeframe, row) -> TradeBar:
        return TradeBar(
            timeframe=timeframe,
            time=row.time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )


def aggregate_bars(bars: list[TradeBar], target_minutes: int) -> list[TradeBar]:
    """Aggregate lower timeframe bars into larger buckets."""

    if not bars:
        return []
    grouped: dict[tuple[int, int, int, int], list[TradeBar]] = defaultdict(list)
    for bar in bars:
        timestamp = datetime.fromisoformat(bar.time)
        hour_bucket = timestamp.hour
        minute_bucket = (timestamp.minute // target_minutes) * target_minutes if target_minutes < 60 else 0
        key = (timestamp.year, timestamp.month, timestamp.day, hour_bucket * 100 + minute_bucket)
        grouped[key].append(bar)

    aggregated: list[TradeBar] = []
    for key in sorted(grouped):
        batch = sorted(grouped[key], key=lambda item: item.time)
        first = batch[0]
        last = batch[-1]
        aggregated.append(
            TradeBar(
                timeframe=f"{target_minutes}m",  # type: ignore[arg-type]
                time=last.time,
                open=first.open,
                high=max(item.high for item in batch),
                low=min(item.low for item in batch),
                close=last.close,
                volume=sum(item.volume for item in batch),
            )
        )
    return aggregated
