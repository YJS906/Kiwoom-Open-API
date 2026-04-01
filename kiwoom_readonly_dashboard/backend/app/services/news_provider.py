"""News provider abstraction."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from html import unescape

from app.core.config import Settings
from app.models.schemas import NewsItem
from app.services.cache import TTLCache
from app.services.kiwoom_client import now_kr


class BaseNewsProvider(ABC):
    """Abstract provider interface."""

    provider_name: str = "base"

    @abstractmethod
    async def fetch(self, query: str) -> list[NewsItem]:
        """Fetch news items for a query."""


class NewsService:
    """Provider abstraction with cache and fallback."""

    def __init__(self, settings: Settings, cache: TTLCache, logger: logging.Logger) -> None:
        from app.services.naver_news import NaverNewsProvider
        from app.services.rss_news import RssNewsProvider

        self.settings = settings
        self.cache = cache
        self.logger = logger.getChild("news")
        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None
        self._recent_errors: list[str] = []
        self._rss_provider = RssNewsProvider(logger)
        self._naver_provider = (
            NaverNewsProvider(settings, logger)
            if settings.naver_client_id and settings.naver_client_secret
            else None
        )

    async def fetch(self, company_name: str) -> list[NewsItem]:
        """Fetch recent news with configured provider and fallback."""

        cache_key = f"news:{normalize_text(company_name)}"

        async def _factory() -> list[NewsItem]:
            providers = self._select_providers()
            last_exception: Exception | None = None
            collected: list[NewsItem] = []
            for provider in providers:
                try:
                    items = await provider.fetch(company_name)
                    if items:
                        collected = dedupe_and_sort_news(items)
                        self.last_error = None
                        self.last_updated_at = now_kr()
                        return collected
                except Exception as exc:  # pragma: no cover - network/provider fallback
                    last_exception = exc
                    self._remember_error(f"{provider.provider_name}: {exc}")
                    self.logger.warning("News provider %s failed: %s", provider.provider_name, exc)
            if last_exception:
                raise RuntimeError(str(last_exception))
            return collected

        return await self.cache.get_or_set(
            cache_key,
            self.settings.news_cache_ttl_seconds,
            _factory,
        )

    def _select_providers(self) -> list[BaseNewsProvider]:
        if self.settings.news_provider == "naver":
            return [self._require_naver()]
        if self.settings.news_provider == "rss":
            return [self._rss_provider]
        if self._naver_provider is not None:
            return [self._naver_provider, self._rss_provider]
        return [self._rss_provider]

    def _require_naver(self) -> BaseNewsProvider:
        if self._naver_provider is None:
            raise RuntimeError(
                "NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required when NEWS_PROVIDER=naver."
            )
        return self._naver_provider

    def get_connection_state(self) -> tuple[bool, str, str | None, datetime | None]:
        """Return provider readiness details."""

        if self.settings.news_provider == "naver" and self._naver_provider is None:
            return False, "misconfigured", "Naver credentials are missing.", self.last_updated_at
        if self.last_error:
            return False, "degraded", self.last_error, self.last_updated_at
        return True, "ready", None, self.last_updated_at

    def get_active_provider_name(self) -> str:
        """Return the current primary provider name."""

        return self._select_providers()[0].provider_name

    def get_recent_errors(self) -> list[str]:
        return list(self._recent_errors)

    def _remember_error(self, message: str) -> None:
        self.last_error = message
        self._recent_errors.append(message)
        self._recent_errors = self._recent_errors[-10:]


def strip_html(text: str | None) -> str:
    """Strip simple HTML tags from provider responses."""

    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return unescape(cleaned).strip()


def dedupe_and_sort_news(items: list[NewsItem]) -> list[NewsItem]:
    """Remove duplicates and sort newest first."""

    unique: dict[str, NewsItem] = {}
    for item in items:
        dedupe_key = f"{normalize_text(item.title)}::{normalize_text(item.url)}"
        existing = unique.get(dedupe_key)
        if existing is None:
            unique[dedupe_key] = item
            continue
        if (item.published_at or datetime.min) > (existing.published_at or datetime.min):
            unique[dedupe_key] = item

    return sorted(
        unique.values(),
        key=lambda item: item.published_at or datetime.min,
        reverse=True,
    )


def normalize_text(text: str) -> str:
    """Normalize text for dedupe matching."""

    return re.sub(r"\\s+", " ", text).strip().lower()
