#!/usr/bin/env python3
"""
annotate.py - chart-reader helper for crypto chart screenshots.

Three commands:

  detect  Find candles in a screenshot by colour, then find swing pivots
          and label them HH / HL / LH / LL. Prints JSON.
  draw    Draw pivots, structure, patterns, zones and a trade plan
          (or a NO TRADE stamp) on the screenshot from a JSON spec.
  size    Position sizing and risk/reward from entry, stop and targets.

Educational tool only. Not financial advice.

Examples
  python annotate.py detect chart.png --region 0,60,1180,640 --calib 120:2400,560:2200 > detect.json
  python annotate.py draw chart.png spec.json --detect detect.json -o chart_annotated.png
  python annotate.py size --account 1000 --risk-pct 1 --entry 2350 --stop 2290 --targets 2470 2560
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

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


def cmd_draw(args):
    spec = json.load(open(args.spec, encoding="utf-8"))
    src = Image.open(args.image).convert("RGBA")
    W, H = src.size
    s = max(1.0, W / 1100.0)  # scale for line widths and fonts

    det = json.load(open(args.detect, encoding="utf-8")) if args.detect else None
    candles = det["candles"] if det else []
    calib = parse_calib(args.calib or spec.get("calib"))

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

    # ---------------- zones
    for z in spec.get("zones", []):
        ya, _ = resolve_y(z["from"], calib)
        yb, _ = resolve_y(z["to"], calib)
        kind = z.get("kind", "support")
        col = (34, 197, 94) if kind == "support" else (239, 68, 68)
        top, bot = Y(min(ya, yb)), Y(max(ya, yb))
        d.rectangle([rx0, top, rx1, bot], fill=col + (40,), outline=col + (120,))
        label_box(d, (rx0 + 8 * s, top - 2 * s), z.get("label", kind.title()),
                  f_small, (255, 255, 255, 240), col + (190,), anchor="lb")

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

    r = 5 * s
    for p in pivots:
        x, y = float(p["x"]), Y(p["y"])
        lab = p.get("label", "")
        is_high = p.get("type", "high") == "high"
        col = (34, 197, 94) if lab in ("HH", "HL") else (239, 68, 68) if lab in ("LH", "LL") else (203, 213, 225)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (255,), outline=(255, 255, 255, 255), width=max(1, int(s)))
        if lab:
            anchor = "cb" if is_high else "ct"
            yy = y - r - 3 * s if is_high else y + r + 3 * s
            label_box(d, (x, yy), lab, f_mid, (255, 255, 255, 255), col + (235,), anchor=anchor)

    # ---------------- patterns (label at the middle of the first line, grade badge on top)
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
        if segs:
            xa, ya, xb, yb = segs[0]
            ax, ay = (xa + xb) / 2, (ya + yb) / 2
            ax += 14 * s  # nudge off the line
        else:
            ax, ay = rx0 + (rx1 - rx0) * 0.5, Y(ry0 + 40 * s)
        name = pat.get("name", "Pattern")
        status = pat.get("status")
        text = name + (f" ({status})" if status else "")
        box = label_box(d, (ax, ay), text, f_mid, (255, 255, 255, 255), (15, 23, 42, 225), anchor="lt")
        label_box(d, (box[0], box[1] - 3 * s), f"Evidence: {GRADE_TEXT.get(grade, grade.upper())}",
                  f_small, (15, 23, 42, 255), col + (245,), anchor="lb")

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
    b.add_argument("-o", "--output")
    b.set_defaults(func=cmd_draw)

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
