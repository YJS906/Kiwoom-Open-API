"""Shared pytest fixtures."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.models import (
    ApiSettings,
    AppSettings,
    Credentials,
    LoggingSettings,
    RiskSettings,
    RuntimeSettings,
    SafetySettings,
    StrategySettings,
    TradingSettings,
)


@pytest.fixture
def logger() -> logging.Logger:
    """Minimal logger fixture."""

    return logging.getLogger("kiwoom_mock_trader_test")


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    """Build isolated settings for tests."""

    return AppSettings(
        environment="mock",
        api=ApiSettings(),
        trading=TradingSettings(),
        safety=SafetySettings(),
        risk=RiskSettings(),
        strategy=StrategySettings(),
        runtime=RuntimeSettings(
            state_dir=".runtime",
            token_cache_file=".runtime/token_mock.json",
            state_file=".runtime/state.json",
            orders_dir=".runtime/orders",
        ),
        logging=LoggingSettings(),
        credentials=Credentials(
            app_key="test-app-key",
            secret_key="test-secret-key",
            account_no="1234567890",
            account_password="0000",
        ),
        project_root=tmp_path,
    )

