"""Paper-trading execution helpers."""

from __future__ import annotations

from uuid import uuid4

from app.models.trading import FillEvent, OrderIntent


class PaperBroker:
    """Simulate fills immediately using configurable slippage."""

    def simulate_fill(self, intent: OrderIntent, current_price: int, slippage_bps: int) -> FillEvent:
        """Return an immediate simulated fill."""

        fill_price = simulate_fill_price(intent, current_price, slippage_bps)
        return FillEvent(
            id=f"fill-{uuid4().hex[:12]}",
            order_intent_id=intent.id,
            symbol=intent.symbol,
            name=intent.name,
            side=intent.side,
            price=fill_price,
            quantity=intent.quantity,
            fill_value_krw=fill_price * intent.quantity,
            paper=True,
            reason="Simulated immediate fill.",
        )


def simulate_fill_price(intent: OrderIntent, current_price: int, slippage_bps: int) -> int:
    """Estimate a realistic fill price for paper trading."""

    anchor = intent.desired_price or intent.trigger_price or current_price
    slippage = max(anchor * slippage_bps // 10_000, 1)

    if intent.side == "buy":
        if intent.order_type == "limit":
            return max(anchor, current_price)
        if intent.order_type == "stop_limit":
            return max(current_price, anchor + slippage)
        return current_price + slippage

    if intent.order_type == "limit":
        return min(anchor, current_price)
    if intent.order_type == "stop_limit":
        return max(min(current_price, anchor - slippage), 1)
    return max(current_price - slippage, 1)

