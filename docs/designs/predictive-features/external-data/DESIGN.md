# External Data Sources: Multi-Provider Data Pipeline

## Status: Design
## Date: 2026-03-07
## Contributors: Karl + Lux

---

## 1. Problem Statement

KTRDR's neuro-fuzzy architecture works. The regression pipeline works. But standard technical indicators (RSI, MACD, Stochastic, ADX) on EURUSD 1h carry **zero predictive power** for forward returns. A properly trained regression model predicts near-zero for everything — correctly learning that these inputs contain no information about future returns.

The inputs are the problem:
- **Lagging** — derived from past prices, which are public information
- **Universal** — RSI(14) means the same thing to every participant
- **Crowded** — any edge was arbitraged away decades ago
- **Single-asset** — EURUSD doesn't move because RSI hit 30; it moves because of macro flows

Professional FX quant funds trade on three well-documented factors, **none of which our system currently uses**:

| Factor | Sharpe Ratio | What It Captures | Our Status |
|--------|-------------|-------------------|------------|
| **Momentum** | ~0.96 | Trend persistence across currencies | We have price data but don't compute proper momentum factors |
| **Carry** | ~0.61 | Interest rate differential flows | **Nothing — no rate data at all** |
| **Positioning** | Strong at extremes | Crowding / contrarian signals | **Nothing — no positioning data** |

This design addresses the fundamental gap: bringing in the data sources that actually drive FX returns.

---

## 2. Goals

1. **Multi-provider data acquisition** — extend beyond IB to include FRED (economic data), CFTC (positioning), economic calendars, and retail sentiment APIs
2. **Strategy grammar extension** — `context_data` section that declares external data dependencies with provider, frequency, and alignment rules
3. **Mixed-frequency alignment** — daily yields and weekly positioning data aligned to hourly trading bars via forward-fill
4. **Provider abstraction** — clean interface so new data sources can be added without touching core pipeline code
5. **Evolution integration** — the researcher genome can discover which external data sources improve strategies

## 3. Non-Goals

- **Real-time streaming** — all external data is fetched in batch for training/backtesting. Live trading data feeds are a separate concern.
- **Options data** (risk reversals, vol surfaces) — requires commercial data subscriptions. Deferred unless IB provides this cheaply.
- **NLP pipeline for central bank communication** — high potential but complex. Designed as M6 stretch goal, not core scope.
- **Building our own economic surprise index** — requires consensus estimate data we don't have. Use published indices if available.
- **Multi-pair portfolio optimization** — this design provides data for individual pair models. Portfolio-level allocation is a separate system.

---

## 4. Data Source Catalog

### Tier 1: Must Have (proven factors, free data)

#### 4.1 Interest Rate Differentials (Carry Factor)

**What:** Yield spreads between countries whose currencies form a pair. US 2Y minus German 2Y for EURUSD. US 2Y minus UK 2Y for GBPUSD. Etc.

**Why it works:** The strongest fundamental FX driver. When US yields rise relative to German yields, capital flows to USD, EURUSD drops. This relationship has worked for 200+ years of data. Carry is not just a curiosity — it's Sharpe ~0.61 as a standalone factor.

**Data source:** FRED API (Federal Reserve Economic Data)
- Free (requires free API key registration — instant, no approval process)
- Daily data, most series back to the 1960s
- REST API returns CSV/JSON
- Key series: `DGS2` (US 2Y), `DGS10` (US 10Y), `IRLTLT01DEM156N` (German 10Y), `T10Y2Y` (US yield curve slope)

**Feature approach:** Rate of change in the yield spread, not the level. The level changes slowly (meeting to meeting); the *change in rate expectations* moves FX on a daily basis.

**Multi-pair mapping:**

| Pair | Yield Spread | FRED Series |
|------|-------------|-------------|
| EURUSD | US 2Y - DE 2Y | DGS2, IRLTLT01DEM156N (10Y proxy) |
| GBPUSD | US 2Y - UK 2Y | DGS2, UK series TBD |
| USDJPY | US 2Y - JP 2Y | DGS2, JP series TBD |
| USDCHF | US 2Y - CH 2Y | DGS2, CH series TBD |
| AUDUSD | US 2Y - AU 2Y | DGS2, AU series TBD |
| NZDUSD | US 2Y - NZ 2Y | DGS2, NZ series TBD |
| USDCAD | US 2Y - CA 2Y | DGS2, CA series TBD |

