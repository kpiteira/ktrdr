---
design: docs/designs/forward-return-regression/DESIGN.md
architecture: docs/designs/forward-return-regression/ARCHITECTURE.md
---

# M1: Regression Substrate

The minimum viable regression pipeline. A regression strategy can be trained and backtested end-to-end with cost-aware trading decisions.

## Task 1.1: ForwardReturnLabeler

**File(s):** Create `ktrdr/training/forward_return_labeler.py`, create `tests/unit/training/test_forward_return_labeler.py`
**Type:** CODING

**Description:**
New labeler that computes forward simple returns: `(close[t+horizon] - close[t]) / close[t]`. Returns a float Series of length `len(data) - horizon` (last `horizon` bars dropped because no future data exists).

**Implementation Notes:**
- Class with `__init__(self, horizon: int = 20)` and `generate_labels(self, price_data: pd.DataFrame) -> pd.Series`
- Also add `get_label_statistics(self, labels: pd.Series) -> dict` returning mean, std, min, max, pct_positive, pct_negative
- Raise `DataError` if data has fewer than `horizon + 1` bars
- Guard against zero close price (division check)
- Follow existing pattern: ZigZagLabeler in `ktrdr/training/zigzag_labeler.py`

**Testing Requirements:**
- [ ] Correct return calculation on known data (manually computed expected values)
- [ ] Output length is `len(data) - horizon`
- [ ] Horizon=1 produces simple 1-bar returns
- [ ] Horizon=len(data)-1 produces single label
- [ ] DataError raised when data too short
- [ ] get_label_statistics returns correct stats
- [ ] NaN in close column propagates correctly (NaN in output, not crash)

**Acceptance Criteria:**
- [ ] ForwardReturnLabeler produces correct float labels
- [ ] All edge cases handled with tests
- [ ] No dependency on any other M1 task

---

## Task 1.2: MLPTradingModel Regression Support

**File(s):** Modify `ktrdr/neural/models/mlp.py`, create `tests/unit/neural/test_mlp_regression.py`
**Type:** CODING

**Description:**
Add regression mode to MLPTradingModel. When `output_format == "regression"`: build 1-output model (no activation), use Huber/MSE loss, compute directional accuracy instead of argmax accuracy.

