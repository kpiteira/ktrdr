---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 7: Backend-Local Operations

**Branch:** `feature/checkpoint-m7-backend-local`
**Depends On:** M4 (Training Resume) + Agent System Work (external)
**Status:** BLOCKED - waiting for agent system implementation

---

## Capability

When M7 is complete:
- Backend-local operations (agent system) support checkpointing
- On backend restart, backend-local RUNNING operations marked FAILED
- Error message indicates checkpoint availability
- Agent sessions can be resumed from checkpoint

---

## Blocking Dependency

This milestone depends on the agent system work being complete on the separate branch. The checkpoint integration points are:

1. Agent session state to checkpoint
2. Agent design artifacts to checkpoint
3. Resume flow for agent operations

**Do not start M7 until:**
- [ ] Agent system merged to main
- [ ] Agent session state structure is stable
- [ ] Agent operation lifecycle is defined

---

## E2E Test Scenario

```bash
#!/bin/bash
# M7 E2E Test: Backend-Local Operations (Agent)

set -e

echo "=== M7 E2E Test: Backend-Local Operations ==="

# 1. Start agent design session
echo "Step 1: Start agent session..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger \
    -H "Content-Type: application/json" \
    -d '{"trigger_reason": "start_new_cycle"}')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
SESSION_ID=$(echo $RESPONSE | jq -r '.data.session_id')
echo "Started operation: $OP_ID, session: $SESSION_ID"

# 2. Wait for some progress (design phase)
echo "Step 2: Waiting for design progress..."
for i in {1..30}; do
    sleep 2
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.data.phase')
    echo "  Phase: $STATUS"
    if [ "$STATUS" == "TRAINING" ]; then
        echo "Reached training phase"
        break
    fi
done

# 3. Restart backend
echo "Step 3: Restarting backend..."
docker-compose restart backend
sleep 10

# 4. Check operation status
echo "Step 4: Check operation status..."
OP_STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
ERROR_MSG=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.error_message')
echo "Status: $OP_STATUS"
echo "Error: $ERROR_MSG"

# 5. Check checkpoint exists
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_EXISTS=$(echo $CHECKPOINT | jq -r '.success')
echo "Checkpoint exists: $CP_EXISTS"

# 6. Resume agent session
if [ "$CP_EXISTS" == "true" ]; then
    echo "Step 6: Resume agent session..."
    RESUME=$(curl -s -X POST http://localhost:8000/api/v1/operations/$OP_ID/resume)
    RESUME_SUCCESS=$(echo $RESUME | jq -r '.success')
    echo "Resume success: $RESUME_SUCCESS"
fi

if [ "$OP_STATUS" == "FAILED" ] && [ "$CP_EXISTS" == "true" ]; then
    echo ""
    echo "=== M7 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M7 E2E TEST FAILED ==="
    exit 1
fi
```

---

## Tasks

### Task 7.1: Mark Backend-Local Operations in DB

**File(s):**
- `ktrdr/api/services/operations_service.py` (modify)

**Type:** CODING

**Description:**
Ensure backend-local operations are marked with `is_backend_local=True`.

**Implementation Notes:**
- Agent operations created with is_backend_local=True
- Startup reconciliation uses this flag to determine handling

**Acceptance Criteria:**
- [ ] Agent operations created with is_backend_local=True
- [ ] Flag queryable for startup reconciliation

---

### Task 7.2: Update Startup Reconciliation for Checkpoints

**File(s):**
- `ktrdr/api/services/startup_reconciliation.py` (modify)

**Type:** CODING

**Description:**
Update startup reconciliation to check for checkpoint availability when marking backend-local operations as FAILED.

