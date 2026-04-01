"""Unit tests for risk rules."""

from __future__ import annotations

from app.models import OrderResponse
from app.risk import RiskManager


def test_preflight_blocks_large_buy_order(settings, logger) -> None:
    """Orders over max_order_amount_krw should be rejected."""

    risk = RiskManager(settings, logger)
    risk.prepare_for_today("20260401", 1_000_000)

    result = risk.preflight_check(
        side="buy",
        order_amount_krw=200_000,
        position_count=0,
        daily_pnl_krw=0,
        open_order_exists=False,
    )

    assert result.allowed is False


def test_preflight_blocks_after_daily_loss_limit(settings, logger) -> None:
    """Daily loss limit should stop additional trading."""

    risk = RiskManager(settings, logger)
    risk.prepare_for_today("20260401", 1_000_000)

    result = risk.preflight_check(
        side="buy",
        order_amount_krw=50_000,
        position_count=0,
        daily_pnl_krw=-40_000,
        open_order_exists=False,
    )

    assert result.allowed is False


def test_register_order_increments_daily_count(settings, logger) -> None:
    """Every order attempt should increment the persisted daily count."""

    risk = RiskManager(settings, logger)
    risk.prepare_for_today("20260401", 1_000_000)
    response = OrderResponse(
        order_no="DRYRUN-1",
        side="buy",
        symbol="005930",
        quantity=1,
        order_type="limit",
        price=100_000,
        exchange="KRX",
        simulated=True,
        requested_at="2026-04-01T09:00:00",
    )

    risk.register_order(response, amount_krw=100_000)

    assert risk.state.daily_order_count == 1
