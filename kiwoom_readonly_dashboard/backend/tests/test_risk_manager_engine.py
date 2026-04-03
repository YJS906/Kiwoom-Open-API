"""Tests for the risk manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.schemas import AccountSummary, HoldingItem, StockQuote, StockSearchItem
from app.models.trading import PositionState, RiskConfig, SessionConfig, SessionState
from app.services.risk_manager import RiskManager
from app.services.session_guard import SessionGuard


SEOUL = timezone(timedelta(hours=9))


def build_summary() -> AccountSummary:
    return AccountSummary(
        total_evaluation_amount=1_000_000,
        total_profit_loss=0,
        total_profit_rate=0.0,
        holdings_count=0,
        deposit=1_000_000,
        orderable_amount=1_000_000,
        estimated_assets=1_000_000,
        updated_at=datetime(2026, 4, 2, 9, 0, tzinfo=SEOUL),
    )


def build_quote(change_rate: float = 2.0) -> StockQuote:
    return StockQuote(
        symbol="005930",
        name="Samsung Electronics",
        current_price=80_000,
        previous_close=79_000,
        diff_from_previous_close=1_000,
        change_rate=change_rate,
        volume=100_000,
        open_price=79_500,
        high_price=80_500,
        low_price=79_200,
        updated_at=datetime(2026, 4, 2, 9, 0, tzinfo=SEOUL),
    )


def test_risk_manager_blocks_when_position_limit_is_hit() -> None:
    config = RiskConfig(max_positions=1)
    manager = RiskManager(config, SessionGuard(SessionConfig()))
    decision = manager.evaluate_entry(
        symbol="005930",
        entry_price=80_000,
        account_summary=build_summary(),
        actual_holdings=[
            HoldingItem(
                symbol="000660",
                name="SK Hynix",
                quantity=1,
                available_quantity=1,
                average_price=100_000,
                current_price=100_000,
                evaluation_profit_loss=0,
                profit_rate=0.0,
            )
        ],
        paper_positions={},
        session=SessionState(
            trade_date="20260402",
            paper_cash_balance_krw=1_000_000,
            actual_available_cash_krw=1_000_000,
        ),
        quote=build_quote(),
        metadata=StockSearchItem(
            symbol="005930",
            name="Samsung Electronics",
            market_code="0",
            market_name="KOSPI",
            last_price=80_000,
        ),
        now=datetime(2026, 4, 2, 10, 0, tzinfo=SEOUL),
    )

    assert decision.allowed is False
    assert any("maximum number of positions" in reason for reason in decision.reasons)


def test_risk_manager_allows_normal_entry() -> None:
    config = RiskConfig(max_positions=3, max_daily_new_entries=3)
    manager = RiskManager(config, SessionGuard(SessionConfig()))
    decision = manager.evaluate_entry(
        symbol="005930",
        entry_price=80_000,
        account_summary=build_summary(),
        actual_holdings=[],
        paper_positions={},
        session=SessionState(
            trade_date="20260402",
            paper_cash_balance_krw=1_000_000,
            actual_available_cash_krw=1_000_000,
        ),
        quote=build_quote(change_rate=1.5),
        metadata=StockSearchItem(
            symbol="005930",
            name="Samsung Electronics",
            market_code="0",
            market_name="KOSPI",
            last_price=80_000,
        ),
        now=datetime(2026, 4, 2, 10, 0, tzinfo=SEOUL),
    )

    assert decision.allowed is True
    assert decision.quantity > 0


def test_risk_manager_blocks_duplicate_symbol() -> None:
    manager = RiskManager(RiskConfig(), SessionGuard(SessionConfig()))
    decision = manager.evaluate_entry(
        symbol="005930",
        entry_price=80_000,
        account_summary=build_summary(),
        actual_holdings=[],
        paper_positions={
            "005930": PositionState(
                symbol="005930",
                name="Samsung Electronics",
                quantity=1,
                avg_price=80_000,
                current_price=80_000,
                market_value_krw=80_000,
                unrealized_pnl_krw=0,
            )
        },
        session=SessionState(
            trade_date="20260402",
            paper_cash_balance_krw=1_000_000,
            actual_available_cash_krw=1_000_000,
        ),
        quote=build_quote(),
        metadata=StockSearchItem(
            symbol="005930",
            name="Samsung Electronics",
            market_code="0",
            market_name="KOSPI",
            last_price=80_000,
        ),
        now=datetime(2026, 4, 2, 10, 0, tzinfo=SEOUL),
    )

    assert decision.allowed is False
    assert any("already held" in reason for reason in decision.reasons)
