# Handoff: M3 Worker Queuing

## Task 3.1 Complete: Add Worker Availability Check to Design→Training Transition

### Gotchas

- **Import location for patching**: The `get_worker_registry` import is done inside `_is_training_worker_available()` to avoid circular imports. When testing, patch `ktrdr.api.endpoints.workers.get_worker_registry` (not the research_worker module) because the import happens at runtime inside the method.

- **Retry scenario requires stored results**: When design completes but no worker is available, the task is removed from `_child_tasks` but results are stored in `_design_results`. On retry, the code must check `_design_results` first before starting a new design.

### Implementation Notes

Added `_is_training_worker_available()` helper method (line 997-1010):
- Imports `get_worker_registry` and `WorkerType` inside method
- Calls `registry.get_available_workers(WorkerType.TRAINING)`
- Returns `True` if list is non-empty

Worker availability check added in two locations:
1. **Stub worker flow** (line 370-375): After design task completes successfully
2. **Real child op flow** (line 443-449): After design child operation completes

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
