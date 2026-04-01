"""Naver news search provider."""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import Settings
from app.models.schemas import NewsItem
from app.services.news_provider import BaseNewsProvider, strip_html


class NaverNewsProvider(BaseNewsProvider):
    """Fetch news from the official Naver Search API."""

    provider_name = "naver"

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("naver_news")

    async def fetch(self, query: str) -> list[NewsItem]:
        """Fetch recent news results from Naver."""

        headers = {
            "X-Naver-Client-Id": self.settings.naver_client_id or "",
            "X-Naver-Client-Secret": self.settings.naver_client_secret or "",
        }
        params = {
            "query": query,
            "display": 20,
            "start": 1,
            "sort": "date",
        }
        url = "https://openapi.naver.com/v1/search/news.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        items: list[NewsItem] = []
        for row in data.get("items", []) or []:
            items.append(
                NewsItem(
                    title=strip_html(str(row.get("title", "") or "")),
                    source=self._extract_source(row),
                    published_at=parse_naver_date(row.get("pubDate")),
                    url=str(row.get("originallink") or row.get("link") or ""),
                    summary=strip_html(str(row.get("description", "") or "")),
                    provider=self.provider_name,
                )
            )
        return items

    def _extract_source(self, item: dict[str, object]) -> str:
        link = str(item.get("originallink") or item.get("link") or "")
        if "naver.com" in link:
            return "Naver"
        return "External"


def parse_naver_date(value: object) -> datetime | None:
    """Parse RFC 822 date strings from Naver news search."""

    if not value:
        return None
    try:
        return parsedate_to_datetime(str(value))
    except (TypeError, ValueError, IndexError):
        return None
