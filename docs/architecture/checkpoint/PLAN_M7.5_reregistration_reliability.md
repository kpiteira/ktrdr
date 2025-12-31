---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 7.5: Re-Registration Reliability

**Branch:** `feature/checkpoint-m7.5-reregistration`
**Depends On:** M1 (Operations Persistence + Worker Re-Registration)
**Estimated Tasks:** 5

---

## Background

Investigation of the M1 re-registration system revealed two bugs and an opportunity for faster re-registration on graceful backend shutdown.

### Issues Found

**Issue 1: Monitor never triggers if no health check received**

Location: `ktrdr/workers/base.py:830-832`

```python
# Skip if no health check has been received yet
if self._last_health_check_received is None:
    continue
```

If a worker never received a health check (e.g., backend crashed before first health check), `_last_health_check_received` stays `None` and the monitor **never triggers re-registration**.

**Issue 2: No retry on initial registration failure**

Location: `ktrdr/workers/base.py:775-781`

If initial registration fails (e.g., backend still starting), the worker just logs a warning. Since the monitor only triggers after receiving a health check (Issue 1), the worker may **never successfully register**.

**Issue 3: Slow re-registration on graceful shutdown**

Currently, workers detect backend restart via health check timeout (30 seconds). On graceful shutdown (e.g., hot reload), we can notify workers immediately for much faster re-registration (~5 seconds vs ~30-40 seconds).

---

## Capability

When M7.5 is complete:
- Workers reliably re-register even if they never received a health check
- Initial registration retries with exponential backoff
- Graceful backend shutdown notifies workers before stopping
- Backend rejects registrations during shutdown (prevents race condition)
- Workers poll and re-register within ~5 seconds of backend restart (graceful)
- Hard crash recovery still works via health check timeout (~30-40 seconds)

---

## Tasks

### Task 7.5.1: Fix Monitor to Check Registration Without Prior Health Checks

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** BUG_FIX

**Description:**
Fix the re-registration monitor to check registration status even when `_last_health_check_received` is None. This ensures workers that never received a health check can still detect they're not registered.

**Current Code:**
```python
async def _monitor_health_checks(self) -> None:
    while True:
        await asyncio.sleep(self._reregistration_check_interval)

        # Skip if no health check has been received yet
        if self._last_health_check_received is None:
            continue  # BUG: Never checks registration!

        elapsed = (datetime.utcnow() - self._last_health_check_received).total_seconds()
        if elapsed > self._health_check_timeout:
            await self._ensure_registered()
            self._last_health_check_received = datetime.utcnow()
```

**Fixed Code:**
```python
async def _monitor_health_checks(self) -> None:
    while True:
        await asyncio.sleep(self._reregistration_check_interval)

        # If never received health check, still verify we're registered
        # This handles the case where backend crashed before first health check
        if self._last_health_check_received is None:
            logger.debug("No health check received yet - verifying registration")
            await self._ensure_registered()
            continue

        elapsed = (datetime.utcnow() - self._last_health_check_received).total_seconds()
        if elapsed > self._health_check_timeout:
            logger.warning(f"No health check in {elapsed:.0f}s - checking registration")
            await self._ensure_registered()
            self._last_health_check_received = datetime.utcnow()
```

**Acceptance Criteria:**
- [ ] Monitor checks registration even when `_last_health_check_received` is None
- [ ] Unit test: worker re-registers after backend restart even without prior health check
- [ ] Existing re-registration behavior unchanged for normal case

---

### Task 7.5.2: Add Retry with Backoff to Initial Registration

**File(s):**
- `ktrdr/workers/base.py` (modify)

**Type:** BUG_FIX

**Description:**
Add retry logic with exponential backoff to `self_register()`. This ensures workers eventually register even if backend is slow to start.

**Implementation:**
```python
async def self_register(
    self,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
) -> bool:
    """
    Register this worker with backend's WorkerRegistry.

    Retries with exponential backoff if registration fails.

    Args:
        max_retries: Maximum number of registration attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)

    Returns:
        True if registration succeeded, False otherwise
    """
    import httpx

    registration_url = f"{self.backend_url}/api/v1/workers/register"

    # Build payload (existing code)
    payload = self._build_registration_payload()

    delay = initial_delay
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(registration_url, json=payload)

                # 503 means backend is shutting down - retry with backoff
                if response.status_code == 503:
                    logger.info(
                        f"Backend is shutting down (attempt {attempt + 1}/{max_retries}) "
                        f"- will retry in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay)
                    continue

                response.raise_for_status()
                logger.info(
                    f"Worker registered successfully: {self.worker_id} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                self._completed_operations.clear()
                return True

        except httpx.ConnectError:
            logger.warning(
                f"Registration attempt {attempt + 1}/{max_retries} failed: "
                f"backend not reachable (retrying in {delay:.1f}s)"
            )
        except Exception as e:
            logger.warning(
                f"Registration attempt {attempt + 1}/{max_retries} failed: {e} "
                f"(retrying in {delay:.1f}s)"
            )

        if attempt < max_retries - 1:
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)

    logger.error(f"Failed to register after {max_retries} attempts")
    return False
```

