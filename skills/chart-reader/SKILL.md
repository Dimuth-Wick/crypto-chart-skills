---
name: chart-reader
description: Annotate a crypto chart screenshot as two images - a structure chart (swing pivots HH/HL/LH/LL, evidence-graded patterns, risk-first trade plan or NO TRADE) and a levels chart (support/resistance lines with counted touches, pattern name and exact breakout prices). Use when the user shares a candlestick chart image and asks what the chart shows, where to enter, exit or put a stop, or whether a setup is worth taking. Educational, not financial advice.
---

# Chart Reader

Turn a chart screenshot into **two annotated images** plus a **short text card**:

1. **Structure chart** (`draw`): pivots HH/HL/LH/LL, structure line, graded patterns, plan or NO TRADE.
2. **Levels chart** (`draw-levels`): support and resistance lines with numbered touches,
   the pattern name and bias (zigzag/channel, triangle, range, double bottom/top), whether it
   is VALID, and the exact price where it breaks up or down.

The images are the main answer. Keep text to a few lines.
Labels are placed in empty areas with an arrow to the pattern, so they never cover it.

Everything in this skill follows the research in `docs/research.md` of the repo:
market structure has the best evidence, classic shapes are weak, candlestick
patterns mostly have no edge, and risk management matters more than any pattern.

## What you need

- Python 3 with `Pillow` and `numpy` (`pip install pillow numpy` if missing).
- The script `scripts/annotate.py` (paths below are relative to this skill folder).
- References, read when needed:
  - `references/evidence-grades.md`: the grade for every pattern. **Never grade higher than this file.**
  - `references/patterns.md`: how to recognise each pattern and when it counts as confirmed.
  - `references/risk-rules.md`: when to trade, when to say NO TRADE, sizing.
  - `references/spec-format.md`: the JSON the `draw` command accepts.

