"""Signal queue and replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.trading import ReplayResponse, SignalEvent


router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=list[SignalEvent])
async def get_signals(request: Request) -> list[SignalEvent]:
    """Return the latest signal queue."""

    snapshot = await request.app.state.signal_engine.get_snapshot()
    return snapshot.queued_signals


@router.get("/replay/{symbol}", response_model=ReplayResponse)
async def replay_symbol(request: Request, symbol: str) -> ReplayResponse:
    """Return a minimal replay response for one symbol."""

    return await request.app.state.signal_engine.replay(symbol)

