# Handoff: Milestone 6 (Graceful Shutdown)

## Task 6.1 Complete

**Implemented:** SIGTERM signal handler infrastructure in WorkerAPIBase

### Key Components Added

**Location:** [ktrdr/workers/base.py:158-161](ktrdr/workers/base.py#L158-L161) (initialization)
**Location:** [ktrdr/workers/base.py:487-515](ktrdr/workers/base.py#L487-L515) (methods)

```python
# In __init__:
self._shutdown_event = asyncio.Event()
self._shutdown_timeout = 25  # seconds (Docker gives 30s)

# Methods added:
def _setup_signal_handlers(self) -> None:
    """Registers SIGTERM handler that sets _shutdown_event."""

async def wait_for_shutdown(self) -> bool:
    """Wait for shutdown signal. Returns True if signaled, False on timeout."""
```

### Signal Handler Pattern

The SIGTERM handler uses `call_soon_threadsafe` to bridge from the signal handler thread to the asyncio event loop:

```python
def handle_sigterm(signum, frame):
    logger.info("SIGTERM received - initiating graceful shutdown")
    asyncio.get_event_loop().call_soon_threadsafe(self._shutdown_event.set)
```

This is necessary because signal handlers run in the main thread, not the event loop thread.

### Integration Point for Task 6.2

Task 6.2 should use the `_shutdown_event` to race between operation completion and shutdown signal:

```python
async def run_with_graceful_shutdown(self, operation_id: str, operation_coro: Coroutine):
    operation_task = asyncio.create_task(operation_coro)
    shutdown_task = asyncio.create_task(self._shutdown_event.wait())

    done, pending = await asyncio.wait(
        [operation_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    if shutdown_task in done:
        # Handle graceful shutdown - cancel operation, save checkpoint
        operation_task.cancel()
        # ... save checkpoint, update status
```

### Tests Added

Location: [tests/unit/workers/test_base_shutdown.py](tests/unit/workers/test_base_shutdown.py)

- 13 unit tests covering initialization, signal handling, and wait_for_shutdown behavior

### Acceptance Criteria Verified

- [x] SIGTERM handler registered on startup
- [x] Shutdown event set on SIGTERM
- [x] Handler works correctly in async context
- [x] Logged when SIGTERM received

---

## Task 6.2 Complete

**Implemented:** Graceful shutdown operation execution with racing logic

### Key Components Added

**Location:** [ktrdr/workers/base.py:49-57](ktrdr/workers/base.py#L49-L57) (exception)
**Location:** [ktrdr/workers/base.py:538-647](ktrdr/workers/base.py#L538-L647) (methods)

```python
class GracefulShutdownError(Exception):
    """Raised when worker receives SIGTERM during operation."""

async def run_with_graceful_shutdown(self, operation_id: str, operation_coro: Any) -> Any:
    """Races operation against shutdown event."""

async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
    """Hook for subclasses to save checkpoints."""

async def _update_operation_status(self, operation_id: str, status: str, ...) -> None:
    """Stub for Task 6.3 to implement."""
```

### Racing Logic Pattern

```python
operation_task = asyncio.create_task(operation_coro)
shutdown_task = asyncio.create_task(self._shutdown_event.wait())

done, pending = await asyncio.wait(
    [operation_task, shutdown_task],
    return_when=asyncio.FIRST_COMPLETED,
)

if shutdown_task in done:
    operation_task.cancel()
    await self._save_checkpoint(operation_id, "shutdown")
    await self._update_operation_status(operation_id, "CANCELLED", ...)
    raise GracefulShutdownError("Worker shutdown requested")
```

### Integration Point for Task 6.3

Task 6.3 should implement `_update_operation_status` with HTTP call to backend:

```python
async def _update_operation_status(self, operation_id: str, status: str, ...):
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.patch(f"{self.backend_url}/api/v1/operations/{operation_id}", ...)
```

### Subclass Override Pattern

Training/Backtest workers should override `_save_checkpoint`:

```python
class TrainingWorker(WorkerAPIBase):
    async def _save_checkpoint(self, operation_id: str, checkpoint_type: str):
        checkpoint_service = self._get_checkpoint_service()
        await checkpoint_service.save_checkpoint(operation_id, checkpoint_type, ...)
```

### Tests Added

Location: [tests/unit/workers/test_base_graceful_shutdown.py](tests/unit/workers/test_base_graceful_shutdown.py)

- 18 unit tests covering:
  - GracefulShutdownError exception
  - _current_operation_id tracking
  - Normal operation completion
  - Shutdown detection and cancellation
  - Checkpoint saving on shutdown/failure
  - Hook method existence

### Acceptance Criteria Verified

- [x] Shutdown detected during operation
- [x] Operation task cancelled cleanly
- [x] Checkpoint saved with type="shutdown"
- [x] Status updated to CANCELLED
- [x] Completes within grace period

---

## Task 6.3 Complete

**Implemented:** HTTP status update call from worker to backend

### Key Components Added

**Worker side:** [ktrdr/workers/base.py:552-591](ktrdr/workers/base.py#L552-L591)

```python
async def _update_operation_status(
    self,
    operation_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Update operation status in backend via HTTP call."""
    import httpx

    status_url = f"{self.backend_url}/api/v1/operations/{operation_id}/status"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.patch(status_url, json={...})
            # Log success/failure
    except Exception as e:
        logger.warning(f"Could not update operation status: {e}")
        # Continue shutdown - OrphanDetector handles missed updates
```

**Backend endpoint:** [ktrdr/api/endpoints/operations.py:981-1073](ktrdr/api/endpoints/operations.py#L981-L1073)

```python
@router.patch("/operations/{operation_id}/status")
async def update_operation_status(request: StatusUpdateRequest, ...):
    """Update operation status (simplified, for worker shutdown)."""
```

**New models:** [ktrdr/api/models/operations.py](ktrdr/api/models/operations.py)

- `StatusUpdateRequest` - Request body with status and optional error_message
- `StatusUpdateResponse` - Response with previous and new status

### Resilience Pattern

The implementation is designed to be resilient:

- 5-second timeout prevents blocking shutdown
- All exceptions caught and logged (doesn't raise)
- Failure continues shutdown - OrphanDetector will eventually mark operation FAILED
- Backend endpoint uses simplified `update_status()` (no cascade cancellation)

### Tests Added

Location: [tests/unit/workers/test_base_update_status.py](tests/unit/workers/test_base_update_status.py)

- 9 unit tests covering:
  - PATCH request to correct URL
  - Timeout configuration (5.0 seconds)
  - Success/failure handling
  - Connection and timeout error handling
  - Optional error_message parameter

### Acceptance Criteria Verified

- [x] Worker calls backend to update status
- [x] Timeout prevents hanging (5-second timeout)
- [x] Failure doesn't block shutdown (exceptions caught)
- [x] Logged success/failure

---

## Task 6.4 Complete

**Implemented:** Docker grace period configuration for all workers

### Files Modified

- `deploy/environments/local/docker-compose.yml` — 4 workers
- `deploy/environments/homelab/docker-compose.workers.yml` — 6 workers
- `deploy/environments/homelab/docker-compose.gpu-worker.yml` — 1 GPU worker
- `deploy/environments/canary/docker-compose.yml` — 2 workers

### Configuration Added

```yaml
# M6: Graceful shutdown - gives worker 30s to save checkpoint before SIGKILL
stop_grace_period: 30s
```

### Why 30s?

- Worker's internal shutdown timeout is 25s (set in Task 6.1)
- Gives 5s buffer for cleanup after checkpoint save
- Docker sends SIGTERM first, waits grace period, then SIGKILL
- Without this, Docker defaults to 10s which may not be enough for large checkpoints

### Acceptance Criteria Verified

- [x] Grace period configured in docker-compose (30s)
- [x] Both worker types configured (backtest + training)
- [x] Documented in comments (inline YAML comments)

---

## Task 6.5 Complete

**Implemented:** Integration tests for graceful shutdown

### Test File

Location: [tests/integration/test_m6_graceful_shutdown.py](tests/integration/test_m6_graceful_shutdown.py)

### Test Infrastructure

The tests use in-memory mocks following M4 patterns:
- `GracefulShutdownTestWorker`: Worker with mock checkpoint/operations services
- `IntegrationCheckpointService`: In-memory checkpoint storage with filesystem artifacts
- `MockOperationsRepository`: In-memory operations storage

### Test Coverage (10 tests)

**Checkpoint saving:**
- `test_shutdown_during_operation_saves_checkpoint` — verifies checkpoint saved with type="shutdown"
- `test_shutdown_checkpoint_includes_artifacts` — verifies model artifacts saved

**Status updates:**
- `test_shutdown_sets_status_to_cancelled` — verifies status=CANCELLED
- `test_shutdown_error_message_mentions_shutdown` — verifies error message

**Resume flow:**
- `test_can_resume_after_shutdown` — full shutdown→resume flow
- `test_model_weights_valid_after_shutdown_resume` — model weights loadable

**Edge cases:**
- `test_shutdown_before_operation_starts` — immediate shutdown
- `test_multiple_shutdown_signals` — idempotent shutdown events
- `test_operation_completes_without_shutdown` — no checkpoint on normal completion
- `test_checkpoint_preserved_on_resume_failure` — checkpoint survives failed resume

### Testing Pattern

Tests simulate SIGTERM via `worker._shutdown_event.set()` — the same event that the real SIGTERM handler sets. This tests the same code paths without requiring actual Docker stop.

### Acceptance Criteria Verified

- [x] Test simulates shutdown signal
- [x] Test verifies checkpoint saved
- [x] Test verifies status=CANCELLED
- [x] Tests pass: `make test-integration`

---

## E2E Container Tests

Location: [tests/e2e/container/test_m6_graceful_shutdown.py](tests/e2e/container/test_m6_graceful_shutdown.py)

**Test classes:**
- `TestM6GracefulShutdown` — Core shutdown saves checkpoint test
- `TestM6E2EScriptValidation` — Full E2E scenario from milestone plan
- `TestM6WorkerStopSignal` — SIGTERM signal handling verification

**Run with:**
```bash
pytest tests/e2e/container/test_m6_graceful_shutdown.py -v --run-container-e2e
```

---

## Milestone 6 Complete

All tasks verified:
- [x] Task 6.1: SIGTERM handler
- [x] Task 6.2: Graceful shutdown operation execution
- [x] Task 6.3: HTTP status update from worker
- [x] Task 6.4: Docker grace period configuration
- [x] Task 6.5: Integration tests
- [x] E2E container tests (bonus)
