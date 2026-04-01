"""Demo strategy module.

This strategy is intentionally simple and exists only to validate that the
automation pipeline works end to end in the mock environment.
"""

from __future__ import annotations

import logging

from app.models import DailyCandle, Holding, StockBasicInfo, StrategyDecision, StrategySettings


class PreviousCloseDemoStrategy:
    """Sample strategy based on previous close breakouts."""

    def __init__(self, settings: StrategySettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("strategy")

    def decide(
        self,
        *,
        quote: StockBasicInfo,
        candles: list[DailyCandle],
        holding: Holding | None,
        default_order_type: str,
    ) -> StrategyDecision:
        """Return buy, sell, or hold based on a simple demo rule set."""

        if quote.current_price <= 0:
            return StrategyDecision(action="hold", reason="Current price was unavailable.")

        if len(candles) < 2:
            return StrategyDecision(
                action="hold",
                reason="Not enough daily candle history to compute the previous close.",
            )

        previous_close = candles[-2].close_price
        buy_trigger = previous_close * (1 + self.settings.buy_above_prev_close_pct)

        if holding is None:
            if quote.current_price >= buy_trigger:
                return StrategyDecision(
                    action="buy",
                    reason=(
                        "Sample buy signal: current price is above the configured "
                        "previous-close threshold."
                    ),
                    order_type=default_order_type,
                    price=quote.current_price if default_order_type == "limit" else None,
                )
            return StrategyDecision(
                action="hold",
                reason="No position and buy threshold has not been reached yet.",
            )

        stop_loss_price = holding.purchase_price * (1 - self.settings.stop_loss_pct)
        take_profit_price = holding.purchase_price * (1 + self.settings.take_profit_pct)

        if quote.current_price <= stop_loss_price:
            return StrategyDecision(
                action="sell",
                reason="Sample sell signal: stop-loss threshold reached.",
                quantity=holding.available_quantity,
                order_type=default_order_type,
                price=quote.current_price if default_order_type == "limit" else None,
            )

        if quote.current_price >= take_profit_price:
            return StrategyDecision(
                action="sell",
                reason="Sample sell signal: take-profit threshold reached.",
                quantity=holding.available_quantity,
                order_type=default_order_type,
                price=quote.current_price if default_order_type == "limit" else None,
            )

        return StrategyDecision(
            action="hold",
            reason="Holding position and neither stop-loss nor take-profit was triggered.",
        )

