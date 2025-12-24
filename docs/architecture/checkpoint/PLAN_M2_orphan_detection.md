---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 2: Orphan Detection

**Branch:** `feature/checkpoint-m2-orphan-detection`
**Depends On:** M1 (Operations Persistence)
**Estimated Tasks:** 5

---

## Capability

When M2 is complete:
- RUNNING operations with no worker are detected
- After 60-second timeout, orphan operations marked FAILED
- Operations in PENDING_RECONCILIATION that aren't claimed are marked FAILED
- System self-heals without manual intervention

---

## E2E Test Scenario

```bash
#!/bin/bash
# M2 E2E Test: Orphan Detection

set -e

echo "=== M2 E2E Test: Orphan Detection ==="

# 1. Start a training operation
echo "Step 1: Start training operation..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{"strategy_path": "strategies/test.yaml", "symbol": "EURUSD", "timeframe": "1h"}')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Verify it's running
sleep 2
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
echo "Initial status: $STATUS"

# 3. Kill the worker (simulate crash)
echo "Step 3: Killing worker..."
docker-compose stop training-worker

# 4. Wait for orphan detection (60s timeout + some buffer)
echo "Step 4: Waiting for orphan detection (70s)..."
for i in {1..14}; do
    sleep 5
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    echo "  Check $i: status=$STATUS"
    if [ "$STATUS" == "FAILED" ]; then
        echo "Orphan detected at check $i"
        break
    fi
done

# 5. Verify final state
echo "Step 5: Final verification..."
FINAL=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq '.data')
STATUS=$(echo $FINAL | jq -r '.status')
ERROR=$(echo $FINAL | jq -r '.error_message')

echo "Final status: $STATUS"
echo "Error message: $ERROR"

# 6. Restart worker for cleanup
docker-compose start training-worker

if [ "$STATUS" == "FAILED" ]; then
    echo ""
    echo "=== M2 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M2 E2E TEST FAILED ==="
    exit 1
fi
```

---

## Tasks

### Task 2.1: Create OrphanOperationDetector Service

**File(s):**
- `ktrdr/api/services/orphan_detector.py` (new)
- `tests/unit/api/services/test_orphan_detector.py` (new)

**Type:** CODING

**Task Categories:** Background/Async, Wiring/DI, Cross-Component

**Description:**
Create the orphan detection service that runs as a background task, checking for RUNNING operations with no worker.

**Implementation Notes:**
- Background asyncio task
- Check every 15 seconds
- Track "first seen" time for potential orphans
- After 60 seconds without a worker claiming it, mark FAILED
- Also handle PENDING_RECONCILIATION status (from M1)

**Code Structure:**
```python
class OrphanOperationDetector:
    def __init__(
        self,
        operations_service: OperationsService,
        worker_registry: WorkerRegistry,
        orphan_timeout_seconds: int = 60,
        check_interval_seconds: int = 15,
    ):
        self._operations_service = operations_service
        self._worker_registry = worker_registry
        self._orphan_timeout = orphan_timeout_seconds
        self._check_interval = check_interval_seconds
        self._potential_orphans: dict[str, datetime] = {}
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._task = asyncio.create_task(self._detection_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def _detection_loop(self):
        while True:
            await asyncio.sleep(self._check_interval)
            await self._check_for_orphans()

    async def _check_for_orphans(self):
        # Get RUNNING and PENDING_RECONCILIATION operations
        running_ops = await self._operations_service.list_operations(
            status=['RUNNING', 'PENDING_RECONCILIATION']
        )

        # Get operations claimed by workers
        workers = self._worker_registry.list_workers()
        claimed_ops = {w.current_operation_id for w in workers if w.current_operation_id}

        now = datetime.utcnow()

        for op in running_ops:
            if op.operation_id in claimed_ops:
                # Worker claims it - not orphan
                self._potential_orphans.pop(op.operation_id, None)
                continue

            if op.is_backend_local:
                # Backend-local should already be FAILED from startup
                continue

            # Potential orphan
            if op.operation_id not in self._potential_orphans:
                self._potential_orphans[op.operation_id] = now
                continue

            # Check timeout
            first_seen = self._potential_orphans[op.operation_id]
            if (now - first_seen).total_seconds() >= self._orphan_timeout:
                await self._mark_orphan_failed(op)
                self._potential_orphans.pop(op.operation_id)

    async def _mark_orphan_failed(self, op: OperationInfo):
        logger.warning(f"Orphan operation detected: {op.operation_id}")
        await self._operations_service.update_status(
            op.operation_id,
            status='FAILED',
            error_message='Operation was RUNNING but no worker claimed it'
        )
```

**Acceptance Criteria:**
- [ ] OrphanOperationDetector class implemented
- [ ] Background loop runs every 15 seconds
- [ ] Tracks potential orphans with first-seen timestamp
- [ ] Marks FAILED after 60 seconds
- [ ] Handles both RUNNING and PENDING_RECONCILIATION
- [ ] Ignores backend-local operations
- [ ] Unit tests cover detection logic

