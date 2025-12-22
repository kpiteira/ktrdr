---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 6: Graceful Shutdown (SIGTERM)

**Branch:** `feature/checkpoint-m6-graceful-shutdown`
**Depends On:** M4 (Training Resume)
**Estimated Tasks:** 5

---

## Capability

When M6 is complete:
- Workers save checkpoint on SIGTERM
- Workers update operation status to CANCELLED before exit
- Docker stop gives workers time to save (30s grace period)
- Operations can be resumed after infrastructure maintenance

---

## E2E Test Scenario

```bash
#!/bin/bash
# M6 E2E Test: Graceful Shutdown

set -e

echo "=== M6 E2E Test: Graceful Shutdown ==="

# 1. Start training
echo "Step 1: Start training..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_path": "strategies/test.yaml",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "epochs": 100
    }')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Wait for some progress
echo "Step 2: Waiting for progress..."
for i in {1..30}; do
    sleep 2
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_percent')
    echo "  Progress: $PROGRESS%"
    if (( $(echo "$PROGRESS > 20" | bc -l) )); then
        break
    fi
done

# 3. Send SIGTERM to worker (docker stop)
echo "Step 3: Stopping worker gracefully..."
docker-compose stop -t 30 training-worker

# 4. Wait a moment
sleep 5

# 5. Check operation status
echo "Step 5: Check operation status..."
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
echo "Status after shutdown: $STATUS"

# 6. Check checkpoint
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_EXISTS=$(echo $CHECKPOINT | jq -r '.success')
CP_TYPE=$(echo $CHECKPOINT | jq -r '.data.checkpoint_type')
echo "Checkpoint exists: $CP_EXISTS, type: $CP_TYPE"

# 7. Restart worker
echo "Step 7: Restarting worker..."
docker-compose start training-worker
sleep 10

# 8. Verify can resume
echo "Step 8: Verify resumable..."
RESUME_TEST=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID | jq -r '.success')

if [ "$STATUS" == "CANCELLED" ] && [ "$CP_TYPE" == "shutdown" ] && [ "$RESUME_TEST" == "true" ]; then
    echo ""
    echo "=== M6 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M6 E2E TEST FAILED ==="
    echo "Expected: status=CANCELLED, checkpoint_type=shutdown"
    echo "Got: status=$STATUS, checkpoint_type=$CP_TYPE"
    exit 1
fi
```

---

## Tasks

### Task 6.1: Add SIGTERM Handler to WorkerAPIBase

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** CODING

**Description:**
Add signal handler for SIGTERM that triggers graceful shutdown.

**Implementation Notes:**
- Register SIGTERM handler on worker startup
- Set shutdown event when SIGTERM received
- Give operations time to checkpoint before exit

**Code:**
```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing ...
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout = 25  # seconds (Docker gives 30s)

    def _setup_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        import signal

        def handle_sigterm(signum, frame):
            logger.info("SIGTERM received - initiating graceful shutdown")
            # Set event from signal handler context
            asyncio.get_event_loop().call_soon_threadsafe(
                self._shutdown_event.set
            )

        signal.signal(signal.SIGTERM, handle_sigterm)
        logger.info("SIGTERM handler registered")

    async def wait_for_shutdown(self) -> bool:
        """Wait for shutdown signal with timeout. Returns True if signaled."""
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=self._shutdown_timeout
            )
            return True
        except asyncio.TimeoutError:
            return False
```

**Acceptance Criteria:**
- [ ] SIGTERM handler registered on startup
- [ ] Shutdown event set on SIGTERM
- [ ] Handler works correctly in async context
- [ ] Logged when SIGTERM received

---

### Task 6.2: Implement Graceful Shutdown in Operation Execution

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** CODING

**Description:**
Modify operation execution to detect shutdown and save checkpoint.

**Implementation Notes:**
- Race between operation completion and shutdown signal
- On shutdown: save checkpoint, update status, exit
- Must complete within Docker grace period (30s)

