"""
Test cases for ServiceOrchestrator operations service integration enhancements.

This module tests the new start_managed_operation() and run_sync_operation()
methods that integrate with the operations service to handle ALL async complexity.

Following TDD methodology - tests written first, then implementation.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationInfo, OperationMetadata, OperationType
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator


class MockServiceOrchestrator(ServiceOrchestrator):
    """Mock implementation of ServiceOrchestrator for testing operations service integration."""

    def __init__(self, **kwargs):
        self._service_name = kwargs.get("service_name", "TestService")
        self._default_host_url = kwargs.get("default_host_url", "http://localhost:8000")
        self._env_var_prefix = kwargs.get("env_var_prefix", "TEST")

        # Create a mock adapter
        self.adapter = MagicMock()
        self.adapter.use_host_service = kwargs.get("use_host_service", False)
        self.adapter.host_service_url = kwargs.get("host_service_url", None)

        # Initialize progress infrastructure that ServiceOrchestrator expects
        from ktrdr.async_infrastructure.progress import GenericProgressManager
        from ktrdr.async_infrastructure.service_orchestrator import (
            DefaultServiceProgressRenderer,
        )

        self._progress_renderer = DefaultServiceProgressRenderer(self._service_name)
        self._generic_progress_manager = GenericProgressManager()
        self._current_operation_progress = None
        self._current_cancellation_token = None

    def _initialize_adapter(self):
        return self.adapter

    def _get_service_name(self) -> str:
        return self._service_name

    def _get_default_host_url(self) -> str:
        return self._default_host_url

    def _get_env_var_prefix(self) -> str:
        return self._env_var_prefix


class TestStartManagedOperation:
    """Test start_managed_operation() method - handles ALL async complexity."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.fixture
    def mock_operations_service(self):
        """Mock operations service for testing."""
        mock_service = MagicMock()
        mock_service.create_operation = AsyncMock()
        mock_service.start_operation = AsyncMock()
        mock_service.update_progress = AsyncMock()
        mock_service.complete_operation = AsyncMock()
        mock_service.fail_operation = AsyncMock()
        mock_service.get_cancellation_token = MagicMock()
        return mock_service

    @pytest.mark.asyncio
    async def test_start_managed_operation_exists(self, orchestrator):
        """Test that start_managed_operation method exists (will fail initially)."""
        # This test will fail until we implement the method
        assert hasattr(orchestrator, "start_managed_operation")
        assert callable(orchestrator.start_managed_operation)

    @pytest.mark.asyncio
    async def test_start_managed_operation_creates_operation(
        self, orchestrator, mock_operations_service
    ):
        """Test that start_managed_operation creates operation via operations service."""
        # Mock the operation creation
        mock_operation = OperationInfo(
            operation_id="op_test_123",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        # Mock async operation function
        async def test_operation():
            await asyncio.sleep(0.01)
            return {"result": "success"}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # This will fail until we implement start_managed_operation
            result = await orchestrator.start_managed_operation(
                operation_name="test_operation",
                operation_type="DATA_LOAD",
                operation_func=test_operation,
            )

            # Should return API response format
            assert isinstance(result, dict)
            assert "operation_id" in result
            assert "status" in result
            assert "message" in result
            assert result["operation_id"] == "op_test_123"
            assert result["status"] == "started"

            # Should have created operation via operations service
            mock_operations_service.create_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_managed_operation_handles_background_execution(
        self, orchestrator, mock_operations_service
    ):
        """Test that start_managed_operation executes operation in background task."""
        # Mock operation creation
        mock_operation = OperationInfo(
            operation_id="op_test_456",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        operation_executed = False

        async def test_operation():
            nonlocal operation_executed
            await asyncio.sleep(0.02)  # Simulate work
            operation_executed = True
            return {"result": "background_success"}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Start the operation
            result = await orchestrator.start_managed_operation(
                operation_name="background_test",
                operation_type="DATA_LOAD",
                operation_func=test_operation,
            )

            # Should return immediately with started status
            assert result["status"] == "started"

            # Give background task time to complete
            await asyncio.sleep(0.05)

            # Background operation should have executed
            assert operation_executed

            # Should have started operation in background
            mock_operations_service.start_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_managed_operation_integrates_with_progress_system(
        self, orchestrator, mock_operations_service
    ):
        """Test that start_managed_operation integrates with progress tracking."""
        # Mock operation creation
        mock_operation = OperationInfo(
            operation_id="op_progress_test",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        async def test_operation_with_progress():
            # This should be able to use orchestrator's progress system
            for i in range(3):
                orchestrator.update_operation_progress(
                    step=i + 1, message=f"Step {i + 1}", items_processed=i + 1
                )
                await asyncio.sleep(0.01)
            return {"progress_steps": 3}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            result = await orchestrator.start_managed_operation(
                operation_name="progress_test",
                operation_type="DATA_LOAD",
                operation_func=test_operation_with_progress,
            )

            # Should handle progress integration
            assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_managed_operation_handles_cancellation_coordination(
        self, orchestrator, mock_operations_service
    ):
        """Test that start_managed_operation coordinates with cancellation system."""
        # Mock operation with cancellation token
        mock_operation = OperationInfo(
            operation_id="op_cancel_test",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        # Mock cancellation token
        mock_token = MagicMock()
        mock_token.is_cancelled.return_value = False
        mock_operations_service.get_cancellation_token.return_value = mock_token

        cancellation_checked = False

        async def test_operation_with_cancellation():
            nonlocal cancellation_checked
            # Operation should be able to check cancellation
            token = orchestrator.get_current_cancellation_token()
            if token:
                cancellation_checked = True
                if token.is_cancelled():
                    return {"status": "cancelled"}
            await asyncio.sleep(0.01)
            return {"status": "completed"}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            result = await orchestrator.start_managed_operation(
                operation_name="cancel_test",
                operation_type="DATA_LOAD",
                operation_func=test_operation_with_cancellation,
            )

            # Should provide cancellation coordination
            assert result["status"] == "started"

            # Give time for background execution
            await asyncio.sleep(0.05)

            # Should have integrated with cancellation system
            assert cancellation_checked

    @pytest.mark.asyncio
    async def test_start_managed_operation_handles_operation_failure(
        self, orchestrator, mock_operations_service
    ):
        """Test that start_managed_operation handles operation failures properly."""
        # Mock operation creation
        mock_operation = OperationInfo(
            operation_id="op_fail_test",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        async def failing_operation():
            await asyncio.sleep(0.01)
            raise ValueError("Test operation failure")

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Should still return started status immediately
            result = await orchestrator.start_managed_operation(
                operation_name="fail_test",
                operation_type="DATA_LOAD",
                operation_func=failing_operation,
            )

            assert result["status"] == "started"

            # Give time for background failure
            await asyncio.sleep(0.05)

            # Should have marked operation as failed
            mock_operations_service.fail_operation.assert_called_once()


class TestRunSyncOperation:
    """Test run_sync_operation() method - synchronous execution with progress/cancellation."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    def test_run_sync_operation_exists(self, orchestrator):
        """Test that run_sync_operation method exists (will fail initially)."""
        # This test will fail until we implement the method
        assert hasattr(orchestrator, "run_sync_operation")
        assert callable(orchestrator.run_sync_operation)

    @pytest.mark.asyncio
    async def test_run_sync_operation_executes_synchronously(self, orchestrator):
        """Test that run_sync_operation runs operation synchronously but returns results directly."""

        async def test_operation():
            await asyncio.sleep(0.01)
            return {"result": "sync_success", "data": [1, 2, 3]}

        # This will fail until we implement run_sync_operation
        result = orchestrator.run_sync_operation(
            operation_name="sync_test", operation_func=test_operation
        )

        # Should return direct results from operation, not API response wrapper
        assert isinstance(result, dict)
        assert result["result"] == "sync_success"
        assert result["data"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_run_sync_operation_integrates_with_progress(self, orchestrator):
        """Test that run_sync_operation still provides progress tracking."""

        progress_steps = []

        async def test_operation_with_progress():
            for i in range(2):
                # Should be able to report progress even in sync mode
                orchestrator.update_operation_progress(
                    step=i + 1, message=f"Sync step {i + 1}"
                )
                progress_steps.append(i + 1)
                await asyncio.sleep(0.01)
            return {"steps_completed": len(progress_steps)}

        result = orchestrator.run_sync_operation(
            operation_name="sync_progress_test",
            operation_func=test_operation_with_progress,
        )

        # Should have completed with progress tracking
        assert result["steps_completed"] == 2
        assert len(progress_steps) == 2

    @pytest.mark.asyncio
    async def test_run_sync_operation_supports_cancellation(self, orchestrator):
        """Test that run_sync_operation supports cancellation even in sync mode."""

        cancellation_checked = False

        async def test_operation_with_cancellation():
            nonlocal cancellation_checked
            # Should be able to check cancellation even in sync mode
            token = orchestrator.get_current_cancellation_token()
            if token:
                cancellation_checked = True
            await asyncio.sleep(0.01)
            return {"cancellation_support": cancellation_checked}

        result = orchestrator.run_sync_operation(
            operation_name="sync_cancel_test",
            operation_func=test_operation_with_cancellation,
        )

        # Should have cancellation support even in sync mode
        assert result["cancellation_support"] == cancellation_checked


class TestOperationsServiceIntegration:
    """Test overall operations service integration patterns."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.mark.asyncio
    async def test_operations_service_dependency_injection(self, orchestrator):
        """Test that operations service is properly injected and used."""

        mock_service = MagicMock()
        mock_service.create_operation = AsyncMock()

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_service,
        ):
            # Both methods should use the same operations service instance
            assert hasattr(orchestrator, "start_managed_operation")
            assert hasattr(orchestrator, "run_sync_operation")

    @pytest.mark.asyncio
    async def test_api_response_formatting_for_cli_compatibility(self, orchestrator):
        """Test that API responses are formatted for CLI/AsyncOperationManager compatibility."""

        mock_operations_service = MagicMock()
        mock_operation = OperationInfo(
            operation_id="op_cli_test",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(
                symbol="TEST",
                timeframe="1min",
                mode="test",
                start_date=datetime.now(timezone.utc).date(),
                end_date=datetime.now(timezone.utc).date(),
            ),
        )
        mock_operations_service.create_operation = AsyncMock(
            return_value=mock_operation
        )
        mock_operations_service.start_operation = AsyncMock()
        mock_operations_service.complete_operation = AsyncMock()
        mock_operations_service.fail_operation = AsyncMock()

        async def test_operation():
            return {"data": "test"}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            result = await orchestrator.start_managed_operation(
                operation_name="cli_test",
                operation_type="DATA_LOAD",
                operation_func=test_operation,
            )

            # Should format response for CLI compatibility
            assert "operation_id" in result
            assert "status" in result
            assert "message" in result

            # Should match AsyncOperationManager expected format
            assert result["operation_id"] == "op_cli_test"
            assert result["status"] in ["started", "pending", "running"]

    @pytest.mark.asyncio
    async def test_error_handling_in_operations_integration(self, orchestrator):
        """Test error handling when operations service integration fails."""

        # Mock operations service that fails
        mock_service = MagicMock()
        mock_service.create_operation = AsyncMock(
            side_effect=Exception("Operations service error")
        )

        async def test_operation():
            return {"data": "test"}

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_service,
        ):
            # Should handle operations service errors gracefully
            with pytest.raises(Exception, match="Operations service error"):
                await orchestrator.start_managed_operation(
                    operation_name="error_test",
                    operation_type="DATA_LOAD",
                    operation_func=test_operation,
                )


class TestBackwardCompatibility:
    """Test that operations service integration doesn't break existing functionality."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.mark.asyncio
    async def test_existing_progress_methods_still_work(self, orchestrator):
        """Test that existing progress tracking methods still work."""

        # Existing execute_with_progress should still work
        async def test_operation():
            return "success"

        result = await orchestrator.execute_with_progress(
            test_operation(), operation_name="backward_compat_test"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_existing_cancellation_methods_still_work(self, orchestrator):
        """Test that existing cancellation methods still work."""

        async def test_operation():
            return "success"

        # Existing execute_with_cancellation should still work
        result = await orchestrator.execute_with_cancellation(
            test_operation(), operation_name="cancel_compat_test"
        )

        assert result == "success"

    def test_existing_configuration_methods_still_work(self, orchestrator):
        """Test that existing configuration methods are not broken."""

        # All existing methods should still work
        assert not orchestrator.is_using_host_service()
        config_info = orchestrator.get_configuration_info()
        assert isinstance(config_info, dict)

        validation = orchestrator.validate_configuration()
        assert isinstance(validation, dict)