**Helper method to extract:**
```python
def _build_registration_payload(self) -> dict:
    """Build the registration payload with current worker state."""
    # ... existing payload building code from self_register ...
```

**Acceptance Criteria:**
- [ ] Registration retries up to 5 times with exponential backoff
- [ ] 503 response handled specially (backend shutting down)
- [ ] Returns bool indicating success/failure
- [ ] Unit test: registration succeeds after transient failures
- [ ] Unit test: registration gives up after max retries

---

### Task 7.5.3: Backend Shutdown Mode

**File(s):**
- `ktrdr/api/services/worker_registry.py` (modify)
- `ktrdr/api/endpoints/workers.py` (modify)
- `ktrdr/api/startup.py` (modify)

**Type:** CODING

**Description:**
Add shutdown mode to WorkerRegistry that rejects new registrations. This prevents the race condition where a worker re-registers to a backend that's about to shut down.

**WorkerRegistry changes:**
```python
class WorkerRegistry:
    def __init__(self):
        self._workers: dict[str, WorkerEndpoint] = {}
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval: int = 10
        self._removal_threshold_seconds: int = 300
        self._operations_service: OperationsService | None = None
        self._shutting_down: bool = False  # NEW

    def begin_shutdown(self) -> None:
        """Enter shutdown mode - reject new registrations."""
        self._shutting_down = True
        logger.info("Worker registry entering shutdown mode")

    def is_shutting_down(self) -> bool:
        """Check if registry is in shutdown mode."""
        return self._shutting_down
```

**Endpoint changes:**
```python
@router.post("/workers/register")
async def register_worker(
    request: WorkerRegistrationRequest,
    registry: WorkerRegistry = Depends(get_worker_registry),
) -> dict:
    # Reject registrations during shutdown
    if registry.is_shutting_down():
        raise HTTPException(
            status_code=503,
            detail="Backend is shutting down - retry after restart",
            headers={"Retry-After": "5"},
        )

    # ... existing registration logic ...
```

**Startup.py lifespan changes:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup code ...
    yield

    # Shutdown - Phase 1: Stop accepting registrations
    logger.info("Shutting down KTRDR API...")
    registry.begin_shutdown()

    # Phase 2: Notify workers (Task 7.5.4)
    await _notify_workers_of_shutdown(registry)

    # Phase 3: Normal shutdown
    # ... existing shutdown code ...
```

**Acceptance Criteria:**
- [ ] `begin_shutdown()` sets shutdown flag
- [ ] Registration endpoint returns 503 during shutdown
- [ ] 503 response includes Retry-After header
- [ ] Shutdown calls `begin_shutdown()` before notifying workers
- [ ] Unit test: registration rejected during shutdown

---

### Task 7.5.4: Worker Shutdown Notification and Reconnection

**File(s):**
- `ktrdr/workers/base.py` (modify)
- `ktrdr/api/startup.py` (modify)

**Type:** CODING

**Description:**
Implement worker-side endpoint to receive shutdown notifications and poll for backend restart.

**Worker endpoint:**
```python
def _register_shutdown_notification_endpoint(self) -> None:
    """Register endpoint for backend shutdown notifications."""

    @self.app.post("/backend-shutdown")
    async def backend_shutdown_notification():
        """
        Receive notification that backend is shutting down.

        Triggers reconnection polling to quickly re-register
        when backend comes back up.
        """
        logger.info("Received backend shutdown notification - starting reconnection polling")

        # Start reconnection task if not already running
        if self._reconnection_task is None or self._reconnection_task.done():
            self._reconnection_task = asyncio.create_task(
                self._poll_for_backend_restart()
            )

        return {"acknowledged": True}
