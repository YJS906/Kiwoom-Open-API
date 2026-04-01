"""High level trading bot orchestration."""

from __future__ import annotations

import logging

from app.account import AccountService
from app.auth import TokenManager
from app.client import KiwoomRESTClient
from app.market import MarketService
from app.models import AppSettings, Holding, OrderRequest
from app.orders import OrderService
from app.risk import RiskManager
from app.scheduler import PollingScheduler
from app.strategy import PreviousCloseDemoStrategy
from app.utils import normalize_symbol, today_yyyymmdd


class TradingBot:
    """Single-account mock trading bot."""

    def __init__(self, settings: AppSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("bot")
        self.token_manager = TokenManager(settings, logger)
        self.client = KiwoomRESTClient(settings, self.token_manager, logger)
        self.account = AccountService(self.client, logger)
        self.market = MarketService(self.client, logger)
        self.orders = OrderService(settings, self.client, logger)
        self.risk = RiskManager(settings, logger)
        self.strategy = PreviousCloseDemoStrategy(settings.strategy, logger)
        self.scheduler = PollingScheduler(settings.trading.poll_interval_seconds, logger)
        self._initialized = False

    def initialize(self) -> None:
        """Do one-time account validation and token warm-up."""

        if self._initialized:
            return
        self.token_manager.get_access_token(force_refresh=False)
        if self.settings.safety.fail_if_account_mismatch:
            self.account.verify_expected_account(self.settings.credentials.account_no)
        self._initialized = True
        self.logger.info(
            "Bot initialized. environment=%s dry_run=%s",
            self.settings.environment,
            self.settings.safety.dry_run,
        )

    def run_once(self) -> None:
        """Run one full poll cycle."""

        try:
            self.initialize()
            symbol = self.settings.trading.symbol
            exchange = self.settings.trading.exchange
            trade_date = today_yyyymmdd(self.settings.trading.timezone)

            cash = self.account.get_cash_balance()
            snapshot = self.account.get_account_snapshot(exchange=exchange)
            estimated_assets = (
                snapshot.estimated_assets_krw
                or snapshot.total_evaluation_amount_krw
                or cash.deposit_krw
            )
            self.risk.prepare_for_today(trade_date, estimated_assets)
            self.risk.raise_if_daily_loss_hit(estimated_assets)

            if not self.risk.is_market_open():
                self.logger.info("Outside market window. Skipping this cycle.")
                return

            quote = self.market.get_basic_info(symbol=symbol, exchange=exchange)
            candles = self.market.get_daily_candles(symbol=symbol, exchange=exchange, limit=3)
            order_statuses = self.orders.get_order_statuses(exchange=exchange, symbol=symbol)

            current_holding = self._find_holding(snapshot.holdings, symbol)
            decision = self.strategy.decide(
                quote=quote,
                candles=candles,
                holding=current_holding,
                default_order_type=self.settings.trading.default_order_type,
            )
            if decision.action == "hold":
                self.logger.info("No trade: %s", decision.reason)
                return

            quantity = decision.quantity
            if quantity is None:
                quantity = self.risk.calculate_order_quantity(
                    current_price=quote.current_price,
                    available_cash_krw=cash.deposit_krw,
                )

            if decision.action == "sell" and current_holding is not None:
                quantity = min(quantity or 0, current_holding.available_quantity)

            if quantity <= 0:
                self.logger.info("No trade: calculated quantity is 0.")
                return

            order_price = decision.price if decision.order_type == "limit" else None
            order_amount_krw = quantity * quote.current_price
            daily_pnl_krw = self.risk.current_daily_pnl_krw(estimated_assets)
            preflight = self.risk.preflight_check(
                side=decision.action,
                order_amount_krw=order_amount_krw,
                position_count=len(snapshot.holdings),
                daily_pnl_krw=daily_pnl_krw,
                open_order_exists=self.orders.has_open_order(
                    statuses=order_statuses,
                    symbol=symbol,
                    side=decision.action,
                ),
            )
            if not preflight.allowed:
                self.logger.warning("Order blocked by risk checks: %s", " | ".join(preflight.reasons))
                return

            request = OrderRequest(
                symbol=symbol,
                side=decision.action,
                quantity=quantity,
                order_type=decision.order_type,
                price=order_price,
                exchange=exchange,
            )
            response = self.orders.place_order(request, dry_run=self.settings.safety.dry_run)
            self.risk.register_order(response, order_amount_krw)
            self.logger.info(
                "Order completed. simulated=%s order_no=%s side=%s symbol=%s qty=%s",
                response.simulated,
                response.order_no,
                response.side,
                response.symbol,
                response.quantity,
            )
            if not response.simulated and response.order_no:
                follow_up_statuses = self.orders.get_order_statuses(
                    exchange=exchange,
                    symbol=symbol,
                    order_no=response.order_no,
                )
                matched = [status for status in follow_up_statuses if status.order_no == response.order_no]
                if matched:
                    latest = matched[0]
                    self.logger.info(
                        "Order status follow-up: order_no=%s filled=%s remaining=%s accepted_type=%s",
                        latest.order_no,
                        latest.filled_quantity,
                        latest.remaining_quantity,
                        latest.accepted_type,
                    )
        except Exception as exc:
            self.logger.exception("Bot cycle failed: %s", exc)
            if self.settings.safety.stop_on_error:
                self.risk.halt(f"Stopped due to exception: {exc}")
                raise

    def run_forever(self) -> None:
        """Run the bot on an interval until interrupted."""

        self.scheduler.run(self.run_once)

    @staticmethod
    def _find_holding(holdings: list[Holding], symbol: str) -> Holding | None:
        for holding in holdings:
            if normalize_symbol(holding.symbol) == normalize_symbol(symbol):
                return holding
        return None
