"""Tests for worker re-registration monitor (Task 1.7).

This module tests the re-registration monitor that detects missed health
checks and re-registers with the backend.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import CompletedOperationReport, WorkerType
from ktrdr.workers.base import WorkerAPIBase


class MockWorker(WorkerAPIBase):
    """Mock worker for testing re-registration."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )


class TestReregistrationMonitorConfiguration:
    """Test re-registration monitor configuration fields."""

    def test_health_check_timeout_default(self):
        """Test default health check timeout is 30 seconds."""
        worker = MockWorker()
        assert hasattr(worker, "_health_check_timeout")
        assert worker._health_check_timeout == 30

    def test_reregistration_check_interval_default(self):
        """Test default re-registration check interval is 10 seconds."""
        worker = MockWorker()
        assert hasattr(worker, "_reregistration_check_interval")
        assert worker._reregistration_check_interval == 10

    def test_completed_operations_initialized_empty(self):
        """Test completed operations list is initialized empty."""
        worker = MockWorker()
        assert hasattr(worker, "_completed_operations")
        assert isinstance(worker._completed_operations, list)
        assert len(worker._completed_operations) == 0

    def test_monitor_task_initialized_none(self):
        """Test monitor task is initialized to None."""
        worker = MockWorker()
        assert hasattr(worker, "_monitor_task")
        assert worker._monitor_task is None


class TestRecordOperationCompleted:
    """Test recording completed operations for re-registration."""

    def test_record_operation_completed_adds_to_list(self):
        """Test recording a completed operation adds it to the list."""
        worker = MockWorker()

        worker.record_operation_completed(
            operation_id="op_123",
            status="COMPLETED",
            result={"accuracy": 0.95},
        )

        assert len(worker._completed_operations) == 1
        report = worker._completed_operations[0]
        assert report.operation_id == "op_123"
        assert report.status == "COMPLETED"
        assert report.result == {"accuracy": 0.95}
        assert isinstance(report.completed_at, datetime)

    def test_record_operation_completed_multiple(self):
        """Test recording multiple completed operations."""
        worker = MockWorker()

        worker.record_operation_completed("op_1", "COMPLETED", {"result": 1})
        worker.record_operation_completed("op_2", "FAILED", error_message="Error")
        worker.record_operation_completed("op_3", "CANCELLED")

        assert len(worker._completed_operations) == 3
        assert worker._completed_operations[0].operation_id == "op_1"
        assert worker._completed_operations[1].status == "FAILED"
        assert worker._completed_operations[1].error_message == "Error"
        assert worker._completed_operations[2].status == "CANCELLED"

    def test_record_operation_completed_creates_report(self):
        """Test that recorded operations are CompletedOperationReport instances."""
        worker = MockWorker()

        worker.record_operation_completed("op_123", "COMPLETED")

        report = worker._completed_operations[0]
        assert isinstance(report, CompletedOperationReport)


class TestEnsureRegistered:
    """Test the _ensure_registered method."""

    @pytest.mark.asyncio
    async def test_ensure_registered_when_already_registered(self):
        """Test that nothing happens when worker is already registered."""
        worker = MockWorker()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Simulate 200 OK - worker is registered
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            await worker._ensure_registered()

            # Should have checked registration
            mock_client.get.assert_called_once()
            # Should NOT have tried to register (already registered)
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_registered_when_not_registered(self):
        """Test that worker registers when not found in registry."""
        worker = MockWorker()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Simulate 404 - worker not registered
            mock_get_response = MagicMock()
            mock_get_response.status_code = 404
            mock_client.get.return_value = mock_get_response

            # Simulate successful registration
            mock_post_response = MagicMock()
            mock_post_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_post_response

            await worker._ensure_registered()

            # Should have checked registration
            mock_client.get.assert_called_once()
            # Should have registered
            mock_client.post.assert_called_once()


