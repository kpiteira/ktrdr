# Signal Model Evolution: From Regression Collapse to Adaptive Neuro-Fuzzy Meta-Labeling

## Status: Design
## Date: 2026-03-14
## Contributors: Karl + Lux

---

## 1. Executive Summary

The signal models in ktrdr's predictive features pipeline are fundamentally broken. Through empirical experiments and deep research, we've identified a cascade of three compounding failures: the target is noise, the features are sparse, and the training is under-equipped. No single fix addresses all three.

This document proposes a four-phase evolution that restructures the signal generation pipeline from "predict forward returns" to "filter and size trade candidates." The changes preserve all working components (regime classifier, context classifier, ensemble router, context gate) while replacing the broken signal prediction with a more tractable approach grounded in quantitative finance literature.

**The core insight: stop asking the neural network to predict returns. Start asking it to filter trades.**

---

## 2. Background: What We Built (M1-M8)

Milestones M1 through M8 built a modular ensemble prediction system:

| Milestone | Component | Status |
|-----------|-----------|--------|
| M1 | Strategy grammar v3 + feature resolver | Working |
| M2 | DecisionFunction (stateless inference) | Working |
| M3 | Ensemble backtest runner | Working |
| M4 | Regime classifier training pipeline | Working (69-79% accuracy) |
| M5 | Multi-TF context classifier (daily trend gate) | Working |
| M6 | Forward-return regression signal models | **Collapsed** |
| M7 | Multi-scale zigzag regime labeler | Working |
| M8 | Context gate for ensemble threshold adjustment | Working (mechanism correct) |
| M9 | External data (FRED, CFTC) | Working |

The architecture works. The regime classifier identifies market states with genuine accuracy. The context classifier detects daily trend direction. The ensemble router dispatches to per-regime models. The context gate adjusts thresholds based on alignment.

**The single broken link: the signal models that generate actual trade decisions.** Both `trend_regression_signal` and `range_regression_signal` collapse to predicting their training mean, producing constant outputs regardless of input.

---

## 3. Root Cause Analysis

### 3.1 Layer 1: The Target Is Noise (Critical)

The `ForwardReturnLabeler` computes `(close[t+h] - close[t]) / close[t]` with horizon h=8-12 bars on EURUSD 1h data. The signal models (`trend_regression_signal` with h=12, `range_regression_signal` with h=8) use these short horizons.

**We already learned this lesson with regime labeling.** In M7/M11, the original SER-based RegimeLabeler used a fixed horizon of 24 bars (1 day on 1H). It collapsed — 68%+ bars labeled RANGING because everything looks like noise at the wrong zoom level. The fix was the MultiScaleRegimeLabeler, which reads the market's own swing structure via ATR-scaled zigzag instead of using a fixed horizon. That fix worked: regime classification improved to 69-79% accuracy with balanced 4-class distribution.

**But we never applied this lesson to the signal models.** The signal models still use `source: forward_return` with fixed short horizons. The same problem that plagued regime labeling — fixed horizon captures noise, not structure — is why signal models collapse to predicting the mean. The triple barrier method proposed in this document is the direct analogue of the MultiScaleRegimeLabeler for signal models: replace a fixed-horizon point-in-time label with a structure-aware, volatility-adaptive label.

**Empirical measurements:**

| Metric | Value | Implication |
|--------|-------|-------------|
| Mean forward return | +0.000097 | Near zero — no directional bias |
| Std of forward return | 0.0048 | 48x larger than mean |
| Signal-to-noise ratio | 0.002 | Target is 99.8% noise |
| Best indicator correlation | r = -0.032 (ADX) | Explains 0.1% of variance |
| Directional accuracy (best model) | 50.2% | Indistinguishable from random |

**Why the model predicts the mean:** The optimal prediction under MSE or Huber loss when the signal is negligible IS the mean. The model discovers in the first few epochs that its hidden layers add nothing useful, and the output bias (≈ 0.0001) alone minimizes loss. This is not a bug — it's the mathematically correct response to an unsolvable problem.

**Why this is fundamentally about the target, not the model:** We tested 4 different encodings (fuzzy triangular, raw normalized, calibrated 3-zone fuzzy, ordinal classification) and 3 different architectures. All converge to ~50% directional accuracy. The indicators simply don't carry information about fixed-horizon forward returns on EURUSD 1h.

**The path-independence problem:** Forward return labels ignore what happens BETWEEN entry and exit. A bar labeled +0.04% might have experienced -0.3% drawdown before recovering — a real trader with a stop-loss would have exited at -0.3%. The label says "profit" but the trade would have been a loss. This mismatch between label and real outcome reduces SNR further.

### 3.2 Layer 2: Fuzzy Dead Zones Starve the Input

The strategy YAMLs use binary paired triangular membership functions:

```yaml
fuzzy_sets:
  rsi_zone:
    indicator: rsi_14
    oversold: [20, 30, 40]    # membership > 0 only when RSI in [20, 40]
    overbought: [60, 70, 80]  # membership > 0 only when RSI in [60, 80]
```

**The dead zone: RSI 40-80 has zero membership in both sets.** On EURUSD 1h data, RSI falls in this gap 39.8% of the time. For those bars, the NN receives exactly 0.0 from both RSI fuzzy features — it is completely blind to RSI.

Measured dead zone coverage across regression signal model features:

| Feature | Dead Zone Range | % of Bars Affected |
|---------|----------------|-------------------|
| RSI zone (oversold/overbought) | 40-60 | 39.8% |
| BBWidth level (tight/wide) | 0.02-0.03 | 99.7% |
| MACD signal (bearish/bullish) | -0.0003 to 0.0003 | 34.7% |
| ROC direction (falling/rising) | -0.15 to 0.15 | ~45% |
| **Average bar** | — | **5.1 of 8 features = 0** |

**This violates a fundamental principle of fuzzy logic.** The Ruspini partition constraint requires that at every point in the input domain, membership values sum to 1.0 (or at least > 0). Our binary paired sets violate this, creating regions where the neural network receives zero gradient signal. This is a well-understood failure mode in fuzzy systems literature, not a novel finding.

**Why this matters beyond dead zones:** Even in the "active" regions (RSI < 40 or > 60), the triangular MFs have non-differentiable corner points. Gradients are discontinuous at the peak and edges, making optimization harder. And with only 2 sets per indicator, the NN has a very coarse view of each input — it can distinguish "oversold" from "overbought" but nothing in between.

### 3.3 Layer 3: Training Pipeline Is Under-Equipped

The training loop in `MLPTradingModel.train()` (mlp.py:104-219) is a bare-bones implementation:

| Missing Feature | Impact |
|----------------|--------|
| Full-batch training (no mini-batches) | No stochastic noise → poor generalization, overfits to training mean |
| No early stopping | Model trains for exactly N epochs regardless of overfitting/convergence |
| No learning rate scheduling | Fixed LR throughout — no fine-tuning phase, no warmup |
| No label purging | Overlapping horizons leak future info between train/val/test |
| No sample weighting | All bars weighted equally regardless of informativeness |
| No gradient clipping | Vulnerable to exploding gradients on outlier returns |

Any ONE of these would be tolerable. Together, they compound with the noise target to guarantee collapse. Even if the target had signal, the training pipeline would struggle to extract it.

### 3.4 The Compounding Effect

These three layers multiply:
- Layer 1 (noise target) means the model CANNOT learn useful patterns
- Layer 2 (dead zones) means the model CANNOT see ~50% of the input space
- Layer 3 (basic training) means the model CANNOT optimize effectively even on the visible part