#### 4.2 CFTC Commitment of Traders (Positioning Factor)

**What:** Net speculative positioning in currency futures. When speculators are extremely long EUR futures, the trade is crowded and reversal probability rises.

**Why it works:** Well-documented contrarian signal at extremes. Not about predicting direction — about detecting *crowding*. When >90th percentile of historical positioning is long, the fuel for further gains is exhausted.

**Data source:** CFTC public API
- Free, no authentication
- Weekly (Tuesday snapshot, Friday 3:30pm ET release)
- Historical data back to 1986
- Python library `cot_reports` handles download/parsing
- Reports: "Traders in Financial Futures" (TFF) for currency futures

**Feature approach:** Net speculative position as percentile of its 52-week and 3-year history (0-100 scale). Extreme readings (>90th or <10th percentile) are the signal, not the raw position.

**Caveat:** Weekly data. Forward-filled to hourly. Changes slowly — this is a regime-level feature, not a timing signal.

#### 4.3 Cross-Pair Context

**What:** Other major FX pairs provide context for decomposing moves into currency-specific vs broad USD moves.

**Why it works:** If EURUSD is up and GBPUSD is flat, that's EUR strength (potentially mean-reverting). If ALL USD pairs are moving together, that's a USD macro event (potentially persistent). A single-pair model can't distinguish these.

**Data source:** IB (already available, no new infrastructure)

**Feature approach:**
- USD basket: mean of all USD pair returns (isolates USD component)
- Pair deviation from basket: is this move currency-specific or broad?
- Cross-pair momentum divergence: when correlated pairs diverge, mean-reversion pressure builds

### Tier 2: High Value, Moderate Effort

#### 4.4 Economic Calendar Events

**What:** Scheduled high-impact releases (NFP, CPI, FOMC, ECB) with timing and expected impact level.

**Why it works:** Not for predicting event outcomes — for predicting **volatility regime around events**. Vol expansion before major releases is systematic and predictable. Most losing trades in systematic FX happen when models get steamrolled by scheduled news they didn't know about.

**Data source:** Finnhub API (free tier: 60 calls/min) or similar calendar API

**Feature approach:**
- `hours_until_next_high_impact_event` — continuous countdown feature
- `is_event_day` — binary flag for the affected currency
- `last_surprise_direction` — did the most recent release beat or miss expectations?
- These are regime/gating features: when to step aside, not when to enter

#### 4.5 Retail Sentiment (Contrarian Signal)

**What:** Long/short ratio of retail traders at major brokers. When 80%+ of retail is positioned one way, the market tends to go the other way.

**Why it works:** Retail traders are systematically wrong at extremes. This is documented across multiple brokers and time periods.

**Data source:** Myfxbook API (free: 100 req/day), OANDA order book

**Feature approach:** Retail long ratio as percentile. Extreme readings (>80% or <20%) are contrarian signals.

**Caveat:** Real-time snapshots available; historical data for backtesting is limited. May need to start collecting now and train on shorter history initially.

### Tier 3: Stretch Goals

#### 4.6 Central Bank Communication via LLM

**What:** Process Fed/ECB speeches and minutes through Claude to extract hawkish/dovish sentiment scores.

**Why it works:** IMF research (June 2025) validates LLM analysis across 169 central banks and 74,882 documents. Central bank language IS the policy signal — markets move on wording changes. We have Claude, which gives us a genuine capability advantage over most systematic funds.

**Data source:** Fed/ECB websites (free, published on schedule)

**Feature approach:** Hawkish/dovish score (continuous), delta from previous communication, surprise relative to prior messaging.

**Deferred because:** Requires building an NLP ingestion pipeline, determining scoring methodology, and validating against historical communications. High potential but significant implementation scope.

---

## 5. Key Design Decisions

### D1: Separate `context_data` section (not extending `training_data.symbols`)

**Decision:** `context_data` is a new top-level section in the strategy grammar, peer to `training_data`.

