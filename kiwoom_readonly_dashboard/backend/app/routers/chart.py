"""Chart endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.schemas import ChartResponse
from app.services.kiwoom_client import KiwoomRequestError


router = APIRouter(prefix="/api/chart", tags=["chart"])


@router.get("/{symbol}", response_model=ChartResponse)
async def get_chart(
    request: Request,
    symbol: str,
    range: str = Query(default="3m", pattern="^(1m|3m|6m|1y)$"),
    interval: str = Query(default="day", pattern="^(day|minute)$"),
) -> ChartResponse:
    """Return chart bars for a stock."""

    try:
        return await request.app.state.kiwoom_client.get_chart(symbol, range, interval)  # type: ignore[arg-type]
    except KiwoomRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
