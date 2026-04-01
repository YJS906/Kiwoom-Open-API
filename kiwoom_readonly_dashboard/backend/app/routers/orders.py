"""Strategy order log and manual execution endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.models.trading import FillEvent, OrderIntent


router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=list[OrderIntent])
async def get_orders(request: Request) -> list[OrderIntent]:
    """Return recent strategy order intents."""

    snapshot = await request.app.state.signal_engine.get_snapshot()
    return snapshot.orders


@router.get("/fills", response_model=list[FillEvent])
async def get_fills(request: Request) -> list[FillEvent]:
    """Return recent fills."""

    snapshot = await request.app.state.signal_engine.get_snapshot()
    return snapshot.fills


@router.post("/execute/{signal_id}")
async def execute_signal(request: Request, signal_id: str) -> dict[str, Any]:
    """Manually execute one queued signal."""

    return await request.app.state.signal_engine.execute_signal(signal_id)

