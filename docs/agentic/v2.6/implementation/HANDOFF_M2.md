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

### Next Task Notes (Task 2.3)

Task 2.3 is about writing unit and integration tests for error isolation. The unit tests already exist in `tests/unit/agents/test_error_isolation.py`. Task 2.3 may just need to verify coverage or add integration tests.

---
