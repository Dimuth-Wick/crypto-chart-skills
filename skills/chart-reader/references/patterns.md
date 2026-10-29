# Pattern recognition rules

Draw only what is clearly there. Use the detected pivots as anchor points for
lines, so lines touch real wicks. "Confirmed" always means a candle has
**closed** beyond the level, not just wicked through it.

## Market structure (always first)
- Label every pivot: HH, HL, LH, LL.
- Uptrend = last high HH and last low HL. Downtrend = LH and LL. Otherwise range.
- **Break of structure (BOS)**: close above the last swing high (bullish) or below
  the last swing low (bearish). `detect` reports this as `structure_break`.

## The 3-touch rule (support and resistance lines)
A line pattern (channel/zigzag, range, triangle) is **valid only if price touched the
resistance line 3+ times AND the support line 3+ times**, and candle bodies did not close
through the lines in between (wicks may poke through). Use `annotate.py levels`.
- 3+ touches each, inside → valid, forming (`unproven`).
- 3+ touches each, candle **closed** outside → breakout (`moderate`).
- Fewer touches → "possible ..." only, not graded.
3 touches makes the pattern valid. It does not guarantee the breakout direction.

## Channels (zigzag)
- **Descending channel (bearish zigzag)**: both lines falling, roughly parallel.
- **Ascending channel (bullish zigzag)**: both lines rising.
- Breakout = candle close outside either line. A break against the channel's bias
  (e.g. up out of a descending channel) is a possible reversal; wait for structure to confirm.

## Range
- At least 3 touches of a similar high and 3 of a similar low (the 3-touch rule).
- Draw top and bottom lines. Breakout = close outside. Grade `moderate` only after the close.

## Triangles
Need at least 3 highs and 3 lows touching the lines (the 3-touch rule).
- **Ascending**: flat highs (EQH), rising lows (HL, HL).
- **Descending**: falling highs (LH, LH), flat lows (EQL).
- **Symmetrical**: falling highs (LH) and rising lows (HL).
Draw both lines through the pivots. Before the breakout: `unproven`, status `forming`.
After a close outside: `moderate`, status `breakout up` or `breakout down`.
A common target method: triangle height added to the breakout point. Present it as a
rough guide, not a forecast.

## Head & shoulders (and inverse)
- Three highs: middle highest (head), two lower and roughly equal (shoulders).
- Neckline through the two lows between them.
- Confirmed only on a close below the neckline (above for inverse). Grade `weak`.

## Double top / bottom
- Two highs (or lows) within ~0.5–1% with a clear pullback between.
- Confirmed on a close beyond the pullback low/high. Grade `weak`.

## Flags, pennants, wedges
- Flag: strong move ("pole") then a small channel against it. Wedge: both lines sloping the same way, converging.
- Grade `unproven`. Mention, draw lightly, do not base a plan on them alone.

## Support / resistance
- Zones, not lines: always a band with width, never a single line. Sloped lines from
  `levels` get a band too. A break means a candle **closes beyond the outer edge** of the zone.
- Grade `weak`. Use them mainly for stop placement and targets.

## Candlesticks
- Grade `no_edge`. Never draw them as patterns. At most a short note in the text
  ("a hammer printed at support, which is weak confirmation at best").
