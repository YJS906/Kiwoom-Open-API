"""Account read-only endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import AccountSummary, HoldingsResponse
from app.services.kiwoom_client import KiwoomRequestError


router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/summary", response_model=AccountSummary)
async def get_account_summary(request: Request) -> AccountSummary:
    """Return account summary metrics."""

    try:
        return await request.app.state.kiwoom_client.get_account_summary()
    except KiwoomRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/holdings", response_model=HoldingsResponse)
async def get_holdings(request: Request) -> HoldingsResponse:
    """Return current holdings."""

    try:
        return await request.app.state.kiwoom_client.get_holdings()
    except KiwoomRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
