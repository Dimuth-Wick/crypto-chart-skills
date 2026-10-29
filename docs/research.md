# How AI Changed Crypto Trading — and What the Evidence Says About Chart Patterns

*Research basis for the `crypto-chart-skills` repository. Draft, 29 October 2026.*
*Educational material only. Not financial advice.*

---

## TL;DR

1. **Machines run the market plumbing.** Market makers, arbitrage, liquidation engines and on-chain agents dominate execution. Popular "65–86% of volume is AI" figures come mostly from marketing blogs and are **not reliable**; treat them as rough estimates.
2. **Bots amplify, they don't create edge.** The 10 October 2025 crash ($19B+ liquidated) showed automated systems can turn a shock into a cascade when liquidity providers pull out.
3. **LLMs are not yet good autonomous traders.** In live tests most frontier models lost money, overtraded, and behaved inconsistently. Even the newest models (Claude Opus 5.5, GPT-6 Astra) have **no long, robust live record yet**.
4. **Chart patterns: mostly weak evidence.** Trend/price-structure signals have the best support. Classic shapes (head & shoulders, double tops) show mixed results. Candlestick patterns mostly fail after costs.
5. **AI supercharged scams.** AI-linked crypto scams earned ~4.5× more per operation; regulators warn that "AI bot" return promises are a red flag.

**Implication for the skill:** lead with market structure (HH/HL/LH/LL), treat classic patterns as weaker context, treat candlesticks as weak confirmation only, put risk management first, and make "NO TRADE" a normal answer.

---

## 1. Bots & market structure

**What the data reliably shows**

