#!/usr/bin/env python3
"""
annotate.py - chart-reader helper for crypto chart screenshots.

Commands:

  detect  Find candles in a screenshot by colour, then find swing pivots
          and label them HH / HL / LH / LL. Prints JSON.
  draw    Chart 1: pivots, structure, patterns, zones and a trade plan
          (or a NO TRADE stamp) on the screenshot from a JSON spec.
  levels  Support/resistance lines, touch counts (3+ each = valid),
          pattern name, bias and exact breakout prices. Prints JSON.
  draw-levels  Chart 2: the levels, numbered touches, breakout prices.
  size    Position sizing and risk/reward from entry, stop and targets.

Educational tool only. Not financial advice.

Examples
  python annotate.py detect chart.png --region 0,60,1180,640 --calib 120:2400,560:2200 > detect.json
  python annotate.py draw chart.png spec.json --detect detect.json -o chart_annotated.png
  python annotate.py levels detect.json > levels.json
  python annotate.py draw-levels chart.png levels.json --detect detect.json -o chart_levels.png
  python annotate.py size --account 1000 --risk-pct 1 --entry 2350 --stop 2290 --targets 2470 2560
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------

GRADE_COLOURS = {
    "strong": (34, 197, 94),
    "moderate": (34, 197, 94),
    "weak": (234, 179, 8),
    "unproven": (148, 163, 184),
    "no_edge": (239, 68, 68),
    "none": (239, 68, 68),
}

GRADE_TEXT = {
    "strong": "STRONG",
    "moderate": "MODERATE",
    "weak": "WEAK",
    "unproven": "UNPROVEN",
    "no_edge": "NO EDGE",
    "none": "NO EDGE",
}


def parse_region(text, width, height):
    """'x0,y0,x1,y1' -> clipped tuple. None -> whole image."""
    if not text:
        return (0, 0, width, height)
    parts = [int(float(p)) for p in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("--region must be x0,y0,x1,y1")
    x0, y0, x1, y1 = parts
    x0, x1 = max(0, min(x0, x1)), min(width, max(x0, x1))
    y0, y1 = max(0, min(y0, y1)), min(height, max(y0, y1))
    if x1 - x0 < 20 or y1 - y0 < 20:
        raise SystemExit("--region is too small")
    return (x0, y0, x1, y1)


def parse_calib(text):
    """'y1:price1,y2:price2' -> (y1, p1, y2, p2) or None."""
    if not text:
        return None
    try:
        a, b = text.split(",")
        y1, p1 = (float(v) for v in a.split(":"))
        y2, p2 = (float(v) for v in b.split(":"))
    except ValueError:
        raise SystemExit("--calib must look like 120:2400,560:2200 (pixelY:price)")
    if y1 == y2 or p1 == p2:
        raise SystemExit("--calib needs two different pixel rows and two different prices")
    return (y1, p1, y2, p2)


LOG_SCALE = False  # set by --log: price axis is logarithmic


def _fwd(p):
    return math.log(p) if LOG_SCALE else p


def _inv(v):
    return math.exp(v) if LOG_SCALE else v


def y_to_price(y, calib):
    if calib is None:
        return None
    y1, p1, y2, p2 = calib
    a, b = _fwd(p1), _fwd(p2)
    return _inv(a + (y - y1) * (b - a) / (y2 - y1))


def price_to_y(price, calib):
    y1, p1, y2, p2 = calib
    a, b = _fwd(p1), _fwd(p2)
    return y1 + (_fwd(price) - a) * (y2 - y1) / (b - a)


def fmt_price(p):
    if p is None:
        return ""
    a = abs(p)
    if a >= 1000:
        return f"{p:,.0f}" if a >= 10000 else f"{p:,.1f}"
    if a >= 1:
        return f"{p:,.2f}"
    if a >= 0.01:
        return f"{p:.4f}"
    return f"{p:.8f}".rstrip("0")


# ----------------------------------------------------------------------------
# detect
# ----------------------------------------------------------------------------

def candle_mask(rgb, sat_min, val_min):
    """Pixels that look like candle colour (saturated), plus a green/red map."""
    arr = rgb.astype(np.float32)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    val = mx / 255.0
    mask = (sat >= sat_min) & (val >= val_min)
    r, g = arr[:, :, 0], arr[:, :, 1]
    green = mask & (g > r)
    red = mask & (r >= g)
    return mask, green, red


def runs(bool_1d):
    """Start/end (inclusive) of consecutive True runs."""
    out = []
    start = None
    for i, v in enumerate(bool_1d):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(bool_1d) - 1))
    return out


def extract_candles(rgb, sat_min=0.25, val_min=0.25):
    """Return list of candles (pixel coords relative to rgb) and warnings."""
    mask, green, red = candle_mask(rgb, sat_min, val_min)
    warnings = []
    col_runs = runs(mask.any(axis=0))
    raw = []
    for c0, c1 in col_runs:
        sub = mask[:, c0:c1 + 1]
        row_runs = runs(sub.any(axis=1))
        # keep vertical runs of at least 2 px; take the topmost one
        # (volume bars sit below the price pane)
        row_runs = [r for r in row_runs if r[1] - r[0] >= 1]
        if not row_runs:
            continue
        top, bot = row_runs[0]
        block = sub[top:bot + 1]
        counts = block.sum(axis=1)
        body_rows = np.where(counts >= max(1, 0.6 * counts.max()))[0]
        g = green[top:bot + 1, c0:c1 + 1].sum()
        rd = red[top:bot + 1, c0:c1 + 1].sum()
        raw.append({
            "x": (c0 + c1) / 2.0,
            "x0": c0,
            "x1": c1,
            "width": c1 - c0 + 1,
            "high_y": float(top),
            "low_y": float(bot),
            "body_top_y": float(top + body_rows.min()),
            "body_bottom_y": float(top + body_rows.max()),
            "colour": "green" if g >= rd else "red",
        })

    if not raw:
        return [], ["No candle-coloured pixels found. Is this a candlestick chart with coloured candles?"]

    widths = np.array([c["width"] for c in raw])
    med = float(np.median(widths))
    candles = [c for c in raw if c["width"] <= max(3 * med, med + 4)]
    dropped = len(raw) - len(candles)
    if dropped:
        warnings.append(f"Ignored {dropped} wide coloured block(s) (price labels or overlapping objects).")
    if med > 0 and widths.max() > 6 * med and dropped == 0:
        warnings.append("Some candles look merged. Indicators or drawings may be on the chart.")
    return candles, warnings


def find_pivots(candles, left=3, right=3):
    """Fractal swing highs/lows on pixel y (smaller y = higher price)."""
    n = len(candles)
    hi = [c["high_y"] for c in candles]
    lo = [c["low_y"] for c in candles]
    piv = []
    for i in range(left, n - right):
        if all(hi[i] < hi[j] for j in range(i - left, i)) and all(hi[i] <= hi[j] for j in range(i + 1, i + right + 1)):
            piv.append({"index": i, "type": "high", "y": hi[i]})
        if all(lo[i] > lo[j] for j in range(i - left, i)) and all(lo[i] >= lo[j] for j in range(i + 1, i + right + 1)):
            piv.append({"index": i, "type": "low", "y": lo[i]})
    piv.sort(key=lambda p: (p["index"], 0 if p["type"] == "high" else 1))

    # enforce alternation high/low, keeping the more extreme point
    alt = []
    for p in piv:
        if alt and alt[-1]["type"] == p["type"]:
            prev = alt[-1]
            more_extreme = p["y"] < prev["y"] if p["type"] == "high" else p["y"] > prev["y"]
            if more_extreme:
                alt[-1] = p
        else:
            alt.append(p)
    return alt


def label_pivots(pivots, tol_px):
    last = {"high": None, "low": None}
    for p in pivots:
        prev = last[p["type"]]
        if prev is None:
            p["label"] = "H" if p["type"] == "high" else "L"
        elif p["type"] == "high":
            if p["y"] < prev["y"] - tol_px:
                p["label"] = "HH"
            elif p["y"] > prev["y"] + tol_px:
                p["label"] = "LH"
            else:
                p["label"] = "EQH"
        else:
            if p["y"] < prev["y"] - tol_px:
                p["label"] = "HL"
            elif p["y"] > prev["y"] + tol_px:
                p["label"] = "LL"
            else:
                p["label"] = "EQL"
        last[p["type"]] = p
    return pivots


def trend_from_pivots(pivots):
    highs = [p["label"] for p in pivots if p["type"] == "high"]
    lows = [p["label"] for p in pivots if p["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "unclear", "Not enough swings to judge structure."
    h, l = highs[-1], lows[-1]
    if h == "HH" and l == "HL":
        return "uptrend", "Last high is a HH and last low is a HL."
    if h == "LH" and l == "LL":
        return "downtrend", "Last high is a LH and last low is a LL."
    if h == "LH" and l == "HL":
        return "range", "Lower high and higher low: price is compressing (possible triangle)."
    if h == "HH" and l == "LL":
        return "range", "Higher high and lower low: expanding, volatile range."
    return "range", f"Mixed structure (last high {h}, last low {l})."


def cmd_detect(args):
    img = Image.open(args.image).convert("RGB")
    W, H = img.size
    region = parse_region(args.region, W, H)
    calib = parse_calib(args.calib)
    x0, y0, x1, y1 = region
    rgb = np.asarray(img)[y0:y1, x0:x1]

    candles, warnings = extract_candles(rgb, args.sat_min, args.val_min)
    for c in candles:  # back to full-image coordinates
        for k in ("x", "x0", "x1"):
            c[k] = round(c[k] + x0, 1)
        for k in ("high_y", "low_y", "body_top_y", "body_bottom_y"):
            c[k] = round(c[k] + y0, 1)
        if calib:
            c["high"] = y_to_price(c["high_y"], calib)
            c["low"] = y_to_price(c["low_y"], calib)

    if len(candles) < 15:
        warnings.append(f"Only {len(candles)} candles found. Zoom out or crop to the price pane with --region.")
    if len(candles) > 400:
        warnings.append(f"{len(candles)} candles found. Very dense charts make pivots less reliable; zoom in.")

    pivots = find_pivots(candles, args.left, args.right) if candles else []
    tol = max(1.0, 0.002 * (y1 - y0))
    label_pivots(pivots, tol)
    for p in pivots:
        c = candles[p["index"]]
        p["x"] = c["x"]
        if calib:
            p["price"] = y_to_price(p["y"], calib)
    trend, reason = trend_from_pivots(pivots)

    # Break of structure: has the latest candle closed beyond the last swing?
    # (The last `right` candles can never be confirmed pivots yet.)
    structure_break = None
    if candles and pivots:
        last = candles[-1]
        close_y = last["body_top_y"] if last["colour"] == "green" else last["body_bottom_y"]
        last_hi = next((p for p in reversed(pivots) if p["type"] == "high"), None)
        last_lo = next((p for p in reversed(pivots) if p["type"] == "low"), None)
        if last_hi and close_y < last_hi["y"] - tol:
            structure_break = {"direction": "up", "level_label": last_hi["label"], "level_y": last_hi["y"],
                               "note": f"Latest candle closed above the last swing high ({last_hi['label']})."}
        elif last_lo and close_y > last_lo["y"] + tol:
            structure_break = {"direction": "down", "level_label": last_lo["label"], "level_y": last_lo["y"],
                               "note": f"Latest candle closed below the last swing low ({last_lo['label']})."}
        if structure_break and calib:
            structure_break["level_price"] = y_to_price(structure_break["level_y"], calib)
            structure_break["close_price"] = y_to_price(close_y, calib)

    if not candles or len(pivots) < 4:
        confidence = "low"
    elif warnings:
        confidence = "medium"
    else:
        confidence = "high"

    out = {
        "image": os.path.basename(args.image),
        "image_size": [W, H],
        "region": list(region),
        "calibrated": calib is not None,
        "calib": args.calib,
        "log": LOG_SCALE,
        "candle_count": len(candles),
        "median_candle_width": float(np.median([c["width"] for c in candles])) if candles else None,
        "pivot_settings": {"left": args.left, "right": args.right},
        "trend": trend,
        "trend_reason": reason,
        "structure_break": structure_break,
        "unconfirmed_last_candles": args.right,
        "pivot_confidence": confidence,
        "warnings": warnings,
        "pivots": pivots,
        "candles": candles,
    }
    json.dump(out, sys.stdout, indent=1, default=float)
    sys.stdout.write("\n")


# ----------------------------------------------------------------------------
# draw
# ----------------------------------------------------------------------------

def load_font(size, bold=False):
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"] if bold else []) + [
        "DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttc"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def text_size(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


def label_box(draw, xy, text, font, fg, bg, pad=4, anchor="lt"):
    """Text with a filled box. anchor: l/c/r + t/m/b."""
    w, h = text_size(draw, text, font)
    x, y = xy
    if anchor[0] == "c":
        x -= w / 2 + pad
    elif anchor[0] == "r":
        x -= w + 2 * pad
    if anchor[1] == "m":
        y -= h / 2 + pad
    elif anchor[1] == "b":
        y -= h + 2 * pad
    cw, ch = draw.im.size  # keep the box inside the image
    x = min(max(0, x), cw - w - 2 * pad)
    y = min(max(0, y), ch - h - 2 * pad)
    draw.rounded_rectangle([x, y, x + w + 2 * pad, y + h + 2 * pad], radius=pad, fill=bg)
    draw.text((x + pad, y + pad - 1), text, font=font, fill=fg)
    return (x, y, x + w + 2 * pad, y + h + 2 * pad)


def dashed_line(draw, p1, p2, fill, width, dash=10, gap=6):
    (xa, ya), (xb, yb) = p1, p2
    length = math.hypot(xb - xa, yb - ya)
    if length == 0:
        return
    dx, dy = (xb - xa) / length, (yb - ya) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        draw.line([(xa + dx * pos, ya + dy * pos), (xa + dx * end, ya + dy * end)], fill=fill, width=width)
        pos = end + gap


def resolve_y(value, calib):
    """A level can be {'y': px}, {'price': p} or a bare number (price if calibrated, else px)."""
    if isinstance(value, dict):
        if "y" in value:
            return float(value["y"]), value.get("price")
        if "price" in value:
            if calib is None:
                raise SystemExit("A level uses 'price' but no --calib was given.")
            return price_to_y(float(value["price"]), calib), float(value["price"])
    v = float(value)
    if calib is not None:
        return price_to_y(v, calib), v
    return v, None


def snap_pivot(p, candles):
    """Move a pivot to the nearest detected candle's wick."""
    if not candles:
        return p
    c = min(candles, key=lambda c: abs(c["x"] - float(p["x"])))
    p = dict(p)
    p["x"] = c["x"]
    p["y"] = c["high_y"] if p.get("type", "high") == "high" else c["low_y"]
    return p


