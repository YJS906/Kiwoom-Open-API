"""News endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import NewsResponse
from app.services.kiwoom_client import now_kr


router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/{symbol}", response_model=NewsResponse)
async def get_news(request: Request, symbol: str) -> NewsResponse:
    """Return recent news for the selected stock."""

    try:
        company_name = await request.app.state.kiwoom_client.find_company_name(symbol)
        items = await request.app.state.news_service.fetch(company_name)
        return NewsResponse(
            symbol=symbol,
            company_name=company_name,
            provider=request.app.state.news_service.get_active_provider_name(),
            items=items,
            updated_at=request.app.state.news_service.last_updated_at or now_kr(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
