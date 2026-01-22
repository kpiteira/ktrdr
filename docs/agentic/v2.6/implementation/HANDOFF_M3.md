# Handoff: M3 Worker Queuing

## Task 3.1 Complete: Add Worker Availability Check to Design→Training Transition

### Gotchas

- **Import location for patching**: The `get_worker_registry` import is done inside `_is_training_worker_available()` to avoid circular imports. When testing, patch `ktrdr.api.endpoints.workers.get_worker_registry` (not the research_worker module) because the import happens at runtime inside the method.

- **Retry scenario requires stored results**: When design completes but no worker is available, the task is removed from `_child_tasks` but results are stored in `_design_results`. On retry, the code must check `_design_results` first before starting a new design.

### Implementation Notes

Added `_is_training_worker_available()` helper method (lines 1015-1029):
- Imports `get_worker_registry` and `WorkerType` inside method
- Calls `registry.get_available_workers(WorkerType.TRAINING)`
- Returns `True` if list is non-empty

Worker availability check added in two locations:
1. **Stub worker flow** (line 370-375): After design task completes successfully
2. **Real child op flow** (lines 450-455): After design child operation completes

Retry scenario handled (line 383-393):
- When `child_op is None` and no task running, check `_design_results` first
- If results exist, this is a retry - check worker availability
- If worker available, proceed to training
- If not available, log and return (stay in designing)

### Files Modified

- `ktrdr/agents/workers/research_worker.py`:
  - Added `_is_training_worker_available()` method
  - Added worker availability checks before `_start_training()` calls
  - Added retry logic for stored design results

### Next Task Notes (Task 3.2)

Task 3.2 adds the same pattern for training→backtest transition:
- Check `get_available_workers(WorkerType.BACKTESTING)` in `_handle_training_phase()`
- Gate rejection path should bypass worker check (goes directly to assessment)
- No need for retry scenario handling (training results stored in parent_op.metadata.parameters, not a separate dict)

---

## Task 3.2 Complete: Add Worker Availability Check to Training→Backtest Transition

### Gotchas

- **Same patching approach as 3.1**: The `get_worker_registry` import is inside `_is_backtest_worker_available()`. When testing, patch `ktrdr.api.endpoints.workers.get_worker_registry`.

- **No retry scenario needed**: Unlike design→training, there's no separate `_training_results` dict. Training results are stored in `parent_op.metadata.parameters["training_result"]` which persists across poll cycles. The research simply stays in "training" phase and re-evaluates worker availability on next cycle.

### Implementation Notes

Added `_is_backtest_worker_available()` helper method (lines 1031-1045):
- Same pattern as `_is_training_worker_available()`
- Calls `registry.get_available_workers(WorkerType.BACKTESTING)`
- Returns `True` if list is non-empty

Worker availability check added after gate passes (lines 597-602):
- Check is placed after `record_gate_result()` and before `_start_backtest()`
- Gate rejection path bypasses worker check (goes directly to assessment at lines 591-595)
- If no worker available, returns early (stays in training phase)

### Files Modified

- `ktrdr/agents/workers/research_worker.py`:
  - Added `_is_backtest_worker_available()` method
  - Added worker availability check before `_start_backtest()` call
- `tests/unit/agents/test_worker_queuing.py`:
  - Added `TestTrainingToBacktestWorkerCheck` class with 4 tests

### Next Task Notes (Task 3.3)

Task 3.3 adds comprehensive unit and integration tests for worker queuing:
- Most unit tests are already written in Task 3.1 and 3.2
- Focus on integration tests that verify the full queuing behavior with multiple researches
- Key scenario: 2 training workers, 3 researches → A and B train in parallel, C waits

---

## Task 3.3 Complete: Unit and Integration Tests for Worker Queuing

### Test Coverage Summary

**Unit Tests** (in `tests/unit/agents/test_worker_queuing.py`):
- `TestDesignToTrainingWorkerCheck` (5 tests) - from Task 3.1
- `TestDesignToTrainingWithRealChildOp` (2 tests) - from Task 3.1
- `TestTrainingToBacktestWorkerCheck` (4 tests) - from Task 3.2
- `TestMultipleResearchesQueuing` (3 tests) - NEW in Task 3.3

**Integration Tests** (in `tests/integration/test_worker_queuing.py`):
- `test_natural_queuing_with_limited_training_workers` - E2E scenario: 2 workers, 3 researches
- `test_queuing_preserves_order_of_completion` - First-come-first-served ordering
- `test_no_starvation_all_researches_eventually_proceed` - All queued researches get workers

### Implementation Notes

Unit test `TestMultipleResearchesQueuing` tests:
- Multiple researches competing for limited training workers
- Queued research proceeds when worker frees up
- Multiple researches competing for limited backtest workers

Integration tests simulate the full coordinator polling cycle:
- Create multiple research operations in same phase
- Mock worker registry to control availability
- Verify phase transitions happen only when workers available
- Verify all researches eventually complete

### Key Test Patterns

**Worker availability simulation**:
```python
available_count = [2]  # Mutable to track availability
def get_available_workers(worker_type):
    if available_count[0] > 0:
        available_count[0] -= 1  # Worker gets assigned
        return [MagicMock(worker_id="worker-1")]
    return []
```

**Phase verification**:
```python
updated = await mock_operations_service.get_operation(op.operation_id)
assert updated.metadata.parameters["phase"] == "training"  # or "designing"
```

### Files Created/Modified

- `tests/unit/agents/test_worker_queuing.py`:
  - Added `TestMultipleResearchesQueuing` class with 3 tests
- `tests/integration/test_worker_queuing.py`:
  - NEW file with 3 integration tests

### Milestone Completion Notes

M3 Worker Queuing is now complete:
- ✅ Task 3.1: Design→training worker availability check
- ✅ Task 3.2: Training→backtest worker availability check
- ✅ Task 3.3: Unit and integration tests

**Test Results:**
- Unit tests: 4244 passed
- Integration tests (worker queuing): 3 passed
- Quality checks: All passing
