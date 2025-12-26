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

### Notes for Task 4.2

Task 4.2 will enhance `try_resume()` with repository-level atomicity. Current implementation uses in-memory lock + cache update. Repository-level implementation should use atomic SQL UPDATE with status check.

### Notes for Task 4.3-4.4

The resume endpoint currently:
1. Updates status to RUNNING (via try_resume)
2. Verifies checkpoint exists
3. Returns success response

**TODO:** Task 4.4 will add worker dispatch:
```python
# After checkpoint verification, dispatch to worker
await dispatch_resume_to_worker(worker, operation_id)
```

The worker dispatch pattern should follow existing training dispatch in TrainingService._run_distributed_worker_training.