**Implementation Notes:**
- `build_model()` (line ~52): branch on `self.config.get("output_format", "classification")` — 1 output for regression, 3 for classification
- `train()` (line ~101): branch loss function — `nn.HuberLoss(delta=config.get("huber_delta", 0.01))` or `nn.MSELoss()` for regression, `nn.CrossEntropyLoss()` for classification
- `train()` (line ~146): keep labels as float for regression (don't `y.long()`)
- `train()` (line ~161): directional accuracy for regression: `(sign(output) == sign(label)).mean()`
- Output squeeze: regression output is `(batch, 1)`, squeeze to `(batch,)` before loss
- The `output_format` config key must be passed into the model config dict by the caller (TrainingPipeline, Task 1.4)

**Testing Requirements:**
- [ ] build_model produces 1-output Sequential for regression
- [ ] build_model produces 3-output Sequential for classification (unchanged)
- [ ] Regression training with Huber loss runs without error
- [ ] Regression training with MSE loss runs without error
- [ ] Directional accuracy computed correctly (known predictions vs known labels)
- [ ] Float labels accepted (no .long() conversion)
- [ ] Default behavior (no output_format) remains classification

**Acceptance Criteria:**
- [ ] Regression model builds and trains with correct loss
- [ ] Classification path completely unchanged
- [ ] Directional accuracy metric reported during training

---

## Task 1.3: ModelTrainer Regression Support

**File(s):** Modify `ktrdr/training/model_trainer.py`, create `tests/unit/training/test_model_trainer_regression.py`
**Type:** CODING

**Description:**
Add regression mode to ModelTrainer (the production training path used by the host service). Same branching as Task 1.2 but in the production training loop.

**Implementation Notes:**
- `train()` method (line ~289): branch loss function on `self.config.get("output_format", "classification")`
- Same Huber/MSE selection as MLPTradingModel
- Metric calculation (line ~380-408): branch accuracy computation — directional accuracy for regression
- Label tensor type: regression labels must stay FloatTensor, classification uses LongTensor
- Gradient clipping, early stopping, LR scheduling all apply unchanged to regression
- Progress reporting: report `directional_accuracy` instead of `accuracy` for regression
- Checkpoint resume: must handle regression model (1 output) correctly

**Testing Requirements:**
- [ ] ModelTrainer trains regression model with Huber loss
- [ ] ModelTrainer trains regression model with MSE loss
- [ ] Directional accuracy reported in training metrics
- [ ] Classification training unchanged (regression test)
- [ ] Early stopping works with regression loss
- [ ] Progress callback receives regression metrics

**Acceptance Criteria:**
- [ ] Production training path supports regression
- [ ] Metrics reported correctly for regression
- [ ] No classification behavior changes

---

## Task 1.4: TrainingPipeline Integration

**File(s):** Modify `ktrdr/training/training_pipeline.py`, add tests in `tests/unit/training/test_training_pipeline_regression.py`
**Type:** CODING

**Description:**
Wire ForwardReturnLabeler into TrainingPipeline.create_labels(). Handle feature-label alignment (truncation). Inject `output_format` into model config so downstream components know the mode.

**Implementation Notes:**
- `create_labels()` (line ~460): branch on `label_config.get("source", "zigzag")`
  - `"forward_return"`: use ForwardReturnLabeler, return FloatTensor
  - `"zigzag"` (default): existing path, return LongTensor
- **Critical**: feature-label alignment. ForwardReturnLabeler returns `N - horizon` labels. Features must be truncated to match: `features = features[:len(labels)]`. This truncation happens HERE, not in the labeler. Add clear logging: `"Truncated features from {N} to {N-horizon} to match forward return labels (horizon={horizon})"`
- Inject `output_format` from strategy config into the model config dict before calling model build/train. Read from `strategy_config["decisions"]["output_format"]`, inject into model config.
- Also inject `loss`, `huber_delta` from strategy training config if present.
- The V3 training pipeline (`_execute_v3_training` code path) is the one that matters — trace through it to find where to inject.

**Testing Requirements:**
- [ ] create_labels returns FloatTensor for source="forward_return"
- [ ] create_labels returns LongTensor for source="zigzag" (unchanged)
- [ ] Feature tensor truncated to match label length
- [ ] Truncation logged
- [ ] output_format injected into model config
- [ ] Default source is "zigzag" when not specified

**Acceptance Criteria:**
- [ ] Forward return labels generated in training pipeline
- [ ] Feature-label alignment correct (no shape mismatch errors)
- [ ] output_format flows from strategy YAML to model config

---

## Task 1.5: DecisionFunction Regression Path

**File(s):** Modify `ktrdr/backtesting/decision_function.py`, create `tests/unit/backtesting/test_decision_function_regression.py`
**Type:** CODING

**Description:**
Add regression inference path to DecisionFunction. Instead of softmax+argmax, read the raw model output as predicted return and compare against cost-aware threshold.

**Implementation Notes:**
- Constructor: read `output_format` from decisions_config. If regression, compute `trade_threshold = round_trip_cost * min_edge_multiplier` from `cost_model` sub-dict.
- `_predict()` (line ~146): branch on output_format
  - Regression: `predicted_return = float(outputs[0, 0])`, threshold comparison -> BUY/SELL/HOLD
  - Classification: existing softmax+argmax (unchanged)
- Cosmetic confidence: `min(abs(predicted_return) / (3 * trade_threshold), 1.0)` — maps typical predictions to [0, 1] range
- Return dict includes `predicted_return` key for regression (useful for logging/debugging)
- `_apply_filters()`: skip confidence threshold filter for regression (cost threshold already applied in _predict). Signal separation and position awareness still apply.
- Use existing Signal enum (BUY, HOLD, SELL) — no changes to PositionManager interface

**Testing Requirements:**
- [ ] Predicted return > threshold -> BUY signal
- [ ] Predicted return < -threshold -> SELL signal
- [ ] Predicted return between -threshold and +threshold -> HOLD signal
- [ ] Threshold = round_trip_cost * min_edge_multiplier (verify calculation)
- [ ] Cosmetic confidence in [0, 1] range
- [ ] Confidence filter skipped in regression mode
- [ ] Signal separation filter still applied
- [ ] Position awareness filter still applied
- [ ] Classification path unchanged
- [ ] Default (no output_format) behaves as classification

**Acceptance Criteria:**
- [ ] Cost-aware threshold produces correct BUY/SELL/HOLD signals
- [ ] Regression predictions drive trading decisions
- [ ] Classification inference completely unchanged

---

## Task 1.6: Strategy Validation + Model Metadata

**File(s):** Modify `ktrdr/config/strategy_validator.py`, modify `ktrdr/backtesting/model_bundle.py`, add tests
**Type:** CODING

**Description:**
Strategy validator accepts regression config. Model bundle saves and loads output_format + cost_model in config.json.

**Implementation Notes:**

Strategy validator (`strategy_validator.py`):
- `decisions.output_format`: must be "classification" or "regression" (default: "classification")
- If regression: `decisions.cost_model` required with `round_trip_cost` (float > 0) and `min_edge_multiplier` (float > 0)
- If regression: `training.labels.source` should be "forward_return"
- If regression: `training.labels.horizon` required (positive integer)
- If regression: `training.loss` optional, must be "huber" or "mse"
- If regression: warn if `decisions.confidence_threshold` present (it's ignored)
- Follow existing validation patterns in the file

Model bundle (`model_bundle.py`):
- `reconstruct_config_from_metadata()` already passes decisions_config from config.json (fixed in recent commit)
- Verify that `output_format`, `cost_model` survive the save->load round trip
- Verify config.json written during training includes these fields

**Testing Requirements:**
- [ ] Valid regression strategy config passes validation
- [ ] Missing cost_model in regression mode rejected
- [ ] Invalid output_format rejected
- [ ] Missing horizon for forward_return labels rejected
- [ ] Classification config still validates (unchanged)
- [ ] Warning when confidence_threshold present in regression mode
- [ ] output_format round-trips through config.json save/load
- [ ] cost_model round-trips through config.json save/load

**Acceptance Criteria:**
- [ ] Regression strategies validated correctly
- [ ] Invalid configs rejected with helpful errors
- [ ] Model metadata preserves regression config

---

## Task 1.7: Example Strategy + Integration Test

**File(s):** Create `strategies/regression_example_v3.yaml`, create `tests/integration/test_regression_pipeline.py`
**Type:** CODING

**Description:**
Create an example regression strategy YAML and an integration test that trains and backtests it end-to-end.

**Implementation Notes:**

Example strategy (`strategies/regression_example_v3.yaml`):
```yaml
version: "3"
training_data:
  symbols: ["EURUSD"]
  timeframes: ["1h"]
  date_range: { start: "2024-01-01", end: "2025-03-01" }
indicators:
  rsi_14: { type: rsi, timeframe: "1h", params: { period: 14 } }
  macd_12_26_9: { type: macd, timeframe: "1h", params: { fast: 12, slow: 26, signal: 9 } }
fuzzy_sets:
  rsi_oversold: { indicator: rsi_14, type: low, params: [20, 30, 40] }
  rsi_overbought: { indicator: rsi_14, type: high, params: [60, 70, 80] }
  macd_bullish: { indicator: macd_12_26_9.line, type: high, params: [-0.005, 0, 0.005] }
  macd_bearish: { indicator: macd_12_26_9.line, type: low, params: [-0.005, 0, 0.005] }
nn_inputs: [rsi_oversold, rsi_overbought, macd_bullish, macd_bearish]
decisions:
  output_format: regression
  cost_model:
    round_trip_cost: 0.003
    min_edge_multiplier: 1.5
training:
  labels:
    source: forward_return
    horizon: 20
  loss: huber
  huber_delta: 0.01
  epochs: 50
  hidden_layers: [64, 32]
  learning_rate: 0.001
  dropout: 0.2
```

Integration test:
- Load strategy, validate config
- Generate forward return labels from sample price data
- Build regression model (1 output)
- Train for a few epochs (fast, not full training)
- Run predictions through DecisionFunction
- Verify: BUY only when predicted return > threshold, SELL < -threshold, HOLD otherwise
- Verify: trade count is reasonable (not every bar, not zero)
- This is NOT an E2E test against running containers — it's an in-process integration test

**Testing Requirements:**
- [ ] Strategy YAML parses and validates
- [ ] Labels generated as float Series
- [ ] Model trains without error
- [ ] DecisionFunction produces cost-filtered signals
- [ ] At least some HOLD signals (cost threshold filtering works)
- [ ] Signal types are valid (BUY/HOLD/SELL only)

**Acceptance Criteria:**
- [ ] Example strategy demonstrates all regression config fields
- [ ] Integration test proves the full in-process pipeline works
- [ ] A human can follow the example to create their own regression strategy

---

## Task 1.8: E2E Validation

**File(s):** No new files — validation against running infrastructure
**Type:** VALIDATION

**Description:**
Validate M1 end-to-end: train a regression strategy via CLI, backtest it via CLI, verify cost-aware trading behavior.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke ke2e-test-scout with M1 validation requirements:
   - Train regression strategy via `ktrdr models train strategies/regression_example_v3.yaml EURUSD 1h --start-date 2024-01-01 --end-date 2025-03-01`
   - Backtest trained model via `ktrdr backtest run <strategy_name> EURUSD 1h --start-date 2025-03-01 --end-date 2025-06-01`
   - Verify model saved with `output_format: regression` in config.json
   - Verify backtest produces trades (not zero) but not every bar (cost filtering works)
   - Verify backtest results include predicted_return in trade metadata
3. Invoke ke2e-test-runner with identified test recipes
4. Tests must exercise real running infrastructure (training worker, backtest worker)
5. Tests that use mocks or seeded data without real external calls are integration tests, not E2E

**Acceptance Criteria:**
- [ ] Regression strategy trains successfully via CLI
- [ ] Trained model has correct output_format in saved metadata
- [ ] Backtest produces cost-filtered trades (some HOLD decisions)
- [ ] No regression in classification strategy behavior
