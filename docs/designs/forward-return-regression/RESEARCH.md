# Forward-Return Regression: Deep Research

This document captures all research, code analysis, and investigation findings that inform the design. Written 2026-03-06 after a deep investigation session and comprehensive codebase exploration.

---

## 1. Investigation: Why All Strategies Get ~10% Win Rate

### Executive Summary

Every ktrdr strategy produces ~10% backtest win rate despite 64% training accuracy. A 6-phase investigation traced the root cause to a config preservation bug AND fundamental structural problems with the prediction framing.

### Phase 1: Signal Chain Verification

Traced the complete chain: ZigZag labels -> model training -> softmax/argmax -> _SIGNAL_MAP -> PositionManager.

**Result**: Signal chain correctly wired. BUY=0, HOLD=1, SELL=2 throughout.
- `_SIGNAL_MAP = {0: Signal.BUY, 1: Signal.HOLD, 2: Signal.SELL}` in `decision_function.py:29`
- No signal inversion bug.

### Phase 2: Model Behavior Analysis

Loaded a trained model and ran inference on 115,229 bars of EURUSD 1h data.

| Class | Predicted % | Mean Confidence |
|---|---|---|
| BUY | 36.8% | 0.737 |
| HOLD | 0.0% | N/A |
| SELL | 63.2% | 0.644 |

**Critical finding**: Model NEVER predicts HOLD. Zero times across 115,229 bars. It's a degenerate 2-class classifier with strong SELL bias (nearly 2:1 vs BUY).

Architecture: 6 inputs -> [32, 16] -> 3 outputs. Only 803 parameters.

### Phase 3: Feature Pipeline Verification

Computed features manually and via FeatureCache. Results identical (6/6 match). Feature ordering is consistent: training pipeline reorders to canonical order (line 982-983 in training_pipeline.py), FeatureCache reorders to resolved_features (line 157).

Fuzzy membership functions are deterministic and stateless. Same config = same output.

**Not the problem.**

### Phase 4: MACD Fuzzy Boundary Analysis

- MACD line range on EURUSD 1h: [-0.016, 0.018]
- Fuzzy boundaries span [-0.01, 0.01] -- covers ~95% of values
- Memberships are reasonable: bearish/bullish ~19%, neutral ~30%

**Not the problem.**

### Phase 5: Trade Simulation vs Actual Backtest

This is where the discrepancy became clear:

| Scenario | Trades | Win Rate | Notes |
|---|---|---|---|
| Simulation: conf=0.6, 2020-2021, no costs | 87 | 36.8% | Intended behavior |
| Simulation: conf=0.6, 2020-2021, with costs | 87 | 27.6% | Costs reduce wins |
| Simulation: conf=0.5, 2020-2021, with costs | 247 | 16.6% | BUG behavior |
| Actual experiment result | 246 | 10.6% | Matches bug trade count |

Trade count 247 vs 246 was the smoking gun -- the bug was lowering the confidence threshold.

### Phase 6: Root Cause Found

**Bug**: `reconstruct_config_from_metadata()` in `model_bundle.py:150` hardcoded:
```python
decisions={"output_format": "classification"}
```

This drops the strategy's actual decisions config. DecisionFunction defaults to `confidence_threshold=0.5` instead of the intended 0.6.

**Why 0.5 is catastrophic**: Model's minimum confidence is ~0.500. A threshold of 0.5 lets EVERY prediction through. Since the model never predicts HOLD, every bar triggers a trade -- including the weakest, near-random signals.

**Fix applied**: `model_bundle.py` now passes decisions/model/training config from config.json. Committed 2026-03-06.

---

## 2. Deeper Analysis: Even With Bug Fixed, Strategy Doesn't Work

### The Math

With the config bug fixed (threshold=0.6):
- Win rate with costs: 27.6% (87 trades over 2020-2021)
- Win/loss ratio: 1.75x (avg win 0.0092 vs avg loss -0.0053)
- Breakeven win rate for 1.75x ratio: 1/(1+1.75) = 36.4%
- Per-trade expectancy: -0.00128 (negative)

Without costs:
- Win rate: 36.8%
- Win/loss ratio: 2.53x
- Per-trade expectancy: +0.00106 (positive but thin)

**The model captures a real but thin edge (~1 pip/trade pre-cost). Round-trip costs of ~15 pips (0.05% slippage + 0.1% commission per side) destroy this edge completely.**

### Confidence Does NOT Correlate with Accuracy

