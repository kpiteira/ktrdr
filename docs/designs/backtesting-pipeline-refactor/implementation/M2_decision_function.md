---
design: docs/designs/backtesting-pipeline-refactor/DESIGN.md
architecture: docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md
---

# M2: DecisionFunction (Stateless Decisions)

## Goal

Create `DecisionFunction` — a stateless decision maker that maps `(features, position, bar, last_signal_time) → TradingDecision`. Prove it produces identical outputs to `DecisionEngine._apply_position_logic()` for the same inputs. No integration with the engine yet — this milestone only builds and validates the component.

## Tasks

### Task 2.1: Create DecisionFunction class

**File(s):** `ktrdr/backtesting/decision_function.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create `DecisionFunction` — a callable class that takes pre-computed features, current position, and bar data, and returns a `TradingDecision`. Position is received as input, not tracked internally. The model forward pass and all signal filtering logic live here.

**Implementation Notes:**
- `__init__(self, model: nn.Module, feature_names: list[str], decisions_config: dict)` — receives a ready-to-infer model (from ModelBundle), the ordered feature names, and the decisions config section from the strategy
- `__call__(self, features, position, bar, last_signal_time=None) -> TradingDecision` — the main entry point
- Feature-to-tensor conversion: iterate `self.feature_names` in order, build a 1D tensor from the feature dict values. This replaces the `DecisionEngine._prepare_decision_features()` → `MLPTradingModel.prepare_features()` chain which goes through `FuzzyNeuralProcessor`. The FeatureCache already produces the exact features the model expects (same processing pipeline as training), so DecisionFunction just needs to arrange them in order and convert to tensor.
- Model forward pass: `self.model(tensor.unsqueeze(0))` → logits → softmax → probabilities → argmax → signal
- Signal map: `{0: "BUY", 1: "HOLD", 2: "SELL"}` (same as `BaseNeuralModel.predict()`)
- Filters to port from `DecisionEngine._apply_position_logic()` (lines 201-259):
  1. **Confidence threshold**: `confidence < min_confidence → HOLD`
  2. **Signal separation**: `time_since_last < min_separation_hours → HOLD` (with timezone-aware UTC comparison)
  3. **Position awareness**: `LONG + BUY → HOLD`, `SHORT + SELL → HOLD`, `FLAT + SELL → HOLD` (no short positions in MVP)
- The timezone normalization logic from `_apply_position_logic` lines 227-243 must be preserved exactly
- Inference errors → return HOLD with error metadata (current behavior, see engine.py lines 438-482)
- Lazy `import torch` inside the module's function bodies is NOT needed here — this module will always be used in a context where torch is available (backtest worker)

**Pattern to follow:** `DecisionEngine._apply_position_logic()` for filter logic, `BaseNeuralModel.predict()` for model forward pass and probability extraction.

**Testing Requirements:**
- [ ] Test: `DecisionFunction.__call__` with mock model returns correct signal mapping (BUY/HOLD/SELL)
- [ ] Test: confidence below threshold returns HOLD
- [ ] Test: signal separation filter returns HOLD when too recent
- [ ] Test: position awareness — BUY when LONG returns HOLD
- [ ] Test: position awareness — SELL when FLAT returns HOLD
- [ ] Test: position awareness — SELL when LONG returns SELL (close position)
- [ ] Test: model inference error returns HOLD with error metadata
- [ ] Test: feature dict ordering matches `feature_names` parameter

**Acceptance Criteria:**
- [ ] `DecisionFunction` is stateless — no mutable instance state modified during `__call__`
- [ ] Position is received as input, not tracked internally
- [ ] All three filters (confidence, separation, position awareness) ported from DecisionEngine
- [ ] Returns `TradingDecision` (same type as DecisionEngine)
- [ ] All tests pass

---

### Task 2.2: Equivalence test fixture — DecisionFunction vs DecisionEngine

**File(s):** `tests/unit/backtesting/test_decision_function.py` (NEW)
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
Create a test fixture that proves `DecisionFunction` produces identical outputs to `DecisionEngine._apply_position_logic()` for the same inputs. This is the gate for M2 — it must pass before M3 can integrate the new component.

**Implementation Notes:**
- Build a test fixture: list of `(features_dict, position, bar, last_signal_time, expected_signal)` tuples covering all filter branches
- Create a small deterministic model (fixed weights) that produces known outputs for given inputs
- Run both `DecisionEngine.generate_decision()` and `DecisionFunction.__call__()` with the same inputs
- Compare: signal, confidence, and which filter was applied
- The fixture must cover:
  - BUY signal with high confidence and no position → BUY
  - BUY signal with low confidence → HOLD (confidence filter)
  - BUY signal when already LONG → HOLD (position awareness)
  - SELL signal when FLAT → HOLD (no short positions)
  - SELL signal when LONG → SELL (close position)
  - BUY signal within min_separation window → HOLD (signal separation)
  - BUY signal outside min_separation window → BUY
- The key insight: `DecisionEngine._prepare_decision_features` uses `FuzzyNeuralProcessor` to convert fuzzy dict → tensor, while `DecisionFunction` directly orders the dict values. These produce the same tensor because FeatureCache already does the fuzzy processing. The equivalence test validates this claim.

**Testing Requirements:**
- [ ] At least 7 test cases covering all filter branches
- [ ] Both DecisionFunction and DecisionEngine produce the same signal for each test case
- [ ] Confidence values match within floating-point tolerance (1e-6)

**Acceptance Criteria:**
- [ ] All equivalence tests pass
- [ ] Every filter branch (confidence, separation, position awareness) tested in both directions (pass and block)
- [ ] Test uses a deterministic model with known weights (not random)

---

### Task 2.3: M2 Validation

**File(s):** Tests
**Type:** VALIDATION
**Estimated time:** 30 minutes

**Description:**
Validate that DecisionFunction is ready for integration.

**Validation Steps:**
1. Run `uv run pytest tests/unit/backtesting/test_decision_function.py -x -q` — all pass
2. Run `uv run pytest tests/unit/backtesting/ -x -q` — all existing tests still pass
3. Run `make quality` — clean
4. Verify `DecisionFunction` has no mutable instance state: grep for `self.` assignments outside `__init__`

**Acceptance Criteria:**
- [ ] All new tests pass
- [ ] All existing backtesting tests pass
- [ ] Quality gates clean
- [ ] No mutable state outside `__init__`