class Occupancy:
    """Where candles, lines and labels already are, so callouts go to empty space."""

    def __init__(self, size):
        self.img = Image.new("L", size, 0)
        self.d = ImageDraw.Draw(self.img)
        self._ii = None

    def add_mask(self, mask, x, y):
        m = Image.fromarray(mask.astype("uint8") * 255).filter(ImageFilter.MaxFilter(9))
        self.img.paste(255, (int(x), int(y)), m)
        self._ii = None

    def box(self, b, grow=4):
        self.d.rectangle([b[0] - grow, b[1] - grow, b[2] + grow, b[3] + grow], fill=255)
        self._ii = None

    def line(self, pts, width):
        self.d.line([tuple(p) for p in pts], fill=255, width=max(1, int(width)))
        self._ii = None

    def cost(self, b):
        if self._ii is None:
            arr = (np.asarray(self.img) > 0).astype(np.int64)
            self._ii = np.pad(arr.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        h, w = self._ii.shape[0] - 1, self._ii.shape[1] - 1
        x0, y0 = max(0, int(b[0])), max(0, int(b[1]))
        x1, y1 = min(w, int(b[2])), min(h, int(b[3]))
        if x1 <= x0 or y1 <= y0:
            return 1e12
        ii = self._ii
        return int(ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0])


def draw_arrow(d, p_from, p_to, col, width, head):
    d.line([p_from, p_to], fill=col, width=width)
    ang = math.atan2(p_to[1] - p_from[1], p_to[0] - p_from[0])
    pts = [p_to]
    for da in (150, -150):
        a = ang + math.radians(da)
        pts.append((p_to[0] + head * math.cos(a), p_to[1] + head * math.sin(a)))
    d.polygon(pts, fill=col)


