"""
Integration test for distributed checkpoint state retrieval (Task 3.8).

Tests the complete distributed flow:
1. Worker caches checkpoint state in progress bridge
2. Backend queries worker via HTTP to retrieve state
3. State includes artifact paths (not bytes) for shared filesystem

This validates that backend can retrieve cached checkpoint state from workers
during cancellation without transferring large artifacts over HTTP.

Architecture:
- Worker: FastAPI app with real OperationsService
- Backend: OperationServiceProxy querying worker via HTTP
- Shared filesystem: Artifact paths accessible to both
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.adapters.operation_service_proxy import (
    OperationServiceProxy,
)
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.workers.base import WorkerAPIBase


class MockTrainingContext:
    """Mock training context for progress bridge."""

    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.session_id = "test_session_001"
        self.total_epochs = 100
        self.total_batches = 10000
        self.training_config = {"progress": {"batch_stride": 10}}


def noop_progress_callback(*args, **kwargs):
    """No-op callback for testing."""
    pass


class TestWorkerForStateRetrieval(WorkerAPIBase):
    """Test worker with real progress bridge for integration testing."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.TRAINING,
            operation_type=OperationType.TRAINING,
            worker_port=5999,  # Test port
            backend_url="http://backend:8000",
        )


@pytest.mark.asyncio
class TestDistributedCheckpointStateRetrieval:
    """Integration tests for distributed checkpoint state retrieval."""

    async def test_full_distributed_state_retrieval_flow(self):
        """
        Test complete distributed flow: cache state → query via HTTP → retrieve state.

        Flow:
        1. Create worker with real OperationsService
        2. Create operation with real TrainingProgressBridge
        3. Cache checkpoint state with artifact paths
        4. Query worker via OperationServiceProxy
        5. Verify complete state returned with artifact paths
        """
        # Step 1: Create worker
        worker = TestWorkerForStateRetrieval()
        client = TestClient(worker.app)

        # Step 2: Create operation with progress bridge
        operation_id = "op_training_integration_001"
        context = MockTrainingContext(operation_id)
        bridge = TrainingProgressBridge(
            context=context, update_progress_callback=noop_progress_callback
        )

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

        # Attach bridge to operation (simulates real flow)
        operation = worker._operations_service._operations[operation_id]
        operation._progress_bridge = bridge
        bridge.started_at = datetime.now()

        # Step 3: Cache checkpoint state with artifact paths
        checkpoint_data = {
            "epoch": 45,
            "train_loss": 0.5,
            "val_accuracy": 0.72,
            "training_history": [
                {"epoch": 44, "loss": 0.52},
                {"epoch": 45, "loss": 0.50},
            ],
        }

        artifacts = {
            "model.pt": f"data/checkpoints/artifacts/{operation_id}/model.pt",
            "optimizer.pt": f"data/checkpoints/artifacts/{operation_id}/optimizer.pt",
            "config.json": f"data/checkpoints/artifacts/{operation_id}/config.json",
        }

        bridge.set_latest_checkpoint_state(
            checkpoint_data=checkpoint_data, artifacts=artifacts
        )

        # Update some progress (simulates training progress)
        bridge.on_epoch(epoch=45, total_epochs=100, metrics={"train_loss": 0.5})

        # Step 4: Query worker via HTTP (direct endpoint call)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Verify response structure
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        state = response_data["state"]

        # Step 5: Verify complete state returned
        # Basic fields
        assert state["operation_id"] == operation_id
        assert state["operation_type"] == "training"
        assert "progress" in state

        # Checkpoint data
        assert state["epoch"] == 45
        assert state["train_loss"] == 0.5
        assert state["val_accuracy"] == 0.72
        assert len(state["training_history"]) == 2

        # Artifact paths (not bytes!)
        assert "artifacts" in state
        assert isinstance(state["artifacts"], dict)
        assert isinstance(state["artifacts"]["model.pt"], str)
        assert state["artifacts"]["model.pt"].startswith("data/checkpoints/artifacts")
        assert operation_id in state["artifacts"]["model.pt"]
        assert state["artifacts"]["model.pt"].endswith(".pt")

        # All 3 artifacts present
        assert len(state["artifacts"]) == 3
        assert "model.pt" in state["artifacts"]
        assert "optimizer.pt" in state["artifacts"]
        assert "config.json" in state["artifacts"]

    async def test_distributed_state_retrieval_graceful_fallback(self):
        """
        Test graceful fallback when bridge unavailable.

        Validates that system returns basic state instead of failing.
        """
        worker = TestWorkerForStateRetrieval()
        client = TestClient(worker.app)

        # Create operation WITHOUT progress bridge
        operation_id = "op_training_fallback_001"
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

        # Query state (should fallback to basic state)
        response = client.get(f"/api/v1/operations/{operation_id}/state")

        # Verify graceful fallback
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        state = response_data["state"]

        # Basic state fields
        assert state["operation_id"] == operation_id
        assert state["operation_type"] == "training"
        assert "status" in state
        assert "progress" in state

    async def test_distributed_state_retrieval_artifact_path_format(self):
        """
        Test artifact path format matches shared filesystem structure.

        Validates paths are in correct format for shared filesystem access.
        """
        worker = TestWorkerForStateRetrieval()
        client = TestClient(worker.app)

        operation_id = "op_training_artifacts_001"
        context = MockTrainingContext(operation_id)
        bridge = TrainingProgressBridge(
            context=context, update_progress_callback=noop_progress_callback
        )

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

        # Cache checkpoint with artifact paths
        artifacts = {
            "model.pt": f"data/checkpoints/artifacts/{operation_id}/model.pt",
            "optimizer.pt": f"data/checkpoints/artifacts/{operation_id}/optimizer.pt",
        }
        bridge.set_latest_checkpoint_state(checkpoint_data={}, artifacts=artifacts)

        # Query state
        response = client.get(f"/api/v1/operations/{operation_id}/state")
        state = response.json()["state"]

        # Verify artifact path format
        for artifact_name, artifact_path in state["artifacts"].items():
            # Path is a string
            assert isinstance(artifact_path, str)

            # Path starts with data/checkpoints/artifacts/
            assert artifact_path.startswith("data/checkpoints/artifacts/")

            # Path includes operation_id
            assert operation_id in artifact_path

            # Path ends with correct extension
            assert artifact_path.endswith(f".{artifact_name.split('.')[-1]}")

            # Path is relative (not absolute)
            assert not artifact_path.startswith("/")

            # Path uses forward slashes (POSIX style)
            assert "\\" not in artifact_path
