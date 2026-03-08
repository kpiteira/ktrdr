# Multi-Timeframe Context ("Cortex"): Design

## Status: Design
## Date: 2026-03-07
## Contributors: Karl + Lux

---

## 1. Problem Statement

Standard technical indicators on a single timeframe carry no predictive power for forward returns — our regression experiment proved it. But information at different timescales is partially independent. Daily trends have genuine persistence (momentum factor, well-documented). Hourly mean-reversion within a daily trend is a classic institutional approach.

Previous multi-TF attempts used the same indicator at different scales ("RSI on 5m AND RSI on 1h") — redundant information. The right approach: **different indicators for different purposes across timeframes**. The higher timeframe classifies *direction* (bullish/bearish/neutral context); the lower timeframe generates entry signals filtered by that context.

This is Thread 2 of the adult brain architecture — the "Cortex" that provides multi-timescale reasoning. It extends Thread 1's ensemble with a second gate: regime says *what state the market is in*; context says *which direction the macro flow is going*.

### 1.1 Prerequisites

A blocking bug exists: the backtest pipeline is single-timeframe. Models trained on multiple timeframes fail at backtest with `KeyError` on secondary timeframes. This must be fixed before any multi-TF work can proceed. (See Section 7, Milestone 1.)

---

## 2. What Context Is (and Isn't)

### 2.1 Context vs Regime

Thread 1 (Regime Detection) classifies market *state*: trending, ranging, or volatile. Thread 2 classifies market *direction at a higher timeframe*: bullish, bearish, or neutral.

These are complementary, not overlapping:
- A **trending-up** 1h market can exist within a **bearish daily context** (counter-trend rally) or a **bullish daily context** (trend continuation). These are fundamentally different situations.
- A **ranging** 1h market in a **bullish daily context** suggests buying dips; in a **bearish daily context**, selling rallies.

| | Regime (Thread 1) | Context (Thread 2) |
|---|---|---|
| **Question** | What kind of market is this? | Which direction is the macro flow? |
| **Timescale** | Same as signal (1h) | Higher than signal (1d, 4h) |
| **Output** | trending-up / trending-down / ranging / volatile | bullish / neutral / bearish |
| **Changes** | When market state shifts | When daily bar closes |
| **Update frequency** | Per bar | Per higher-TF bar close |
| **Persistence** | Hours to days | Days to weeks |

### 2.2 What Context Does Not Do

Context does not predict returns. It does not generate signals. It provides **directional bias** that gates or weights the signal model's output. The signal model still does the work — context just tells it which direction to favor.

---

## 3. Key Design Decisions

### D1: Context Model Output — Ternary Soft Probabilities

**Options considered:**
- Binary (bullish/bearish) — too aggressive, no "uncertain" state
- Ternary hard labels (bullish/neutral/bearish) — loses confidence information
- Continuous strength (-1 to +1) — harder to compose with regime router
- **Ternary soft probabilities** — `{bullish: 0.6, neutral: 0.3, bearish: 0.1}`

**Decision:** Ternary soft probabilities. Matches Thread 1's regime output format. Enables nuanced gating (reduce size when context is uncertain, not just binary on/off). Compatible with the multi-gate router extension.

### D2: How Context Gates Signals — Asymmetric Threshold Modifier

**Options considered:**
- **Hard filter** — only trade in context direction. Simple but too aggressive. In neutral context (which could be ~40% of the time), no trades at all.
- **Soft weight** — reduce position size against context. Requires position sizing infrastructure that doesn't exist yet.
- **Asymmetric threshold** — lower the confidence threshold for aligned trades, raise it for counter-trend trades. Context shifts the bar for how confident the signal model must be.

**Decision:** Asymmetric threshold modifier. This is the simplest mechanism that captures the key insight: aligned trades should require less conviction, counter-trend trades should require more. It composes cleanly with the existing `confidence_threshold` in the decisions config.

Implementation:
```
base_threshold = 0.6  (from strategy config)

context = bullish (0.7 confidence):
  long_threshold  = base * (1 - context_strength * aligned_discount)   → 0.48
  short_threshold = base * (1 + context_strength * counter_premium)    → 0.72

context = neutral (0.5 confidence):
  thresholds stay near base → 0.57 / 0.63  (minimal effect)

context = bearish (0.8 confidence):
  long_threshold  = base * (1 + context_strength * counter_premium)    → 0.78
  short_threshold = base * (1 - context_strength * aligned_discount)   → 0.41
```

