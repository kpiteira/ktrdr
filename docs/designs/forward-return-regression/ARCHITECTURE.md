# Forward-Return Regression: Architecture

## Component Overview

```
+---------------------------+     +---------------------------+
|   Strategy YAML (v3)      |     |   ForwardReturnLabeler    |
|  output_format: regression|     |  (close[t+h]-close[t])/   |
|  cost_model: {...}        |     |   close[t]                |
|  labels.source:           |---->|  Returns: float Series    |
|    forward_return         |     +---------------------------+
|  labels.horizon: 20      |                |
+---------------------------+                v
            |                    +---------------------------+
            |                    |   TrainingPipeline        |
            |                    |  create_labels() branches |
            |                    |  on labels.source         |
            |                    +---------------------------+
            |                                |
            v                                v
+---------------------------+     +---------------------------+
|   MLPTradingModel         |     |   ModelTrainer            |
|  build_model():           |     |  Loss: HuberLoss/MSE     |
|    regression: 1 output   |     |  Labels: FloatTensor     |
|    classification: 3 out  |     |  Metrics: dir. accuracy  |
+---------------------------+     +---------------------------+
            |                                |
            v                                v
+---------------------------+     +---------------------------+
|   Model Storage           |     |   MetricsCollector        |
|  weights + metadata +     |     |  regression: R2, MAE,     |
|  config.json (has         |     |    directional accuracy   |
|  output_format)           |     |  classification: F1, acc  |
+---------------------------+     +---------------------------+
            |
            v
+---------------------------+     +---------------------------+
|   ModelBundle.load()      |     |   Gate System             |
|  Reads output_format      |---->|  regression: dir_acc>50%, |
|  from config.json         |     |    net_return > 0         |
+---------------------------+     |  classification: acc>10%  |
            |                     +---------------------------+
            v
+---------------------------+
|   DecisionFunction        |
|  regression: threshold    |
|    = cost * multiplier    |
|    predicted > threshold  |
|    -> BUY                 |
|  classification: softmax  |
|    -> argmax -> Signal    |
+---------------------------+
            |
            v
+---------------------------+     +---------------------------+
|   BacktestEngine          |     |   Assessment Agent        |
|  Execute at t+1 open      |     |  Receives output_format   |
|  (look-ahead fix)         |     |  + regression metrics     |
|  Signal enum interface    |     |  + backtest results       |
+---------------------------+     |  LLM reasons about quality|
            |                     +---------------------------+
            v
+---------------------------+
|   PositionManager         |
|   (unchanged)             |
|   Signal -> Trade         |
+---------------------------+
```

---

## Component Details

### ForwardReturnLabeler

**New file**: `ktrdr/training/forward_return_labeler.py`

**Responsibility**: Generate float return labels from price data.

**Interface**:
```python
class ForwardReturnLabeler:
    def __init__(self, horizon: int = 20):
        ...

    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate forward return labels.

        Args:
            price_data: DataFrame with 'close' column

        Returns:
            Series of float returns. Length = len(price_data) - horizon.
            Last `horizon` rows have no label (no future data).
        """

    def get_label_statistics(self, labels: pd.Series) -> dict:
        """Return distribution stats: mean, std, min, max, % positive, % negative."""
```

**Label calculation**:
```python
close = price_data['close']
returns = (close.shift(-horizon) - close) / close
returns = returns.dropna()  # last `horizon` bars have no label
```

**Edge cases**:
- Insufficient data (< horizon + 1 bars): raise DataError
- Missing close values: propagate NaN, drop in training pipeline
- Zero close price: impossible for real market data, but guard with division check

### TrainingPipeline Changes

**File**: `ktrdr/training/training_pipeline.py`

**Change**: `create_labels()` static method gains a branch.

```python
@staticmethod
def create_labels(price_data, label_config) -> torch.Tensor:
    source = label_config.get("source", "zigzag")

    if source == "forward_return":
        horizon = label_config.get("horizon", 20)
        labeler = ForwardReturnLabeler(horizon=horizon)
        labels = labeler.generate_labels(tf_price_data)
        label_tensor = torch.FloatTensor(labels.values)  # float, not long
    else:
        # existing zigzag path (unchanged)
        labeler = ZigZagLabeler(...)
        labels = labeler.generate_segment_labels(tf_price_data)
        label_tensor = torch.LongTensor(labels.values)

    return label_tensor
```

**Critical alignment**: When labels are shorter than features (last `horizon` bars dropped), features must be truncated to match. This truncation happens here, not in the labeler.

### MLPTradingModel Changes

**File**: `ktrdr/neural/models/mlp.py`

