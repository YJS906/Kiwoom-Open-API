"""Signal execution and broker routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings
from app.models.trading import ExecutionConfig, FillEvent, OrderIntent, SignalEvent
from app.services.kiwoom_client import KiwoomClientService
from app.services.paper_broker import PaperBroker


@dataclass
class ExecutionResult:
    intent: OrderIntent
    fill: FillEvent | None


class OrderExecutor:
    """Route orders to the paper broker or Kiwoom REST."""

    def __init__(
        self,
        settings: Settings,
        config: ExecutionConfig,
        kiwoom_client: KiwoomClientService,
        paper_broker: PaperBroker,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.config = config
        self.kiwoom_client = kiwoom_client
        self.paper_broker = paper_broker
        self.logger = logger.getChild("order_executor")

    async def execute(
        self,
        signal: SignalEvent,
        intent: OrderIntent,
        current_price: int,
    ) -> ExecutionResult:
        """Execute one signal using the configured broker path."""

        if self.config.paper_trading:
            fill = self.paper_broker.simulate_fill(intent, current_price, self.config.slippage_bps)
            intent.state = "filled"
            intent.updated_at = fill.filled_at
            return ExecutionResult(intent=intent, fill=fill)

        if self.config.use_mock_only and self.settings.kiwoom_env != "mock":
            raise RuntimeError("Broker order execution is blocked because KIWOOM_ENV is not mock.")

        if self.settings.kiwoom_env == "mock":
            if not self.config.mock_order_enabled:
                raise RuntimeError("Kiwoom mock-order execution is disabled by feature flag.")
        elif not self.config.real_order_enabled:
            raise RuntimeError("Real order execution is disabled by feature flag.")

        api_id = "kt10000" if intent.side == "buy" else "kt10001"
        trade_type_map = {"market": "3", "limit": "0", "stop_limit": "28"}
        body = {
            "dmst_stex_tp": "KRX",
            "stk_cd": intent.symbol,
            "ord_qty": str(intent.quantity),
            "ord_uv": str(intent.desired_price or ""),
            "trde_tp": trade_type_map[intent.order_type],
            "cond_uv": str(intent.trigger_price or ""),
        }
        result = await self.kiwoom_client._post("/api/dostk/ordr", api_id, body)  # noqa: SLF001
        intent.state = "submitted"
        intent.reason = f"Kiwoom order number: {result.body.get('ord_no', '')}"
        if self.settings.kiwoom_env == "mock":
            self.logger.warning(
                "A Kiwoom mock order was submitted. symbol=%s qty=%s api_id=%s",
                intent.symbol,
                intent.quantity,
                api_id,
            )
        else:
            self.logger.warning(
                "A live order was submitted. symbol=%s qty=%s api_id=%s",
                intent.symbol,
                intent.quantity,
                api_id,
            )
        return ExecutionResult(intent=intent, fill=None)
