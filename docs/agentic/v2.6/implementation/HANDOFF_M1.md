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

### Next Task Notes (Task 1.2)

Task 1.2 adds `_get_concurrency_limit()` method which calculates max concurrent researches from worker pool. You'll need to import from `ktrdr.api.endpoints.workers` for the worker registry.
