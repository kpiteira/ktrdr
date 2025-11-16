"""
Unit tests for OperationsService.resume_operation() functionality.

Tests cover:
- Happy path: Resume FAILED/CANCELLED operations
- Error cases: Invalid status, missing checkpoint, corrupted checkpoint
- Edge cases: New operation creation, original checkpoint deletion
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def operations_service():
    """Create OperationsService instance for testing."""
    return OperationsService()


@pytest.fixture
def failed_operation():
    """Create a FAILED operation for testing."""
    return OperationInfo(
        operation_id="op_training_001",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.FAILED,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        progress=OperationProgress(percentage=45.0, current_step="Epoch 45/100"),
        metadata=OperationMetadata(
            symbol="AAPL",
            timeframe="1d",
            parameters={"strategy": "test_strategy"},
        ),
        error="Out of memory at epoch 45",
    )


@pytest.fixture
def cancelled_operation():
    """Create a CANCELLED operation for testing."""
    return OperationInfo(
        operation_id="op_training_002",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.CANCELLED,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        progress=OperationProgress(percentage=30.0, current_step="Epoch 30/100"),
        metadata=OperationMetadata(
            symbol="EURUSD",
            timeframe="1h",
            parameters={"strategy": "test_strategy"},
        ),
    )


@pytest.fixture
def running_operation():
    """Create a RUNNING operation (not resumable)."""
    return OperationInfo(
        operation_id="op_training_003",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        progress=OperationProgress(percentage=50.0, current_step="Epoch 50/100"),
        metadata=OperationMetadata(
            symbol="BTCUSD",
            timeframe="1d",
            parameters={"strategy": "test_strategy"},
        ),
    )


@pytest.fixture
def mock_checkpoint_state():
    """Create mock checkpoint state."""
    return {
        "checkpoint_version": "1.0",
        "ktrdr_version": "0.5.0",
        "checkpoint_type": "epoch_snapshot",
        "created_at": "2025-01-17T12:00:00Z",
        "epoch": 45,
        "total_epochs": 100,
        "config": {
            "strategy": "test_strategy",
            "learning_rate": 0.001,
        },
        "artifacts": {
            "model_state_dict": "path/to/model.pt",
            "optimizer_state_dict": "path/to/optimizer.pt",
        },
    }


class TestResumeOperationHappyPath:
    """Test successful resume operation scenarios."""

    @pytest.mark.asyncio
    async def test_resume_failed_operation_success(
        self, operations_service, failed_operation, mock_checkpoint_state
    ):
        """Test resuming a FAILED operation successfully."""
        # Setup: Mock get_operation to return failed operation
        with patch.object(
            operations_service, "get_operation", return_value=failed_operation
        ):
            # Mock CheckpointService.load_checkpoint
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = (
                    mock_checkpoint_state
                )
                mock_get_checkpoint.return_value = mock_checkpoint_service

                # Mock TrainingService.resume_training
                with patch(
                    "ktrdr.api.services.operations_service.get_training_service"
                ) as mock_get_training:
                    mock_training_service = AsyncMock()
                    mock_training_service.resume_training.return_value = {
                        "success": True,
                        "result": "training_resumed",
                    }
                    mock_get_training.return_value = mock_training_service

                    # Mock create_operation
                    with patch.object(
                        operations_service, "create_operation"
                    ) as mock_create:
                        new_operation = OperationInfo(
                            operation_id="op_training_new_001",
                            operation_type=OperationType.TRAINING,
                            status=OperationStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            progress=OperationProgress(),
                            metadata=failed_operation.metadata,
                        )
                        mock_create.return_value = new_operation

                        # Execute: Resume operation
                        result = await operations_service.resume_operation(
                            "op_training_001"
                        )

                        # Assert: Check result structure
                        assert result["success"] is True
                        assert result["original_operation_id"] == "op_training_001"
                        assert result["new_operation_id"] == "op_training_new_001"
                        assert "resumed_from_checkpoint" in result

                        # Assert: CheckpointService.load_checkpoint was called
                        mock_checkpoint_service.load_checkpoint.assert_called_once_with(
                            "op_training_001"
                        )

                        # Assert: CheckpointService.delete_checkpoint was called
                        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
                            "op_training_001"
                        )

                        # Assert: TrainingService.resume_training was called
                        mock_training_service.resume_training.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_cancelled_operation_success(
        self, operations_service, cancelled_operation, mock_checkpoint_state
    ):
        """Test resuming a CANCELLED operation successfully."""
        # Setup: Mock get_operation to return cancelled operation
        with patch.object(
            operations_service, "get_operation", return_value=cancelled_operation
        ):
            # Mock CheckpointService.load_checkpoint
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = (
                    mock_checkpoint_state
                )
                mock_get_checkpoint.return_value = mock_checkpoint_service

                # Mock TrainingService.resume_training
                with patch(
                    "ktrdr.api.services.operations_service.get_training_service"
                ) as mock_get_training:
                    mock_training_service = AsyncMock()
                    mock_training_service.resume_training.return_value = {
                        "success": True
                    }
                    mock_get_training.return_value = mock_training_service

                    # Mock create_operation
                    with patch.object(
                        operations_service, "create_operation"
                    ) as mock_create:
                        new_operation = OperationInfo(
                            operation_id="op_training_new_002",
                            operation_type=OperationType.TRAINING,
                            status=OperationStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            progress=OperationProgress(),
                            metadata=cancelled_operation.metadata,
                        )
                        mock_create.return_value = new_operation

                        # Execute: Resume operation
                        result = await operations_service.resume_operation(
                            "op_training_002"
                        )

                        # Assert: Success
                        assert result["success"] is True
                        assert result["original_operation_id"] == "op_training_002"


class TestResumeOperationValidation:
    """Test validation and error cases."""

    @pytest.mark.asyncio
    async def test_resume_operation_not_found(self, operations_service):
        """Test resume fails when operation doesn't exist."""
        # Setup: Mock get_operation to return None
        with patch.object(operations_service, "get_operation", return_value=None):
            # Execute & Assert: Should raise ValueError
            with pytest.raises(ValueError, match="Operation not found"):
                await operations_service.resume_operation("op_nonexistent")

    @pytest.mark.asyncio
    async def test_resume_running_operation_fails(
        self, operations_service, running_operation
    ):
        """Test resume fails for RUNNING operation."""
        # Setup: Mock get_operation to return running operation
        with patch.object(
            operations_service, "get_operation", return_value=running_operation
        ):
            # Execute & Assert: Should raise ValueError
            with pytest.raises(
                ValueError,
                match="Cannot resume.*Only FAILED or CANCELLED operations can be resumed",
            ):
                await operations_service.resume_operation("op_training_003")

    @pytest.mark.asyncio
    async def test_resume_completed_operation_fails(self, operations_service):
        """Test resume fails for COMPLETED operation."""
        # Setup: Create completed operation
        completed_op = OperationInfo(
            operation_id="op_training_004",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            progress=OperationProgress(percentage=100.0),
            metadata=OperationMetadata(),
        )

        with patch.object(
            operations_service, "get_operation", return_value=completed_op
        ):
            # Execute & Assert: Should raise ValueError
            with pytest.raises(ValueError, match="Cannot resume"):
                await operations_service.resume_operation("op_training_004")

    @pytest.mark.asyncio
    async def test_resume_no_checkpoint_found(
        self, operations_service, failed_operation
    ):
        """Test resume fails when no checkpoint exists."""
        # Setup: Mock get_operation to return failed operation
        with patch.object(
            operations_service, "get_operation", return_value=failed_operation
        ):
            # Mock CheckpointService.load_checkpoint to return None
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = None
                mock_get_checkpoint.return_value = mock_checkpoint_service

                # Execute & Assert: Should raise ValueError
                with pytest.raises(ValueError, match="No checkpoint found"):
                    await operations_service.resume_operation("op_training_001")


