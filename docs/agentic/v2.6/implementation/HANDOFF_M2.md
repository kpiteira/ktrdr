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

---
