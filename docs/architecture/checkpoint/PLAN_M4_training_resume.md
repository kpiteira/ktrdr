---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 4: Training Resume

**Branch:** `feature/checkpoint-m4-training-resume`
**Depends On:** M3 (Training Checkpoint Save)
**Estimated Tasks:** 7

---

## Capability

When M4 is complete:
- User can resume cancelled/failed training with `ktrdr operations resume <id>`
- Training continues from checkpoint epoch
- Model weights, optimizer state, training history restored
- Final model is equivalent to uninterrupted training
- Checkpoint deleted after successful completion

---

## E2E Test Scenario

```bash
#!/bin/bash
# M4 E2E Test: Training Resume

set -e

echo "=== M4 E2E Test: Training Resume ==="

# 1. Start training
echo "Step 1: Start training..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_path": "strategies/test.yaml",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "epochs": 50,
        "checkpoint_interval": 10
    }')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Wait until epoch 25+
echo "Step 2: Waiting for progress..."
for i in {1..60}; do
    sleep 2
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_percent')
    echo "  Progress: $PROGRESS%"
    if (( $(echo "$PROGRESS > 50" | bc -l) )); then
        break
    fi
done

# 3. Cancel training
echo "Step 3: Cancel training..."
curl -s -X DELETE http://localhost:8000/api/v1/operations/$OP_ID/cancel
sleep 3

# 4. Verify cancelled with checkpoint
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_EPOCH=$(echo $CHECKPOINT | jq -r '.data.state.epoch')
echo "Cancelled at epoch $CP_EPOCH, status: $STATUS"

# 5. Resume training
echo "Step 5: Resume training..."
RESUME_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/operations/$OP_ID/resume)
RESUME_SUCCESS=$(echo $RESUME_RESPONSE | jq -r '.success')

if [ "$RESUME_SUCCESS" != "true" ]; then
    echo "FAIL: Resume failed"
    echo $RESUME_RESPONSE | jq
    exit 1
fi

RESUMED_FROM=$(echo $RESUME_RESPONSE | jq -r '.data.resumed_from.epoch')
echo "Resumed from epoch $RESUMED_FROM"

# 6. Wait for completion
echo "Step 6: Waiting for completion..."
for i in {1..120}; do
    sleep 2
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_percent')
    echo "  Status: $STATUS, Progress: $PROGRESS%"
    if [ "$STATUS" == "COMPLETED" ]; then
        break
    fi
    if [ "$STATUS" == "FAILED" ]; then
        echo "FAIL: Training failed after resume"
        exit 1
    fi
done

# 7. Verify completion and checkpoint cleanup
echo "Step 7: Final verification..."
FINAL_STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
CHECKPOINT_AFTER=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_EXISTS=$(echo $CHECKPOINT_AFTER | jq -r '.success')

echo "Final status: $FINAL_STATUS"
echo "Checkpoint exists after completion: $CP_EXISTS"

if [ "$FINAL_STATUS" == "COMPLETED" ] && [ "$CP_EXISTS" == "false" ]; then
    echo ""
    echo "=== M4 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M4 E2E TEST FAILED ==="
    echo "Expected: COMPLETED with no checkpoint"
    exit 1
fi
```

---

## Tasks

### Task 4.1: Create Resume API Endpoint

**File(s):**
- `ktrdr/api/endpoints/operations.py` (modify)
- `ktrdr/api/models/operations.py` (modify if needed)

**Type:** CODING

**Description:**
Add the resume endpoint with optimistic locking.

**Endpoint:**
```python
@router.post("/operations/{operation_id}/resume")
async def resume_operation(
    operation_id: str,
    operations_service: OperationsService = Depends(get_operations_service),
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
) -> ResumeResponse
```

