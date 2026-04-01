"""Session window helpers for the strategy engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.trading import SessionConfig


def _get_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Seoul":
            return timezone(timedelta(hours=9), name="Asia/Seoul")
        return timezone.utc


class SessionGuard:
    """Centralize time-window checks for entries and scanning."""

    def __init__(self, config: SessionConfig) -> None:
        self.config = config

    def now(self) -> datetime:
        return datetime.now(_get_timezone(self.config.timezone))

    def today(self) -> str:
        return self.now().strftime("%Y%m%d")

    def is_market_open(self, current: datetime | None = None) -> bool:
        current = current or self.now()
        return self._parse_hhmm(self.config.market_open_time) <= current.time().replace(
            tzinfo=None
        ) <= self._parse_hhmm(self.config.market_close_time)

    def can_enter_new_positions(self, cutoff_hhmm: str, current: datetime | None = None) -> bool:
        current = current or self.now()
        if not self.is_market_open(current):
            return False
        return current.time().replace(tzinfo=None) <= self._parse_hhmm(cutoff_hhmm)

    @staticmethod
    def _parse_hhmm(value: str):
        hour, minute = value.split(":", maxsplit=1)
        return datetime.strptime(f"{hour}:{minute}", "%H:%M").time()