def callout(d, occ, anchor, rows, bounds, s, accent):
    """A label box placed in the emptiest nearby spot, with an arrow to `anchor`.

    rows: list of (text, font, rgba). bounds: (x0, y0, x1, y1) the box must stay in.
    """
    pad, gap = 8 * s, 4 * s
    sizes = [text_size(d, t, f) for t, f, _ in rows]
    w = max(sz[0] for sz in sizes) + 2 * pad + 6 * s
    h = sum(sz[1] for sz in sizes) + gap * (len(rows) - 1) + 2 * pad
    ax, ay = anchor
    bx0, by0, bx1, by1 = bounds
    best = None
    for r in (70, 110, 160, 220, 290, 370, 460):
        for k in range(24):
            ang = 2 * math.pi * k / 24
            cx, cy = ax + r * s * math.cos(ang), ay + r * s * math.sin(ang)
            b = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            if b[0] < bx0 or b[1] < by0 or b[2] > bx1 or b[3] > by1:
                continue
            c = occ.cost(b) + r * s * 4  # covering things costs far more than distance
            if best is None or c < best[0]:
                best = (c, b)
    if best is None:
        x = min(max(bx0, ax - w / 2), bx1 - w)
        y = min(max(by0, ay - h - 60 * s), by1 - h)
        b = (x, y, x + w, y + h)
    else:
        b = best[1]
    # arrow from the box edge nearest the anchor
    ex, ey = min(max(ax, b[0]), b[2]), min(max(ay, b[1]), b[3])
    dist = math.hypot(ax - ex, ay - ey)
    if dist > 12 * s:
        k = (dist - 7 * s) / dist
        tip = (ex + (ax - ex) * k, ey + (ay - ey) * k)
        draw_arrow(d, (ex, ey), tip, accent + (255,), max(2, int(2 * s)), 10 * s)
        occ.line([(ex, ey), tip], 6 * s)
    d.rounded_rectangle(b, radius=7 * s, fill=(15, 23, 42, 238), outline=accent + (255,), width=max(1, int(2 * s)))
    d.rectangle([b[0] + 2 * s, b[1] + 6 * s, b[0] + 6 * s, b[3] - 6 * s], fill=accent + (255,))
    y = b[1] + pad
    for (t, f, c), sz in zip(rows, sizes):
        d.text((b[0] + pad + 6 * s, y - 2 * s), t, font=f, fill=c)
        y += sz[1] + gap
    occ.box(b)
    return b


def pane_occupancy(src, canvas_size, region, top_offset):
    """Occupancy map pre-filled with the candles of the price pane."""
    occ = Occupancy(canvas_size)
    rx0, ry0, rx1, ry1 = (int(v) for v in region)
    rgb = np.asarray(src.convert("RGB"))[ry0:ry1, rx0:rx1]
    mask, _, _ = candle_mask(rgb, 0.25, 0.25)
    occ.add_mask(mask, rx0, ry0 + top_offset)
    return occ


def calib_from(args, spec, det):
    """Calibration and log flag: command line first, then spec, then detect.json."""
    global LOG_SCALE
    if det and det.get("log"):
        LOG_SCALE = True
    text = getattr(args, "calib", None) or (spec or {}).get("calib") or (det or {}).get("calib")
    return parse_calib(text)


def cmd_draw(args):
    spec = json.load(open(args.spec, encoding="utf-8"))
    src = Image.open(args.image).convert("RGBA")
    W, H = src.size
    s = max(1.0, W / 1100.0)  # scale for line widths and fonts

    det = json.load(open(args.detect, encoding="utf-8")) if args.detect else None
    candles = det["candles"] if det else []
    calib = calib_from(args, spec, det)

    f_small = load_font(int(12 * s))
    f_mid = load_font(int(14 * s), bold=True)
    f_big = load_font(int(30 * s), bold=True)

    region = spec.get("region") or (det["region"] if det else [0, 0, W, H])
    rx0, ry0, rx1, ry1 = region

    # ---------------- layout: side panel for the plan, padding for far levels,
    # bottom band for the summary. Nothing is drawn over the candles except
    # pivots, structure and pattern lines.
    plan = spec.get("plan") or {}
    has_plan = plan.get("type") in ("long", "short")
    level_ys = []
    if has_plan:
        for v in [plan["entry"], plan["stop"]] + list(plan.get("targets", [])):
            level_ys.append(resolve_y(v, calib)[0])
    pad_top = int(max(0, 30 * s - min(level_ys))) if level_ys else 0
    pad_bot_lv = int(max(0, max(level_ys) - (H - 30 * s))) if level_ys else 0
    panel_w = int(0.28 * W) if has_plan else 0

    lines = []
    if spec.get("title"):
        lines.append(("title", spec["title"]))
    trend = spec.get("trend") or (det["trend"] if det else None)
    if trend:
        lines.append(("text", f"Structure: {trend.upper()}"))
    for ln in spec.get("summary", [])[:5]:
        lines.append(("text", ln))
    conf = spec.get("confidence") or (det["pivot_confidence"] if det else None)
    if conf:
        lines.append(("dim", f"Confidence: {conf}"))
    lh = int(19 * s)
    band_h = int(max(lh * max(1, len(lines)), 110 * s) + 2 * lh + 16 * s)

    bg = src.getpixel((min(W - 1, 2), min(H - 1, 2)))
    canvas = Image.new("RGBA", (W + panel_w, H + pad_top + pad_bot_lv + band_h), (15, 23, 42, 255))
    canvas.paste(Image.new("RGBA", (W + panel_w, H + pad_top + pad_bot_lv), bg), (0, 0))
    canvas.paste(src, (0, pad_top))
    CW, CH = canvas.size

    def Y(y):
        return float(y) + pad_top

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    occ = pane_occupancy(src, canvas.size, region, pad_top)
    pane_bounds = (rx0 + 4 * s, Y(ry0) + 4 * s, rx1 - 4 * s, Y(ry1) - 4 * s)

    # ---------------- zones
    for z in spec.get("zones", []):
        ya, _ = resolve_y(z["from"], calib)
        yb, _ = resolve_y(z["to"], calib)
        kind = z.get("kind", "support")
        col = (34, 197, 94) if kind == "support" else (239, 68, 68)
        top, bot = Y(min(ya, yb)), Y(max(ya, yb))
        d.rectangle([rx0, top, rx1, bot], fill=col + (40,), outline=col + (120,))
        occ.box(label_box(d, (rx0 + 8 * s, top - 2 * s), z.get("label", kind.title()),
                          f_small, (255, 255, 255, 240), col + (190,), anchor="lb"))

    # ---------------- pivots + structure
    pivots = spec.get("pivots")
    if pivots is None or spec.get("use_detected_pivots"):
        pivots = det["pivots"] if det else []
    if spec.get("snap", True) and candles:
        pivots = [snap_pivot(p, candles) for p in pivots]
    pivots = sorted(pivots, key=lambda p: float(p["x"]))

    if spec.get("structure_line", True) and len(pivots) >= 2:
        pts = [(float(p["x"]), Y(p["y"])) for p in pivots]
        d.line(pts, fill=(147, 197, 253, 210), width=max(2, int(2 * s)), joint="curve")
        occ.line(pts, 4 * s)

    r = 5 * s
    for p in pivots:
        x, y = float(p["x"]), Y(p["y"])
        lab = p.get("label", "")
        is_high = p.get("type", "high") == "high"
        col = (34, 197, 94) if lab in ("HH", "HL") else (239, 68, 68) if lab in ("LH", "LL") else (203, 213, 225)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (255,), outline=(255, 255, 255, 255), width=max(1, int(s)))
        occ.box((x - r, y - r, x + r, y + r))
        if lab:
            anchor = "cb" if is_high else "ct"
            yy = y - r - 3 * s if is_high else y + r + 3 * s
            occ.box(label_box(d, (x, yy), lab, f_mid, (255, 255, 255, 255), col + (235,), anchor=anchor))

    # ---------------- patterns: lines on the chart, name in an empty spot with an arrow
    pending = []
    for pat in spec.get("patterns", []):
        grade = str(pat.get("grade", "unproven")).lower().replace(" ", "_")
        col = GRADE_COLOURS.get(grade, GRADE_COLOURS["unproven"])
        segs = []
        for ln in pat.get("lines", []):
            xa, ya, xb, yb = (float(v) for v in ln)
            if calib is not None and pat.get("lines_in_price"):
                ya, yb = price_to_y(ya, calib), price_to_y(yb, calib)
            segs.append((xa, Y(ya), xb, Y(yb)))
            dashed_line(d, (xa, Y(ya)), (xb, Y(yb)), col + (240,), max(2, int(3 * s)))
            occ.line([(xa, Y(ya)), (xb, Y(yb))], 6 * s)
        if segs:
            xa, ya, xb, yb = segs[0]
            anchor_pt = ((xa + xb) / 2, (ya + yb) / 2)
        else:
            anchor_pt = (rx0 + (rx1 - rx0) * 0.5, Y(ry0 + 40 * s))
        rows = [(pat.get("name", "Pattern"), f_mid, (255, 255, 255, 255))]
        if pat.get("status"):
            rows.append((pat["status"], f_small, (203, 213, 225, 255)))
        rows.append((f"Evidence: {GRADE_TEXT.get(grade, grade.upper())}", f_small, col + (255,)))
        pending.append((anchor_pt, rows, col))
    for anchor_pt, rows, col in pending:  # after all lines, so callouts avoid every line
        callout(d, occ, anchor_pt, rows, pane_bounds, s, col)

    # ---------------- double bottom / top from levels.json, drawn as a visible W / M
    lv = json.load(open(args.levels, encoding="utf-8")) if getattr(args, "levels", None) else None
    if lv and lv.get("double") and candles:
        draw_double(overlay, d, occ, src, lv["double"], candles, region, s, Y, calib,
                    (f_small, f_mid, load_font(int(11 * s), bold=True)), in_pane_labels=True)

    # ---------------- plan
    if has_plan:
        start_x = float(pivots[-1]["x"]) if pivots else rx0 + (rx1 - rx0) * 0.6
        right = CW - 6 * s
        entry_y, _ = resolve_y(plan["entry"], calib)
        stop_y, _ = resolve_y(plan["stop"], calib)
        tgt = [resolve_y(t, calib)[0] for t in plan.get("targets", [])]
        # panel background so labels never sit on candles
        d.rectangle([W, 0, CW, H + pad_top + pad_bot_lv], fill=(15, 23, 42, 120))
        if tgt:
            far = min(tgt) if plan["type"] == "long" else max(tgt)
            d.rectangle([start_x, Y(min(entry_y, far)), CW, Y(max(entry_y, far))], fill=(34, 197, 94, 32))
        d.rectangle([start_x, Y(min(entry_y, stop_y)), CW, Y(max(entry_y, stop_y))], fill=(239, 68, 68, 38))
        levels = [("Entry", plan["entry"], (59, 130, 246)), ("Stop", plan["stop"], (239, 68, 68))]
        for i, t in enumerate(plan.get("targets", []), 1):
            levels.append((f"Target {i}", t, (34, 197, 94)))
        for name, val, col in levels:
            y, p = resolve_y(val, calib)
            y = Y(y)
            d.line([(start_x, y), (CW, y)], fill=col + (240,), width=max(2, int(2 * s)))
            txt = name + (f"  {fmt_price(p)}" if p is not None else "")
            label_box(d, (right, y), txt, f_small, (255, 255, 255, 255), col + (235,), anchor="rm")
        tag = plan["type"].upper() + (f"  ·  R:R {plan['rr']}" if plan.get("rr") else "")
        label_box(d, (W + 8 * s, Y(entry_y) - 3 * s), tag, f_mid, (255, 255, 255, 255), (59, 130, 246, 235),
                  anchor="lb")
    # ---------------- bottom band: summary + disclaimer
    by = H + pad_top + pad_bot_lv
    d.line([(0, by), (CW, by)], fill=(71, 85, 105, 255), width=max(1, int(s)))
    y = by + 8 * s
    for k, t in lines:
        font = f_mid if k == "title" else f_small
        colr = (148, 163, 184, 255) if k == "dim" else (255, 255, 255, 255)
        d.text((12 * s, y), t, font=font, fill=colr)
        y += lh
    d.text((12 * s, CH - lh - 4 * s),
           "Educational only. Not financial advice.  github.com/Dimuth-Wick/crypto-chart-skills",
           font=f_small, fill=(148, 163, 184, 255))
    if plan.get("type") == "no_trade":
        tw, th = text_size(d, "NO TRADE", f_big)
        pad = 12 * s
        sx1, sy0 = CW - 14 * s, by + 12 * s
        sx0 = sx1 - tw - 2 * pad
        d.rounded_rectangle([sx0, sy0, sx1, sy0 + th + 2 * pad], radius=8 * s, fill=(15, 23, 42, 255),
                            outline=(239, 68, 68, 255), width=max(2, int(3 * s)))
        d.text((sx0 + pad, sy0 + pad - 4 * s), "NO TRADE", font=f_big, fill=(239, 68, 68, 255))
        if plan.get("reason"):
            label_box(d, (sx1, sy0 + th + 2 * pad + 8 * s), plan["reason"], f_small,
                      (255, 255, 255, 255), (127, 29, 29, 235), anchor="rt")
    # grade legend (right side of the band)
    lx = CW - 12 * s
    for g in ("no_edge", "unproven", "weak", "moderate"):
        b = label_box(d, (lx, CH - lh - 6 * s), GRADE_TEXT[g], f_small, (15, 23, 42, 255),
                      GRADE_COLOURS[g] + (245,), anchor="rt")
        lx = b[0] - 6 * s
    d.text((lx, CH - lh - 4 * s), "Evidence grades:", font=f_small, fill=(148, 163, 184, 255), anchor="ra")

    out = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path = args.output or os.path.splitext(args.image)[0] + "_annotated.png"
    out.save(out_path)
    print(out_path)


