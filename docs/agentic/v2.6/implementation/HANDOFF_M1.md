# Handoff: M1 Coordinator Loop

## Task 1.1 Complete: Add `_get_all_active_research_ops()` Method

### Gotchas

- **Import location**: `OperationInfo` needs to be imported from `ktrdr.api.models.operations` at the top of the file, not locally inside the method. The existing method `_get_active_research_op()` didn't need this because it returns `ops[0] | None` which doesn't need a type hint.

### Implementation Notes

The new method follows the same pattern as the existing `_get_active_research_op()`:
- Queries for each active status (RUNNING, RESUMING, PENDING)
- Uses `ops.list_operations()` with status filter
- Returns a list instead of returning the first match

Key difference from code sketch in plan:
- Plan showed `limit=1` removal, but the actual existing code doesn't use explicit limit removal. The default limit in `list_operations` is 100 which is plenty for concurrent researches.

---

## Task 1.2 Complete: Add `_get_concurrency_limit()` Method

### Gotchas

- **Import inside method**: The imports for `get_worker_registry` and `WorkerType` are done inside the method to avoid circular imports. The worker registry is a singleton accessed via `get_worker_registry()` from `ktrdr.api.endpoints.workers`.

- **Testing with mock**: When testing, patch `ktrdr.api.endpoints.workers.get_worker_registry` (not the agent_service module) because the import happens inside the method.

### Implementation Notes

- Override via `AGENT_MAX_CONCURRENT_RESEARCHES` env var (non-zero = use it)
- Calculation: `training_workers + backtest_workers + buffer`
- Buffer from `AGENT_CONCURRENCY_BUFFER` (default 1)
- Returns minimum 1 to always allow at least one research

### Next Task Notes (Task 1.3)

Task 1.3 modifies `trigger()` to use the new methods for capacity checking. Replace the single-research rejection block with a capacity check using `_get_all_active_research_ops()` and `_get_concurrency_limit()`.

---

## Task 1.3 Complete: Modify `trigger()` for Capacity Check

### Gotchas

- **Updated existing test**: The test `test_trigger_rejects_when_cycle_active` in `test_agent_service_new.py` was testing for `active_cycle_exists` reason. Updated to `test_trigger_rejects_when_at_capacity` which tests the new `at_capacity` response with explicit limit=1.

- **Response shape changed**: Old response had `operation_id` pointing to the active cycle. New response has `active_count` and `limit` instead. Any code checking for `active_cycle_exists` reason needs to be updated to check for `at_capacity`.

### Implementation Notes

The change is minimal - just replacing the single-research rejection block with:
```python
active_ops = await self._get_all_active_research_ops()
limit = self._get_concurrency_limit()
if len(active_ops) >= limit:
    return {"triggered": False, "reason": "at_capacity", ...}
```

Budget check order preserved (happens before capacity check).

### Next Task Notes (Task 1.4)

Task 1.4 refactors `run()` in `research_worker.py` to iterate over all active researches. This is the core architectural change - the coordinator will query all active ops and advance each one, rather than running a single operation to completion.

---

## Task 1.4 Complete: Refactor `run()` to Multi-Research Loop

### Gotchas

- **Telemetry tests refactored**: The tests in `test_research_worker_telemetry.py` were testing the old `run(operation_id)` signature. They've been completely rewritten to:
  - Test coordinator span creation (`agent.coordinator` instead of per-operation `agent.research_cycle`)
  - Test phase spans by calling handlers directly (simpler, more unit-test-like)
  - Test gate attributes and outcome recording via the coordinator model

- **Completion handling moved inside**: The `_handle_assessing_phase` method now calls `ops.complete_operation()` directly when a research completes. This was necessary because the coordinator loop no longer returns a result to complete the operation externally.

- **AgentService._run_worker updated**: The method now calls `worker.run()` without arguments since the coordinator discovers operations itself.

### Implementation Notes

Key new methods in `research_worker.py`:
- `_get_active_research_operations()` - Queries RUNNING and PENDING AGENT_RESEARCH operations
- `_advance_research(op)` - Advances a single research one step through its phase state machine

The `run()` method now:
1. Queries all active operations
2. Iterates and advances each one step
3. Sleeps for POLL_INTERVAL
4. Exits when no active operations remain

Error handling: If one research fails, it's marked as FAILED and the coordinator continues with other researches.

### Next Task Notes (Task 1.5)

Task 1.5 manages coordinator lifecycle - starting on first trigger, tracking the coordinator task, and reusing it for subsequent triggers. The key change is moving from "one task per operation" to "one coordinator task for all operations".
