# Handoff: M2 Error Isolation

## Task 2.1 Complete: Move Exception Handling Inside Per-Research Loop

### Gotchas

- **`GateFailedError` vs `GateError`**: The existing code used `GateFailedError` alias, but the canonical exception name is `GateError`. Both work (aliased), but new code should use `GateError` for consistency.

- **Per-research `CancelledError` vs coordinator `CancelledError`**: There are TWO levels of cancellation handling:
  1. **Per-research** (inside the `for` loop): When a single research operation's child task is cancelled (e.g., user cancelled one specific operation). This marks THAT research as CANCELLED, others continue.
  2. **Coordinator level** (outer try/except): When the entire coordinator task is cancelled (e.g., backend shutdown). This saves checkpoints for ALL active researches and re-raises.

  Don't confuse these - the per-research handler does NOT re-raise.

### Implementation Notes

New handler methods added to `AgentResearchWorker`:
- `_handle_research_cancelled(op)` - Marks single research CANCELLED, saves checkpoint, records "cancelled" metric
- `_handle_research_failed(op, error)` - Marks single research FAILED, saves checkpoint, records "failed" metric

The `run()` method's per-research exception handling now catches:
1. `asyncio.CancelledError` → `_handle_research_cancelled(op)`
2. `(WorkerError, GateError)` → `_handle_research_failed(op, e)`
3. `Exception` → logs "Unexpected error" then `_handle_research_failed(op, e)`

### Next Task Notes (Task 2.2)

Task 2.2 adds `_save_checkpoint()` helper. This method **already exists** (added in M1, lines 980-1022). Task 2.2 may just need verification that it works correctly with the new handlers, or the task may be a no-op.

---

## Task 2.2 Complete: Add Checkpoint Save Helper

### Implementation Notes

**Task 2.2 was effectively a no-op** - the `_save_checkpoint()` method already existed from M1 implementation (lines 1027-1069). The method:

