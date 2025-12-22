"""
End-to-end tests for agent cancellation.

Tests the full cancellation flow through the HTTP API:
- Cancel during design phase
- Cancel when no active cycle
- Trigger new cycle after cancel
- Cancellation speed

Run with: pytest tests/e2e/agent/test_agent_cancellation_e2e.py -v -m "e2e" --no-cov
Requires: Backend running (docker compose up)
"""

import asyncio
import time

import httpx
import pytest
import pytest_asyncio

BACKEND_URL = "http://localhost:8000/api/v1"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


@pytest_asyncio.fixture
async def backend_ready():
    """Wait for backend to be healthy before running tests."""
    max_retries = 30
    for _ in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    print("Backend healthy")
                    return True
        except Exception:
            pass
        await asyncio.sleep(1)

    pytest.skip("Backend not available")


@pytest_asyncio.fixture
async def clean_state(backend_ready):
    """Ensure no active agent cycle before test."""
    async with httpx.AsyncClient() as client:
        # Cancel any active cycle
        await client.delete(f"{BACKEND_URL}/agent/cancel", timeout=10.0)
        await asyncio.sleep(0.5)
    yield
    # Cleanup: cancel any cycle started during test
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BACKEND_URL}/agent/cancel", timeout=10.0)


class TestCancelDuringDesign:
    """E2E tests for cancellation during design phase."""

    @pytest.mark.asyncio
    async def test_cancel_during_design_phase(self, clean_state):
        """Cancel during design phase via HTTP API."""
        async with httpx.AsyncClient() as client:
            # Trigger cycle
            trigger_resp = await client.post(
                f"{BACKEND_URL}/agent/trigger", timeout=10.0
            )
            assert trigger_resp.status_code == 202
            data = trigger_resp.json()
            assert data["triggered"] is True
            op_id = data["operation_id"]

            # Wait for designing phase
            for _ in range(30):
                status_resp = await client.get(
                    f"{BACKEND_URL}/agent/status", timeout=10.0
                )
                status = status_resp.json()
                if status.get("phase") == "designing":
                    break
                await asyncio.sleep(0.2)

            # Cancel
            cancel_resp = await client.delete(
                f"{BACKEND_URL}/agent/cancel", timeout=10.0
            )
            assert cancel_resp.status_code == 200
            cancel_data = cancel_resp.json()
            assert cancel_data["success"] is True
            assert cancel_data["operation_id"] == op_id

            # Wait for cancellation
            await asyncio.sleep(1)

            # Verify operation is cancelled
            op_resp = await client.get(
                f"{BACKEND_URL}/operations/{op_id}", timeout=10.0
            )
            assert op_resp.status_code == 200
            op_data = op_resp.json()
            assert op_data["data"]["status"] == "cancelled"


class TestCancelNoActiveCycle:
    """E2E tests for cancel when no active cycle."""

    @pytest.mark.asyncio
    async def test_cancel_no_active_cycle_returns_404(self, clean_state):
        """Cancel when no active cycle returns 404."""
        async with httpx.AsyncClient() as client:
            cancel_resp = await client.delete(
                f"{BACKEND_URL}/agent/cancel", timeout=10.0
            )
            assert cancel_resp.status_code == 404
            data = cancel_resp.json()
            assert data["success"] is False
            assert data["reason"] == "no_active_cycle"


class TestTriggerAfterCancel:
    """E2E tests for triggering new cycle after cancel."""

    @pytest.mark.asyncio
    async def test_trigger_after_cancel_succeeds(self, clean_state):
        """Can trigger a new cycle after cancelling previous one."""
        async with httpx.AsyncClient() as client:
            # Start first cycle
            resp1 = await client.post(f"{BACKEND_URL}/agent/trigger", timeout=10.0)
            assert resp1.status_code == 202
            op_id1 = resp1.json()["operation_id"]

            await asyncio.sleep(0.5)

            # Cancel it
            cancel_resp = await client.delete(
                f"{BACKEND_URL}/agent/cancel", timeout=10.0
            )
            assert cancel_resp.status_code == 200

            await asyncio.sleep(1)

            # Verify first cycle is cancelled
            op_resp = await client.get(
                f"{BACKEND_URL}/operations/{op_id1}", timeout=10.0
            )
            assert op_resp.json()["data"]["status"] == "cancelled"

            # Start new cycle
            resp2 = await client.post(f"{BACKEND_URL}/agent/trigger", timeout=10.0)
            assert resp2.status_code == 202
            data2 = resp2.json()
            assert data2["triggered"] is True
            assert data2["operation_id"] != op_id1


class TestCancellationSpeed:
    """E2E tests for cancellation performance."""

    @pytest.mark.asyncio
    async def test_cancellation_completes_within_500ms(self, clean_state):
        """Cancellation should complete within 500ms."""
        async with httpx.AsyncClient() as client:
            # Trigger cycle
            resp = await client.post(f"{BACKEND_URL}/agent/trigger", timeout=10.0)
            op_id = resp.json()["operation_id"]

            await asyncio.sleep(0.5)

            # Time the cancellation
            start = time.time()
            cancel_resp = await client.delete(
                f"{BACKEND_URL}/agent/cancel", timeout=10.0
            )
            assert cancel_resp.status_code == 200

            # Poll for cancelled status
            for _ in range(10):
                op_resp = await client.get(
                    f"{BACKEND_URL}/operations/{op_id}", timeout=10.0
                )
                if op_resp.json()["data"]["status"] == "cancelled":
                    break
                await asyncio.sleep(0.05)

            elapsed = time.time() - start
            assert elapsed < 0.5, f"Cancellation took {elapsed:.3f}s, expected < 0.5s"


class TestChildOperationsCleanup:
    """E2E tests for child operation cleanup."""

    @pytest.mark.asyncio
    async def test_cancel_response_includes_child_op_id(self, clean_state):
        """Cancel response includes the child operation ID."""
        async with httpx.AsyncClient() as client:
            # Trigger and wait for designing phase
            resp = await client.post(f"{BACKEND_URL}/agent/trigger", timeout=10.0)
            assert resp.status_code == 202

            for _ in range(30):
                status_resp = await client.get(
                    f"{BACKEND_URL}/agent/status", timeout=10.0
                )
                status = status_resp.json()
                if status.get("phase") == "designing":
                    break
                await asyncio.sleep(0.2)

            # Cancel and check response has child ID
            cancel_resp = await client.delete(
                f"{BACKEND_URL}/agent/cancel", timeout=10.0
            )
            cancel_data = cancel_resp.json()
            assert cancel_data["success"] is True
            assert cancel_data.get("child_cancelled") is not None
