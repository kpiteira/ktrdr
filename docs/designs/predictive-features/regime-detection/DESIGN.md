# Regime Detection — Design Document

## Status: Draft
## Date: 2026-03-07
## Contributors: Karl + Lux

---

## 1. Problem Statement

KTRDR's models treat all market conditions identically. A properly trained regression model on standard indicators (RSI, MACD, Stochastic, ADX) predicts near-zero returns for everything — correctly identifying that these inputs carry no information about future returns.

But market *state* is different from market *direction*. Volatility clusters. Trends persist. Ranges resolve. These are well-documented phenomena with genuinely stronger signal than return prediction. The system can't exploit this because it has no concept of regime — it's a single monolithic model that applies the same logic to trending markets, choppy ranges, and volatility crises.

**We're building:** A regime detection module — a specialized classifier that identifies market state (trending / ranging / volatile) from current indicators. This becomes a gate for trading logic: trust momentum in trends, mean-reversion in ranges, stay flat in crises.

**This is the first "brain region"** in the adult architecture from the evolution framework — a modular component with a specific job, clean inputs/outputs, and independent training.

---

## 2. Goals

1. **Classify market regime** into 4 states: trending-up, trending-down, ranging, volatile/crisis
2. **Demonstrate regime persistence** — detected regimes last >24 hours on average (not noise)
3. **Show measurably different return distributions** across detected regimes
4. **Route to specialized strategies** — each regime dispatches to a signal model optimized for that market state (trend-following in trends, mean-reversion in ranges, flat in crises)
5. **Establish the multi-model ensemble pattern** — clean architecture for composing N independent models with typed outputs, where the Researcher agent discovers the best strategy for each regime

## 3. Non-Goals

