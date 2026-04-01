"""RSS news fallback provider.

Google News RSS is used as a public fallback source. Availability and result
format can change by provider, so this is intentionally implemented as a
best-effort backup rather than a guaranteed primary feed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx

from app.models.schemas import NewsItem
from app.services.news_provider import BaseNewsProvider, strip_html


class RssNewsProvider(BaseNewsProvider):
    """Fetch Korean-language news from a public RSS feed."""

    provider_name = "rss"

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger.getChild("rss_news")

    async def fetch(self, query: str) -> list[NewsItem]:
        """Fetch RSS items from Google News RSS search."""

        encoded = quote_plus(f"{query} when:7d")
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            xml_text = response.text

        root = ElementTree.fromstring(xml_text)
        items: list[NewsItem] = []
        for item in root.findall("./channel/item"):
            items.append(
                NewsItem(
                    title=strip_html(item.findtext("title")),
                    source=extract_rss_source(item.findtext("source"), item.findtext("title")),
                    published_at=parse_rss_date(item.findtext("pubDate")),
                    url=str(item.findtext("link") or ""),
                    summary=strip_html(item.findtext("description")),
                    provider=self.provider_name,
                )
            )
        return items


def parse_rss_date(value: str | None) -> datetime | None:
    """Parse RSS publication dates."""

    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None


def extract_rss_source(source: str | None, title: str | None) -> str:
    """Extract a displayable source name from RSS fields."""

    if source:
        return strip_html(source)
    if title and " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "RSS"
