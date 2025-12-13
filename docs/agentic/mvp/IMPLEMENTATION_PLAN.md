# Implementation Plan: Operations-Only Agent

**Based on**: [design.md](design.md) and [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md)
**Status**: Ready for implementation
**Date**: 2025-12-12

---

## Overview

This plan implements the autonomous research agent using **only OperationsService** for state management. No session database. Each phase builds on the previous one.

**Total estimated tasks**: ~20
**Approach**: Incremental, testable at each phase

---

## Phase 1: Foundation (Design-Only Cycle)

**Goal**: Trigger → Claude designs strategy → Save to disk → Complete

This proves the core loop works without training/backtest complexity.

### Task 1.1: Add AGENT_RESEARCH operation type

Add new operation type to OperationsService.

**Files**:
- `ktrdr/api/services/operations_service.py` - Add `OperationType.AGENT_RESEARCH`

**Test**: Can create/query/cancel AGENT_RESEARCH operations

---

### Task 1.2: Create minimal AgentService

New service that orchestrates research cycles using OperationsService.

**Files**:
- `ktrdr/api/services/agent_service.py` - Rewrite from scratch

**Implementation**:
```python
class AgentService:
    def __init__(self, operations_service: OperationsService):
        self._ops = operations_service

    async def trigger(self) -> dict:
        """Start a research cycle."""
        # Check no active cycle
        # Create AGENT_RESEARCH operation
        # Start async task
        # Return operation_id

    async def get_status(self) -> dict:
        """Get current cycle status."""
        # Query operations for active AGENT_RESEARCH
```

**Test**: Can trigger, get status, see operation created

---

### Task 1.3: Implement design phase

The async task that runs Claude to design a strategy.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add `_run_design_phase()`

**Implementation**:
```python
async def _run_design_phase(self, operation_id: str) -> dict:
    """Run Claude to design a strategy."""
    # Update metadata: phase = "designing"
    # Call AnthropicAgentInvoker
    # Extract strategy_name from tool_outputs
    # Return result
```

**Dependencies**: Reuse existing `AnthropicAgentInvoker` and `ToolExecutor`

**Test**: Trigger → Claude runs → strategy saved → operation completes

---

### Task 1.4: Wire up API endpoints

Minimal endpoints for triggering and status.

**Files**:
- `ktrdr/api/endpoints/agent.py` - Simplify to just trigger/status

**Endpoints**:
- `POST /agent/trigger` → Start cycle, return operation_id
- `GET /agent/status` → Get active cycle info

**Test**: Can trigger via API, query status

---

### Task 1.5: Wire up CLI commands

Minimal CLI for manual testing.

**Files**:
- `ktrdr/cli/agent_commands.py` - Simplify to trigger/status/cancel

**Commands**:
- `ktrdr agent trigger` → Start cycle
- `ktrdr agent status` → Show current cycle
- `ktrdr agent cancel <op_id>` → Cancel via operations API

**Test**: Full CLI workflow works

---

### Phase 1 Checkpoint

**Acceptance criteria**:
- [ ] `ktrdr agent trigger` starts a cycle
- [ ] Claude designs and saves a strategy
- [ ] `ktrdr agent status` shows progress
- [ ] `ktrdr agent cancel` cleanly stops cycle
- [ ] Operation appears in `ktrdr operations list`
- [ ] No session database code remains

---

## Phase 2: Training Integration

**Goal**: Design → Train → Complete (or fail on gate)

### Task 2.1: Add training phase to cycle

After design completes, start training.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add `_run_training_phase()`

**Implementation**:
```python
async def _run_training_phase(self, operation_id: str, strategy_name: str) -> dict:
    """Start training and wait for completion."""
    # Update metadata: phase = "training"
    # Extract symbols/timeframes from strategy config
    # Call training API
    # Poll for completion
    # Return training result
```

**Test**: Design → Training starts → Training completes

---

### Task 2.2: Implement training gate

Check training metrics before proceeding.

**Files**:
- `ktrdr/agents/gates.py` - Create new file

**Implementation**:
```python
def check_training_gate(metrics: dict) -> tuple[bool, str]:
    """Check if training passed quality gate.

    Returns (passed, reason)
    """
    if metrics.get("accuracy", 0) < 0.45:
        return False, "accuracy_below_threshold"
    if metrics.get("final_loss", 1.0) > 0.8:
        return False, "loss_too_high"
    return True, "passed"
```

**Test**: Gate rejects bad metrics, passes good metrics

---

### Task 2.3: Handle training failure

If training fails or gate fails, mark cycle failed.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add failure handling

**Test**: Bad training → cycle marked FAILED with reason

---

### Phase 2 Checkpoint

**Acceptance criteria**:
- [ ] Design phase completes, training starts automatically
- [ ] Training progress shows in operation metadata
- [ ] Training gate rejects poor results
- [ ] Training failure marks cycle as FAILED
- [ ] Successful training proceeds (ready for Phase 3)

---

## Phase 3: Full Cycle

**Goal**: Design → Train → Backtest → Assess → Complete

### Task 3.1: Add backtest phase

After training passes gate, run backtest.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add `_run_backtest_phase()`

**Implementation**: Similar to training phase

