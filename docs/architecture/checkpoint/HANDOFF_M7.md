# Handoff: Milestone 7 (Backend-Local Operations)

## Task 7.4 Complete

**Implemented:** Agent checkpoint save on failure/cancellation in AgentService

### Key Components Added

**Location:** [ktrdr/api/services/agent_service.py:93-149](ktrdr/api/services/agent_service.py#L93-L149)

```python
def _get_checkpoint_service(self) -> "CheckpointService":
    """Lazy initialization of checkpoint service."""

async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
    """Save checkpoint using build_agent_checkpoint_state."""
```

**Location:** [ktrdr/api/services/agent_service.py:230-260](ktrdr/api/services/agent_service.py#L230-L260) (`_run_worker`)

### Checkpoint Integration Pattern

Agent checkpoints are saved in `_run_worker`, not in the worker itself:

```python
async def _run_worker(self, operation_id, worker):
    try:
        result = await worker.run(operation_id)
        # Delete checkpoint on success
        await checkpoint_service.delete_checkpoint(operation_id)
        await self.ops.complete_operation(operation_id, result)
    except asyncio.CancelledError:
        await self._save_checkpoint(operation_id, "cancellation")
        await self.ops.cancel_operation(...)
        raise
    except Exception as e:
        await self._save_checkpoint(operation_id, "failure")
        await self.ops.fail_operation(...)
        raise
```

### Why AgentService, Not AgentResearchWorker?

Agent operations are **backend-local** (`is_backend_local=True`), meaning they run in the backend process, not a separate container. Unlike training/backtest workers that have their own checkpoint logic, the agent's checkpoint save is managed at the service level because:

1. The service controls the operation lifecycle (complete/fail/cancel)
2. Checkpoint state comes from operation metadata, not internal worker state
3. No artifacts to save (agent checkpoints are state-only)

### Gotcha: Checkpoint State Uses Operation Metadata

The `build_agent_checkpoint_state` function (from Task 7.3) extracts state from `operation.metadata.parameters`:

```python
# Keys it looks for:
- "phase" → current phase (idle, designing, training, backtesting, assessing)
- "strategy_name" → strategy being designed
- "strategy_path" → path to saved strategy config
- "training_op_id" → child training operation ID
- "backtest_op_id" → child backtest operation ID
- "token_counts" → accumulated token usage
- "trigger_reason" → original trigger
- "model" → model being used
```

If the worker doesn't update these metadata fields, the checkpoint won't have the right state to resume from.

### Integration Point for Task 7.5 (Resume)

Resume logic should:
1. Load checkpoint via `checkpoint_service.load_checkpoint(operation_id)`
2. Use `AgentCheckpointState.from_dict(checkpoint.state)` to deserialize
3. Check `state.phase` to determine where to resume from
4. If training phase with `training_operation_id`, check if that operation has a checkpoint too

### Tests Added

Location: [tests/unit/agent_tests/test_agent_checkpoint_integration.py](tests/unit/agent_tests/test_agent_checkpoint_integration.py)

- 8 passing tests (failure, cancellation, state shape, success cleanup)
- Uses dependency injection: `AgentService(checkpoint_service=mock)`

---

## Task 7.5 Complete

**Implemented:** Agent resume from checkpoint in AgentService and operations endpoint

### Resume Components

**Location:** [ktrdr/api/services/agent_service.py:344-462](ktrdr/api/services/agent_service.py#L344-L462)

```python
async def resume(self, operation_id: str) -> dict[str, Any]:
    """Resume a cancelled or failed research cycle from checkpoint."""
```

**Location:** [ktrdr/api/endpoints/operations.py:744-784](ktrdr/api/endpoints/operations.py#L744-L784)

```python
elif op_type == "agent":
    # Agent operations are backend-local - call AgentService.resume() directly
    agent_service = get_agent_service()
    result = await agent_service.resume(operation_id)
```

### Resume Flow

1. **Validation**: Check operation exists and is in resumable state (CANCELLED/FAILED)
2. **Conflict check**: Ensure no active cycle is running
3. **Load checkpoint**: Via `checkpoint_service.load_checkpoint()`
4. **Deserialize state**: Using `AgentCheckpointState.from_dict()`
5. **Update metadata**: Restore phase, strategy info, child operation IDs
6. **Start worker**: Background task continues from checkpointed phase

### Gotcha: Backend-Local Resume vs Worker Resume

Agent resume is different from training/backtest resume:

- **Training/Backtest**: Endpoint dispatches to external worker via HTTP
- **Agent**: Endpoint calls `AgentService.resume()` directly (backend-local)

This is because agent operations run in the backend process itself.

### Resume Tests

Location: [tests/unit/agent_tests/test_agent_resume.py](tests/unit/agent_tests/test_agent_resume.py)

- 10 passing tests covering all resume scenarios
- Tests for: basic flow, no checkpoint, not found, running, completed, active cycle conflict, phase handling

---

## Task 7.6 Complete

**Implemented:** Integration tests for agent checkpoint

### Test Location

[tests/integration/test_m7_agent_checkpoint.py](tests/integration/test_m7_agent_checkpoint.py)

### Test Classes (19 tests total)

1. **TestM7AgentCheckpointSave** (3 tests): Checkpoint save on failure/cancellation
2. **TestM7StartupReconciliation** (3 tests): Backend restart with checkpoint messages
3. **TestM7AgentResume** (6 tests): Resume status transitions and checkpoint loading
4. **TestM7FullAgentCheckpointFlow** (3 tests): End-to-end flow scenarios
5. **TestM7PhaseSpecificResume** (4 tests): Phase-specific resume verification

### Test Infrastructure

Uses `AgentOperationsRepository` (extends `MockOperationsRepository`) with:

- `is_backend_local` flag support
- `OperationInfo` model compatibility for StartupReconciliation
- Case-insensitive status handling

### Key Test Scenarios

- Full flow: start → failure → reconciliation → resume
- Startup reconciliation marks backend-local ops FAILED with checkpoint message
- Resume from different phases (designing, training, backtesting, assessing)
- Checkpoint deleted on successful completion

---

## E2E Test Script

**Location:** [scripts/test_m7_e2e.py](scripts/test_m7_e2e.py)

### Run Command

```bash
uv run python scripts/test_m7_e2e.py
```

### What It Tests

1. **Training Phase Cancellation + Resume**
   - Trigger agent → wait for training phase
   - Wait 20s for periodic checkpoints to be saved
   - Cancel operation
   - Verify checkpoint saved at training phase
   - Resume and verify design phase is skipped
   - Verify training resumes from checkpoint epoch (not epoch 0)

2. **Backtesting Phase Cancellation + Resume** (if training passes gate)
   - Same flow but for backtesting phase

### Key Result (Verified)

```text
Training checkpoint exists at epoch 4
Training resumed, current epoch: 4
...
Epoch before cancel: 4; Epoch after resume: 4
Skipped phases: ['Designing']
```

### Important Findings

1. **Design phase checkpoints are symbolic** - No real progress to save (LLM call is atomic)
2. **Training checkpoints preserve epoch** - Can resume from mid-training
3. **Periodic checkpoints deleted on completion** - Only available during training
4. **Hard crash = no checkpoint** - Checkpoints only saved on failure/cancellation

---

## Previous Tasks (7.1-7.4)

Tasks 7.1, 7.2, 7.3, 7.4 were completed in earlier commits on this branch. See git log for details.
