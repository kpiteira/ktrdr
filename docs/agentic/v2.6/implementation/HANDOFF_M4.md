# Handoff: M4 Individual Cancel

## Task 4.1 & 4.2 Complete: Modify cancel() and API Endpoint

### Summary

Changed `cancel()` from no-argument (cancels "the active cycle") to `cancel(operation_id: str)` (cancels a specific research). This enables individual research cancellation in multi-research scenarios.

### Gotchas

- **API endpoint path changed**: From `DELETE /agent/cancel` to `DELETE /agent/cancel/{operation_id}`. CLI will need updating in Task 4.3.

- **HTTP status codes**: The endpoint now returns:
  - 200: Success
  - 404: not_found or not_research
  - 409: not_cancellable (already completed/failed)
  - 500: Internal error

### Implementation Notes

**Service (`agent_service.py:330-380`):**
- Validates operation exists via `ops.get_operation(operation_id)`
- Checks `operation_type == OperationType.AGENT_RESEARCH`
- Checks `status in [RUNNING, PENDING]` for cancellability
- Returns structured response with reason codes: `not_found`, `not_research`, `not_cancellable`

**Endpoint (`agent.py:80-110`):**
- Path param: `operation_id: str`
- Maps reason codes to HTTP status codes
- Passes operation_id to service

### Test Coverage

Unit tests added for cancel(operation_id):
- Running research cancellation
- Pending research cancellation
- Unknown operation_id (not_found)
- Non-research operation (not_research)
- Completed research (not_cancellable)
- Failed research (not_cancellable)
- Multiple researches - cancel one, others continue

Endpoint tests updated for new path format.

---

## Task 4.3: N/A (CLI Restructure)

Task 4.3 was written assuming the old CLI structure (`ktrdr agent cancel`). The CLI has since been restructured:

- `ktrdr agent cancel` → `ktrdr cancel`
- `ktrdr cancel <operation_id>` already exists and works
- Uses general `/operations/{id}` endpoint which cancels any operation type

The general cancel is actually **better** for CLI users - they can cancel research ops or child ops (training/backtest) without caring about operation types. The agent-specific `/agent/cancel/{id}` endpoint remains available for API consumers who want strict validation.

**Decision**: Task 4.3 is complete - no changes needed.

---

## Task 4.4 Complete: Track Child Tasks Per Operation

### Summary

Updated `_handle_research_cancelled` to properly cancel child tasks when a research is cancelled. The `_child_tasks` dict already existed but the cancellation method wasn't using it properly.

### The Bug

The existing code in `_handle_research_cancelled` just popped tasks from the tracking dict without actually cancelling them:

```python
# OLD - just removes, doesn't cancel!
self._child_tasks.pop(operation_id, None)
```

### The Fix

Now properly cancels the task before removing (`research_worker.py:1107-1118`):

```python
# Cancel child task if running
if operation_id in self._child_tasks:
    task = self._child_tasks[operation_id]
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    del self._child_tasks[operation_id]
```

### Test Coverage

Added `TestChildTaskCancellation` class in `test_research_worker_multi.py`:
- Task tracked when design starts
- Task tracked when assessment starts
- **Task cancelled when research cancelled** (the key test)
- Task not cancelled if already done
- Task removed on completion
- No memory leak - tasks cleaned on failure

### Implementation Notes

- `_child_tasks: dict[str, asyncio.Task]` was already in place (line 176)
- Design and assessment already track tasks properly
- Cleanup on completion/failure already works
- Only `_handle_research_cancelled` was missing the actual cancellation step
