# M6 Cancellation & Error Handling Handoff

## Summary

M6 adds cancellation support for agent research cycles at both API and worker levels.

## Completed Tasks

### Task 6.1: Cancel Endpoint ✅

Added DELETE /agent/cancel endpoint for cancelling active research cycles.

### Task 6.2: Parent-Child Cancellation ✅

The research worker already had cancellation propagation implemented. Task 6.2 added comprehensive unit tests validating the behavior.

## Implementation

### Files Created

- `tests/unit/agent_tests/test_agent_endpoint.py` - Endpoint tests for cancel
- `tests/unit/agent_tests/test_cancellation.py` - Comprehensive worker cancellation tests

### Files Modified

- `ktrdr/api/endpoints/agent.py` - Added DELETE /cancel endpoint
- `ktrdr/api/services/agent_service.py` - Added cancel() method
- `tests/unit/agent_tests/test_agent_service_new.py` - Added TestAgentServiceCancel tests

## API Contract

### DELETE /agent/cancel

**Success (200)**:

```json
{
    "success": true,
    "operation_id": "op_agent_research_...",
    "child_cancelled": "op_training_...",
    "message": "Research cycle cancelled"
}
```

**No active cycle (404)**:

```json
{
    "success": false,
    "reason": "no_active_cycle",
    "message": "No active research cycle to cancel"
}
```

## Key Patterns

### Child Operation ID Mapping

The `_get_child_op_id_for_phase()` method maps phases to their child operation metadata keys:

- `designing` → `design_op_id`
- `training` → `training_op_id`
- `backtesting` → `backtest_op_id`
- `assessing` → `assessment_op_id`

### Cancellation Flow

1. **API Layer**: AgentService.cancel() finds active AGENT_RESEARCH operation and calls `ops.cancel_operation()`
2. **Worker Layer**: AgentResearchWorker catches `asyncio.CancelledError` and calls `_cancel_current_child()`
3. **Propagation**: Child operation is cancelled via `ops.cancel_operation()` and child task is cancelled
4. **Result**: Both parent and child marked CANCELLED

### Worker Instance Variables

The research worker tracks current child for cancellation:

- `self._current_child_op_id: str | None` - Set by `_start_*` methods
- `self._current_child_task: asyncio.Task | None` - Set for local workers (design, assessment)

## Next Tasks

- **6.3**: Add `ktrdr agent cancel` CLI command
- **6.4**: Improve error messages with context
- **6.5**: Integration tests for cancellation flow