The `aligned_discount` and `counter_premium` are tunable parameters in the ensemble config.

### D3: Architecture — Second Gate in RegimeRouter (Multi-Gate Extension)

**Options considered:**
- **Context as input to regime model** — daily trend features feed into the regime classifier. Couples the brain regions, defeats modularity.
- **Context as separate model feeding a DAG** — fully modular but complex. Overkill until we have 3+ brain regions.
- **Context as second gate in RegimeRouter** — extends the existing router with an additional gate. Regime selects the signal model; context adjusts the threshold.

**Decision:** Context as second gate in RegimeRouter. This is the natural extension Thread 1's Scenario 6 identified. The router already determines which model to run; context adds *how aggressively* to trade.

Composition flow:
```
RegimeRouter (extended):
  1. Regime model → regime probabilities → select signal model
  2. Context model → context probabilities → compute threshold modifier
  3. Signal model → direction + confidence
  4. Apply modified threshold: is confidence > adjusted_threshold?
  5. Execute or hold
```

This keeps regime and context as independent brain regions with separate models, separate features, separate training. The router is the only place they interact.

### D4: Context Labeling — Forward-Looking Trend Direction

**Decision:** Same principle as Thread 1's regime labeling — labels must use future information.

Context labels use **signed price change over H daily bars**, smoothed:

```
signed_return = (close[T+H] - close[T]) / close[T]

If signed_return > +threshold → BULLISH (0)
If signed_return < -threshold → BEARISH (1)
Else → NEUTRAL (2)
```

Where:
- H = 5 daily bars (one trading week lookahead)
- threshold = tunable (start with 0.5%, ~50 pips for EURUSD)

This is simpler than Thread 1's Signed ER + RV because context doesn't need to distinguish trending from volatile — just direction. The model's job is to predict this from current daily indicators.

### D5: Context Update Frequency — On Daily Bar Close

**Decision:** Context is re-evaluated once per day when the daily bar closes. Between closes, the previous context holds.

