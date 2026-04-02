# Strategy Research Notes

This document summarizes the strategy ideas that informed the current paper-trading profiles.

## Safety first

- These profiles are for research and paper-trading only.
- They are not investment advice.
- The default profile remains `high52_pullback`.
- `AUTO_BUY_ENABLED` must stay `false` until each profile is validated on replay and paper fills.

## 1. 52-week-high effect

Primary references:

- George, Thomas J. and Hwang, Chuan-Yang. *The 52-Week High and Momentum Investing*.
  - Public mirror: https://sigarra.up.pt/fpceup/en/pub_geral.show_file?pi_doc_id=33114
- Della Vedova, Joshua and Grant, Andrew R. and Westerholm, P. Joakim. *Investor Behavior at the 52 Week High*.
  - SSRN: https://ssrn.com/abstract=3021585

Why it matters:

- The 52-week-high literature suggests that prices near their 52-week high can display momentum-like behavior.
- The later household-investor paper shows how the 52-week-high level can become a strong behavioral anchor.

Implementation impact:

- `high52_breakout` uses a recent 52-week breakout with moving-average confirmation and volume confirmation.
- `high52_pullback` stays more selective by waiting for a constructive pullback after the breakout.

## 2. Pullback after breakout

Practical references:

- Kiwoom Hero4 help and user education material around 52-week highs and condition search.
- Internal rule design built around:
  - recent breakout
  - trend alignment
  - controlled pullback depth
  - volume dry-up
  - lower-timeframe rebound confirmation

Implementation impact:

- `high52_pullback` remains the default.
- This profile tries to avoid buying extended moves by waiting for a shallower retracement and rebound.

## 3. Box breakout / range breakout

Research references:

- FinLLM-B abstract on trading range breakout motivation:
  - https://arxiv.org/abs/2402.07536

Why it matters:

- Trading-range breakout methods are popular, but false breakouts are common.
- That means a usable implementation should not look only at price crossing a range high.

Implementation impact:

- `box_breakout` requires:
  - a tight box (`box_window_days`, `box_max_range_pct`)
  - moving-average trend alignment
  - breakout close above the box high
  - stronger-than-normal breakout volume

## Current profiles

### `high52_pullback`

- Best for strong stocks that already made a meaningful 52-week high breakout.
- Waits for a pullback and rebound trigger.

### `high52_breakout`

- Simpler continuation profile.
- Useful when the stock is still holding close to the breakout area without a deep pullback.

### `box_breakout`

- Looks for a tight daily consolidation box and a clean breakout.
- Can capture early-stage expansions even before a full 52-week-high pullback pattern develops.

## Suggested paper-trading workflow

1. Start with `high52_pullback`.
2. Compare it against `high52_breakout` on replay mode.
3. Add `box_breakout` only after checking false-breakout frequency on your preferred symbols.
4. Keep `PAPER_TRADING=true` and `AUTO_BUY_ENABLED=false` while comparing profiles.
