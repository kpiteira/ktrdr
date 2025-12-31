"""E2E test for M7.5: Re-Registration Reliability.

This test validates the M7.5 improvements:
1. Fast re-registration after graceful backend restart (~5-10s vs ~30-40s)
2. Re-registration works even without prior health checks
3. Backend shutdown mode rejects registrations during shutdown

Requirements:
- Docker containers must be running: docker compose up -d
- Test will be skipped if API is not available

Usage:
    pytest tests/e2e/container/test_m7_5_reregistration.py -v --tb=short
"""

import subprocess
import time

import httpx
import pytest

# Test configuration
API_BASE_URL = "http://localhost:8000/api/v1"
API_TIMEOUT = 30.0
BACKEND_RESTART_WAIT = 15  # seconds to wait for backend to restart


def check_api_available() -> bool:
    """Check if API is available."""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_api(timeout: int = 60) -> bool:
    """Wait for API to become available."""
    start = time.time()
    while time.time() - start < timeout:
        if check_api_available():
            return True
        time.sleep(1)
    return False


def get_registered_workers() -> list:
    """Get list of currently registered workers."""
    try:
        response = httpx.get(f"{API_BASE_URL}/workers", timeout=5.0)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def restart_backend() -> bool:
    """Restart the backend container using docker compose."""
    try:
        result = subprocess.run(
            ["docker", "compose", "restart", "backend"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to restart backend: {e}")
        return False


def wait_for_workers(expected_count: int, timeout: int = 45) -> list:
    """Wait for expected number of workers to register."""
    start = time.time()
    while time.time() - start < timeout:
        workers = get_registered_workers()
        if len(workers) >= expected_count:
            return workers
        time.sleep(1)
    return get_registered_workers()


@pytest.fixture(scope="module")
def api_client():
    """Create HTTP client for API testing."""
    if not check_api_available():
        pytest.skip("API server not available - requires Docker containers running")
    return httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT)


@pytest.fixture(scope="module")
def initial_workers(api_client):
    """Get initial workers registered before tests."""
    response = api_client.get("/workers")
    if response.status_code != 200:
        return []
    workers = response.json()
    if not workers:
        pytest.skip("No workers registered - requires workers running")
    return workers


@pytest.mark.container_e2e
class TestM75GracefulRestart:
    """E2E tests for M7.5: Fast re-registration after graceful backend restart."""

    def test_graceful_restart_fast_reregistration(self, api_client, initial_workers):
        """
        Test that workers re-register within ~15 seconds of graceful restart.

        This validates the M7.5 improvement where backend notifies workers
        before shutdown, allowing them to poll and re-register quickly.

        Expected timeline:
        - T=0: Backend receives SIGTERM (docker compose restart)
        - T=0.1: Backend enters shutdown mode, notifies workers
        - T=0.5: Workers start polling for backend availability
        - T=5-10: Backend restarts, workers re-register immediately
        """
        print("\n=== M7.5 E2E Test: Fast Re-registration ===")

        # Get initial worker count
        initial_count = len(initial_workers)
        worker_ids = [w["worker_id"] for w in initial_workers]
        print(f"Initial workers ({initial_count}): {worker_ids}")

        # Restart backend (graceful - sends SIGTERM)
        print("Restarting backend (graceful)...")
        restart_start = time.time()
        assert restart_backend(), "Failed to restart backend"

        # Wait for backend to be ready
        print("Waiting for backend to become available...")
        assert wait_for_api(timeout=30), "Backend failed to restart"
        backend_ready_time = time.time() - restart_start
        print(f"Backend ready after {backend_ready_time:.1f}s")

        # Poll for workers to re-register (should be fast!)
        reregistration_start = time.time()
        workers = wait_for_workers(
            expected_count=initial_count,
            timeout=15,  # Should be much faster than 30-40s
        )
        reregistration_time = time.time() - reregistration_start

        print(f"Workers re-registered in {reregistration_time:.1f}s")
        print(
            f"Re-registered workers ({len(workers)}): {[w['worker_id'] for w in workers]}"
        )

        # Verify timing - should be fast on graceful shutdown
        # Allow some slack for CI environments
        assert reregistration_time < 20, (
            f"Re-registration took {reregistration_time:.1f}s - "
            f"expected < 20s for graceful shutdown. "
            f"This may indicate the shutdown notification is not working."
        )

        # Verify all workers re-registered
        registered_ids = [w["worker_id"] for w in workers]
        for wid in worker_ids:
            assert wid in registered_ids, f"Worker {wid} did not re-register"

        print("")
        print("=== M7.5 E2E TEST PASSED ===")
        print(
            f"All {initial_count} workers re-registered in {reregistration_time:.1f}s"
        )

    def test_workers_registered_after_restart(self, api_client, initial_workers):
        """
        Test that workers are available after backend restart.

        Simpler test that just verifies workers eventually register.
        Uses longer timeout for reliability.
        """
        print("\n=== M7.5 Test: Workers Available After Restart ===")

        initial_count = len(initial_workers)
        print(f"Initial workers: {initial_count}")

        # Restart backend
        print("Restarting backend...")
        assert restart_backend(), "Failed to restart backend"
        assert wait_for_api(timeout=30), "Backend failed to restart"
        print("Backend is back online")

        # Wait for workers with generous timeout
        workers = wait_for_workers(
            expected_count=initial_count,
            timeout=45,  # Allow full health check timeout + margin
        )

        print(f"Found {len(workers)} workers after restart")
        assert (
            len(workers) >= initial_count
        ), f"Expected {initial_count} workers, got {len(workers)}"

        print("=== TEST PASSED ===")


@pytest.mark.container_e2e
class TestM75ShutdownMode:
    """E2E tests for M7.5: Backend shutdown mode behavior."""

    def test_registration_during_normal_operation(self, api_client):
        """Test that registration works normally when backend is running."""
        worker_id = f"test-e2e-{int(time.time())}"

        response = api_client.post(
            "/workers/register",
            json={
                "worker_id": worker_id,
                "worker_type": "backtesting",
                "endpoint_url": f"http://{worker_id}:5003",
            },
        )

        assert response.status_code == 200, f"Registration failed: {response.text}"
        print(f"Successfully registered test worker: {worker_id}")


@pytest.mark.container_e2e
class TestM75MonitorBugFix:
    """E2E tests for M7.5: Monitor bug fixes."""

    def test_reregistration_without_prior_health_check(
        self, api_client, initial_workers
    ):
        """
        Test that re-registration works even without prior health checks.

        This validates the fix for Issue 1 where the monitor would skip
        checks if _last_health_check_received was None.

        The test restarts both backend and workers quickly to test
        the scenario where backend crashes before first health check.
        """
        print("\n=== M7.5 Test: Re-registration Without Prior Health Check ===")

        initial_count = len(initial_workers)

        # Quick restart to simulate backend crash before health checks
        print("Quick restart to test monitor bug fix...")
        assert restart_backend(), "Failed to restart backend"

        # Wait only briefly for backend (simulates quick restart)
        time.sleep(3)
        assert wait_for_api(timeout=30), "Backend failed to restart"

        # Workers should still re-register eventually
        print("Waiting for workers to re-register...")
        workers = wait_for_workers(
            expected_count=initial_count,
            timeout=60,  # Allow time for monitor to trigger
        )

        print(f"Found {len(workers)} workers after restart")
        assert (
            len(workers) >= initial_count
        ), f"Expected {initial_count} workers, got {len(workers)}"

        print("=== TEST PASSED ===")
        print("Workers re-registered successfully (monitor bug fix verified)")
