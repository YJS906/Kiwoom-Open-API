"""Tests for paper and Kiwoom mock order execution paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.trading import ExecutionConfig, OrderIntent, StrategyDecision, SignalEvent
from app.services.order_executor import OrderExecutor
from app.services.paper_broker import PaperBroker


@dataclass
class DummyResponse:
    body: dict[str, object]


class StubKiwoomClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def _post(self, path: str, api_id: str, body: dict[str, object]) -> DummyResponse:
        self.calls.append((path, api_id, body))
        return DummyResponse(body={"ord_no": "MOCK-12345"})


def make_signal() -> SignalEvent:
    return SignalEvent(
        id="sig-1",
        symbol="005930",
        name="Samsung Electronics",
        signal_type="entry",
        decision=StrategyDecision(
            symbol="005930",
            passed=True,
            stage="buy_signal",
            summary="Buy signal",
            entry_price=100_000,
        ),
        explanation="Buy signal",
    )


def make_intent() -> OrderIntent:
    return OrderIntent(
        id="ord-1",
        signal_id="sig-1",
        symbol="005930",
        name="Samsung Electronics",
        side="buy",
        quantity=3,
        order_type="market",
        desired_price=100_000,
        paper=True,
    )


async def test_order_executor_simulates_fill_when_paper_trading_enabled(settings, logger) -> None:
    client = StubKiwoomClient()
    executor = OrderExecutor(settings, ExecutionConfig(paper_trading=True), client, PaperBroker(), logger)

    result = await executor.execute(make_signal(), make_intent(), current_price=99_500)

    assert result.fill is not None
    assert result.intent.state == "filled"
    assert client.calls == []


async def test_order_executor_blocks_mock_orders_when_flag_is_disabled(settings, logger) -> None:
    client = StubKiwoomClient()
    executor = OrderExecutor(
        settings,
        ExecutionConfig(paper_trading=False, mock_order_enabled=False, real_order_enabled=False),
        client,
        PaperBroker(),
        logger,
    )

    with pytest.raises(RuntimeError, match="mock-order execution is disabled"):
        await executor.execute(make_signal(), make_intent(), current_price=99_500)


async def test_order_executor_submits_to_kiwoom_mock_when_enabled(settings, logger) -> None:
    client = StubKiwoomClient()
    executor = OrderExecutor(
        settings,
        ExecutionConfig(paper_trading=False, mock_order_enabled=True, real_order_enabled=False),
        client,
        PaperBroker(),
        logger,
    )

    result = await executor.execute(make_signal(), make_intent(), current_price=99_500)

    assert result.fill is None
    assert result.intent.state == "submitted"
    assert result.intent.reason == "Kiwoom order number: MOCK-12345"
    assert client.calls == [
        (
            "/api/dostk/ordr",
            "kt10000",
            {
                "dmst_stex_tp": "KRX",
                "stk_cd": "005930",
                "ord_qty": "3",
                "ord_uv": "100000",
                "trde_tp": "3",
                "cond_uv": "",
            },
        )
    ]
