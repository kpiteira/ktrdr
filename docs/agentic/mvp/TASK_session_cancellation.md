# Task: Unified Session-Operation Lifecycle

**Priority:** High (architectural consistency + operability)
**Effort:** 4-6 hours
**Branch:** `feature/agent-mvp`

---

## Problem Statement

Agent sessions and operations have inconsistent lifecycles:

| Phase | Has Operation? | Cancellable? | Observable? | Cost Tracked? |
|-------|---------------|--------------|-------------|---------------|
| DESIGNING | ❌ No | ❌ No | ❌ No | ❌ No |
| TRAINING | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| BACKTESTING | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| ASSESSING | ❌ No | ❌ No | ❌ No | ❌ No |

**Consequences:**
1. Sessions can become stuck with no way to cancel
2. DESIGNING and ASSESSING phases are invisible to operations
3. Token costs during agent invocation aren't tracked
4. No unified view of agent work in progress
5. Parent-child operation aggregation not used

---

## Vision: Unified Lifecycle

Every agent session should be fully observable and cancellable through the operations system.

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent Session = Parent Operation                                │
│  OperationType: AGENT_SESSION                                    │
│  operation_id: op_agent_session_20241212_123456_abc123          │
│                                                                  │
│  Progress: Aggregated from children (0-100%)                    │
│  Status: RUNNING while any child active                         │
│                                                                  │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  Child: AGENT_DESIGN                                     │  │
│    │  - Tracks: tokens, duration, strategy output            │  │
│    │  - Progress: 0-25% of parent                            │  │
│    └─────────────────────────────────────────────────────────┘  │
│                        │                                        │
│                        ▼                                        │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  Child: TRAINING                                         │  │
│    │  - Tracks: epochs, loss, accuracy                       │  │
│    │  - Progress: 25-60% of parent                           │  │
│    └─────────────────────────────────────────────────────────┘  │
│                        │                                        │
│                        ▼                                        │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  Child: BACKTESTING                                      │  │
│    │  - Tracks: trades, equity curve, metrics                │  │
│    │  - Progress: 60-90% of parent                           │  │
│    └─────────────────────────────────────────────────────────┘  │
│                        │                                        │
│                        ▼                                        │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  Child: AGENT_ASSESSMENT                                 │  │
│    │  - Tracks: tokens, analysis output                      │  │
│    │  - Progress: 90-100% of parent                          │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  CANCEL parent → cancels all children → ends session            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Benefits

1. **Unified Cancellation**: `ktrdr operations cancel <session_op_id>` cancels everything
2. **Full Observability**: All phases visible in `ktrdr operations list`
3. **Cost Tracking**: Token usage for DESIGNING/ASSESSING tracked as operation metrics
4. **Progress Aggregation**: Parent shows overall session progress (existing infrastructure)
5. **Consistent Model**: Same patterns for all agent work
6. **Debugging**: Can see exactly where a session is stuck

---

## Implementation Plan

### Phase A: Schema & Types (1 hour)

1. **Add OperationType values** (ktrdr/api/models/operations.py):
```python
class OperationType(str, Enum):
    # ... existing ...
    AGENT_SESSION = "agent_session"      # Parent operation for session
    AGENT_ASSESSMENT = "agent_assessment"  # Assessment phase
```

2. **Add SessionOutcome** (research_agents/database/schema.py):
```python
class SessionOutcome(str, Enum):
    # ... existing ...
    CANCELLED = "cancelled"  # User-initiated cancellation
```

### Phase B: Session Operation Creation (2 hours)

3. **TriggerService creates parent operation** when session starts:
```python
async def _trigger_design_phase(self, operation_id: str | None = None) -> dict:
    # Create session FIRST
    session = await self.db.create_session()

    # Create PARENT operation for entire session
    ops_service = get_operations_service()
    session_op_id = await ops_service.create_operation(
        operation_type=OperationType.AGENT_SESSION,
        metadata=OperationMetadata(
            description=f"Agent research session #{session.id}"
        ),
    )

    # Link session to parent operation
    await self.db.update_session(
        session_id=session.id,
        operation_id=session_op_id,  # Now DESIGNING has operation!
    )

    # Create CHILD operation for design phase
    design_op_id = await ops_service.create_operation(
        operation_type=OperationType.AGENT_DESIGN,
        parent_operation_id=session_op_id,  # Linked to parent
        metadata=OperationMetadata(
            description=f"Design strategy for session #{session.id}"
        ),
    )

    # ... invoke agent, track tokens in design operation ...
```

