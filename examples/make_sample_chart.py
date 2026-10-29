#!/usr/bin/env python3
"""
Make a synthetic candlestick screenshot for testing the chart-reader skill.

It looks like a dark exchange chart: grid lines, a price axis with labels,
a coloured "last price" tag and optional volume bars. It also writes the
true OHLC and pixel positions to a JSON file, so tests can check detection.

    python make_sample_chart.py out.png --seed 7 --style uptrend
"""

import argparse
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BG = (19, 23, 34)
GRID = (42, 46, 57)
TEXT = (178, 181, 190)
GREEN = (38, 166, 154)
RED = (239, 83, 80)


def make_channel(n, seed, slope=-0.0025, period=18, width=0.045):
    """Zigzag between two parallel lines (descending channel if slope < 0)."""
    rng = np.random.default_rng(seed)
    mid = 2000 * np.exp(slope * np.arange(n))
    phase = (np.arange(n) % period) / period
    tri = np.where(phase < 0.5, phase * 4 - 1, 3 - phase * 4)  # -1..1 zigzag
    close = mid * (1 + tri * width / 2 * 0.85) * (1 + rng.normal(0, 0.002, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    upper, lower = mid * (1 + width / 2), mid * (1 - width / 2)
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    top = (np.abs(tri - 1) < 1e-9)
    bot = (np.abs(tri + 1) < 1e-9)
    high = np.where(top, upper, np.minimum(high, upper))
    low = np.where(bot, lower, np.maximum(low, lower))
    return open_, high, low, close, rng.uniform(0.3, 1.0, n)


def make_ohlc(n, seed, style):
    if style == "channel":
        return make_channel(n, seed)
    rng = np.random.default_rng(seed)
    drift = {"uptrend": 0.0025, "downtrend": -0.0025, "range": 0.0}[style]
    wave = np.sin(np.linspace(0, 5 * np.pi, n)) * 0.012
    rets = drift + np.diff(np.concatenate([[0], wave])) + rng.normal(0, 0.008, n)
    close = 2000 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[2000], close[:-1]])
    spread = np.abs(rng.normal(0, 0.006, n)) * close
    high = np.maximum(open_, close) + spread * rng.uniform(0.2, 1.0, n)
    low = np.minimum(open_, close) - spread * rng.uniform(0.2, 1.0, n)
    vol = rng.uniform(0.3, 1.0, n)
    return open_, high, low, close, vol


def render(path, n=70, seed=7, style="uptrend", width=1280, height=720, volume=True):
    o, h, l, c, v = make_ohlc(n, seed, style)
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = ImageFont.load_default()

    pane = (10, 50, width - 90, height - (150 if volume else 40))  # price pane
    px0, py0, px1, py1 = pane
    pmin, pmax = l.min() * 0.995, h.max() * 1.005

    def y_of(p):
        return py1 - (p - pmin) / (pmax - pmin) * (py1 - py0)

    # grid + axis labels
    for k in range(7):
        price = pmin + (pmax - pmin) * k / 6
        y = y_of(price)
        d.line([(px0, y), (width - 85, y)], fill=GRID, width=1)
        d.text((width - 80, y - 7), f"{price:,.1f}", font=font, fill=TEXT)
    for k in range(10):
        x = px0 + (px1 - px0) * k / 9
        d.line([(x, py0), (x, height - 30)], fill=GRID, width=1)
    d.text((14, 14), "ETHUSDT · 4h · SAMPLE (synthetic data)", font=font, fill=TEXT)

    step = (px1 - px0) / n
    body_w = max(3, int(step * 0.65))
    truth = []
    for i in range(n):
        xc = px0 + step * (i + 0.5)
        col = GREEN if c[i] >= o[i] else RED
        d.line([(xc, y_of(h[i])), (xc, y_of(l[i]))], fill=col, width=2)
        top, bot = y_of(max(o[i], c[i])), y_of(min(o[i], c[i]))
        if bot - top < 2:
            bot = top + 2
        d.rectangle([xc - body_w / 2, top, xc + body_w / 2, bot], fill=col)
        truth.append({"x": xc, "high_y": y_of(h[i]), "low_y": y_of(l[i]),
                      "open": o[i], "high": h[i], "low": l[i], "close": c[i]})
        if volume:
            vh = v[i] * 90
            d.rectangle([xc - body_w / 2, height - 40 - vh, xc + body_w / 2, height - 40],
                        fill=tuple(int(ch * 0.55) for ch in col))

    # coloured last-price tag on the axis (a classic false positive)
    yl = y_of(c[-1])
    tag = GREEN if c[-1] >= o[-1] else RED
    d.rectangle([width - 86, yl - 10, width - 4, yl + 10], fill=tag)
    d.text((width - 80, yl - 7), f"{c[-1]:,.1f}", font=font, fill=(255, 255, 255))

    img.save(path)
    calib = f"{y_of(pmax):.1f}:{pmax:.4f},{y_of(pmin):.1f}:{pmin:.4f}"
    meta = {"pane": pane, "calib": calib, "candles": truth}
    with open(path.rsplit(".", 1)[0] + "_truth.json", "w") as fh:
        json.dump(meta, fh, indent=1, default=float)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n", type=int, default=70)
    ap.add_argument("--style", choices=["uptrend", "downtrend", "range", "channel"], default="uptrend")
    ap.add_argument("--no-volume", action="store_true")
    a = ap.parse_args()
    m = render(a.out, a.n, a.seed, a.style, volume=not a.no_volume)
    print(a.out, "calib:", m["calib"])
