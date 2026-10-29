# crypto-chart-skills

**An evidence-graded chart-reading skill for AI agents (Claude, Codex and other tools that load `SKILL.md` skills).**
Give it a crypto chart screenshot and it returns **two annotated charts**:

| Chart | What it shows |
|---|---|
| **1. Structure** | Swing pivots (HH / HL / LH / LL), market structure, patterns **with their research grade**, and a risk-first trade plan, or a **NO TRADE** stamp |
| **2. Levels** | Support and resistance **zones** (bands, not thin lines) with **numbered touches**, the pattern (zigzag/channel, triangle, range, double bottom/top), bullish or bearish bias, whether it is **VALID** (3+ touches on each line), and the **exact breakout prices** |

Pattern names sit in empty space with an arrow, so they never cover the chart.

**Chart 1: structure**

| Input screenshot | Output |
|---|---|
| ![input](examples/sample_uptrend.png) | ![output](examples/sample_uptrend_annotated.png) |

**Chart 2: levels.** A descending channel (bearish zigzag) with 3 resistance and 4 support touches, so it is valid, plus the price where it breaks:

![levels](examples/sample_channel_levels.png)

When there is no clean setup, the skill says so:

![no trade](examples/sample_range_no_trade.png)

*Sample images use synthetic data.*

> ⚠️ **Educational only. Not financial advice.** Most chart patterns have weak
> evidence, and even frontier AI models lost money in live trading tests.
> Never risk money you cannot afford to lose.

---

## Why evidence grades?

Before building this, I reviewed the research on AI in crypto trading and on chart
patterns ([full report](docs/research.md)). The short version:

| Signal | Grade |
|---|---|
| Market structure (HH-HL / LH-LL), range and triangle **breakouts** | 🟢 Moderate |
| Head & shoulders, double tops/bottoms, support/resistance | 🟡 Weak |
| Triangles before breakout, flags, wedges | ⚪ Unproven |
| Candlestick patterns | 🔴 Mostly no edge |

So the skill leads with structure, shows every pattern's grade on the chart, and
treats "NO TRADE" as a normal answer.

### The 3-touch rule
A support/resistance pattern (zigzag channel, range, triangle) only counts as **valid** when
price has touched the resistance line **3+ times** and the support line **3+ times**, without
candle bodies closing through the lines. This rule comes from my own trading experience.

| Touches | Result |
|---|---|
| Fewer than 3 on a line | "Possible ..." only, not graded, no plan |
| 3+ each, still inside | Valid, forming: ⚪ Unproven until breakout |
| 3+ each, candle **closed** outside | Valid breakout: 🟢 Moderate |

A valid pattern is not a guaranteed breakout. It only means the levels are well tested.

## How it works

```
screenshot ──► detect ──► levels ──► Claude/Codex checks the result ──► draw        (chart 1: structure)
               candles,    S/R lines,   grades patterns, applies            draw-levels (chart 2: levels)
               pivots,     touches,     risk rules, plan or NO TRADE
               HH/HL       breakouts
```

The script snaps every pivot to a real candle wick, because general vision
models are not precise at reading exact positions on candlestick charts.

## Install

1. Download this repo (green **Code** button → *Download ZIP*) or `git clone` it.
2. Copy the folder `skills/chart-reader` into your agent's skills folder:
   - **Claude Code**: `~/.claude/skills/chart-reader` (or `.claude/skills/` inside a project)
   - **Claude app**: zip the `chart-reader` folder and upload it as a skill in Claude's settings
   - **Codex**: `~/.codex/skills/chart-reader`
   - Other agents: any tool that reads `SKILL.md` skills
   (If your tool uses a different path, check its docs.)
3. Install the two Python libraries: `pip install -r requirements.txt`
4. Share a chart screenshot and ask, for example, *"What does this chart show? Any setup?"*

### Recommended timeframes

| Timeframe | Recommendation |
|---|---|
| **4-hour and higher** (4h, 1D, 1W) | ✅ Recommended. Patterns and structure are clearest here |
| **1-hour** | ⚠️ Sometimes works. Use with extra caution |
| **Below 1-hour** (30m, 15m, 5m, 1m) | ❌ Not recommended. Too much noise; patterns often don't make sense |

This comes from my own trading experience, not from the research studies. Lower
timeframes are also where fees, spread and fast bots have the biggest effect.

### Tips for good screenshots
- Use a **4-hour or higher** timeframe (see above).
- Candlestick chart with coloured candles (default green/red works best).
- Hide indicators and drawings on the price pane.
- 40–200 candles visible; the price axis visible on the right.

## Use the script directly

```bash
cd skills/chart-reader
# 1. find candles and pivots (region = price pane only, calib = two axis labels)
python scripts/annotate.py detect chart.png --region 10,50,1190,570 --calib 50:2168.3,570:1909.5 > detect.json
# 2. chart 1: draw your annotations (see references/spec-format.md)
python scripts/annotate.py draw chart.png spec.json --detect detect.json --calib 50:2168.3,570:1909.5 -o out.png
# 3. support/resistance, touches, pattern, breakout prices + chart 2
python scripts/annotate.py levels detect.json > levels.json
python scripts/annotate.py draw-levels chart.png levels.json --detect detect.json -o levels.png
# 4. position size and risk/reward
python scripts/annotate.py size --account 1000 --risk-pct 1 --entry 2160 --stop 2098 --targets 2250 2310
```

Try it on a generated chart: `python examples/make_sample_chart.py test.png --style channel`

## Repository layout

```
skills/chart-reader/
  SKILL.md                     instructions the agent follows
  scripts/annotate.py          detect / draw / size
  references/evidence-grades.md  grade for every pattern
  references/patterns.md       how each pattern is recognised and confirmed
  references/risk-rules.md     when to plan, when to say NO TRADE
  references/spec-format.md    JSON format for drawing
docs/research.md               the research behind the grades (with sources)
examples/                      sample charts and a synthetic chart generator
tests/                         pytest tests on synthetic charts
```

## Limitations

- Tested on synthetic charts and a real TradingView ETHUSDT 4h screenshot. Real screenshots vary; check the detected pivots.
- Needs coloured candles. Hollow, line or Heikin-Ashi charts may detect poorly.
- Price calibration supports linear and log axes (`--log`); check a third axis label to confirm.
- The last few candles cannot be confirmed pivots yet.
- Grades come from a limited set of studies and will change as evidence changes.

## Contributing

Issues and pull requests are welcome, especially new studies that support or
change a grade (please include the source), and screenshots where detection fails.

Run the tests: `pip install -r requirements-dev.txt && python -m pytest tests -q`

## License

[MIT](LICENSE) © Dimuth-Wick. Provided "as is", without warranty. You are
responsible for your own trading decisions.