| Confidence Threshold | BUY next-bar up% | SELL next-bar down% |
|---|---|---|
| >= 0.4 | 47.5% | 47.9% |
| >= 0.6 | 47.6% | 47.1% |
| >= 0.8 | 46.3% | 46.4% |

All below 50% (worse than coin flip). Higher confidence = slightly worse accuracy. The model's softmax probabilities are not calibrated -- they reflect learned class biases, not prediction quality.

### Training Accuracy vs Trade Win Rate Gap

- Training accuracy: 64% (bar-level classification -- "did we predict the ZigZag label correctly?")
- Trade win rate: ~37% (round-trip profitability -- "did we make money between BUY and SELL?")

These measure fundamentally different things. ZigZag labels reflect multi-bar trends (1.5% moves over 20 bars), not single-bar direction. The model can be 64% right about the eventual trend direction but wrong about timing and magnitude.

### Cost Structure Sets a Hard Floor

With 0.1% commission + 0.05% slippage per side (0.3% round-trip):
- On EURUSD at ~1.08: 0.3% = ~32 pips round-trip cost
- Strategies need ~33 pip expected profit per trade to be profitable
- Current model edge: ~1 pip pre-cost

This requires either:
- Much higher conviction (wider edge per trade)
- Longer hold times (fewer trades, more profit per trade)
- Lower-cost execution (reduce commission/slippage params)

---

## 3. Current Labeling System: Deep Code Analysis

### ZigZag Labeler (`ktrdr/training/zigzag_labeler.py`)

Two labeling methods:

**Method 1: `generate_labels()` (sparse)**
- Scans each bar, looks ahead up to `lookahead` bars
- Labels BUY if price rises by `threshold%` AND gain > loss
- Labels SELL if price falls by `threshold%` AND loss > gain
- Labels HOLD for everything else (default)
- Requires `min_swing_length` bars before extreme is reached
- **Problem**: Most bars get HOLD. BUY/SELL are rare events.

**Method 2: `generate_segment_labels()` (currently used)**
- Uses `ZigZagIndicator` to find price extremes
- Labels entire segments between extremes: upward = BUY, downward = SELL
- Only the extreme points themselves get HOLD
- **Problem**: HOLD is now <1% of labels. Overcorrected the imbalance.

### ZigZag Indicator (`ktrdr/indicators/zigzag_indicator.py`)

The `get_zigzag_segment_labels()` method (lines 178-227):
- Computes ZigZag line connecting significant reversals
- With threshold=2.5% on 1h EURUSD: ~30-50 extremes per year of data (~6,500 bars)
- Extreme points = HOLD labels = 30-50 out of 6,500 bars = <1%
- All other bars labeled BUY or SELL based on segment direction

### Label Config in Strategy YAML

All existing strategies use identical config:
```yaml
training:
  labels:
    source: zigzag
    zigzag_threshold: 0.025   # 2.5% price swing
    label_lookahead: 20       # not used by segment method
```

The `label_lookahead` parameter is only used by `generate_labels()` (sparse method), not by `generate_segment_labels()` which is actually called. This is a dead parameter in current usage.

### Training Pipeline Label Creation (`training_pipeline.py:413-477`)

```python
@staticmethod
def create_labels(price_data, label_config):
    labeler = ZigZagLabeler(
        threshold=label_config["zigzag_threshold"],
        lookahead=label_config["label_lookahead"],
    )
    # Uses segment-based labeling
    labels = labeler.generate_segment_labels(tf_price_data)
    label_tensor = torch.LongTensor(labels.values)
    return label_tensor
```

Key: this is the ONLY entry point for label generation. Adding `source: forward_return` means adding an `if` branch here.

---

## 4. Current Model Architecture: Deep Code Analysis

### MLPTradingModel (`ktrdr/neural/models/mlp.py`)

```python
class MLPTradingModel(BaseNeuralModel):
    def build_model(self, input_size):
        layers = []
        prev_size = input_size
        for hidden_size in hidden_layers:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                activation_fn(),
                nn.Dropout(dropout),
            ])
            prev_size = hidden_size
        # HARDCODED: 3 classes
        layers.append(nn.Linear(prev_size, 3))
        return nn.Sequential(*layers)
```

Output is always 3 neurons. No softmax in the model (CrossEntropyLoss applies it internally).

### Training Loop (`mlp.py:101-185`)

Simple training loop (used by `mlp.py` directly -- the host service uses `model_trainer.py` instead):
```python
criterion = nn.CrossEntropyLoss()  # No class weights
y = y.long()  # Integer labels required

for epoch in range(epochs):
    outputs = self.model(X)
    loss = criterion(outputs, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    _, predicted = torch.max(outputs.data, 1)
    accuracy = (predicted == y).float().mean()
```