**Code:**
```python
async def reconcile(self):
    running_ops = await self._operations_service.list_operations(status='RUNNING')

    for op in running_ops:
        if op.is_backend_local:
            # Check checkpoint availability
            checkpoint = await self._checkpoint_service.load_checkpoint(
                op.operation_id, load_artifacts=False
            )

            if checkpoint:
                error_msg = "Backend restarted - checkpoint available for resume"
            else:
                error_msg = "Backend restarted - no checkpoint available"

            await self._operations_service.update_status(
                op.operation_id,
                status='FAILED',
                error_message=error_msg
            )
```

**Acceptance Criteria:**
- [ ] Checkpoint checked on startup
- [ ] Error message indicates checkpoint availability
- [ ] User knows whether resume is possible

---

### Task 7.3: Define Agent Checkpoint State Shape

**File(s):**
- `ktrdr/checkpointing/schemas.py` (modify)
- `ktrdr/agents/checkpoint_builder.py` (new)

**Type:** CODING

**Description:**
Define checkpoint state for agent sessions.

**Note:** This depends on agent system design. Placeholder structure:

```python
@dataclass
class AgentCheckpointState:
    # Session info
    session_id: int
    phase: str  # DESIGNING, TRAINING, BACKTESTING, etc.

    # Design state (if in/past design phase)
    strategy_config: Optional[dict] = None
    research_notes: Optional[str] = None

    # Training state (if in training phase)
    training_operation_id: Optional[str] = None
    training_checkpoint_epoch: Optional[int] = None

    # Backtest state (if in backtest phase)
    backtest_operation_id: Optional[str] = None

    # Original trigger
    trigger_reason: str = ""
```

**Acceptance Criteria:**
- [ ] State shape matches agent system needs
- [ ] Builder extracts state from agent service
- [ ] All resumable state captured

---

### Task 7.4: Integrate Checkpoint Save into Agent Service

**File(s):**
- `ktrdr/agents/agent_service.py` (modify, when exists)

**Type:** CODING

**Description:**
Add checkpoint saving at key points in agent workflow.

**Checkpoint Points:**
- After design phase completes
- After training completes
- After backtest completes
- On any phase transition
- On caught exceptions

**Acceptance Criteria:**
- [ ] Checkpoint saved at phase transitions
- [ ] Checkpoint saved on failure
- [ ] Checkpoint includes current phase state

---

### Task 7.5: Implement Agent Resume Logic

**File(s):**
- `ktrdr/agents/agent_service.py` (modify, when exists)

**Type:** CODING

**Description:**
Implement resume from checkpoint for agent sessions.

**Resume Logic:**
- Load checkpoint
- Restore session to checkpointed phase
- Continue from that phase

**Acceptance Criteria:**
- [ ] Agent can resume from checkpoint
- [ ] Resumes at correct phase
- [ ] Previous phase results preserved

---

### Task 7.6: Integration Test for Agent Checkpoint

**File(s):**
- `tests/integration/test_m7_agent_checkpoint.py` (new)

**Type:** CODING

**Description:**
Integration test for agent checkpoint and resume.

**Test Scenarios:**
1. Start agent session
2. Progress to training phase
3. Simulate backend restart
4. Verify operation marked FAILED with checkpoint message
5. Resume session
6. Verify continues from correct phase

**Acceptance Criteria:**
- [ ] Test covers agent checkpoint save
- [ ] Test covers startup reconciliation
- [ ] Test covers resume
- [ ] Tests pass: `make test-integration`

---

## Milestone 7 Verification Checklist

Before marking M7 complete:

- [ ] Agent system work merged
- [ ] All 6 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1-M6 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/api/services/operations_service.py` | Modify | 7.1 |
| `ktrdr/api/services/startup_reconciliation.py` | Modify | 7.2 |
| `ktrdr/checkpointing/schemas.py` | Modify | 7.3 |
| `ktrdr/agents/checkpoint_builder.py` | Create | 7.3 |
| `ktrdr/agents/agent_service.py` | Modify | 7.4, 7.5 |
| `tests/integration/test_m7_agent_checkpoint.py` | Create | 7.6 |
