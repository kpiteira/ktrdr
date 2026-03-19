---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M6: Meta-Labeling Enhancement

**Phase:** 3 — Optional Enhancement Layer
**Dependencies:** M5 (Combined Validation) — proceed only if signal model accuracy > 55%
**Branch:** `impl/sme-M6-meta-labeling`

**Prerequisite:** Phase 3 only makes sense if Phases 1-2 produce signal models with >50% directional accuracy. If the signal models still predict randomly after fixing targets and features, meta-labeling cannot create edge from nothing.

---

## Task 6.1: Meta-Labeler Model

**File(s):** `ktrdr/backtesting/meta_labeler.py` (new)
**Type:** CODING
**Estimated time:** 3-4 hours

**Description:**
Create a `MetaLabeler` class that takes a signal model's BUY/SELL candidate and predicts `P(this trade will be profitable)`. The meta-labeler is a separate model trained on the same TB labels but with enriched features (signal model output + indicators + regime + context).

**Implementation Notes:**
- The meta-labeler is a binary classifier: P(profitable) ∈ [0, 1]
- Training data preparation:
  1. Run the signal model (from M5) on training data to get trade candidates
  2. For each candidate, collect: signal model probabilities, indicator values, regime probabilities, context scores
  3. Label: was the actual TB outcome +1 (profitable)? Binary label.
  4. Only train on bars where signal model produced a candidate (BUY or SELL), not HOLD bars
- Model: initially MLP, same architecture pattern as signal models but binary output
- Input features: signal model P(+1), P(-1), plus all indicator features, plus regime probabilities (4), plus context scores (3)
- Output: single neuron with sigmoid → P(profitable)
- `MetaLabeler` follows `ModelBundle` pattern: loadable via same infrastructure
- `output_type: "meta_label"` — new output type for DecisionFunction

**Constructor:**
```python
class MetaLabeler:
    def __init__(self, model: nn.Module, feature_names: list[str], threshold: float = 0.5):
        ...
    def predict(self, features: dict[str, float]) -> dict:
        """Returns {"probability": float, "take_trade": bool, "position_size": float}"""
```

**Testing Requirements:**
- [ ] Test MetaLabeler produces probability output in [0, 1]
- [ ] Test with known-good features: should predict high probability
- [ ] Test with known-bad features: should predict low probability
- [ ] Test threshold: probability > threshold → take_trade = True
- [ ] Test training data preparation: only candidate bars (not HOLD bars) included
- [ ] Test feature vector: includes signal model output + indicators + regime + context
- [ ] Test model saves/loads via existing infrastructure

**Acceptance Criteria:**
- [ ] MetaLabeler produces P(profitable) for each trade candidate
- [ ] Binary classification with sigmoid output
- [ ] Trainable using same `MLPTradingModel` infrastructure (binary output mode)
- [ ] Loadable via ModelBundle with `output_type: "meta_label"`

---

## Task 6.2: Position Sizer

**File(s):** `ktrdr/backtesting/position_sizer.py` (new)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Create a `PositionSizer` that maps meta-labeler probability to position size. Higher confidence → larger position, lower confidence → smaller or zero position.

**Implementation Notes:**
- Simple linear mapping:
  ```python
  class PositionSizer:
      def __init__(self, min_threshold: float = 0.5, max_size: float = 1.0):
          ...
      def size(self, probability: float) -> float:
          if probability < self.min_threshold:
              return 0.0  # don't trade
          # Linear: 0.5 → 0.0, 1.0 → max_size
          return max_size * (probability - self.min_threshold) / (1.0 - self.min_threshold)
  ```
- Also support discrete sizing: full (>0.6), half (>0.5), none (<0.5) — configurable
- Context gate adjusts `min_threshold` via ThresholdModifier (same mechanism as M8)
- Position size is passed to PositionManager for trade execution

**Testing Requirements:**
- [ ] Test probability below threshold → size = 0
- [ ] Test probability at threshold → size = 0 (or small)
- [ ] Test probability = 1.0 → size = max_size
- [ ] Test linear interpolation between threshold and 1.0
- [ ] Test discrete mode: configurable tier boundaries
- [ ] Test context gate adjustment: threshold modified by context

**Acceptance Criteria:**
- [ ] Position sizing maps P(profitable) → trade size
- [ ] Zero size for low-confidence trades
- [ ] Configurable thresholds and sizing mode

---

## Task 6.3: Ensemble Runner Meta-Label Integration

**File(s):** `ktrdr/backtesting/ensemble_runner.py`
**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Extend `EnsembleBacktestRunner._run_bar()` to support meta-labeling: after the signal model produces a BUY/SELL candidate, pass it through the meta-labeler for filtering and sizing before executing the trade.

