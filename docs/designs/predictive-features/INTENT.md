# Predictive Features: Beyond Standard Indicators

## Status: Intent (pre-design exploration)
## Date: 2026-03-07
## Contributors: Karl + Lux

---

## 1. What We Learned

### 1.1 The Experiment

We built a forward-return regression strategy (`momentum_regime_regression_v3`) that predicts `(close[t+20] - close[t]) / close[t]` using fuzzy memberships of standard indicators (RSI, MACD, Stochastic, ADX) on EURUSD 1h. The model only trades when the predicted return exceeds a cost threshold of 0.45%.

### 1.2 The Result

The model produced **1 trade in 6.5 years** of backtesting (2019–2025). Its predictions clustered around zero:

```
Mean: 0.00057   Std: 0.00012   Range: [-0.001, +0.002]
Predictions exceeding ±0.0045 trade threshold: 0/1000
```

### 1.3 What This Means

The model correctly learned that **the best prediction is approximately zero**. Standard technical indicators on EURUSD 1h carry no information about 20-bar forward returns. They are:

- **Lagging** — derived from past prices, which are public information
- **Universal** — RSI(14) means the same thing to every participant
- **Crowded** — any edge was arbitraged away long ago
- **Single-asset** — EURUSD doesn't move because RSI hit 30; it moves because of macro flows

The neuro-fuzzy architecture works. The regression pipeline works. **The inputs are the problem.**

---

## 2. The Fundamental Problem

### 2.1 Information Content

For a model to predict returns, it needs inputs that contain information about future returns that isn't already reflected in current price. Standard technical indicators fail this test because:

1. **They're lagging** — computed from past prices, which are public information
2. **They're universal** — RSI(14) means the same thing to every market participant
3. **They're crowded** — any edge they once had was competed away decades ago
4. **They're single-asset** — EURUSD doesn't move because RSI hit 30; it moves because of macro flows

### 2.2 What Does Have Information Content?

Features that might predict returns share characteristics:
- **Not universally watched** — fewer participants trade on them
- **Cross-domain** — combine information from different markets
- **Structural** — capture market microstructure, not just price patterns
- **Temporal** — exploit regime persistence or calendar effects
- **Latency** — information that takes time to propagate across markets

### 2.3 Cost Floor Reality

From our earlier analysis (memory): strategies need ~33 pip edge per trade to survive 0.3% round-trip costs. Current models capture ~1 pip pre-cost edge. Any viable features must predict returns that exceed this floor, or we need to trade much less frequently on higher-conviction signals.

---

## 3. Three Paths Forward

These are complementary threads that build toward the "adult brain with specialized regions" from the evolution framework (`docs/agentic/evolution/neural_system_maturity_evolution_framework.md`). They can be explored in parallel.

### 3.1 Thread 1: Regime Detection ("Reptilian Brain")

**The idea:** Don't predict direction. Predict the market's *state*. Is it trending, ranging, or in crisis? Then use the regime label to gate which trading logic applies.

**Why this might work:**
- Regime persistence is well-documented in finance literature
- Volatility clusters (GARCH effect) — high-vol periods follow high-vol periods
- This is a classification problem with stronger signal than return prediction
- The model doesn't need to predict *when* regimes change, just *what regime we're in now*

**Candidate features:**
- ATR ratio (short-term / long-term) — expanding vs contracting volatility
- ADX level (already have this, but as a regime label, not a trade signal)
- Bollinger bandwidth — squeeze detection
- Realized volatility vs historical average
- Range-to-body ratio of recent candles (directional conviction)

**How it composes:**
- Regime model outputs: `{trending: 0.8, ranging: 0.15, volatile: 0.05}`
- Trading model sees regime as *context*, not input to predict returns directly
- In trend regime: trust momentum signals, larger position sizes
- In range regime: trust mean-reversion signals, tighter stops
- In volatile regime: reduce exposure or stay flat

**Architecture implications:**
- Two separate models (or model heads): regime classifier + conditional signal generator
- This is the first "brain region" — a specialized module with a specific job
- Maps to Adult Competency: "Persistent specialized regions (emergent, not hard-coded)"

