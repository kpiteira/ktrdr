---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 1: Operations Persistence + Worker Re-Registration

**Branch:** `feature/checkpoint-m1-operations-persistence`
**Depends On:** None (foundation milestone)
**Estimated Tasks:** 11

---

## Capability

When M1 is complete:
- Operations are persisted to PostgreSQL (survive backend restart)
- Workers detect missed health checks and re-register automatically
- Operation status syncs when workers re-register
- Workers report completed operations on re-registration

---

## E2E Test Scenario

```bash
#!/bin/bash
# M1 E2E Test: Operations persist and sync after backend restart

set -e

echo "=== M1 E2E Test: Operations Persistence + Re-Registration ==="

# 1. Verify worker is registered
echo "Step 1: Check worker registered..."
WORKERS=$(curl -s http://localhost:8000/api/v1/workers | jq '.data | length')
if [ "$WORKERS" -lt 1 ]; then
    echo "FAIL: No workers registered"
    exit 1
fi
echo "OK: $WORKERS worker(s) registered"

# 2. Start a training operation
echo "Step 2: Start training operation..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{"strategy_path": "strategies/test.yaml", "symbol": "EURUSD", "timeframe": "1h"}')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 3. Verify operation is RUNNING
echo "Step 3: Verify operation status..."
sleep 2
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
if [ "$STATUS" != "RUNNING" ]; then
    echo "FAIL: Expected RUNNING, got $STATUS"
    exit 1
fi
echo "OK: Operation status is RUNNING"

# 4. Restart backend
echo "Step 4: Restarting backend..."
docker-compose restart backend
sleep 10  # Wait for backend to come up

# 5. Verify operation still exists in DB
echo "Step 5: Check operation persisted..."
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
if [ -z "$STATUS" ] || [ "$STATUS" == "null" ]; then
    echo "FAIL: Operation not found after restart"
    exit 1
fi
echo "OK: Operation exists, status: $STATUS"

# 6. Wait for worker to re-register (max 45s)
echo "Step 6: Waiting for worker re-registration..."
for i in {1..9}; do
    sleep 5
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    WORKER=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.worker_id')
    echo "  Check $i: status=$STATUS, worker=$WORKER"
    if [ "$STATUS" == "RUNNING" ] && [ "$WORKER" != "null" ] && [ -n "$WORKER" ]; then
        echo "OK: Operation synced - RUNNING on $WORKER"
        break
    fi
done

# 7. Final verification
echo "Step 7: Final verification..."
FINAL=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq '.data')
echo "Final state: $FINAL"

STATUS=$(echo $FINAL | jq -r '.status')
WORKER=$(echo $FINAL | jq -r '.worker_id')

if [ "$STATUS" == "RUNNING" ] && [ "$WORKER" != "null" ]; then
    echo ""
    echo "=== M1 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M1 E2E TEST FAILED ==="
    echo "Expected: status=RUNNING, worker_id=<some_id>"
    echo "Got: status=$STATUS, worker_id=$WORKER"
    exit 1
fi
```

---

## Tasks

### Task 1.1: Create Operations Database Table

**File(s):**
- `ktrdr/api/models/db/operations.py` (new)
- `alembic/versions/xxx_create_operations_table.py` (new)

**Type:** CODING

**Description:**
Create the operations table schema and Alembic migration. This is the foundation for persistent operations.

**Implementation Notes:**
- Use SQLAlchemy ORM model
- Include all fields from VALIDATION.md schema
- Add indexes for status and worker_id queries
- JSONB for metadata and result fields

**Schema:**
```python
class OperationRecord(Base):
    __tablename__ = "operations"

    operation_id = Column(String(255), primary_key=True)
    operation_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)

    worker_id = Column(String(255), nullable=True)
    is_backend_local = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    progress_percent = Column(Float, default=0)
    progress_message = Column(String(500), nullable=True)

    metadata_ = Column("metadata", JSONB, nullable=False, default={})
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    reconciliation_status = Column(String(50), nullable=True)
```

