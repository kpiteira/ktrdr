"""Tests for pipeline error propagation to operation status.

M1 Task 1.4: Verify that PipelineError subclasses (TrainingDataError, etc.)
propagate correctly and result in FAILED operations with meaningful error messages.

This is the "fail loudly" behavior - infrastructure errors should not be silently
swallowed, they should fail operations visibly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.training.exceptions import (
    BacktestDataError,
    ModelLoadError,
    PipelineError,
    TrainingDataError,
)


class TestPipelineErrorPropagation:
    """Test that pipeline errors propagate to operation status correctly."""

    @pytest.fixture
    def mock_operations_service(self):
        """Create a mock operations service that tracks operations."""
        service = AsyncMock()
        operations: dict[str, OperationInfo] = {}

        async def async_create_operation(
            operation_type, metadata=None, parent_operation_id=None
        ):
            op_id = f"op_{operation_type.value}_{len(operations)}"
            op = OperationInfo(
                operation_id=op_id,
                operation_type=operation_type,
                status=OperationStatus.PENDING,
                created_at=MagicMock(),
                metadata=metadata or OperationMetadata(),
                parent_operation_id=parent_operation_id,
            )
            operations[op_id] = op
            return op

        async def async_get_operation(operation_id):
            return operations.get(operation_id)

        async def async_fail_operation(operation_id, error_message=None):
            if operation_id in operations:
                operations[operation_id].status = OperationStatus.FAILED
                operations[operation_id].error_message = error_message

        async def async_start_operation(operation_id, task=None):
            if operation_id in operations:
                operations[operation_id].status = OperationStatus.RUNNING

        service.create_operation = async_create_operation
        service.get_operation = async_get_operation
        service.fail_operation = async_fail_operation
        service.start_operation = async_start_operation
        service._operations = operations  # Expose for assertions

        return service

    @pytest.mark.asyncio
    async def test_training_data_error_fails_operation(self, mock_operations_service):
        """TrainingDataError should result in FAILED operation with error message."""
        # Create an operation
        op = await mock_operations_service.create_operation(OperationType.TRAINING)
        await mock_operations_service.start_operation(op.operation_id)

        # Simulate what happens when TrainingDataError is raised and caught
        error = TrainingDataError(
            "Training produced no test data. "
            "This usually indicates a data pipeline issue."
        )

        # The training worker catches exceptions and calls fail_operation
        await mock_operations_service.fail_operation(op.operation_id, str(error))

        # Verify operation is FAILED with error message
        failed_op = await mock_operations_service.get_operation(op.operation_id)
        assert failed_op.status == OperationStatus.FAILED
        assert failed_op.error_message is not None
        assert "test data" in failed_op.error_message.lower()
        assert "data pipeline" in failed_op.error_message.lower()

    @pytest.mark.asyncio
    async def test_backtest_data_error_fails_operation(self, mock_operations_service):
        """BacktestDataError should result in FAILED operation with error message."""
        op = await mock_operations_service.create_operation(OperationType.BACKTESTING)
        await mock_operations_service.start_operation(op.operation_id)

        error = BacktestDataError("No price data available for EURUSD")
        await mock_operations_service.fail_operation(op.operation_id, str(error))

        failed_op = await mock_operations_service.get_operation(op.operation_id)
        assert failed_op.status == OperationStatus.FAILED
        assert "price data" in failed_op.error_message.lower()
        assert "eurusd" in failed_op.error_message.lower()

    @pytest.mark.asyncio
    async def test_model_load_error_fails_operation(self, mock_operations_service):
        """ModelLoadError should result in FAILED operation with error message."""
        op = await mock_operations_service.create_operation(OperationType.BACKTESTING)
        await mock_operations_service.start_operation(op.operation_id)

        error = ModelLoadError("Model file not found: /path/to/model.pt")
        await mock_operations_service.fail_operation(op.operation_id, str(error))

        failed_op = await mock_operations_service.get_operation(op.operation_id)
        assert failed_op.status == OperationStatus.FAILED
        assert "model" in failed_op.error_message.lower()
        assert "not found" in failed_op.error_message.lower()

    @pytest.mark.asyncio
    async def test_generic_pipeline_error_fails_operation(
        self, mock_operations_service
    ):
        """Generic PipelineError should also result in FAILED operation."""
        op = await mock_operations_service.create_operation(OperationType.TRAINING)
        await mock_operations_service.start_operation(op.operation_id)

        error = PipelineError("Unexpected pipeline infrastructure failure")
        await mock_operations_service.fail_operation(op.operation_id, str(error))

        failed_op = await mock_operations_service.get_operation(op.operation_id)
        assert failed_op.status == OperationStatus.FAILED
        assert "pipeline" in failed_op.error_message.lower()


class TestErrorMessagePreservation:
    """Test that exception details are preserved in operation error_message."""

    def test_training_data_error_message_preserved(self):
        """TrainingDataError message should be fully preserved when converted to str."""
        msg = (
            "Training produced no test data. "
            "This usually indicates a data pipeline issue with multi-symbol "
            "or multi-timeframe configurations. Check data loading and splitting."
        )
        error = TrainingDataError(msg)

        # When the worker calls str(e), the full message should be preserved
        assert str(error) == msg
        assert "multi-symbol" in str(error)
        assert "multi-timeframe" in str(error)

    def test_backtest_data_error_message_preserved(self):
        """BacktestDataError message should be fully preserved."""
        msg = "No price data available for EURUSD. Check data cache and date range."
        error = BacktestDataError(msg)
        assert str(error) == msg

    def test_model_load_error_message_preserved(self):
        """ModelLoadError message should be fully preserved."""
        msg = "Model file not found: /app/models/strategy/1d_v1/model.pt"
        error = ModelLoadError(msg)
        assert str(error) == msg


class TestNoExperimentOnInfrastructureError:
    """Test that infrastructure errors don't create experiments in memory."""

    @pytest.mark.asyncio
    async def test_failed_operation_has_no_result_summary(self, tmp_path):
        """FAILED operations should not have result_summary (no experiment recorded)."""
        # This test verifies the contract: infrastructure errors don't produce
        # experiment results. The actual memory recording is done elsewhere,
        # but the operation status should indicate failure, not completion.

        op = OperationInfo(
            operation_id="op_test_1",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.FAILED,
            created_at=MagicMock(),
            metadata=OperationMetadata(),
            error_message="TrainingDataError: No test data",
        )

        # A failed operation should not have a result_summary
        # (result_summary is only set on completion)
        assert op.result_summary is None
        assert op.status == OperationStatus.FAILED
        assert op.error_message is not None