**Integration Tests (based on categories):**
- [ ] **Wiring:** `assert get_orphan_detector()._operations_service is not None`
- [ ] **Wiring:** `assert get_orphan_detector()._worker_registry is not None`
- [ ] **Lifecycle:** Background task starts: `assert detector._task is not None and not detector._task.done()`
- [ ] **Lifecycle:** Background task stops cleanly on shutdown
- [ ] **DB Verification:** After orphan detected, query DB directly to verify status=FAILED

**Smoke Test:**
```bash
# Check orphan detector is running:
docker compose logs backend | grep "Orphan detector started"
# After killing a worker, check for detection:
docker compose logs backend | grep "Orphan operation detected"
```

---

### Task 2.2: Integrate OrphanDetector with Backend Startup

**File(s):**
- `ktrdr/api/main.py` (modify)
- `ktrdr/api/dependencies.py` (modify if needed)

**Type:** CODING

**Task Categories:** Wiring/DI, Background/Async

**Description:**
Start the orphan detector on backend startup and stop it on shutdown.

**Implementation Notes:**
- Create singleton instance
- Start on FastAPI startup event (after M1 reconciliation)
- Stop on shutdown event

**Code:**
```python
# In main.py
orphan_detector: Optional[OrphanOperationDetector] = None

@app.on_event("startup")
async def startup():
    global orphan_detector
    # M1: Startup reconciliation first
    await startup_reconciliation()

    # M2: Start orphan detector
    orphan_detector = OrphanOperationDetector(
        operations_service=get_operations_service(),
        worker_registry=get_worker_registry(),
    )
    await orphan_detector.start()
    logger.info("Orphan detector started")

@app.on_event("shutdown")
async def shutdown():
    global orphan_detector
    if orphan_detector:
        await orphan_detector.stop()
```

**Acceptance Criteria:**
- [ ] Orphan detector starts on backend startup
- [ ] Starts after M1 reconciliation
- [ ] Stops cleanly on shutdown
- [ ] Logged startup/shutdown

**Integration Tests (based on categories):**
- [ ] **Wiring:** Verify `orphan_detector` global is not None after startup
- [ ] **Lifecycle:** Verify detector task is running after startup event

**Smoke Test:**
```bash
# After backend starts, verify detector is running:
docker compose logs backend | grep "Orphan detector started"
```

---

### Task 2.3: Add Health Check to Orphan Detector

**File(s):**
- `ktrdr/api/services/orphan_detector.py` (modify)
- `ktrdr/api/endpoints/health.py` (modify if exists)

**Type:** CODING

**Task Categories:** API Endpoint

**Description:**
Add health check endpoint or metrics for orphan detector status.

**Implementation Notes:**
- Track last check time
- Track number of potential orphans being watched
- Expose via health endpoint or metrics

**Acceptance Criteria:**
- [ ] Orphan detector exposes status
- [ ] Last check time tracked
- [ ] Number of watched orphans tracked
- [ ] Can query status via API or metrics

**Integration Tests (based on categories):**
- [ ] **API:** Health endpoint returns correct response format
- [ ] **API:** Health endpoint reflects actual detector state

**Smoke Test:**
```bash
curl http://localhost:8000/api/v1/health | jq '.orphan_detector'
```

---

### Task 2.4: Configuration for Orphan Detection

**File(s):**
- `ktrdr/config/settings.py` (modify)
- Environment variables

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Make orphan detection timeouts configurable.

**Configuration:**
```python
# Environment variables
ORPHAN_TIMEOUT_SECONDS=60
ORPHAN_CHECK_INTERVAL_SECONDS=15
```

**Acceptance Criteria:**
- [ ] Timeout configurable via environment
- [ ] Check interval configurable
- [ ] Sensible defaults (60s, 15s)
- [ ] Documentation in config

**Integration Tests (based on categories):**
- [ ] **Config:** Startup fails with invalid ORPHAN_TIMEOUT_SECONDS (e.g., negative)
- [ ] **Config:** Defaults work when env vars not set

**Smoke Test:**
```bash
docker compose exec backend env | grep ORPHAN
```

---

### Task 2.5: Integration Test for Orphan Detection

**File(s):**
- `tests/integration/test_m2_orphan_detection.py` (new)

**Type:** CODING

**Description:**
Integration test that verifies orphan detection works.

**Test Scenarios:**
1. Create operation with worker
2. Simulate worker disappearance (remove from registry)
3. Wait for orphan detection
4. Verify operation marked FAILED
5. Verify error message is informative

**Acceptance Criteria:**
- [ ] Test simulates worker disappearance
- [ ] Test verifies FAILED status after timeout
- [ ] Test verifies error message
- [ ] Tests pass: `make test-integration`

---

## Milestone 2 Verification Checklist

Before marking M2 complete:

- [ ] All 5 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1 E2E test still passes (no regression)
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/api/services/orphan_detector.py` | Create | 2.1 |
| `ktrdr/api/main.py` | Modify | 2.2 |
| `ktrdr/api/endpoints/health.py` | Modify | 2.3 |
| `ktrdr/config/settings.py` | Modify | 2.4 |
| `tests/unit/api/services/test_orphan_detector.py` | Create | 2.1 |
| `tests/integration/test_m2_orphan_detection.py` | Create | 2.5 |
