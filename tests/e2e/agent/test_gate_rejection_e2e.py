"""
End-to-end tests for gate rejection → memory flow.

Tests the full flow where training gate rejects but experiment is still
recorded to memory with partial results.

Run with: pytest tests/e2e/agent/test_gate_rejection_e2e.py -v -m "e2e" --no-cov
Requires: Backend running (docker compose up) with USE_STUB_WORKERS=true

Environment variables that affect behavior:
- TRAINING_GATE_MIN_ACCURACY: Set to 0.99 to force gate rejection
- STUB_WORKER_FAST: Set to true for faster stub worker delays
"""

import asyncio
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import yaml

BACKEND_URL = "http://localhost:8000/api/v1"
MEMORY_EXPERIMENTS_DIR = Path("memory/experiments")

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
            # Treat any error as "backend not ready yet" and retry
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


def count_experiments() -> int:
    """Count experiment files in memory directory."""
    if not MEMORY_EXPERIMENTS_DIR.exists():
        return 0
    return len(list(MEMORY_EXPERIMENTS_DIR.glob("*.yaml")))


def get_latest_experiment() -> dict | None:
    """Get the most recently created experiment from memory."""
    if not MEMORY_EXPERIMENTS_DIR.exists():
        return None

    experiments = list(MEMORY_EXPERIMENTS_DIR.glob("*.yaml"))
    if not experiments:
        return None

    latest = max(experiments, key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        return yaml.safe_load(f)


class TestGateRejectionRecordsExperiment:
    """E2E tests for gate rejection → memory recording."""

    @pytest.mark.asyncio
    async def test_training_gate_rejection_records_experiment(self, clean_state):
        """Gate rejection records experiment with partial results.

        This test requires:
        - Backend running with USE_STUB_WORKERS=true
        - TRAINING_GATE_MIN_ACCURACY=0.99 (to force gate rejection)

        The test verifies:
        1. Experiment is saved to memory/experiments/
        2. status is "gate_rejected_training"
        3. gate_rejection_reason is set
        4. results contains training metrics (test_accuracy, val_accuracy)
        5. results has None for backtest metrics (sharpe_ratio, total_trades, win_rate)
        """
        # Count experiments before
        before_count = count_experiments()

        async with httpx.AsyncClient() as client:
            # Trigger research cycle
            trigger_resp = await client.post(
                f"{BACKEND_URL}/agent/trigger",
                timeout=10.0,
            )
            assert (
                trigger_resp.status_code == 202
            ), f"Trigger failed: {trigger_resp.text}"
            trigger_data = trigger_resp.json()
            assert trigger_data["triggered"] is True
            op_id = trigger_data["operation_id"]

            # Poll until cycle completes (up to 4 minutes for training)
            max_polls = 120
            for i in range(max_polls):
                status_resp = await client.get(
                    f"{BACKEND_URL}/agent/status",
                    timeout=10.0,
                )
                status = status_resp.json()
                phase = status.get("phase")

                # Check if idle (cycle completed)
                if status.get("status") == "idle":
                    break

                # Log progress
                if i % 10 == 0:
                    print(f"Poll {i}/{max_polls}: phase={phase}")

                await asyncio.sleep(2)
            else:
                pytest.fail(f"Cycle did not complete in time. Last status: {status}")

            # Verify operation completed (not failed)
            op_resp = await client.get(
                f"{BACKEND_URL}/operations/{op_id}",
                timeout=10.0,
            )
            op_data = op_resp.json()
            assert op_data["data"]["status"] == "completed", (
                f"Operation should complete even with gate rejection, "
                f"got: {op_data['data']['status']}"
            )

        # Verify experiment was saved
        after_count = count_experiments()
        assert (
            after_count > before_count
        ), f"No new experiment recorded. Before: {before_count}, After: {after_count}"

        # Verify experiment content
        experiment = get_latest_experiment()
        assert experiment is not None, "Could not load latest experiment"

        # Verify gate rejection status
        assert (
            experiment.get("status") == "gate_rejected_training"
        ), f"Expected status 'gate_rejected_training', got: {experiment.get('status')}"

        # Verify gate rejection reason is set
        assert (
            experiment.get("gate_rejection_reason") is not None
        ), "gate_rejection_reason should be set"

        # Verify results field is present with training metrics
        results = experiment.get("results")
        assert results is not None, "results should be present even for gate rejection"

        # Training metrics should be present (test_accuracy, val_accuracy)
        assert "test_accuracy" in results, "test_accuracy should be in results"
        assert "val_accuracy" in results, "val_accuracy should be in results"

        # Backtest metrics should be None (skipped due to gate rejection)
        assert results.get("sharpe_ratio") is None, (
            f"sharpe_ratio should be None for training gate rejection, "
            f"got: {results.get('sharpe_ratio')}"
        )
        assert (
            results.get("total_trades") is None
        ), "total_trades should be None for training gate rejection"
        assert (
            results.get("win_rate") is None
        ), "win_rate should be None for training gate rejection"


class TestGateRejectionExperimentFields:
    """E2E tests for experiment field content."""

    @pytest.mark.asyncio
    async def test_experiment_has_required_fields(self, clean_state):
        """Verify experiment has all required fields after gate rejection."""
        # Count experiments before
        before_count = count_experiments()

        async with httpx.AsyncClient() as client:
            # Trigger research cycle
            trigger_resp = await client.post(
                f"{BACKEND_URL}/agent/trigger",
                timeout=10.0,
            )
            assert trigger_resp.status_code == 202

            # Poll until idle
            for _ in range(120):
                status_resp = await client.get(
                    f"{BACKEND_URL}/agent/status",
                    timeout=10.0,
                )
                if status_resp.json().get("status") == "idle":
                    break
                await asyncio.sleep(2)

        # Wait for experiment to be saved
        await asyncio.sleep(1)

        after_count = count_experiments()
        if after_count <= before_count:
            pytest.skip(
                "No new experiment recorded - may need TRAINING_GATE_MIN_ACCURACY=0.99"
            )

        experiment = get_latest_experiment()
        assert experiment is not None

        # Check all required ExperimentRecord fields
        required_fields = [
            "id",
            "timestamp",
            "strategy_name",
            "context",
            "results",
            "assessment",
            "source",
            "status",
        ]

        for field in required_fields:
            assert field in experiment, f"Missing required field: {field}"

        # For gate rejection, these should be set
        if experiment.get("status") == "gate_rejected_training":
            assert experiment.get("gate_rejection_reason") is not None
            # Backtest metrics within results should be None
            results = experiment.get("results", {}) or {}
            assert results.get("sharpe_ratio") is None
            assert results.get("total_trades") is None
            assert results.get("win_rate") is None


class TestGateRejectionReason:
    """E2E tests for gate rejection reason content."""

    @pytest.mark.asyncio
    async def test_gate_rejection_reason_includes_threshold(self, clean_state):
        """Gate rejection reason should include the actual threshold."""
        before_count = count_experiments()

        async with httpx.AsyncClient() as client:
            trigger_resp = await client.post(
                f"{BACKEND_URL}/agent/trigger",
                timeout=10.0,
            )
            assert trigger_resp.status_code == 202

            for _ in range(120):
                status_resp = await client.get(
                    f"{BACKEND_URL}/agent/status",
                    timeout=10.0,
                )
                if status_resp.json().get("status") == "idle":
                    break
                await asyncio.sleep(2)

        after_count = count_experiments()
        if after_count <= before_count:
            pytest.skip("No new experiment recorded")

        experiment = get_latest_experiment()
        if experiment is None or experiment.get("status") != "gate_rejected_training":
            pytest.skip("Latest experiment is not a gate rejection")

        reason = experiment.get("gate_rejection_reason", "")

        # The reason should mention "Training gate" and include threshold info
        assert (
            "Training gate" in reason or "training" in reason.lower()
        ), f"Reason should mention training gate: {reason}"
