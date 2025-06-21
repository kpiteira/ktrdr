"""
Unit tests for TrainingService.

Tests the training service that manages async neural network training operations
and integrates with the OperationsService framework.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path

from ktrdr.api.services.training_service import TrainingService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationType, OperationStatus
from ktrdr.errors import ValidationError, DataError


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    from ktrdr.api.models.operations import (
        OperationInfo,
        OperationType,
        OperationStatus,
        OperationMetadata,
        OperationProgress,
    )
    from datetime import datetime, timezone

    mock = AsyncMock(spec=OperationsService)

    # Create a mock OperationInfo object
    mock_operation = OperationInfo(
        operation_id="test_training_id",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        metadata=OperationMetadata(),
        progress=OperationProgress(),
    )

    mock.create_operation.return_value = mock_operation
    mock.start_operation.return_value = None
    mock.update_progress.return_value = None
    mock.complete_operation.return_value = None
    mock.fail_operation.return_value = None
    return mock


@pytest.fixture
def training_service(mock_operations_service):
    """Create a TrainingService with mocked dependencies."""
    with (
        patch("ktrdr.api.services.training_service.ModelStorage"),
        patch("ktrdr.api.services.training_service.ModelLoader"),
    ):
        service = TrainingService(operations_service=mock_operations_service)
        return service


@pytest.fixture
def sample_training_config():
    """Sample training configuration."""
    return {
        "model_type": "mlp",
        "hidden_layers": [64, 32, 16],
        "epochs": 100,
        "learning_rate": 0.001,
        "batch_size": 32,
        "validation_split": 0.2,
        "early_stopping": {"patience": 10, "monitor": "val_accuracy"},
        "optimizer": "adam",
        "dropout_rate": 0.2,
    }


@pytest.fixture
def sample_training_params(sample_training_config):
    """Sample training parameters."""
    return {
        "symbol": "AAPL",
        "timeframe": "1h",
        "config": sample_training_config,
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    }


class TestTrainingService:
    """Test TrainingService functionality."""

    @pytest.mark.asyncio
    async def test_start_training_success(
        self, training_service, mock_operations_service, sample_training_params
    ):
        """Test successfully starting a training operation."""
        result = await training_service.start_training(**sample_training_params)

        assert result["success"] is True
        assert result["task_id"] == "test_training_id"
        assert result["status"] == "training_started"
        assert "AAPL" in result["message"]
        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "1h"
        assert result["config"] == sample_training_params["config"]

        # Verify operations service was called correctly
        mock_operations_service.create_operation.assert_called_once()
        call_args = mock_operations_service.create_operation.call_args
        assert call_args[1]["operation_type"] == OperationType.TRAINING

        mock_operations_service.start_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_training_with_optional_params(
        self, training_service, mock_operations_service, sample_training_params
    ):
        """Test starting training with optional task_id parameter."""
        sample_training_params["task_id"] = "custom_task_id"

        result = await training_service.start_training(**sample_training_params)

        assert result["success"] is True
        assert result["task_id"] == "test_training_id"  # Service generates its own ID

    @pytest.mark.asyncio
    async def test_get_model_performance_success(
        self, training_service, mock_operations_service
    ):
        """Test getting model performance for completed training."""
        mock_operation = MagicMock()
        mock_operation.operation_id = "completed_training_id"
        mock_operation.status.value = "completed"
        mock_operation.progress.items_processed = 100
        mock_operation.metadata.parameters = {
            "config": {"epochs": 100, "hidden_layers": [64, 32, 16]}
        }
        mock_operation.result_summary = {
            "training_metrics": {
                "final_train_loss": 0.025,
                "final_val_loss": 0.032,
                "final_train_accuracy": 0.94,
                "final_val_accuracy": 0.91,
                "early_stopped": False,
                "training_time_minutes": 28.5,
            },
            "test_metrics": {
                "test_loss": 0.038,
                "test_accuracy": 0.90,
                "precision": 0.89,
                "recall": 0.91,
                "f1_score": 0.90,
            },
            "model_info": {
                "model_size_mb": 15.2,
                "parameters_count": 142500,
                "architecture": "mlp_64_32_16",
            },
        }

        mock_operations_service.get_operation.return_value = mock_operation

        performance = await training_service.get_model_performance(
            "completed_training_id"
        )

        assert performance["success"] is True
        assert performance["task_id"] == "completed_training_id"
        assert performance["status"] == "completed"
        assert performance["training_metrics"]["final_train_accuracy"] == 0.94
        assert performance["test_metrics"]["test_accuracy"] == 0.90
        assert performance["model_info"]["model_size_mb"] == 15.2

    @pytest.mark.asyncio
    async def test_get_model_performance_not_completed(
        self, training_service, mock_operations_service
    ):
        """Test getting performance for non-completed training."""
        mock_operation = MagicMock()
        mock_operation.status.value = "running"

        mock_operations_service.get_operation.return_value = mock_operation

        with pytest.raises(ValidationError, match="not completed"):
            await training_service.get_model_performance("running_training_id")

    @pytest.mark.asyncio
    async def test_save_trained_model_success(
        self, training_service, mock_operations_service
    ):
        """Test saving a trained model."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {"model_path": "/tmp/test_model.pth"}

        mock_operations_service.get_operation.return_value = mock_operation

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):

            mock_stat.return_value.st_size = 15728640  # 15MB in bytes

            result = await training_service.save_trained_model(
                "completed_training_id", "my_model", "Test model description"
            )

            assert result["success"] is True
            assert result["model_name"] == "my_model"
            assert result["task_id"] == "completed_training_id"
            assert result["model_size_mb"] == 15.0
            assert "model_" in result["model_id"]

    @pytest.mark.asyncio
    async def test_save_trained_model_not_completed(
        self, training_service, mock_operations_service
    ):
        """Test saving model for non-completed training."""
        mock_operation = MagicMock()
        mock_operation.status.value = "running"

        mock_operations_service.get_operation.return_value = mock_operation

        with pytest.raises(ValidationError, match="not completed"):
            await training_service.save_trained_model("running_training_id", "my_model")

    @pytest.mark.asyncio
    async def test_save_trained_model_file_not_found(
        self, training_service, mock_operations_service
    ):
        """Test saving model when model file doesn't exist."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {"model_path": "/tmp/nonexistent_model.pth"}

        mock_operations_service.get_operation.return_value = mock_operation

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValidationError, match="model file not found"):
                await training_service.save_trained_model(
                    "completed_training_id", "my_model"
                )

    @pytest.mark.asyncio
    async def test_load_trained_model_success(self, training_service):
        """Test loading a trained model."""
        # Mock ModelStorage to return available models
        mock_model_info = {
            "name": "test_model",
            "path": "/tmp/test_model.pth",
            "created_at": "2024-01-01T00:00:00Z",
            "symbol": "AAPL",
            "timeframe": "1h",
        }

        with (
            patch.object(
                training_service.model_storage,
                "list_models",
                return_value=[mock_model_info],
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):

            result = await training_service.load_trained_model("test_model")

            assert result["success"] is True
            assert result["model_name"] == "test_model"
            assert result["model_loaded"] is True
            assert result["model_info"]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_load_trained_model_not_found(self, training_service):
        """Test loading a non-existent model."""
        with patch.object(
            training_service.model_storage, "list_models", return_value=[]
        ):
            with pytest.raises(ValidationError, match="not found"):
                await training_service.load_trained_model("nonexistent_model")

    @pytest.mark.asyncio
    async def test_test_model_prediction(self, training_service):
        """Test making predictions with a loaded model."""
        # First "load" a model
        with patch.dict(
            "ktrdr.api.services.training_service._loaded_models",
            {"test_model": {"model": "mock_model", "info": {}}},
        ):

            result = await training_service.test_model_prediction(
                "test_model", "AAPL", "1h", "2024-01-01"
            )

            assert result["success"] is True
            assert result["model_name"] == "test_model"
            assert result["symbol"] == "AAPL"
            assert result["test_date"] == "2024-01-01"
            assert "prediction" in result
            assert "signal" in result["prediction"]

    @pytest.mark.asyncio
    async def test_test_model_prediction_not_loaded(self, training_service):
        """Test making predictions with an unloaded model."""
        with pytest.raises(ValidationError, match="not loaded"):
            await training_service.test_model_prediction("unloaded_model", "AAPL")

    @pytest.mark.asyncio
    async def test_list_trained_models(self, training_service):
        """Test listing all trained models."""
        mock_models = [
            {
                "id": "model_1",
                "name": "test_model_1",
                "symbol": "AAPL",
                "timeframe": "1h",
                "created_at": "2024-01-01T00:00:00Z",
                "description": "Test model 1",
            },
            {
                "id": "model_2",
                "name": "test_model_2",
                "symbol": "MSFT",
                "timeframe": "1d",
                "created_at": "2024-01-02T00:00:00Z",
                "description": "Test model 2",
            },
        ]

        with patch.object(
            training_service.model_storage, "list_models", return_value=mock_models
        ):
            result = await training_service.list_trained_models()

            assert result["success"] is True
            assert len(result["models"]) == 2
            assert result["models"][0]["model_name"] == "test_model_1"
            assert result["models"][1]["model_name"] == "test_model_2"

    @pytest.mark.asyncio
    async def test_run_training_async_integration(
        self, training_service, mock_operations_service, sample_training_config
    ):
        """Test the async training execution flow."""
        with (
            patch("tempfile.NamedTemporaryFile") as mock_temp_file,
            patch("yaml.dump"),
            patch("pathlib.Path.unlink"),
            patch(
                "ktrdr.api.services.training_service.StrategyTrainer"
            ) as mock_trainer_class,
        ):

            # Mock temporary file
            mock_temp_file.return_value.__enter__.return_value.name = (
                "/tmp/temp_strategy.yaml"
            )

            # Mock trainer
            mock_trainer = MagicMock()
            mock_trainer_class.return_value = mock_trainer
            mock_trainer.train_strategy.return_value = {
                "model_path": "/tmp/trained_model.pth",
                "final_metrics": {"accuracy": 0.92},
            }

            # Call the async training method
            await training_service._run_training_async(
                "test_operation_id",
                "AAPL",
                "1h",
                sample_training_config,
                "2024-01-01",
                "2024-06-01",
            )

            # Verify progress updates were called
            assert mock_operations_service.update_progress.call_count >= 3

            # Verify completion was called
            mock_operations_service.complete_operation.assert_called_once()

            # Verify trainer was called
            mock_trainer.train_strategy.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_training_async_failure(
        self, training_service, mock_operations_service, sample_training_config
    ):
        """Test handling of training failures."""
        with (
            patch("tempfile.NamedTemporaryFile"),
            patch("yaml.dump"),
            patch("pathlib.Path.unlink"),
            patch(
                "ktrdr.api.services.training_service.StrategyTrainer"
            ) as mock_trainer_class,
        ):

            # Mock trainer to raise an exception
            mock_trainer = MagicMock()
            mock_trainer_class.return_value = mock_trainer
            mock_trainer.train_strategy.side_effect = Exception("Training failed")

            # Call the async training method
            await training_service._run_training_async(
                "test_operation_id",
                "AAPL",
                "1h",
                sample_training_config,
                "2024-01-01",
                "2024-06-01",
            )

            # Verify failure was called
            mock_operations_service.fail_operation.assert_called_once_with(
                "test_operation_id", "Training failed"
            )
