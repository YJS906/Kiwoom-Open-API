"""Shared backend test fixtures."""

from __future__ import annotations

import logging

import pytest

from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        APP_NAME="Test Dashboard",
        APP_ENV="test",
        KIWOOM_APP_KEY="test-app-key",
        KIWOOM_SECRET_KEY="test-secret-key",
        KIWOOM_ACCOUNT_NO="1234567890",
        NAVER_CLIENT_ID="",
        NAVER_CLIENT_SECRET="",
    )


@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("kiwoom_dashboard_test")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