No class weighting. No balanced sampling. Plain CrossEntropyLoss.

### Production Training Loop (`model_trainer.py:289+`)

The actual training loop used by the host service:
```python
criterion = nn.CrossEntropyLoss()  # Also no class weights

# Has gradient clipping (default 1.0)
torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)

# Has early stopping, learning rate scheduling
# Has batch-level progress reporting
# Has checkpoint support for resume
```

Same unweighted CrossEntropyLoss. More sophisticated training mechanics but same fundamental loss.

---

## 5. Current Decision Pipeline: Deep Code Analysis

### DecisionFunction (`ktrdr/backtesting/decision_function.py`)

Stateless: (features, position, bar, last_signal_time) -> TradingDecision

**Inference flow** (`_predict()`, lines 123-168):
```python
def _predict(self, features):
    # Build tensor in feature_names order
    values = [features[name] for name in self.feature_names]
    tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        outputs = self.model(tensor)

    # Softmax (manual, with numerical stability)
    exp_outputs = np.exp(raw_outputs - np.max(raw_outputs))
    probs = exp_outputs / np.sum(exp_outputs)

    signal_idx = int(np.argmax(probs))
    confidence = float(probs[signal_idx])

    return {
        "signal": _SIGNAL_MAP[signal_idx],  # {0: BUY, 1: HOLD, 2: SELL}
        "confidence": confidence,
        "probabilities": {"BUY": probs[0], "HOLD": probs[1], "SELL": probs[2]},
    }
```

**Filters** (`_apply_filters()`, lines 170-230):
1. Confidence threshold: `if confidence < self.confidence_threshold: return HOLD`
2. Signal separation: minimum hours between consecutive trades
3. Position awareness: no redundant BUY when LONG, no SELL from FLAT (no shorting in MVP)

### BaseNeuralModel.predict() (`base_model.py:172-220`)

Alternative inference path (not used in backtesting but used elsewhere):
- Also assumes 3-class output
- Has collapse detection logging (checks if one class dominates)
- Returns same dict structure with "BUY", "HOLD", "SELL" probabilities

---

## 6. Current Cost Model: Deep Code Analysis

### PositionManager (`ktrdr/backtesting/position_manager.py`)

Trade execution with costs:

**BUY order:**
```
execution_price = price * (1 + slippage)          # pays worse price
trade_value = execution_price * quantity
commission_cost = trade_value * commission_rate
total_cost = trade_value + commission_cost         # deducted from capital
```

**SELL order:**
```
execution_price = price * (1 - slippage)           # receives worse price
trade_value = execution_price * quantity
commission_cost = trade_value * commission_rate
net_proceeds = trade_value - commission_cost        # added to capital
```

**Position sizing**: Fixed 25% of available capital per trade.

### Cost Configuration Inconsistencies

| Component | Commission | Slippage | Location |
|---|---|---|---|
| BacktestConfig (engine.py) | 0.1% | 0.05% | Default in dataclass |
| Backtest worker | 0.1% | 0.0% | Worker defaults |
| API service | 0.1% | 0.1% | Endpoint parameter default |

Three different slippage defaults depending on execution path. The worker defaults to ZERO slippage, which is unrealistic.

### Look-Ahead Bias

**Current flow** (`engine.py:203-229`):
```python
for idx in range(start_idx, len(data)):
    bar = data.iloc[idx]
    price = bar["close"]                    # <-- uses close price
    features = self.feature_cache.get_features_for_timestamp(timestamp)
    decision = self.decide(features=features, ...)
    trade = self.position_manager.execute_trade(signal=decision.signal, price=price, ...)
```

Features computed using bar's close price, trade executed at same close price. In reality, the close price is unknown until the bar closes, and execution would happen at the next bar's open.

Documented in `docs/developer/backtesting-issues.md` as highest priority issue.

---

## 7. Full Touchpoint Map: What Changes for Regression

### CRITICAL (must change for regression to work)

