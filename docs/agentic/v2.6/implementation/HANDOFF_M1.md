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