class TestResumeOperationDispatch:
    """Test dispatch to appropriate service based on operation type."""

    @pytest.mark.asyncio
    async def test_resume_dispatches_to_backtesting_service(
        self, operations_service, mock_checkpoint_state
    ):
        """Test resume dispatches to BacktestingService for backtesting operations."""
        # Setup: Create failed backtesting operation
        backtest_op = OperationInfo(
            operation_id="op_backtest_001",
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.FAILED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            progress=OperationProgress(percentage=50.0),
            metadata=OperationMetadata(symbol="AAPL", timeframe="1h"),
        )

        with patch.object(
            operations_service, "get_operation", return_value=backtest_op
        ):
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = (
                    mock_checkpoint_state
                )
                mock_get_checkpoint.return_value = mock_checkpoint_service

                # Mock BacktestingService.resume_backtest
                with patch(
                    "ktrdr.api.services.operations_service.get_backtesting_service"
                ) as mock_get_backtest:
                    mock_backtest_service = AsyncMock()
                    mock_backtest_service.resume_backtest.return_value = {
                        "success": True
                    }
                    mock_get_backtest.return_value = mock_backtest_service

                    with patch.object(
                        operations_service, "create_operation"
                    ) as mock_create:
                        new_operation = OperationInfo(
                            operation_id="op_backtest_new_001",
                            operation_type=OperationType.BACKTESTING,
                            status=OperationStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            progress=OperationProgress(),
                            metadata=backtest_op.metadata,
                        )
                        mock_create.return_value = new_operation

                        # Execute: Resume operation
                        result = await operations_service.resume_operation(
                            "op_backtest_001"
                        )

                        # Assert: BacktestingService.resume_backtest was called
                        mock_backtest_service.resume_backtest.assert_called_once()
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_resume_unsupported_operation_type_fails(
        self, operations_service, mock_checkpoint_state
    ):
        """Test resume fails for unsupported operation types."""
        # Setup: Create failed data load operation (not supported for resume)
        data_op = OperationInfo(
            operation_id="op_data_001",
            operation_type=OperationType.DATA_LOAD,
            status=OperationStatus.FAILED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            progress=OperationProgress(percentage=50.0),
            metadata=OperationMetadata(symbol="AAPL", timeframe="1h"),
        )

        with patch.object(operations_service, "get_operation", return_value=data_op):
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = (
                    mock_checkpoint_state
                )
                mock_get_checkpoint.return_value = mock_checkpoint_service

                # Execute & Assert: Should raise ValueError
                with pytest.raises(
                    ValueError, match="Resume not supported for operation type"
                ):
                    await operations_service.resume_operation("op_data_001")


