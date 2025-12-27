# Handoff: Milestone 4 (Training Resume)

## Task 4.1 Complete

**Implemented:** Resume API endpoint at `POST /operations/{operation_id}/resume`

### Endpoint Details

Location: [ktrdr/api/endpoints/operations.py:521-652](ktrdr/api/endpoints/operations.py#L521-L652)

```python
@router.post("/operations/{operation_id}/resume")
async def resume_operation(
    operation_id: str = Path(...),
    operations_service: OperationsService = Depends(get_operations_service),
    checkpoint_service = Depends(_get_checkpoint_service),  # Wrapper for testing
) -> ResumeOperationResponse
```

### Response Models Added

Location: [ktrdr/api/models/operations.py](ktrdr/api/models/operations.py)

```python
ResumedFromInfo     # checkpoint_type, created_at, epoch
ResumeOperationData # operation_id, status, resumed_from
ResumeOperationResponse  # success, data
```

### Service Methods Added

Location: [ktrdr/api/services/operations_service.py:688-810](ktrdr/api/services/operations_service.py#L688-L810)

```python
async def try_resume(self, operation_id: str) -> bool:
    """Atomically update status to RUNNING if CANCELLED/FAILED."""

async def update_status(self, operation_id: str, status: str) -> None:
    """Direct status update (used when checkpoint not available)."""
```

### Key Implementation Notes

**Optimistic Locking:**
`try_resume()` uses async lock + status check to prevent race conditions. Only updates if status is CANCELLED or FAILED.

**FastAPI Dependency Pattern:**
Cross-module dependency (CheckpointService from checkpoints.py) wrapped in local function for proper test mocking:

```python
def _get_checkpoint_service():
    from ktrdr.api.endpoints.checkpoints import get_checkpoint_service
    return get_checkpoint_service()

# In tests
app.dependency_overrides[_get_checkpoint_service] = lambda: mock_service
```

**Error Responses:**
- 404: Operation not found OR no checkpoint available
- 409: Operation already running/completed OR not in resumable state

### Acceptance Criteria Verified

- [x] Endpoint exists at POST /operations/{id}/resume
- [x] Optimistic locking prevents race conditions
- [x] Returns 404 if operation not found
- [x] Returns 404 if no checkpoint
- [x] Returns 409 if already running/completed
- [x] Returns success with resumed_from info

### Tests Added

Location: [tests/unit/api/endpoints/test_resume_operation.py](tests/unit/api/endpoints/test_resume_operation.py)

- 9 unit tests covering all acceptance criteria
- Tests for optimistic locking behavior

---

## Task 4.2 Complete

**Implemented:** Repository-level atomic `try_resume()` with SQL UPDATE

### Repository Method Added

Location: [ktrdr/api/repositories/operations_repository.py:187-230](ktrdr/api/repositories/operations_repository.py#L187-L230)

```python
async def try_resume(self, operation_id: str) -> bool:
    """Atomically update status to RUNNING if currently resumable."""
    # Uses atomic UPDATE with WHERE clause checking status
```

**SQL Pattern:**
```sql
UPDATE operations
SET status = 'running', started_at = NOW(), completed_at = NULL, error_message = NULL
WHERE operation_id = :op_id AND status IN ('cancelled', 'failed')
```

### Service Updated

Location: [ktrdr/api/services/operations_service.py:687-788](ktrdr/api/services/operations_service.py#L687-L788)

- Service `try_resume()` now delegates to repository for atomic DB update
- Cache updated after repository success
- Fallback path for cache-only mode preserved

### Acceptance Criteria Verified

- [x] Atomic update with status check
- [x] Returns True if updated, False otherwise
- [x] Cache updated on success
- [x] Concurrent calls: only one succeeds (SQL atomicity)

### Tests Added

Location: [tests/unit/api/repositories/test_operations_repository.py](tests/unit/api/repositories/test_operations_repository.py)

- 7 new tests for repository `try_resume()`

---

## Task 4.3 Complete

**Implemented:** Training restore functionality in `checkpoint_restore.py` and `TrainingWorker.restore_from_checkpoint()`

### New Module: checkpoint_restore.py

Location: [ktrdr/training/checkpoint_restore.py](ktrdr/training/checkpoint_restore.py)

```python
@dataclass
class TrainingResumeContext:
    """Context for resuming training from a checkpoint."""
    start_epoch: int           # checkpoint_epoch + 1 (per design D7)
    model_weights: bytes       # Serialized model state_dict
    optimizer_state: bytes     # Serialized optimizer state_dict
    scheduler_state: Optional[bytes] = None
    best_model_weights: Optional[bytes] = None
    training_history: dict[str, list[float]] = field(default_factory=dict)
    best_val_loss: float = float("inf")
    original_request: dict[str, Any] = field(default_factory=dict)

async def restore_from_checkpoint(
    checkpoint_service: CheckpointService,
    operation_id: str,
) -> TrainingResumeContext:
    """Load checkpoint and create resume context."""
```

**Custom Exceptions:**
- `CheckpointNotFoundError`: No checkpoint for operation
- `CheckpointCorruptedError`: Missing/invalid artifacts

### TrainingWorker Method Added

Location: [ktrdr/training/training_worker.py:454-481](ktrdr/training/training_worker.py#L454-L481)

```python
async def restore_from_checkpoint(self, operation_id: str) -> TrainingResumeContext:
    """Restore training context from a checkpoint."""
```

### Key Implementation Notes

**Start Epoch Calculation:**
Per design decision D7, resume starts from `checkpoint_epoch + 1` (may redo partial epoch for reproducibility).

**Artifact Validation:**
Uses existing `validate_artifacts()` from `checkpoint_builder.py` to ensure required artifacts (model.pt, optimizer.pt) are present before restore.

### Acceptance Criteria Verified

- [x] Checkpoint loaded from shared storage
- [x] Model weights restored
- [x] Optimizer state restored
- [x] Training history restored
- [x] Start epoch is checkpoint_epoch + 1
- [x] Artifacts validated before use

### Tests Added

Location: [tests/unit/training/test_checkpoint_restore.py](tests/unit/training/test_checkpoint_restore.py)

- 20 unit tests covering:
  - TrainingResumeContext dataclass
  - restore_from_checkpoint function
  - Artifact validation (missing/empty)
  - TrainingWorker.restore_from_checkpoint method

---

## Task 4.4 Complete

**Implemented:** Training worker resume endpoint at `POST /training/resume`

### Endpoint Added

Location: [ktrdr/training/training_worker.py:127-170](ktrdr/training/training_worker.py#L127-L170)

```python
@self.app.post("/training/resume")
async def resume_training(request: TrainingResumeRequest):
    resume_context = await self.restore_from_checkpoint(operation_id)
    asyncio.create_task(self._execute_resumed_training(operation_id, resume_context))
    return {"success": True, "operation_id": operation_id, "status": "started", ...}
```

### Request Model Added

Location: [ktrdr/training/training_worker.py:65-72](ktrdr/training/training_worker.py#L65-L72)

```python
class TrainingResumeRequest(WorkerOperationMixin):
    operation_id: str = Field(description="Operation ID to resume")
```

### New Method Added

Location: [ktrdr/training/training_worker.py:538-759](ktrdr/training/training_worker.py#L538-L759)

```python
async def _execute_resumed_training(
    self, operation_id: str, resume_context: TrainingResumeContext
) -> dict[str, Any]:
    """Execute resumed training from checkpoint."""
```

### Key Implementation Notes

**Endpoint Pattern:**
Follows same pattern as `/training/start` - returns immediately, executes training in background via `asyncio.create_task()`.

**Error Handling:**
- 404 if no checkpoint found (`CheckpointNotFoundError`)
- 422 if checkpoint corrupted (`CheckpointCorruptedError`)

**Resume Context Integration:**
`_execute_resumed_training` is structurally ready but actual model/optimizer restoration requires Task 4.5 to add `resume_context` support to `LocalTrainingOrchestrator`.

### Acceptance Criteria Verified

- [x] Endpoint accepts operation_id
- [x] Loads checkpoint (via `restore_from_checkpoint`)
- [x] Starts training in background
- [x] Returns success response

### Tests Added

Location: [tests/unit/training/test_training_worker_resume_endpoint.py](tests/unit/training/test_training_worker_resume_endpoint.py)

- 10 unit tests covering:
  - TrainingResumeRequest model
  - Endpoint existence and success response
  - restore_from_checkpoint integration
  - Error handling (404, 422)
  - _execute_resumed_training method

---

## Task 4.5 Complete

**Implemented:** ModelTrainer resume_context integration and full pipeline wiring

### ModelTrainer Updates

Location: [ktrdr/training/model_trainer.py:103-160](ktrdr/training/model_trainer.py#L103-L160)

```python
def __init__(
    self,
    config: dict[str, Any],
    progress_callback=None,
    cancellation_token: CancellationToken | None = None,
    checkpoint_callback=None,
    resume_context: Optional["TrainingResumeContext"] = None,  # NEW
)
```

**Resume Logic in `train()` method:**
1. After `model.to(device)`: Load model weights from `resume_context.model_weights`
2. After creating optimizer: Load optimizer state from `resume_context.optimizer_state`
3. After creating scheduler: Load scheduler state if provided
4. Training loop: `for epoch in range(start_epoch, epochs)`
5. Progress calculations: Adjusted for resumed training (relative to remaining epochs)

### Pipeline Wiring

**Call chain updated:**
```
TrainingWorker._execute_resumed_training(resume_context)
    → LocalTrainingOrchestrator(resume_context=resume_context)
        → TrainingPipeline.train_strategy(resume_context=resume_context)
            → TrainingPipeline.train_model(resume_context=resume_context)
                → ModelTrainer(resume_context=resume_context)
```

**Files modified:**
- `ktrdr/api/services/training/local_orchestrator.py` - Added `resume_context` parameter
- `ktrdr/training/training_pipeline.py` - Added `resume_context` to `train_strategy()` and `train_model()`
- `ktrdr/training/training_worker.py` - Pass `resume_context` to orchestrator

### Acceptance Criteria Verified

- [x] ModelTrainer accepts resume context
- [x] Model weights loaded from checkpoint
- [x] Optimizer state loaded from checkpoint
- [x] Training starts from correct epoch
- [x] Training history merged correctly

### Tests Added

Location: [tests/unit/training/test_model_trainer_resume.py](tests/unit/training/test_model_trainer_resume.py)

- 10 unit tests covering:
  - resume_context parameter acceptance
  - Model/optimizer/scheduler state restoration
  - Correct start epoch (loop starts from `resume_context.start_epoch`)
  - Training history merging
  - Edge cases (epoch 0, final epoch, scheduler state, best_model_weights)

---

## Task 4.6 Complete

**Implemented:** Resume CLI command `ktrdr operations resume <operation_id>`

### CLI Command Added

Location: [ktrdr/cli/operations_commands.py:668-771](ktrdr/cli/operations_commands.py#L668-L771)

```bash
ktrdr operations resume <operation_id> [--verbose]
```

**Usage:**

```bash
# Resume a cancelled or failed operation
ktrdr operations resume op_training_20241201_123456

# With verbose output
ktrdr operations resume op_training_20241201_123456 --verbose
```

**Output (success):**
```
✅ Successfully resumed operation: op_training_20241201_123456
Status: RUNNING
Resumed from: epoch 25
💡 Use 'ktrdr operations status op_training_20241201_123456' to monitor progress
```

### API Client Method Added

Location: [ktrdr/cli/api_client.py:772-781](ktrdr/cli/api_client.py#L772-L781)

```python
async def resume_operation(self, operation_id: str) -> dict[str, Any]:
    """Resume a cancelled or failed operation from checkpoint."""
```

### Error Handling

- 404: Operation not found or no checkpoint available
- 409: Operation already running/completed or not in resumable state

### Acceptance Criteria Verified

- [x] Command exists: `ktrdr operations resume <id>`
- [x] Shows success message with epoch
- [x] Shows error message on failure
- [x] Works with existing CLI infrastructure

### Tests Added

Location: [tests/unit/cli/test_resume_command.py](tests/unit/cli/test_resume_command.py)

- 9 unit tests covering:
  - API client `resume_operation` method (success, failure)
  - CLI command success with epoch display
  - API connection failure handling
  - 404 not found error handling
  - 409 conflict error handling
  - No checkpoint error handling
  - Command registration verification

---

## Task 4.7 Complete

**Implemented:** Full integration test suite for training resume flow

### Test File

Location: [tests/integration/test_m4_training_resume.py](tests/integration/test_m4_training_resume.py)

### Test Classes

| Class                            | Tests | Purpose                                     |
| -------------------------------- | ----- | ------------------------------------------- |
| `TestM4FullResumeFlow`           | 1     | Full start→cancel→resume→complete flow     |
| `TestM4ResumeFromCorrectEpoch`   | 3     | Verify epoch continuation (D7 compliance)  |
| `TestM4CheckpointCleanup`        | 3     | Verify checkpoint deletion on completion   |
| `TestM4ModelValidityAfterResume` | 3     | Verify model/optimizer state restoration   |
| `TestM4EdgeCases`                | 5     | Resume status transitions, no-checkpoint   |
| `TestM4ResumeContextIntegration` | 2     | TrainingResumeContext field validation     |

**Total:** 17 tests covering all acceptance criteria

### Test Infrastructure

Uses in-memory mock services for fast feedback:

- `IntegrationCheckpointService` — In-memory checkpoint storage with filesystem artifacts
- `MockOperationsRepository` — In-memory operation state with `try_resume()` semantics

### Key Scenarios Tested

1. **Full Resume Flow:** Start training → periodic checkpoints → cancel → resume → complete → checkpoint deleted
2. **Epoch Continuation:** Per design D7, resume starts from `checkpoint_epoch + 1`
3. **Model Validity:** Checkpoint weights/optimizer state load correctly into fresh models
4. **Status Transitions:** Only CANCELLED/FAILED operations can be resumed

### Task 4.7 Acceptance Criteria

- [x] Test covers full resume flow
- [x] Test verifies correct resume epoch
- [x] Test verifies checkpoint cleanup
- [x] Tests pass

---

## E2E Testing Issues & Fixes (Session 2025-12-27)

### Issue 1: Missing Dispatch in Resume Endpoint (FIXED)

**Problem**: The resume endpoint at `ktrdr/api/endpoints/operations.py:629` had a TODO comment instead of actual dispatch logic. Status was updated to RUNNING but training never started.

**Fix Applied**:
- Added `worker_registry` dependency to resume endpoint
- Added dispatch logic to call worker's `/training/resume` endpoint
- Added error handling with status revert on dispatch failure

**Key Code Added** (lines 639-683):
```python
from ktrdr.api.models.workers import WorkerType
worker = worker_registry.select_worker(WorkerType.TRAINING)
# ... dispatch via httpx to worker.endpoint_url/training/resume
```

### Issue 2: Enum vs String Type Errors (FIXED)

**Problem**: `op.operation_type` and `op.status` sometimes returned Enum, sometimes string. Calling `.value` on a string caused `AttributeError`.

**Fix Applied**: Added safe extraction pattern:
```python
op_type = op.operation_type.value if hasattr(op.operation_type, "value") else str(op.operation_type)
status_value = op.status.value if hasattr(op.status, "value") else str(op.status)
```

### Issue 3: WorkerRegistry.select_worker Expects Enum (FIXED)

**Problem**: Called `worker_registry.select_worker("training")` but function expects `WorkerType.TRAINING` enum.

**Fix Applied**: Import and use enum:
```python
from ktrdr.api.models.workers import WorkerType
worker = worker_registry.select_worker(WorkerType.TRAINING)
```

### Issue 4: Strategy YAML Truncated in Checkpoint (BLOCKING - NOT FIXED)

**Problem**: Strategy YAML stored in checkpoint DB state is truncated, causing resume to fail with YAML parse error.

**Root Cause**: The `original_request.strategy_yaml` field in checkpoint state is truncated, likely due to JSON column size limits.

**Proposed Fix**: Don't store strategy YAML in checkpoint. Store `strategy_path` and read from disk on resume. See: `docs/architecture/checkpoint/TASK_fix_checkpoint_strategy_storage.md`

---

## E2E Test Execution Guide

### Prerequisites

1. **Backend must be restarted** after code changes (Docker mounts code but Python caches modules):
   ```bash
   docker compose restart backend
   ```

2. **Workers must re-register** after backend restart:
   ```bash
   docker compose restart training-worker-1 training-worker-2
   sleep 20  # Wait for registration
   curl http://localhost:8000/api/v1/workers  # Verify 2+ training workers
   ```

### API Endpoints (Correct Paths)

| Action | Method | Endpoint |
|--------|--------|----------|
| Start training | POST | `/api/v1/trainings/start` (not `/training/start`) |
| Check status | GET | `/api/v1/operations/{id}` |
| Cancel | DELETE | `/api/v1/operations/{id}` (not `/cancel`) |
| Resume | POST | `/api/v1/operations/{id}/resume` |
| Check checkpoint | GET | `/api/v1/checkpoints/{id}` |

### Training Request Schema

```json
{
  "strategy_name": "test_e2e_local_pull",
  "symbols": ["EURUSD"],
  "timeframes": ["5m"]
}
```

Note: `epochs` and `checkpoint_interval` come from strategy YAML, not API request.

### Shell Scripting Gotchas

The shell in this environment has issues with multi-line commands. Use separate Bash calls:
```bash
# BAD - newlines break
sleep 5
echo "done"

# GOOD - separate calls
Bash: sleep 5
Bash: echo "done"
```

### Orphan Operations

If an operation gets stuck in RUNNING but workers restarted, wait ~60 seconds for orphan detector to mark it FAILED, or start a fresh operation.

---

## Milestone 4 Status

All 8 tasks completed.

- Task 4.1: Resume API Endpoint ✅
- Task 4.2: try_resume in OperationsService ✅
- Task 4.3: Training Restore in Worker ✅
- Task 4.4: Resume Endpoint in Training Worker API ✅
- Task 4.5: Resume Context in ModelTrainer ✅
- Task 4.6: Resume CLI Command ✅
- Task 4.7: Integration Tests ✅
- Task 4.8: Fix Checkpoint Strategy Storage ✅

**Next Step**: Run full E2E test to verify resume flow works end-to-end.

---

## Task 4.8 Complete

**Implemented:** Checkpoint stores `strategy_path` instead of `strategy_yaml` to avoid DB truncation

### Root Cause

Line 233 in training_worker.py was explicitly truncating strategy YAML:
```python
original_request = {
    "strategy_yaml": request.strategy_yaml[:100],  # TRUNCATION BUG
    ...
}
```

### Fix Applied

1. **TrainingStartRequest**: Added `strategy_path` field (optional)

2. **training_service.py**: Sends `strategy_path` (relative format) in request payload

3. **training_worker.py**:
   - Stores `strategy_path` in checkpoint (not `strategy_yaml`)
   - On resume, reads strategy from disk using path
   - Backward compatible with old checkpoints that have `strategy_yaml`

### Key Code Locations

- [ktrdr/training/training_worker.py:50-54](ktrdr/training/training_worker.py#L50-L54) - `strategy_path` field
- [ktrdr/training/training_worker.py:237-245](ktrdr/training/training_worker.py#L237-L245) - Checkpoint storage
- [ktrdr/training/training_worker.py:596-641](ktrdr/training/training_worker.py#L596-L641) - Resume loading
- [ktrdr/api/services/training_service.py:358-379](ktrdr/api/services/training_service.py#L358-L379) - Path in payload

### Acceptance Criteria Verified

- [x] Checkpoint state does NOT contain `strategy_yaml`
- [x] Checkpoint state contains `strategy_path`
- [x] Resume reads strategy from disk using `strategy_path`
- [x] Resume fails gracefully if strategy file doesn't exist
- [x] Unit tests pass (176 training tests, 7 new for Task 4.8)
- [x] M4 integration tests pass (17/17)