**Implementation:**
```python
async def resume_operation(operation_id: str, ...):
    # 1. Optimistic lock: Update status only if resumable
    updated = await operations_service.try_resume(operation_id)
    if not updated:
        op = await operations_service.get_operation(operation_id)
        if op is None:
            raise HTTPException(404, "Operation not found")
        if op.status == "RUNNING":
            raise HTTPException(409, "Operation already running")
        if op.status == "COMPLETED":
            raise HTTPException(409, "Operation already completed")
        raise HTTPException(409, f"Cannot resume from status {op.status}")

    # 2. Load checkpoint
    checkpoint = await checkpoint_service.load_checkpoint(operation_id, load_artifacts=False)
    if checkpoint is None:
        await operations_service.update_status(operation_id, status="FAILED")
        raise HTTPException(404, "No checkpoint available")

    # 3. Dispatch to worker
    op = await operations_service.get_operation(operation_id)
    worker = await worker_registry.select_worker(op.operation_type)
    await dispatch_resume_to_worker(worker, operation_id)

    return ResumeResponse(
        success=True,
        data={
            "operation_id": operation_id,
            "status": "RUNNING",
            "resumed_from": {
                "checkpoint_type": checkpoint.checkpoint_type,
                "created_at": checkpoint.created_at,
                "epoch": checkpoint.state.get("epoch"),
            }
        }
    )
```

**Acceptance Criteria:**
- [ ] Endpoint exists at POST /operations/{id}/resume
- [ ] Optimistic locking prevents race conditions
- [ ] Returns 404 if operation not found
- [ ] Returns 404 if no checkpoint
- [ ] Returns 409 if already running/completed
- [ ] Returns success with resumed_from info

---

### Task 4.2: Add try_resume to OperationsService

**File(s):**
- `ktrdr/api/services/operations_service.py` (modify)
- `ktrdr/api/repositories/operations_repository.py` (modify)

**Type:** CODING

**Description:**
Add optimistic locking method for resume.

**Implementation:**
```python
# In repository
async def try_resume(self, operation_id: str) -> bool:
    """Atomically update status to RUNNING if currently resumable."""
    result = await self._db.execute(
        text("""
            UPDATE operations
            SET status = 'RUNNING',
                started_at = NOW(),
                error_message = NULL,
                reconciliation_status = NULL
            WHERE operation_id = :op_id
              AND status IN ('CANCELLED', 'FAILED')
            RETURNING operation_id
        """),
        {"op_id": operation_id}
    )
    await self._db.commit()
    return result.rowcount > 0

# In service
async def try_resume(self, operation_id: str) -> bool:
    success = await self._repository.try_resume(operation_id)
    if success:
        # Update cache
        if operation_id in self._cache:
            self._cache[operation_id].status = OperationStatus.RUNNING
    return success
```

**Acceptance Criteria:**
- [ ] Atomic update with status check
- [ ] Returns True if updated, False otherwise
- [ ] Cache updated on success
- [ ] Concurrent calls: only one succeeds

---

### Task 4.3: Implement Training Restore in Worker

**File(s):**
- `ktrdr/training/training_worker.py` (modify)
- `ktrdr/training/checkpoint_restore.py` (new)

**Type:** CODING

**Description:**
Implement the restore logic in training worker to resume from checkpoint.

**Implementation Notes:**
- Load checkpoint from shared storage
- Restore model weights
- Restore optimizer state
- Restore training history
- Continue from checkpoint epoch

**Code:**
```python
async def restore_from_checkpoint(self, operation_id: str) -> TrainingResumeContext:
    """Load checkpoint and prepare for resumed training."""
    checkpoint = await self.checkpoint_service.load_checkpoint(operation_id, load_artifacts=True)

    if checkpoint is None:
        raise ValueError(f"No checkpoint found for {operation_id}")

    # Validate artifacts
    missing = validate_training_artifacts(checkpoint.artifacts)
    if missing:
        raise CheckpointCorruptedError(f"Missing artifacts: {missing}")

    # Create resume context
    return TrainingResumeContext(
        start_epoch=checkpoint.state["epoch"] + 1,  # Resume from NEXT epoch
        model_weights=checkpoint.artifacts["model.pt"],
        optimizer_state=checkpoint.artifacts["optimizer.pt"],
        scheduler_state=checkpoint.artifacts.get("scheduler.pt"),
        best_model_weights=checkpoint.artifacts.get("best_model.pt"),
        training_history=checkpoint.state.get("training_history", {}),
        best_val_loss=checkpoint.state.get("best_val_loss", float('inf')),
        original_request=checkpoint.state.get("original_request", {}),
    )
```