class TestResumeOperationNewOperationCreation:
    """Test that resume creates a new operation with correct metadata."""

    @pytest.mark.asyncio
    async def test_new_operation_has_resumed_from_link(
        self, operations_service, failed_operation, mock_checkpoint_state
    ):
        """Test that new operation has 'resumed_from' link to original."""
        # Setup: Mock get_operation
        with patch.object(
            operations_service, "get_operation", return_value=failed_operation
        ):
            with patch(
                "ktrdr.api.services.operations_service.get_checkpoint_service"
            ) as mock_get_checkpoint:
                mock_checkpoint_service = MagicMock()
                mock_checkpoint_service.load_checkpoint.return_value = (
                    mock_checkpoint_state
                )
                mock_get_checkpoint.return_value = mock_checkpoint_service

                with patch(
                    "ktrdr.api.services.operations_service.get_training_service"
                ) as mock_get_training:
                    mock_training_service = AsyncMock()
                    mock_training_service.resume_training.return_value = {
                        "success": True
                    }
                    mock_get_training.return_value = mock_training_service

                    # Mock create_operation to capture call arguments
                    with patch.object(
                        operations_service, "create_operation"
                    ) as mock_create:
                        new_operation = OperationInfo(
                            operation_id="op_training_new_001",
                            operation_type=OperationType.TRAINING,
                            status=OperationStatus.PENDING,
                            created_at=datetime.now(timezone.utc),
                            progress=OperationProgress(),
                            metadata=OperationMetadata(
                                parameters={"resumed_from": "op_training_001"}
                            ),
                        )
                        mock_create.return_value = new_operation

                        # Execute
                        await operations_service.resume_operation("op_training_001")

                        # Assert: create_operation was called with resumed_from
                        mock_create.assert_called_once()
                        call_args = mock_create.call_args
                        assert (
                            call_args.kwargs["metadata"].parameters["resumed_from"]
                            == "op_training_001"
                        )