| File | Line(s) | What | Change |
|---|---|---|---|
| `ktrdr/neural/models/mlp.py` | 52-53 | Output layer hardcoded to 3 | Branch: 1 for regression, 3 for classification |
| `ktrdr/neural/models/mlp.py` | 135 | `nn.CrossEntropyLoss()` | Branch: `nn.HuberLoss()` for regression |
| `ktrdr/neural/models/mlp.py` | 146 | `y = y.long()` | Branch: keep float for regression |
| `ktrdr/neural/models/mlp.py` | 161-162 | `torch.max` for accuracy | Branch: directional accuracy for regression |
| `ktrdr/backtesting/decision_function.py` | 29 | `_SIGNAL_MAP` | Regression doesn't use this |
| `ktrdr/backtesting/decision_function.py` | 146-168 | `_predict()` softmax + argmax | Branch: raw output + threshold for regression |
| `ktrdr/training/training_pipeline.py` | 460-469 | `create_labels()` ZigZag only | Branch: ForwardReturnLabeler for `source: forward_return` |

### HIGH (needed for full pipeline)

| File | Line(s) | What | Change |
|---|---|---|---|
| `ktrdr/training/model_trainer.py` | 289 | `nn.CrossEntropyLoss()` | Branch: `nn.HuberLoss()` for regression |
| `ktrdr/training/model_trainer.py` | 380-408 | accuracy = argmax match | Branch: directional accuracy |
| `ktrdr/training/analytics/metrics_collector.py` | 23 | `class_names = ["BUY", "HOLD", "SELL"]` | Skip class metrics for regression |
| `ktrdr/training/analytics/metrics_collector.py` | 146 | sklearn precision_recall_fscore | Branch: MSE, MAE, R-squared |
| `ktrdr/agents/gates.py` | 86-93 | Gate checks `test_accuracy` | Branch: directional accuracy for regression |
| `ktrdr/agents/gates.py` | 32-34 | `min_accuracy: float = 0.10` | Add regression gate config |
| `ktrdr/config/strategy_validator.py` | 93-97 | DECISIONS_REQUIRED schema | Allow regression-specific fields |
| `ktrdr/backtesting/engine.py` | 205-222 | Execute at close price | Fix: execute at next bar open |

### MEDIUM (needed for agent integration)

| File | Line(s) | What | Change |
|---|---|---|---|
| `ktrdr/agents/design_sdk_prompt.py` | Full | No regression guidance | Add regression mode documentation |
| `ktrdr/agents/prompts.py` | 315-317 | Example strategy hardcodes zigzag | Add regression example |
| `ktrdr/agents/workers/assessment_agent_worker.py` | 62-66 | Metrics documentation | Add regression context |
| `ktrdr/config/strategy_loader.py` | defaults | Default output_format | Handle regression defaults |
| `ktrdr/backtesting/model_bundle.py` | 73-103 | reconstruct_config | Already fixed -- passes config.json |

### LOW (cosmetic / display)

| File | Line(s) | What | Change |
|---|---|---|---|
| `ktrdr/cli/model_testing_commands.py` | 135-176 | Signal color display | Branch: show predicted return |
| `ktrdr/neural/models/base_model.py` | 172-220 | predict() 3-class logging | Branch: regression logging |

### NEW FILES

| File | Purpose |
|---|---|
| `ktrdr/training/forward_return_labeler.py` | Generate forward return labels |
| `tests/unit/training/test_forward_return_labeler.py` | Unit tests for labeler |
| `strategies/regression_example_v3.yaml` | Example regression strategy |

---

## 8. Data Flow: Classification vs Regression

### Classification (current)

```
OHLCV data
  |-> IndicatorEngine: compute RSI, MACD, etc.
  |-> FuzzyEngine: convert to membership values [0, 1]
  |-> FuzzyNeuralProcessor: build feature tensor (N samples x F features)
  |-> ZigZagLabeler: generate integer labels [0, 1, 2] (N samples)
  |-> MLPTradingModel: 3-output NN, CrossEntropyLoss, LongTensor labels
  |-> Trained model saved with metadata + config.json
  |
  |-> Backtest:
      |-> FeatureCache: pre-compute features
      |-> ModelBundle: load model + metadata
      |-> DecisionFunction._predict(): softmax -> argmax -> Signal enum
      |-> DecisionFunction._apply_filters(): confidence, separation, position
      |-> PositionManager: execute trade at close price
      |-> PerformanceTracker: equity curve, metrics
```

### Regression (proposed)

