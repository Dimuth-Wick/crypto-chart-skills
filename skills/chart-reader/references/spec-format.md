# `draw` spec format

`annotate.py draw chart.png spec.json --detect detect.json --calib Y1:P1,Y2:P2 -o out.png`

All pixel coordinates are in the original screenshot. With `--calib`, plan and
zone levels can be given as prices (plain numbers). Without it, plain numbers are
pixel rows; you can also write `{"y": 312}` or `{"price": 2150}` explicitly.

```json
{
  "title": "ETHUSDT 4h",
  "use_detected_pivots": true,
  "snap": true,
  "structure_line": true,
  "trend": "uptrend",
  "confidence": "high",
  "summary": [
    "HH at 2,154 + HL at 2,107",
    "Ascending triangle broke out on close"
  ],
  "patterns": [
    {
      "name": "Ascending triangle",
      "grade": "moderate",
      "status": "breakout up",
      "lines": [[620, 180, 1100, 180], [640, 420, 1100, 200]],
      "lines_in_price": false
    }
  ],
  "zones": [
    {"label": "Support (weak)", "from": 2100, "to": 2112, "kind": "support"}
  ],
  "plan": {
    "type": "long",
    "entry": 2160,
    "stop": 2098,
    "targets": [2250, 2310],
    "rr": "1:1.5 / 1:2.4"
  }
}
```

| Key | Notes |
|---|---|
| `use_detected_pivots` | Use pivots from `detect.json`. Or give `"pivots": [{"x":..,"y":..,"type":"high","label":"HH"}]` |
| `snap` | Default true: each pivot moves to the nearest detected candle's wick |
| `trend`, `confidence` | Default to the values in `detect.json` |
| `summary` | Up to 5 short lines, shown in the bottom band |
| `patterns[].grade` | `moderate`, `weak`, `unproven`, `no_edge` (from evidence-grades.md) |
| `patterns[].lines` | `[x1, y1, x2, y2]` per line. Set `lines_in_price: true` to give y values as prices |
| `zones[].kind` | `support` (green) or `resistance` (red) |
| `plan.type` | `long`, `short` or `no_trade` (then add `"reason"`) |

Layout: the plan gets its own panel on the right, the canvas grows if a level
is above or below the visible chart, and the summary plus disclaimer sit in a
band at the bottom, so nothing covers the candles.