**Recommended timeframes:** 4h and higher. 1h sometimes. Below 1h, say patterns are
unreliable there (author's experience; noise, fees and fast bots dominate).

## Workflow

### 1. Check the screenshot
Look at the image. Note symbol, timeframe and exchange if visible; ask only if
the timeframe is missing and it matters. Good input is a candlestick chart with
coloured candles and no indicators or drawings on the price pane.
If the chart has line/area style, heavy indicators, or is very blurry, say so
and ask for a cleaner screenshot (you can still give a rough read).

### 2. Find the price pane and calibrate
- **Region**: pixel box of the candles only, excluding the price axis on the
  right, the header, the time axis and any volume or indicator panes:
  `x0,y0,x1,y1`. Estimate it from the image; a little margin is fine.
- **Calibration** (recommended): pick two price labels on the right axis, far
  apart, and estimate the pixel row of each: `y1:price1,y2:price2`.
  **Check the axis scale.** If equal price steps take different pixel heights
  (e.g. $40 is ~48 px at the top but ~57 px at the bottom), the axis is
  logarithmic (TradingView often is). Then add `--log` to both `detect` and `draw`.
  Verify by converting a third axis label with the calibration; it should match within ~0.2%.

### 3. Detect candles and pivots
```bash
python scripts/annotate.py detect chart.png --region X0,Y0,X1,Y1 --calib Y1:P1,Y2:P2 [--log] > detect.json
```
Read the result and check it against what you see:
- Compare the last candle's `high`/`low` with the OHLC shown in the chart header, if visible. They should match closely.
- `candle_count` should be close to the number of visible candles. If not,
  adjust `--region`, or `--sat-min` for pale candles.
- `warnings` and `pivot_confidence`: report low confidence honestly.
- `pivots` with labels `HH`, `HL`, `LH`, `LL` (`H`/`L` = first swing, `EQH`/`EQL` = equal).
- `trend` and `trend_reason`; `structure_break` (latest close beyond the last swing).
- The last `unconfirmed_last_candles` candles cannot be confirmed pivots yet. Say so if
  the most important move is in those candles.
Use `--left/--right 2` for short charts, `5` for long noisy ones.

### 4. Read the structure
- **Uptrend**: HH + HL. **Downtrend**: LH + LL. **Range**: anything else.
- A **break of structure** (close beyond the last swing high or low) is the main
  signal. A break against the trend is a warning, not an automatic reversal.

### 5. Name a pattern only if it is clearly there
Use `references/patterns.md`. Most charts have **no clean pattern**; say "no clear pattern".
Copy the grade from `references/evidence-grades.md` and show it on the chart.
Rules that are easy to get wrong:
- Triangle / range **breakout** after a close outside = `moderate`.
  A triangle that has **not** broken out = `unproven`.
- Support/resistance = `weak`. Candlestick patterns = `no_edge`, mention them only as context.

### 5b. Support/resistance and the 3-touch rule
```bash
python scripts/annotate.py levels detect.json > levels.json
```
It fits the best resistance line through swing highs and support line through swing lows
(lines whose candle **bodies** never close through them), counts the touches, names the
pattern from the two slopes and reports the breakout prices at the latest candle.
- **Valid pattern = 3+ touches on EACH line** (`--min-touches 3`, the default). Fewer touches:
  call it "possible ...", do not grade it, do not base a plan on it.
- Valid and still inside = `unproven` (forming). Valid and a candle has **closed** outside = `moderate`.
- Breakout prices: `breakout_up_price` / `breakdown_price`. Always say "on a candle CLOSE".
- `double` reports a double bottom/top with its neckline (`weak`). `tentative` points are in the
  last few candles and are not confirmed yet.
- Lines broken long ago (`--max-age`, default 10 candles) or not touched recently
  (`--max-stale`, default 40) are ignored, so the result describes the **current** pattern.
Check the lines against the image. If they look wrong, say so and rely on structure.
Never say a pattern "guarantees" a breakout; 3 touches makes a pattern valid, not certain.

### 6. Decide: plan or NO TRADE
Follow `references/risk-rules.md`. Short version:
- Trade direction must agree with structure (or with a confirmed break).
- Stop goes beyond the swing that would prove the idea wrong.
- First target must give **R:R ≥ 1.5 after fees**, otherwise NO TRADE.
- If anything is unclear, NO TRADE is the correct answer.
If the user gave an account size and risk %, run:
```bash
python scripts/annotate.py size --account 1000 --risk-pct 1 --entry E --stop S --targets T1 T2
```
Otherwise show the plan with R:R only and mention 1% risk per trade as a common default.

### 7. Draw and check
Write `spec.json` (see `references/spec-format.md`), then:
```bash
python scripts/annotate.py draw chart.png spec.json --detect detect.json --calib Y1:P1,Y2:P2 [--log] -o chart_annotated.png
```
Then the levels chart:
```bash
python scripts/annotate.py draw-levels chart.png levels.json --detect detect.json --spec levels_spec.json -o chart_levels.png
```
(`levels_spec.json` is optional: `{"title": "...", "summary": ["extra line"]}`.)

Open both images and check them: pivots sit on wicks, lines touch the numbered points,
labels are readable and do not cover the pattern. Fix and redraw if needed.
Deliver **both** images to the user.

## Text card (keep it short)

```
📊 SYMBOL TF: UPTREND (HH + HL) · confidence: high
🔺 Pattern: Ascending triangle breakout (R 3 / S 3 touches, VALID): Evidence MODERATE
📏 Break UP above 2,160 · Break DOWN below 2,090 (on a candle close)
🎯 Plan: LONG above 2,160 · Stop 2,098 · T1 2,250 (R:R 1.5) · T2 2,310 (2.4)
⚠️ Risk 1% max. Leverage can liquidate you.
Educational only. Not financial advice.
```
Or for no setup:
```
📊 SYMBOL TF: RANGE · ⛔ NO TRADE: structure unclear, wait for a close outside the range.
```

## Hard rules

- Never promise or imply returns, win rates or "guaranteed" setups. Use "could", not "will".
- Never grade a pattern above `references/evidence-grades.md`.
- Never call a pattern confirmed before the candle **closes** beyond the level.
- Always include invalidation (stop) and the disclaimer. Warn about leverage.
- Do not place trades or connect to exchanges. This skill only reads charts.
- If the user seems to risk money they cannot afford to lose, say so plainly.
