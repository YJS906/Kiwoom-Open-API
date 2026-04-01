"""Strategy detail and config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.trading import AdminConfigPatch, StrategyChartSeries, StrategySymbolDetail, TradingConfig


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
async def get_strategy_detail(
    request: Request,
    symbol: str,
    include_charts: bool = Query(default=False),
) -> StrategySymbolDetail:
    """Return strategy detail panels for a single symbol."""

    return await request.app.state.signal_engine.get_symbol_detail(symbol, include_charts=include_charts)


@router.get("/chart/{symbol}", response_model=StrategyChartSeries)
async def get_strategy_chart(
    request: Request,
    symbol: str,
    timeframe: str = Query(pattern="^(daily|weekly|60m|15m|5m)$"),
) -> StrategyChartSeries:
    """Return one strategy chart timeframe on demand."""

    return await request.app.state.signal_engine.get_chart_series(symbol, timeframe)