**Why:** Clean separation between "what we trade" and "what we observe." Context data has properties that trading data doesn't: different providers, frequencies, alignment rules, instrument types. Mixing them into `training_data.symbols` would complicate validation and data loading.

**Trade-off:** Slightly more YAML. Acceptable because the agent generates YAML anyway.

### D2: Provider-based data acquisition (not IB-only)

**Decision:** Context data entries specify a `provider` field. Each provider (IB, FRED, CFTC, etc.) implements a common interface for fetching and caching data.

**Why:** Interest rate data comes from FRED, positioning from CFTC, prices from IB. These have fundamentally different APIs, frequencies, and access patterns. A single abstraction with provider-specific implementations is the natural pattern.

**Trade-off:** More infrastructure than "just add more IB symbols." But without this, we can't access the data sources that actually matter.

### D3: Forward-fill for alignment (not dropping rows or NaN)

**Decision:** When context data has lower frequency than primary data (daily yields → hourly bars), forward-fill the last known value.

**Why:**
- Dropping rows would lose ~2/3 of data (daily data → 16 hours/day of gaps in hourly bars)
- NaN propagation means context features are absent most of the time, defeating the purpose
- Forward-fill is semantically correct: yesterday's yield close IS the current yield until the market updates it

**Applied at data level:** Forward-fill happens on raw OHLCV/values before indicator computation. Indicators on forward-filled data naturally plateau during gaps (correct behavior — RSI shouldn't change if price doesn't change).

### D4: `data_source` field on indicators (not separate indicator sections)

**Decision:** Indicators reference context data via a `data_source` field. Omitting `data_source` means "primary traded instrument" (backward compatible).

**Important naming note:** The field is `data_source`, NOT `source`. The existing `IndicatorDefinition` uses `model_config = {"extra": "allow"}` and some indicators already use `source` as a parameter (e.g., RSI has `source: close` to specify which OHLCV column). Using `source` for context data would collide with these existing parameters.

**Why:** Minimal grammar change. Fuzzy sets and nn_inputs don't need to know about data sources — they just reference indicator IDs. The `data_source` field is resolved during data loading and feature computation.

### D5: Defer cross-asset computed features (spreads, correlations)

**Decision:** Start with standard indicators computed on context data independently. Don't build two-input indicators (EURUSD/DXY spread, rolling correlation) in M1-M2.

**Why:** If you run RSI on EURUSD and RSI on DXY separately, the neural network receives both fuzzy memberships and can learn the relationship itself. We have 6+ years of hourly data — enough for the model to discover cross-asset relationships. Explicit cross-asset features are a natural extension if needed, but start simple.

**Revisit when:** Training shows the model can't learn cross-asset relationships from independent indicator features. Then add synthetic series (USD basket, pair deviation) as a computed preprocessing step.

### D6: Start with FRED + cross-pair, not IB exotics

**Decision:** M1 implements the FRED provider (yield data), not more IB symbols like DXY or SPY.

**Why:** DXY is ~57% correlated with EURUSD (nearly redundant). SPY is contemporaneously correlated, not predictive at hourly scale. Interest rate differentials are the strongest fundamental FX driver and the data is free. Starting with FRED proves the multi-provider architecture on the most valuable data source.

---

## 6. User Scenarios

### S1: Researcher designs a carry-aware strategy

The design agent, aware that yield spread data is available, creates a strategy that:
- Computes RSI on the US-DE yield spread to detect rate momentum
- Uses fuzzy sets: "yield_spread_widening" (USD strengthening), "yield_spread_narrowing" (EUR strengthening)
- Combines with EURUSD price momentum for entry timing
- Only takes trades aligned with the carry direction

### S2: Model avoids event-driven losses

A strategy with economic calendar context:
- Feature: `hours_until_next_high_impact_usd_event`
- Fuzzy set: "pre_event" (0-4 hours before), "normal" (>4 hours)
- The model learns to suppress trades in the pre-event window
- Result: fewer trades, but far fewer "event steamroll" losses

### S3: Evolution discovers positioning as edge

The researcher agent runs multiple generations:
- Generation 1-3: tries different indicator combinations (no improvement)
- Generation 4: assessment agent notes "capability_request: positioning data could help detect crowded trades"
- Generation 5+: genome enables COT positioning features
- A researcher discovers that filtering trades by COT extremes improves Sharpe by 0.15