```

**Reconnection polling:**
```python
async def _poll_for_backend_restart(
    self,
    poll_interval: float = 2.0,
    max_duration: float = 120.0,
) -> None:
    """
    Poll for backend restart and re-register when available.

    Args:
        poll_interval: Seconds between poll attempts
        max_duration: Maximum seconds to poll before giving up
    """
    import httpx

    start_time = datetime.utcnow()
    attempt = 0

    logger.info(f"Polling for backend restart (max {max_duration}s)")

    while (datetime.utcnow() - start_time).total_seconds() < max_duration:
        attempt += 1
        await asyncio.sleep(poll_interval)

        try:
            success = await self.self_register(max_retries=1, initial_delay=0)
            if success:
                logger.info(f"Re-registered after backend restart (attempt {attempt})")
                self._last_health_check_received = datetime.utcnow()
                return

        except Exception as e:
            logger.debug(f"Reconnection attempt {attempt} failed: {e}")

    logger.warning(f"Failed to reconnect after {max_duration}s - falling back to health check detection")
```

**Backend notification function:**
```python
async def _notify_workers_of_shutdown(registry: WorkerRegistry) -> None:
    """
    Notify all registered workers that backend is shutting down.

    Best-effort notification - workers may be unreachable.
    """
    import httpx

    workers = registry.list_workers()
    if not workers:
        logger.info("No workers to notify of shutdown")
        return

    logger.info(f"Notifying {len(workers)} workers of shutdown")

    async with httpx.AsyncClient(timeout=2.0) as client:
        for worker in workers:
            try:
                response = await client.post(
                    f"{worker.endpoint_url}/backend-shutdown",
                    json={"message": "Backend shutting down"}
                )
                if response.status_code == 200:
                    logger.debug(f"Notified {worker.worker_id} of shutdown")
                else:
                    logger.debug(f"Worker {worker.worker_id} returned {response.status_code}")
            except Exception as e:
                # Best effort - worker might be dead or unreachable
                logger.debug(f"Could not notify {worker.worker_id}: {e}")

    logger.info("Worker shutdown notification complete")
```

**Worker __init__ additions:**
```python
# Reconnection polling task (M7.5)
self._reconnection_task: Optional[asyncio.Task] = None

# Register shutdown notification endpoint
self._register_shutdown_notification_endpoint()
```

**Acceptance Criteria:**
- [ ] Worker has `/backend-shutdown` endpoint
- [ ] Endpoint starts reconnection polling task
- [ ] Polling attempts re-registration every 2 seconds
- [ ] Polling gives up after 120 seconds (falls back to health check detection)
- [ ] Backend notifies all workers during shutdown
- [ ] Notification is best-effort (doesn't fail if workers unreachable)
- [ ] Unit test: worker receives notification and starts polling
- [ ] Unit test: worker re-registers when backend comes back

---

### Task 7.5.5: E2E Test - Graceful Backend Restart

**File(s):**
- `tests/e2e/test_m7_5_reregistration.py` (new)

**Type:** TESTING

**Description:**
End-to-end test verifying fast re-registration on graceful backend restart.

**Test Implementation:**
```python
"""
E2E Test: M7.5 Re-Registration Reliability

Tests:
1. Worker re-registers after backend restart (graceful)
2. Worker re-registers even without prior health checks
3. Re-registration is fast on graceful shutdown (~5s vs ~30s)
"""

import asyncio
import subprocess
import time
import httpx
import pytest


@pytest.fixture
def docker_compose():
    """Ensure docker-compose is running."""
    # Start services if not running
    subprocess.run(["docker", "compose", "up", "-d"], check=True)
    yield
    # Don't stop - leave running for other tests