# ----------------------------------------------------------------------------
# levels: support / resistance lines, touch counts, pattern, breakout prices
# ----------------------------------------------------------------------------

def close_y(c):
    return c["body_top_y"] if c["colour"] == "green" else c["body_bottom_y"]


def tail_extremes(candles, left, right):
    """Tentative swing points inside the last `right` candles (not confirmable yet)."""
    n = len(candles)
    out = []
    if n < left + 2:
        return out
    tail = range(max(left, n - right), n)
    i_hi = min(tail, key=lambda i: candles[i]["high_y"])
    if all(candles[i_hi]["high_y"] < candles[j]["high_y"] for j in range(i_hi - left, i_hi)):
        out.append({"index": i_hi, "type": "high", "y": candles[i_hi]["high_y"], "tentative": True})
    i_lo = max(tail, key=lambda i: candles[i]["low_y"])
    if all(candles[i_lo]["low_y"] > candles[j]["low_y"] for j in range(i_lo - left, i_lo)):
        out.append({"index": i_lo, "type": "low", "y": candles[i_lo]["low_y"], "tentative": True})
    return out


def best_line(points, candles, kind, tol, max_age=None, max_stale=None):
    """Line through two swing points with the most touches whose candle BODIES respect it.

    Wicks may poke through; a body closing through the line between the first
    and the last touch rejects the line.
    """
    best = None
    for a in range(len(points)):
        for b in range(a + 1, len(points)):
            pa, pb = points[a], points[b]
            if pb["x"] == pa["x"]:
                continue
            slope = (pb["y"] - pa["y"]) / (pb["x"] - pa["x"])

            def f(x, pa=pa, slope=slope):
                return pa["y"] + slope * (x - pa["x"])

            touches = [p for p in points if abs(p["y"] - f(p["x"])) <= tol]
            first = min(t["index"] for t in touches)
            last = max(t["index"] for t in touches)
            ok = True
            for c in candles[first:last + 1]:
                if kind == "resistance" and c["body_top_y"] < f(c["x"]) - tol:
                    ok = False
                    break
                if kind == "support" and c["body_bottom_y"] > f(c["x"]) + tol:
                    ok = False
                    break
            if not ok:
                continue
            if max_stale is not None and last < len(candles) - max_stale:
                continue  # price has not touched this line for a long time
            if max_age is not None:  # skip lines that were broken long ago (finished patterns)
                tmp = {"kind": kind, "y0": pa["y"], "x0": pa["x"], "slope": slope, "last_index": last}
                brk = first_break(tmp, candles, tol)
                if brk is not None and brk < len(candles) - max_age:
                    continue
            key = (len(touches), last, last - first)
            if best is None or key > best[0]:
                best = (key, {"kind": kind, "y0": pa["y"], "x0": pa["x"], "slope": slope,
                              "first_index": first, "last_index": last,
                              "touches": sorted(touches, key=lambda t: t["index"])})
    return best[1] if best else None


def line_y(line, x):
    return line["y0"] + line["slope"] * (x - line["x0"])


def first_break(line, candles, tol):
    """First candle after the last touch that CLOSES beyond the line."""
    for i in range(line["last_index"] + 1, len(candles)):
        c = candles[i]
        ly = line_y(line, c["x"])
        if line["kind"] == "resistance" and close_y(c) < ly - tol:
            return i
        if line["kind"] == "support" and close_y(c) > ly + tol:
            return i
    return None


def classify(res, sup, tol):
    """Name the pattern from the slopes of the two lines (pixel y grows downward)."""
    x_first = min(res["touches"][0]["x"], sup["touches"][0]["x"])
    x_last = max(res["touches"][-1]["x"], sup["touches"][-1]["x"])
    span = max(1.0, x_last - x_first)

    def direction(line):
        dy = line["slope"] * span
        if abs(dy) <= 1.5 * tol:
            return "flat"
        return "up" if dy < 0 else "down"

    r, s_ = direction(res), direction(sup)
    table = {
        ("flat", "flat"): ("Range (rectangle)", "neutral"),
        ("down", "down"): ("Descending channel (bearish zigzag)", "bearish"),
        ("up", "up"): ("Ascending channel (bullish zigzag)", "bullish"),
        ("flat", "up"): ("Ascending triangle", "bullish"),
        ("down", "flat"): ("Descending triangle", "bearish"),
        ("down", "up"): ("Symmetrical triangle", "neutral"),
        ("up", "down"): ("Broadening pattern", "neutral"),
        ("up", "flat"): ("Rising resistance, flat support (broadening)", "neutral"),
        ("flat", "down"): ("Flat resistance, falling support (broadening)", "neutral"),
    }
    name, bias = table[(r, s_)]
    return name, bias, r, s_


