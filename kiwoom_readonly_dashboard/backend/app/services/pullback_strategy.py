"""52-week-high pullback strategy engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.trading import PriceLevel, RiskConfig, StrategyConfig, StrategyDecision, TradeBar


@dataclass
class PullbackAnalysis:
    passed: bool
    ratio: float | None
    rally_volume_avg: float | None
    pullback_volume_avg: float | None
    breakout_price: int | None
    support_price: int | None
    support_reference: str | None
    summary: str


@dataclass
class TriggerAnalysis:
    passed: bool
    entry_price: int | None
    vwap: float | None
    bullish_reversal: bool
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
        if len(daily_bars) < minimum_daily:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="insufficient_data",
                summary="Not enough history to evaluate the strategy safely.",
                reasons=[
                    f"daily_bars={len(daily_bars)} required>={minimum_daily}",
                ],
            )

        if self.config.strategy_profile == "high52_breakout":
            return self._evaluate_high52_breakout_strategy(symbol, daily_bars)

        if self.config.strategy_profile == "box_breakout":
            return self._evaluate_box_breakout_strategy(symbol, daily_bars)

        if len(bars_60m) < self.config.min_intraday_bars:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="insufficient_data",
                summary="Not enough intraday history to evaluate the pullback strategy safely.",
                reasons=[
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
                breakout_price=to_int_or_none(daily_filter.get("breakout_price")),
                metrics=daily_filter,
            )

        pullback = self._evaluate_pullback(bars_60m, daily_filter)
        if not pullback.passed:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="pullback_filter",
                summary=pullback.summary,
                reasons=[pullback.summary],
                breakout_price=to_int_or_none(daily_filter.get("breakout_price")),
                pullback_ratio=pullback.ratio,
                rally_volume_avg=pullback.rally_volume_avg,
                pullback_volume_avg=pullback.pullback_volume_avg,
                annotations=self._build_annotations(
                    entry_price=None,
                    stop_price=None,
                    target_price=None,
                    breakout_price=pullback.breakout_price or to_int_or_none(daily_filter.get("breakout_price")),
                    support_price=pullback.support_price,
                ),
                metrics={"daily": daily_filter, "support_reference": pullback.support_reference},
            )

        decision_breakout_price = to_int_or_none(daily_filter.get("breakout_price")) or pullback.breakout_price
        trigger_reference_price = pullback.support_price or decision_breakout_price
        trigger = self._evaluate_trigger(
            trigger_bars,
            breakout_price=trigger_reference_price,
        )
        if not trigger.passed:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="trigger",
                summary=trigger.summary,
                reasons=[trigger.summary],
                breakout_price=decision_breakout_price,
                pullback_ratio=pullback.ratio,
                rally_volume_avg=pullback.rally_volume_avg,
                pullback_volume_avg=pullback.pullback_volume_avg,
                vwap=trigger.vwap,
                annotations=self._build_annotations(
                    entry_price=None,
                    stop_price=None,
                    target_price=None,
                    breakout_price=decision_breakout_price,
                    support_price=pullback.support_price,
                ),
                metrics={
                    "daily": daily_filter,
                    "support_reference": pullback.support_reference,
                    "bullish_reversal": trigger.bullish_reversal,
                },
            )

        entry_price = int(trigger.entry_price or trigger_bars[-1].close)
        breakout_price = decision_breakout_price
        support_price = pullback.support_price
        stop_price = self._calculate_stop_price(entry_price, support_price)
        target_price = self._calculate_profit_reference_price(
            entry_price=entry_price,
            breakout_price=breakout_price,
            strategy_profile="high52_pullback",
        )

        return StrategyDecision(
            symbol=symbol,
            passed=True,
            stage="buy_signal",
            summary="All daily, pullback and trigger filters passed. A buy signal is ready.",
            reasons=[
                "Daily close is above the fast MA.",
                "Fast MA is above the slow MA.",
                "A recent 52-week breakout was confirmed with strong daily volume.",
                "60-minute pullback depth and volume contraction passed.",
                "The pullback held the configured breakout / moving-average support zone.",
                f"{self.config.trigger_timeframe} trigger confirmed the rebound.",
            ],
            entry_timeframe=self.config.trigger_timeframe,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            breakout_price=breakout_price,
            pullback_ratio=pullback.ratio,
            rally_volume_avg=pullback.rally_volume_avg,
            pullback_volume_avg=pullback.pullback_volume_avg,
            vwap=trigger.vwap,
            annotations=self._build_annotations(
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                breakout_price=breakout_price,
                support_price=support_price,
            ),
            metrics={
                "daily": daily_filter,
                "pullback_ratio": pullback.ratio,
                "support_reference": pullback.support_reference,
                "support_price": support_price,
                "vwap": trigger.vwap,
                "bullish_reversal": trigger.bullish_reversal,
            },
        )

    def _evaluate_high52_breakout_strategy(
        self,
        symbol: str,
        daily_bars: list[TradeBar],
    ) -> StrategyDecision:
        """Evaluate a simpler 52-week breakout continuation profile."""

        daily_filter = self._evaluate_daily_filter(daily_bars)
        if not daily_filter["passed"]:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="daily_filter",
                summary="The 52-week breakout profile did not pass the daily trend filter.",
                reasons=daily_filter["reasons"],
                breakout_price=to_int_or_none(daily_filter.get("breakout_price")),
                metrics=daily_filter,
            )

        latest = daily_bars[-1]
        breakout_price = to_int_or_none(daily_filter.get("breakout_price")) or latest.high
        threshold = int(breakout_price * (1 - self.config.breakout_entry_buffer_pct))
        if latest.close < threshold:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="trigger",
                summary="The stock is near a 52-week breakout but has not reclaimed the breakout area strongly enough.",
                reasons=[
                    f"latest_close={latest.close}",
                    f"breakout_hold_threshold={threshold}",
                ],
                breakout_price=breakout_price,
                annotations=self._build_annotations(
                    entry_price=None,
                    stop_price=None,
                    target_price=None,
                    breakout_price=breakout_price,
                    support_price=to_int_or_none(daily_filter.get("ma_fast")),
                ),
                metrics=daily_filter,
            )

        entry_price = max(latest.close, breakout_price)
        support_price = to_int_or_none(daily_filter.get("ma_fast"))
        stop_price = self._calculate_stop_price(entry_price, support_price)
        target_price = self._calculate_profit_reference_price(
            entry_price=entry_price,
            breakout_price=breakout_price,
            strategy_profile="high52_breakout",
        )
        return StrategyDecision(
            symbol=symbol,
            passed=True,
            stage="buy_signal",
            summary="The 52-week breakout continuation profile is active.",
            reasons=[
                "Close is above the fast moving average.",
                "Fast moving average is above the slow moving average.",
                "A recent 52-week breakout with strong volume was confirmed.",
                "Price is still holding above the breakout zone.",
            ],
            entry_timeframe="daily",
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            breakout_price=breakout_price,
            annotations=self._build_annotations(
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                breakout_price=breakout_price,
                support_price=support_price,
            ),
            metrics=daily_filter,
        )

    def _evaluate_box_breakout_strategy(
        self,
        symbol: str,
        daily_bars: list[TradeBar],
    ) -> StrategyDecision:
        """Evaluate a Darvas-like box breakout profile on daily bars."""

        minimum_bars = max(
            self.config.daily_ma_slow + 5,
            self.config.box_window_days + 2,
            self.config.min_daily_bars,
        )
        if len(daily_bars) < minimum_bars:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="insufficient_data",
                summary="Not enough history to evaluate the box-breakout profile safely.",
                reasons=[f"daily_bars={len(daily_bars)} required>={minimum_bars}"],
            )

        closes = [bar.close for bar in daily_bars]
        ma_fast = moving_average(closes, self.config.daily_ma_fast)
        ma_slow = moving_average(closes, self.config.daily_ma_slow)
        latest = daily_bars[-1]
        box_window = daily_bars[-self.config.box_window_days - 1 : -1]
        box_high = max(bar.high for bar in box_window)
        box_low = min(bar.low for bar in box_window)
        box_range_pct = ((box_high - box_low) / box_low) if box_low else 0.0
        avg_volume = average([bar.volume for bar in box_window])
        volume_ratio = (latest.volume / avg_volume) if avg_volume else 0.0
        breakout_threshold = int(box_high * (1 + self.config.box_breakout_buffer_pct))

        reasons: list[str] = []
        passed = True
        if latest.close <= ma_fast:
            passed = False
            reasons.append("Close is not above the fast moving average.")
        if ma_fast <= ma_slow:
            passed = False
            reasons.append("Fast moving average is not above the slow moving average.")
        if box_range_pct > self.config.box_max_range_pct:
            passed = False
            reasons.append("The recent box range is too wide to qualify as a tight consolidation.")
        if latest.close < breakout_threshold:
            passed = False
            reasons.append("Price has not broken above the recent box high.")
        if volume_ratio < self.config.box_breakout_volume_multiplier:
            passed = False
            reasons.append("Breakout volume is not strong enough versus the recent box average.")

        metrics = {
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "box_high": box_high,
            "box_low": box_low,
            "box_range_pct": box_range_pct,
            "volume_ratio": volume_ratio,
            "breakout_threshold": breakout_threshold,
        }
        if not passed:
            return StrategyDecision(
                symbol=symbol,
                passed=False,
                stage="trigger",
                summary="The box-breakout profile did not confirm yet.",
                reasons=reasons,
                breakout_price=box_high,
                annotations=self._build_annotations(
                    entry_price=None,
                    stop_price=None,
                    target_price=None,
                    breakout_price=box_high,
                    support_price=box_low,
                ),
                metrics=metrics,
            )

        entry_price = max(latest.close, breakout_threshold)
        stop_price = self._calculate_stop_price(entry_price, box_low)
        target_price = self._calculate_profit_reference_price(
            entry_price=entry_price,
            breakout_price=box_high,
            strategy_profile="box_breakout",
        )
        return StrategyDecision(
            symbol=symbol,
            passed=True,
            stage="buy_signal",
            summary="The box-breakout profile is active.",
            reasons=[
                "A tight daily box formed under resistance.",
                "Price closed above the box high.",
                "Breakout volume expanded versus the recent box average.",
                "The higher-timeframe moving averages still point up.",
            ],
            entry_timeframe="daily",
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            breakout_price=box_high,
            annotations=self._build_annotations(
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                breakout_price=box_high,
                support_price=box_low,
            ),
            metrics=metrics,
        )

    def _evaluate_daily_filter(self, bars: list[TradeBar]) -> dict[str, object]:
        closes = [bar.close for bar in bars]
        ma_fast = moving_average(closes, self.config.daily_ma_fast)
        ma_slow = moving_average(closes, self.config.daily_ma_slow)
        current_close = closes[-1]
        recent_window = bars[-252:] if len(bars) >= 252 else bars
        highest_52w = max(bar.high for bar in recent_window)
        breakout_bar: TradeBar | None = None
        breakout_volume_ratio: float | None = None

        recent_start = max(0, len(bars) - self.config.recent_breakout_days)
        for index in range(len(bars) - 1, recent_start - 1, -1):
            bar = bars[index]
            trailing = bars[max(0, index - 251) : index + 1]
            prior_trailing = trailing[:-1]
            if not prior_trailing:
                continue
            prior_high = max(item.high for item in prior_trailing)
            if bar.high < prior_high:
                continue

            volume_window = bars[max(0, index - self.config.breakout_volume_lookback_days) : index]
            avg_volume = average([item.volume for item in volume_window])
            volume_ratio = (bar.volume / avg_volume) if avg_volume else 0.0
            if volume_ratio >= self.config.breakout_volume_multiplier:
                breakout_bar = bar
                breakout_volume_ratio = volume_ratio
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
            reasons.append(
                "No recent 52-week breakout with strong enough daily volume was found in the configured window."
            )

        return {
            "passed": passed,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "current_close": current_close,
            "highest_52w": highest_52w,
            "breakout_price": breakout_bar.high if breakout_bar else highest_52w,
            "breakout_date": breakout_bar.time if breakout_bar else None,
            "breakout_volume_ratio": breakout_volume_ratio,
            "reasons": reasons,
        }

    def _evaluate_pullback(
        self,
        bars_60m: list[TradeBar],
        daily_filter: dict[str, object],
    ) -> PullbackAnalysis:
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
                support_price=None,
                support_reference=None,
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
                support_price=None,
                support_reference=None,
                summary="The 60-minute pullback depth is outside the configured ratio band.",
            )

        if pullback_volume_avg > rally_volume_avg * self.config.volume_dryup_ratio:
            return PullbackAnalysis(
                passed=False,
                ratio=ratio,
                rally_volume_avg=rally_volume_avg,
                pullback_volume_avg=pullback_volume_avg,
                breakout_price=rally_high,
                support_price=None,
                support_reference=None,
                summary="Pullback volume has not dried up enough versus the prior rally.",
            )

        support_price, support_reference, support_ok = self._evaluate_support_zone(
            pullback_low=pullback_low,
            breakout_price=to_int_or_none(daily_filter.get("breakout_price")),
            ma_fast=daily_filter.get("ma_fast"),
        )
        if support_price is not None and not support_ok:
            return PullbackAnalysis(
                passed=False,
                ratio=ratio,
                rally_volume_avg=rally_volume_avg,
                pullback_volume_avg=pullback_volume_avg,
                breakout_price=rally_high,
                support_price=support_price,
                support_reference=support_reference,
                summary="The pullback fell too far below the configured support zone.",
            )

        return PullbackAnalysis(
            passed=True,
            ratio=ratio,
            rally_volume_avg=rally_volume_avg,
            pullback_volume_avg=pullback_volume_avg,
            breakout_price=rally_high,
            support_price=support_price,
            support_reference=support_reference,
            summary="60-minute pullback depth, volume contraction and support-hold checks passed.",
        )

    def _evaluate_trigger(
        self,
        bars: list[TradeBar],
        breakout_price: int | None,
    ) -> TriggerAnalysis:
        if len(bars) < 12:
            return TriggerAnalysis(
                passed=False,
                entry_price=None,
                vwap=None,
                bullish_reversal=False,
                summary="Not enough trigger bars were available for the short-term entry check.",
            )

        recent = bars[-5:]
        previous = bars[-6:-1]
        latest = recent[-1]
        higher_low = min(bar.low for bar in recent[-2:]) > min(bar.low for bar in previous[-2:])
        breakout = latest.close > max(bar.high for bar in previous[-3:])
        fast_ma = moving_average([bar.close for bar in bars], 5)
        slow_ma = moving_average([bar.close for bar in bars], 10)
        vwap_value = calculate_vwap(bars[-20:])
        bullish_reversal = latest.close >= latest.open or latest.close > previous[-1].close

        checks = [higher_low or breakout, fast_ma > slow_ma]
        if breakout_price is not None:
            checks.append(latest.close >= int(breakout_price * (1 - self.config.support_tolerance_pct)))
        if self.config.use_vwap:
            checks.append(latest.close > vwap_value)
        if self.config.require_bullish_reversal_candle:
            checks.append(bullish_reversal)

        if not all(checks):
            return TriggerAnalysis(
                passed=False,
                entry_price=None,
                vwap=vwap_value,
                bullish_reversal=bullish_reversal,
                summary="The lower timeframe rebound trigger has not confirmed yet.",
            )

        entry_price = max(latest.close, previous[-1].high)
        return TriggerAnalysis(
            passed=True,
            entry_price=entry_price,
            vwap=vwap_value,
            bullish_reversal=bullish_reversal,
            summary="The lower timeframe trigger confirmed a rebound from the pullback.",
        )

    def _calculate_stop_price(self, entry_price: int, support_price: int | None) -> int:
        """Use the tighter of the fixed stop and the support-based stop."""

        percent_stop = max(min(int(entry_price * (1 - self.risk.stop_loss_pct)), entry_price - 1), 1)
        stop_candidates = [percent_stop]
        if support_price is not None:
            support_stop = max(
                min(int(support_price * (1 - self.config.support_tolerance_pct)), entry_price - 1),
                1,
            )
            stop_candidates.append(support_stop)
        return max(stop_candidates)

    def _calculate_profit_reference_price(
        self,
        *,
        entry_price: int,
        breakout_price: int | None,
        strategy_profile: str,
    ) -> int | None:
        """Return the first profit-protection zone used by the exit engine.

        The referenced 52-week-high / pullback materials are closer to
        "retest the prior high, then hold until trend damage" than to a fixed
        +4% target. We therefore keep a discrete profit reference only for the
        pullback profile, where a return to the prior breakout zone is a
        meaningful first milestone.
        """

        if strategy_profile != "high52_pullback":
            return None
        if breakout_price is None or breakout_price <= entry_price:
            return None
        return breakout_price

    def _evaluate_support_zone(
        self,
        *,
        pullback_low: int,
        breakout_price: int | None,
        ma_fast: Any,
    ) -> tuple[int | None, str | None, bool]:
        """Evaluate whether the pullback respected the configured support anchors."""

        ma_fast_value = int(float(ma_fast)) if ma_fast is not None else None
        reference = self.config.support_reference
        candidates: list[tuple[int, str]] = []
        if breakout_price is not None and breakout_price > 0:
            candidates.append((breakout_price, "breakout"))
        if ma_fast_value is not None and ma_fast_value > 0:
            candidates.append((ma_fast_value, "ma_fast"))

        if reference == "breakout":
            candidates = [item for item in candidates if item[1] == "breakout"]
        elif reference == "ma_fast":
            candidates = [item for item in candidates if item[1] == "ma_fast"]

        if not candidates:
            return None, None, True

        passed_candidates = [
            item for item in candidates if pullback_low >= item[0] * (1 - self.config.support_tolerance_pct)
        ]
        if reference == "both":
            support_ok = len(passed_candidates) == len(candidates)
            chosen = max(candidates, key=lambda item: item[0])
        else:
            support_ok = len(passed_candidates) > 0
            chosen = max(passed_candidates or candidates, key=lambda item: item[0])

        return chosen[0], reference, support_ok

    def _build_annotations(
        self,
        *,
        entry_price: int | None,
        stop_price: int | None,
        target_price: int | None,
        breakout_price: int | None,
        support_price: int | None,
    ) -> list[PriceLevel]:
        annotations: list[PriceLevel] = []
        if entry_price is not None:
            annotations.append(PriceLevel(label="Entry", price=entry_price, kind="entry"))
        if stop_price is not None:
            annotations.append(PriceLevel(label="Stop", price=stop_price, kind="stop"))
        if target_price is not None:
            annotations.append(PriceLevel(label="Profit Zone", price=target_price, kind="target"))
        if breakout_price is not None:
            annotations.append(PriceLevel(label="Breakout", price=breakout_price, kind="breakout"))
        if support_price is not None:
            annotations.append(PriceLevel(label="Support", price=support_price, kind="support"))
        return annotations


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


def to_int_or_none(value: Any) -> int | None:
    """Convert strategy metric values to int when possible."""

    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
