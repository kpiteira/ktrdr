"""Tests for TrainingWorker following training-host-service pattern."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType


@pytest.fixture
def mock_training_manager():
    """Mock TrainingManager."""
    with patch("ktrdr.training.training_worker.TrainingManager") as mock:
        manager_instance = MagicMock()

        # Mock the train_multi_symbol_strategy method to return a result
        async def mock_train(*args, **kwargs):
            return {
                "model_path": "/models/test_model.pt",
                "training_metrics": {"final_loss": 0.05, "accuracy": 0.95},
                "test_metrics": {"test_loss": 0.06, "test_accuracy": 0.93},
                "model_info": {"version": "v1.0"},
            }

        manager_instance.train_multi_symbol_strategy = AsyncMock(side_effect=mock_train)
        mock.return_value = manager_instance
        yield mock


class TestTrainingWorker:
    """Test TrainingWorker implementation."""

    def test_worker_initialization(self):
        """Test TrainingWorker initializes correctly."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker(worker_port=5002, backend_url="http://backend:8000")

        assert worker.worker_type == WorkerType.TRAINING
        assert worker.operation_type == OperationType.TRAINING
        assert worker.worker_port == 5002
        assert worker._operations_service is not None

    def test_training_start_endpoint_exists(self):
        """Test /training/start endpoint is registered."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        # Test endpoint exists (should return 422 for missing body)
        response = client.post("/training/start")
        assert (
            response.status_code == 422
        )  # Unprocessable entity (missing request body)

    @pytest.mark.asyncio
    async def test_training_start_generates_operation_id_if_not_provided(
        self, mock_training_manager
    ):
        """Test operation_id is generated if task_id not provided."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "strategy_yaml": "strategy: test\nsymbols: [AAPL]\ntimeframes: [1d]",
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        response = client.post("/training/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_id" in data
        assert data["operation_id"].startswith("worker_training_")
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_training_start_uses_provided_task_id(self, mock_training_manager):
        """Test operation_id uses provided task_id (ID synchronization)."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "backend_train_12345",  # Backend provides this
            "strategy_yaml": "strategy: test\nsymbols: [EURUSD]\ntimeframes: [1h]",
            "symbols": ["EURUSD"],
            "timeframes": ["1h"],
        }

        response = client.post("/training/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "backend_train_12345"  # Same ID returned!

    @pytest.mark.asyncio
    async def test_training_creates_operation_in_operations_service(
        self, mock_training_manager
    ):
        """Test training creates operation in worker's OperationsService."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_train_op_123",
            "strategy_yaml": "strategy: test",
            "symbols": ["GBPUSD"],
            "timeframes": ["4h"],
        }

        response = client.post("/training/start", json=request_data)
        assert response.status_code == 200

        # Verify operation was created in OperationsService
        operation = await worker._operations_service.get_operation("test_train_op_123")
        assert operation is not None
        assert operation.operation_id == "test_train_op_123"
        assert operation.operation_type == OperationType.TRAINING

    @pytest.mark.asyncio
    async def test_training_manager_is_called(self, mock_training_manager):
        """Test TrainingManager is called."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "strategy_yaml": "strategy: neuro_mean_reversion",
            "symbols": ["USDJPY", "EURUSD"],
            "timeframes": ["1d", "1h"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        response = client.post("/training/start", json=request_data)
        assert response.status_code == 200

        # Verify TrainingManager was called
        assert mock_training_manager.called

    @pytest.mark.asyncio
    async def test_training_completes_operation_on_success(self, mock_training_manager):
        """Test operation is marked completed on successful training."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_complete_train",
            "strategy_yaml": "strategy: test",
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
        }

        response = client.post("/training/start", json=request_data)
        assert response.status_code == 200

        # Verify operation completed
        operation = await worker._operations_service.get_operation(
            "test_complete_train"
        )
        assert operation.status.value in [
            "completed",
            "running",
        ]  # May complete async

    @pytest.mark.asyncio
    async def test_training_returns_model_info(self, mock_training_manager):
        """Test training returns model information."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "strategy_yaml": "strategy: test",
            "symbols": ["EURUSD"],
            "timeframes": ["1d"],
        }

        response = client.post("/training/start", json=request_data)
        assert response.status_code == 200
        data = response.json()

        assert "model_path" in data
        assert isinstance(data.get("model_path"), str)

    @pytest.mark.asyncio
    async def test_training_fails_operation_on_exception(self, mock_training_manager):
        """Test operation is marked failed on exception."""
        from ktrdr.training.training_worker import TrainingWorker

        # Make manager raise exception
        mock_training_manager.return_value.train_multi_symbol_strategy.side_effect = (
            Exception("Training error")
        )

        worker = TrainingWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_fail_train",
            "strategy_yaml": "strategy: test",
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
        }

        # Should raise exception
        with pytest.raises(Exception, match="Training error"):
            client.post("/training/start", json=request_data)

        # Verify operation failed
        operation = await worker._operations_service.get_operation("test_fail_train")
        assert operation.status.value == "failed"

    def test_worker_forces_local_mode(self):
        """Test worker forces USE_TRAINING_HOST_SERVICE=false."""
        import os

        from ktrdr.training.training_worker import TrainingWorker

        # Set to true initially
        os.environ["USE_TRAINING_HOST_SERVICE"] = "true"

        TrainingWorker()  # Create worker (forces env var to false)

        # Should be forced to false
        assert os.environ.get("USE_TRAINING_HOST_SERVICE") == "false"

    def test_worker_app_is_fastapi_instance(self):
        """Test worker exports FastAPI app for uvicorn."""
        from fastapi import FastAPI

        from ktrdr.training.training_worker import app, worker

        assert isinstance(app, FastAPI)
        assert app is worker.app