class TestGracefulReregistration:
    """Test fast re-registration on graceful backend shutdown."""

    async def test_graceful_restart_fast_reregistration(self, docker_compose):
        """Workers should re-register within ~10 seconds of graceful restart."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # 1. Verify workers are registered
            response = await client.get("/api/v1/workers")
            assert response.status_code == 200
            initial_workers = response.json()
            assert len(initial_workers) > 0, "No workers registered"

            worker_ids = [w["worker_id"] for w in initial_workers]
            print(f"Initial workers: {worker_ids}")

            # 2. Restart backend (graceful - sends SIGTERM)
            print("Restarting backend...")
            restart_start = time.time()
            subprocess.run(["docker", "compose", "restart", "backend"], check=True)

            # 3. Wait for backend to be ready
            await self._wait_for_backend_ready(client, timeout=30)
            backend_ready_time = time.time() - restart_start
            print(f"Backend ready after {backend_ready_time:.1f}s")

            # 4. Poll for workers to re-register (should be fast!)
            reregistration_start = time.time()
            registered_workers = await self._wait_for_workers(
                client,
                expected_count=len(initial_workers),
                timeout=15,  # Should be much faster than 30s
            )
            reregistration_time = time.time() - reregistration_start

            print(f"Workers re-registered in {reregistration_time:.1f}s")

            # 5. Verify timing - should be fast on graceful shutdown
            assert reregistration_time < 15, (
                f"Re-registration took {reregistration_time:.1f}s - "
                f"expected < 15s for graceful shutdown"
            )

            # 6. Verify all workers re-registered
            registered_ids = [w["worker_id"] for w in registered_workers]
            for wid in worker_ids:
                assert wid in registered_ids, f"Worker {wid} did not re-register"

    async def test_reregistration_without_prior_health_check(self, docker_compose):
        """
        Worker should re-register even if it never received a health check.

        This tests the fix for Issue 1 (monitor skips when _last_health_check_received is None).
        """
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # 1. Start fresh - restart everything
            subprocess.run(["docker", "compose", "restart"], check=True)

            # 2. Wait for backend but NOT long enough for health checks
            await self._wait_for_backend_ready(client, timeout=30)

            # 3. Immediately restart backend (before first health check cycle)
            subprocess.run(["docker", "compose", "restart", "backend"], check=True)
            await self._wait_for_backend_ready(client, timeout=30)

            # 4. Workers should still re-register (within reasonable time)
            workers = await self._wait_for_workers(client, expected_count=1, timeout=45)
            assert len(workers) >= 1, "Workers failed to re-register without prior health check"

    async def _wait_for_backend_ready(
        self,
        client: httpx.AsyncClient,
        timeout: float,
    ) -> None:
        """Wait for backend to be ready to accept requests."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    return
            except httpx.ConnectError:
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError(f"Backend not ready after {timeout}s")

    async def _wait_for_workers(
        self,
        client: httpx.AsyncClient,
        expected_count: int,
        timeout: float,
    ) -> list:
        """Wait for expected number of workers to register."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = await client.get("/api/v1/workers")
                if response.status_code == 200:
                    workers = response.json()
                    if len(workers) >= expected_count:
                        return workers
            except httpx.ConnectError:
                pass
            await asyncio.sleep(1.0)

        # Return whatever we have (test will fail with assertion)
        try:
            response = await client.get("/api/v1/workers")
            return response.json() if response.status_code == 200 else []
        except:
            return []
```

**Acceptance Criteria:**
- [ ] Test verifies graceful restart re-registration < 15 seconds
- [ ] Test verifies re-registration works without prior health checks
- [ ] Test passes in CI environment
- [ ] Test is tagged for E2E suite (not unit tests)

---

## Milestone 7.5 Verification Checklist

Before marking M7.5 complete:

- [ ] All 5 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes: `pytest tests/e2e/test_m7_5_reregistration.py -v`
- [ ] Quality gates pass: `make quality`
- [ ] Manual verification:
  - [ ] `docker compose restart backend` → workers re-register in < 15s
  - [ ] Kill backend process → workers re-register in < 45s

---

## Timing Summary

| Scenario | Before M7.5 | After M7.5 |
|----------|-------------|------------|
| Graceful backend restart | ~30-40s | ~5-10s |
| Hard backend crash | ~30-40s | ~30-40s (unchanged) |
| Backend crash before first health check | **Never** (bug) | ~10-20s |
| Initial registration failure | **Never** (bug) | Retries with backoff |

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/workers/base.py` | Modify | 7.5.1, 7.5.2, 7.5.4 |
| `ktrdr/api/services/worker_registry.py` | Modify | 7.5.3 |
| `ktrdr/api/endpoints/workers.py` | Modify | 7.5.3 |
| `ktrdr/api/startup.py` | Modify | 7.5.3, 7.5.4 |
| `tests/e2e/test_m7_5_reregistration.py` | Create | 7.5.5 |

---

## Risk Assessment

**Low Risk:**
- Tasks 7.5.1, 7.5.2 are bug fixes with clear scope
- Changes are additive (new endpoint, new flag)

**Medium Risk:**
- Task 7.5.4 modifies shutdown sequence - must not break existing shutdown
- Notification is best-effort, so graceful degradation if workers unreachable

**Mitigation:**
- All existing M1-M7 E2E tests must still pass
- Manual verification of both graceful and hard restart scenarios