**Change in `build_model()`**:
```python
def build_model(self, input_size: int) -> nn.Module:
    ...
    output_format = self.config.get("output_format", "classification")
    if output_format == "regression":
        layers.append(nn.Linear(prev_size, 1))
    else:
        layers.append(nn.Linear(prev_size, 3))
    return nn.Sequential(*layers)
```

**Change in `train()`**:
```python
output_format = self.config.get("output_format", "classification")
if output_format == "regression":
    loss_type = self.config.get("loss", "huber")
    if loss_type == "huber":
        huber_delta = self.config.get("huber_delta", 0.01)
        criterion = nn.HuberLoss(delta=huber_delta)
    else:
        criterion = nn.MSELoss()
    # Labels stay as float, squeeze output to match
    # Metrics: directional accuracy instead of argmax accuracy
else:
    criterion = nn.CrossEntropyLoss()
    y = y.long()
    # Metrics: standard accuracy
```

**Note**: The `output_format` must be passed through config. The model config dict in strategy YAML doesn't currently have this field — it comes from `decisions.output_format`. The training pipeline must inject it into the model config before calling `build_model()`.

### ModelTrainer Changes

**File**: `ktrdr/training/model_trainer.py`

**Change in `train()` method (line ~289)**:

Same branching as MLPTradingModel.train() — loss function selection and metric calculation. The ModelTrainer is the production training path (host service uses this), while MLPTradingModel.train() is the simpler in-process path.

```python
# Loss function selection
output_format = self.config.get("output_format", "classification")
if output_format == "regression":
    loss_type = self.config.get("loss", "huber")
    if loss_type == "huber":
        criterion = nn.HuberLoss(delta=self.config.get("huber_delta", 0.01))
    else:
        criterion = nn.MSELoss()
else:
    criterion = nn.CrossEntropyLoss()
```

**Metric calculation change** (replaces argmax accuracy):
```python
if output_format == "regression":
    # Directional accuracy: % where sign(predicted) == sign(actual)
    pred_sign = (outputs.squeeze() > 0).float()
    actual_sign = (batch_y > 0).float()
    train_correct += (pred_sign == actual_sign).sum().item()
else:
    _, predicted = torch.max(outputs.data, 1)
    train_correct += (predicted == batch_y).sum().item()
```

### DecisionFunction Changes

**File**: `ktrdr/backtesting/decision_function.py`

**New constructor parameter**:
```python
def __init__(self, model, feature_names, decisions_config):
    ...
    self.output_format = decisions_config.get("output_format", "classification")

    if self.output_format == "regression":
        cost_model = decisions_config.get("cost_model", {})
        self.round_trip_cost = cost_model.get("round_trip_cost", 0.003)
        self.min_edge_multiplier = cost_model.get("min_edge_multiplier", 1.5)
        self.trade_threshold = self.round_trip_cost * self.min_edge_multiplier
    else:
        self.confidence_threshold = decisions_config.get("confidence_threshold", 0.5)
```

**New `_predict()` branch**:
```python
def _predict(self, features):
    ...
    with torch.no_grad():
        outputs = self.model(tensor)

    if self.output_format == "regression":
        predicted_return = float(outputs[0, 0].cpu().numpy())

        if predicted_return > self.trade_threshold:
            signal = Signal.BUY
        elif predicted_return < -self.trade_threshold:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        # Cosmetic confidence for TradingDecision compatibility
        confidence = min(abs(predicted_return) / (3 * self.trade_threshold), 1.0)

        return {
            "signal": signal,
            "confidence": confidence,
            "predicted_return": predicted_return,
            "probabilities": {  # backward compat, less meaningful for regression
                "BUY": max(predicted_return, 0) / self.trade_threshold,
                "HOLD": 0.0,
                "SELL": max(-predicted_return, 0) / self.trade_threshold,
            },
        }
    else:
        # existing softmax + argmax path (unchanged)
        ...
```

**Filter changes**: In regression mode, the confidence threshold filter is replaced by the cost threshold (already applied in `_predict`). Signal separation and position awareness filters still apply.

### BacktestEngine Changes (Look-Ahead Fix)

**File**: `ktrdr/backtesting/engine.py`