**Implementation Notes:**
- The meta-labeler is configured in the ensemble YAML as another model:
  ```yaml
  models:
    regime: ...
    context: ...
    trend_signal: ...
    range_signal: ...
    meta_labeler:                    # NEW
      model_path: /path/to/meta_labeler
      output_type: meta_label
  composition:
    meta_labeler: meta_labeler       # NEW: optional field
  ```
- In `_run_bar()`, after signal model produces a decision:
  1. If `composition.meta_labeler` is set and signal is BUY or SELL:
     - Collect meta-labeler features: signal probs, indicators, regime probs, context scores
     - Run meta-labeler: get P(profitable)
     - Run through PositionSizer: get position size
     - If size = 0: override signal to HOLD (trade filtered)
     - Else: pass size to PositionManager
  2. If no meta-labeler configured: behave as before (no filtering, fixed size)
- Context gate adjusts the PositionSizer's threshold (not the signal model's threshold)
- Logging: record which trades were filtered by meta-labeler and why

**Testing Requirements:**
- [ ] Test meta-labeler filters low-confidence trade candidates (signal → HOLD)
- [ ] Test meta-labeler passes high-confidence candidates with size
- [ ] Test without meta-labeler: backward compatible, no filtering
- [ ] Test position sizing flows through to PositionManager
- [ ] Test context gate adjusts meta-labeler threshold
- [ ] Test meta-labeler features include all required inputs (signal + indicators + regime + context)
- [ ] Test logging records filtered trades with probability

**Acceptance Criteria:**
- [ ] Meta-labeler integrates into the per-bar loop without disrupting existing flow
- [ ] Trade filtering observable in backtest results
- [ ] Backward compatible: ensemble without meta_labeler works unchanged
- [ ] Position sizing affects trade execution

---

## Task 6.4: LightGBM Meta-Labeler Variant (Experiment 6)

**File(s):** `ktrdr/backtesting/meta_labeler.py` (extend)
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Implement a LightGBM-based meta-labeler as an alternative to the MLP variant. Research suggests tree-based models outperform NNs on tabular financial data. This implements Design Experiment 6: MLP vs LightGBM meta-labeler.

**Implementation Notes:**
- Add `lightgbm` to project dependencies (optional dependency)
- Create `LightGBMMetaLabeler` class:
  ```python
  class LightGBMMetaLabeler:
      def __init__(self, params: dict = None):
          self.params = params or {
              "objective": "binary",
              "num_leaves": 31,
              "max_depth": 5,
              "n_estimators": 100,
              "learning_rate": 0.05,
          }
      def train(self, X, y, validation_data=None): ...
      def predict(self, features: dict) -> dict: ...
  ```
- LightGBM provides feature importance for free — log and store it
- Use the same `ModelBundle` / model loading pattern but with joblib serialization instead of torch
- Same predict interface: returns `{"probability": float, "take_trade": bool, "position_size": float}`
- Configurable in ensemble YAML: `model_type: lightgbm` in the meta_labeler model config

**Testing Requirements:**
- [ ] Test LightGBM meta-labeler trains and produces probabilities in [0, 1]
- [ ] Test feature importance is logged
- [ ] Test serialization: model saves and loads correctly
- [ ] Test prediction interface matches MLP variant
- [ ] Test with same data as MLP variant for comparison

**Acceptance Criteria:**
- [ ] LightGBM meta-labeler is a drop-in alternative to MLP
- [ ] Feature importance available for inspection
- [ ] Same predict interface as MLP variant

---

## Task 6.5: Validation — Meta-Labeling Impact (Experiment 5)

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 3 hours

**Description:**
Execute Design Experiment 5: Signal Model Alone vs Signal Model + Meta-Labeler. Validates that meta-labeling adds value on top of working signal models.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing tests covering meta-labeling or trade filtering
3. Design a test (via `ke2e-test-designer` if needed) that:
   a. Runs ensemble backtest WITHOUT meta-labeler (signal model only — M5 baseline)
   b. Trains meta-labeler (both MLP and LightGBM variants) on 2020-2023 data
   c. Runs ensemble backtest WITH meta-labeler on 2024 data
   d. Compares: Sharpe, precision, recall, win rate, trade count, position sizing impact
   e. Compares MLP vs LightGBM meta-labeler (Experiment 6)
4. Execute via `ke2e-test-runner`

**Success Criteria (from Design Section 11 — Phase 3):**
- [ ] Meta-labeler precision > 60% (majority of taken trades are profitable)
- [ ] Sharpe improves vs signal-model-only baseline
- [ ] Sharpe > 0.5 on validation window
- [ ] Position sizing produces risk-adjusted improvement vs fixed sizing
- [ ] Signal model + meta-labeler outperforms signal model alone
