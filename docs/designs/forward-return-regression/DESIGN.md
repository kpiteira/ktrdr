# Forward-Return Regression: Design

## Problem Statement

The ktrdr training pipeline uses 3-class classification (BUY/HOLD/SELL) to train neural networks. This framing is structurally broken: ZigZag labeling produces <1% HOLD labels, models collapse to 2-class classifiers, confidence is uncalibrated, and the thin pre-cost edge is destroyed by round-trip costs. We need a regression-based prediction mode where models predict forward returns and trading decisions are made by comparing predictions against cost-aware thresholds.

## Goals

1. Models predict **return magnitude and direction**, not action classes
2. Trading decisions are **explicitly cost-aware** — only trade when predicted edge exceeds known costs
3. HOLD emerges naturally from small predicted returns, not as a failed class prediction
4. The system can train, backtest, and assess regression strategies through the full pipeline
5. Classification code remains functional but regression becomes the primary path
6. The substrate supports future evolution (genome dimensions for horizon, edge multiplier, architecture)

## Non-Goals

- Replacing the feature pipeline (indicators, fuzzy engine, feature cache stay as-is)
- Building a multi-horizon regression system (single horizon for now)
- Implementing the opportunity filter or regime classifier (planned as future phases)
- Optimizing for production trading (backtesting only)
- Changing the PositionManager or trade execution model (beyond look-ahead fix)

---

## Key Decisions

### D1: Output format branching via mode flag

**Decision**: Components check `output_format` from strategy config and branch. No abstract interfaces or strategy pattern.

**Rationale**: We're adding one alternative mode, not building a framework. ~10 branch points across the codebase. If a third mode arrives (Phase 2 opportunity filter), we reassess — but that mode will likely compose with regression rather than replace it, so the branching structure may be different anyway.

### D2: Dynamic cost-aware threshold

**Decision**: Trading threshold = `round_trip_cost * min_edge_multiplier`. The `round_trip_cost` is a known constant. The `min_edge_multiplier` is a learnable parameter (evolution can tune it).

**Rationale**: Separates facts (costs are ~0.3%) from strategy choices (how much edge to demand). A fixed `min_predicted_return` would conflate these and make it hard for the evolution system to reason about cost sensitivity independently.

**Default**: `round_trip_cost: 0.003`, `min_edge_multiplier: 1.5` → threshold of 0.45%.

### D3: Huber loss as default

**Decision**: Use `nn.HuberLoss(delta=huber_delta)` with configurable delta (default 0.01).

**Rationale**: Financial returns have fat tails. MSE lets extreme moves (2-3% in an hour) dominate the loss gradient. Huber transitions to L1 for large errors, giving outliers linear instead of quadratic influence. The delta parameter (1% return) is a reasonable transition point for hourly forex data.

**Alternative considered**: MSE — simpler, but known to be sensitive to outliers in financial data. Available as `loss: mse` option in strategy YAML for experimentation.

### D4: No separate confidence concept

**Decision**: In regression mode, the magnitude of the predicted return IS the signal strength. The `confidence` field in TradingDecision is set to `min(abs(predicted_return) / (3 * threshold), 1.0)` for cosmetic compatibility — the trading rule uses predicted return directly.

**Rationale**: Classification confidence (softmax probability) is a measure of certainty about a categorical choice. Regression has no such concept. Trying to engineer a confidence metric would be artificial. The predicted return magnitude naturally serves as signal strength.

### D5: Minimal gates, rich assessment

**Decision**: The gate system applies minimal binary checks (directional accuracy > 50%, net return > 0, trade count >= 5). The real evaluation is the LLM assessment agent, which receives full regression context.

**Rationale**: Gates are a safety net for obviously broken strategies. The nuanced evaluation — "is this model's R-squared low but its trading rule effective?" — requires judgment, not thresholds. That's what the assessment agent is for.

### D6: Next-bar execution for look-ahead fix

**Decision**: Decisions made at bar t execute at bar t+1's open price. Applied to both regression and classification modes.