**Acceptance Criteria:**
- [ ] SQLAlchemy model defined with all fields
- [ ] Alembic migration creates table
- [ ] Migration runs successfully: `alembic upgrade head`
- [ ] Indexes created for status, worker_id, operation_type
- [ ] Migration rollback works: `alembic downgrade -1`

---

### Task 1.2: Create Operations Repository

**File(s):**
- `ktrdr/api/repositories/operations_repository.py` (new)
- `tests/unit/api/repositories/test_operations_repository.py` (new)

**Type:** CODING

**Description:**
Create a repository class for operations CRUD with the database. This isolates DB access from business logic.

**Implementation Notes:**
- Async SQLAlchemy session handling
- Methods: create, get, update, list, delete
- Convert between DB model and domain model (OperationInfo)

**Key Methods:**
```python
class OperationsRepository:
    async def create(self, operation: OperationInfo) -> OperationInfo
    async def get(self, operation_id: str) -> Optional[OperationInfo]
    async def update(self, operation_id: str, **fields) -> Optional[OperationInfo]
    async def list(self, status: Optional[str] = None,
                   worker_id: Optional[str] = None) -> list[OperationInfo]
    async def delete(self, operation_id: str) -> bool
```

**Acceptance Criteria:**
- [ ] Repository class with all CRUD methods
- [ ] Proper async session handling
- [ ] Conversion between DB model and OperationInfo
- [ ] Unit tests with mocked DB session
- [ ] Tests pass: `make test-unit`

---

### Task 1.3: Refactor OperationsService to Use Repository

**File(s):**
- `ktrdr/api/services/operations_service.py` (modify)
- `tests/unit/api/services/test_operations_service.py` (modify)

**Type:** CODING

**Description:**
Refactor OperationsService to use the repository for persistence while keeping runtime handles (tasks, bridges, tokens) in memory.

**Implementation Notes:**
- Inject repository via constructor
- Remove `self._operations` dict as primary storage
- Keep `self._cache` as read-through cache
- Keep runtime handles in memory: `_operation_tasks`, `_local_bridges`, `_cancellation_coordinator`
- All state mutations go to DB first, then update cache

**Key Pattern:**
```python
class OperationsService:
    def __init__(self, repository: OperationsRepository):
        self._repository = repository
        self._cache: dict[str, OperationInfo] = {}  # Read cache

        # Runtime handles (not persisted)
        self._operation_tasks: dict[str, asyncio.Task] = {}
        self._local_bridges: dict[str, Any] = {}
        self._cancellation_coordinator = get_global_coordinator()

    async def create_operation(self, ...) -> OperationInfo:
        operation = OperationInfo(...)
        # DB first
        await self._repository.create(operation)
        # Then cache
        self._cache[operation.operation_id] = operation
        return operation

    async def get_operation(self, operation_id: str) -> Optional[OperationInfo]:
        # Check cache
        if operation_id in self._cache:
            return self._cache[operation_id]
        # Miss → DB
        operation = await self._repository.get(operation_id)
        if operation:
            self._cache[operation_id] = operation
        return operation
```

**Acceptance Criteria:**
- [ ] OperationsService uses repository for all persistence
- [ ] Cache is read-through (DB on miss)
- [ ] All writes go to DB first
- [ ] Runtime handles still work (tasks, bridges, tokens)
- [ ] Existing tests updated and passing
- [ ] No behavior change for existing callers

---

### Task 1.4: Enhance Worker Registration Model

**File(s):**
- `ktrdr/api/models/workers.py` (modify)
- `ktrdr/api/models/operations.py` (modify if needed)

**Type:** CODING

**Description:**
Add `current_operation_id` and `completed_operations` fields to worker registration request model.

**Implementation Notes:**
- Extend existing Pydantic models
- `completed_operations` is a list of operation summaries
- Make new fields optional for backward compatibility

**Models:**
```python
class CompletedOperationReport(BaseModel):
    """Operation that completed while backend was unavailable."""
    operation_id: str
    status: Literal["COMPLETED", "FAILED", "CANCELLED"]
    result: Optional[dict] = None
    error_message: Optional[str] = None
    completed_at: datetime

class WorkerRegistrationRequest(BaseModel):
    worker_id: str
    worker_type: str
    endpoint_url: str
    capabilities: Optional[dict] = None
    # NEW fields for resilience
    current_operation_id: Optional[str] = None
    completed_operations: list[CompletedOperationReport] = []
```

