"""Health and status endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from app.models.schemas import ConnectionState, StatusPanel


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=StatusPanel)
async def get_status(request: Request) -> StatusPanel:
    """Return backend + provider status details."""

    kiwoom_client = request.app.state.kiwoom_client
    ws_service = request.app.state.kiwoom_ws
    news_service = request.app.state.news_service
    strategy_engine = request.app.state.signal_engine

    rest_ready = await kiwoom_client.health_check()
    news_connected, news_status, news_detail, news_updated = news_service.get_connection_state()
    ws_connected, ws_status, ws_detail, ws_updated = ws_service.get_connection_state()
    strategy_status = strategy_engine.get_status()

    timestamps = [
        ts
        for ts in [kiwoom_client.last_updated_at, ws_updated, news_updated, strategy_status.last_updated_at]
        if isinstance(ts, datetime)
    ]
    recent_errors = merge_errors(
        kiwoom_client.get_recent_errors(),
        ws_service.get_recent_errors(),
        news_service.get_recent_errors(),
        strategy_engine.get_recent_errors(),
        request.app.state.kiwoom_auth.get_recent_errors(),
    )

    return StatusPanel(
        kiwoom_rest=ConnectionState(
            connected=rest_ready,
            status="connected" if rest_ready else "degraded",
            last_updated_at=kiwoom_client.last_updated_at,
            detail=None if rest_ready else kiwoom_client.last_error,
        ),
        kiwoom_websocket=ConnectionState(
            connected=ws_connected,
            status=ws_status,
            last_updated_at=ws_updated,
            detail=ws_detail,
        ),
        news_provider=ConnectionState(
            connected=news_connected,
            status=news_status,
            last_updated_at=news_updated,
            detail=news_detail,
        ),
        strategy_engine=ConnectionState(
            connected=strategy_status.connected,
            status=strategy_status.status,
            last_updated_at=strategy_status.last_updated_at,
            detail=strategy_status.detail,
        ),
        last_refresh_at=max(timestamps) if timestamps else None,
        recent_errors=recent_errors,
    )


def merge_errors(*groups: list[str]) -> list[str]:
    """Merge and dedupe recent errors."""

    merged: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in merged:
                merged.append(item)
    return merged[-10:]