**Rationale**: Current behavior (decide and execute at same bar's close) uses information that wouldn't be available in real trading. This is a documented pre-existing bug. Fixing it now ensures regression baseline results are trustworthy from the start.

**Impact**: All backtest performance metrics will degrade. This is correct — current metrics are inflated.

### D7: Classification preserved, regression primary

**Decision**: Classification code stays in place. Regression is the default for new strategies. No effort spent maintaining or improving the 3-class BUY/HOLD/SELL path.

**Rationale**: Classification infrastructure (CrossEntropyLoss, softmax, categorical labels) has future value for the planned opportunity filter (Phase 2) and regime classifier (Phase 3). Both use classification but with completely different class definitions than BUY/HOLD/SELL. Removing and rebuilding later would be more expensive than maintaining the ~10 branch points.

---

## User Scenarios

### S1: Manual regression strategy design and test

A developer writes a v3 strategy YAML with `output_format: regression` and `labels.source: forward_return`. They run `ktrdr models train` and `ktrdr backtest run`. The model trains with Huber loss, predicts returns, and the backtest only trades when predicted returns exceed cost thresholds.

**Expected outcome**: Fewer trades than classification (cost filter removes low-conviction signals), directional accuracy above 50%, and net return closer to zero (rather than deeply negative as with current classification).

### S2: Agent-designed regression strategy

The design agent receives a research brief and creates a regression strategy. The training pipeline handles forward-return labels and Huber loss. The assessment agent evaluates using regression-specific metrics (R-squared, directional accuracy, predicted return distribution) alongside standard backtest metrics.

**Expected outcome**: The agent designs strategies with varying horizons, edge multipliers, and architectures. The assessment agent provides meaningful feedback about prediction quality and cost-effectiveness.

### S3: Evolution with regression substrate

The primordial soup experiment runs with researchers whose genomes include structural dimensions (horizon, min_edge_multiplier, hidden_layers). Selection operates on backtest fitness. Later generations discover effective combinations.

**Expected outcome**: Selection pressure produces organisms that survive costs — something impossible on the classification substrate where all organisms produce strategies with negative expected value.

### S4: Existing classification strategy still works

A developer has an old v3 strategy with `output_format: classification` and `labels.source: zigzag`. It continues to train and backtest exactly as before. No changes needed.

---

## Milestone Structure

### M1: Regression Substrate

The minimum viable regression pipeline. A regression strategy can be trained and backtested end-to-end.

**Scope**:
- ForwardReturnLabeler: generate float return labels from price data
- MLPTradingModel: 1-output architecture, Huber/MSE loss selection
- ModelTrainer: regression training loop with appropriate metrics
- TrainingPipeline: `source: forward_return` label generation path
- DecisionFunction: regression prediction with cost-aware threshold
- Strategy validation: accept regression-specific config fields
- Model metadata: store and load output_format

**E2E test**: Manually create a regression strategy YAML, train it, backtest it, verify trades only occur when predictions exceed cost threshold.

**Not in scope**: Assessment agent, gates, design prompt, CLI display changes.

### M2: Assessment and Agent Integration

The system can evaluate regression strategies and run autonomous research cycles.

**Scope**:
- MetricsCollector: regression metrics (directional accuracy, R-squared, MSE, MAE)
- Gate system: regression-aware safety checks
- Assessment prompt: regression context and evaluation guidance
- Design prompt: teach design agent about regression mode
- Research worker: handle regression-specific result metadata

**E2E test**: Trigger a full autonomous research cycle (design -> train -> backtest -> assess) using regression mode. Assessment agent produces meaningful evaluation.

### M3: Execution Realism

Fix look-ahead bias. Makes backtest results trustworthy.

**Scope**:
- Backtest engine: execute trades at next bar's open, not current bar's close
- Applies to both regression and classification modes
- Update affected tests
- Standardize slippage defaults across engine/worker/API

**E2E test**: Run same regression strategy with and without the fix. Verify the fix produces worse (more realistic) results.

### Future: Phase 2 — Binary Opportunity Filter

Not part of this build. A binary classifier that identifies "trade-worthy moments" to gate the regression signal. Uses classification infrastructure with different class definitions (opportunity/no-opportunity instead of BUY/HOLD/SELL).

### Future: Phase 3 — Regime Classification

Not part of this build. A regime classifier whose output enriches the regression model's input features. Enables context-dependent predictions (trending vs ranging behavior).