**Acceptance Criteria:**
- [ ] Registration request model has new fields
- [ ] Fields are optional (backward compatible)
- [ ] CompletedOperationReport model defined
- [ ] Model validation works correctly

---

### Task 1.5: Implement Reconciliation Logic in WorkerRegistry

**File(s):**
- `ktrdr/api/services/worker_registry.py` (modify)
- `tests/unit/api/services/test_worker_registry.py` (modify)

**Type:** CODING

**Description:**
When a worker registers with `current_operation_id` or `completed_operations`, reconcile operation status in the database.

**Implementation Notes:**
- Process `completed_operations` first (update DB to terminal states)
- Then process `current_operation_id` (sync running status)
- Use reconciliation rules from VALIDATION.md

**Reconciliation Rules:**
```python
async def _reconcile_completed_operations(self, completed: list[CompletedOperationReport]):
    for report in completed:
        db_op = await self._operations_service.get_operation(report.operation_id)
        if db_op is None:
            # Unknown - create record
            await self._operations_service.create_operation(...)
        elif db_op.status not in ['COMPLETED', 'CANCELLED']:
            # Update to terminal state
            await self._operations_service.update_status(
                report.operation_id,
                status=report.status,
                result=report.result,
                completed_at=report.completed_at
            )

async def _reconcile_current_operation(self, operation_id: str, worker_id: str):
    db_op = await self._operations_service.get_operation(operation_id)

    if db_op is None:
        # Create record for unknown operation
        await self._operations_service.create_operation(...)
    elif db_op.status == 'COMPLETED':
        # Trust DB, tell worker to stop
        await self._send_stop_to_worker(worker_id, operation_id)
    elif db_op.status in ['FAILED', 'CANCELLED', 'PENDING', 'PENDING_RECONCILIATION']:
        # Worker is alive, so it's running
        await self._operations_service.update_status(
            operation_id, status='RUNNING', worker_id=worker_id
        )
```

**Acceptance Criteria:**
- [ ] Completed operations reconciled on registration
- [ ] Current operation reconciled on registration
- [ ] Unknown operations create DB records
- [ ] COMPLETED in DB sends stop to worker
- [ ] FAILED/CANCELLED in DB updated to RUNNING
- [ ] Unit tests cover all reconciliation scenarios

---

### Task 1.6: Add Health Check Tracking to Worker Base

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** CODING

**Description:**
Track when the backend last health-checked this worker. This enables detection of backend restart.

**Implementation Notes:**
- Add `_last_health_check_received: Optional[datetime]` field
- Update timestamp in `/health` endpoint handler
- This is preparation for Task 1.7

**Code Changes:**
```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing ...
        self._last_health_check_received: Optional[datetime] = None

    # In health endpoint setup:
    @self.app.get("/health")
    async def health_check():
        # Track when backend checked on us
        self._last_health_check_received = datetime.utcnow()

        return {
            "healthy": True,
            "worker_id": self.worker_id,
            "worker_status": "busy" if self._current_operation_id else "idle",
            "current_operation": self._current_operation_id,
        }
```

**Acceptance Criteria:**
- [ ] `_last_health_check_received` field added
- [ ] Health endpoint updates timestamp
- [ ] No change to health response format (backward compatible)

---

### Task 1.7: Implement Re-Registration Monitor

**File(s):**
- `ktrdr/workers/base.py` (modify)
- `tests/unit/workers/test_base_reregistration.py` (new)

**Type:** CODING

**Description:**
Add a background task that detects missed health checks and re-registers with the backend.

**Implementation Notes:**
- Check every 10 seconds
- If no health check received in 30 seconds, assume backend restarted
- Check if still registered (GET /workers/{id}), if not → register
- Include `current_operation_id` and `completed_operations` in registration

