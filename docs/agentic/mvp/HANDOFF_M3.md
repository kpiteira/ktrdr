# M3 Handoff: Training Integration

## Task 3.1 Completed

Created `TrainingWorkerAdapter` that bridges agent orchestrator to existing TrainingService.

### Files Created

| File | Description |
|------|-------------|
| `ktrdr/agents/workers/training_adapter.py` | TrainingWorkerAdapter class |
| `tests/unit/agent_tests/test_training_adapter.py` | 8 unit tests |

### Implementation

- Loads strategy YAML to extract `symbols`, `timeframes`, `strategy_name`
- Calls `TrainingService.start_training()` with extracted config
- Polls `OperationsService.get_operation()` until COMPLETED/FAILED/CANCELLED
- Returns metrics dict: `{success, training_op_id, accuracy, final_loss, initial_loss, model_path}`
- Propagates cancellation to child training operation

---

## Task 3.2 (Already Implemented in M1)

Training gate was already implemented in M1 Task 1.11. Located in `research_worker.py::_advance_to_next_phase()`.

---

## Task 3.3 Completed

Wired `TrainingWorkerAdapter` into orchestrator replacing `StubTrainingWorker`.

### Files Modified

| File | Change |
|------|--------|
| `ktrdr/api/services/agent_service.py` | Replace StubTrainingWorker with TrainingWorkerAdapter |
| `tests/unit/agent_tests/test_agent_service_new.py` | Update test to verify TrainingWorkerAdapter |

---

## Task 3.4 Completed

Added integration tests for training gate evaluation.

### Files Created

| File | Description |
|------|-------------|
| `tests/integration/agent_tests/test_agent_training_gate.py` | 5 integration tests |

### Tests

- Gate failure with low accuracy
- Gate pass with good metrics
- Gate failure with high loss
- Gate failure with insufficient improvement
- Gate reason includes threshold values

---

## M3 Complete

All 4 tasks completed. The agent now:
1. Designs strategy via Claude (M2)
2. Trains model via TrainingService (M3)
3. Evaluates training quality gate (M1/M3)
4. Continues to backtest if gate passes

---

## Gotchas for M4+

1. **Circular import avoidance** - TrainingService import causes circular dependency. Solution: Use `Protocol` for type hints and lazy import in property getter.

2. **WorkerRegistry required** - TrainingService requires WorkerRegistry in constructor. Get via `get_worker_registry()` from `ktrdr.api.endpoints.workers`.

3. **result_summary can be None** - OperationInfo.result_summary is Optional. Guard with `result_summary = op.result_summary or {}`.

4. **Gate reason formats**:
   - `accuracy_below_threshold (35.0% < 45%)`
   - `loss_too_high (0.900 > 0.8)`
   - `insufficient_loss_decrease (6.7% < 20%)`

---

## Bug Fixes Applied (Post-M3)

### Strategy Validation Fix (commit e9edfbf)

**Issue**: Claude-designed strategies failed TrainingService validation due to case mismatch.

**Root Cause**: API returns PascalCase indicator names (e.g., `Ichimoku`), Claude uses these in strategies, but fuzzy set keys use lowercase `feature_id` (e.g., `ichimoku_9`). The validation compared base names case-sensitively.

**Fix**: Modified `_validate_strategy_config` in `ktrdr/api/endpoints/strategies.py` to extract `feature_id` from indicators and include them in valid targets for fuzzy set validation.

### Circular Import Fix (commit 1b26892)

**Issue**: Training worker failed with `ImportError: cannot import name 'TrainingOperationContext'`.

**Root Cause**: Import chain: `context.py → strategies.py → endpoints/__init__.py → models.py → training_service.py → training/__init__.py → context.py`

**Fix**: Made `_validate_strategy_config` import lazy (inside function) in `context.py`.

---

## Known Issues for Future

### Data Availability for Designed Strategies

**Issue**: Claude may design strategies using symbol/timeframe combinations that aren't available in the training worker's data cache.

**Example**: Strategy designed with `EURUSD 4h` fails because that data isn't pre-loaded.

**Future Fix Options**:

1. Pre-load common symbol/timeframe combinations into training containers
2. Add `list_available_data` tool to design phase so Claude knows what's available
3. Add data availability check before training starts with helpful error message