This is semantically correct (the daily context hasn't changed mid-day), computationally efficient (one inference per day vs 24 per day), and avoids lookahead bias (no peeking at the incomplete daily bar).

The forward-fill alignment from `MultiTimeframeCoordinator` already handles this: the daily context value is held constant across all hourly bars until the next daily close.

### D6: Relationship with Thread 3 (External Data)

Thread 3's daily/weekly data sources (yield spreads, COT positioning) are natural inputs to the context model. They're inherently daily or lower frequency, perfectly aligned with the context model's timescale.

**Decision:** The context model's indicator set should be designed to accept Thread 3's context data when available. In M2-M3 of this design, the context model uses only price-derived daily indicators (ROC, ADX, RSI, EMA). When Thread 3 ships, yield spreads and positioning data become additional context model inputs — no architectural change needed, just strategy YAML updates.

Thread 3's `context_data` grammar extension handles the data loading; the context model just sees additional indicator columns.

---

## 4. What Already Works

The multi-timeframe feature pipeline is largely complete:

- **Strategy grammar v3** supports `training_data.timeframes` with arbitrary combinations
- **FeatureResolver** expands `nn_inputs` with `timeframes: all` or specific timeframe lists
- **IndicatorEngine** computes indicators per timeframe with prefix columns (`1h_rsi_14`, `1d_roc_20`)
- **FuzzyEngine** generates memberships per timeframe (`1h_rsi_momentum_oversold`, `1d_trend_bullish`)
- **MultiTimeframeCoordinator** loads and aligns data across timeframes (forward-fill)
- **FeatureCache** mirrors the training pipeline for backtesting

---

## 5. What Needs Building

### 5.1 Backtest Multi-TF Plumbing (Prerequisite)

The backtest pipeline is single-timeframe from API to engine. `BacktestStartRequest`, `BacktestConfig`, and engine data loading all use `timeframe: str` (singular). This must be fixed to thread `timeframes: list[str]` through the chain. See Architecture doc Section 2 for details.

### 5.2 Context Labeler

A `ContextLabeler` that generates forward-looking trend direction labels from daily OHLCV data. Analogous to Thread 1's `RegimeLabeler` but simpler — ternary direction classification instead of quad-class state classification.

### 5.3 Context Model Training

Wire `labels.source: context` into the training pipeline. Same pattern as Thread 1's `labels.source: regime` — a new label source that produces 3-class labels (bullish/neutral/bearish).

### 5.4 Multi-Gate Router Extension

Extend Thread 1's `RegimeRouter` to accept an optional second gate (context). The router already selects which model to run; the context gate adds threshold modification. This requires an extension to `EnsembleConfiguration` and `RegimeRouter.route()`.

### 5.5 EnsembleBacktestRunner Extension

The runner needs to evaluate the context model (once per daily bar close) and pass context probabilities to the router alongside regime probabilities.

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Daily context has no predictive power (same as hourly indicators) | Medium | Design is wasted; but labeler + validation catches this in M2 | M2 validation gates further work — if no signal, stop |
| Context and regime are redundant | Low | Simplify to single gate | M2 measures correlation between context and regime labels |
| Multi-gate router adds complexity for marginal value | Medium | Regime alone might suffice | Measure: does adding context improve ensemble performance vs regime-only? |
| Forward-fill creates lookahead in context features | Low | Careful alignment: use previous *completed* daily bar only | MultiTimeframeCoordinator already handles this correctly |

---

## 7. Milestones

### M1: Backtest Multi-TF Plumbing Fix (Prerequisite)

Thread `timeframes: list[str]` through the backtest pipeline. Small, surgical, ~5 files changed.

**E2E test:** Train on `v3_multi_timeframe.yaml` (1h+4h+1d), backtest completes without KeyError.

### M2: Context Labeler & Validation (No ML)

Build `ContextLabeler` using forward-looking signed return over H daily bars. Generate labels for EURUSD 1d.

**Validate:**
- Label distribution: bullish/neutral/bearish roughly balanced (not 90% neutral)
- Context persistence: average duration >3 days (not noise)
- Return distributions differ by context: bullish context → positive mean hourly returns, bearish → negative
- Correlation with Thread 1 regime labels: should be low (complementary, not redundant)

**CLI:** `ktrdr context analyze EURUSD 1d --start-date 2020-01-01 --end-date 2025-01-01`

**Gate:** If context shows no persistence or no return differentiation, stop here. The hypothesis is falsified.

### M3: Context Model Training

Wire `labels.source: context` into training pipeline (3-class cross-entropy). Create seed strategy with daily indicators (ROC, ADX, RSI, EMA).

**Evaluate:**
- Accuracy vs 33% random baseline for 3-class
- Context persistence of predictions (not flipping every bar)
- Does filtering a naive hourly momentum strategy by predicted context improve performance?

### M4: Multi-Gate Ensemble Integration

Extend `EnsembleConfiguration` with optional `context_gate`. Extend `RegimeRouter` to apply context-based threshold modification. Extend `EnsembleBacktestRunner` to evaluate context model per daily bar close.

**E2E test:** Full ensemble backtest with regime + context + per-regime signal models. Compare vs regime-only ensemble from Thread 1.

### M5: Researcher Integration

Make context available to the evolution system:
- Researcher can evolve context model indicators/architecture
- Researcher can evolve aligned_discount/counter_premium parameters
- Assessment evaluates context contribution (does it help vs hurt?)

---

## 8. Open Questions

1. **Optimal context horizon (H):** 5 daily bars (1 week) is our starting point. Shorter horizons may flip too often; longer may be too slow. The Researcher can experiment with this.

2. **Context threshold:** What signed_return value separates bullish/neutral/bearish? Depends on the instrument. For EURUSD, 0.5% (~50 pips) per week seems reasonable. May need to be adaptive.

3. **Should context evaluate on incomplete daily bars?** Current decision is no — wait for daily close. But this means context is always 0-23 hours stale. Alternative: re-evaluate using partial daily bar with reduced confidence. Deferred to M3 experimentation.

4. **Position of context in the router:** Current design has regime select model, context modify threshold. Alternative: context could also influence model selection (e.g., bearish daily context → skip trend_long entirely, even in trending-up regime). More aggressive but worth testing in M4.

5. **EMA slope indicator:** The ideal context feature is "slope of EMA" (is the moving average rising or falling, and how fast?). This doesn't exist as a standalone indicator. The seed strategy uses ROC (Rate of Change) as a proxy for trend direction. A purpose-built `ema_slope` indicator may be worth adding during M3 — it's simple (~50 lines: normalized difference between current EMA and N-bars-ago EMA). Flag for `/kplan` so it doesn't become a surprise.