**Change in main loop**:
```python
pending_signal = None
pending_metadata = None

for idx in range(start_idx, len(data)):
    bar = data.iloc[idx]
    timestamp = cast(pd.Timestamp, bar.name)

    # Execute pending signal from previous bar at this bar's open
    if pending_signal is not None:
        open_price = bar["open"]
        trade = self.position_manager.execute_trade(
            signal=pending_signal,
            price=open_price,
            timestamp=timestamp,
            symbol=self.config.symbol,
            decision_metadata=pending_metadata,
        )
        if trade:
            last_signal_time = timestamp
        pending_signal = None
        pending_metadata = None

    # Decide based on current bar (features use this bar's close)
    close_price = bar["close"]
    features = self.feature_cache.get_features_for_timestamp(timestamp)
    if features is not None:
        decision = self.decide(
            features=features,
            position=self.position_manager.current_position_status,
            bar=bar,
            last_signal_time=last_signal_time,
        )

        if decision.signal != Signal.HOLD:
            pending_signal = decision.signal
            pending_metadata = {"confidence": decision.confidence}

    # Track at close price (mark-to-market)
    self.position_manager.update_position(close_price, timestamp)
    ...
```

**Edge case**: Last bar of backtest with a pending signal — force-close handles this already.

### MetricsCollector Changes

**File**: `ktrdr/training/analytics/metrics_collector.py`

**New regression metrics**:
```python
def collect_regression_metrics(self, y_true, y_pred):
    """Collect regression-specific metrics.

    Returns dict with: mse, mae, r_squared, directional_accuracy,
    profitable_direction_accuracy, mean_predicted_return, std_predicted_return
    """
```

The existing `collect_epoch_metrics()` branches on output_format to call either classification metrics (precision/recall/F1) or regression metrics (R2/MAE/directional accuracy).

### Gate System Changes

**File**: `ktrdr/agents/gates.py`

**New regression gate config**:
```python
@dataclass
class GateConfig:
    # Classification gates (existing)
    min_accuracy: float = 0.10

    # Regression gates (new)
    min_directional_accuracy: float = 0.50  # must beat coin flip
    min_net_return: float = 0.0  # must not lose money on test set
    min_trades: int = 5  # must actually trade
```

**Gate check branches on output_format**:
```python
if output_format == "regression":
    dir_acc = test_metrics.get("directional_accuracy", 0)
    if dir_acc < config.min_directional_accuracy:
        return (False, f"Directional accuracy {dir_acc:.1%} below minimum")
    ...
else:
    accuracy = test_metrics.get("test_accuracy", 0)
    if accuracy < config.min_accuracy:
        return (False, f"Accuracy {accuracy:.1%} below minimum")
```

### Strategy Validation Changes

**File**: `ktrdr/config/strategy_validator.py`

**Extended validation for regression**:
- `decisions.output_format` must be "classification" or "regression"
- If regression: `decisions.cost_model` required with `round_trip_cost` and `min_edge_multiplier`
- If regression: `training.labels.source` should be "forward_return"
- If regression: `training.labels.horizon` required (positive integer)
- If regression: `training.loss` optional, must be "huber" or "mse"
- If regression: `decisions.confidence_threshold` ignored (warn if present)

### Assessment Prompt Changes

**File**: `ktrdr/agents/prompts.py`

The assessment prompt receives `output_format` in context and additional guidance:

```
When evaluating a REGRESSION strategy (output_format: regression):
- The model predicts forward returns, not BUY/HOLD/SELL classes
- Key training metrics: R-squared (variance explained), directional accuracy
  (sign prediction accuracy), MAE (average absolute prediction error)
- The trading rule only acts when predicted return exceeds a cost threshold
- A model with modest R-squared but good directional accuracy can still be
  profitable if the cost threshold filters effectively
- Consider the relationship between trade count and selectivity — fewer
  trades with higher win rate may be better than many trades with thin edge
```

### Design Prompt Changes

**File**: `ktrdr/agents/design_sdk_prompt.py`

Add regression mode documentation and example. Key additions:
- `output_format: regression` option
- `labels.source: forward_return` with `horizon` parameter
- `cost_model` configuration
- `loss: huber` option
- Guidance: "Use [64, 32] or larger architectures for regression"

---

## Data Flow

### Training (regression path)

```
1. Strategy YAML loaded
   - output_format: regression
   - labels: {source: forward_return, horizon: 20}
   - loss: huber, huber_delta: 0.01

2. TrainingPipeline.load_market_data()
   - Same as classification

3. TrainingPipeline.calculate_indicators()
   - Same as classification

4. TrainingPipeline.generate_fuzzy_memberships()
   - Same as classification

5. TrainingPipeline.create_features()
   - Same as classification
   - Returns: feature_tensor (N x F)

6. TrainingPipeline.create_labels()
   - NEW PATH: ForwardReturnLabeler
   - Returns: FloatTensor (N - horizon)
   - Features truncated to match: feature_tensor[:N-horizon]

7. Train/val/test split
   - Same as classification

8. ModelTrainer.train() or MLPTradingModel.train()
   - Output layer: 1 neuron
   - Loss: HuberLoss(delta=0.01)
   - Labels: FloatTensor (not LongTensor)
   - Metrics: directional accuracy, MSE

9. Model saved
   - config.json includes output_format, cost_model, loss config
   - metadata includes feature names (same as classification)
```

