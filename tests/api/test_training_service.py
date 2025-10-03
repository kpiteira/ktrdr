"""
Unit tests for TrainingService orchestrator integration.

This suite exercises the refactored TrainingService that now subclasses
ServiceOrchestrator and relies on the new training context helpers.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.training import TrainingOperationContext
from ktrdr.api.services.training_service import TrainingService
from ktrdr.errors import ValidationError


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    operations_service = AsyncMock()

    # Provide OperationInfo stub like previous tests relied on
    from ktrdr.api.models.operations import OperationInfo

    mock_operation = OperationInfo(
        operation_id="test_training_id",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        metadata=OperationMetadata(),
        progress=OperationProgress(),
    )

    operations_service.create_operation.return_value = mock_operation
    operations_service.start_operation.return_value = None
    operations_service.update_progress.return_value = None
    operations_service.complete_operation.return_value = None
    operations_service.fail_operation.return_value = None
    return operations_service


@pytest.fixture
def training_service(mock_operations_service):
    """Instantiate TrainingService with patched dependencies."""
    adapter_mock = MagicMock()
    adapter_mock.use_host_service = False

    training_manager_mock = MagicMock()
    training_manager_mock.training_adapter = adapter_mock
    training_manager_mock.is_using_host_service.return_value = False

    with (
        patch("ktrdr.api.services.training_service.ModelStorage"),
        patch("ktrdr.api.services.training_service.ModelLoader"),
        patch(
            "ktrdr.api.services.training_service.TrainingManager",
            return_value=training_manager_mock,
        ),
        patch(
            "ktrdr.api.services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ),
    ):
        service = TrainingService()

    # Inject mock manager for downstream calls (cancel, etc.)
    service.training_manager = training_manager_mock
    return service


def make_context(**overrides) -> TrainingOperationContext:
    """Utility to produce a populated TrainingOperationContext for tests."""
    metadata = OperationMetadata(
        symbol="AAPL",
        timeframe="1h",
        mode="training",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        parameters={
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
            "training_type": "mlp",
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "epochs": 25,
            "use_host_service": False,
            "analytics_enabled": False,
            "training_mode": "local",
        },
    )

    base = TrainingOperationContext(
        operation_id=None,
        strategy_name="test_strategy",
        strategy_path=Path("/tmp/test_strategy.yaml"),
        strategy_config={"model": {"training": {"epochs": 25}}},
        symbols=["AAPL"],
        timeframes=["1h"],
        start_date="2024-01-01",
        end_date="2024-06-01",
        training_config={"epochs": 25, "estimated_duration_minutes": 45},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=25,
        total_batches=None,
        metadata=metadata,
    )

    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestTrainingService:
    """Test TrainingService behaviour with orchestrator."""

    @pytest.mark.asyncio
    async def test_start_training_success(self, training_service):
        """start_training should invoke orchestrator and return legacy payload."""
        context = make_context()

        with (
            patch(
                "ktrdr.api.services.training_service.build_training_context",
                return_value=context,
            ) as mock_builder,
            patch.object(
                TrainingService, "start_managed_operation", new_callable=AsyncMock
            ) as mock_start_op,
        ):
            mock_start_op.return_value = {
                "operation_id": "op_training_123",
                "status": "started",
                "message": "Started training operation",
            }

            result = await training_service.start_training(
                symbols=["AAPL"],
                timeframes=["1h"],
                strategy_name="test_strategy",
                start_date="2024-01-01",
                end_date="2024-06-01",
            )

        mock_builder.assert_called_once()
        builder_kwargs = mock_builder.call_args.kwargs
        assert builder_kwargs["operation_id"] is None
        assert builder_kwargs["use_host_service"] is False

        mock_start_op.assert_awaited_once()
        call_kwargs = mock_start_op.call_args.kwargs
        assert call_kwargs["operation_name"] == "training"
        assert call_kwargs["operation_type"] == OperationType.TRAINING.value
        assert (
            call_kwargs["operation_func"]
            == training_service._legacy_operation_entrypoint
        )
        assert call_kwargs["context"] is context
        assert call_kwargs["metadata"] == context.metadata
        assert call_kwargs["total_steps"] == context.total_steps

        assert result["success"] is True
        assert result["task_id"] == "op_training_123"
        assert result["status"] == "training_started"
        assert result["symbols"] == ["AAPL"]
        assert result["strategy_name"] == "test_strategy"
        assert result["estimated_duration_minutes"] == 45
        assert "Neural network training started" in result["message"]

        # Context should record the assigned operation id for downstream calls
        assert context.operation_id == "op_training_123"

    @pytest.mark.asyncio
    async def test_start_training_with_custom_task_id(self, training_service):
        """Provided task_id should feed into context builder."""
        context = make_context()

        with (
            patch(
                "ktrdr.api.services.training_service.build_training_context",
                return_value=context,
            ) as mock_builder,
            patch.object(
                TrainingService, "start_managed_operation", new_callable=AsyncMock
            ) as mock_start_op,
        ):
            mock_start_op.return_value = {
                "operation_id": "op_training_456",
                "status": "started",
                "message": "Started training operation",
            }

            await training_service.start_training(
                symbols=["MSFT"],
                timeframes=["1d"],
                strategy_name="test_strategy",
                task_id="custom_id",
            )

        builder_kwargs = mock_builder.call_args.kwargs
        assert builder_kwargs["operation_id"] == "custom_id"
        assert builder_kwargs["symbols"] == ["MSFT"]
        assert builder_kwargs["timeframes"] == ["1d"]

    @pytest.mark.asyncio
    async def test_get_model_performance_success(
        self, training_service, mock_operations_service
    ):
        """Retrieving model performance should mirror legacy behaviour."""
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
                "model_size_bytes": 15952435,
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
        assert performance["model_info"]["model_size_bytes"] == 15952435

    @pytest.mark.asyncio
    async def test_get_model_performance_not_completed(
        self, training_service, mock_operations_service
    ):
        """Non-completed operations should raise ValidationError."""
        mock_operation = MagicMock()
        mock_operation.status.value = "running"

        mock_operations_service.get_operation.return_value = mock_operation

        with pytest.raises(ValidationError, match="not completed"):
            await training_service.get_model_performance("running_training_id")

    @pytest.mark.asyncio
    async def test_save_trained_model_success(
        self, training_service, mock_operations_service
    ):
        """Saving trained model should behave like legacy implementation."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {"model_path": "/tmp/test_model.pth"}

        mock_operations_service.get_operation.return_value = mock_operation

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 10 * 1024 * 1024
            result = await training_service.save_trained_model(
                "completed_training_id", "test_model"
            )

        assert result["success"] is True
        assert result["model_name"] == "test_model"
        assert result["model_size_mb"] == pytest.approx(10.0, rel=1e-3)

    @pytest.mark.asyncio
    async def test_save_trained_model_missing_file(
        self, training_service, mock_operations_service
    ):
        """Missing model artifacts should raise validation error."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {"model_path": "/tmp/missing_model.pth"}
        mock_operations_service.get_operation.return_value = mock_operation

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValidationError, match="Trained model file not found"):
                await training_service.save_trained_model(
                    "completed_training_id", "missing_model"
                )
