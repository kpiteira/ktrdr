# M3 Handoff: Training Integration

## Architecture Change (Revised)

**Previous approach** (wrong): `TrainingWorkerAdapter` with nested polling loop.

**Correct approach**: Orchestrator directly calls TrainingService and tracks the real training operation ID. No adapter, no nested polling.

---

## Task 3.1 Completed

Orchestrator now directly calls TrainingService.

### Implementation

In `research_worker.py`:

- `_start_training()` method calls `TrainingService.start_training()` directly
- Stores `training_op_id` in parent metadata
- Sets phase to "training"
- Main loop polls the real training operation

Key code path:

```python
async def _start_training(self, operation_id: str) -> None:
    result = await self.training_service.start_training(
        symbols=symbols,
        timeframes=timeframes,
        strategy_name=strategy_name,
    )
    training_op_id = result["operation_id"]
    parent_op.metadata.parameters["phase"] = "training"
    parent_op.metadata.parameters["training_op_id"] = training_op_id
```

---

## Task 3.2 Completed

Deleted `TrainingWorkerAdapter` and related files.

### Files Deleted

| File | Description |
|------|-------------|
| `ktrdr/agents/workers/training_adapter.py` | Wrong adapter pattern |
| `tests/unit/agent_tests/test_training_adapter.py` | Tests for deleted adapter |

### Files Modified (Task 3.2)

| File | Change |
|------|--------|
| `ktrdr/agents/workers/stubs.py` | Removed StubTrainingWorker |
| `ktrdr/agents/workers/__init__.py` | Updated exports |

---

## Task 3.3 Completed

Updated tests to mock services instead of workers.

### Files Modified (Task 3.3)

| File | Change |
|------|--------|
| `tests/unit/agent_tests/test_research_worker.py` | Mock `training_service` instead of `training_worker` |
| `tests/unit/agent_tests/test_agent_service_new.py` | Updated wiring tests |
| `tests/unit/agent_tests/test_stub_workers.py` | Removed StubTrainingWorker tests |

---

## Task 3.4 (Integration Tests)

Integration tests exist from previous implementation (`tests/integration/agent_tests/test_agent_training_gate.py`). These test gate behavior but not full training flow.

**Note**: Full E2E integration testing of real training requires running the full Docker stack with workers.

---

## Training Gate (Already in M1)

Training gate was implemented in M1 Task 1.11. Located in `research_worker.py::_handle_training_phase()`.

Gate thresholds:

- Accuracy < 45% → FAIL
- Final loss > 0.8 → FAIL
- Loss decrease < 20% → FAIL

---

## M3 Complete

All core tasks completed. The agent now:

1. Designs strategy via Claude (M2)
2. Calls TrainingService directly (M3)
3. Tracks real training operation ID
4. Evaluates training quality gate
5. Continues to backtest if gate passes

---

## Gotchas for M4+

1. **Lazy loading** - Services are None at construction, lazy-loaded via property getters.

2. **WorkerRegistry required** - Both TrainingService and BacktestingService require WorkerRegistry:

   ```python
   from ktrdr.api.endpoints.workers import get_worker_registry
   registry = get_worker_registry()
   ```

3. **result_summary can be None** - Guard with `result_summary = op.result_summary or {}`.

4. **Circular import avoidance** - Use Protocol for type hints and lazy imports in property getters.

---

## Bug Fixes Applied (Post-M3)

### Strategy Validation Fix (commit e9edfbf)

**Issue**: Claude-designed strategies failed validation due to case mismatch.
**Fix**: Modified validation to use `feature_id` for fuzzy set matching.

### Circular Import Fix (commit 1b26892)

**Issue**: `ImportError` from circular import chain.
**Fix**: Made `_validate_strategy_config` import lazy in `context.py`.

---

## Known Issues for Future

### Data Availability

Claude may design strategies using symbol/timeframe combinations not available in training workers.

**Future Fix Options**:

1. Pre-load common data into training containers
2. Add `list_available_data` tool to design phase
3. Add data availability check before training