4. **Training/Backtest operations become children**:
```python
async def _handle_designed_session(self, session: Any) -> dict:
    # Get parent operation from session
    parent_op_id = session.operation_id

    # Start training with parent linkage
    result = await start_training_via_api(
        strategy_name=session.strategy_name,
        parent_operation_id=parent_op_id,  # NEW: link to session
    )
```

5. **Assessment creates child operation**:
```python
async def _invoke_assessment(self, session: Any, backtest_results: dict) -> dict:
    parent_op_id = session.operation_id

    # Create assessment operation
    assess_op_id = await ops_service.create_operation(
        operation_type=OperationType.AGENT_ASSESSMENT,
        parent_operation_id=parent_op_id,
        metadata=OperationMetadata(
            description=f"Assess results for session #{session.id}"
        ),
    )

    # ... invoke agent, track tokens ...
```

### Phase C: Cancellation Flow (1 hour)

6. **Operation cancellation cascades to session**:
```python
# In OperationsService.cancel_operation():
async def cancel_operation(self, operation_id: str) -> bool:
    operation = await self.get_operation(operation_id)

    # If this is an AGENT_SESSION, also cancel the DB session
    if operation.operation_type == OperationType.AGENT_SESSION:
        # Find linked session and cancel it
        await self._cancel_linked_session(operation_id)

    # Existing: cancel children, update status
    ...
```

7. **AgentDatabase cancel method** (backstop for direct access):
```python
async def cancel_session(self, session_id: int) -> dict:
    """Cancel session - also cancels linked operation."""
    session = await self.get_session(session_id)

    # Cancel via operation if exists (preferred path)
    if session.operation_id:
        ops_service = get_operations_service()
        await ops_service.cancel_operation(session.operation_id)

    # Mark session as cancelled
    await self.complete_session(session_id, SessionOutcome.CANCELLED)

    return {"success": True, ...}
```

### Phase D: CLI & API (1 hour)

8. **API endpoint** (ktrdr/api/endpoints/agent.py):
```python
@router.delete("/sessions/{session_id}")
async def cancel_session(session_id: int) -> dict:
    """Cancel an agent session and all its operations."""
    return await agent_service.cancel_session(session_id)
```

9. **CLI command** (ktrdr/cli/agent_commands.py):
```python
@agent_app.command()
def cancel(session_id: Optional[int] = None):
    """Cancel agent session (and all child operations).

    Examples:
        ktrdr agent cancel        # Cancel active session
        ktrdr agent cancel 146    # Cancel specific session

    Note: You can also use 'ktrdr operations cancel <op_id>'
    to cancel the session's parent operation directly.
    """
```

### Phase E: Token Tracking (1 hour)

10. **Track tokens in design/assessment operations**:
```python
# After agent invocation completes:
await ops_service.add_metrics(design_op_id, {
    "input_tokens": result.input_tokens,
    "output_tokens": result.output_tokens,
    "total_tokens": result.input_tokens + result.output_tokens,
    "model": "claude-sonnet-4-20250514",
})
```

---

## Acceptance Criteria

### Core Functionality
- [ ] Session creation creates AGENT_SESSION parent operation
- [ ] DESIGNING phase has child AGENT_DESIGN operation
- [ ] TRAINING operation is child of session operation
- [ ] BACKTESTING operation is child of session operation
- [ ] ASSESSING phase has child AGENT_ASSESSMENT operation
- [ ] All phases visible in `ktrdr operations list`

### Cancellation
- [ ] `ktrdr operations cancel <session_op_id>` cancels entire session
- [ ] `ktrdr agent cancel` cancels active session
- [ ] Cancelling parent cancels all children
- [ ] Session outcome = CANCELLED after cancel

### Observability
- [ ] Parent operation shows aggregated progress
- [ ] Token usage tracked for design/assessment phases
- [ ] `ktrdr agent status` shows current operation

### Backwards Compatibility
- [ ] Existing sessions without operation_id still work (graceful degradation)
- [ ] Tests updated for new operation structure

---

## Test Scenarios

1. **Full cycle creates proper operation tree**
2. **Cancel via operations cancels session**
3. **Cancel via agent cancel cancels operations**
4. **Token usage recorded for design phase**
5. **Token usage recorded for assessment phase**
6. **Progress aggregation works across phases**
7. **Existing sessions without operations still complete**

---

## Migration Notes

- Existing sessions won't have parent operations (that's OK)
- New sessions will have full operation tree
- No database migration needed (operation_id column exists)
- Consider: cleanup script for orphan sessions?

---

## Future Enhancements

1. **Cost estimation**: Use token counts to estimate $ cost
2. **Time tracking**: Duration per phase for optimization
3. **Retry with history**: Failed operations retain metrics for analysis
4. **Dashboard**: Grafana dashboard for agent session metrics