### S4: Multi-pair training with shared context

A strategy for GBPUSD that uses:
- GBPUSD price indicators (primary)
- EURUSD as cross-pair context (via IB)
- US-UK yield spread (via FRED)
- GBP COT positioning (via CFTC)
- Each data source from its natural provider, aligned to 1h bars

---

## 7. Connection to Evolution Framework

This design maps to the Adult Brain competency lattice:

| Competency | How External Data Enables It |
|---|---|
| "Cross-domain signal fusion" | Carry + momentum + positioning = three independent information domains |
| "Multi-timescale reasoning" | Daily yields + weekly positioning + hourly prices = three timescales |
| "Context-aware decision policies" | Event calendar enables regime-conditional behavior |
| "Persistent specialized regions" | Each data source can feed a specialized model head (Thread 1 interaction) |

The capability request mechanism already exists in the assessment agent. External data sources become *unlockable capabilities* — the agent identifies what it needs, the system makes it available.

---

## 8. Milestone Structure

### M1: Multi-Provider Data Framework + FRED
- Strategy grammar `context_data` extension
- `data_source` field on `IndicatorDefinition`
- Abstract data provider interface
- FRED provider implementation
- Forward-fill alignment for mixed-frequency data
- Strategy validation: `data_source` values must exist in `context_data`
- **E2E:** Define strategy with FRED yield spread context, load data, compute indicators

### M2: Cross-Pair Context + Feature Resolution
- IB context symbols (sibling forex pairs)
- FeatureResolver handles source-prefixed indicators
- IndicatorEngine computes on context DataFrames
- TrainingPipeline passes context data through feature computation
- **E2E:** Train a model with cross-pair + yield spread features

### M3: CFTC Positioning Data
- CFTC COT provider (weekly data)
- COT percentile computation as preprocessing
- Weekly → hourly forward-fill alignment
- **E2E:** Train a model with carry + cross-pair + positioning features

### M4: Economic Calendar + Event Regime
- Calendar provider (Finnhub or similar)
- Event proximity features
- Event regime classification
- **E2E:** Model that reduces activity around high-impact events

### M5: Backtest + Evolution Integration
- Backtest engine loads all context data from model bundle
- Model bundle stores context data requirements
- Evolution genome includes data source selection
- Design agent prompt updated with available data sources
- **E2E:** Full evolution run with multi-source data

### M6: Central Bank NLP (Stretch)
- Fed/ECB speech ingestion pipeline
- LLM-based hawkish/dovish scoring
- Sentiment delta features
- **E2E:** Model includes central bank sentiment features

---

## 9. Open Questions

1. **FRED data granularity:** 2Y yields are the theoretical ideal for carry, but FRED's German/UK/JP 2Y series may be limited. 10Y yields are readily available for all countries. Is 10Y an acceptable proxy? (Probably yes — the spread dynamics are similar.)

2. **COT data lag:** 3-day lag (Tuesday snapshot, Friday release). Is this acceptable for a weekly feature that changes slowly? (Probably yes — positioning extremes persist for weeks, not days.)

3. **Retail sentiment history:** Myfxbook/OANDA don't offer historical downloads. We'd need to start collecting now and train on shorter history. Is 6-12 months enough for the model to learn contrarian patterns? Or defer until we have 2+ years?

4. **Thread 1 interaction:** Multi-network architecture may want different context data for different model heads (regime model vs signal model). The grammar should support this but we don't need to design for it now — Thread 1 owns that concern.

5. **Provider failure handling:** FRED goes down, CFTC delays release. Strategy depends on context data that's temporarily unavailable. Forward-fill with staleness warning? Or fail loudly? (Recommend: forward-fill with staleness metadata, fail only if data has never been fetched.)

6. **Backtesting with external data:** FRED/CFTC data is point-in-time (no revisions for yields, some revisions for COT). But economic calendar "surprise" values require knowing the consensus estimate *at the time*. This is lookahead-sensitive. How do we handle this? (Recommend: use only features that don't require consensus estimates in M1-M4. Calendar features use timing only, not surprise direction.)