### Inference (regression path)

```
1. ModelBundle.load()
   - Reads output_format from config.json
   - Passes to DecisionFunction

2. DecisionFunction.__init__()
   - Sets trade_threshold = round_trip_cost * min_edge_multiplier

3. DecisionFunction._predict(features)
   - Forward pass: model(tensor) -> single float
   - Apply threshold: > threshold -> BUY, < -threshold -> SELL, else HOLD
   - Return signal + cosmetic confidence + predicted_return

4. DecisionFunction._apply_filters()
   - Skip confidence filter (threshold already applied)
   - Apply signal separation (same)
   - Apply position awareness (same)

5. BacktestEngine main loop
   - NEW: pending signal executed at next bar's open
   - PositionManager.execute_trade() receives Signal enum (unchanged)
```

---

## State and Lifecycle

No new persistent state. The `output_format` travels through:

```
Strategy YAML
  -> StrategyConfigurationV3 (parsed config)
    -> TrainingPipeline (determines label type, loss function)
    -> config.json (saved with model)
      -> ModelBundle.load() (reads it back)
        -> DecisionFunction (determines inference behavior)
```

This is a **configuration-driven branch**, not a runtime state machine. The output_format is fixed at strategy design time and never changes during training or inference.

---

## Error Handling

### New error cases

| Error | When | Handling |
|---|---|---|
| Insufficient data for horizon | price_data has fewer than horizon+1 bars | Raise DataError with context |
| Invalid output_format | YAML has unknown value | Strategy validator rejects |
| Missing cost_model for regression | regression mode without cost config | Strategy validator rejects with helpful error |
| Feature-label length mismatch | Truncation not applied correctly | Assert in training pipeline, fail fast |
| Model output shape mismatch | 1-output model loaded in classification mode | Check output shape in DecisionFunction, raise |

### Preserved error handling

All existing error handling (NaN detection, gradient explosion, feature ordering) remains unchanged. The regression path inherits these protections.

---

## Integration Points

### What changes

| Component | Nature of change | Risk |
|---|---|---|
| ForwardReturnLabeler | New file, no dependencies | Low |
| TrainingPipeline.create_labels() | New branch, existing code untouched | Low |
| MLPTradingModel.build_model() | One conditional for output size | Low |
| MLPTradingModel.train() | Loss + metrics branching | Medium (two training paths) |
| ModelTrainer.train() | Same as above | Medium |
| DecisionFunction._predict() | New inference path | Medium (must match training) |
| BacktestEngine loop | Execution timing change | High (affects all results) |
| MetricsCollector | New metrics type | Low |
| Gates | New threshold type | Low |
| Strategy validator | New validation rules | Low |

### What doesn't change

| Component | Why unchanged |
|---|---|
| IndicatorEngine | Features are the same for both modes |
| FuzzyEngine | Fuzzy memberships are the same |
| FuzzyNeuralProcessor | Feature tensor preparation is the same |
| FeatureCache | Pre-computation is output-format agnostic |
| PositionManager | Operates on Signal enum, doesn't know about output_format |
| PerformanceTracker | Calculates from trades, not predictions |
| Model storage | Format-agnostic (weights + metadata + config.json) |

---

## Testing Strategy

### Unit tests (per component)

| Component | Key test cases |
|---|---|
| ForwardReturnLabeler | Correct returns, edge cases (short data, horizon=1), statistics |
| MLPTradingModel | 1-output model builds, trains with Huber, regression metrics correct |
| DecisionFunction | Threshold logic, BUY/SELL/HOLD boundaries, cosmetic confidence |
| TrainingPipeline | Feature-label alignment after truncation |
| MetricsCollector | Directional accuracy, R-squared calculation |
| Gates | Regression gate pass/fail |
| Strategy validator | Accept valid regression config, reject invalid |

### Integration tests

| Test | What it validates |
|---|---|
| Train regression model | Full pipeline: labels -> features -> model -> saved weights |
| Backtest regression model | Load model -> predict -> threshold -> trades |
| Next-bar execution | Decision at bar t executes at bar t+1 open |

### E2E tests

| Milestone | E2E test |
|---|---|
| M1 | Manually create regression strategy, train, backtest, verify cost-aware trades |
| M2 | Trigger autonomous research cycle with regression, assessment agent evaluates |
| M3 | Run same strategy with/without look-ahead fix, verify degraded (realistic) results |