Fixing any single layer alone won't help. A perfect training pipeline on noise targets still produces noise. Perfect features predicting noise targets still predict noise. The right target with zero-valued features still can't learn. **All three layers must be addressed.**

---

## 4. Architecture Today

### 4.1 Current Pipeline (Training Path)

```
                    STRATEGY YAML (v3)
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  indicators:       fuzzy_sets:      nn_inputs:
  {rsi_14, adx,     {rsi_zone:       [{fuzzy_set:
   macd, roc}        oversold/         rsi_zone,
                     overbought}       timeframes: all}]
        │                │                │
        ▼                ▼                ▼
  ┌───────────┐   ┌───────────┐   ┌──────────────┐
  │ Indicator │   │  Fuzzy    │   │   Feature    │
  │  Engine   │──▶│  Engine   │──▶│  Resolver    │
  │ (compute) │   │(fuzzify)  │   │ (order+map)  │
  └───────────┘   └───────────┘   └──────┬───────┘
                                         │
        ┌────────────────────────────────┘
        ▼
  ┌──────────────────┐     ┌─────────────────────┐
  │ FuzzyNeural      │     │ ForwardReturn       │
  │ Processor        │     │ Labeler             │
  │ (fuzzy → tensor) │     │ (close[t+h]-close[t]│
  │                  │     │  / close[t])        │
  └────────┬─────────┘     └──────────┬──────────┘
           │                          │
           ▼                          ▼
  ┌─────────────────────────────────────────────┐
  │              MLPTradingModel                 │
  │  Input(8 fuzzy) → [64] → [32] → Output(1)  │
  │                                             │
  │  Loss: Huber(predicted_return, actual_return)│
  │  Full-batch, fixed LR, fixed epochs         │
  └─────────────────────────────────────────────┘
```

### 4.2 Current Pipeline (Backtest / Ensemble Path)

```
  ┌─────────────────────────────────────────────────────────────┐
  │                 EnsembleBacktestRunner                       │
  │                                                             │
  │  Per bar:                                                   │
  │                                                             │
  │  1. OHLCV bar                                               │
  │     │                                                       │
  │     ├──▶ RegimeClassifier ──▶ regime probabilities          │
  │     │    (69-79% accurate)    {trending_up: 0.7, ...}       │
  │     │                              │                        │
  │     ├──▶ ContextClassifier ──▶ context (daily eval)         │
  │     │    (bullish/bearish/       {bullish: 0.67, ...}       │
  │     │     neutral)                  │                       │
  │     │                              │                        │
  │     │         ┌────────────────────┘                        │
  │     │         ▼                                             │
  │     │    RegimeRouter                                       │
  │     │    ├── trending_up → trend_signal_model               │
  │     │    ├── trending_down → trend_signal_model             │
  │     │    ├── ranging → range_signal_model                   │
  │     │    └── volatile → FLAT (no trade)                     │
  │     │              │                                        │
  │     │              ▼                                        │
  │     ├──▶ Signal Model ──▶ predicted_return ≈ 0.0001         │
  │     │    (COLLAPSED)      (constant for all inputs)         │
  │     │                          │                            │
  │     │                          ▼                            │
  │     │                  ThresholdModifier                     │
  │     │                  (context gate adjusts                │
  │     │                   trade_threshold ±20-30%)            │
  │     │                          │                            │
  │     │                          ▼                            │
  │     │                  DecisionFunction                      │
  │     │                  predicted_return > threshold?         │
  │     │                  → BUY / SELL / HOLD                  │
  │     │                          │                            │
  │     │                          ▼                            │
  │     └──▶ PositionManager ──▶ execute trade                  │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘

  PROBLEM: Signal models output constant ≈ 0.0001 for ALL inputs.
  The entire downstream pipeline (context gate, threshold, decision)
  operates on garbage input.
```

### 4.3 What Works vs What's Broken

```
  ┌──────────────────────────────────────────────────┐
  │ WORKING (keep as-is)                              │
  │                                                   │
  │  ✅ Regime Classifier (4-class, 69-79% accuracy)  │
  │  ✅ Context Classifier (3-class, daily trend)     │
  │  ✅ MultiScale Zigzag Labeler (ATR-adaptive)      │
  │  ✅ Ensemble Router (regime → model dispatch)     │
  │  ✅ Context Gate (threshold modifier mechanism)   │
  │  ✅ External Data Pipeline (FRED, CFTC)           │
  │  ✅ Feature Resolver (canonical ordering)         │
  │  ✅ FeatureCache (backtest feature delivery)      │
  │  ✅ PositionManager (trade execution/tracking)    │
  │  ✅ Strategy Grammar V3 (configuration)           │
  │                                                   │
  │ BROKEN (must fix)                                 │
  │                                                   │
  │  ❌ ForwardReturnLabeler (noise target, SNR=0.002)│
  │  ❌ Fuzzy set definitions (dead zones, Ruspini)   │
  │  ❌ Training loop (no minibatch, early stop, etc) │
  │  ❌ Signal model concept (predict returns → trade)│
  │                                                   │
  └──────────────────────────────────────────────────┘
```

---

## 5. Research Findings

### 5.1 Triple Barrier Method (Lopez de Prado, 2018)

The triple barrier method (from *Advances in Financial Machine Learning*) replaces fixed-horizon returns with path-dependent, volatility-adaptive trade outcomes.

**How it works:**

For each candidate entry bar t:
1. Compute `daily_vol` = EWMA standard deviation of log returns (span 50-100 bars)
2. Set upper barrier: `entry_price + pt_mult * daily_vol` (take profit)
3. Set lower barrier: `entry_price - sl_mult * daily_vol` (stop loss)
4. Set vertical barrier: `t + max_holding_period` (time expiry)
5. Walk forward through future prices:
   - If upper barrier touched first → label = **+1** (profitable trade)
   - If lower barrier touched first → label = **-1** (losing trade)
   - If vertical barrier reached → label = **0** or **sign(return at expiry)**

**Why this solves the noise target problem:**

| Property | Forward Returns | Triple Barrier |
|----------|----------------|----------------|
| Path-dependent? | No — only final price matters | Yes — captures drawdowns |
| Volatility-adaptive? | No — fixed horizon | Yes — barriers scale with vol |
| Reflects real trading? | No — ignores stops/TPs | Yes — mirrors actual risk mgmt |
| Label SNR | ~0.002 | Much higher — labels encode achievable outcomes |
| Output type | Continuous (regression) | Categorical (classification) |
| What model learns | "Average future return" ≈ 0 | "Will this trade hit TP or SL?" |

**Important caveat — label concurrency:** Triple barrier labels create overlapping active periods. Bar t's label might depend on prices up to t+50, while bar t+1's label depends on prices up to t+51. These labels are NOT independent. Solution: **uniqueness weighting** — weight each sample inversely proportional to its concurrency. Lopez de Prado provides the formula: `w_t = 1 / (avg concurrent labels at time t)`.

**CUSUM filter for event sampling:** Don't label every bar. Use a cumulative sum filter: accumulate returns until they exceed a threshold (typically 1x daily vol), then emit an event. This produces training samples only at moments of significant price movement, reducing noise and making the learning task easier.

**Parameters we'll need to experiment with:**