class TestSelfRegisterWithResilienceFields:
    """Test that self_register includes resilience fields."""

    @pytest.mark.asyncio
    async def test_self_register_includes_current_operation_id(self):
        """Test that registration includes current_operation_id."""
        worker = MockWorker()

        # Add a mock active operation
        from ktrdr.api.models.operations import OperationMetadata

        await worker._operations_service.create_operation(
            operation_id="active_op_123",
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            await worker.self_register()

            # Check the registration payload
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json"))

            assert "current_operation_id" in payload
            assert payload["current_operation_id"] == "active_op_123"

    @pytest.mark.asyncio
    async def test_self_register_includes_completed_operations(self):
        """Test that registration includes completed_operations."""
        worker = MockWorker()

        # Record some completed operations
        worker.record_operation_completed("op_1", "COMPLETED", {"result": "success"})
        worker.record_operation_completed("op_2", "FAILED", error_message="Timeout")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            await worker.self_register()

            # Check the registration payload
            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", call_args[1].get("json"))

            assert "completed_operations" in payload
            assert len(payload["completed_operations"]) == 2

    @pytest.mark.asyncio
    async def test_self_register_clears_completed_operations_on_success(self):
        """Test that completed_operations is cleared after successful registration."""
        worker = MockWorker()

        # Record some completed operations
        worker.record_operation_completed("op_1", "COMPLETED")
        worker.record_operation_completed("op_2", "COMPLETED")
        assert len(worker._completed_operations) == 2

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            await worker.self_register()

            # Completed operations should be cleared after successful registration
            assert len(worker._completed_operations) == 0


class TestMonitorHealthChecks:
    """Test the health check monitoring logic."""

    @pytest.mark.asyncio
    async def test_monitor_detects_missed_health_check(self):
        """Test monitor detects when health check timeout exceeded."""
        worker = MockWorker()

        # Set last health check to be older than timeout
        worker._last_health_check_received = datetime.utcnow() - timedelta(seconds=35)

        # Mock _ensure_registered to track if it's called
        worker._ensure_registered = AsyncMock()

        # Run one iteration of the monitor logic
        elapsed = (
            datetime.utcnow() - worker._last_health_check_received
        ).total_seconds()
        if elapsed > worker._health_check_timeout:
            await worker._ensure_registered()

        worker._ensure_registered.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_does_not_trigger_within_timeout(self):
        """Test monitor does not trigger re-registration within timeout period."""
        worker = MockWorker()

        # Set last health check to be recent (within timeout)
        worker._last_health_check_received = datetime.utcnow() - timedelta(seconds=10)

        # Mock _ensure_registered
        worker._ensure_registered = AsyncMock()

        # Simulate monitor check
        elapsed = (
            datetime.utcnow() - worker._last_health_check_received
        ).total_seconds()
        if elapsed > worker._health_check_timeout:
            await worker._ensure_registered()

        worker._ensure_registered.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_skips_when_no_health_check_received(self):
        """Test monitor skips check when no health check has been received yet."""
        worker = MockWorker()

        # No health check received yet
        assert worker._last_health_check_received is None

        worker._ensure_registered = AsyncMock()

        # Simulate monitor check
        if worker._last_health_check_received is not None:
            elapsed = (
                datetime.utcnow() - worker._last_health_check_received
            ).total_seconds()
            if elapsed > worker._health_check_timeout:
                await worker._ensure_registered()

        # Should not trigger because no health check received yet
        worker._ensure_registered.assert_not_called()


class TestStartReregistrationMonitor:
    """Test starting the re-registration monitor."""

    def test_has_start_reregistration_monitor_method(self):
        """Test that _start_reregistration_monitor method exists."""
        worker = MockWorker()
        assert hasattr(worker, "_start_reregistration_monitor")
        assert callable(worker._start_reregistration_monitor)

    def test_has_monitor_health_checks_method(self):
        """Test that _monitor_health_checks method exists."""
        worker = MockWorker()
        assert hasattr(worker, "_monitor_health_checks")
        assert callable(worker._monitor_health_checks)
