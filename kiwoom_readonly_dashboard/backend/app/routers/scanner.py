"""Strategy scanner endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.trading import CandidateStock, StrategyDashboardSnapshot


router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.get("/overview", response_model=StrategyDashboardSnapshot)
async def get_overview(request: Request) -> StrategyDashboardSnapshot:
    """Return the full strategy snapshot used by the dashboard panels."""

    return await request.app.state.signal_engine.get_snapshot()


@router.get("/candidates", response_model=list[CandidateStock])
async def get_candidates(
    request: Request,
    state: str | None = Query(default=None, description="Optional candidate state filter"),
) -> list[CandidateStock]:
    """Return scanner candidates with an optional state filter."""

    snapshot = await request.app.state.signal_engine.get_snapshot()
    if not state:
        return snapshot.candidates
    return [item for item in snapshot.candidates if item.state == state]


@router.post("/refresh", response_model=StrategyDashboardSnapshot)
async def refresh_scanner(request: Request) -> StrategyDashboardSnapshot:
    """Force an immediate refresh of the strategy snapshot."""

    return await request.app.state.signal_engine.refresh_now()