| Parameter | Range | Effect |
|-----------|-------|--------|
| `pt_multiplier` | 1.0 - 3.0 | Take profit width in vol units |
| `sl_multiplier` | 1.0 - 3.0 | Stop loss width in vol units |
| `max_holding_period` | 10 - 100 bars | Time expiry |
| `vol_span` | 20 - 100 | EWMA volatility lookback |
| `cusum_threshold` | 0.5 - 2.0 × daily_vol | Event sampling sensitivity |

### 5.2 Meta-Labeling (Lopez de Prado, 2017)

Meta-labeling separates trade direction (side) from trade confidence/sizing.

**Two-stage architecture:**

```
Stage 1: Primary Model (determines SIDE)
  Input: market features
  Output: BUY candidate or SELL candidate
  Requirement: high RECALL (catch most real opportunities)
  Can be simple: RSI < 30 in ranging → BUY candidate

Stage 2: Meta-Labeler (determines SIZE)
  Input: primary signal + features + regime + context
  Output: P(this trade will be profitable) ∈ [0, 1]
  Requirement: high PRECISION (filter false positives)
  Maps probability → position size
```

**Why this helps:**

The meta-labeler has a MUCH easier learning task than direct return prediction:
- Binary classification (profitable / not profitable) vs continuous return regression
- The primary model handles the hard part (direction) with domain knowledge
- The meta-labeler only learns WHEN a known pattern works, not WHAT will happen
- Position sizing naturally manages risk — low confidence = small bet

**Critical caveat:** Meta-labeling cannot create edge where none exists. If the primary model's directional signals are random (50% accuracy), meta-labeling can't fix it. **But our regime classifier IS better than random** (69-79% for regime, and regime persistence IS a genuine financial factor). A primary model that says "trade with the trend in trending regime, mean-revert in ranging" exploits a real edge — momentum and mean-reversion are the two most robust factors in finance.

### 5.3 Ruspini Partition and Membership Function Theory

Our binary paired triangular MFs violate the **Ruspini partition** — the requirement that membership values sum to 1 at every point in the input domain. This is not an optional best practice; it's a necessary condition for fuzzy systems to produce meaningful output.

**Solutions (ordered by effort):**

1. **Add neutral set (minimum fix):** 3 overlapping triangular sets with 50% overlap. Eliminates dead zones.
2. **Gaussian MFs:** Already implemented in `ktrdr/fuzzy/membership.py` as `GaussianMF`. Two parameters (mean, sigma). Never reaches exactly zero. Smooth gradients everywhere.
3. **Learnable MFs (ANFIS):** Initialize MF parameters from data percentiles, then tune via backpropagation alongside the NN weights. The fuzzy layer becomes a differentiable part of the network.

**Empirical recommendation from literature:** A sigmoid-based or Gaussian ANFIS with **4 fuzzy sets per input** emerged as the most consistent performer for financial applications across a 2013-2023 benchmark study. The number of sets matters: 2 creates dead zones, 3 is minimal, 4-5 is optimal, >7 creates overfitting in the rule base.

### 5.4 Training Pipeline Best Practices

| Improvement | Why It Matters | Effort |
|-------------|---------------|--------|
| Mini-batch SGD (batch=256) | Stochastic noise improves generalization | Low |
| Early stopping (patience=10) | Prevents overfitting, saves compute | Low |
| LR scheduling (ReduceLROnPlateau) | Fine-tunes convergence, avoids local minima | Low |
| Label purging | Prevents information leakage across train/val/test | Medium |
| Uniqueness weighting | Handles triple barrier label concurrency | Medium |
| Focal loss | Focuses learning on hard examples, not easy majority | Medium |
| Purged k-fold CV | Proper validation for time series with overlapping labels | Medium |

### 5.5 What Actually Works in ML Trading (Literature Survey)

From a comprehensive review of academic papers and practitioner literature (2020-2025):

**Approaches with documented out-of-sample success:**
- Cross-sectional factor models (momentum, value, quality) + gradient boosting
- Triple barrier labeling + meta-labeling (Lopez de Prado framework)
- Volatility forecasting (GARCH, realized vol prediction) — NOT return prediction
- Regime detection → conditional strategy selection

