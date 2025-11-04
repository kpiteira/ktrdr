"""Unit tests for operations service metrics functionality (M2)."""

import pytest
import pytest_asyncio

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.operations_service import OperationsService

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def operations_service():
    """Create operations service for testing."""
    return OperationsService()


@pytest_asyncio.fixture
async def training_operation(operations_service):
    """Create a training operation for testing."""
    metadata = OperationMetadata(
        description="Test training operation", user="test", tags=["test"]
    )
    operation = await operations_service.create_operation(
        operation_type=OperationType.TRAINING, metadata=metadata
    )
    return operation


class TestAddMetrics:
    """Test adding metrics to operations."""

    async def test_add_metrics_initializes_training_structure(
        self, operations_service, training_operation
    ):
        """Test that add_metrics initializes training metrics structure."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding first epoch metrics
        epoch_metrics = {
            "epoch": 0,
            "train_loss": 0.8234,
            "train_accuracy": 0.65,
            "val_loss": 0.8912,
            "val_accuracy": 0.58,
            "learning_rate": 0.001,
            "duration": 12.5,
            "timestamp": "2025-01-17T10:00:00Z",
        }
        await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then metrics structure should be initialized
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics is not None
        assert "epochs" in operation.metrics
        assert isinstance(operation.metrics["epochs"], list)
        assert len(operation.metrics["epochs"]) == 1
        assert operation.metrics["epochs"][0] == epoch_metrics

    async def test_add_metrics_appends_multiple_epochs(
        self, operations_service, training_operation
    ):
        """Test that add_metrics appends multiple epochs."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding multiple epoch metrics
        for epoch in range(5):
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.8 - (epoch * 0.1),
                "train_accuracy": 0.6 + (epoch * 0.05),
                "val_loss": 0.85 - (epoch * 0.08),
                "val_accuracy": 0.55 + (epoch * 0.04),
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then all epochs should be stored
        operation = await operations_service.get_operation(operation_id)
        assert len(operation.metrics["epochs"]) == 5
        assert operation.metrics["epochs"][0]["epoch"] == 0
        assert operation.metrics["epochs"][4]["epoch"] == 4

    async def test_add_metrics_updates_epochs_completed(
        self, operations_service, training_operation
    ):
        """Test that add_metrics updates total_epochs_completed."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding 3 epochs
        for epoch in range(3):
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.8,
                "train_accuracy": 0.6,
                "val_loss": 0.85,
                "val_accuracy": 0.55,
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then total_epochs_completed should be 3
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["total_epochs_completed"] == 3

    async def test_add_metrics_raises_error_for_nonexistent_operation(
        self, operations_service
    ):
        """Test that add_metrics raises error for non-existent operation."""
        # Given a non-existent operation ID
        operation_id = "op-nonexistent"

        # When adding metrics
        epoch_metrics = {"epoch": 0, "train_loss": 0.8}

        # Then should raise KeyError
        with pytest.raises(KeyError, match="Operation not found"):
            await operations_service.add_metrics(operation_id, epoch_metrics)


class TestTrainingMetricsTrendAnalysis:
    """Test trend analysis computations."""

    async def test_best_epoch_tracking(self, operations_service, training_operation):
        """Test that best epoch is tracked correctly."""
        # Given a training operation with varying val_loss
        operation_id = training_operation.operation_id

        # When adding epochs with decreasing then increasing val_loss
        val_losses = [0.9, 0.75, 0.6, 0.55, 0.58, 0.62]  # Best at epoch 3
        for epoch, val_loss in enumerate(val_losses):
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.7,
                "train_accuracy": 0.7,
                "val_loss": val_loss,
                "val_accuracy": 0.65,
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then best_epoch should be 3 and epochs_since_improvement should be 2
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["best_epoch"] == 3
        assert operation.metrics["best_val_loss"] == 0.55
        assert operation.metrics["epochs_since_improvement"] == 2

    async def test_overfitting_detection(self, operations_service, training_operation):
        """Test overfitting detection (train_loss↓ while val_loss↑)."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding 10 epochs showing clear overfitting pattern
        for epoch in range(10):
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.8 - (epoch * 0.05),  # Decreasing
                "train_accuracy": 0.6 + (epoch * 0.03),
                "val_loss": 0.75 + (epoch * 0.04),  # Increasing
                "val_accuracy": 0.65 - (epoch * 0.01),
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then is_overfitting should be True
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["is_overfitting"] is True

    async def test_no_overfitting_when_both_improving(
        self, operations_service, training_operation
    ):
        """Test that overfitting is not detected when both losses improve."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding 10 epochs with both losses decreasing
        for epoch in range(10):
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.8 - (epoch * 0.05),  # Decreasing
                "train_accuracy": 0.6 + (epoch * 0.03),
                "val_loss": 0.85 - (epoch * 0.04),  # Also decreasing
                "val_accuracy": 0.55 + (epoch * 0.02),
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then is_overfitting should be False
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["is_overfitting"] is False

    async def test_plateau_detection(self, operations_service, training_operation):
        """Test plateau detection (no improvement for N epochs)."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding epochs with no improvement after epoch 2
        for epoch in range(15):
            val_loss = 0.6 if epoch < 3 else 0.65  # Best at epoch 2, no improvement
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.7,
                "train_accuracy": 0.7,
                "val_loss": val_loss,
                "val_accuracy": 0.65,
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then is_plateaued should be True (>= 10 epochs without improvement)
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["is_plateaued"] is True
        assert operation.metrics["epochs_since_improvement"] >= 10

    async def test_no_plateau_with_recent_improvement(
        self, operations_service, training_operation
    ):
        """Test that plateau is not detected with recent improvement."""
        # Given a training operation
        operation_id = training_operation.operation_id

        # When adding 8 epochs with best at the end
        for epoch in range(8):
            val_loss = 0.8 - (epoch * 0.05)  # Continuously improving
            epoch_metrics = {
                "epoch": epoch,
                "train_loss": 0.7,
                "train_accuracy": 0.7,
                "val_loss": val_loss,
                "val_accuracy": 0.65,
                "learning_rate": 0.001,
                "duration": 12.0,
                "timestamp": f"2025-01-17T10:{epoch:02d}:00Z",
            }
            await operations_service.add_metrics(operation_id, epoch_metrics)

        # Then is_plateaued should be False
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics["is_plateaued"] is False


