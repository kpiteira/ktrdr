# Forward-Return Regression: Fixing the Substrate

## What We Want to Build

A **regression-based prediction mode** for the training and backtesting pipeline, alongside the existing 3-class classification. Instead of predicting BUY/HOLD/SELL, the model predicts a scalar: the expected forward return over the next N bars. Trading decisions are then made by comparing that prediction against a cost-aware threshold.

This separates **perception** ("what's about to happen?") from **decision** ("should I trade?"). The NN's job becomes prediction, not action selection.

---

## Why Now

A deep investigation on 2026-03-06 traced the root cause of universal ~10% backtest win rates across all strategies. The findings are structural — not bugs we can patch, but fundamental problems with how the system frames the prediction task.

### Investigation Findings

| Finding | Evidence | Impact |
|---|---|---|
| ZigZag labeling is degenerate | Model never predicts HOLD (0 out of 115,229 bars). Segment labeling marks <1% of bars as HOLD. | 3-class classification collapses to 2-class |
| Confidence is uncalibrated | Higher confidence = slightly worse accuracy (47% at all thresholds) | Confidence filtering is meaningless |
| Training accuracy != trade profitability | 64% accuracy, 37% win rate, 10% after config bug | The metric we optimize doesn't predict what we care about |
| Thin edge destroyed by costs | Pre-cost: +0.1 pip/trade. Post-cost: -1.3 pip/trade. Need ~33 pip edge. | Cost-blind prediction is useless for trading |
| Architecture is undersized | 803 parameters, [32, 16] hidden layers | No capacity headroom |

### Why Classification Is the Wrong Framing

The current pipeline asks: "at each bar, should we BUY, HOLD, or SELL?" This has three structural problems:

1. **HOLD is the wrong kind of class.** HOLD isn't a positive prediction — it's the absence of opportunity. Treating it as a class to predict creates a severe imbalance problem that no labeling trick can fully fix.

2. **All classes are not equal.** BUY and SELL are expensive actions (costs ~0.3% round-trip). HOLD is free. The loss function treats misclassifying HOLD-as-BUY the same as BUY-as-SELL, but the real-world cost is completely different.

3. **Magnitude matters.** "The market will go up 2%" and "the market will go up 0.1%" both map to BUY, but only one is tradeable after costs. Classification discards magnitude.

Regression solves all three: HOLD emerges naturally when predicted returns are too small. Cost-awareness is structural, not ad-hoc. Magnitude is the output.

---

## Prior Thinking (Read These)

The investigation report is the primary context:
- `~/.claude/projects/.../memory/notes/2026-03-06-backtest-investigation.md` — Full 6-phase investigation trail with evidence tables, root cause analysis, and cost math

The evolution docs provide the broader vision (paused, not abandoned):
- `docs/agentic/evolution/BRAINSTORM.md` — "Baby forever" problem, selection pressure
- `docs/agentic/evolution/03_synthesis_researcher_genome_evolution.md` — Phylogeny model, researcher genomes
- `docs/agentic/evolution/04_primordial_soup_experiment_design.md` — v0 experiment (blocked by broken substrate)

---

## The Design

### Core Change

**Today:**
```
Features → NN (3 outputs) → softmax → argmax → BUY/HOLD/SELL → confidence filter → trade
```

**Proposed:**
```
Features → NN (1 output) → predicted return (float) → cost-aware threshold → BUY/HOLD/SELL → trade
```

### What the Model Predicts

Forward simple return: `(close[t+horizon] - close[t]) / close[t]`

- Single horizon, configurable (default: 20 bars)
- Raw return, not normalized — directly comparable to cost thresholds
- On EURUSD 1h, typical values: [-0.03, +0.03]

### Labels

New `ForwardReturnLabeler`:
- Input: price data DataFrame + horizon (int)
- Output: Series of float returns (not integer classes)
- Every bar gets a label (except last `horizon` bars which are dropped)
- Distribution is naturally symmetric around 0 — no class imbalance by construction

### Loss Function

Huber loss (smooth L1) — robust to fat-tailed return distributions:
```python
criterion = nn.HuberLoss(delta=huber_delta)  # default delta=0.01
```

The `delta` parameter (configurable in strategy YAML) controls where L1 kicks in. At 0.01 (1% return), the model optimizes MSE for normal moves and L1 for extreme moves.

### Model Architecture

Output layer: 1 neuron, no activation (raw linear output).

```python
if output_format == "regression":
    layers.append(nn.Linear(prev_size, 1))
else:
    layers.append(nn.Linear(prev_size, 3))  # existing classification
```

Default architecture suggestion increased to [64, 32] minimum.

### Decision Function

The trading rule is explicit about costs:

```python
threshold = cost_model.round_trip_cost * cost_model.min_edge_multiplier

if predicted_return > threshold:
    signal = BUY
elif predicted_return < -threshold:
    signal = SELL
else:
    signal = HOLD
```

Where:
- `round_trip_cost` = known cost (commission + slippage, ~0.003)
- `min_edge_multiplier` = how much edge above cost to demand (learnable, default 1.5)
- Actual threshold = 0.003 * 1.5 = 0.0045 (0.45% minimum predicted move)

The `min_edge_multiplier` becomes a genome dimension for evolution: higher = conservative (fewer trades, higher conviction), lower = aggressive (more trades, thinner edge).

### Cost Model in Strategy YAML

```yaml
decisions:
  output_format: regression
  cost_model:
    round_trip_cost: 0.003
    min_edge_multiplier: 1.5
  filters:
    min_signal_separation: 4
  position_awareness: true
```

### Confidence

In regression, the magnitude of the predicted return IS the signal strength. There's no separate "confidence" concept. For backward compatibility with TradingDecision, we set:
- `confidence = abs(predicted_return) / normalizer` (cosmetic, maps to ~[0, 1])
- The trading rule uses predicted return directly, not confidence

### Training Metrics

| Classification (existing) | Regression (new) |
|---|---|
| Accuracy | Directional accuracy (sign match %) |
| CrossEntropyLoss | HuberLoss / MSE |
| Per-class precision/recall | MSE, MAE, R-squared |
| Confusion matrix | Predicted vs actual scatter |

### Gate System