**Code Structure:**
```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing ...
        self._health_check_timeout: int = 30  # seconds
        self._reregistration_check_interval: int = 10  # seconds
        self._completed_operations: list[CompletedOperationReport] = []
        self._monitor_task: Optional[asyncio.Task] = None

    async def _start_reregistration_monitor(self):
        self._monitor_task = asyncio.create_task(self._monitor_health_checks())

    async def _monitor_health_checks(self):
        while True:
            await asyncio.sleep(self._reregistration_check_interval)

            if self._last_health_check_received is None:
                continue

            elapsed = (datetime.utcnow() - self._last_health_check_received).total_seconds()

            if elapsed > self._health_check_timeout:
                logger.warning(f"No health check in {elapsed:.0f}s - checking registration")
                await self._ensure_registered()
                self._last_health_check_received = datetime.utcnow()

    async def _ensure_registered(self):
        # Check if registered
        response = await self._http_client.get(f"{self.backend_url}/api/v1/workers/{self.worker_id}")
        if response.status_code == 200:
            return  # Already registered

        # Not registered - register now
        await self._register_with_backend()

    async def _register_with_backend(self):
        payload = {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "endpoint_url": self._get_endpoint_url(),
            "capabilities": self._get_capabilities(),
            "current_operation_id": self._current_operation_id,
            "completed_operations": [op.dict() for op in self._completed_operations],
        }
        await self._http_client.post(f"{self.backend_url}/api/v1/workers/register", json=payload)
        self._completed_operations.clear()  # Clear after successful report

    def record_operation_completed(self, operation_id: str, status: str, result: Optional[dict] = None):
        """Called when an operation completes - stores for next registration."""
        self._completed_operations.append(CompletedOperationReport(
            operation_id=operation_id,
            status=status,
            result=result,
            completed_at=datetime.utcnow()
        ))
```

**Acceptance Criteria:**
- [ ] Background monitor task starts on worker startup
- [ ] Detects missed health checks (>30s)
- [ ] Checks registration status before re-registering
- [ ] Includes current_operation_id in registration
- [ ] Includes completed_operations in registration
- [ ] Clears completed_operations after successful registration
- [ ] Unit tests for monitor logic

---

### Task 1.8: Backend Startup Reconciliation

**File(s):**
- `ktrdr/api/main.py` (modify)
- `ktrdr/api/services/startup_reconciliation.py` (new)
- `tests/unit/api/services/test_startup_reconciliation.py` (new)

**Type:** CODING

**Description:**
On backend startup, mark all RUNNING operations as PENDING_RECONCILIATION so orphan detector can track them.

**Implementation Notes:**
- Run on FastAPI startup event
- Query all RUNNING operations
- Set `reconciliation_status = 'PENDING_RECONCILIATION'`
- Backend-local operations: Mark FAILED immediately (M7 will add checkpoint awareness)

**Code Structure:**
```python
class StartupReconciliation:
    def __init__(self, operations_service: OperationsService):
        self._operations_service = operations_service

    async def reconcile(self):
        """Called on backend startup."""
        running_ops = await self._operations_service.list_operations(status='RUNNING')

        for op in running_ops:
            if op.is_backend_local:
                # Backend-local: process died, mark failed
                await self._operations_service.update_status(
                    op.operation_id,
                    status='FAILED',
                    error_message='Backend restarted'
                )
            else:
                # Worker-based: wait for re-registration
                await self._operations_service.update_reconciliation_status(
                    op.operation_id,
                    reconciliation_status='PENDING_RECONCILIATION'
                )

        logger.info(f"Startup reconciliation: {len(running_ops)} operations processed")

# In main.py
@app.on_event("startup")
async def startup_reconciliation():
    reconciliation = StartupReconciliation(get_operations_service())
    await reconciliation.reconcile()
```

**Acceptance Criteria:**
- [ ] Startup reconciliation runs on FastAPI startup
- [ ] All RUNNING worker-based ops marked PENDING_RECONCILIATION
- [ ] Backend-local ops marked FAILED (simple for now, M7 adds checkpoint check)
- [ ] Logging shows reconciliation summary
- [ ] Unit tests cover startup scenarios

---

### Task 1.9: Update Worker Registration Endpoint

**File(s):**
- `ktrdr/api/endpoints/workers.py` (modify)

**Type:** CODING

**Description:**
Update the worker registration endpoint to accept and process the new fields.