class TestGenericMetricsHandling:
    """Test that metrics handling works for all operation types (Phase 0, Task 0.2)."""

    async def test_refresh_from_bridge_handles_backtesting_metrics(
        self, operations_service
    ):
        """Test that _refresh_from_bridge handles BACKTESTING operation type correctly."""
        from unittest.mock import MagicMock

        # Given a backtesting operation
        metadata = OperationMetadata(description="Test backtest", user="test")
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Create a mock bridge for backtesting
        mock_bridge = MagicMock()
        mock_bridge.get_status.return_value = {
            "percentage": 50.0,
            "message": "Backtesting AAPL 1h",
            "current_step": 500,
            "total_steps": 1000,
        }
        # Backtesting metrics should be bar-level data
        bar_metrics = [
            {"bar": 450, "pnl": 1500.0, "trades": 5},
            {"bar": 500, "pnl": 1750.0, "trades": 6},
        ]
        mock_bridge.get_metrics.return_value = (bar_metrics, 2)

        # Register the mock bridge
        operations_service._local_bridges[operation_id] = mock_bridge
        operations_service._metrics_cursors[operation_id] = 0

        # When refreshing from bridge
        operations_service._refresh_from_bridge(operation_id)

        # Then metrics should be stored in "bars" key (not "epochs")
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics is not None
        assert "bars" in operation.metrics
        assert len(operation.metrics["bars"]) == 2
        assert operation.metrics["bars"][0]["bar"] == 450
        assert operation.metrics["bars"][1]["pnl"] == 1750.0

    async def test_refresh_from_bridge_handles_data_load_metrics(
        self, operations_service
    ):
        """Test that _refresh_from_bridge handles DATA_LOAD operation type correctly."""
        from unittest.mock import MagicMock

        # Given a data loading operation
        metadata = OperationMetadata(description="Test data load", user="test")
        operation = await operations_service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )
        operation_id = operation.operation_id

        # Create a mock bridge for data loading
        mock_bridge = MagicMock()
        mock_bridge.get_status.return_value = {
            "percentage": 75.0,
            "message": "Loading AAPL 1h data",
            "current_step": 75,
            "total_steps": 100,
        }
        # Data loading metrics should be segment-level data
        segment_metrics = [
            {"segment": "2024-01-01_2024-03-01", "bars": 1000},
            {"segment": "2024-03-01_2024-06-01", "bars": 1200},
        ]
        mock_bridge.get_metrics.return_value = (segment_metrics, 2)

        # Register the mock bridge
        operations_service._local_bridges[operation_id] = mock_bridge
        operations_service._metrics_cursors[operation_id] = 0

        # When refreshing from bridge
        operations_service._refresh_from_bridge(operation_id)

        # Then metrics should be stored in "segments" key
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics is not None
        assert "segments" in operation.metrics
        assert len(operation.metrics["segments"]) == 2
        assert operation.metrics["segments"][0]["segment"] == "2024-01-01_2024-03-01"

    async def test_refresh_from_bridge_handles_unknown_operation_type(
        self, operations_service
    ):
        """Test that _refresh_from_bridge handles unknown operation types with fallback."""
        from unittest.mock import MagicMock

        # Given a dummy operation (generic type)
        metadata = OperationMetadata(description="Test dummy op", user="test")
        operation = await operations_service.create_operation(
            operation_type=OperationType.DUMMY, metadata=metadata
        )
        operation_id = operation.operation_id

        # Create a mock bridge
        mock_bridge = MagicMock()
        mock_bridge.get_status.return_value = {
            "percentage": 30.0,
            "message": "Running dummy task",
        }
        generic_metrics = [{"iteration": 1, "value": 42}, {"iteration": 2, "value": 43}]
        mock_bridge.get_metrics.return_value = (generic_metrics, 2)

        # Register the mock bridge
        operations_service._local_bridges[operation_id] = mock_bridge
        operations_service._metrics_cursors[operation_id] = 0

        # When refreshing from bridge
        operations_service._refresh_from_bridge(operation_id)

        # Then metrics should be stored in generic "history" key
        operation = await operations_service.get_operation(operation_id)
        assert operation.metrics is not None
        assert "history" in operation.metrics
        assert len(operation.metrics["history"]) == 2
