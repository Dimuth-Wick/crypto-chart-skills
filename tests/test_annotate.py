"""Tests for the chart-reader annotate script, using synthetic charts.

Run:  python -m pytest tests -q
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "chart-reader", "scripts", "annotate.py")
sys.path.insert(0, os.path.join(ROOT, "examples"))
sys.path.insert(0, os.path.dirname(SCRIPT))

import annotate  # noqa: E402
from make_sample_chart import render  # noqa: E402


def run(*args):
    out = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, check=True)
    return out.stdout


@pytest.mark.parametrize("style,seed", [("uptrend", 7), ("downtrend", 11), ("range", 3)])
def test_detect_finds_every_candle(tmp_path, style, seed):
    img = tmp_path / "c.png"
    truth = render(str(img), n=70, seed=seed, style=style)
    det = json.loads(run("detect", str(img)))
    assert det["candle_count"] == 70  # volume bars and the price tag are ignored
    for got, exp in zip(det["candles"], truth["candles"]):
        assert abs(got["x"] - exp["x"]) <= 2
        assert abs(got["high_y"] - exp["high_y"]) <= 2
        assert abs(got["low_y"] - exp["low_y"]) <= 2


def test_pivots_match_ground_truth(tmp_path):
    img = tmp_path / "c.png"
    truth = render(str(img), n=70, seed=7, style="uptrend")
    det = json.loads(run("detect", str(img)))
    expected = annotate.find_pivots(truth["candles"], 3, 3)
    assert [(p["index"], p["type"]) for p in det["pivots"]] == [(p["index"], p["type"]) for p in expected]


def test_calibration_gives_prices(tmp_path):
    img = tmp_path / "c.png"
    truth = render(str(img), n=70, seed=7, style="uptrend")
    det = json.loads(run("detect", str(img), "--calib", truth["calib"]))
    for got, exp in zip(det["candles"], truth["candles"]):
        assert abs(got["high"] - exp["high"]) / exp["high"] < 0.002


def test_labels_and_trend():
    candles = [{"high_y": h, "low_y": h + 20} for h in
               [100, 90, 80, 70, 80, 90, 100, 95, 85, 75, 60, 70, 80, 90, 85, 75, 65, 50, 60, 70, 80]]
    piv = annotate.label_pivots(annotate.find_pivots(candles, 2, 2), 1)
    labels = [p["label"] for p in piv]
    assert "HH" in labels and "HL" in labels
    assert annotate.trend_from_pivots(piv)[0] == "uptrend"


def test_draw_plan_and_no_trade(tmp_path):
    img = tmp_path / "c.png"
    truth = render(str(img), n=70, seed=7, style="uptrend")
    det_path = tmp_path / "d.json"
    det_path.write_text(run("detect", str(img), "--calib", truth["calib"]))
    for plan in ({"type": "long", "entry": 2160, "stop": 2098, "targets": [2250], "rr": "1:1.5"},
                 {"type": "no_trade", "reason": "unclear"}):
        spec = tmp_path / "s.json"
        spec.write_text(json.dumps({"title": "t", "use_detected_pivots": True, "plan": plan,
                                    "patterns": [{"name": "p", "grade": "weak", "lines": [[100, 300, 400, 200]]}]}))
        out = tmp_path / "o.png"
        run("draw", str(img), str(spec), "--detect", str(det_path), "--calib", truth["calib"], "-o", str(out))
        assert out.exists() and out.stat().st_size > 10_000


def test_size_math():
    res = json.loads(run("size", "--account", "1000", "--risk-pct", "1", "--entry", "100",
                         "--stop", "95", "--targets", "110", "--fee-pct", "0"))
    assert res["side"] == "long"
    assert res["risk_amount"] == 10
    assert abs(res["units"] - 2) < 1e-9
    assert res["targets"][0]["rr"] == 2.0


def test_size_rejects_wrong_side_target():
    with pytest.raises(subprocess.CalledProcessError):
        run("size", "--account", "1000", "--entry", "100", "--stop", "95", "--targets", "90")


def test_log_scale_calibration():
    # TradingView-style log axis: labels from a real ETHUSDT 4h screenshot
    annotate.LOG_SCALE = True
    try:
        calib = (190, 2800, 871, 2282)
        for y, price in [(238, 2760), (568, 2500), (788, 2340), (912, 2254.5)]:
            assert abs(annotate.y_to_price(y, calib) - price) < 2
            assert abs(annotate.price_to_y(price, calib) - y) < 2
    finally:
        annotate.LOG_SCALE = False