**Implementation Notes:**
- Accept `current_operation_id` and `completed_operations` in request
- Call WorkerRegistry with new fields
- Backward compatible (fields are optional)

**Acceptance Criteria:**
- [ ] Endpoint accepts new fields
- [ ] Passes fields to WorkerRegistry
- [ ] Works without new fields (backward compatible)
- [ ] Returns success response

---

### Task 1.10: Add GET Worker Endpoint

**File(s):**
- `ktrdr/api/endpoints/workers.py` (modify)

**Type:** CODING

**Description:**
Add endpoint for workers to check their registration status. This is needed for the re-registration monitor to verify if the backend knows about this worker.

**Implementation Notes:**

- Simple lookup by worker_id
- Return 404 if not found (triggers re-registration)
- Return worker info if found

**Code:**

```python
@router.get(
    "/workers/{worker_id}",
    tags=["Workers"],
    summary="Get worker by ID",
    description="Check if a specific worker is registered",
)
async def get_worker(
    worker_id: str,
    registry: WorkerRegistry = Depends(get_worker_registry),
) -> dict:
    """
    Get a specific worker by ID.

    Used by workers to check if they're still registered after
    backend restart.

    Args:
        worker_id: The worker's unique identifier
        registry: The worker registry (injected dependency)

    Returns:
        dict: Worker information if found

    Raises:
        HTTPException: 404 if worker not found
    """
    worker = registry.get_worker(worker_id)
    if worker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Worker not found: {worker_id}"
        )
    return worker.to_dict()
```

**Acceptance Criteria:**

- [ ] Endpoint exists at GET /workers/{worker_id}
- [ ] Returns worker info if found
- [ ] Returns 404 if not found
- [ ] WorkerRegistry has get_worker method

---

### Task 1.11: Integration Test

**File(s):**
- `tests/integration/test_m1_operations_persistence.py` (new)

**Type:** CODING

**Description:**
Integration test that verifies the full M1 flow: create operation, restart simulation, re-registration, status sync.

**Implementation Notes:**
- Can't actually restart backend in test, but can simulate by clearing registry
- Test the reconciliation logic end-to-end

**Test Scenarios:**
1. Create operation, verify in DB
2. Simulate backend restart (clear in-memory state)
3. Worker re-registration with current_operation_id
4. Verify status synced correctly
5. Worker re-registration with completed_operations
6. Verify completed operation updated in DB

**Acceptance Criteria:**
- [ ] Test creates operation and verifies persistence
- [ ] Test simulates restart scenario
- [ ] Test verifies re-registration syncs status
- [ ] Test verifies completed operations reconciliation
- [ ] Tests pass: `make test-integration`

---

## Milestone 1 Verification Checklist

Before marking M1 complete:

- [ ] All 11 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes (see above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in existing functionality
- [ ] Code reviewed and merged to feature branch

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/api/models/db/operations.py` | Create | 1.1 |
| `alembic/versions/xxx_create_operations_table.py` | Create | 1.1 |
| `ktrdr/api/repositories/operations_repository.py` | Create | 1.2 |
| `ktrdr/api/services/operations_service.py` | Modify | 1.3 |
| `ktrdr/api/models/workers.py` | Modify | 1.4 |
| `ktrdr/api/services/worker_registry.py` | Modify | 1.5, 1.10 |
| `ktrdr/workers/base.py` | Modify | 1.6, 1.7 |
| `ktrdr/api/main.py` | Modify | 1.8 |
| `ktrdr/api/services/startup_reconciliation.py` | Create | 1.8 |
| `ktrdr/api/endpoints/workers.py` | Modify | 1.9, 1.10 |
| `tests/unit/api/repositories/test_operations_repository.py` | Create | 1.2 |
| `tests/unit/api/services/test_operations_service.py` | Modify | 1.3 |
| `tests/unit/api/services/test_worker_registry.py` | Modify | 1.5 |
| `tests/unit/workers/test_base_reregistration.py` | Create | 1.7 |
| `tests/unit/api/services/test_startup_reconciliation.py` | Create | 1.8 |
| `tests/integration/test_m1_operations_persistence.py` | Create | 1.11 |