**Test**: Training passes → Backtest starts → Backtest completes

---

### Task 3.2: Implement backtest gate

Check backtest metrics before assessment.

**Files**:
- `ktrdr/agents/gates.py` - Add `check_backtest_gate()`

**Test**: Gate rejects bad backtests, passes good ones

---

### Task 3.3: Add assessment phase

Claude evaluates results and records learnings.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add `_run_assessment_phase()`

**Implementation**:
```python
async def _run_assessment_phase(self, operation_id: str, results: dict) -> dict:
    """Have Claude assess the results."""
    # Update metadata: phase = "assessing"
    # Call AnthropicAgentInvoker with results context
    # Save assessment to strategy folder
    # Return assessment
```

**Test**: Backtest passes → Claude assesses → Cycle completes

---

### Task 3.4: Store assessment results

Save assessment somewhere persistent.

**Files**:
- `ktrdr/agents/executor.py` - Add `save_assessment()` tool

**Storage**: `strategies/{name}/assessment.json`

**Test**: Assessment saved, readable for future cycles

---

### Phase 3 Checkpoint

**Acceptance criteria**:
- [ ] Full cycle: design → train → backtest → assess → complete
- [ ] Each phase updates operation metadata
- [ ] Gates reject poor results at each stage
- [ ] Assessment saved to disk
- [ ] Cycle duration tracked in operation

---

## Phase 4: Polish

**Goal**: Budget, observability, robustness

### Task 4.1: Budget enforcement

Track token usage, enforce daily limit.

**Files**:
- `ktrdr/agents/budget.py` - Create new file
- `ktrdr/api/services/agent_service.py` - Check budget before trigger

**Implementation**:
- Track tokens per invocation (from AgentResult)
- Store daily usage in file or operation metadata
- Reject trigger if over budget

**Test**: Budget exceeded → trigger rejected

---

### Task 4.2: Recent strategies tool

Let agent see what was tried before.

**Files**:
- `ktrdr/agents/executor.py` - Update `get_recent_strategies()`

**Implementation**: Scan `strategies/` directory for recent configs

**Test**: Agent can see recent strategy summaries

---

### Task 4.3: Observability integration

Add traces and metrics for research cycles.

**Files**:
- `ktrdr/api/services/agent_service.py` - Add OTEL instrumentation

**Metrics**:
- `agent_cycles_total` (counter, by outcome)
- `agent_cycle_duration_seconds` (histogram)
- `agent_tokens_used` (counter)

**Traces**: Full cycle from trigger to completion

**Test**: Cycles appear in Jaeger, metrics in Grafana

---

### Task 4.4: Error handling improvements

Robust handling of edge cases.

**Files**:
- `ktrdr/api/services/agent_service.py` - Improve error paths

**Cases**:
- Anthropic API timeout → fail cycle with reason
- Training service unavailable → fail cycle with reason
- Cancellation during any phase → clean shutdown

**Test**: Each error case handled gracefully

---

### Phase 4 Checkpoint

**Acceptance criteria**:
- [ ] Budget prevents overspending
- [ ] Agent sees recent strategies
- [ ] Cycles visible in Jaeger traces
- [ ] Grafana dashboard shows metrics
- [ ] Error cases handled gracefully

---

## Cleanup Tasks

### Task C.1: Delete session database code

Remove all session DB artifacts.

**Delete**:
- `research_agents/database/` - Entire directory
- Session-related tests
- PostgreSQL schema for agent_sessions

---

### Task C.2: Update documentation

Ensure docs match implementation.

**Update**:
- `CLAUDE.md` agent section
- API documentation
- CLI help text

---

## Testing Strategy

### Unit Tests

Each task should have unit tests:
- Mock OperationsService for AgentService tests
- Mock Anthropic API for invoker tests
- Test gates with various metric inputs

### Integration Tests

After each phase:
- Full cycle test with mocked LLM
- Cancellation test
- Error handling test

### Manual Validation

Before marking phase complete:
- Run real cycle (costs ~$0.20)
- Verify CLI shows correct state
- Check Jaeger traces
- Confirm strategy saved correctly

---

## Definition of Done

The MVP is complete when:

1. ✅ Full cycle works: trigger → design → train → backtest → assess → complete
2. ✅ Cancellation works cleanly at any phase
3. ✅ Budget enforcement prevents overspending
4. ✅ Cycles visible in operations list
5. ✅ Metrics in Grafana
6. ✅ Traces in Jaeger
7. ✅ No session database code remains
8. ✅ All tests pass

---

## Notes

### What we're NOT doing (intentionally deferred)

- Learning across cycles (agent memory)
- Multiple concurrent cycles
- Checkpoint recovery within cycles
- Auto-retry failed cycles
- Background triggering (manual only for MVP)

### Salvaged from previous implementation

These existing components are reusable:
- `ktrdr/agents/invoker.py` - AnthropicAgentInvoker
- `ktrdr/agents/tools.py` - Tool definitions
- `ktrdr/agents/executor.py` - Tool execution (with simplification)
- `ktrdr/agents/prompts.py` - Agent prompts

### Learnings from previous attempt

See `archive/TASK_session_cancellation.md` for what went wrong with session database approach.
