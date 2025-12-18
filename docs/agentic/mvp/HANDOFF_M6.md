# M6 Cancellation & Error Handling Handoff

## Summary

M6 adds cancellation support for agent research cycles at API, worker, and CLI levels.

## Completed Tasks

### Task 6.1: Cancel Endpoint ✅

Added DELETE /agent/cancel endpoint for cancelling active research cycles.

### Task 6.2: Parent-Child Cancellation ✅

The research worker already had cancellation propagation implemented. Task 6.2 added comprehensive unit tests validating the behavior.

### Task 6.3: CLI Cancel Command ✅

Added `ktrdr agent cancel` CLI command for cancelling active cycles.

## Implementation

### Files Created

- `tests/unit/agent_tests/test_agent_endpoint.py` - Endpoint tests for cancel
- `tests/unit/agent_tests/test_cancellation.py` - Comprehensive worker cancellation tests

### Files Modified

- `ktrdr/api/endpoints/agent.py` - Added DELETE /cancel endpoint
- `ktrdr/api/services/agent_service.py` - Added cancel() method
- `ktrdr/cli/agent_commands.py` - Added cancel command
- `tests/unit/agent_tests/test_agent_service_new.py` - Added TestAgentServiceCancel tests
- `tests/unit/agent_tests/test_agent_cli.py` - Updated for cancel command
- `tests/unit/agent_tests/test_agent_cli_api.py` - Added TestAgentCancelViaAPI tests

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

## CLI Usage

```bash
# Cancel active cycle
ktrdr agent cancel
# Research cycle cancelled!
#   Operation: op_agent_research_...
#   Child operation: op_training_...

# When no cycle running
ktrdr agent cancel
# No active research cycle to cancel.
# Use ktrdr agent trigger to start a new research cycle.
```

## Key Patterns

### Child Operation ID Mapping

The `_get_child_op_id_for_phase()` method maps phases to their child operation metadata keys:

- `designing` → `design_op_id`
- `training` → `training_op_id`
- `backtesting` → `backtest_op_id`
- `assessing` → `assessment_op_id`

### Cancellation Flow

1. **CLI**: `ktrdr agent cancel` calls DELETE /agent/cancel
2. **API Layer**: AgentService.cancel() finds active AGENT_RESEARCH operation and calls `ops.cancel_operation()`
3. **Worker Layer**: AgentResearchWorker catches `asyncio.CancelledError` and calls `_cancel_current_child()`
4. **Propagation**: Child operation is cancelled via `ops.cancel_operation()` and child task is cancelled
5. **Result**: Both parent and child marked CANCELLED

### Gotcha: 404 Handling in CLI

The API returns 404 when no active cycle exists. The CLI catches `AsyncCLIClientError` and checks for "no active" in the message to display a friendly message instead of an error.

## Next Tasks

- **6.4**: Improve error messages with context
- **6.5**: Integration tests for cancellation flow
