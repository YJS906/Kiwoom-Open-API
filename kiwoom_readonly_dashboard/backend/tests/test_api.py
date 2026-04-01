"""FastAPI router tests with stub services."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import AccountSummary, ChartResponse, HoldingItem, HoldingsResponse, NewsItem, StockQuote, StockSearchItem
from app.services.cache import TTLCache
from app.services.kiwoom_auth import KiwoomAuthService


class StubKiwoomClient:
    last_updated_at = datetime(2026, 4, 1, 9, 0, 0)
    last_error = None

    async def get_account_summary(self) -> AccountSummary:
        return AccountSummary(
            total_evaluation_amount=1_000_000,
            total_profit_loss=50_000,
            total_profit_rate=5.0,
            holdings_count=1,
            deposit=200_000,
            estimated_assets=1_200_000,
            updated_at=self.last_updated_at,
        )

    async def get_holdings(self) -> HoldingsResponse:
        return HoldingsResponse(
            items=[
                HoldingItem(
                    symbol="005930",
                    name="삼성전자",
                    quantity=3,
                    available_quantity=3,
                    average_price=70000,
                    current_price=72000,
                    evaluation_profit_loss=6000,
                    profit_rate=2.85,
                    market_name="KOSPI",
                )
            ],
            updated_at=self.last_updated_at,
        )

    async def search_stocks(self, query: str) -> list[StockSearchItem]:
        return [
            StockSearchItem(
                symbol="005930",
                name="삼성전자",
                market_code="0",
                market_name="KOSPI",
                last_price=72000,
            )
        ]

    async def get_stock_quote(self, symbol: str) -> StockQuote:
        return StockQuote(
            symbol=symbol,
            name="삼성전자",
            market_name="KOSPI",
            current_price=72000,
            previous_close=71000,
            diff_from_previous_close=1000,
            change_rate=1.4,
            volume=1000000,
            open_price=71500,
            high_price=72500,
            low_price=71200,
            best_ask=72100,
            best_bid=72000,
            market_phase="장중",
            updated_at=self.last_updated_at,
        )

    async def get_orderbook(self, symbol: str):
        from app.models.schemas import OrderbookLevel, OrderbookSnapshot

        return OrderbookSnapshot(
            symbol=symbol,
            asks=[OrderbookLevel(price=72100, quantity=100, delta=10)],
            bids=[OrderbookLevel(price=72000, quantity=120, delta=-5)],
            total_ask_quantity=1000,
            total_bid_quantity=900,
            timestamp="09:01:00",
            updated_at=self.last_updated_at,
        )

    async def get_chart(self, symbol: str, range_label: str, interval: str) -> ChartResponse:
        from app.models.schemas import ChartBar

        return ChartResponse(
            symbol=symbol,
            interval=interval,  # type: ignore[arg-type]
            range_label=range_label,
            bars=[
                ChartBar(time="2026-03-31", open=70000, high=71000, low=69500, close=70500, volume=1000)
            ],
            updated_at=self.last_updated_at,
        )

    async def health_check(self) -> bool:
        return True

    async def find_company_name(self, symbol: str) -> str:
        return "삼성전자"

    def get_recent_errors(self) -> list[str]:
        return []


class StubNewsService:
    last_updated_at = datetime(2026, 4, 1, 9, 0, 0)

    async def fetch(self, company_name: str) -> list[NewsItem]:
        return [
            NewsItem(
                title="삼성전자 관련 뉴스",
                source="RSS",
                published_at=self.last_updated_at,
                url="https://example.com/news",
                summary="요약",
                provider="rss",
            )
        ]

    def get_connection_state(self) -> tuple[bool, str, str | None, datetime | None]:
        return True, "ready", None, self.last_updated_at

    def get_recent_errors(self) -> list[str]:
        return []

    def get_active_provider_name(self) -> str:
        return "rss"


class StubWsService:
    market_phase_label = "장중"
    last_updated_at = datetime(2026, 4, 1, 9, 0, 0)

    def get_connection_state(self) -> tuple[bool, str, str | None, datetime | None]:
        return False, "disconnected", None, self.last_updated_at

    def get_recent_errors(self) -> list[str]:
        return []


def test_health_and_account_routes(settings, logger) -> None:
    app = create_app(
        settings=settings,
        logger=logger,
        cache=TTLCache(),
        auth_service=KiwoomAuthService(settings, logger),
        kiwoom_client=StubKiwoomClient(),
        news_service=StubNewsService(),
        ws_service=StubWsService(),
    )
    client = TestClient(app)

    health = client.get("/api/health")
    summary = client.get("/api/account/summary")
    holdings = client.get("/api/account/holdings")
    stock = client.get("/api/stocks/005930")
    chart = client.get("/api/chart/005930?range=3m&interval=day")
    news = client.get("/api/news/005930")

    assert health.status_code == 200
    assert summary.status_code == 200
    assert holdings.status_code == 200
    assert stock.status_code == 200
    assert chart.status_code == 200
    assert news.status_code == 200
    assert summary.json()["holdings_count"] == 1
    assert holdings.json()["items"][0]["symbol"] == "005930"
    assert stock.json()["quote"]["name"] == "삼성전자"
    assert news.json()["items"][0]["provider"] == "rss"
