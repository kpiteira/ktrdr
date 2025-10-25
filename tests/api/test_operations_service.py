"""
Unit tests for OperationsService.

Tests the core operations service that manages async operations for
backtesting, training, and other long-running tasks.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


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

        await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

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
            symbol="",
            timeframe="1h",
            parameters={},  # Invalid empty symbol
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


class TestOperationsServiceBridgeRegistry:
    """Test bridge registry and pull-based refresh functionality (Task 1.3)."""

    @pytest.mark.asyncio
    async def test_register_local_bridge(self, operations_service, sample_metadata):
        """Test registering a local bridge for pull-based progress."""
        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

        # Create mock bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Verify bridge registered
        assert operation.operation_id in operations_service._local_bridges
        assert operations_service._local_bridges[operation.operation_id] is bridge

        # Verify cursor initialized to 0
        assert operation.operation_id in operations_service._metrics_cursors
        assert operations_service._metrics_cursors[operation.operation_id] == 0

    @pytest.mark.asyncio
    async def test_refresh_from_bridge_updates_operation(
        self, operations_service, sample_metadata
    ):
        """Test that _refresh_from_bridge() updates operation with bridge data."""
        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge with state
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(
            percentage=55.0,
            message="Epoch 55/100",
            current_step=55,
            items_processed=5500,
            epoch_index=55,
            total_epochs=100,
        )

        # Add some metrics
        bridge._append_metric(
            {
                "epoch": 54,
                "train_loss": 1.5,
                "val_loss": 1.7,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Refresh from bridge
        operations_service._refresh_from_bridge(operation.operation_id)

        # Verify operation updated
        updated_op = await operations_service.get_operation(operation.operation_id)
        assert updated_op.progress.percentage == 55.0
        assert (
            updated_op.progress.current_step == "Epoch 55/100"
        )  # message goes to current_step
        assert (
            updated_op.progress.steps_completed == 55
        )  # numeric step goes to steps_completed
        assert updated_op.progress.items_processed == 5500

    @pytest.mark.asyncio
    async def test_get_operation_pulls_from_bridge_when_running(
        self, operations_service, sample_metadata
    ):
        """Test that get_operation() refreshes from bridge when operation is RUNNING."""
        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge with state
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(
            percentage=75.0,
            message="Epoch 75/100",
            current_step=75,
            items_processed=7500,
        )

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Get operation should trigger refresh
        updated_op = await operations_service.get_operation(operation.operation_id)

        # Verify operation was refreshed from bridge
        assert updated_op.progress.percentage == 75.0
        assert updated_op.progress.current_step == "Epoch 75/100"

    @pytest.mark.asyncio
    async def test_immutable_operations_never_refresh(
        self, operations_service, sample_metadata
    ):
        """Test that completed/failed/cancelled operations never refresh."""
        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(percentage=50.0, message="Epoch 50/100", current_step=50)

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Complete operation
        await operations_service.complete_operation(
            operation.operation_id, {"final_result": "success"}
        )

        # Update bridge with new state (should NOT be reflected)
        bridge._update_state(
            percentage=99.0, message="Should not appear", current_step=99
        )

        # Get operation - should NOT refresh from bridge
        final_op = await operations_service.get_operation(operation.operation_id)

        # Progress should remain at 100% (from complete), not 99% (from bridge)
        assert final_op.status == OperationStatus.COMPLETED
        assert final_op.progress.percentage == 100.0
        assert final_op.progress.current_step != "Should not appear"

    @pytest.mark.asyncio
    async def test_metrics_cursor_increments(self, operations_service, sample_metadata):
        """Test that metrics cursor increments correctly with multiple pulls."""
        import time

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()

        # Add initial metrics
        bridge._append_metric({"epoch": 0, "loss": 2.5})
        bridge._append_metric({"epoch": 1, "loss": 2.3})

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # First refresh - should get 2 metrics
        operations_service._refresh_from_bridge(operation.operation_id)
        assert operations_service._metrics_cursors[operation.operation_id] == 2

        # Add more metrics
        bridge._append_metric({"epoch": 2, "loss": 2.1})

        # TASK 1.4: Wait for cache to expire before second refresh (TTL=1s)
        time.sleep(1.1)

        # Second refresh - should get only 1 new metric
        operations_service._refresh_from_bridge(operation.operation_id)
        assert operations_service._metrics_cursors[operation.operation_id] == 3

    @pytest.mark.asyncio
    async def test_refresh_with_no_bridge_registered(
        self, operations_service, sample_metadata
    ):
        """Test that refresh handles missing bridge gracefully."""
        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

        # Try to refresh without registering bridge (should not crash)
        operations_service._refresh_from_bridge(operation.operation_id)

        # Operation should still exist
        op = await operations_service.get_operation(operation.operation_id)
        assert op is not None


class TestOperationsServiceCancellationEvents:
    """Test dynamic cancellation events attribute functionality."""

    @pytest.mark.asyncio
    async def test_cancellation_events_initialization(self):
        """Test that _cancellation_events attribute is properly initialized."""
        operations_service = OperationsService()

        # The attribute should now exist and be initialized as empty dict
        assert hasattr(operations_service, "_cancellation_events")
        assert operations_service._cancellation_events == {}
        assert isinstance(operations_service._cancellation_events, dict)

    @pytest.mark.asyncio
    async def test_cancellation_events_storage_and_retrieval(self):
        """Test storing and retrieving cancellation events."""
        operations_service = OperationsService()

        # Set up cancellation events like DataService does
        operations_service._cancellation_events = {}

        # Create mock cancellation events
        event1 = asyncio.Event()
        event2 = asyncio.Event()

        operation_id1 = "test-op-1"
        operation_id2 = "test-op-2"

        # Store events
        operations_service._cancellation_events[operation_id1] = event1
        operations_service._cancellation_events[operation_id2] = event2

        # Verify storage
        assert len(operations_service._cancellation_events) == 2
        assert operations_service._cancellation_events[operation_id1] is event1
        assert operations_service._cancellation_events[operation_id2] is event2

    @pytest.mark.asyncio
    async def test_cancellation_events_with_async_operations(self):
        """Test cancellation events in realistic async operation scenario."""
        operations_service = OperationsService()
        operations_service._cancellation_events = {}

        # Create a cancellation event for an operation
        operation_id = "data-load-123"
        cancellation_event = asyncio.Event()
        operations_service._cancellation_events[operation_id] = cancellation_event

        # Simulate an async operation that waits for cancellation
        operation_cancelled = False

        async def mock_data_operation():
            nonlocal operation_cancelled
            try:
                # This would be the actual data loading work
                await asyncio.sleep(0.1)  # Simulate work
                # Check for cancellation during work
                if cancellation_event.is_set():
                    operation_cancelled = True
                    return "cancelled"
                return "completed"
            except asyncio.CancelledError:
                operation_cancelled = True
                raise

        # Start the operation
        operation_task = asyncio.create_task(mock_data_operation())

        # Wait a bit, then signal cancellation
        await asyncio.sleep(0.05)
        cancellation_event.set()

        await operation_task
        # The operation should have detected the cancellation signal
        assert operation_cancelled is True

    @pytest.mark.asyncio
    async def test_cancellation_events_cleanup(self):
        """Test that cancellation events can be cleaned up after operations."""
        operations_service = OperationsService()
        operations_service._cancellation_events = {}

        operation_id = "cleanup-test-op"
        cancellation_event = asyncio.Event()

        # Store the event
        operations_service._cancellation_events[operation_id] = cancellation_event
        assert operation_id in operations_service._cancellation_events

        # Cleanup after operation completes
        del operations_service._cancellation_events[operation_id]
        assert operation_id not in operations_service._cancellation_events

        # Should be able to handle empty dict
        assert len(operations_service._cancellation_events) == 0

    @pytest.mark.asyncio
    async def test_multiple_operations_with_cancellation_events(self):
        """Test handling multiple operations each with their own cancellation events."""
        operations_service = OperationsService()
        operations_service._cancellation_events = {}

        # Create multiple operations with events
        num_operations = 3
        events = {}

        for i in range(num_operations):
            op_id = f"multi-op-{i}"
            event = asyncio.Event()
            operations_service._cancellation_events[op_id] = event
            events[op_id] = event

        # Verify all events are stored
        assert len(operations_service._cancellation_events) == num_operations

        # Cancel one specific operation
        target_op_id = "multi-op-1"
        operations_service._cancellation_events[target_op_id].set()

        # Verify only the target operation was cancelled
        assert operations_service._cancellation_events[target_op_id].is_set()
        assert not operations_service._cancellation_events["multi-op-0"].is_set()
        assert not operations_service._cancellation_events["multi-op-2"].is_set()


class TestOperationsServiceCache:
    """Test TTL cache functionality for preventing redundant bridge refreshes (Task 1.4)."""

    @pytest.mark.asyncio
    async def test_cache_prevents_redundant_refresh(
        self, operations_service, sample_metadata
    ):
        """Test that multiple clients polling within TTL window only trigger one bridge read."""
        import time

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge and track how many times get_status() is called
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(
            percentage=50.0,
            message="Epoch 50/100",
            current_step=50,
        )

        # Track get_status calls
        original_get_status = bridge.get_status
        call_count = {"count": 0}

        def tracked_get_status():
            call_count["count"] += 1
            return original_get_status()

        bridge.get_status = tracked_get_status

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # First query - should trigger refresh (cache miss)
        op1 = await operations_service.get_operation(operation.operation_id)
        assert op1.progress.percentage == 50.0
        first_call_count = call_count["count"]
        assert first_call_count == 1  # Should have called get_status once

        # Second query immediately (within TTL=1s) - should NOT trigger refresh (cache hit)
        time.sleep(0.1)  # Wait 100ms
        op2 = await operations_service.get_operation(operation.operation_id)
        assert op2.progress.percentage == 50.0
        assert (
            call_count["count"] == first_call_count
        )  # No additional calls (cache hit)

        # Third query still within TTL - should NOT trigger refresh (cache hit)
        time.sleep(0.3)  # Total elapsed: 400ms
        op3 = await operations_service.get_operation(operation.operation_id)
        assert op3.progress.percentage == 50.0
        assert call_count["count"] == first_call_count  # Still no additional calls

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self, operations_service, sample_metadata
    ):
        """Test that force_refresh=True parameter bypasses cache."""
        import time

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(percentage=30.0, message="Epoch 30/100", current_step=30)

        # Track get_status calls
        original_get_status = bridge.get_status
        call_count = {"count": 0}

        def tracked_get_status():
            call_count["count"] += 1
            return original_get_status()

        bridge.get_status = tracked_get_status

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # First query - should trigger refresh
        op1 = await operations_service.get_operation(operation.operation_id)
        assert op1.progress.percentage == 30.0
        assert call_count["count"] == 1

        # Update bridge state
        bridge._update_state(percentage=35.0, message="Epoch 35/100", current_step=35)

        # Second query with force_refresh=True (should bypass cache even within TTL)
        time.sleep(0.2)  # Within TTL
        op2 = await operations_service.get_operation(
            operation.operation_id, force_refresh=True
        )
        assert op2.progress.percentage == 35.0  # Should see updated state
        assert call_count["count"] == 2  # Should have called get_status again

    @pytest.mark.asyncio
    async def test_cache_respects_ttl(self, operations_service, sample_metadata):
        """Test that cache becomes stale after TTL expires."""
        import time

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(percentage=20.0, message="Epoch 20/100", current_step=20)

        # Track get_status calls
        original_get_status = bridge.get_status
        call_count = {"count": 0}

        def tracked_get_status():
            call_count["count"] += 1
            return original_get_status()

        bridge.get_status = tracked_get_status

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # First query - should trigger refresh
        op1 = await operations_service.get_operation(operation.operation_id)
        assert op1.progress.percentage == 20.0
        assert call_count["count"] == 1

        # Update bridge state
        bridge._update_state(percentage=25.0, message="Epoch 25/100", current_step=25)

        # Wait for TTL to expire (default is 1.0 seconds)
        # Sleep slightly more than TTL to ensure cache is stale
        time.sleep(1.1)

        # Query again - cache should be stale, should trigger refresh
        op2 = await operations_service.get_operation(operation.operation_id)
        assert op2.progress.percentage == 25.0  # Should see updated state
        assert (
            call_count["count"] == 2
        )  # Should have called get_status again (cache miss)

    @pytest.mark.asyncio
    async def test_cache_initialization(self, operations_service):
        """Test that cache infrastructure is properly initialized."""
        # Verify cache tracking attributes exist
        assert hasattr(operations_service, "_last_refresh")
        assert isinstance(operations_service._last_refresh, dict)
        assert operations_service._last_refresh == {}

        # Verify cache TTL is configured
        assert hasattr(operations_service, "_cache_ttl")
        assert isinstance(operations_service._cache_ttl, float)
        assert operations_service._cache_ttl > 0  # Should be positive

    @pytest.mark.asyncio
    async def test_cache_only_for_running_operations(
        self, operations_service, sample_metadata
    ):
        """Test that completed/failed operations never use cache (always return stored state)."""
        import time

        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(percentage=80.0, message="Epoch 80/100", current_step=80)

        # Track get_status calls
        original_get_status = bridge.get_status
        call_count = {"count": 0}

        def tracked_get_status():
            call_count["count"] += 1
            return original_get_status()

        bridge.get_status = tracked_get_status

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Complete operation
        await operations_service.complete_operation(
            operation.operation_id, {"result": "success"}
        )

        # Update bridge (should be ignored)
        bridge._update_state(
            percentage=90.0, message="Should not appear", current_step=90
        )

        # Query completed operation multiple times
        op1 = await operations_service.get_operation(operation.operation_id)
        time.sleep(0.1)
        op2 = await operations_service.get_operation(operation.operation_id)

        # Should NEVER call get_status for completed operations
        assert call_count["count"] == 0
        assert op1.progress.percentage == 100.0  # From complete_operation
        assert op2.progress.percentage == 100.0  # Same
        assert op1.status == OperationStatus.COMPLETED
        assert op2.status == OperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cache_updated_on_refresh(self, operations_service, sample_metadata):
        """Test that _last_refresh timestamp is updated after successful refresh."""
        import time

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create bridge
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        bridge = ProgressBridge()
        bridge._update_state(percentage=40.0, message="Epoch 40/100", current_step=40)

        # Register bridge
        operations_service.register_local_bridge(operation.operation_id, bridge)

        # Verify no cache entry initially
        assert operation.operation_id not in operations_service._last_refresh

        # First query - should create cache entry
        await operations_service.get_operation(operation.operation_id)

        # Verify cache entry created with recent timestamp
        assert operation.operation_id in operations_service._last_refresh
        first_timestamp = operations_service._last_refresh[operation.operation_id]
        assert first_timestamp > 0

        # Wait and trigger refresh
        time.sleep(1.1)  # Exceed TTL
        await operations_service.get_operation(operation.operation_id)

        # Verify timestamp updated
        second_timestamp = operations_service._last_refresh[operation.operation_id]
        assert second_timestamp > first_timestamp  # Should be newer


class TestRemoteProxyRefresh:
    """Test _refresh_from_remote_proxy functionality (M2 Task 2.5)."""

    @pytest.mark.asyncio
    async def test_refresh_from_remote_proxy_updates_operation(
        self, operations_service, sample_metadata
    ):
        """Test that remote refresh updates operation from host service data."""
        from unittest.mock import AsyncMock

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create mock proxy
        mock_proxy = AsyncMock()
        mock_proxy.get_operation = AsyncMock(
            return_value={
                "status": "running",
                "progress": {
                    "percentage": 75.0,
                    "current_step": "Epoch 75/100",
                    "steps_completed": 75,
                    "steps_total": 100,
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        mock_proxy.get_metrics = AsyncMock(
            return_value=(
                [
                    {"epoch": 74, "train_loss": 0.15, "val_loss": 0.18},
                    {"epoch": 75, "train_loss": 0.14, "val_loss": 0.17},
                ],
                2,  # new_cursor
            )
        )

        # Register proxy
        host_op_id = "host_op_123"
        operations_service._remote_proxies[operation.operation_id] = (
            mock_proxy,
            host_op_id,
        )
        operations_service._metrics_cursors[operation.operation_id] = 0

        # Call refresh
        await operations_service._refresh_from_remote_proxy(operation.operation_id)

        # Verify operation updated
        updated_op = await operations_service.get_operation(
            operation.operation_id, force_refresh=False
        )
        assert updated_op.progress.percentage == 75.0
        assert updated_op.progress.current_step == "Epoch 75/100"

        # Verify proxy was called with correct args
        mock_proxy.get_operation.assert_called_once_with(host_op_id)
        mock_proxy.get_metrics.assert_called_once_with(host_op_id, 0)

    @pytest.mark.asyncio
    async def test_refresh_from_remote_proxy_appends_metrics(
        self, operations_service, sample_metadata
    ):
        """Test that metrics from host service are appended correctly."""
        from unittest.mock import AsyncMock

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Create mock proxy with metrics
        mock_proxy = AsyncMock()
        mock_proxy.get_operation = AsyncMock(
            return_value={
                "status": "running",
                "progress": {"percentage": 50.0},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        mock_proxy.get_metrics = AsyncMock(
            return_value=(
                [
                    {"epoch": 0, "train_loss": 2.5, "val_loss": 2.7},
                    {"epoch": 1, "train_loss": 2.3, "val_loss": 2.5},
                ],
                2,
            )
        )

        # Register proxy
        host_op_id = "host_op_456"
        operations_service._remote_proxies[operation.operation_id] = (
            mock_proxy,
            host_op_id,
        )
        operations_service._metrics_cursors[operation.operation_id] = 0

        # Refresh
        await operations_service._refresh_from_remote_proxy(operation.operation_id)

        # Verify metrics appended
        updated_op = await operations_service.get_operation(
            operation.operation_id, force_refresh=False
        )
        assert updated_op.metrics is not None
        assert "epochs" in updated_op.metrics
        assert len(updated_op.metrics["epochs"]) == 2
        assert updated_op.metrics["epochs"][0]["epoch"] == 0
        assert updated_op.metrics["epochs"][1]["epoch"] == 1

    @pytest.mark.asyncio
    async def test_refresh_from_remote_proxy_updates_cursor(
        self, operations_service, sample_metadata
    ):
        """Test that cursor is updated after fetching metrics."""
        from unittest.mock import AsyncMock

        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Mock proxy
        mock_proxy = AsyncMock()
        mock_proxy.get_operation = AsyncMock(
            return_value={
                "status": "running",
                "progress": {"percentage": 60.0},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        mock_proxy.get_metrics = AsyncMock(
            return_value=([{"epoch": 5, "train_loss": 1.8}], 6)  # new_cursor = 6
        )

        # Register proxy with cursor=5
        operations_service._remote_proxies[operation.operation_id] = (
            mock_proxy,
            "host_op_789",
        )
        operations_service._metrics_cursors[operation.operation_id] = 5

        # Refresh
        await operations_service._refresh_from_remote_proxy(operation.operation_id)

        # Verify cursor updated from 5 to 6
        assert operations_service._metrics_cursors[operation.operation_id] == 6

        # Verify proxy called with cursor=5
        mock_proxy.get_metrics.assert_called_once_with("host_op_789", 5)

    @pytest.mark.asyncio
    async def test_refresh_from_remote_proxy_respects_cache(
        self, operations_service, sample_metadata
    ):
        """Test that remote refresh respects cache TTL."""
        import time
        from unittest.mock import AsyncMock

        # Set short TTL for testing
        operations_service._cache_ttl = 1.0

        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Mock proxy
        mock_proxy = AsyncMock()
        mock_proxy.get_operation = AsyncMock(
            return_value={
                "status": "running",
                "progress": {"percentage": 80.0},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        mock_proxy.get_metrics = AsyncMock(return_value=([], 0))

        # Register proxy
        operations_service._remote_proxies[operation.operation_id] = (
            mock_proxy,
            "host_op_cache",
        )

        # First refresh
        await operations_service._refresh_from_remote_proxy(operation.operation_id)
        assert mock_proxy.get_operation.call_count == 1

        # Second refresh immediately (should use cache)
        await operations_service._refresh_from_remote_proxy(operation.operation_id)
        assert mock_proxy.get_operation.call_count == 1  # No new call

        # Third refresh after TTL expires
        time.sleep(1.1)
        await operations_service._refresh_from_remote_proxy(operation.operation_id)
        assert mock_proxy.get_operation.call_count == 2  # New call

    @pytest.mark.asyncio
    async def test_refresh_from_remote_proxy_no_proxy_registered(
        self, operations_service, sample_metadata
    ):
        """Test that refresh does nothing if no proxy is registered."""
        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Don't register any proxy

        # Call refresh - should not raise
        await operations_service._refresh_from_remote_proxy(operation.operation_id)

        # Operation should be unchanged
        updated_op = await operations_service.get_operation(operation.operation_id)
        assert updated_op.progress.percentage == 0.0

    @pytest.mark.asyncio
    async def test_get_operation_calls_remote_refresh(
        self, operations_service, sample_metadata
    ):
        """Test that get_operation calls remote refresh for running operations with proxy."""
        from unittest.mock import AsyncMock

        # Create and start operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=sample_metadata
        )
        mock_task = AsyncMock()
        await operations_service.start_operation(operation.operation_id, mock_task)

        # Mock proxy
        mock_proxy = AsyncMock()
        mock_proxy.get_operation = AsyncMock(
            return_value={
                "status": "running",
                "progress": {"percentage": 90.0, "current_step": "Almost done"},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        mock_proxy.get_metrics = AsyncMock(return_value=([], 0))

        # Register proxy
        operations_service._remote_proxies[operation.operation_id] = (
            mock_proxy,
            "host_op_get",
        )

        # Get operation - should trigger remote refresh
        result = await operations_service.get_operation(operation.operation_id)

        # Verify proxy was called
        assert mock_proxy.get_operation.called
        assert result.progress.percentage == 90.0
        assert result.progress.current_step == "Almost done"