**Code:**
```python
async def run_with_graceful_shutdown(
    self,
    operation_id: str,
    operation_coro: Coroutine,
) -> Any:
    """Run operation with graceful shutdown support."""
    self._current_operation_id = operation_id

    operation_task = asyncio.create_task(operation_coro)
    shutdown_task = asyncio.create_task(self._shutdown_event.wait())

    try:
        done, pending = await asyncio.wait(
            [operation_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if shutdown_task in done:
            # Graceful shutdown requested
            logger.info(f"Graceful shutdown - saving checkpoint for {operation_id}")

            # Cancel the operation task
            operation_task.cancel()
            try:
                await operation_task
            except asyncio.CancelledError:
                pass

            # Save shutdown checkpoint
            await self._save_checkpoint(operation_id, "shutdown")

            # Update status to CANCELLED
            await self._update_operation_status(operation_id, "CANCELLED",
                error_message="Graceful shutdown - checkpoint saved")

            raise GracefulShutdownError("Worker shutdown requested")

        # Operation completed normally
        return operation_task.result()

    except Exception as e:
        if not isinstance(e, GracefulShutdownError):
            # Save failure checkpoint
            await self._save_checkpoint(operation_id, "failure")
        raise
    finally:
        self._current_operation_id = None
```

**Acceptance Criteria:**
- [ ] Shutdown detected during operation
- [ ] Operation task cancelled cleanly
- [ ] Checkpoint saved with type="shutdown"
- [ ] Status updated to CANCELLED
- [ ] Completes within grace period

---

### Task 6.3: Add Status Update Call from Worker

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** CODING

**Description:**
Worker must call backend to update operation status to CANCELLED before exiting.

**Implementation Notes:**
- HTTP call to backend
- Must succeed before worker exits
- Timeout to avoid hanging

**Code:**
```python
async def _update_operation_status(
    self,
    operation_id: str,
    status: str,
    error_message: Optional[str] = None,
):
    """Update operation status in backend."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.patch(
                f"{self.backend_url}/api/v1/operations/{operation_id}",
                json={
                    "status": status,
                    "error_message": error_message,
                }
            )
            if response.status_code == 200:
                logger.info(f"Updated operation {operation_id} to {status}")
            else:
                logger.warning(f"Failed to update operation status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not update operation status: {e}")
        # Continue shutdown even if status update fails
        # OrphanDetector will eventually mark it FAILED
```

**Acceptance Criteria:**
- [ ] Worker calls backend to update status
- [ ] Timeout prevents hanging
- [ ] Failure doesn't block shutdown
- [ ] Logged success/failure

---

### Task 6.4: Configure Docker Grace Period

**File(s):**
- `docker/docker-compose.yml` (modify)
- `docker/docker-compose.override.yml` (modify if exists)

**Type:** CODING

**Description:**
Configure Docker to give workers 30 seconds before SIGKILL.

**Configuration:**
```yaml
services:
  training-worker:
    stop_grace_period: 30s

  backtest-worker:
    stop_grace_period: 30s
```

**Acceptance Criteria:**
- [ ] Grace period configured in docker-compose
- [ ] Both worker types configured
- [ ] Documented in comments

---

### Task 6.5: Integration Test for Graceful Shutdown

**File(s):**
- `tests/integration/test_m6_graceful_shutdown.py` (new)

**Type:** CODING

**Description:**
Integration test for graceful shutdown.

**Test Scenarios:**
1. Start operation
2. Simulate SIGTERM (or use test hook)
3. Verify checkpoint saved with type="shutdown"
4. Verify status updated to CANCELLED
5. Verify can resume

**Note:** May need to test with mock signal or test hook rather than actual Docker stop.

**Acceptance Criteria:**
- [ ] Test simulates shutdown signal
- [ ] Test verifies checkpoint saved
- [ ] Test verifies status=CANCELLED
- [ ] Tests pass: `make test-integration`

---

## Milestone 6 Verification Checklist

Before marking M6 complete:

- [ ] All 5 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1-M5 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/workers/base.py` | Modify | 6.1, 6.2, 6.3 |
| `docker/docker-compose.yml` | Modify | 6.4 |
| `tests/integration/test_m6_graceful_shutdown.py` | Create | 6.5 |
