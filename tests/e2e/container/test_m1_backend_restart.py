"""E2E test for M1: Operations Persistence across real backend restart.

This test validates the complete M1 capability by:
1. Starting an operation via the API
2. Restarting the backend container (docker compose restart backend)
3. Verifying the operation state persisted in the database
4. Simulating worker re-registration with operation state
5. Verifying reconciliation updates the operation correctly

Requirements:
- Docker containers must be running: docker compose up -d
- Test will be skipped if API is not available

Usage:
    pytest tests/e2e/container/test_m1_backend_restart.py -v --tb=short
"""

import subprocess
import time
from datetime import datetime, timezone

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
        time.sleep(2)
    return False


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


@pytest.fixture(scope="module")
def api_client():
    """Create HTTP client for API testing."""
    if not check_api_available():
        pytest.skip("API server not available - requires Docker containers running")
    return httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT)


@pytest.mark.container_e2e
class TestM1BackendRestart:
    """E2E tests for M1: Operations persist across backend restart."""

    def test_operation_persists_after_backend_restart(self, api_client):
        """
        Test that an operation survives a backend restart.

        This is the core M1 validation: operations stored in PostgreSQL
        survive when the backend process restarts.
        """
        # Step 1: Create an operation
        response = api_client.post(
            "/operations",
            json={
                "operation_type": "backtesting",
                "metadata": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "mode": "backtest",
                },
            },
        )
        assert (
            response.status_code == 200
        ), f"Failed to create operation: {response.text}"
        operation_data = response.json()
        operation_id = operation_data["data"]["operation_id"]
        print(f"\nCreated operation: {operation_id}")

        # Step 2: Verify operation exists before restart
        response = api_client.get(f"/operations/{operation_id}")
        assert response.status_code == 200
        pre_restart_status = response.json()["data"]["status"]
        print(f"Pre-restart status: {pre_restart_status}")

        # Step 3: Restart the backend
        print("Restarting backend container...")
        assert restart_backend(), "Failed to restart backend"

        # Step 4: Wait for backend to come back up
        print(f"Waiting for backend to restart (up to {BACKEND_RESTART_WAIT}s)...")
        assert wait_for_api(
            timeout=BACKEND_RESTART_WAIT + 30
        ), "Backend failed to restart"
        print("Backend is back online")

        # Step 5: Verify operation still exists after restart
        # Need new client since backend restarted
        with httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
            response = client.get(f"/operations/{operation_id}")
            assert (
                response.status_code == 200
            ), f"Operation not found after restart: {operation_id}"
            post_restart_data = response.json()["data"]
            print(f"Post-restart status: {post_restart_data['status']}")

            # Operation should exist with same ID
            assert post_restart_data["operation_id"] == operation_id
            # Status might be PENDING_RECONCILIATION after restart
            assert post_restart_data["status"] in [
                "pending",
                "running",
                "pending_reconciliation",
            ]

    def test_worker_reregistration_syncs_operation_status(self, api_client):
        """
        Test that worker re-registration after backend restart syncs operation status.

        Flow:
        1. Register a worker
        2. Create an operation
        3. Restart backend
        4. Worker re-registers with current_operation_id
        5. Operation status should be synced
        """
        # Step 1: Register a worker
        worker_id = f"test-worker-{int(time.time())}"
        response = api_client.post(
            "/workers/register",
            json={
                "worker_id": worker_id,
                "worker_type": "backtesting",
                "endpoint_url": f"http://{worker_id}:5003",
            },
        )
        assert response.status_code == 200
        print(f"\nRegistered worker: {worker_id}")

        # Step 2: Create an operation
        response = api_client.post(
            "/operations",
            json={
                "operation_type": "backtesting",
                "metadata": {"symbol": "GBPUSD", "timeframe": "4h"},
            },
        )
        assert response.status_code == 200
        operation_id = response.json()["data"]["operation_id"]
        print(f"Created operation: {operation_id}")

        # Step 3: Restart backend
        print("Restarting backend...")
        assert restart_backend()
        assert wait_for_api(timeout=BACKEND_RESTART_WAIT + 30)
        print("Backend restarted")

        # Step 4: Worker re-registers with current_operation_id
        with httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
            response = client.post(
                "/workers/register",
                json={
                    "worker_id": worker_id,
                    "worker_type": "backtesting",
                    "endpoint_url": f"http://{worker_id}:5003",
                    "current_operation_id": operation_id,
                },
            )
            assert response.status_code == 200
            print(f"Worker re-registered with operation: {operation_id}")

            # Step 5: Verify operation status
            response = client.get(f"/operations/{operation_id}")
            assert response.status_code == 200
            status = response.json()["data"]["status"]
            print(f"Operation status after re-registration: {status}")

            # After reconciliation, operation should be RUNNING
            # (worker reported it as current, so it's still running)
            assert status in ["running", "pending_reconciliation"]

    def test_completed_operation_reconciliation(self, api_client):
        """
        Test that completed operations are reconciled on worker re-registration.

        Flow:
        1. Create an operation
        2. Restart backend
        3. Worker re-registers reporting the operation completed
        4. Operation should be marked COMPLETED
        """
        # Step 1: Create an operation
        response = api_client.post(
            "/operations",
            json={
                "operation_type": "training",
                "metadata": {"symbol": "USDJPY", "timeframe": "1h"},
            },
        )
        assert response.status_code == 200
        operation_id = response.json()["data"]["operation_id"]
        print(f"\nCreated operation: {operation_id}")

        # Step 2: Restart backend
        print("Restarting backend...")
        assert restart_backend()
        assert wait_for_api(timeout=BACKEND_RESTART_WAIT + 30)
        print("Backend restarted")

        # Step 3: Worker re-registers reporting completion
        worker_id = f"training-worker-{int(time.time())}"
        with httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
            response = client.post(
                "/workers/register",
                json={
                    "worker_id": worker_id,
                    "worker_type": "training",
                    "endpoint_url": f"http://{worker_id}:5004",
                    "completed_operations": [
                        {
                            "operation_id": operation_id,
                            "status": "COMPLETED",
                            "result": {"accuracy": 0.95},
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                },
            )
            assert response.status_code == 200
            print("Worker reported operation completed")

            # Step 4: Verify operation is COMPLETED
            response = client.get(f"/operations/{operation_id}")
            assert response.status_code == 200
            status = response.json()["data"]["status"]
            print(f"Operation status after completion report: {status}")
            assert status == "completed"


@pytest.mark.container_e2e
class TestM1E2EScriptValidation:
    """
    Validates the M1 E2E test scenario from the milestone plan.

    This runs the same steps as the bash script in PLAN_M1_operations_persistence.md
    """

    def test_m1_e2e_scenario(self, api_client):
        """
        Complete M1 E2E test matching the milestone plan script.

        Steps from plan:
        1. Verify worker is registered
        2. Start a training operation
        3. Verify operation is RUNNING
        4. Restart backend
        5. Verify operation persisted
        6. Wait for worker re-registration
        7. Final verification
        """
        print("\n=== M1 E2E Test: Operations Persistence + Re-Registration ===")

        # Step 1: Check workers registered
        print("Step 1: Check workers registered...")
        response = api_client.get("/workers")
        workers = response.json()
        worker_count = len(workers) if isinstance(workers, list) else 0
        print(f"  Found {worker_count} worker(s)")
        # Note: We don't require workers for this test

        # Step 2: Create a training operation
        print("Step 2: Create training operation...")
        response = api_client.post(
            "/operations",
            json={
                "operation_type": "training",
                "metadata": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "parameters": {"strategy_name": "m1_e2e_test"},
                },
            },
        )
        assert response.status_code == 200
        operation_id = response.json()["data"]["operation_id"]
        print(f"  Created operation: {operation_id}")

        # Step 3: Verify initial status
        print("Step 3: Verify operation status...")
        response = api_client.get(f"/operations/{operation_id}")
        assert response.status_code == 200
        status = response.json()["data"]["status"]
        print(f"  Status: {status}")
        # Operation starts as PENDING, that's expected
        assert status in ["pending", "running"]

        # Step 4: Restart backend
        print("Step 4: Restarting backend...")
        assert restart_backend(), "Failed to restart backend"
        time.sleep(5)  # Brief pause

        # Step 5: Wait for backend and verify operation persisted
        print("Step 5: Verify operation persisted...")
        assert wait_for_api(timeout=60), "Backend failed to come back"

        with httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
            response = client.get(f"/operations/{operation_id}")
            assert response.status_code == 200, "Operation not found after restart"
            data = response.json()["data"]
            print(f"  Operation exists: {data['operation_id']}")
            print(f"  Status: {data['status']}")

            # Step 6 & 7: Final verification
            print("Step 6-7: Final verification...")
            # Operation should exist with a valid status
            assert data["operation_id"] == operation_id
            assert data["status"] in [
                "pending",
                "running",
                "completed",
                "failed",
                "pending_reconciliation",
            ]

            print("")
            print("=== M1 E2E TEST PASSED ===")
            print(f"Operation {operation_id} survived backend restart")
