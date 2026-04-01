"""Stock lookup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.schemas import OrderbookSnapshot, StockDetailResponse, StockSearchResponse
from app.services.kiwoom_client import KiwoomRequestError, now_kr


router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/search", response_model=StockSearchResponse)
async def search_stocks(
    request: Request,
    q: str = Query(..., min_length=1, description="Symbol or company name"),
) -> StockSearchResponse:
    """Return stock search suggestions."""

    try:
        items = await request.app.state.kiwoom_client.search_stocks(q)
        return StockSearchResponse(
            items=items,
            updated_at=request.app.state.kiwoom_client.last_updated_at or now_kr(),
        )
    except KiwoomRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}", response_model=StockDetailResponse)
async def get_stock_detail(request: Request, symbol: str) -> StockDetailResponse:
    """Return quote + orderbook for one stock."""

    try:
        quote = await request.app.state.kiwoom_client.get_stock_quote(symbol)
    except KiwoomRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    orderbook: OrderbookSnapshot | None = None
    try:
        orderbook = await request.app.state.kiwoom_client.get_orderbook(symbol)
    except KiwoomRequestError:
        orderbook = None

    if orderbook and orderbook.asks:
        quote.best_ask = orderbook.asks[0].price
    if orderbook and orderbook.bids:
        quote.best_bid = orderbook.bids[0].price

    if request.app.state.kiwoom_ws.market_phase_label:
        quote.market_phase = request.app.state.kiwoom_ws.market_phase_label

    return StockDetailResponse(quote=quote, orderbook=orderbook)