```
OHLCV data
  |-> IndicatorEngine: compute RSI, MACD, etc.        (SAME)
  |-> FuzzyEngine: convert to membership values [0, 1] (SAME)
  |-> FuzzyNeuralProcessor: build feature tensor       (SAME)
  |-> ForwardReturnLabeler: generate float returns      (NEW)
  |     - (close[t+horizon] - close[t]) / close[t]
  |     - Last `horizon` bars dropped (no label)
  |-> MLPTradingModel: 1-output NN, HuberLoss, FloatTensor labels (CHANGED)
  |-> Trained model saved with metadata + config.json   (SAME format)
  |
  |-> Backtest:
      |-> FeatureCache: pre-compute features             (SAME)
      |-> ModelBundle: load model + metadata              (SAME)
      |-> DecisionFunction._predict(): raw output -> threshold -> Signal (CHANGED)
      |     - predicted_return = model(features)[0]
      |     - threshold = round_trip_cost * min_edge_multiplier
      |     - if predicted_return > threshold: BUY
      |     - if predicted_return < -threshold: SELL
      |     - else: HOLD
      |-> DecisionFunction._apply_filters(): separation, position (SAME)
      |     - confidence filter replaced by threshold (above)
      |-> PositionManager: execute at next bar open       (FIXED)
      |-> PerformanceTracker: equity curve, metrics        (SAME)
```

The feature pipeline (left side) is completely identical. Changes are only in labels, model output, loss function, and decision logic.

---

## 9. Strategy YAML: Regression vs Classification

### Classification (existing)

```yaml
decisions:
  output_format: classification
  confidence_threshold: 0.6
  filters:
    min_signal_separation: 4
  position_awareness: true

training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.025
    label_lookahead: 20
  epochs: 100
  batch_size: 32
  learning_rate: 0.001

model:
  type: mlp
  architecture:
    hidden_layers: [32, 16]
    dropout: 0.2
```

### Regression (proposed)

```yaml
decisions:
  output_format: regression
  cost_model:
    round_trip_cost: 0.003        # known: commission + slippage
    min_edge_multiplier: 1.5      # learnable: demanded edge above cost
  filters:
    min_signal_separation: 4
  position_awareness: true

training:
  method: supervised
  labels:
    source: forward_return
    horizon: 20                    # bars ahead to predict
  loss: huber                      # huber or mse
  huber_delta: 0.01                # transition point for Huber loss
  epochs: 100
  batch_size: 32
  learning_rate: 0.001
  hidden_layers: [64, 32]          # larger default for regression
  dropout: 0.2
```

### Key differences

| Field | Classification | Regression |
|---|---|---|
| `decisions.output_format` | `classification` | `regression` |
| `decisions.confidence_threshold` | 0.6 (softmax prob) | Not used |
| `decisions.cost_model` | Not used | `{round_trip_cost, min_edge_multiplier}` |
| `training.labels.source` | `zigzag` | `forward_return` |
| `training.labels.zigzag_threshold` | 0.025 | Not used |
| `training.labels.horizon` | Not used | 20 |
| `training.loss` | Implicit CrossEntropy | `huber` or `mse` |
| `training.huber_delta` | Not used | 0.01 |
| `training.hidden_layers` | [32, 16] typical | [64, 32] minimum |

---

## 10. Training Metrics: Classification vs Regression

### Classification metrics (existing)

Collected by `MetricsCollector` in `ktrdr/training/analytics/metrics_collector.py`:
- Per-class precision, recall, F1 (using sklearn)
- Overall accuracy (argmax match %)
- Confusion matrix
- Loss (CrossEntropy)
- Class distribution in predictions

### Regression metrics (proposed)

| Metric | Formula | What it tells us |
|---|---|---|
| MSE | mean((predicted - actual)^2) | Overall prediction error |
| MAE | mean(abs(predicted - actual)) | Average absolute error |
| R-squared | 1 - SS_res/SS_tot | Variance explained (>0 is better than mean) |
| Directional accuracy | % where sign(predicted) == sign(actual) | Can the model get direction right? |
| Profitable direction accuracy | % where correct sign AND abs(predicted) > cost | Would correct predictions survive costs? |
| HuberLoss | Training loss value | What the model actually optimized |

### Gate thresholds

| Gate | Classification | Regression |
|---|---|---|
| Minimum quality | accuracy > 10% | directional_accuracy > 50% |
| Profitability | win_rate > 10% | net_return_after_costs > 0 |
| Activity | min_trades > 0 | min_trades >= 5 |

The gate is a safety net. The real evaluation is the assessment agent.

---

## 11. Assessment Agent Context

The assessment agent (`ktrdr/agents/workers/assessment_agent_worker.py`) receives:
- `training_metrics`: dict of training results
- `backtest_results`: dict of backtest performance

For regression, the assessment prompt should include:

**Training context:**
- Output format: regression (forward return prediction)
- Horizon: N bars
- HuberLoss value (lower is better)
- R-squared (>0 means model explains some variance)
- Directional accuracy (>50% means better than random)
- MAE (typical prediction error in return terms)

**Backtest context (same as classification):**
- Total return, Sharpe ratio, max drawdown
- Win rate, profit factor, trade count
- Average win vs average loss

**Cost context:**
- Round-trip cost: X%
- Min edge multiplier: Y
- Effective threshold: X * Y = Z%
- Whether the strategy's average trade exceeds cost

The LLM assessment agent can reason about this holistically -- e.g., "R-squared is low (0.02) but directional accuracy is 54%, and with the conservative edge multiplier of 2.0, the strategy only took 35 trades with a 60% win rate. The model's predictions are noisy but the trading rule effectively filters for high-conviction signals."

---

## 12. Evolution Genome Dimensions

Once the regression substrate works, these become tunable:

| Dimension | Type | Range | Effect |
|---|---|---|---|
| `horizon` | structural | 5, 10, 20, 50 | Prediction timescale |
| `min_edge_multiplier` | behavioral | 1.2 - 3.0 | Trade selectivity |
| `huber_delta` | structural | 0.005 - 0.02 | Loss sensitivity |
| `hidden_layers` | structural | [32,16] to [128,64,32] | Model capacity |
| `dropout` | structural | 0.1 - 0.4 | Regularization |
| `learning_rate` | structural | 0.0001 - 0.01 | Training speed |

The researcher genome (novelty_seeking, skepticism, memory_depth) still controls HOW the researcher designs strategies. These structural dimensions control WHAT it can design. Both matter for evolution, but the structural dimensions are what determine whether the organism can survive at all.

---

## 13. Look-Ahead Bias: Current State and Fix

### Current behavior (`engine.py:203-229`)

```python
for idx in range(start_idx, len(data)):
    bar = data.iloc[idx]
    price = bar["close"]
    features = self.feature_cache.get_features_for_timestamp(timestamp)
    decision = self.decide(features=features, ...)
    if decision.signal != Signal.HOLD:
        trade = self.position_manager.execute_trade(
            signal=decision.signal, price=price, ...)
```

The decision is made using bar t's features (which include bar t's close), and the trade executes at bar t's close price. This means we're using information we wouldn't have until the bar closes, then executing at the exact moment we get it.

### Proposed fix

```python
pending_signal = None
for idx in range(start_idx, len(data)):
    bar = data.iloc[idx]
    open_price = bar["open"]

    # Execute pending signal from previous bar at this bar's open
    if pending_signal is not None:
        trade = self.position_manager.execute_trade(
            signal=pending_signal, price=open_price, ...)
        pending_signal = None

    # Decide based on current bar's features
    close_price = bar["close"]
    features = self.feature_cache.get_features_for_timestamp(timestamp)
    decision = self.decide(features=features, ...)
    if decision.signal != Signal.HOLD:
        pending_signal = decision.signal  # execute next bar
```

This introduces a 1-bar delay: decide at bar t close, execute at bar t+1 open. More realistic.

**Impact**: Will reduce all backtest performance metrics. That's correct -- current metrics are inflated by look-ahead bias.

---

## 14. Cost Configuration: Standardization Needed

The three different slippage defaults are a separate bug:

| Component | Default Slippage |
|---|---|
| BacktestConfig (engine) | 0.05% |
| Backtest worker | 0.0% (unrealistic) |
| API service | 0.1% |

Should be standardized. The worker's 0% slippage means agent-triggered backtests have unrealistically good results. Recommendation: standardize to 0.05% everywhere, configurable via strategy YAML or API parameter.

This is a separate fix from the regression work but worth noting.

---

## 15. Existing Infrastructure That Helps

Things we DON'T need to build:

- **Feature pipeline**: Indicators, fuzzy engine, feature cache all work as-is
- **PositionManager**: Operates on Signal enum, doesn't care how the signal was generated
- **PerformanceTracker**: Calculates metrics from trade history, agnostic to prediction method
- **Model storage**: Saves weights + metadata + config.json, format-agnostic
- **Strategy YAML parsing**: Already flexible dict-based, supports arbitrary fields
- **Assessment agent**: LLM-based, can understand any metric format given context
- **Gate system**: Simple threshold checks, easy to add regression branch
- **Design agent**: LLM-based, can learn regression mode from prompt + examples

The regression change is mostly about the **training output side** (labels, loss, model output) and the **decision input side** (how model output becomes a Signal). Everything in between stays the same.