def zones_from(points, close_yv, tol, max_zones=4):
    pts = sorted(points, key=lambda p: p["y"])
    groups, cur = [], []
    for p in pts:
        if cur and p["y"] - cur[0]["y"] > 2 * tol:
            groups.append(cur)
            cur = []
        cur.append(p)
    if cur:
        groups.append(cur)
    zones = []
    for g in groups:
        if len(g) < 2:
            continue
        ys = [p["y"] for p in g]
        cy = float(np.mean(ys))
        zones.append({"kind": "support" if cy > close_yv else "resistance",
                      "top_y": min(ys) - tol / 2, "bottom_y": max(ys) + tol / 2, "center_y": cy,
                      "touches": len(g), "last_index": max(p["index"] for p in g),
                      "points": [{"index": p["index"], "x": p["x"], "y": p["y"]} for p in g]})
    zones.sort(key=lambda z: (z["touches"], z["last_index"]), reverse=True)
    return zones[:max_zones]


def double_pattern(points, candles, tol, close_yv, kind):
    """Double bottom (kind='low') or double top (kind='high') from the last two swings."""
    sw = [p for p in points if p["type"] == kind]
    if len(sw) < 2:
        return None
    a, b = sw[-2], sw[-1]
    if abs(a["y"] - b["y"]) > 1.5 * tol:
        return None
    between = candles[a["index"] + 1:b["index"]]
    if not between:
        return None
    if kind == "low":
        neck_c = min(between, key=lambda c: c["high_y"])
        neck = neck_c["high_y"]
        if max(a["y"], b["y"]) - neck < 3 * tol:
            return None
        confirmed = any(close_y(c) < neck - tol for c in candles[b["index"] + 1:])
        name, bias = "Double bottom", "bullish"
    else:
        neck_c = max(between, key=lambda c: c["low_y"])
        neck = neck_c["low_y"]
        if neck - min(a["y"], b["y"]) < 3 * tol:
            return None
        confirmed = any(close_y(c) > neck + tol for c in candles[b["index"] + 1:])
        name, bias = "Double top", "bearish"
    return {"name": name, "bias": bias, "points": [a, b], "neck_y": neck, "neck_x": neck_c["x"],
            "confirmed": confirmed, "grade": "weak",
            "tentative": bool(a.get("tentative") or b.get("tentative"))}


def cmd_levels(args):
    global LOG_SCALE
    det = json.load(open(args.detect, encoding="utf-8"))
    LOG_SCALE = bool(det.get("log"))
    calib = parse_calib(det.get("calib"))
    candles = det["candles"]
    if len(candles) < 20:
        raise SystemExit("Need at least 20 candles; run detect on a wider chart.")
    rx0, ry0, rx1, ry1 = det["region"]
    tol = args.tol_px if args.tol_px else max(3.0, args.tol_pct / 100 * (ry1 - ry0))

    n = len(candles)
    start = max(0, n - args.lookback)
    piv = find_pivots(candles, args.left, args.right)
    piv += tail_extremes(candles, args.left, args.right)
    for p in piv:
        p["x"] = candles[p["index"]]["x"]
    piv = [p for p in piv if p["index"] >= start]
    highs = [p for p in piv if p["type"] == "high"]
    lows = [p for p in piv if p["type"] == "low"]
    last = candles[-1]
    cy = close_y(last)

    def price(y):
        return y_to_price(y, calib) if calib else None

    res = best_line(highs, candles, "resistance", tol, args.max_age, args.max_stale)
    sup = best_line(lows, candles, "support", tol, args.max_age, args.max_stale)

    def export_line(line):
        if not line:
            return None
        # zone width: spread of the touches around the line, at least `zone_half` each side
        res_ = [t["y"] - line_y(line, t["x"]) for t in line["touches"]]
        zone_half = args.zone_pct / 100 * (ry1 - ry0) / 2 if args.zone_pct else 0.75 * tol
        top_off = min(min(res_), 0) - zone_half
        bot_off = max(max(res_), 0) + zone_half
        edge = top_off if line["kind"] == "resistance" else bot_off  # the edge price must close beyond
        brk = None
        for i in range(line["last_index"] + 1, len(candles)):
            c = candles[i]
            ey = line_y(line, c["x"]) + edge
            if (line["kind"] == "resistance" and close_y(c) < ey) or (line["kind"] == "support" and close_y(c) > ey):
                brk = i
                break
        ly = line_y(line, last["x"])
        return {
            "zone_top_offset_px": top_off,
            "zone_bottom_offset_px": bot_off,
            "zone_top_price": price(ly + top_off),
            "zone_bottom_price": price(ly + bot_off),
            "break_edge_y": ly + edge,
            "break_edge_price": price(ly + edge),
            "kind": line["kind"],
            "touch_count": len(line["touches"]),
            "touches": [{"index": t["index"], "x": t["x"], "y": t["y"], "price": price(t["y"]),
                         "tentative": bool(t.get("tentative"))} for t in line["touches"]],
            "start": [line["touches"][0]["x"], line["touches"][0]["y"]],
            "slope_px": line["slope"],
            "y_at_last_candle": ly,
            "price_at_last_candle": price(ly),
            "broken_at_index": brk,
            "broken_price": price(line_y(line, candles[brk]["x"]) + edge) if brk is not None else None,
        }

    out = {
        "tolerance_px": round(tol, 2),
        "min_touches": args.min_touches,
        "lookback_candles": args.lookback,
        "last_close_y": cy,
        "last_close_price": price(cy),
        "resistance": export_line(res),
        "support": export_line(sup),
        "zones": [],
        "pattern": None,
        "double": None,
        "notes": [],
    }
    for z in zones_from(piv, cy, tol):
        z["center_price"] = price(z["center_y"])
        z["top_price"], z["bottom_price"] = price(z["top_y"]), price(z["bottom_y"])
        out["zones"].append(z)

    if res and sup:
        name, bias, rdir, sdir = classify(res, sup, tol)
        r_ok = len(res["touches"]) >= args.min_touches
        s_ok = len(sup["touches"]) >= args.min_touches
        valid = r_ok and s_ok
        R, S = out["resistance"], out["support"]
        if R["broken_at_index"] is not None and (S["broken_at_index"] is None or
                                                 R["broken_at_index"] <= S["broken_at_index"]):
            status, brk_price = "broke up", R["broken_price"]
        elif S["broken_at_index"] is not None:
            status, brk_price = "broke down", S["broken_price"]
        else:
            status, brk_price = "inside", None
        if not valid:
            grade = "none"
            verdict = (f"Not a valid pattern: resistance {len(res['touches'])} / support "
                       f"{len(sup['touches'])} touches (need {args.min_touches} each)")
        elif status == "inside":
            grade = "unproven"
            verdict = "Valid pattern, still forming: wait for a candle CLOSE outside"
        else:
            grade = "moderate"
            verdict = f"Valid pattern, {status} on a close"
        out["pattern"] = {
            "name": name, "bias": bias, "resistance_direction": rdir, "support_direction": sdir,
            "valid": valid, "status": status, "grade": grade, "verdict": verdict,
            "breakout_up_price": R["break_edge_price"], "breakout_up_y": R["break_edge_y"],
            "breakdown_price": S["break_edge_price"], "breakdown_y": S["break_edge_y"],
            "break_price": brk_price,
        }
    else:
        out["notes"].append("Could not fit both a support and a resistance line in the lookback window.")

    dbl = double_pattern(piv, candles, tol, cy, "low") or double_pattern(piv, candles, tol, cy, "high")
    if dbl:
        dbl["neck_price"] = price(dbl["neck_y"])
        dbl["points"] = [{"index": p["index"], "x": p["x"], "y": p["y"], "price": price(p["y"]),
                          "tentative": bool(p.get("tentative"))} for p in dbl["points"]]
        out["double"] = dbl
    if any(p.get("tentative") for p in piv):
        out["notes"].append("Swings in the last few candles are tentative (not confirmed yet).")
    json.dump(out, sys.stdout, indent=1, default=float)
    sys.stdout.write("\n")


