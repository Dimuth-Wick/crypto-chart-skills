---
name: chart-reader
description: Annotate a crypto chart screenshot with swing pivots (HH/HL/LH/LL), market structure, evidence-graded chart patterns and a risk-first trade plan or a NO TRADE stamp. Use when the user shares a candlestick chart image and asks what the chart shows, where to enter, exit or put a stop, or whether a setup is worth taking. Educational, not financial advice.
---

# Chart Reader

Turn a chart screenshot into an **annotated image** plus a **short text card**.
The image is the main answer. Keep text to a few lines.

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
Open the output image and check it: pivots sit on wicks, labels are readable,
plan levels are on the right side. Fix the spec and redraw if needed.
Deliver the annotated image to the user.

## Text card (keep it short)

```
📊 SYMBOL TF: UPTREND (HH + HL) · confidence: high
🔺 Pattern: Ascending triangle breakout: Evidence MODERATE
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
