"""Paper position state updates."""

from __future__ import annotations

from copy import deepcopy

from app.models.trading import FillEvent, OrderIntent, PositionState, now_kr


class PositionManager:
    """Apply fills and keep paper positions marked to market."""

    def apply_fill(
        self,
        positions: dict[str, PositionState],
        fill: FillEvent,
        order: OrderIntent,
    ) -> tuple[dict[str, PositionState], int]:
        """Apply one fill and return updated positions plus realized PnL."""

        updated = deepcopy(positions)
        symbol = fill.symbol
        realized = 0
        current = updated.get(symbol)

        if fill.side == "buy":
            if current is None:
                updated[symbol] = PositionState(
                    symbol=symbol,
                    name=fill.name,
                    quantity=fill.quantity,
                    avg_price=fill.price,
                    current_price=fill.price,
                    market_value_krw=fill.price * fill.quantity,
                    unrealized_pnl_krw=0,
                    stop_price=order.stop_price,
                    target_price=order.target_price,
                    highest_price=fill.price,
                    opened_at=fill.filled_at,
                    last_updated_at=fill.filled_at,
                )
            else:
                new_quantity = current.quantity + fill.quantity
                total_cost = current.avg_price * current.quantity + fill.price * fill.quantity
                current.quantity = new_quantity
                current.avg_price = total_cost // max(new_quantity, 1)
                current.current_price = fill.price
                current.market_value_krw = current.current_price * current.quantity
                current.unrealized_pnl_krw = (current.current_price - current.avg_price) * current.quantity
                current.last_updated_at = fill.filled_at
                current.stop_price = order.stop_price or current.stop_price
                current.target_price = order.target_price or current.target_price
                current.highest_price = max(current.highest_price or 0, fill.price, current.current_price)
                updated[symbol] = current
            return updated, realized

        if current is None:
            return updated, realized

        sell_quantity = min(fill.quantity, current.quantity)
        realized = (fill.price - current.avg_price) * sell_quantity
        current.quantity -= sell_quantity
        current.realized_pnl_krw += realized
        current.current_price = fill.price
        current.market_value_krw = current.current_price * current.quantity
        current.unrealized_pnl_krw = (current.current_price - current.avg_price) * current.quantity
        current.last_updated_at = fill.filled_at
        if current.quantity <= 0:
            current.quantity = 0
            current.closed_at = fill.filled_at
            updated.pop(symbol, None)
        else:
            updated[symbol] = current
        return updated, realized

    def mark_to_market(
        self,
        positions: dict[str, PositionState],
        quotes: dict[str, int],
    ) -> dict[str, PositionState]:
        """Update current prices without changing the average price."""

        updated = deepcopy(positions)
        for symbol, position in updated.items():
            price = quotes.get(symbol)
            if price is None or price <= 0:
                continue
            position.current_price = price
            position.market_value_krw = price * position.quantity
            position.unrealized_pnl_krw = (price - position.avg_price) * position.quantity
            position.highest_price = max(position.highest_price or 0, price)
            position.last_updated_at = now_kr()
        return updated
