"""FastAPI entry point for the read-only dashboard backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings, load_trading_config
from app.core.logging import configure_logging
from app.models.schemas import ErrorResponse
from app.routers.scanner import router as scanner_router
from app.routers.signals import router as signals_router
from app.routers.strategy import router as strategy_router
from app.routers.orders import router as orders_router
from app.routers.account import router as account_router
from app.routers.chart import router as chart_router
from app.routers.health import router as health_router
from app.routers.news import router as news_router
from app.routers.stocks import router as stocks_router
from app.services.bar_builder import BarBuilderService
from app.services.cache import TTLCache
from app.services.condition_search import ConditionSearchService
from app.services.high52_scanner import High52Scanner
from app.services.kiwoom_auth import KiwoomAuthError, KiwoomAuthService
from app.services.kiwoom_client import KiwoomClientService, KiwoomRequestError
from app.services.kiwoom_ws import KiwoomWebSocketService
from app.services.news_provider import NewsService
from app.services.order_executor import OrderExecutor
from app.services.paper_broker import PaperBroker
from app.services.position_manager import PositionManager
from app.services.pullback_strategy import PullbackStrategyEngine
from app.services.realtime_high52 import RealtimeHigh52Service
from app.services.risk_manager import RiskManager
from app.services.session_guard import SessionGuard
from app.services.signal_engine import SignalEngine


def create_app(
    settings: Settings | None = None,
    logger: logging.Logger | None = None,
    cache: TTLCache | None = None,
    auth_service: KiwoomAuthService | None = None,
    kiwoom_client: KiwoomClientService | None = None,
    news_service: NewsService | None = None,
    ws_service: KiwoomWebSocketService | None = None,
    signal_engine: SignalEngine | None = None,
) -> FastAPI:
    """Create the FastAPI application."""

    settings = settings or get_settings()
    logger = logger or configure_logging(settings)
    cache = cache or TTLCache()
    auth_service = auth_service or KiwoomAuthService(settings, logger)
    kiwoom_client = kiwoom_client or KiwoomClientService(settings, auth_service, cache, logger)
    news_service = news_service or NewsService(settings, cache, logger)
    ws_service = ws_service or KiwoomWebSocketService(settings, auth_service, logger)
    market_auth_service = None
    if settings.kiwoom_market_env == "production":
        if settings.has_dedicated_market_credentials:
            market_auth_service = KiwoomAuthService(
                settings,
                logger,
                service_name="kiwoom_market",
                rest_base_url=settings.kiwoom_market_rest_base_url,
                app_key=settings.kiwoom_market_app_key,
                secret_key=settings.kiwoom_market_secret_key,
                token_cache_file=settings.market_token_cache_file,
            )
        elif settings.kiwoom_env == "production":
            market_auth_service = auth_service
    realtime_high52 = RealtimeHigh52Service(settings, market_auth_service, cache, logger)
    trading_config = load_trading_config(settings)
    session_guard = SessionGuard(trading_config.session)
    condition_search = ConditionSearchService(settings, auth_service, logger, ws_service)
    scanner = High52Scanner(trading_config.scanner, condition_search, kiwoom_client, realtime_high52, logger)
    bar_builder = BarBuilderService(kiwoom_client, cache, logger)
    paper_broker = PaperBroker()
    position_manager = PositionManager()
    risk_manager = RiskManager(trading_config.risk, session_guard)
    strategy = PullbackStrategyEngine(trading_config.strategy, trading_config.risk)
    order_executor = OrderExecutor(settings, trading_config.execution, kiwoom_client, paper_broker, logger)
    signal_engine = signal_engine or SignalEngine(
        settings,
        trading_config,
        kiwoom_client,
        scanner,
        bar_builder,
        strategy,
        risk_manager,
        order_executor,
        position_manager,
        session_guard,
        logger,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            if settings.app_env != "test":
                await signal_engine.start()
            yield
        finally:
            await signal_engine.shutdown()
            await ws_service.shutdown()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Read-only dashboard for Kiwoom REST/WebSocket market data.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.logger = logger
    app.state.cache = cache
    app.state.kiwoom_auth = auth_service
    app.state.kiwoom_client = kiwoom_client
    app.state.news_service = news_service
    app.state.kiwoom_ws = ws_service
    app.state.realtime_high52 = realtime_high52
    app.state.trading_config = trading_config
    app.state.signal_engine = signal_engine
    app.state.condition_search = condition_search

    app.include_router(account_router)
    app.include_router(stocks_router)
    app.include_router(chart_router)
    app.include_router(news_router)
    app.include_router(health_router)
    app.include_router(scanner_router)
    app.include_router(signals_router)
    app.include_router(strategy_router)
    app.include_router(orders_router)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"message": "Kiwoom readonly dashboard backend is running."}

    @app.get("/api", tags=["root"])
    async def api_root() -> dict[str, str]:
        return {
            "message": (
                "Use /api/health, /api/account, /api/stocks, /api/chart, /api/news, "
                "/api/scanner, /api/signals, /api/strategy, /api/orders."
            )
        }

    @app.websocket("/ws/stream")
    async def stream(websocket: WebSocket) -> None:
        await app.state.kiwoom_ws.relay(websocket)

    @app.exception_handler(KiwoomRequestError)
    async def kiwoom_request_exception_handler(
        request: Request,
        exc: KiwoomRequestError,
    ) -> JSONResponse:
        request.app.state.logger.error("Kiwoom request error: %s", exc)
        return JSONResponse(status_code=502, content=ErrorResponse(detail=str(exc)).model_dump())

    @app.exception_handler(KiwoomAuthError)
    async def kiwoom_auth_exception_handler(request: Request, exc: KiwoomAuthError) -> JSONResponse:
        request.app.state.logger.error("Kiwoom auth error: %s", exc)
        return JSONResponse(status_code=502, content=ErrorResponse(detail=str(exc)).model_dump())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request.app.state.logger.exception("Unhandled application error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="Unexpected server error.").model_dump(),
        )

    return app
