"""52-week-high pullback strategy engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.trading import PriceLevel, RiskConfig, StrategyConfig, StrategyDecision, TradeBar


@dataclass
class PullbackAnalysis:
    passed: bool
    ratio: float | None
    rally_volume_avg: float | None
    pullback_volume_avg: float | None
    breakout_price: int | None
    summary: str


@dataclass
class TriggerAnalysis:
    passed: bool
    entry_price: int | None
    vwap: float | None
    summary: str


class PullbackStrategyEngine:
    """Pure-ish strategy evaluator that can be unit tested."""

    def __init__(self, config: StrategyConfig, risk: RiskConfig) -> None:
        self.config = config
        self.risk = risk

    def evaluate(
        self,
        *,
        symbol: str,
        daily_bars: list[TradeBar],
        bars_60m: list[TradeBar],
        trigger_bars: list[TradeBar],
    ) -> StrategyDecision:
        """Evaluate the pullback strategy and return a detailed decision."""

        minimum_daily = max(self.config.daily_ma_slow + 5, self.config.min_daily_bars)
        if len(daily_bars) < minimum_daily or len(bars_60m) < self.config.min_intraday_bars:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="insufficient_data",
                summary="Not enough history to evaluate the strategy safely.",
                reasons=[
                    f"daily_bars={len(daily_bars)} required>={minimum_daily}",
                    f"bars_60m={len(bars_60m)} required>={self.config.min_intraday_bars}",
                ],
            )

        daily_filter = self._evaluate_daily_filter(daily_bars)
        if not daily_filter["passed"]:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="daily_filter",
                summary="The daily trend filter did not pass.",
                reasons=daily_filter["reasons"],
                breakout_price=daily_filter.get("breakout_price"),
                metrics=daily_filter,
            )

        pullback = self._evaluate_pullback(bars_60m)
        if not pullback.passed:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="pullback_filter",
                summary=pullback.summary,
                reasons=[pullback.summary],
                breakout_price=daily_filter.get("breakout_price"),
                pullback_ratio=pullback.ratio,
                rally_volume_avg=pullback.rally_volume_avg,
                pullback_volume_avg=pullback.pullback_volume_avg,
                metrics={"daily": daily_filter},
            )

        trigger = self._evaluate_trigger(trigger_bars)
        if not trigger.passed:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="trigger",
                summary=trigger.summary,
                reasons=[trigger.summary],
                breakout_price=pullback.breakout_price or daily_filter.get("breakout_price"),
                pullback_ratio=pullback.ratio,
                rally_volume_avg=pullback.rally_volume_avg,
                pullback_volume_avg=pullback.pullback_volume_avg,
                vwap=trigger.vwap,
                metrics={"daily": daily_filter},
            )

        entry_price = int(trigger.entry_price or trigger_bars[-1].close)
        stop_price = max(int(entry_price * (1 - self.risk.stop_loss_pct)), 1)
        risk_per_share = max(entry_price - stop_price, 1)
        target_price = entry_price + int(risk_per_share * self.risk.take_profit_r_multiple)

        return StrategyDecision(
            symbol=symbol,
            passed=True,
            stage="buy_signal",
            summary="All daily, pullback and trigger filters passed. A buy signal is ready.",
            reasons=[
                "Daily close is above the fast MA.",
                "Fast MA is above the slow MA.",
                "A recent 52-week breakout is still in effect.",
                "60-minute pullback depth and volume contraction passed.",
                f"{self.config.trigger_timeframe} trigger confirmed the rebound.",
            ],
            entry_timeframe=self.config.trigger_timeframe,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            breakout_price=pullback.breakout_price or daily_filter.get("breakout_price"),
            pullback_ratio=pullback.ratio,
            rally_volume_avg=pullback.rally_volume_avg,
            pullback_volume_avg=pullback.pullback_volume_avg,
            vwap=trigger.vwap,
            annotations=[
                PriceLevel(label="Entry", price=entry_price, kind="entry"),
                PriceLevel(label="Stop", price=stop_price, kind="stop"),
                PriceLevel(label="Target", price=target_price, kind="target"),
                PriceLevel(
                    label="Breakout",
                    price=int(pullback.breakout_price or daily_filter.get("breakout_price") or entry_price),
                    kind="breakout",
                ),
            ],
            metrics={
                "daily": daily_filter,
                "pullback_ratio": pullback.ratio,
                "vwap": trigger.vwap,
            },
        )

    def _evaluate_daily_filter(self, bars: list[TradeBar]) -> dict[str, object]:
        closes = [bar.close for bar in bars]
        ma_fast = moving_average(closes, self.config.daily_ma_fast)
        ma_slow = moving_average(closes, self.config.daily_ma_slow)
        current_close = closes[-1]
        recent_window = bars[-252:] if len(bars) >= 252 else bars
        highest_52w = max(bar.high for bar in recent_window)
        breakout_bar = None
        for bar in reversed(bars[-self.config.recent_breakout_days :]):
            trailing = [item.high for item in bars if item.time <= bar.time][-252:]
            if trailing and bar.high >= max(trailing):
                breakout_bar = bar
                break

        reasons: list[str] = []
        passed = True
        if current_close <= ma_fast:
            passed = False
            reasons.append("Close is not above the fast moving average.")
        if ma_fast <= ma_slow:
            passed = False
            reasons.append("Fast moving average is not above the slow moving average.")
        if breakout_bar is None:
            passed = False
            reasons.append("No recent 52-week breakout was found in the configured window.")

        return {
            "passed": passed,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "current_close": current_close,
            "highest_52w": highest_52w,
            "breakout_price": breakout_bar.high if breakout_bar else highest_52w,
            "breakout_date": breakout_bar.time if breakout_bar else None,
            "reasons": reasons,
        }

    def _evaluate_pullback(self, bars_60m: list[TradeBar]) -> PullbackAnalysis:
        window = bars_60m[-self.config.rally_window_bars_60m :]
        breakout_bar = max(window, key=lambda bar: bar.high)
        breakout_index = window.index(breakout_bar)
        if breakout_index < 2 or breakout_index >= len(window) - 2:
            return PullbackAnalysis(
                passed=False,
                ratio=None,
                rally_volume_avg=None,
                pullback_volume_avg=None,
                breakout_price=breakout_bar.high,
                summary="The 60-minute bars do not show a usable rally and pullback structure.",
            )

        rally_leg = window[max(0, breakout_index - self.config.breakout_lookback_bars_60m) : breakout_index + 1]
        pullback_leg = window[breakout_index + 1 :]
        rally_low = min(bar.low for bar in rally_leg)
        rally_high = breakout_bar.high
        pullback_low = min(bar.low for bar in pullback_leg)
        rally_range = max(rally_high - rally_low, 1)
        pullback_range = max(rally_high - pullback_low, 0)
        ratio = pullback_range / rally_range
        rally_volume_avg = average([bar.volume for bar in rally_leg])
        pullback_volume_avg = average([bar.volume for bar in pullback_leg])

        if not (self.config.pullback_min_ratio <= ratio <= self.config.pullback_max_ratio):
            return PullbackAnalysis(
                passed=False,
                ratio=ratio,
                rally_volume_avg=rally_volume_avg,
                pullback_volume_avg=pullback_volume_avg,
                breakout_price=rally_high,
                summary="The 60-minute pullback depth is outside the configured ratio band.",
            )

        if pullback_volume_avg > rally_volume_avg * self.config.volume_dryup_ratio:
            return PullbackAnalysis(
                passed=False,
                ratio=ratio,
                rally_volume_avg=rally_volume_avg,
                pullback_volume_avg=pullback_volume_avg,
                breakout_price=rally_high,
                summary="Pullback volume has not dried up enough versus the prior rally.",
            )

        return PullbackAnalysis(
            passed=True,
            ratio=ratio,
            rally_volume_avg=rally_volume_avg,
            pullback_volume_avg=pullback_volume_avg,
            breakout_price=rally_high,
            summary="60-minute pullback depth and volume contraction passed.",
        )

    def _evaluate_trigger(self, bars: list[TradeBar]) -> TriggerAnalysis:
        if len(bars) < 12:
            return TriggerAnalysis(
                passed=False,
                entry_price=None,
                vwap=None,
                summary="Not enough trigger bars were available for the short-term entry check.",
            )

        recent = bars[-5:]
        previous = bars[-6:-1]
        higher_low = min(bar.low for bar in recent[-2:]) > min(bar.low for bar in previous[-2:])
        breakout = recent[-1].close > max(bar.high for bar in previous[-3:])
        fast_ma = moving_average([bar.close for bar in bars], 5)
        slow_ma = moving_average([bar.close for bar in bars], 10)
        vwap_value = calculate_vwap(bars[-20:])

        checks = [higher_low or breakout, fast_ma > slow_ma]
        if self.config.use_vwap:
            checks.append(bars[-1].close > vwap_value)

        if not all(checks):
            return TriggerAnalysis(
                passed=False,
                entry_price=None,
                vwap=vwap_value,
                summary="The lower timeframe rebound trigger has not confirmed yet.",
            )

        entry_price = max(recent[-1].close, previous[-1].high)
        return TriggerAnalysis(
            passed=True,
            entry_price=entry_price,
            vwap=vwap_value,
            summary="The lower timeframe trigger confirmed a rebound from the pullback.",
        )


def moving_average(values: list[int], length: int) -> float:
    """Simple moving average."""

    if not values:
        return 0.0
    if len(values) < length:
        return average(values)
    return average(values[-length:])


def average(values: list[int]) -> float:
    """Arithmetic mean with safe empty handling."""

    if not values:
        return 0.0
    return sum(values) / len(values)


def calculate_vwap(bars: list[TradeBar]) -> float:
    """Calculate VWAP for a bar window."""

    numerator = 0.0
    denominator = 0.0
    for bar in bars:
        typical = (bar.high + bar.low + bar.close) / 3
        numerator += typical * bar.volume
        denominator += bar.volume
    return numerator / denominator if denominator else 0.0