**Acceptance Criteria:**
- [ ] Checkpoint loaded from shared storage
- [ ] Model weights restored
- [ ] Optimizer state restored
- [ ] Training history restored
- [ ] Start epoch is checkpoint_epoch + 1
- [ ] Artifacts validated before use

---

### Task 4.4: Add Resume Endpoint to Training Worker API

**File(s):**
- `ktrdr/training/training_worker_api.py` (modify)

**Type:** CODING

**Description:**
Add endpoint for backend to dispatch resume requests.

**Endpoint:**
```python
@app.post("/training/resume")
async def resume_training(request: TrainingResumeRequest):
    """Resume training from checkpoint."""
    operation_id = request.operation_id

    # Load checkpoint and create resume context
    resume_context = await worker.restore_from_checkpoint(operation_id)

    # Start resumed training in background
    asyncio.create_task(
        worker.run_resumed_training(operation_id, resume_context)
    )

    return {"success": True, "operation_id": operation_id}
```

**Acceptance Criteria:**
- [ ] Endpoint accepts operation_id
- [ ] Loads checkpoint
- [ ] Starts training in background
- [ ] Returns success response

---

### Task 4.5: Integrate Resume into ModelTrainer

**File(s):**
- `ktrdr/training/model_trainer.py` (modify)

**Type:** CODING

**Description:**
Modify ModelTrainer to accept resume context and continue from checkpoint.

**Implementation Notes:**
- Accept optional resume_context in constructor or method
- Load model/optimizer from bytes if provided
- Set starting epoch
- Merge training history

**Acceptance Criteria:**
- [ ] ModelTrainer accepts resume context
- [ ] Model weights loaded from checkpoint
- [ ] Optimizer state loaded from checkpoint
- [ ] Training starts from correct epoch
- [ ] Training history merged correctly

---

### Task 4.6: Add Resume CLI Command

**File(s):**
- `ktrdr/cli/operations_commands.py` (modify)

**Type:** CODING

**Description:**
Add `ktrdr operations resume <operation_id>` CLI command.

**Command:**
```python
@operations.command()
@click.argument("operation_id")
def resume(operation_id: str):
    """Resume a cancelled or failed operation."""
    async def _resume():
        async with AsyncCLIClient() as client:
            response = await client.post(f"/operations/{operation_id}/resume")

            if not response.get("success"):
                error = response.get("error", {})
                click.echo(f"Error: {error.get('message', 'Resume failed')}")
                return

            data = response["data"]
            click.echo(f"Resumed operation: {data['operation_id']}")
            click.echo(f"Status: {data['status']}")
            click.echo(f"Resumed from: epoch {data['resumed_from']['epoch']}")

    asyncio.run(_resume())
```

**Acceptance Criteria:**
- [ ] Command exists: `ktrdr operations resume <id>`
- [ ] Shows success message with epoch
- [ ] Shows error message on failure
- [ ] Works with existing CLI infrastructure

---

### Task 4.7: Integration Test for Training Resume

**File(s):**
- `tests/integration/test_m4_training_resume.py` (new)

**Type:** CODING

**Description:**
Integration test that verifies full resume flow.

**Test Scenarios:**
1. Start training, cancel at known epoch
2. Resume training
3. Verify training continues from correct epoch
4. Verify checkpoint deleted after completion
5. Verify final model is valid

**Acceptance Criteria:**
- [ ] Test covers full resume flow
- [ ] Test verifies correct resume epoch
- [ ] Test verifies checkpoint cleanup
- [ ] Tests pass: `make test-integration`

---

## Milestone 4 Verification Checklist

Before marking M4 complete:

- [ ] All 7 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1, M2, M3 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/api/endpoints/operations.py` | Modify | 4.1 |
| `ktrdr/api/services/operations_service.py` | Modify | 4.2 |
| `ktrdr/api/repositories/operations_repository.py` | Modify | 4.2 |
| `ktrdr/training/training_worker.py` | Modify | 4.3 |
| `ktrdr/training/checkpoint_restore.py` | Create | 4.3 |
| `ktrdr/training/training_worker_api.py` | Modify | 4.4 |
| `ktrdr/training/model_trainer.py` | Modify | 4.5 |
| `ktrdr/cli/operations_commands.py` | Modify | 4.6 |
| `tests/integration/test_m4_training_resume.py` | Create | 4.7 |
