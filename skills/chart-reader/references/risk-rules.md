# Risk rules: plan or NO TRADE

The research is clear that risk control matters more than pattern choice, and
that even frontier AI models lose money when they trade on their own. So the
default answer is cautious.

## Say NO TRADE when any of these is true
- Structure is a range/mixed and there is no confirmed breakout.
- The setup is against the structure without a confirmed break of structure.
- No clear invalidation point (nowhere logical for the stop).
- First target gives R:R below 1.5 after fees.
- Price is in the middle of a range, far from any level.
- Detection confidence is low and the chart is unclear.
- The latest move happened in the last few candles that are not yet confirmed.

## If there is a plan
- **Long**: in an uptrend (HH + HL), or after a bullish break of structure.
  Entry on a close above the last HH (breakout) or near the last HL (pullback).
  Stop below the last HL. Never move the stop further away.
- **Short**: mirror image (LH + LL, stop above the last LH).
- **Targets**: the next structure levels (previous swing, range height, zone).
  Give 1–2 targets. R:R = distance to target ÷ distance to stop, after fees.
- **Size**: risk a fixed % of the account per trade (1% is a common default,
  2% an upper bound). Use `annotate.py size`. Position size = risk ÷ stop distance.
- **Leverage**: always warn. On 10 Oct 2025 over $19B of leveraged positions
  were liquidated in about a day, and exchanges auto-deleveraged even winning traders.

## Wording
- "If price closes above 2,160, a long could target 2,250 with a stop at 2,098."
- Never: "will go up", "sure", "guaranteed", "easy money", win-rate numbers.
- End with: "Educational only. Not financial advice."
