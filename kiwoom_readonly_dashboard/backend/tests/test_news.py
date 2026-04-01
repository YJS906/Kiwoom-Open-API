"""News helper tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.schemas import NewsItem
from app.services.news_provider import dedupe_and_sort_news, strip_html


def test_strip_html() -> None:
    assert strip_html("<b>삼성전자</b> 뉴스") == "삼성전자 뉴스"


def test_dedupe_and_sort_news() -> None:
    older = datetime.now() - timedelta(hours=1)
    newer = datetime.now()
    items = [
        NewsItem(
            title="삼성전자, 실적 발표",
            source="A",
            published_at=older,
            url="https://example.com/news/1",
            summary=None,
            provider="rss",
        ),
        NewsItem(
            title="삼성전자, 실적 발표",
            source="B",
            published_at=newer,
            url="https://example.com/news/1",
            summary=None,
            provider="naver",
        ),
        NewsItem(
            title="반도체 업황 개선",
            source="C",
            published_at=older,
            url="https://example.com/news/2",
            summary=None,
            provider="rss",
        ),
    ]

    result = dedupe_and_sort_news(items)

    assert len(result) == 2
    assert result[0].source == "B"