- Predicting *when* regime transitions occur (we predict *current* state, not future state)
- Building direction/signal models (that's the existing pipeline, unchanged)
- Replacing the existing training/backtesting infrastructure (we build on top)
- Multi-timeframe regime detection (single timeframe first, compose later)
- External data sources (Thread 3 from INTENT.md — separate design)

---

## 4. Key Decisions

### 4.1 Regime Labeling: Forward-Looking (Crystal Ball)

**Decision:** Use forward-looking labels, like zigzag labeling does for direction.

**Why:** A labeler using current ADX to define "trending" is circular — you'd train a model to predict what you can already compute from the same indicators. Training labels must use future information to define "what regime was this, in hindsight?"

**Method: Efficiency Ratio + Realized Volatility**

For each bar at time T, look at the next H bars (horizon, e.g., H=24 for 1h data):

1. **Signed Efficiency Ratio (SER)**
   ```
   SER = (close[T+H] - close[T]) / Σ|close[t+1] - close[t]| for t in [T, T+H)
   ```
   - SER ≈ +1.0: price moved up in a straight line → trending up
   - SER ≈ -1.0: price moved down in a straight line → trending down
   - SER ≈ 0.0: price went nowhere despite lots of movement → ranging

2. **Realized Volatility (RV)**
   ```
   RV = std(bar-to-bar returns) over [T, T+H]
   RV_ratio = RV / rolling_mean(RV, lookback=120)
   ```
   - RV_ratio > 2.0: extreme volatility → volatile/crisis regime

3. **Label Assignment**
   ```
   if RV_ratio > vol_crisis_threshold:    → VOLATILE     (3)
   elif SER > +trending_threshold:        → TRENDING_UP   (0)
   elif SER < -trending_threshold:        → TRENDING_DOWN (1)
   else:                                  → RANGING       (2)
   ```

**Thresholds** (initial, tunable):
- `vol_crisis_threshold`: 2.0 (2× historical average volatility)
- `trending_threshold`: 0.5 (at least 50% efficient price movement)
- `horizon`: 24 bars (1 day on 1h timeframe)
- `vol_lookback`: 120 bars (5 days on 1h, for rolling average)

**What makes this honest:** Like zigzag, these labels cheat — they know the future. The model's job is to predict these labels from current information only. The model can only succeed if current indicators contain information about forward regime state.

### 4.2 Integration: Regime Router + Per-Regime Signal Models (A+C)

**Decision:** Build the regime classifier as a fully independent model. It acts as a *router*, not just a gate — each regime dispatches to a different signal model specialized for that market state.

**Why:** Different regimes require fundamentally different trading strategies. A trend-following model should hold positions longer and ride momentum. A mean-reversion model should trade faster within range bounds. A single signal model gated by regime is still one strategy trying to work everywhere — that's not the revolution we need.

**What this means:**
- 1 regime classifier + N signal models (one per active regime), each independently trained
- The ensemble is a *dispatch table*: regime → which signal model to run
- New ensemble configuration and EnsembleBacktestRunner for multi-model orchestration
- The Researcher agent discovers the best signal strategy for each regime independently

### 4.3 Ensemble Pattern: Model-Count Agnostic

**Decision:** Design the multi-model composition layer to support N models, not just 2.

**Why:** The adult brain architecture envisions multiple brain regions (regime, multi-TF context, cross-asset signals). Hardcoding "regime + signal" would require rework when we add the third model.

**Pattern:**
```yaml
# ensemble.yaml — defines how models compose
name: regime_routed_v1
models:
  regime:         regime_classifier_v1        # the router
  trend_long:     trend_follower_long_v1      # specialized for uptrends
  trend_short:    trend_follower_short_v1     # specialized for downtrends
  mean_reversion: range_trader_v1             # specialized for ranging markets

composition:
  type: regime_route
  gate_model: regime
  rules:
    trending_up:   { model: trend_long }
    trending_down: { model: trend_short }
    ranging:       { model: mean_reversion }
    volatile:      { action: FLAT }
  on_regime_transition: close_and_switch    # close outgoing model's position, hand to incoming
```

Each model is a standard ModelBundle with typed output. The ensemble config defines routing rules. Adding a new brain region or signal model = one more entry in models + rules.

### 4.4 Regime Model Input Features: Seed Strategy + Researcher Evolution

**Decision:** Ship a seed regime strategy as a sensible starting point, but treat it as a regular v3 strategy YAML that the Researcher can evolve — not hard-coded infrastructure.

**The seed strategy** uses volatility and trend-strength indicators (ATR short/long, BB width, ADX, squeeze intensity) because they're the obvious candidates for regime detection. But these are not baked into the architecture — they're in a strategy file that the Researcher can mutate, replace, or generate alternatives to.

**What we provide (infrastructure — hard to change):**
- The regime labeling method (forward-looking signed ER + RV)
- The ensemble infrastructure (config, runner, router)
- All existing indicators as available building blocks
- The v3 strategy grammar for declaring any combination
- A seed strategy YAML as a starting point

**What the Researcher evolves (strategy — easy to change):**
- Which indicators predict regime from current information
- Which fuzzy set shapes capture regime-relevant signal
- Which NN architecture classifies regime best
- Which signal strategies work best in each regime
- Optimal labeling thresholds (horizon, trending threshold, vol threshold)

### 4.5 Output Format

**Decision:** Regime classifier outputs soft probabilities, not hard labels.

```python
RegimeOutput = {
    "trending_up": 0.65,
    "trending_down": 0.10,
    "ranging": 0.20,
    "volatile": 0.05
}
```

**Why:** Soft probabilities enable nuanced routing — e.g., reduce position size when regime confidence is low, rather than binary on/off. The decision gate applies thresholds; the model produces continuous values.

---

## 5. User Scenarios

### 5.1 Training a Regime Classifier

```bash
# 1. Strategy YAML defines regime-specific indicators and label config
# 2. Train like any other model
uv run ktrdr models train strategies/regime_classifier_v1.yaml EURUSD 1h \
  --start-date 2019-01-01 --end-date 2024-01-01

# Output: model bundle at models/regime_classifier_v1/
```

The training pipeline uses the forward-looking labeler to generate regime labels, then trains a standard MLP classification model.

### 5.2 Backtesting with Regime-Routed Ensemble

```bash
# Backtest uses ensemble config that references regime + per-regime signal models
uv run ktrdr backtest ensemble ensembles/regime_routed_v1.yaml \
  --start-date 2024-01-01 --end-date 2025-03-01
```

The ensemble backtest loads all models, runs regime classification at each bar, routes to the appropriate signal model, and handles position transitions when regime changes.

### 5.3 Validating Regime Quality

```bash
# Analyze regime label distribution and persistence
uv run ktrdr regime analyze EURUSD 1h \
  --start-date 2019-01-01 --end-date 2024-01-01

# Output:
# Regime distribution: trending_up=22%, trending_down=20%, ranging=45%, volatile=13%
# Mean duration: trending_up=29h, trending_down=27h, ranging=28h, volatile=8h
# Forward return by regime: trending_up=+0.18%, trending_down=-0.15%, ranging=-0.01%, volatile=-0.08%
```

### 5.4 Researcher Agent Using Regime Detection

The researcher agent can:
- Generate regime classifier strategies (discovering which indicators best predict regime)
- Generate per-regime signal strategies (optimized for each market state)
- Generate ensemble configs that combine regime + specialized signal models
- Evaluate whether regime routing improves vs. a single unrouted strategy
- Iterate: improve the regime classifier, improve individual signal models, or try new ensemble compositions

---

## 6. What Needs Building

### New Components
1. **RegimeLabeler** — forward-looking regime label generator (signed ER + RV method, 4-class)
2. **Ensemble configuration format** — YAML defining model routing and composition
3. **EnsembleBacktestRunner** — multi-model backtest orchestration with per-regime dispatch
4. **RegimeRouter** — routes to per-regime signal models, handles regime transitions
5. **Regime analysis CLI** — label distribution, persistence, return-by-regime stats

### Extensions to Existing Components
1. **Training pipeline** — support `labels.source: regime` (new labeler, 4-class)
2. **ModelBundle** — tag output type so ensemble runner knows what each model produces

### No Changes Needed
- IndicatorEngine (all needed indicators exist)
- FuzzyEngine (works as-is)
- FeatureResolver (works as-is)
- Single-model BacktestingEngine (preserved, ensemble builds on top)

---

## 7. Open Questions

1. **Horizon sensitivity:** How sensitive are regime labels to the forward horizon (H=24 vs H=48 vs H=12)? Need to test empirically in M1. Shorter horizons → noisier labels, longer → more lag.

2. **Regime transition cost:** When regime switches (e.g., trending_up → ranging), we close the outgoing model's position and hand control to the incoming model. If transitions are frequent, closing costs add up. M1 label analysis will reveal transition frequency — if transitions happen every few hours, the close-and-switch model may be too expensive.

3. **Per-regime training data:** Should signal models be trained on *all* data or only on bars labeled as their regime? Training a trend-follower only on trending bars gives it a focused dataset, but much less data. Training on all data but with regime-aware labels is another approach. The Researcher should experiment with both.

4. **Ensemble config ownership:** Does the ensemble config live alongside strategies, or is it a separate concept? Decision: `ensembles/` directory parallel to `strategies/`.

---

## 8. Milestone Structure

### M1: Regime Labeling & Validation (no ML)
Build the forward-looking labeler (signed ER + RV, 4 classes). Generate labels for EURUSD 1h. Validate: regime persistence, distinct return distributions, transition frequency. CLI command for analysis. No model training yet — just prove regimes exist and matter.

**E2E test:** Generate regime labels for EURUSD 1h 2019-2024, verify 4-class distribution is reasonable, verify mean regime duration >24h, verify return distributions differ by regime.

### M2: Regime Classifier Training
Wire `labels.source: regime` into training pipeline. Train regime classifier on EURUSD 1h using the labeler from M1. Evaluate: classification accuracy vs. majority-class baseline, confusion matrix, regime prediction persistence.

**E2E test:** Train regime classifier, load model bundle, run inference on held-out data, verify accuracy >30% (better than random baseline of 25% for 4-class uniform).

### M3: Ensemble Architecture
Build ensemble config format, EnsembleBacktestRunner, RegimeRouter. Support N models with typed outputs and per-regime routing. Handle regime transitions (close-and-switch).

**E2E test:** Load regime model + one signal model, run ensemble backtest, verify signal model only runs during its assigned regime, verify trades are closed on regime transition.

### M4: Full Regime-Routed Backtesting
Run ensemble backtest with regime classifier + per-regime signal models. Compare vs. single unrouted signal model. Measure improvement in risk-adjusted returns and drawdown.

**E2E test:** Run ensemble backtest on EURUSD 1h 2024-2025, compare metrics against signal-only baseline.

### M5: Agent Integration
Researcher agent can generate regime classifier strategies, per-regime signal strategies, and ensemble configs. Regime analysis integrated into assessment workflow.

**E2E test:** Agent generates an ensemble config with regime + signal models, triggers ensemble backtest, assessment evaluates regime effectiveness.