- Crypto trading is overwhelmingly derivatives. CoinGlass put Q1 2026 total volume at about $20.57T, with roughly 90% from derivatives ([The CC Press](https://theccpress.com/coinglass-q1-crypto-trading-volume-20-57t-derivatives-90-percent/)). Leverage plus automated liquidation engines is the core structural risk.
- **10 October 2025** was the largest liquidation day on record: over $19B of leveraged positions closed and roughly 1.6M accounts liquidated ([CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained)). Exchanges used auto-deleveraging (ADL), forcibly closing profitable positions to cover losses ([FTI Consulting](https://www.fticonsulting.com/zh-cn/china/insights/articles/crypto-crash-october-2025-leverage-met-liquidity)). Reporting attributes the severity to market-maker liquidity collapsing as order books emptied ([Coinpedia via TradingView](https://www.tradingview.com/news/coinpedia:a9beb70ce094b:0-19-billion-crypto-crash-shows-market-makers-can-also-break-the-market/)).
- On-chain, autonomous agents drive about **19% of activity**, with 17,000+ agents launched since 2025. They do well at narrow tasks such as yield optimisation, but **humans beat them by up to 5:1 in open-ended trading** ([Decrypt on DWF Ventures](https://decrypt.co/364727/ai-agents-already-run-a-fifth-of-defi-but-still-lose-to-humans-at-trading)).

**What is NOT reliable**

- Claims that "AI handles 65–75%" or "86%" of crypto volume trace to blogs and promotional sites without published methodology (e.g. [ai2.work](https://ai2.work/blog/ai-trading-agents-now-drive-66-of-crypto-volume-in-2026), [LedgerMind](https://theledgermind.com/?p=768)). "Algorithmic" (rule-based execution) is also not the same as "AI". **Do not quote these as facts in the repo.**

## 2. Do bots and AI traders actually perform?

### Retail bots
- No rigorous public dataset exists on retail bot returns. The widely repeated "73% of bot accounts fail in 6 months" comes from industry blogs, not audited data ([Lenz summary](https://lenz.io/q/success-rate-of-crypto-trading-bots)). Treat as anecdotal.
- A Bloomberg analysis of Polymarket found most users lost money while a small group of automated accounts captured most profits, largely through **earlier, faster entries** ([CryptoRank summary](https://cryptorank.io/news/feed/490b8-polymarket-users-lose-money-bots)). Speed beats retail, even when retail is right about direction.

### LLMs trading live (strongest current evidence)
| Test | Result |
|---|---|
| **Alpha Arena S1** (Oct–Nov 2025, $10k each, crypto perps on Hyperliquid) | 4 of 6 models finished in the red. Qwen 3 Max +22.3%, DeepSeek +4.9%, GPT-5 −62.7%, Gemini 2.5 Pro −56.7% ([Protos](https://protos.com/llm-crypto-trading-contest-finds-llms-cant-trade-crypto), [Aurpay](https://aurpay.net/?p=23782)) |
| **Alpha Arena S1.5** (US stocks, 4 competitions) | Grok 4.20 won, +12% average, profitable in all four ([Forklog](https://forklog.com/en/?p=91943)). Across all runs only **6 of 32** results were profitable; total portfolio fell ~33%. Overtrading was common (Qwen made 1,418 trades vs Grok's 158) ([KuCoin News](https://www.kucoin.com/news/flash/ai-trading-models-struggle-in-live-market-tests-majority-of-systems-report-losses)) |
| **TradeRank.ai Season 10** (Oct 2026, simulated $10k, includes Claude Opus 5.5 and GPT-6.1 Sol Pro) | Leader at just +1.63% as of 28 Oct 2026, a few weeks in ([TradeRank](https://www.traderank.ai/)). Too early and simulated: no conclusion yet |

**Why LLM backtests can't be trusted:** a model asked in 2026 to trade March 2020 already "knows" what happened. This lookahead bias forces evaluation into live markets ([Wallstreetcn on Bloomberg report](https://wallstreetcn.com/articles/3771681)). Nof1's founder said directly handing an LLM money to trade alone is not yet feasible; LLMs are better at research than at timing and position sizing (same source).

**Newest models.** Claude Opus 5.5 (22 Sep 2026) and GPT-6 Astra (3 Sep 2026) lead general benchmarks ([BenchLM](https://benchlm.ai/compare/chatgpt-vs-claude)). Opus 5.5 also tops a 94-model finance Q&A benchmark at 91.6% ([AIMultiple](https://aimultiple.com/finance-llm)). **Knowledge benchmarks ≠ trading edge.** There is no long live trading record for either model yet.

## 3. Chart-pattern evidence (the core of the skill)

### Can AI read charts at all?
- **Yes, in principle.** A CNN trained on chart images of US stocks found image-based signals were strong out-of-sample return predictors ([Jiang, Kelly & Xiu, *Journal of Finance* 2023](https://economics.yale.edu/research/re-imagining-price-trends)). Note: equities, a trained specialist model, not a chatbot.
- **General vision-language models are weaker.** A 2026 benchmark that isolated visual reasoning found VLMs' ability to combine multi-timeframe candlestick information is limited; they did better spotting downside in bear markets than upside ([arXiv 2604.12659](https://arxiv.org/pdf/2604.12659)).
- → **Design consequence:** the skill must not trust eyeballed pixel positions. A script should snap pivots to detected candle wicks and the output should state a confidence level.

### Evidence grades

| Signal | Grade | Evidence |
|---|---|---|
| **Trend / market structure** (HH-HL, LH-LL, range breakouts, MA trend) | 🟢 **Moderate** | Studies of moving-average and trading-range-breakout rules report excess returns in crypto, with one reporting ~8.8%/yr when Bitcoin is excluded (Hudson & Urquhart; Corbet et al., as summarised in the [crypto trading survey, arXiv 2003.11352](https://arxiv.org/pdf/2003.11352)); image-based trend signals predictive in equities (Jiang-Kelly-Xiu). Caveat: Svogun & Bazán-Palomino (2022) ask whether transaction costs and bubbles erase these gains — to be read in full before final grading |
| **Head & shoulders** | 🟡 **Weak / mixed** | Statistical "incremental information" in US stocks 1962–96 ([Lo, Mamaysky & Wang 2000](https://econpapers.repec.org/RePEc:bla:jfinan:v:55:y:2000:i:4:p:1705-1765)); 5–7%/yr risk-adjusted excess returns mainly in smaller stocks ([Savin, Weller & Zvingelis](https://www.econbiz.de/Record/the-predictive-power-of-head-and-shoulders-price-patterns-in-the-u-s-stock-market/10010638270)); but unprofitable on average per Osler ([CXO Advisory summary](https://www.cxoadvisory.com/?p=987)). No strong crypto-specific study found |
| **Double top / bottom & other classic shapes** | 🟡 **Weak** | Some information content in equities (Lo et al.). Early Bitcoin (Mt.Gox 2011–13): chart-pattern buy signals came with 53%+ abnormal volume and pattern traders earned higher returns, likely because the market was immature and traders herded ([Rink, *Financial Innovation* 2025](https://doaj.org/article/df4659384af94ae49454632aa15fae15)). May not hold in today's bot-dominated market |
| **Triangle breakouts** | 🟢 **Moderate** (via breakout evidence) | Graded as a structure breakout: the evidence comes from trading-range breakout studies above. The triangle *shape* itself has no dedicated crypto study, so the grade applies to the breakout, not to the pattern alone |
| **Flags, wedges** | ⚪ **Unproven** | Widely used, but no rigorous crypto study found in this review |
| **Candlestick patterns** | 🔴 **Mostly no edge** | 68 candlestick patterns across top-23 coins were of little use; many low-accuracy ([EdUHK / IEEE 2021](https://repository.eduhk.hk/en/publications/do-candlestick-patterns-work-in-cryptocurrency-trading/)). A larger study of 41 patterns found only 8 showed potential, and 2 of those moved opposite to their textbook meaning ([Charles University thesis](https://dodo.is.cuni.cz/handle/20.500.11956/197060)) |
| **Support / resistance breakouts** | 🟡 **Weak** | Widely used by practitioners; limited rigorous crypto evidence found. Use as context for stops and targets, not as a stand-alone signal |

### Deep-learning price prediction
Reviews show LSTM/transformer models are popular and multivariate inputs help accuracy ([Wu et al., arXiv 2405.11431](https://arxiv.org/pdf/2405.11431)), but most studies report error metrics (RMSE, MAPE), not trading profit after fees and slippage. **Prediction accuracy is not proof of profitability.**

## 4. Risks, scams & regulation

- **Scams:** at least $14B flowed to crypto scams on-chain in 2025, possibly $17B+ as more wallets are identified. Operations linked to AI vendors averaged about $3.2M each vs ~$719k without, about 4.5× more. Impersonation scams rose ~1,400% ([KnowBe4 on Chainalysis](https://blog.knowbe4.com/report-scammers-stole-17-billion-worth-of-crypto-last-year)). TRM Labs reports 2026 deepfake-scam losses already far above all of 2025 ([CryptoSlate](https://cryptoslate.com/?p=557442)).
- **CFTC:** fraudsters use AI hype to sell bots and signals promising unrealistic or guaranteed returns; AI cannot predict sudden market changes ([CFTC advisory](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/AITradingBots.html)).
- **SEC "AI washing":** first cases in March 2024 against Delphia and Global Predictions ($400k combined penalties), later Rimar Capital, for false claims of AI-driven trading ([InvestmentNews](https://www.investmentnews.com/regulation-and-legislation/another-ai-washing-case-shows-where-sec-is-headed/257668)).
- → **Repo rule:** never claim win rates, returns or "AI-powered profits." Describe what the skill does, and its limits.

## 5. The future of AI trading

- **Agents everywhere, autonomy later.** Infrastructure for agent wallets and on-chain agent identity (ERC-8004, Jan 2026) is live ([Yellow](https://yellow.com/news/ai-agents-humans-trading)), but agents still lose to skilled humans in open-ended trading.
- **Better tooling for LLM traders.** Alpha Arena Season 2 plans web search, longer reasoning, more data and multi-step actions ([ThinkAdvisor / Bloomberg](https://www.thinkadvisor.com/amp/2026/05/06/why-ai-bots-arent-ready-to-replace-your-fund-manager/)).
- **Most likely near-term role: AI as analyst + risk co-pilot, human decides.** This matches the evidence and is exactly where this skill sits.
- **Systemic risk grows with automation:** correlated bots and liquidation engines can amplify crashes (10/10).

## 6. Design rules for the skill (derived from the evidence)

1. **Structure first:** detect pivots and label HH/HL/LH/LL; trend state is the main signal.
2. **Patterns are context, with visible grades:** every drawn pattern carries its evidence badge.
3. **Candlesticks = weak confirmation only,** never a stand-alone trigger.
4. **Pivot snapping by script,** plus a confidence label; ask for a cleaner screenshot when uncertain.
5. **Risk first:** invalidation level, stop, size by % of account, leverage warning.
6. **"NO TRADE" is a first-class output** when structure is unclear or R:R is poor.
7. **No performance claims** anywhere in the repo; clear educational disclaimer.

## Open items
- Look for dedicated studies to confirm the support/resistance grade.
- Look for crypto-specific studies on triangles, flags and wedges.
- Check Alpha Arena Season 2 results when published.