Minimal safety net (the real evaluation is the assessment agent):
- Directional accuracy > 50% (better than coin flip)
- Net return after costs > 0 in test set
- Minimum trade count (didn't just abstain)

### Assessment Agent

The assessment agent is an LLM — it doesn't need normalized metrics. It needs context:
- `output_format: regression` (so it knows what it's looking at)
- Training metrics: MSE, MAE, R², directional accuracy
- Backtest metrics: Sharpe, drawdown, win rate, profit factor (same as today)
- The `cost_model` configuration (so it can reason about cost-awareness)

The LLM can then reason about quality holistically rather than checking thresholds.

### Look-Ahead Bias Fix (Execution Realism)

Pre-existing issue, fixed as part of this work:
- **Current** (biased): features at bar t close → execute at bar t close
- **Fixed** (realistic): features at bar t close → execute at bar t+1 open

This applies to both classification and regression modes.

### Backward Compatibility

All classification code remains untouched. Regression is a parallel path selected by `output_format: regression` in strategy YAML. Existing strategies continue to work exactly as before.

---

## Milestones

### M1: Regression Substrate
Train and backtest with forward returns. The minimum viable regression pipeline.

- ForwardReturnLabeler (new file)
- Model architecture: 1 output, Huber loss
- Training pipeline: `source: forward_return` label path
- Decision function: regression mode with cost-aware threshold
- Strategy YAML validation for regression config
- E2E: manually train + backtest a regression strategy

### M2: Assessment + Agent Integration
The system can evaluate regression strategies and run autonomous research cycles.

- Regression training metrics (directional accuracy, R², MSE)
- Regression-aware gate (minimal safety net)
- Assessment prompt with regression context
- Design prompt update for regression
- E2E: full autonomous research cycle with regression

### M3: Execution Realism
Fix look-ahead bias. Makes results trustworthy.

- Next-bar execution in backtest engine
- Update tests that depend on same-bar execution
- Standardize slippage defaults across engine/worker/API
- Re-run regression baseline with realistic execution

---

## Future Genome Dimensions (for evolution, not this build)

Once the regression substrate is working, these become tunable by the evolution system:

| Dimension | Range | What It Controls |
|---|---|---|
| `horizon` | 5, 10, 20, 50 | How far ahead to predict |
| `min_edge_multiplier` | 1.2 — 3.0 | How selective the trading rule is |
| `huber_delta` | 0.005 — 0.02 | Loss function sensitivity to outliers |
| `hidden_layers` | [32,16] — [128,64,32] | Model capacity |
| `dropout` | 0.1 — 0.4 | Regularization strength |

---

## What This Enables

With a working regression substrate:
1. The primordial soup experiment can run on organisms that aren't all born dead
2. Evolution can discover the right horizon, edge multiplier, and architecture
3. The assessment agent can evaluate strategies by what matters: profitability after costs
4. The "Baby forever" problem has a structural path forward — prediction quality improves → edge grows → costs are overcome → strategies survive selection

The evolution vision (researcher genomes, guided selection, capability accumulation) is paused but not abandoned. This work fixes the substrate it needs to stand on.

---

## Future Phases: Classification Reimagined

The current 3-class BUY/HOLD/SELL classification is structurally broken and becomes the non-recommended path. But classification as a concept has legitimate future value in two different framings, both planned as follow-on work after the regression substrate is stable.

### Phase 2 (future): Binary Opportunity Filter

**Problem**: The regression model predicts a return for every bar, including the ~90% that are genuinely unpredictable noise. It wastes capacity on bars where no prediction is meaningful.

**Solution**: A binary classifier that learns to identify **moments worth trading** — "opportunity" vs "no-opportunity."

**Labeling**: Bars where absolute forward return exceeds 2x round-trip cost are labeled "opportunity" (1). Everything else is "no-opportunity" (0). This gives ~10-15% positive class — imbalanced but well-handled by weighted BCE loss.

**Architecture options**:
- Separate small model (fast, cheap inference, independently trainable)
- Shared backbone with two heads (opportunity sigmoid + return linear)
- Same model with additional output neuron

**Decision flow**:
```
Features -> Opportunity model: P(opportunity) = 0.82
         -> Regression model: predicted_return = +0.8%

If P(opportunity) > opportunity_threshold
   AND predicted_return > cost_threshold:
    -> BUY
```

The opportunity model handles **when** to trade. The regression model handles **how much** and **which direction**. This separates timing from sizing/direction.

**Evolution dimension**: `opportunity_sensitivity` — how aggressive or conservative the filter is. Conservative organisms trade rarely with high conviction. Aggressive ones trade more often with thinner edge.

**Why this matters**: HOLD becomes the default state (no opportunity detected), not a class the model fails to predict. The classifier only needs to identify exceptional moments — a much more natural framing than predicting three competing classes.

### Phase 3 (future): Regime Classification

**Problem**: Market behavior changes. Trending markets reward momentum. Ranging markets reward mean-reversion. The regression model sees the same fuzzy features regardless of context — it doesn't know which regime it's operating in.

**Solution**: A regime classifier whose output becomes an **input** to the regression model, not a trading signal.

**Labeling**: Derived from market characteristics computed over a rolling window:
- ATR relative to price (volatility level)
- ADX or trend strength measure
- Possible regimes: trending_up, trending_down, ranging, volatile (4 classes)
- Or simpler: trending vs ranging (2 classes)

**Usage**: Regime prediction is fed as additional features to the regression model:
```
[fuzzy_rsi_oversold, ..., regime_trending, regime_ranging, regime_volatile]
```

Or more powerfully: the regime conditions the regression model's behavior. In "trending" regime, the model learns to predict larger continuations. In "ranging" regime, it predicts mean reversions.

**Evolution dimension**: Organisms that develop regime awareness would demonstrate a genuine capability jump — the "new sensory capability" from the biological evolution analogy in the synthesis doc. This is the kind of structural capability that can't emerge from just tuning indicators.

**Why this matters**: This maps directly to the evolutionary transition in the vision docs — from single-cell (one model, one context) to multicellular (specialized components working together). The regime classifier is a specialized "sensory organ" that enriches the regression model's perception.

### How the Three Phases Compose

```
Phase 1 (regression only):
  Features -> Regression model -> cost threshold -> trade

Phase 2 (+ opportunity filter):
  Features -> Opportunity filter -> only if "yes":
           -> Regression model -> cost threshold -> trade

Phase 3 (+ regime context):
  Features -> Regime classifier -> regime embedding
           -> Opportunity filter (regime-aware) -> only if "yes":
           -> Regression model (regime-conditioned) -> cost threshold -> trade
```

Each phase adds a new capability without replacing the previous one. The regression substrate is the foundation that Phases 2 and 3 build on. This is why getting regression right matters before anything else.

### Future Idea: Variable-Horizon Prediction (Multi-Task Learning)

Emerged during design discussion about label truncation. The basic labeler drops the last N bars because the horizon shrinks. But what if variable horizon was a *feature*, not a limitation?

**Concept**: A model that takes horizon as an explicit input — "given these features, what's the return over N bars?" — trained on multiple horizons simultaneously.

```
Input: [fuzzy_rsi_oversold, fuzzy_macd_bullish, ..., horizon=20]  -> predict 20-bar return
Input: [fuzzy_rsi_oversold, fuzzy_macd_bullish, ..., horizon=5]   -> predict 5-bar return
```

The same model learns to predict at multiple timescales. This is multi-task learning — the shared representation benefits from seeing both short-term and long-term patterns. A model that can predict both 5-bar and 50-bar returns has genuinely richer market understanding than one fixed to a single horizon.

**Why this could be powerful for evolution**: The genome wouldn't just pick ONE horizon — it could learn which horizons to query at inference time. A conservative organism queries horizon=50 (fewer trades, larger moves). An aggressive one queries horizon=5 (more trades, smaller moves). Or even: query both, and only trade when short-term and long-term agree.

Not planned for any current phase — capturing for future exploration.