def draw_double(overlay, d, occ, src, dbl, candles, region, s, Y, calib, fonts, in_pane_labels):
    """Draw a double bottom/top as a visible W (or M) with neckline, height and a zoom inset.

    Coordinates in `dbl` and `candles` are original-image pixels; Y() maps y to the canvas.
    Returns panel tags [(y_canvas, text, colour, alpha)].
    """
    f_small, f_mid, f_num = fonts
    YEL, DARK = (234, 179, 8), (15, 23, 42)
    rx0, ry0, rx1, ry1 = region
    bottom = dbl["name"] == "Double bottom"
    p1, p2 = dbl["points"]
    i1, i2 = p1["index"], p2["index"]
    neck_x, neck_y = dbl["neck_x"], dbl["neck_y"]
    width_c = max(2, i2 - i1)

    # start of the move into bottom 1 (highest high before it, for a bottom) and the exit (latest close)
    lo = max(0, i1 - width_c)
    before = candles[lo:i1] or candles[i1:i1 + 1]
    c_start = min(before, key=lambda c: c["high_y"]) if bottom else max(before, key=lambda c: c["low_y"])
    start = (c_start["x"], neck_y)
    last = candles[-1]
    # right leg: real candles if price already moved away from bottom 2, else a dashed "still needed" leg
    leg = max(abs(neck_x - p1["x"]), 30 * s) * 0.7
    if len(candles) - 1 - i2 >= 3:
        exit_pt = (last["x"], close_y(last))
        projected = None
    else:
        exit_pt = (p2["x"], p2["y"])
        projected = (min(p2["x"] + leg, rx1 - 4 * s), neck_y)
    shape = [start, (p1["x"], p1["y"]), (neck_x, neck_y), (p2["x"], p2["y"])]
    if exit_pt != (p2["x"], p2["y"]):
        shape.append(exit_pt)
    right_x = projected[0] if projected else exit_pt[0]

    def C(pt):  # original -> canvas
        return (pt[0], Y(pt[1]))

    # shaded W/M area under (over) the neckline
    poly = [C(start), C((p1["x"], p1["y"])), C((neck_x, neck_y)), C((p2["x"], p2["y"])), C((right_x, neck_y))]
    d.polygon(poly, fill=YEL + (48,))
    # the W/M line: dark halo then bright line, so it stands out on any candles
    pts = [C(p) for p in shape]
    d.line(pts, fill=(0, 0, 0, 170), width=max(4, int(7 * s)), joint="curve")
    d.line(pts, fill=YEL + (255,), width=max(3, int(4 * s)), joint="curve")
    occ.line(pts, 8 * s)
    if projected:  # the part of the W that has not happened yet
        dashed_line(d, C((p2["x"], p2["y"])), C(projected), YEL + (255,), max(2, int(3 * s)), dash=8, gap=6)
        draw_arrow(d, C((p2["x"] + (projected[0] - p2["x"]) * 0.85, p2["y"] + (projected[1] - p2["y"]) * 0.85)),
                   C(projected), YEL + (255,), max(2, int(2 * s)), 10 * s)
        occ.line([C((p2["x"], p2["y"])), C(projected)], 6 * s)
    # neckline
    dashed_line(d, C(start), (rx1, Y(neck_y)), YEL + (255,), max(2, int(2 * s)))
    occ.line([C(start), (rx1, Y(neck_y))], 6 * s)
    # bottoms / tops
    tag = "B" if bottom else "T"
    for k, p in enumerate((p1, p2), 1):
        x, y = C((p["x"], p["y"]))
        r = 7 * s
        d.ellipse([x - r, y - r, x + r, y + r], fill=YEL + (255,), outline=(255, 255, 255, 255), width=max(1, int(s)))
        lab = f"{tag}{k}" + ("?" if p.get("tentative") else "")
        occ.box(label_box(d, (x, y + (r + 4 * s if bottom else -r - 4 * s)), lab, f_num, DARK + (255,), YEL + (245,),
                          anchor="ct" if bottom else "cb"))
    # height arrow at the neckline peak
    base_y = (p1["y"] + p2["y"]) / 2
    hx = neck_x
    draw_arrow(d, C((hx, base_y)), C((hx, neck_y)), YEL + (230,), max(1, int(2 * s)), 8 * s)
    draw_arrow(d, C((hx, neck_y)), C((hx, base_y)), YEL + (230,), max(1, int(2 * s)), 8 * s)

    tags = []
    neck_p = y_to_price(neck_y, calib) if calib else None
    base_p = y_to_price(base_y, calib) if calib else None
    target_p = None
    if neck_p is not None and base_p is not None:
        height = abs(neck_p - base_p)
        target_p = neck_p + height if bottom else neck_p - height
        ty = price_to_y(target_p, calib)
        if ry0 <= ty <= ry1:
            dashed_line(d, C((p2["x"], ty)), (rx1, Y(ty)), YEL + (150,), max(1, int(s)), dash=6, gap=6)
        tags.append((Y(min(max(ty, ry0), ry1)), f"Target if confirmed ≈ {fmt_price(target_p)}", YEL, 150))
        label_box(d, (hx + 6 * s, Y((base_y + neck_y) / 2)), f"height {fmt_price(height)}", f_small,
                  DARK + (255,), YEL + (230,), anchor="lm")
    tags.append((Y(neck_y), f"Neckline {fmt_price(neck_p)}", YEL, 245))
    if in_pane_labels:
        for ty, txt, col, a in tags:
            occ.box(label_box(d, (rx1 - 6 * s, ty - 2 * s), txt, f_small, DARK + (255,), col + (a,), anchor="rb"))

    # ---- zoom inset (only when the pattern is small on screen)
    bx0 = max(rx0, start[0] - 18 * s)
    bx1 = min(rx1, right_x + 18 * s)
    top_y = min(neck_y, p1["y"], p2["y"])
    bot_y = max(neck_y, p1["y"], p2["y"])
    by0 = max(ry0, top_y - 28 * s)
    by1 = min(ry1, bot_y + 30 * s)
    bw, bh = bx1 - bx0, by1 - by0
    k = min(0.30 * (rx1 - rx0) / bw, 0.45 * (ry1 - ry0) / bh, 3.0)
    state = "confirmed" if dbl["confirmed"] else "not confirmed"
    title = f"ZOOM: {dbl['name']} · {state} · Evidence WEAK"
    if k >= 1.4:
        head = 24 * s
        tw_title = text_size(d, title, f_small)[0] + 16 * s
        if bw * k < tw_title:  # make the inset wide enough for its title
            k = tw_title / bw
        iw, ih = bw * k, bh * k + head
        occ.box((bx0, Y(by0), bx1, Y(by1)), grow=6)
        bounds = (rx0 + 6 * s, Y(ry0) + 6 * s, rx1 - 6 * s, Y(ry1) - 6 * s)
        best = None
        step = int(16 * s)
        acx, acy = (bx0 + bx1) / 2, Y((by0 + by1) / 2)
        for yy in range(int(bounds[1]), int(bounds[3] - ih), step):
            for xx in range(int(bounds[0]), int(bounds[2] - iw), step):
                b = (xx, yy, xx + iw, yy + ih)
                c = occ.cost(b) + 0.6 * math.hypot(xx + iw / 2 - acx, yy + ih / 2 - acy)
                if best is None or c < best[0]:
                    best = (c, b)
        if best:
            ix, iy = int(best[1][0]), int(best[1][1])
            crop = src.crop((int(bx0), int(by0), int(bx1), int(by1))).resize((int(iw), int(bh * k)), Image.LANCZOS)
            overlay.paste(crop.convert("RGBA"), (ix, int(iy + head)))

            def T(pt):
                return (ix + (pt[0] - bx0) * k, iy + head + (pt[1] - by0) * k)

            ipoly = [T(start), T((p1["x"], p1["y"])), T((neck_x, neck_y)), T((p2["x"], p2["y"])), T((right_x, neck_y))]
            d.polygon(ipoly, fill=YEL + (40,))
            d.line([T(p) for p in shape], fill=(0, 0, 0, 170), width=max(4, int(8 * s)), joint="curve")
            d.line([T(p) for p in shape], fill=YEL + (255,), width=max(3, int(5 * s)), joint="curve")
            if projected:
                dashed_line(d, T((p2["x"], p2["y"])), T(projected), YEL + (255,), max(2, int(4 * s)), dash=10, gap=7)
                draw_arrow(d, T((p2["x"] + (projected[0] - p2["x"]) * 0.8, p2["y"] + (projected[1] - p2["y"]) * 0.8)),
                           T(projected), YEL + (255,), max(2, int(3 * s)), 12 * s)
                mx, my = T(((p2["x"] + projected[0]) / 2, (p2["y"] + projected[1]) / 2))
                label_box(d, (mx + 8 * s, my), "still needed: close above neckline", f_small,
                          (255, 255, 255, 255), DARK + (230,), anchor="lm")
            dashed_line(d, T(start), (ix + iw, T(start)[1]), YEL + (255,), max(2, int(2 * s)))
            for kk, p in enumerate((p1, p2), 1):
                x, y = T((p["x"], p["y"]))
                label_box(d, (x, y + (8 * s if bottom else -8 * s)), f"{tag}{kk}", f_num, DARK + (255,), YEL + (245,),
                          anchor="ct" if bottom else "cb")
            label_box(d, (ix + iw - 4 * s, T(start)[1] - 3 * s), f"Neckline {fmt_price(neck_p)}", f_small,
                      DARK + (255,), YEL + (245,), anchor="rb")
            d.rectangle([ix, iy, ix + iw, iy + head], fill=DARK + (245,))
            d.text((ix + 8 * s, iy + 4 * s), title, font=f_small, fill=YEL + (255,))
            d.rectangle([ix, iy, ix + iw, iy + ih], outline=YEL + (255,), width=max(2, int(2 * s)))
            # source box on the chart + arrow from the inset to it
            dashed_line(d, (bx0, Y(by0)), (bx1, Y(by0)), YEL + (200,), max(1, int(s)), dash=6, gap=4)
            dashed_line(d, (bx0, Y(by1)), (bx1, Y(by1)), YEL + (200,), max(1, int(s)), dash=6, gap=4)
            dashed_line(d, (bx0, Y(by0)), (bx0, Y(by1)), YEL + (200,), max(1, int(s)), dash=6, gap=4)
            dashed_line(d, (bx1, Y(by0)), (bx1, Y(by1)), YEL + (200,), max(1, int(s)), dash=6, gap=4)
            sx = min(max(ix + iw / 2, bx0), bx1)
            sy = Y(by0) if iy + ih < Y(by0) else Y(by1) if iy > Y(by1) else Y((by0 + by1) / 2)
            ex = min(max(sx, ix), ix + iw)
            ey = iy + ih if iy + ih < sy else iy if iy > sy else iy + ih / 2
            if math.hypot(sx - ex, sy - ey) > 15 * s:
                draw_arrow(d, (ex, ey), (sx, sy), YEL + (255,), max(2, int(2 * s)), 10 * s)
            occ.box((ix, iy, ix + iw, iy + ih))
            return tags, True
    # no inset: a callout instead
    rows = [(dbl["name"], f_mid, (255, 255, 255, 255)), (state, f_small, (203, 213, 225, 255)),
            ("Evidence: WEAK", f_small, YEL + (255,))]
    callout(d, occ, C(((p1["x"] + p2["x"]) / 2, neck_y)), rows,
            (rx0 + 4 * s, Y(ry0) + 4 * s, rx1 - 4 * s, Y(ry1) - 4 * s), s, YEL)
    return tags, False