1. Checks for checkpoint service availability (returns early if None)
2. Retrieves the operation
3. Builds checkpoint state via `build_agent_checkpoint_state()`
4. Calls checkpoint service to persist
5. Handles all exceptions gracefully (logs warning, doesn't crash)

The helper was already being called by:
- `_handle_research_cancelled()` (line 939) - saves with type "cancellation"
- `_handle_research_failed()` (line 961) - saves with type "failure"

### Test Coverage

Tests already existed (added during M1/Task 2.1):
- `tests/unit/agents/test_error_isolation.py::TestCheckpointOnFailure` - failure checkpoint tests
- `tests/unit/agents/test_error_isolation.py::TestCancelledErrorIsolation::test_cancelled_research_has_checkpoint_saved`
- `tests/unit/agent_tests/test_agent_checkpoint_integration.py::TestResearchWorkerCheckpointHelpers` - edge cases (missing service, missing operation)

---

## Task 2.3 Complete: Unit and Integration Tests for Error Isolation

### Implementation Notes

- **Unit tests** already existed in `tests/unit/agents/test_error_isolation.py` (from Task 2.1)
- **Integration tests** created in `tests/integration/test_error_isolation.py` with 5 new tests:
  1. `test_one_research_fails_others_continue_three_ops` - Primary E2E test per M2 spec
  2. `test_checkpoint_saved_for_failed_research` - DB verification for checkpoint
  3. `test_gate_error_isolates_single_research` - GateError isolation
  4. `test_multiple_failures_dont_crash_coordinator` - Stress test
  5. `test_unexpected_error_type_isolated` - RuntimeError isolation

### Test Coverage Summary

| Requirement | Unit Test | Integration Test |
|-------------|-----------|------------------|
| WorkerError isolation | ✅ test_worker_error_in_one_research_doesnt_stop_others | ✅ test_one_research_fails_others_continue_three_ops |
| GateError isolation | ✅ test_gate_error_in_one_research_doesnt_stop_others | ✅ test_gate_error_isolates_single_research |
| Unexpected error isolation | ✅ test_unexpected_error_in_one_research_doesnt_stop_others | ✅ test_unexpected_error_type_isolated |
| CancelledError isolation | ✅ test_cancelled_error_in_one_research_cancels_only_that_research | N/A |
| Checkpoint on failure | ✅ test_checkpoint_saved_on_worker_error | ✅ test_checkpoint_saved_for_failed_research |
| Missing service graceful | ✅ test_save_checkpoint_handles_missing_service | N/A |

### Pre-existing Test Failures Fixed

While verifying M2 tests, discovered and fixed 2 pre-existing issues in integration CLI tests (broken since commit c4fb5a39):

1. **Missing `runner` fixture**: `tests/integration/cli/test_sandbox_commands.py` referenced fixture that didn't exist. Created `tests/integration/cli/conftest.py`.

2. **Missing `check_ports_available` mock**: 5 `test_up_*` tests weren't mocking port checks, causing real port conflicts.

**Other pre-existing failures on main** (not in scope for M2):
- `test_host_orchestrator.py`: ImportError for HostTrainingOrchestrator
- `test_local_orchestrator.py`: TrainingPipeline missing `train_strategy`
- `test_compute_indicator.py`: ktrdr.cli missing `indicator_commands`

---

## Bug Fix: Stub Worker Results Not Propagated

### Discovery

During E2E testing, researches were failing with:
```
Strategy file not found: unknown.yaml
```

### Root Cause

The `run_child()` wrapper functions in `_start_design` and `_start_assessment` did not return the worker's result:

```python
# BEFORE (broken)
async def run_child():
    await self.design_worker.run(operation_id, model=model, brief=brief)
    # No return! task.result() returns None
```

When the stub worker completed, `task.result()` returned `None` instead of the dict containing `strategy_path`. This caused `_design_results[operation_id]` to be empty, and the training phase couldn't find the strategy file.

### Fix

Added `return` statement to both wrapper functions:

```python
# AFTER (fixed)
async def run_child():
    return await self.design_worker.run(operation_id, model=model, brief=brief)
```

This ensures the stub worker's result (containing `strategy_path`, `strategy_name`, etc.) is properly captured and stored in `_design_results` for use by subsequent phases.

### Files Modified

- `ktrdr/agents/workers/research_worker.py` (lines 316, 781)

---

## Bug Fix: strategy_path Not Persisted for Backtest Phase

### Discovery

After fixing the return statement, researches still failed with:
```
expected str, bytes or os.PathLike object, not NoneType
```

### Root Cause

In the stub flow, `strategy_path` was stored in `_design_results` but NOT in `parent_op.metadata.parameters`. When `_start_backtest` runs, it reads from `params.get("strategy_path")` which was None.

### Fix

Added metadata persistence in the stub flow handler (line 354):

```python
if parent_op:
    # Store strategy_path in metadata for backtest phase
    parent_op.metadata.parameters["strategy_path"] = result.get("strategy_path")
```

---

## Bug Fix: StubAssessmentWorker Missing gate_rejection_reason Parameter

### Discovery

After fixing the path issue, researches failed with:
```
StubAssessmentWorker.run() got an unexpected keyword argument 'gate_rejection_reason'
```

### Fix

Added `gate_rejection_reason` parameter to `StubAssessmentWorker.run()`:

```python
async def run(
    self,
    operation_id: str,
    results: dict[str, Any],
    model: str | None = None,
    gate_rejection_reason: str | None = None,  # Added
) -> dict[str, Any]:
```

---

## E2E Validation Complete

Final E2E test (3 concurrent researches):
- **Research A**: COMPLETED ✅
- **Research B** (INJECT_FAILURE): FAILED ✅
- **Research C**: COMPLETED ✅

This proves M2 error isolation is working correctly:
1. One research failing doesn't affect others
2. Stub workers properly propagate results
3. All phases (design, training, backtest, assessment) work with stubs

---