**Approaches that consistently fail out-of-sample:**
- Raw TA indicators → NN → forward return prediction (exactly what we're doing)
- Deep learning on small datasets (< millions of samples)
- Single-instrument time-series return prediction at short horizons

**The uncomfortable truth:** Standard technical indicators (RSI, MACD, Bollinger Bands) have weak-to-no predictive power for returns in isolation. They are transformations of price and contain no information not already in the price series. Their value, if any, comes from capturing nonlinear interactions — but tree-based models (XGBoost/LightGBM) discover these interactions from raw features without hand-crafted fuzzy encoding.

**However:** These same indicators MAY have predictive power for **triple barrier outcomes**, because those outcomes depend on path characteristics (drawdowns, volatility spikes) which ARE partially captured by volatility and momentum indicators. This is the key hypothesis we need to test.

---

## 6. Proposed Architecture Evolution

### 6.1 Phase 1: Fix the Target (Triple Barrier Labeling + Training Improvements)

**Goal:** Replace the noise target with a learnable one. Improve the training pipeline to handle it properly.

#### Architecture After Phase 1

```
                    STRATEGY YAML (v3 — extended)
                         │
                    training:
                      labels:
                        source: triple_barrier    ◀── NEW
                        pt_multiplier: 2.0
                        sl_multiplier: 1.5
                        max_holding_period: 50
                        vol_span: 50
                        cusum_threshold: 1.0
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌───────────┐   ┌───────────┐   ┌──────────────┐
  │ Indicator │   │  Fuzzy    │   │   Feature    │
  │  Engine   │──▶│  Engine   │──▶│  Resolver    │
  └───────────┘   └───────────┘   └──────┬───────┘
                                         │
        ┌────────────────────────────────┘
        ▼
  ┌──────────────────┐     ┌─────────────────────┐
  │ FuzzyNeural      │     │ TripleBarrier       │ ◀── NEW
  │ Processor        │     │ Labeler             │
  │                  │     │ vol-scaled barriers  │
  └────────┬─────────┘     │ CUSUM event filter  │
           │               │ uniqueness weights   │
           │               └──────────┬──────────┘
           ▼                          ▼
  ┌─────────────────────────────────────────────┐
  │              MLPTradingModel                 │
  │  Input(8 fuzzy) → [64] → [32] → Output(3)  │ ◀── 3-class
  │                                             │
  │  Loss: FocalLoss(+1 / 0 / -1)              │ ◀── NEW
  │  Mini-batch, early stopping, LR scheduling  │ ◀── NEW
  │  Purged CV, uniqueness-weighted samples     │ ◀── NEW
  └─────────────────────────────────────────────┘
```

**Key changes:**
1. `TripleBarrierLabeler` replaces `ForwardReturnLabeler`
2. Output switches from regression (1 neuron) to 3-class classification (+1/0/-1)
3. Training loop upgraded with mini-batch SGD, early stopping, LR scheduling
4. Label purging and uniqueness weighting handle concurrent labels
5. Focal loss focuses learning on hard-to-classify bars

**What stays the same:** Indicator engine, fuzzy engine, feature resolver, model architecture (MLP with configurable layers). The ensemble backtest runner still routes by regime. Context gate still adjusts thresholds.

**Changes to DecisionFunction:** Instead of `predicted_return > trade_threshold`, the model outputs class probabilities. `P(+1)` = probability of hitting take-profit. Decision: if `P(+1) > confidence_threshold` → BUY; if `P(-1) > confidence_threshold` → SELL; else HOLD. The context gate adjusts `confidence_threshold` exactly as it does today.

#### Experiment 1: Triple Barrier vs Forward Return Baseline

**Setup:**
- Same features (RSI, ADX, MACD, ROC with current fuzzy sets)
- Same model architecture ([64, 32] MLP)
- Same data (EURUSD 1h, train 2020-2023, val 2024)
- Only change: label source

**What to measure:**

| Metric | Forward Return (baseline) | Triple Barrier (expected) |
|--------|--------------------------|--------------------------|
| Training loss convergence | Converges to mean immediately | Should show gradual improvement |
| Val accuracy | ~50% directional | >55% (if indicators carry ANY signal) |
| Hidden layer contribution | Zero (output bias dominates) | Non-zero (hidden layers should activate) |
| Trade count (backtest) | 15-18 (near-random) | Fewer, more selective |
| Sharpe ratio | Near 0 | > 0.3 (hypothesis) |

**What this experiment proves/disproves:**
- If triple barrier labels produce val accuracy >55% with the SAME features → the target was the problem, not the features
- If accuracy is still ~50% → the features genuinely carry no signal, even for path-dependent outcomes → we need to change features too (Phase 2 becomes critical)
- If accuracy is >55% but Sharpe is still near 0 → the model learned something but it doesn't translate to profitable trading → need meta-labeling (Phase 3)

**How to run this via autoresearch:**

The autoresearch harness (PR #352) can execute this experiment directly. Modify `strategies/autoresearch.yaml` to use `source: triple_barrier` with different barrier parameters. The harness trains and backtests, returning `val_sharpe`. The agent can search the barrier parameter space automatically.

#### Experiment 2: CUSUM-Filtered vs Every-Bar Sampling

**Setup:**
- Triple barrier labels on both
- One run: label every bar
- Other run: only label bars where CUSUM filter fires (significant price moves)

**Expected outcome:** CUSUM filtering should improve val accuracy because:
- Removes "boring" bars where no significant price movement occurs
- Creates a smaller but higher-quality training set
- Each sample carries more information

**Risk:** Smaller training set may cause overfitting. Monitor train/val gap closely.

### 6.2 Phase 2: Fix the Features (Hybrid Encoding + Gaussian MFs)

**Goal:** Eliminate fuzzy dead zones. Give the NN full visibility of the input space.

#### Architecture After Phase 2

```
                    STRATEGY YAML (v3 — extended)
                         │
                    fuzzy_sets:
                      rsi_momentum:
                        indicator: rsi_14
                        low:                              ◀── 3+ sets
                          type: gaussian                  ◀── Gaussian
                          parameters: [30, 15]
                        neutral:
                          type: gaussian
                          parameters: [50, 12]
                        high:
                          type: gaussian
                          parameters: [70, 15]
                      ...
                    nn_inputs:
                      - fuzzy_set: rsi_momentum
                        timeframes: all
                      - raw_indicator: rsi_14             ◀── NEW: hybrid
                        timeframes: all
                        normalization: minmax              ◀── NEW
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌───────────┐   ┌───────────┐   ┌──────────────┐
  │ Indicator │   │  Fuzzy    │   │   Feature    │
  │  Engine   │──▶│  Engine   │──▶│  Resolver    │
  └─────┬─────┘   │(Gaussian) │   │ (raw+fuzzy)  │
        │         └───────────┘   └──────┬───────┘
        │                                │
        └───── raw normalized ──────────▶│ ◀── NEW: raw features
                                         │       alongside fuzzy
        ┌────────────────────────────────┘
        ▼
  ┌──────────────────┐     ┌─────────────────────┐
  │ FuzzyNeural      │     │ TripleBarrier       │
  │ Processor        │     │ Labeler             │
  │ (raw + fuzzy)    │     │                     │
  └────────┬─────────┘     └──────────┬──────────┘
           │                          │
           ▼                          ▼
  ┌─────────────────────────────────────────────┐
  │              MLPTradingModel                 │
  │  Input(12-20) → [128] → [64] → Output(3)   │
  │  More features → proportionally wider layers │
  │                                             │
  │  Hybrid input: [rsi_raw, rsi_low, rsi_mid,  │
  │   rsi_high, adx_raw, adx_weak, adx_strong,  │
  │   ...]                                       │
  └─────────────────────────────────────────────┘
```

**Key changes:**
1. Binary fuzzy sets (2 per indicator) → 3-5 Gaussian or overlapping triangular sets
2. Raw normalized indicator values added alongside fuzzy memberships (hybrid encoding)
3. `FuzzyNeuralProcessor` extended to accept raw indicators
4. Strategy YAML gets `raw_indicator` entry type in `nn_inputs`
5. Hidden layers scaled up proportionally to handle more features

**Why hybrid encoding matters:**

The NN gets TWO views of each indicator:
- **Fuzzy view:** Semantic interpretation (RSI is "oversold" with degree 0.7)
- **Raw view:** Precise numerical value (RSI = 28.3)

The fuzzy view provides domain knowledge (expert-defined zones). The raw view fills dead zones and captures gradients the fuzzy encoding misses. The NN can learn to weight each view appropriately. This is a low-effort, high-impact change — ~20 lines of code in `FuzzyNeuralProcessor`.

#### Experiment 3: Encoding Comparison (with Triple Barrier Labels)

**Critical:** This experiment MUST use triple barrier labels from Phase 1. Testing encoding quality on noise targets is meaningless (we already proved that).

**Setup:**
- Triple barrier labels (best parameters from Phase 1 experiments)
- Same model architecture
- Three encoding variants:

| Variant | Features per indicator | Total features (4 indicators) |
|---------|----------------------|-------------------------------|
| A: Binary fuzzy (current) | 2 fuzzy values | 8 |
| B: 3-set Gaussian fuzzy | 3 fuzzy values | 12 |
| C: Hybrid (raw + 3 Gaussian) | 1 raw + 3 fuzzy = 4 | 16 |

**What to measure:**

| Metric | Variant A | Variant B (expected) | Variant C (expected) |
|--------|-----------|---------------------|---------------------|
| Val accuracy | Baseline | +2-5% (no dead zones) | +3-7% (full info) |
| Feature importance | Many zeros | Uniform activation | Raw features may dominate |
| Dead zone bars | 39.8% (RSI) | 0% | 0% |
| Gradient flow | Sparse | Dense | Densest |

**What this experiment proves/disproves:**
- If B >> A → dead zones were killing signal, Gaussian MFs fix it
- If C >> B → raw indicators carry additional signal beyond fuzzy encoding
- If C ≈ B → fuzzy encoding captures everything the raw value does (the fuzzy approach is validated)
- If A ≈ B ≈ C → encoding doesn't matter with these indicators (the indicators themselves lack signal → need different features)

#### Experiment 4: Fractionally Differentiated Features

Lopez de Prado's fractional differentiation applies a non-integer differencing operator (d ≈ 0.1-0.4) to price series. Standard returns use d=1.0 (full differencing), which achieves stationarity but throws away long-term memory. Fractional differencing achieves stationarity while preserving >90% of the original series' correlation structure.

**Setup:**
- Add fractionally differentiated close price as a raw feature (using `fracdiff` package)
- Compare: standard features vs features + frac-diff close
- Triple barrier labels

**What to measure:** Does adding frac-diff features improve val accuracy? If yes, it suggests the NN can extract time-series memory that standard indicators miss.

### 6.3 Phase 3: Meta-Labeling Architecture

**Goal:** Separate trade direction (side) from trade quality (size). Let the regime classifier and simple rules handle direction; train a meta-labeler to filter and size.

#### Architecture After Phase 3

```
  ┌─────────────────────────────────────────────────────────────┐
  │                 EnsembleBacktestRunner (evolved)             │
  │                                                             │
  │  Per bar:                                                   │
  │                                                             │
  │  1. OHLCV bar                                               │
  │     │                                                       │
  │     ├──▶ RegimeClassifier ──▶ regime: trending_up           │
  │     │    (UNCHANGED)              │                         │
  │     │                             │                         │
  │     ├──▶ ContextClassifier ──▶ context: bullish             │
  │     │    (UNCHANGED)              │                         │
  │     │                             │                         │
  │     │         ┌───────────────────┘                         │
  │     │         ▼                                             │
  │     │    RegimeRouter (UNCHANGED)                           │
  │     │    └── trending_up → primary_trend_signal             │
  │     │              │                                        │
  │     │              ▼                                        │
  │     ├──▶ PRIMARY SIGNAL MODEL ──▶ SIDE = BUY candidate      │
  │     │    (rule-based or light ML)                           │ ◀── NEW
  │     │    RSI < 30 in ranging → BUY                          │
  │     │    ADX > 25 + MACD bullish in trending → BUY          │
  │     │    High recall, accepts false positives                │
  │     │                              │                        │
  │     │                              ▼                        │
  │     ├──▶ META-LABELER ──▶ P(profitable) = 0.73              │ ◀── NEW
  │     │    (secondary model, trained on triple barrier)        │
  │     │    Input: primary signal + ALL features + regime       │
  │     │    + context + external data                          │
  │     │    Output: probability [0, 1]                         │
  │     │                              │                        │
  │     │                              ▼                        │
  │     │                     ┌────────────────────┐            │
  │     │                     │ Position Sizer     │            │ ◀── NEW
  │     │                     │ P > 0.6 → full pos │            │
  │     │                     │ P > 0.5 → half pos │            │
  │     │                     │ P < 0.5 → no trade │            │
  │     │                     └────────┬───────────┘            │
  │     │                              │                        │
  │     │                              ▼                        │
  │     │                  ThresholdModifier (UNCHANGED)         │
  │     │                  Context gate adjusts the              │
  │     │                  meta-labeler's threshold              │
  │     │                              │                        │
  │     │                              ▼                        │
  │     └──▶ PositionManager ──▶ execute trade with size         │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘
```

**Key changes:**
1. Signal models split into Primary (side) + Meta-Labeler (filter/size)
2. Primary models can be rule-based (no ML needed for simple patterns)
3. Meta-labeler is a separate model trained on triple barrier labels
4. Position sizing integrated — meta-labeler probability → bet size
5. Context gate adjusts meta-labeler confidence threshold (M8 mechanism preserved)

**Why tree-based meta-labelers may outperform NNs here:**

Research consistently shows XGBoost/LightGBM outperform neural networks on tabular financial data with small-to-medium datasets. The meta-labeler's input is tabular (indicator values, regime probabilities, context scores). We should benchmark both MLP and LightGBM meta-labelers.

This is compatible with the existing architecture: the meta-labeler is just another "model" in the ensemble. Its `output_type` would be `meta_label` (probability), loaded and called via the same `ModelBundle` / `DecisionFunction` interface.

#### Experiment 5: Meta-Labeling vs Direct Classification

**Setup:**
- Same features, same data
- Variant A: Direct 3-class classification (Phase 1 model)
- Variant B: Primary rule model (RSI oversold/overbought) + meta-labeler

**What to measure:**

| Metric | Direct Classification | Meta-Labeling (expected) |
|--------|----------------------|--------------------------|
| Precision | Moderate | Higher (fewer false positives) |
| Recall | Moderate | Lower (filtered) |
| F1 score | Baseline | Higher (precision gain > recall loss) |
| Sharpe ratio | Baseline | Higher (fewer bad trades) |
| Win rate | ~50% | >55% (meta-labeler filters losers) |
| Avg trade size | Fixed | Variable (probability-weighted) |

**What this experiment proves/disproves:**
- If meta-labeling Sharpe >> direct → separating side/size is the right decomposition
- If meta-labeling ≈ direct → the primary model lacks sufficient directional edge for meta-labeling to improve
- If primary model recall < 30% → primary rules are too restrictive, need to loosen

#### Experiment 6: MLP vs LightGBM Meta-Labeler

**Setup:**
- Same primary model, same features, same labels
- Meta-labeler A: MLP [64, 32]
- Meta-labeler B: LightGBM (100 trees, max_depth=5)

**What to measure:** Val accuracy, precision, Sharpe. LightGBM is expected to win on small datasets and provide feature importance rankings for free.

### 6.4 Phase 4: Learnable Membership Functions (ANFIS)

**Goal:** Make the fuzzy encoding layer fully differentiable and trainable end-to-end with the neural network. The system learns its own optimal market partitioning.

#### Architecture After Phase 4

```
                    STRATEGY YAML (v3 — extended)
                         │
                    fuzzy_sets:
                      rsi_momentum:
                        indicator: rsi_14
                        learnable: true                    ◀── NEW
                        num_sets: 4                        ◀── NEW
                        init_method: percentile            ◀── NEW
                        mf_type: gaussian                  ◀── NEW
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌───────────┐   ┌─────────────────┐   ┌──────────────┐
  │ Indicator │   │  LEARNABLE      │   │   Feature    │
  │  Engine   │──▶│  Fuzzy Layer    │──▶│  Resolver    │
  │           │   │  (ANFIS-style)  │   │              │
  └───────────┘   │                 │   └──────┬───────┘
                  │  Gaussian MFs   │          │
                  │  with trainable │          │
                  │  μ and σ params │          │
                  │                 │          │
                  │  ∂L/∂μ, ∂L/∂σ  │          │
                  │  via backprop   │          │
                  └─────────────────┘          │
                                               │
        ┌──────────────────────────────────────┘
        ▼
  ┌──────────────────────────────────────────────────────┐
  │              END-TO-END TRAINABLE MODEL               │
  │                                                       │
  │  Layer 0: Raw indicators (RSI=28.3, ADX=45.1, ...)    │
  │     │                                                 │
  │  Layer 1: LEARNABLE FUZZY LAYER                       │ ◀── NEW
  │     │  μ_rsi_low=30, σ_rsi_low=15 (trainable)        │
  │     │  μ_rsi_mid=50, σ_rsi_mid=12 (trainable)        │
  │     │  μ_rsi_high=70, σ_rsi_high=15 (trainable)      │
  │     │  Apply: exp(-(x - μ)² / (2σ²))                 │
  │     │  Optional: softmax normalize (Ruspini)          │
  │     │                                                 │
  │  Layer 2+: Standard MLP layers [128] → [64]           │
  │     │                                                 │
  │  Output: P(profitable) or class probabilities         │
  │                                                       │
  │  Training: backprop updates ALL parameters jointly     │
  │  - MF params (μ, σ) via ∂L/∂μ, ∂L/∂σ                │
  │  - NN weights via standard backprop                   │
  │  Hybrid ANFIS: gradient descent for MF params,        │
  │  optionally LSE for output layer (Takagi-Sugeno)      │
  └──────────────────────────────────────────────────────┘
```

**Why this is the most exciting phase (and why Karl is right to be bullish):**

Fixed membership functions embed a human's assumption about where "oversold" begins and ends. These assumptions may be wrong — or may be right for one market condition but wrong for another. Learnable MFs let the model discover its own optimal partitioning of indicator space.

**What the model might learn:**

Consider RSI. We assume oversold=[20,30,40], overbought=[60,70,80]. But what if the model discovers:
- In trending regimes, "oversold" should center at RSI=35 (momentum means 30 is already too late)
- In ranging regimes, "oversold" should center at RSI=25 (deeper oversold for mean-reversion)
- The optimal width for "oversold" is σ=20, not σ=10 (wider net catches more opportunities)

These are insights no human would hand-code. The model discovers the market's actual structure, not our assumption about it.

**Implementation approach:**

1. Create `LearnableFuzzyLayer` as a `torch.nn.Module`
2. Parameters: `nn.Parameter` for each μ and σ
3. Forward pass: `membership = exp(-(x - μ)² / (2σ²))` — fully differentiable
4. Optional: enforce Ruspini via softmax across MFs per indicator
5. Initialize from data percentiles: 20th, 40th, 60th, 80th for 4 sets
6. Train end-to-end: MF params update alongside NN weights via same optimizer
7. After training, inspect learned MF params to gain interpretability

**Ruspini enforcement options:**

| Method | Pros | Cons |
|--------|------|------|
| No enforcement | Maximum flexibility | May learn degenerate partitions |
| Softmax normalization | Sum=1 guaranteed | Constrains learned shapes |
| Regularization term | Soft encouragement | Doesn't guarantee Ruspini |
| Ordered means constraint | Prevents sets from crossing | Still allows gaps |

**Recommended:** Softmax normalization + ordered means. This ensures partition of unity while allowing the model to learn widths and positions freely.

**Integration with meta-labeling (Phase 3):**

The learnable fuzzy layer works particularly well with meta-labeling:
- Primary model uses FIXED fuzzy sets (expert-defined, stable, interpretable)
- Meta-labeler uses LEARNABLE fuzzy sets (data-driven, adaptive)
- The primary model provides consistent signals; the meta-labeler optimizes filtering

This separation keeps the primary model's interpretability while allowing the meta-labeler to discover hidden structure.

#### Experiment 7: Fixed vs Learnable MFs

**Setup:**
- Same model (meta-labeler from Phase 3)
- Same labels (triple barrier)
- Variant A: Fixed Gaussian MFs (expert-initialized)
- Variant B: Learnable Gaussian MFs (percentile-initialized, end-to-end trained)

**What to measure:**

| Metric | Fixed MFs | Learnable MFs (expected) |
|--------|-----------|--------------------------|
| Val accuracy | Baseline from Phase 3 | +2-5% (hypothesized) |
| Learned μ values | N/A | Compare vs expert-defined |
| Learned σ values | N/A | May be wider or narrower |
| Per-regime MF shapes | Same everywhere | May specialize per regime |
| Interpretability | High (expert-defined) | Medium (can inspect, but might be surprising) |

**What to look for in learned MFs:**
- Do MF centers shift from expert priors? How far?
- Do MFs for different indicators overlap more or less than expert design?
- Are any MFs effectively "turned off" (σ → ∞ = flat, uninformative)?
- Do they correlate with regime — does RSI's "oversold" center shift in trending vs ranging?

**Risk:** With small datasets, learnable MFs may overfit. Monitor train/val gap. Use dropout on the fuzzy layer (randomly zero-out memberships during training).

#### Experiment 8: Per-Regime Learnable MFs

**Advanced variant:** Train separate learnable MF parameters for each regime. The trend model's RSI "oversold" center may differ from the range model's.

**Setup:**
- Regime classifier routes to per-regime meta-labelers (Phase 3 architecture)
- Each meta-labeler has its own learnable fuzzy layer
- Compare: shared MFs vs per-regime MFs

**Expected outcome:** Per-regime MFs should outperform shared MFs because market structure differs by regime. The model may discover that:
- In trending: momentum indicators need wider MFs (trending = persistent deviation)
- In ranging: mean-reversion indicators need tighter MFs (ranging = tight bounds)

---

## 7. Impact on the Research Model

### 7.1 Current Research Model

The current research model (M1 design → M2 assessment → M3 training → M4 backtest) has a critical weakness: the researcher agent designs strategies by selecting indicators, fuzzy sets, and NN architecture. But none of these choices matter if the target is noise and the features are sparse.

The autoresearch system (PR #352) gives an agent autonomous access to mutate `strategies/autoresearch.yaml` and measure `val_sharpe`. But the search space is constrained to the WRONG dimensions:
- Indicator parameters (RSI period: 14 vs 21 — irrelevant if RSI doesn't predict)
- Fuzzy boundaries (oversold at 30 vs 25 — irrelevant if dead zones dominate)
- NN architecture (64,32 vs 128,64 — irrelevant if the target is noise)

The agent is searching a space where no good solution exists.

### 7.2 How Each Phase Transforms the Research Model

#### After Phase 1 (Triple Barrier):

The autoresearch search space gains genuinely impactful dimensions:

```
NEW search dimensions:
  ├── pt_multiplier: [1.0, 1.5, 2.0, 2.5, 3.0]     ← barrier width
  ├── sl_multiplier: [1.0, 1.5, 2.0, 2.5, 3.0]     ← stop-loss width
  ├── max_holding_period: [10, 20, 50, 100]          ← time expiry
  ├── vol_span: [20, 50, 100]                        ← vol estimation
  ├── cusum_threshold: [0.5, 1.0, 1.5, 2.0]         ← event filter
  └── barrier_symmetry: symmetric vs asymmetric      ← risk management

EXISTING dimensions now become meaningful:
  ├── indicator selection: different indicators may NOW predict TB outcomes
  ├── fuzzy boundaries: NOW affect non-zero feature space
  └── NN architecture: NOW has a learnable target
```

**Expected impact on autoresearch:** The agent should find strategies with `val_sharpe > 0` because:
1. The target has signal (TB outcomes ≠ noise)
2. The search dimensions affect outcomes (barrier width changes the problem)
3. Different indicator combinations may be better for TP vs SL prediction

**Key change to harness.py:** The harness needs to support `source: triple_barrier` in the strategy YAML. Training produces a 3-class classification model instead of regression. Backtesting uses class probabilities instead of predicted returns. The metric (Sharpe) stays the same.

#### After Phase 2 (Fuzzy Fixes):

The agent can search membership function parameters knowing they affect the FULL input space:

```
NEW search dimensions:
  ├── mf_type: [triangular, gaussian, trapezoidal]
  ├── num_sets_per_indicator: [3, 4, 5]
  ├── include_raw_features: [true, false]
  └── normalization: [minmax, zscore, none]

MEANINGFUL interactions:
  ├── gaussian + 4 sets → no dead zones + fine-grained view
  ├── hybrid (raw + fuzzy) → NN has full information
  └── different set counts per indicator → match indicator characteristics
```

**Expected impact on autoresearch:** Higher `val_sharpe` ceiling because:
1. The NN can "see" the full input space (no dead zones)
2. Hybrid encoding provides redundant information paths (fault tolerance)
3. More encoding options = larger search space with valid solutions

#### After Phase 3 (Meta-Labeling):

The research model fundamentally changes from "find the right strategy" to "find the right filter":

```
AUTORESEARCH YAML evolves from:
  strategy → indicators → fuzzy → NN → predict

TO a two-section file:
  primary_signal:
    type: rule_based
    rules:
      trending: [adx > 25, macd_bullish]
      ranging: [rsi < 30 OR stoch < 20]
    ← Agent mutates rules (simple, interpretable)

  meta_labeler:
    features: [all_indicators, regime_probs, context_probs]
    model: [mlp | lightgbm]
    architecture: [...]
    ← Agent mutates ML configuration
```

**Expected impact on autoresearch:**
1. The agent optimizes TWO things independently (decomposed problem)
2. Primary rules are simple enough for the agent to reason about ("RSI < 30 means oversold")
3. Meta-labeler tuning has higher leverage per experiment (each parameter affects filtering, not direction)
4. The agent can discover that certain primary rules work better in certain regimes

**Key insight for the research model:** The agent's hypothesis space becomes more structured. Instead of "try RSI period 21 instead of 14" (vague), the agent reasons "the primary model catches 80% of real opportunities but 60% are false positives — the meta-labeler needs to improve precision on ranging-regime BUY signals." This is a much more tractable optimization problem.

#### After Phase 4 (Learnable MFs):

The autoresearch agent gains a fundamentally new capability: **it can let the gradient tell it where the fuzzy boundaries should be.**

```
AUTORESEARCH YAML:
  fuzzy_sets:
    rsi_momentum:
      learnable: true
      num_sets: 4
      init_method: percentile   ← agent can try: percentile, uniform, expert
      mf_type: gaussian
      learning_rate: 0.001      ← separate LR for MF params (optional)
```

**Expected impact on autoresearch:**
1. The agent doesn't need to search fuzzy boundaries manually — the gradient does it
2. The agent's search space shifts to META-parameters: number of sets, init method, MF learning rate
3. After training, the agent can INSPECT learned MFs and form hypotheses about market structure
4. Per-regime learnable MFs let the agent discover regime-specific market partitioning

**The most powerful autoresearch loop:**
```
1. Agent designs primary rules + meta-labeler config with learnable MFs
2. Harness trains end-to-end (MFs + NN jointly)
3. Agent reads learned MF parameters (μ, σ for each indicator)
4. Agent observes: "RSI's 'oversold' center learned to be 35, not 30"
5. Agent forms hypothesis: "the market's oversold level is higher than textbook"
6. Agent updates primary rules: RSI < 35 instead of RSI < 30
7. Re-run with new primary rules → better or worse?
8. Agent logs insight to confirmed_patterns.md
```

This is the research agent doing genuine market structure discovery, not parameter grid search.

### 7.3 Impact on the Agentic Research System (v2.6)

The agentic research system (design/assess/train/backtest cycle coordinated by the coordinator loop) benefits from each phase:

**Phase 1:** The assessment model needs to evaluate strategies differently. Instead of "did this strategy produce positive returns?" the assessment asks "did the triple barrier labels have acceptable class balance?" and "does the model beat the no-information rate?" These are more meaningful quality gates.

**Phase 2:** The design agent (which generates strategy YAMLs) gains new vocabulary. Instead of only generating fuzzy set boundaries, it can specify `type: gaussian`, `num_sets: 4`, and `include_raw: true`. The design prompt needs updating to include these options.

**Phase 3:** The design agent's strategy YAML structure changes to include `primary_signal` and `meta_labeler` sections. The assessment agent evaluates precision/recall trade-offs, not just accuracy. The backtest harness reports win rate, average win/loss ratio, and position sizing statistics alongside Sharpe.

**Phase 4:** The design agent can specify `learnable: true` for fuzzy sets. After training, the assessment agent can read the learned MF parameters and include them in the assessment report. Over multiple research iterations, the system accumulates knowledge about optimal market partitioning across different regimes and instruments.

---

## 8. Complete Architecture Evolution Summary

### Today

```
  OHLCV → Indicators → Fixed Fuzzy (dead zones) → MLP → Predict Return ≈ 0
                                                              │
                                    BROKEN ◀─────────────────┘
```

### After Phase 1

```
  OHLCV → Indicators → Fixed Fuzzy (dead zones) → MLP → Classify TB Outcome
                                                              │
                        TB labeling creates learnable target   │
                        Training pipeline upgraded             │
                        Classification > regression ──────────┘
```

### After Phase 2

```
  OHLCV → Indicators → Gaussian Fuzzy (no dead zones) ─┐
                    └── Raw Normalized ─────────────────┤→ MLP → Classify TB
                                                        │
            Hybrid encoding eliminates blind spots       │
            Ruspini partition satisfied ─────────────────┘
```

### After Phase 3

```
  OHLCV → Indicators ─┬── Regime Classifier ──── Route
                       ├── Context Classifier ─── Gate
                       ├── Primary Rules ──────── SIDE (BUY/SELL candidate)
                       └── Gaussian Fuzzy + Raw ─┐
                                                  │
                            Meta-Labeler ◀────────┘
                            P(profitable) → position size
                                    │
                        Context gate adjusts threshold
                                    │
                            Execute with sized position
```

### After Phase 4

```
  OHLCV → Indicators ─┬── Regime Classifier ──── Route
                       ├── Context Classifier ─── Gate
                       ├── Primary Rules ──────── SIDE
                       └── Raw Values ──┐
                                        │
                            ┌───────────┘
                            ▼
                    LEARNABLE FUZZY LAYER
                    (μ, σ trained end-to-end)
                    Data-discovered partitions
                            │
                            ▼
                    META-LABELER (MLP or LightGBM)
                    P(profitable) → position size
                            │
                    Context gate adjusts threshold
                            │
                    Execute with sized position
```

---

## 9. Critical Assessment: What Might NOT Work

### 9.1 Triple Barrier Labels Might Not Help If Indicators Truly Carry No Signal

**Risk:** Our empirical experiments showed r = -0.032 between ADX and forward returns. Triple barrier labels have higher SNR than forward returns, but if the indicators don't predict path-dependent outcomes either, the model still won't learn.

**Mitigation:** Experiment 1 tests this directly. If triple barrier accuracy is still ~50% with current features, we know the indicators are truly uninformative and must change features (add cross-asset, microstructure, or alternative data).

**Honest assessment:** There IS theoretical reason to believe indicators predict TB outcomes better than point-in-time returns. ATR captures the volatility that determines barrier width. RSI captures the momentum that determines whether price hits TP or SL first. MACD captures trend strength which determines directional persistence. These are exactly the properties TB labels encode. But theory isn't proof — the experiments will tell us.

### 9.2 Meta-Labeling Requires a Primary Model with Edge

**Risk:** If our rule-based primary model (RSI oversold → BUY) has ~50% directional accuracy, meta-labeling cannot improve it. You can't filter randomness into signal.

**Mitigation:** Our regime classifier works at 69-79%. "Trade with the trend in trending regimes" (momentum) and "mean-revert in ranging regimes" are the two most robust edges in financial markets. The primary model should have genuine directional accuracy if regime classification is correct.

**Honest assessment:** Even if the primary model has 55% accuracy, meta-labeling should improve risk-adjusted returns by filtering the 45% of false positives. The key question is whether 55% accuracy after costs translates to positive expected value. With EURUSD forex costs at ~2 pips round trip, we need sufficient edge per trade.

### 9.3 Learnable MFs Might Overfit on Small Datasets

**Risk:** Adding learnable MF parameters (2 per set × 4 sets × 6 indicators = 48 extra parameters) on a dataset of ~10,000-20,000 bars could overfit. Especially with the CUSUM filter reducing the effective sample size further.

**Mitigation:**
- Regularize MF parameters (L2 penalty on deviation from init values)
- Dropout on fuzzy layer (randomly zero-out memberships during training)
- Separate learning rate for MF params (slower than NN weights)
- Monitor train/val gap closely
- Compare learned MFs across different train windows (stability check)

### 9.4 The Whole Approach Might Be Wrong

**Risk:** Maybe fuzzy-neural on standard TA indicators is simply not a viable approach for FX trading, regardless of labeling or MF design. The literature suggests tree-based models on raw features outperform NNs on tabular financial data.

**Mitigation:** Phase 3's meta-labeler experiment includes a LightGBM variant. If LightGBM significantly outperforms the MLP meta-labeler, we should consider making trees the default for tabular features and reserving NNs for sequence models (LSTM on raw price) or image models (CNN on chart patterns).

**Honest assessment:** The fuzzy-neural approach adds interpretability (we can inspect MF parameters and understand what the model "thinks" about RSI levels). This interpretability is valuable for the research model (the agent can reason about learned MFs). But if the approach doesn't produce positive Sharpe, interpretability is cold comfort. We should be ready to pivot to trees if the experiments demand it.

### 9.5 Backtesting Bias

**Risk:** All our experiments are backtests. Even with proper purged CV and triple barrier labels, backtesting is prone to overfitting. A strategy that produces Sharpe 1.0 in backtests might produce Sharpe 0.0 live.

**Mitigation:**
- Use a strictly held-out test set (2025 data, never seen during development)
- Walk-forward validation (retrain monthly, test on the next month)
- Report results across multiple currency pairs (not just EURUSD)
- Track the number of experiments run (more experiments = higher multiple-testing risk)

---

## 10. Implementation Priority and Dependencies

```
Phase 1: Fix the Target
  ├── TripleBarrierLabeler                    [new file, ~200 LOC]
  ├── CUSUMFilter                             [new file, ~80 LOC]
  ├── UniquenessWeighting                     [new file, ~100 LOC]
  ├── Training pipeline: mini-batch + early stopping  [modify mlp.py]
  ├── Training pipeline: LR scheduling        [modify mlp.py]
  ├── Training pipeline: focal loss           [new loss class]
  ├── Strategy YAML: source: triple_barrier   [modify training_pipeline.py]
  ├── DecisionFunction: classification path   [already exists, verify]
  └── Autoresearch harness update             [modify harness.py if needed]

Phase 2: Fix the Features (can partially overlap with Phase 1)
  ├── Gaussian MF in strategy YAMLs           [YAML change only]
  ├── 3+ sets per indicator                   [YAML change only]
  ├── Hybrid encoding in FuzzyNeuralProcessor [modify ~20 LOC]
  ├── Raw indicator normalization             [new utility, ~50 LOC]
  ├── Strategy YAML: raw_indicator nn_input   [modify models.py]
  └── FeatureResolver: handle raw indicators  [modify feature_resolver.py]

Phase 3: Meta-Labeling (depends on Phase 1)
  ├── PrimarySignalGenerator                  [new file, ~150 LOC]
  ├── MetaLabeler model                       [new model class, ~200 LOC]
  ├── LightGBM meta-labeler variant           [new file, ~150 LOC]
  ├── PositionSizer                           [new file, ~80 LOC]
  ├── Ensemble runner: meta-label integration [modify ensemble_runner.py]
  ├── Strategy YAML: primary + meta sections  [modify models.py]
  └── Autoresearch: two-section YAML support  [modify program.md]

Phase 4: Learnable MFs (depends on Phase 2 + 3)
  ├── LearnableFuzzyLayer (torch.nn.Module)   [new file, ~250 LOC]
  ├── Percentile-based initialization         [new utility, ~50 LOC]
  ├── Ruspini softmax enforcement             [in LearnableFuzzyLayer]
  ├── MF parameter logging/visualization      [new utility, ~100 LOC]
  ├── Strategy YAML: learnable: true          [modify models.py]
  ├── Training: joint MF+NN optimization      [modify training pipeline]
  └── Per-regime learnable MFs                [extend LearnableFuzzyLayer]
```

---

## 11. Success Criteria

### Phase 1 Success

- [ ] Triple barrier labeler produces labels with class distribution within 20/60/20 to 40/20/40 range
- [ ] Model val accuracy > 55% (above the no-information rate for 3 classes)
- [ ] Hidden layer activations are non-zero (model uses features, not just bias)
- [ ] Backtest Sharpe > 0.3 on validation window (2024)
- [ ] Autoresearch agent can search barrier parameters and find improving configurations

### Phase 2 Success

- [ ] Zero dead-zone bars across all indicators
- [ ] Val accuracy improves vs Phase 1 baseline (same labels, better features)
- [ ] Hybrid encoding outperforms fuzzy-only (or demonstrates equivalence, validating fuzzy)

### Phase 3 Success

- [ ] Meta-labeler precision > 60% (majority of taken trades are profitable)
- [ ] Sharpe > 0.5 on validation window
- [ ] Position sizing produces risk-adjusted improvement vs fixed sizing
- [ ] Autoresearch agent independently discovers useful primary rules

### Phase 4 Success

- [ ] Learned MF parameters differ meaningfully from expert initialization
- [ ] Val accuracy improves vs fixed MFs
- [ ] Learned MFs are stable across different training windows (not overfit artifacts)
- [ ] Per-regime MFs show interpretable specialization

### Overall Success (across all phases)

- [ ] Held-out test set (2025) Sharpe > 0.3
- [ ] Results replicate on at least 2 additional currency pairs
- [ ] Autoresearch agent produces consistently improving strategies
- [ ] The system can identify when it's NOT finding edge (knows when to stop trading)

---

## 12. References

### Academic
- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. — Triple barrier method, meta-labeling, CUSUM filter, purged CV, uniqueness weighting
- Jang, J.-S. R. (1993). *ANFIS: Adaptive-Network-Based Fuzzy Inference System*. IEEE Trans. Systems, Man, Cybernetics. — Learnable membership functions
- Ruspini, E. H. (1969). *A new approach to clustering*. Information and Control. — Partition of unity constraint

### Practical Resources
- [Hudson & Thames: Meta-Labeling Signal Efficacy](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/)
- [mlfinlab Documentation: Triple Barrier and Meta-Labeling](https://www.mlfinlab.com/en/latest/labeling/tb_meta_labeling.html)
- [DataFrame-Ready Triple Barrier Implementation](https://www.ostirion.net/post/dataframe-ready-implementation-for-triple-barrier-labels)
- [pytorch-fuzzy: Differentiable Fuzzy Layers for PyTorch](https://github.com/kenoma/pytorch-fuzzy)
- [fracdiff: Fractional Differentiation Package](https://github.com/fracdiff/fracdiff)
- [triple-barrier PyPI Package](https://pypi.org/project/triple-barrier/)
- [RiskLabAI: Labeling Financial Data](https://www.risklab.ai/research/financial-data-science/labeling)

### ktrdr Internal
- `docs/designs/predictive-features/INTENT.md` — Original predictive features intent document
- `docs/designs/predictive-features/implementation/HANDOFF_M8.md` — M8 context gate findings
- `autoresearch/program.md` (PR #352) — Autonomous strategy research framework
