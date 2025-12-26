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

### Notes for Task 4.4

Task 4.4 will add the worker API endpoint:
```python
@app.post("/training/resume")
async def resume_training(request: TrainingResumeRequest):
    resume_context = await worker.restore_from_checkpoint(operation_id)
    asyncio.create_task(worker.run_resumed_training(operation_id, resume_context))
```

Task 4.5 will integrate the resume context into ModelTrainer to load weights/optimizer state.
