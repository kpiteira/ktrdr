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
