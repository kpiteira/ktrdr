"""
Unit tests for worker state endpoint (Task 3.8).

Tests the /api/v1/operations/{operation_id}/state endpoint that workers expose
to allow backend to retrieve cached checkpoint state during cancellation.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.workers.base import WorkerAPIBase


class MockProgressBridge:
    """Mock progress bridge with get_state method."""

    def __init__(self, state_data: dict):
        self._state_data = state_data

    async def get_state(self):
        """Return cached state."""
        return self._state_data


class MockWorker(WorkerAPIBase):
    """Mock worker for testing state endpoint."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )


@pytest.mark.asyncio
class TestWorkerStateEndpoint:
    """Test /api/v1/operations/{operation_id}/state endpoint."""

    async def test_state_endpoint_returns_404_for_missing_operation(self):
        """Test state endpoint returns 404 for non-existent operation."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/api/v1/operations/nonexistent/state")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_state_endpoint_returns_complete_state_from_bridge(self):
        """Test state endpoint returns complete state from progress bridge."""
        worker = MockWorker()

        # Create operation with progress bridge
        operation_id = "test_op_state_001"
        mock_state = {
            "operation_id": operation_id,
            "operation_type": "backtesting",
            "progress": {"percentage": 50.0, "current_bar": 500},
            "checkpoint_data": {
                "current_bar_index": 500,
                "portfolio_state": {"cash": 50000.0, "positions": []},
            },
        }

        bridge = MockProgressBridge(mock_state)

        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        # Store bridge reference in operation metadata (simulate real flow)
        # In real implementation, this would be set during operation execution
        operation = worker._operations_service._operations[operation_id]
        operation._progress_bridge = bridge

        # Query state endpoint
        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["state"]["operation_id"] == operation_id
        assert data["state"]["checkpoint_data"]["current_bar_index"] == 500
        assert data["state"]["checkpoint_data"]["portfolio_state"]["cash"] == 50000.0

    async def test_state_endpoint_returns_basic_state_when_no_bridge(self):
        """Test state endpoint returns basic state when bridge not available."""
        worker = MockWorker()

        # Create operation without progress bridge
        operation_id = "test_op_state_002"
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        # Query state endpoint
        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Verify fallback to basic state
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["state"]["operation_id"] == operation_id
        assert "status" in data["state"]
        assert "progress" in data["state"]

    async def test_state_endpoint_returns_training_state_with_artifact_paths(self):
        """Test state endpoint returns training state with artifact paths (not bytes)."""
        worker = MockWorker()

        # Create training operation with artifacts
        operation_id = "test_op_training_001"
        mock_state = {
            "operation_id": operation_id,
            "operation_type": "training",
            "progress": {"percentage": 45.0, "epoch": 45},
            "epoch": 45,
            "train_loss": 0.5,
            "val_accuracy": 0.72,
            "artifacts": {
                # PATHS not bytes!
                "model.pt": f"data/checkpoints/artifacts/{operation_id}/model.pt",
                "optimizer.pt": f"data/checkpoints/artifacts/{operation_id}/optimizer.pt",
            },
        }

        bridge = MockProgressBridge(mock_state)

        # Create operation
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="training",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        operation = worker._operations_service._operations[operation_id]
        operation._progress_bridge = bridge

        # Query state endpoint
        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Verify artifact paths (not bytes!)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "artifacts" in data["state"]
        assert data["state"]["artifacts"]["model.pt"].startswith("data/checkpoints/")
        assert data["state"]["artifacts"]["optimizer.pt"].startswith(
            "data/checkpoints/"
        )
        # Verify these are strings (paths), not bytes
        assert isinstance(data["state"]["artifacts"]["model.pt"], str)
        assert isinstance(data["state"]["artifacts"]["optimizer.pt"], str)

    async def test_state_endpoint_handles_bridge_get_state_error(self):
        """Test state endpoint handles errors from bridge.get_state()."""
        worker = MockWorker()

        # Create bridge that raises error
        class BrokenBridge:
            async def get_state(self):
                raise RuntimeError("Bridge state unavailable")

        operation_id = "test_op_broken_001"
        bridge = BrokenBridge()

        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        operation = worker._operations_service._operations[operation_id]
        operation._progress_bridge = bridge

        # Query state endpoint
        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert (
            "error" in data["detail"].lower() or "unavailable" in data["detail"].lower()
        )