def cmd_draw_levels(args):
    """Chart 2: support/resistance lines with numbered touches, pattern callout, breakout prices."""
    lv = json.load(open(args.levels, encoding="utf-8"))
    det = json.load(open(args.detect, encoding="utf-8"))
    spec = json.load(open(args.spec, encoding="utf-8")) if args.spec else {}
    calib = calib_from(args, spec, det)
    src = Image.open(args.image).convert("RGBA")
    W, H = src.size
    s = max(1.0, W / 1100.0)
    f_small = load_font(int(12 * s))
    f_mid = load_font(int(14 * s), bold=True)
    f_num = load_font(int(11 * s), bold=True)
    rx0, ry0, rx1, ry1 = det["region"]
    candles = det["candles"]
    last_x = candles[-1]["x"]

    RED, GREEN, YEL = (239, 68, 68), (34, 197, 94), (234, 179, 8)
    pat = lv.get("pattern")
    dbl = lv.get("double")

    # bottom band text
    lines = [("title", spec.get("title", "Support & resistance"))]
    if pat:
        nm = pat["name"] if pat["valid"] else "possible " + pat["name"][0].lower() + pat["name"][1:]
        lines.append(("text", f"Pattern: {nm} · bias {pat['bias'].upper()}"))
        lines.append(("text", pat["verdict"]))
        if pat.get("breakout_up_price") is not None:
            lines.append(("text", f"Break UP if a candle closes above {fmt_price(pat['breakout_up_price'])}"
                                  f" · Break DOWN if it closes below {fmt_price(pat['breakdown_price'])}"))
    else:
        lines.append(("text", "No clear support/resistance pattern in view"))
    if dbl:
        state = "confirmed" if dbl["confirmed"] else "not confirmed"
        lines.append(("text", f"{dbl['name']} ({state}): neckline {fmt_price(dbl.get('neck_price'))} · Evidence WEAK"))
    for t in spec.get("summary", [])[:3]:
        lines.append(("text", t))
    lines.append(("dim", f"Rule: a valid pattern needs {lv['min_touches']}+ touches on each line. "
                         "Confirmed only on a candle CLOSE."))
    lh = int(19 * s)
    band_h = int(lh * len(lines) + 2 * lh + 16 * s)
    panel_w = int(0.30 * W)

    bg = src.getpixel((2, 2))
    canvas = Image.new("RGBA", (W + panel_w, H + band_h), (15, 23, 42, 255))
    canvas.paste(Image.new("RGBA", (W + panel_w, H), bg), (0, 0))
    canvas.paste(src, (0, 0))
    CW, CH = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    occ = pane_occupancy(src, canvas.size, det["region"], 0)
    pane_bounds = (rx0 + 4 * s, ry0 + 4 * s, rx1 - 4 * s, ry1 - 4 * s)
    d.rectangle([W, 0, CW, H], fill=(15, 23, 42, 150))
    panel_tags = []  # (y, text, colour), stacked later so they never overlap

    # zones (light bands)
    line_ys = [L["y_at_last_candle"] for L in (lv.get("resistance"), lv.get("support")) if L]
    zones = [z for z in lv.get("zones", [])
             if all(abs(z["center_y"] - ly) > 3 * lv["tolerance_px"] for ly in line_ys)]
    zones = sorted(zones, key=lambda z: abs(z["center_y"] - lv["last_close_y"]))[:2]
    for z in zones:
        col = GREEN if z["kind"] == "support" else RED
        d.rectangle([rx0, z["top_y"], rx1, z["bottom_y"]], fill=col + (34,), outline=col + (90,))
        txt = f"{z['kind'].title()} zone {fmt_price(z.get('center_price'))} · {z['touches']} touches"
        panel_tags.append((z["center_y"], txt, col, 140))

    def draw_line(L, col, valid):
        if not L:
            return
        x_a, y_a = L["start"]
        sl = L["slope_px"]
        top, bot = L.get("zone_top_offset_px", -3 * s), L.get("zone_bottom_offset_px", 3 * s)
        t_last = L["touches"][-1]

        def yl(x):
            return y_a + sl * (x - x_a)

        x_end = rx1
        if sl and not (ry0 <= yl(rx1) <= ry1):  # stop where the zone leaves the pane
            x_end = x_a + (min(max(yl(rx1), ry0), ry1) - y_a) / sl
        x_end = max(x_end, t_last["x"])
        alpha_fill = 70 if valid else 45
        # tested part of the zone (first to last touch): stronger fill
        d.polygon([(x_a, yl(x_a) + top), (t_last["x"], yl(t_last["x"]) + top),
                   (t_last["x"], yl(t_last["x"]) + bot), (x_a, yl(x_a) + bot)], fill=col + (alpha_fill,))
        # projected part: lighter fill
        if x_end > t_last["x"]:
            d.polygon([(t_last["x"], yl(t_last["x"]) + top), (x_end, yl(x_end) + top),
                       (x_end, yl(x_end) + bot), (t_last["x"], yl(t_last["x"]) + bot)], fill=col + (alpha_fill // 2,))
        ew = max(1, int(2 * s)) if valid else max(1, int(s))
        for off in (top, bot):  # zone edges
            d.line([(x_a, yl(x_a) + off), (t_last["x"], yl(t_last["x"]) + off)], fill=col + (230,), width=ew)
            if x_end > t_last["x"]:
                dashed_line(d, (t_last["x"], yl(t_last["x"]) + off), (x_end, yl(x_end) + off), col + (180,), ew)
        occ.line([(x_a, yl(x_a)), (x_end, yl(x_end))], max(6 * s, bot - top))
        rad = 9 * s
        for k, t in enumerate(L["touches"], 1):
            x, y = t["x"], t["y"]
            if t.get("tentative"):
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(15, 23, 42, 230), outline=col + (255,),
                          width=max(1, int(2 * s)))
                lbl = "?"
            else:
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col + (255,), outline=(255, 255, 255, 255),
                          width=max(1, int(s)))
                lbl = str(k)
            tw, th = text_size(d, lbl, f_num)
            d.text((x - tw / 2, y - th / 2 - 2 * s), lbl, font=f_num, fill=(255, 255, 255, 255))
            occ.box((x - rad, y - rad, x + rad, y + rad))

    valid = bool(pat and pat["valid"])
    draw_line(lv.get("resistance"), RED, valid)
    draw_line(lv.get("support"), GREEN, valid)
    if pat and pat.get("breakout_up_price") is not None:
        R_, S2 = lv["resistance"], lv["support"]
        panel_tags.append((pat["breakout_up_y"],
                           f"Resistance zone {fmt_price(R_.get('zone_bottom_price'))}–{fmt_price(R_.get('zone_top_price'))}"
                           f"\nBreak UP: close above {fmt_price(pat['breakout_up_price'])}", RED, 240))
        panel_tags.append((pat["breakdown_y"],
                           f"Support zone {fmt_price(S2.get('zone_bottom_price'))}–{fmt_price(S2.get('zone_top_price'))}"
                           f"\nBreak DOWN: close below {fmt_price(pat['breakdown_price'])}", GREEN, 240))

    # pattern callouts (after all lines so they avoid them)
    if pat and lv.get("resistance") and lv.get("support"):
        R, S_ = lv["resistance"], lv["support"]
        x_mid = (max(R["touches"][0]["x"], S_["touches"][0]["x"]) + last_x) / 2
        y_mid = (R["start"][1] + R["slope_px"] * (x_mid - R["start"][0]) +
                 S_["start"][1] + S_["slope_px"] * (x_mid - S_["start"][0])) / 2
        grade = pat["grade"]
        gcol = GRADE_COLOURS.get(grade, GRADE_COLOURS["unproven"]) if pat["valid"] else (148, 163, 184)
        gtext = f"Evidence: {GRADE_TEXT.get(grade, grade.upper())}" if pat["valid"] else "Not graded (not a valid pattern)"
        rows = [(pat["name"] if pat["valid"] else "Possible " + pat["name"][0].lower() + pat["name"][1:],
                 f_mid, (255, 255, 255, 255)),
                (f"Bias: {pat['bias'].upper()} · touches R {R['touch_count']} / S {S_['touch_count']}",
                 f_small, (203, 213, 225, 255)),
                ("VALID" if pat["valid"] else f"NOT VALID: needs {lv['min_touches']}+ touches each",
                 f_small, (GREEN if pat["valid"] else RED) + (255,)),
                (gtext, f_small, gcol + (255,))]
        callout(d, occ, (x_mid, y_mid), rows, pane_bounds, s, gcol)
    if dbl:  # drawn last so the zoom inset can find empty space around everything else
        tags, _ = draw_double(overlay, d, occ, src, dbl, candles, det["region"], s, lambda y: float(y), calib,
                              (f_small, f_mid, f_num), in_pane_labels=False)
        panel_tags.extend(tags)

    # panel tags, de-overlapped top to bottom
    panel_tags.sort(key=lambda t: t[0])
    prev_bottom = None
    for y, txt, col, alpha in panel_tags:
        th = text_size(d, txt, f_small)[1] + 8 * s
        yy = y if prev_bottom is None else max(y, prev_bottom + 6 * s + th / 2)
        yy = min(max(yy, th / 2 + 4 * s), H - th / 2 - 4 * s)
        prev_bottom = yy + th / 2
        if abs(yy - y) > 2:
            d.line([(W + 2 * s, y), (W + 12 * s, yy)], fill=col + (200,), width=max(1, int(s)))
        label_box(d, (CW - 8 * s, yy), txt, f_small, (255, 255, 255, 255), col + (alpha,), anchor="rm")

    # bottom band
    by = H
    d.line([(0, by), (CW, by)], fill=(71, 85, 105, 255), width=max(1, int(s)))
    y = by + 8 * s
    for k, t in lines:
        font = f_mid if k == "title" else f_small
        colr = (148, 163, 184, 255) if k == "dim" else (255, 255, 255, 255)
        d.text((12 * s, y), t, font=font, fill=colr)
        y += lh
    d.text((12 * s, CH - lh - 4 * s),
           "Educational only. Not financial advice.  github.com/Dimuth-Wick/crypto-chart-skills",
           font=f_small, fill=(148, 163, 184, 255))
    lx = CW - 12 * s
    for g in ("no_edge", "unproven", "weak", "moderate"):
        b = label_box(d, (lx, CH - lh - 6 * s), GRADE_TEXT[g], f_small, (15, 23, 42, 255),
                      GRADE_COLOURS[g] + (245,), anchor="rt")
        lx = b[0] - 6 * s

    out = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path = args.output or os.path.splitext(args.image)[0] + "_levels.png"
    out.save(out_path)
    print(out_path)


