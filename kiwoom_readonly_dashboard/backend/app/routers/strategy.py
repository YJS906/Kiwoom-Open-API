"""Strategy detail and config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.trading import AdminConfigPatch, StrategySymbolDetail, TradingConfig


router = APIRouter(prefix="/api/strategy", tags=["strategy"])


@router.get("/config", response_model=TradingConfig)
async def get_strategy_config(request: Request) -> TradingConfig:
    """Return the current merged strategy config."""

    return request.app.state.signal_engine.config


@router.patch("/config", response_model=TradingConfig)
async def patch_strategy_config(request: Request, patch: AdminConfigPatch) -> TradingConfig:
    """Persist runtime config overrides."""

    return await request.app.state.signal_engine.update_runtime_config(patch)


@router.get("/detail/{symbol}", response_model=StrategySymbolDetail)
async def get_strategy_detail(request: Request, symbol: str) -> StrategySymbolDetail:
    """Return strategy detail panels for a single symbol."""

    return await request.app.state.signal_engine.get_symbol_detail(symbol)

