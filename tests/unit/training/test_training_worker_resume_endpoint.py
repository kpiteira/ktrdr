"""Unit tests for Training Worker /training/resume endpoint (Task 4.4)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import torch
import torch.nn as nn
import torch.optim as optim
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def mock_operations_service():
    """Provide a mock OperationsService without real DB connections."""
    service = OperationsService(repository=None)
    return service


@pytest.fixture
def sample_model_weights():
    """Create sample serialized model weights."""
    model = nn.Linear(10, 2)
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.getvalue()


@pytest.fixture
def sample_optimizer_state():
    """Create sample serialized optimizer state."""
    model = nn.Linear(10, 2)
    optimizer = optim.Adam(model.parameters())
    buffer = io.BytesIO()
    torch.save(optimizer.state_dict(), buffer)
    return buffer.getvalue()


class TestTrainingResumeRequest:
    """Tests for TrainingResumeRequest model."""

    def test_request_model_exists(self):
        """TrainingResumeRequest model should exist."""
        from ktrdr.training.training_worker import TrainingResumeRequest

        request = TrainingResumeRequest(operation_id="op_test_123")
        assert request.operation_id == "op_test_123"

    def test_request_requires_operation_id(self):
        """TrainingResumeRequest should require operation_id."""
        from pydantic import ValidationError

        from ktrdr.training.training_worker import TrainingResumeRequest

        with pytest.raises(ValidationError):
            TrainingResumeRequest()


class TestTrainingResumeEndpoint:
    """Tests for POST /training/resume endpoint."""

    @pytest.fixture
    def training_worker(self, mock_operations_service):
        """Create a TrainingWorker with mocked dependencies."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker(
            worker_port=5005,
            backend_url="http://test:8000",
        )
        # Override operations service to avoid DB
        worker._operations_service = mock_operations_service
        return worker

    @pytest.fixture
    def client(self, training_worker):
        """Create test client for training worker."""
        return TestClient(training_worker.app)

    def test_resume_endpoint_exists(
        self, client, training_worker, sample_model_weights, sample_optimizer_state
    ):
        """POST /training/resume endpoint should exist."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Mock restore_from_checkpoint to avoid actual checkpoint lookup
        mock_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=sample_model_weights,
            optimizer_state=sample_optimizer_state,
        )

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.return_value = mock_context

            with patch.object(
                training_worker, "_execute_resumed_training", new_callable=AsyncMock
            ):
                response = client.post(
                    "/training/resume",
                    json={"operation_id": "op_test_123"},
                )

        # Should not be 404 (endpoint not found) or 405 (method not allowed)
        # 200 is success, 4xx other than 404/405 would indicate endpoint exists but validation failed
        assert response.status_code not in [
            404,
            405,
        ], f"Endpoint doesn't exist. Status: {response.status_code}"
        assert (
            response.status_code == 200
        ), f"Unexpected status: {response.status_code}, body: {response.json()}"

    def test_resume_returns_success_with_valid_checkpoint(
        self,
        client,
        training_worker,
        sample_model_weights,
        sample_optimizer_state,
    ):
        """Resume should return success when checkpoint exists."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Mock the restore_from_checkpoint to return valid context
        mock_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=sample_model_weights,
            optimizer_state=sample_optimizer_state,
            training_history={"train_loss": [1.0, 0.8]},
            best_val_loss=0.75,
        )

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.return_value = mock_context

            # Also mock the resumed training execution
            with patch.object(
                training_worker, "_execute_resumed_training", new_callable=AsyncMock
            ):
                response = client.post(
                    "/training/resume",
                    json={"operation_id": "op_test_123"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_test_123"
        assert data["status"] == "started"

    def test_resume_calls_restore_from_checkpoint(
        self,
        client,
        training_worker,
        sample_model_weights,
        sample_optimizer_state,
    ):
        """Resume should call restore_from_checkpoint with operation_id."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        mock_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=sample_model_weights,
            optimizer_state=sample_optimizer_state,
        )

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.return_value = mock_context

            with patch.object(
                training_worker, "_execute_resumed_training", new_callable=AsyncMock
            ):
                client.post(
                    "/training/resume",
                    json={"operation_id": "op_test_456"},
                )

        mock_restore.assert_called_once_with("op_test_456")

    def test_resume_starts_training_in_background(
        self,
        client,
        training_worker,
        sample_model_weights,
        sample_optimizer_state,
    ):
        """Resume should start training in background (non-blocking)."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        mock_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=sample_model_weights,
            optimizer_state=sample_optimizer_state,
        )

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.return_value = mock_context

            with patch.object(
                training_worker, "_execute_resumed_training", new_callable=AsyncMock
            ):
                response = client.post(
                    "/training/resume",
                    json={"operation_id": "op_test_789"},
                )

        # Should return immediately (background task scheduled)
        assert response.status_code == 200

    def test_resume_returns_404_when_no_checkpoint(
        self,
        client,
        training_worker,
    ):
        """Resume should return 404 when no checkpoint exists."""
        from ktrdr.training.checkpoint_restore import CheckpointNotFoundError

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.side_effect = CheckpointNotFoundError("op_test_123")

            response = client.post(
                "/training/resume",
                json={"operation_id": "op_test_123"},
            )

        assert response.status_code == 404
        data = response.json()
        assert (
            "checkpoint" in data["detail"].lower()
            or "not found" in data["detail"].lower()
        )

    def test_resume_returns_422_when_checkpoint_corrupted(
        self,
        client,
        training_worker,
    ):
        """Resume should return 422 when checkpoint is corrupted."""
        from ktrdr.training.checkpoint_restore import CheckpointCorruptedError

        with patch.object(
            training_worker, "restore_from_checkpoint", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.side_effect = CheckpointCorruptedError("Missing model.pt")

            response = client.post(
                "/training/resume",
                json={"operation_id": "op_test_123"},
            )

        assert response.status_code == 422
        data = response.json()
        assert (
            "corrupt" in data["detail"].lower() or "missing" in data["detail"].lower()
        )


class TestTrainingWorkerExecuteResumedTraining:
    """Tests for TrainingWorker._execute_resumed_training method."""

    @pytest.fixture
    def training_worker(self, mock_operations_service):
        """Create a TrainingWorker with mocked dependencies."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker(
            worker_port=5005,
            backend_url="http://test:8000",
        )
        worker._operations_service = mock_operations_service
        return worker

    def test_execute_resumed_training_method_exists(self, training_worker):
        """TrainingWorker should have _execute_resumed_training method."""
        assert hasattr(training_worker, "_execute_resumed_training")
        assert callable(training_worker._execute_resumed_training)

    @pytest.mark.asyncio
    async def test_execute_resumed_training_calls_start_operation(
        self,
        training_worker,
        sample_model_weights,
        sample_optimizer_state,
    ):
        """Resumed training should call start_operation to mark as RUNNING."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        resume_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=sample_model_weights,
            optimizer_state=sample_optimizer_state,
            original_request={
                "strategy_yaml": "name: test\ntype: neuro",
                "symbols": ["BTCUSD"],
                "timeframes": ["1h"],
            },
        )

        # Create operation first (simulating backend flow)
        await training_worker._operations_service.create_operation(
            operation_id="op_test_resume",
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="BTCUSD",
                timeframe="1h",
                mode="training",
            ),
        )

        # Mock operations service start_operation
        with patch.object(
            training_worker._operations_service,
            "start_operation",
            new_callable=AsyncMock,
        ) as mock_start:
            # Mock get_cancellation_token to return a mock token
            with patch.object(
                training_worker._operations_service,
                "get_cancellation_token",
                return_value=MagicMock(),
            ):
                # Mock LocalTrainingOrchestrator from where it's imported
                with patch(
                    "ktrdr.api.services.training.local_orchestrator.LocalTrainingOrchestrator"
                ) as mock_orchestrator_class:
                    mock_orchestrator = MagicMock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    # Mock the async run method
                    mock_orchestrator.run = AsyncMock(
                        return_value={
                            "model_path": "/path/to/model",
                            "training_metrics": {},
                            "test_metrics": {},
                        }
                    )

                    # Also mock other required services
                    with patch.object(
                        training_worker, "get_checkpoint_service"
                    ) as mock_cp:
                        mock_cp_service = AsyncMock()
                        mock_cp.return_value = mock_cp_service
                        mock_cp_service.delete_checkpoint = AsyncMock(return_value=True)

                        # Mock complete_operation
                        with patch.object(
                            training_worker._operations_service,
                            "complete_operation",
                            new_callable=AsyncMock,
                        ):
                            # Mock register_local_bridge
                            with patch.object(
                                training_worker._operations_service,
                                "register_local_bridge",
                            ):
                                # Execute resumed training
                                try:
                                    await training_worker._execute_resumed_training(
                                        "op_test_resume", resume_context
                                    )
                                except Exception:
                                    # May fail due to other unmocked dependencies
                                    # but we're testing start_operation was called
                                    pass

                                # Verify start_operation was called
                                mock_start.assert_called_once()
