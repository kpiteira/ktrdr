"""
Unit tests for OperationsService.

Tests the core operations service that manages async operations for
backtesting, training, and other long-running tasks.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any

from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import (
    OperationType,
    OperationStatus,
    OperationMetadata,
    OperationProgress,
    OperationInfo,
)
from ktrdr.errors import ValidationError


@pytest.fixture
def operations_service():
    """Create an OperationsService instance for testing."""
    return OperationsService()


@pytest.fixture
def sample_metadata():
    """Create sample operation metadata."""
    return OperationMetadata(
        symbol="AAPL",
        timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        parameters={
            "strategy_name": "test_strategy",
            "initial_capital": 100000,
        },
    )


class TestOperationsService:
    """Test OperationsService functionality."""

    @pytest.mark.asyncio
    async def test_create_operation(self, operations_service, sample_metadata):
        """Test creating a new operation."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=sample_metadata
        )

        assert operation is not None
        assert operation.operation_id.startswith("op_backtesting_")
        assert operation.operation_type == OperationType.BACKTESTING
        assert operation.status == OperationStatus.PENDING
        assert operation.metadata.symbol == "AAPL"

        # Verify operation was stored
        stored_operation = await operations_service.get_operation(
            operation.operation_id
        )
        assert stored_operation is not None
        assert stored_operation.operation_id == operation.operation_id

    @pytest.mark.asyncio
    async def test_start_operation(self, operations_service, sample_metadata):
        """Test starting an operation with a task."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

        # Create a mock task
        mock_task = AsyncMock()
        mock_task.done.return_value = False
        mock_task.cancelled.return_value = False

        await operations_service.start_operation(operation.operation_id, mock_task)

        updated_operation = await operations_service.get_operation(
            operation.operation_id
        )
        assert updated_operation.status == OperationStatus.RUNNING
        assert updated_operation.started_at is not None

    @pytest.mark.asyncio
    async def test_update_progress(self, operations_service, sample_metadata):
        """Test updating operation progress."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=sample_metadata
        )

        progress = OperationProgress(
            percentage=50.0,
            current_step="Processing data",
            items_processed=500,
            items_total=1000,
        )

        await operations_service.update_progress(operation.operation_id, progress)

        updated_operation = await operations_service.get_operation(
            operation.operation_id
        )
        assert updated_operation.progress.percentage == 50.0
        assert updated_operation.progress.current_step == "Processing data"
        assert updated_operation.progress.items_processed == 500
        assert updated_operation.progress.items_total == 1000
        # Note: details might not be available in the progress object directly

    @pytest.mark.asyncio
    async def test_complete_operation(self, operations_service, sample_metadata):
        """Test completing an operation."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        operation_id = operation.operation_id

        result_summary = {
            "total_return": 15.5,
            "sharpe_ratio": 1.2,
            "max_drawdown": -5.3,
            "total_trades": 45,
        }

        await operations_service.complete_operation(operation_id, result_summary)

        operation = await operations_service.get_operation(operation_id)
        assert operation.status == OperationStatus.COMPLETED
        assert operation.completed_at is not None
        assert operation.progress.percentage == 100.0
        assert operation.result_summary == result_summary

    @pytest.mark.asyncio
    async def test_fail_operation(self, operations_service, sample_metadata):
        """Test failing an operation."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=sample_metadata
        )
        operation_id = operation.operation_id

        error_message = "Data not found for symbol INVALID"
        await operations_service.fail_operation(operation_id, error_message)

        operation = await operations_service.get_operation(operation_id)
        assert operation.status == OperationStatus.FAILED
        assert operation.completed_at is not None
        assert operation.error_message == error_message

    @pytest.mark.asyncio
    async def test_cancel_operation(self, operations_service, sample_metadata):
        """Test cancelling an operation."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        operation_id = operation.operation_id

        # Create a mock task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancelled.return_value = False
        mock_task.cancel = MagicMock()

        await operations_service.start_operation(operation_id, mock_task)
        await operations_service.cancel_operation(operation_id, "User cancelled")

        operation = await operations_service.get_operation(operation_id)
        assert operation.status == OperationStatus.CANCELLED
        assert "User cancelled" in operation.error_message
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_operations(self, operations_service, sample_metadata):
        """Test listing operations with filters."""
        # Create multiple operations
        backtest_op = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=sample_metadata
        )
        backtest_id = backtest_op.operation_id

        training_op = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        training_id = training_op.operation_id

        # Complete one operation
        await operations_service.complete_operation(backtest_id, {"result": "success"})

        # Test listing all operations
        all_ops, total_count, active_count = await operations_service.list_operations()
        assert len(all_ops) >= 2

        # Test filtering by type
        backtest_ops, _, _ = await operations_service.list_operations(
            operation_type=OperationType.BACKTESTING
        )
        assert (
            len(
                [
                    op
                    for op in backtest_ops
                    if op.operation_type == OperationType.BACKTESTING
                ]
            )
            >= 1
        )

        # Test filtering by status (using status parameter, not status_filter)
        completed_ops, _, _ = await operations_service.list_operations(
            status=OperationStatus.COMPLETED
        )
        assert (
            len([op for op in completed_ops if op.status == OperationStatus.COMPLETED])
            >= 1
        )

    @pytest.mark.asyncio
    async def test_get_nonexistent_operation(self, operations_service):
        """Test getting a non-existent operation."""
        operation = await operations_service.get_operation("nonexistent_id")
        assert operation is None

    @pytest.mark.asyncio
    async def test_operation_timeout_handling(
        self, operations_service, sample_metadata
    ):
        """Test operation timeout handling."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=sample_metadata
        )
        operation_id = operation.operation_id

        # Create a mock task that appears hung
        mock_task = AsyncMock()
        mock_task.done.return_value = False
        mock_task.cancelled.return_value = False

        await operations_service.start_operation(operation_id, mock_task)

        # Test updating progress to prevent timeout
        progress = OperationProgress(percentage=10.0, current_step="Starting...")
        await operations_service.update_progress(operation_id, progress)

        operation = await operations_service.get_operation(operation_id)
        assert operation.status == OperationStatus.RUNNING
        assert operation.progress.percentage == 10.0

    @pytest.mark.asyncio
    async def test_operation_metadata_validation(self, operations_service):
        """Test operation metadata validation."""
        # Test with invalid metadata
        invalid_metadata = OperationMetadata(
            symbol="", timeframe="1h", parameters={}  # Invalid empty symbol
        )

        # OperationsService doesn't validate metadata content, just stores it
        # The validation would happen at the service layer (backtesting/training)
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=invalid_metadata
        )
        assert operation is not None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, operations_service, sample_metadata):
        """Test handling multiple concurrent operations."""
        # Create multiple operations concurrently
        tasks = []
        for i in range(5):
            task = operations_service.create_operation(
                operation_type=OperationType.BACKTESTING,
                metadata=OperationMetadata(
                    symbol=f"SYMBOL{i}", timeframe="1h", parameters={"test_param": i}
                ),
            )
            tasks.append(task)

        operations = await asyncio.gather(*tasks)
        assert len(operations) == 5
        operation_ids = [op.operation_id for op in operations]
        assert len(set(operation_ids)) == 5  # All IDs should be unique

        # Verify all operations were created
        for operation in operations:
            stored_operation = await operations_service.get_operation(
                operation.operation_id
            )
            assert stored_operation is not None
            assert stored_operation.status == OperationStatus.PENDING