# ----------------------------------------------------------------------------
# size
# ----------------------------------------------------------------------------

def cmd_size(args):
    entry, stop = args.entry, args.stop
    if entry == stop:
        raise SystemExit("Entry and stop cannot be equal.")
    side = "long" if stop < entry else "short"
    risk_per_unit = abs(entry - stop)
    fee = entry * args.fee_pct / 100 * 2  # round trip, per unit
    risk_amount = args.account * args.risk_pct / 100
    units = risk_amount / (risk_per_unit + fee)
    notional = units * entry
    targets = []
    for t in args.targets or []:
        if (side == "long" and t <= entry) or (side == "short" and t >= entry):
            raise SystemExit(f"Target {t} is on the wrong side of entry for a {side}.")
        reward = abs(t - entry) - fee
        targets.append({"target": t, "rr": round(reward / (risk_per_unit + fee), 2),
                        "profit": round(reward * units, 2)})
    warnings = []
    if args.risk_pct > 2:
        warnings.append("Risk above 2% of account per trade is aggressive.")
    if targets and targets[0]["rr"] < 1.5:
        warnings.append("First target R:R below 1.5 after fees: consider NO TRADE.")
    lev = notional / args.account
    if lev > 1:
        warnings.append(f"Position needs about {lev:.1f}x leverage. Leverage can cause liquidation; "
                        "the 10 Oct 2025 crash liquidated $19B+ in one day.")
    out = {
        "side": side,
        "risk_amount": round(risk_amount, 2),
        "stop_distance_pct": round(risk_per_unit / entry * 100, 2),
        "units": round(units, 6),
        "notional": round(notional, 2),
        "leverage_needed": round(max(lev, 1.0), 2),
        "targets": targets,
        "warnings": warnings,
        "note": "Educational calculation only. Not financial advice.",
    }
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


# ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("detect", help="find candles and HH/HL/LH/LL pivots")
    a.add_argument("image")
    a.add_argument("--region", help="price pane only: x0,y0,x1,y1 (exclude price axis, volume, header)")
    a.add_argument("--calib", help="two price-axis reference points: y1:price1,y2:price2")
    a.add_argument("--log", action="store_true", help="price axis is logarithmic (uneven label spacing)")
    a.add_argument("--left", type=int, default=3, help="candles left of a pivot (default 3)")
    a.add_argument("--right", type=int, default=3, help="candles right of a pivot (default 3)")
    a.add_argument("--sat-min", type=float, default=0.25, help="min colour saturation for candle pixels")
    a.add_argument("--val-min", type=float, default=0.25, help="min brightness for candle pixels")
    a.set_defaults(func=cmd_detect)

    b = sub.add_parser("draw", help="draw annotations from a JSON spec")
    b.add_argument("image")
    b.add_argument("spec")
    b.add_argument("--detect", help="detect.json from the detect command (enables pivot snapping)")
    b.add_argument("--calib", help="y1:price1,y2:price2 so levels can be given as prices")
    b.add_argument("--log", action="store_true", help="price axis is logarithmic")
    b.add_argument("--levels", help="levels.json: draws a detected double bottom/top as a W/M")
    b.add_argument("-o", "--output")
    b.set_defaults(func=cmd_draw)

    lv = sub.add_parser("levels", help="support/resistance lines, touch counts, pattern and breakout prices")
    lv.add_argument("detect", help="detect.json from the detect command")
    lv.add_argument("--min-touches", type=int, default=3, help="touches needed on EACH line for a valid pattern")
    lv.add_argument("--lookback", type=int, default=100, help="only use the last N candles (default 100)")
    lv.add_argument("--max-age", type=int, default=10,
                    help="ignore lines broken more than N candles ago (finished patterns, default 10)")
    lv.add_argument("--max-stale", type=int, default=40,
                    help="a line's last touch must be within the last N candles (default 40)")
    lv.add_argument("--zone-pct", type=float,
                    help="support/resistance zone width, %% of pane height (default: 1.5x touch tolerance)")
    lv.add_argument("--left", type=int, default=3)
    lv.add_argument("--right", type=int, default=3)
    lv.add_argument("--tol-pct", type=float, default=1.2, help="touch tolerance, %% of pane height (default 1.2)")
    lv.add_argument("--tol-px", type=float, help="touch tolerance in pixels (overrides --tol-pct)")
    lv.set_defaults(func=cmd_levels)

    dl = sub.add_parser("draw-levels", help="chart 2: support/resistance, touches, pattern, breakout prices")
    dl.add_argument("image")
    dl.add_argument("levels", help="levels.json from the levels command")
    dl.add_argument("--detect", required=True)
    dl.add_argument("--spec", help="optional JSON with title and extra summary lines")
    dl.add_argument("-o", "--output")
    dl.set_defaults(func=cmd_draw_levels)

    c = sub.add_parser("size", help="position size and risk/reward")
    c.add_argument("--account", type=float, required=True)
    c.add_argument("--risk-pct", type=float, default=1.0)
    c.add_argument("--entry", type=float, required=True)
    c.add_argument("--stop", type=float, required=True)
    c.add_argument("--targets", type=float, nargs="*")
    c.add_argument("--fee-pct", type=float, default=0.1, help="fee per side in percent (default 0.1)")
    c.set_defaults(func=cmd_size)

    args = ap.parse_args(argv)
    global LOG_SCALE
    LOG_SCALE = bool(getattr(args, "log", False))
    args.func(args)


if __name__ == "__main__":
    main()