**Validation approach:**
- Train regime classifier on labeled data (can use unsupervised clustering of realized vol / trend strength to generate labels)
- Measure regime persistence (if labels flip every bar, it's useless)
- Test: does a simple momentum strategy outperform when filtered by "trending" regime vs unfiltered?

### 3.2 Thread 2: Multi-Timeframe Context ("Cortex")

**The idea:** Use daily timeframe for strategic direction, hourly for tactical entry. The daily model says "macro trend is up" — the hourly model only takes long entries.

**Why this might work:**
- Information at different timescales is partially independent
- Daily trends have genuine persistence (momentum factor)
- Hourly mean-reversion within a daily trend is a classic institutional approach
- We already support multi-timeframe in the strategy grammar but never used it properly

**What we tried before vs what's different:**
- Previous multi-TF attempts used "RSI on 5m AND RSI on 1h" — same signal, different scale. Useless.
- The right approach: daily indicators for *trend direction and strength*, hourly indicators for *entry timing*
- The higher timeframe is a *filter*, not an additional predictor

**Candidate approach:**
- Daily: EMA slope direction, ADX trend strength → "bullish context / bearish context / no context"
- Hourly: RSI oversold/overbought, Stochastic → entry signals, but only in the direction allowed by daily context
- The daily context changes slowly (maybe once per week), making it much more predictable

**Architecture implications:**
- Multi-timeframe data is already loaded but single-TF backtest bug exists (KeyError: '5m' — known issue from earlier work)
- Need to fix multi-TF data flow in backtest worker before this thread can proceed
- Maps to Adult Competency: "Multi-timescale reasoning"

### 3.3 Thread 3: External Data Sources ("Sensory Expansion")

**The idea:** Bring in data that isn't derived from EURUSD OHLCV. Cross-asset signals are the least arbitraged because most retail systems don't look at them.

**Why this might work:**
- EURUSD is fundamentally driven by EUR-USD interest rate differential, European vs US equity performance, and global risk appetite
- These drivers are observable in other instruments
- Information propagation across markets takes time (minutes to hours), creating exploitable lag
- Academic literature strongly supports cross-asset momentum and carry factors

**Candidate data sources (ordered by implementation difficulty):**

**Easy (available through IB):**
- US Dollar Index (DXY) — overall dollar strength
- EUR/GBP, GBP/USD — triangular relationships, divergences = mean-reversion
- S&P 500 / DAX futures — risk appetite proxy
- Gold — safe haven / dollar inverse

**Medium (available through IB with some work):**
- US 2Y/10Y Treasury yields — rate expectations
- VIX — implied volatility / fear gauge
- Crude oil — trade balance implications

**Hard (external APIs needed):**
- Fed funds futures — direct rate expectation
- CFTC COT data (Commitments of Traders) — positioning data, weekly
- Economic calendar events — known volatility catalysts

**Architecture implications:**
- Data acquisition layer needs to support multiple symbols for a single strategy
- Feature engineering: compute cross-asset features (ratios, spreads, correlations)
- The strategy grammar needs to support "external context" inputs beyond the primary traded instrument
- Maps to Adult Competency: "Cross-domain signal fusion (price, structure, external data)"

---

## 4. How These Threads Compose: The Adult Brain

The three threads aren't independent features — they're components of a modular decision system:

```
                    ┌──────────────────────────────┐
                    │      Decision Layer           │
                    │  Regime-conditional logic:    │
                    │  IF trending AND bullish      │
                    │    context AND buy signal     │
                    │  THEN buy with sizing X       │
                    └─────────┬────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              │               │                   │
    ┌─────────┴────┐  ┌──────┴──────┐  ┌─────────┴─────────┐
    │ Regime Brain │  │ Context     │  │ Signal Brain       │
    │ (Thread 1)   │  │ Brain       │  │ (Thread 3 feeds    │
    │              │  │ (Thread 2)  │  │  Thread 1+2)       │
    │ "What state  │  │ "What's the │  │ "Cross-asset       │
    │  is the      │  │  higher-TF  │  │  signals suggest   │
    │  market in?" │  │  trend?"    │  │  what?"            │
    └──────────────┘  └─────────────┘  └───────────────────┘
         │                  │                    │
    ATR ratio          Daily EMA          DXY momentum
    Bollinger BW       Daily ADX          Yield spread
    Realized vol       Weekly trend       VIX level
    Candle structure                      Cross-pair divergence
```

Each "brain region" is a specialized model with its own inputs, outputs, and evaluation criteria. The decision layer combines their outputs using regime-conditional logic — not a single monolithic neural network.

This matches the evolution framework's Adult stage:
- "Persistent specialized regions (emergent, not hard-coded)"
- "Multi-timescale reasoning"
- "Context-aware decision policies"
- "Cross-domain signal fusion"

---

## 5. Connection to Evolution Framework

### 5.1 Where We Are Now

The system is **pre-Baby** by the competency lattice definition. It cannot:
- "Distinguish signal from pure noise better than chance" (Foundational #1)
- "React differently to different input regimes" (Foundational #3)

This isn't because the architecture is wrong — it's because the inputs carry no information.

### 5.2 What Gets Us to Baby

**Baby** requires: "Distinguish signal from pure noise better than chance."

Thread 1 (Regime Detection) is the fastest path here. If we can build a regime classifier that predicts trending/ranging with >60% accuracy and demonstrates regime persistence >24 hours, we have a signal. Even if we can't trade on it profitably yet, the system can "distinguish signal from noise."

### 5.3 What Gets Us to Toddler

**Toddler** requires: "Exhibit regime sensitivity (behavior changes with conditions)" and "Delay or suppress action when confidence is low."

This is exactly what the regime-gated architecture does: different behavior in trending vs ranging markets, and suppression of trades in uncertain regimes.

### 5.4 How the Genome Evolves

Currently, the researcher genome mutates indicators and parameters. These threads expand the genome's vocabulary:

| Current Genome Dimensions | New Dimensions |
|---|---|
| Which indicators | Which asset classes to observe |
| Indicator parameters | Which regime to specialize for |
| Fuzzy set shapes | How to combine multi-TF signals |
| NN architecture | Which brain regions to activate |
| Output format (classification/regression) | What to predict (direction/regime/volatility) |

The researcher agent could discover "I should look at DXY when trading EURUSD" — but only if cross-asset data is available as a capability. This is the "capability request" mechanism from the evolution framework: the agent identifies what it needs, and we (or the system) make it available.

---

## 6. Proposed Exploration Plan

### Phase 1: Prove Signal Exists (both threads in parallel)

**Thread 1 (Regime Detection):**
- Build regime labels from historical data (unsupervised: cluster on {ATR ratio, ADX, Bollinger BW})
- Train regime classifier
- Measure: regime persistence, transition predictability
- Test: does filtering trades by regime improve a naive momentum strategy?

**Thread 3 (External Data):**
- Fetch DXY, S&P 500, gold data through IB (same infrastructure)
- Compute cross-asset features (spreads, ratios, rolling correlations)
- Measure: correlation of cross-asset features with EURUSD forward returns
- Test: do cross-asset features improve return prediction vs price-only features?

### Phase 2: Build First Brain Region

Take whichever thread shows stronger signal and build it as a modular component:
- Separate model with defined inputs/outputs
- Integration point with the existing decision pipeline
- Backtest with the regime-gated or cross-asset-informed approach

### Phase 3: Multi-Timeframe Integration

Once we have a working brain region, add multi-TF context:
- Fix the existing multi-TF backtest bug (KeyError on secondary timeframe)
- Build daily context model
- Combine: daily trend + regime + signal → decision

### Phase 4: Integrate with Evolution System

Make the new capabilities available to the researcher genome:
- Add regime detection as an available "capability" the agent can request/use
- Add cross-asset inputs as genome dimensions
- Let evolution discover how to combine them

---

## 7. Technical Prerequisites

### Already Working
- Forward-return regression (model_trainer, mlp, decision_function, host service — all fixed)
- Strategy grammar v3 with fuzzy inputs
- Multi-timeframe strategy definition (grammar supports it)
- IB data acquisition for multiple symbols

### Needs Fixing
- Multi-timeframe backtest data flow (KeyError: '5m' bug — backtest worker only receives primary timeframe)
- Host service orchestrator needs to stay in sync with LocalTrainingOrchestrator (today's bug)

### Needs Building
- Cross-asset data loading in strategy context (currently assumes single traded instrument)
- Regime labeling pipeline (unsupervised clustering → training labels)
- Multi-model composition in decision pipeline (regime model + signal model)
- Strategy grammar extension for external context inputs

---

## 8. Open Questions

1. **Should regime detection be a separate model or a model head?** Separate model is more modular but adds inference latency. A shared backbone with multiple heads is more efficient but couples the training.

2. **How do we label regimes?** Unsupervised clustering is objective but may not align with tradeable regimes. Human-labeled regimes are subjective but actionable. Hidden Markov Models are a middle ground.

3. **Which external data sources give the most bang for the buck?** DXY is easiest (single instrument, high correlation with EURUSD). Rate differentials are most theoretically grounded. VIX is most regime-informative.

4. **Should the evolution system discover these features, or should we hand-build them?** The vision says "capabilities emerge from agent needs" — but the agent can't discover cross-asset signals if the data isn't available. We need to provide the capability; the agent discovers how to use it.

5. **Timeframe for the regime model**: should it predict "current regime" or "regime over the next N hours"? Current regime is easier but less useful for trading decisions.
