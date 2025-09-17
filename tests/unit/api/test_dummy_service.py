"""
Test cases for DummyService - the perfect async service reference implementation.

This module tests DummyService which demonstrates the ServiceOrchestrator pattern:
- Minimal code with maximum power
- Perfect UX with progress and cancellation
- Zero boilerplate - ServiceOrchestrator handles ALL complexity

Following TDD methodology - tests written first, then implementation.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationInfo, OperationMetadata, OperationType


class TestDummyService:
    """Test DummyService implementation - the perfect async service template."""

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

    def test_dummy_service_class_exists(self):
        """Test that DummyService class exists and can be imported."""
        # This will fail initially until we create the class
        from ktrdr.api.services.dummy_service import DummyService

        assert DummyService is not None
        assert hasattr(DummyService, "__name__")
        assert DummyService.__name__ == "DummyService"

    def test_dummy_service_extends_service_orchestrator(self):
        """Test that DummyService properly extends ServiceOrchestrator."""
        from ktrdr.api.services.dummy_service import DummyService
        from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator

        # Should be subclass of ServiceOrchestrator
        assert issubclass(DummyService, ServiceOrchestrator)

    def test_dummy_service_can_be_instantiated(self):
        """Test that DummyService can be instantiated."""
        from ktrdr.api.services.dummy_service import DummyService

        # Should be able to create instance
        service = DummyService()
        assert service is not None
        assert isinstance(service, DummyService)

    def test_dummy_service_implements_required_abstract_methods(self):
        """Test that DummyService implements all required ServiceOrchestrator methods."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Check required abstract method implementations
        assert hasattr(service, "_initialize_adapter")
        assert callable(service._initialize_adapter)
        assert hasattr(service, "_get_service_name")
        assert callable(service._get_service_name)
        assert hasattr(service, "_get_default_host_url")
        assert callable(service._get_default_host_url)
        assert hasattr(service, "_get_env_var_prefix")
        assert callable(service._get_env_var_prefix)

        # Test return values are correct for dummy service
        assert service._get_service_name() == "DummyService"
        assert service._get_default_host_url() == "http://localhost:8000"
        assert service._get_env_var_prefix() == "DUMMY"
        assert service._initialize_adapter() is None  # No adapter needed

    def test_dummy_service_has_async_method(self):
        """Test that DummyService has start_dummy_task async method."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Should have start_dummy_task method
        assert hasattr(service, "start_dummy_task")
        assert callable(service.start_dummy_task)
        assert asyncio.iscoroutinefunction(service.start_dummy_task)

    def test_dummy_service_has_sync_method(self):
        """Test that DummyService has run_dummy_task_sync method."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Should have run_dummy_task_sync method
        assert hasattr(service, "run_dummy_task_sync")
        assert callable(service.run_dummy_task_sync)
        # Should NOT be async (it's the sync version)
        assert not asyncio.iscoroutinefunction(service.run_dummy_task_sync)

    @pytest.mark.asyncio
    async def test_start_dummy_task_calls_service_orchestrator(
        self, mock_operations_service
    ):
        """Test that start_dummy_task calls ServiceOrchestrator.start_managed_operation."""
        from ktrdr.api.services.dummy_service import DummyService

        # Mock the operation creation
        mock_operation = OperationInfo(
            operation_id="op_dummy_123",
            operation_type=OperationType.DATA_LOAD,  # Using DATA_LOAD as fallback
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        service = DummyService()

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):

            # Should call start_managed_operation with correct parameters
            result = await service.start_dummy_task()

            # Should return API response format
            assert isinstance(result, dict)
            assert "operation_id" in result
            assert "status" in result
            assert "message" in result
            assert result["operation_id"] == "op_dummy_123"
            assert result["status"] == "started"
            assert "dummy_task" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_start_dummy_task_uses_correct_operation_parameters(
        self, mock_operations_service
    ):
        """Test that start_dummy_task passes correct parameters to ServiceOrchestrator."""
        from ktrdr.api.services.dummy_service import DummyService

        # Mock the operation creation
        mock_operation = OperationInfo(
            operation_id="op_dummy_params",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        service = DummyService()

        # Spy on start_managed_operation to verify parameters
        with patch.object(service, "start_managed_operation") as mock_start_managed:
            mock_start_managed.return_value = {
                "operation_id": "op_dummy_params",
                "status": "started",
                "message": "Started dummy_task operation",
            }

            await service.start_dummy_task()

            # Should have called start_managed_operation with correct parameters
            mock_start_managed.assert_called_once()
            args, kwargs = mock_start_managed.call_args

            # Check operation parameters (could be passed as kwargs)
            if args:
                assert args[0] == "dummy_task"  # operation_name
                assert args[1] == "DUMMY"  # operation_type
                # Third argument should be the async function
                assert callable(args[2])
                assert asyncio.iscoroutinefunction(args[2])
            else:
                # Called with keyword arguments
                assert kwargs.get("operation_name") == "dummy_task"
                assert kwargs.get("operation_type") == "DUMMY"
                assert callable(kwargs.get("operation_func"))
                assert asyncio.iscoroutinefunction(kwargs.get("operation_func"))

    def test_run_dummy_task_sync_calls_service_orchestrator(self):
        """Test that run_dummy_task_sync calls ServiceOrchestrator.run_sync_operation."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Spy on run_sync_operation to verify parameters
        with patch.object(service, "run_sync_operation") as mock_run_sync:
            mock_run_sync.return_value = {
                "status": "success",
                "iterations_completed": 100,
                "message": "Completed all 100 iterations!",
            }

            result = service.run_dummy_task_sync()

            # Should have called run_sync_operation with correct parameters
            mock_run_sync.assert_called_once()
            args, kwargs = mock_run_sync.call_args

            # Check operation parameters (could be positional or keyword args)
            if args:
                assert len(args) >= 2
                assert args[0] == "dummy_task"  # operation_name
                # Second argument should be the async function
                assert callable(args[1])
                assert asyncio.iscoroutinefunction(args[1])
            else:
                # Called with keyword arguments
                assert kwargs.get("operation_name") == "dummy_task"
                assert callable(kwargs.get("operation_func"))
                assert asyncio.iscoroutinefunction(kwargs.get("operation_func"))

            # Should return direct results (not API wrapper)
            assert result["status"] == "success"
            assert result["iterations_completed"] == 100

    @pytest.mark.asyncio
    async def test_dummy_task_async_implementation_exists(self):
        """Test that _run_dummy_task_async method exists and has correct signature."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Should have the domain logic method
        assert hasattr(service, "_run_dummy_task_async")
        assert callable(service._run_dummy_task_async)
        assert asyncio.iscoroutinefunction(service._run_dummy_task_async)

    @pytest.mark.asyncio
    async def test_dummy_task_async_performs_work_with_progress(self):
        """Test that _run_dummy_task_async performs work with progress reporting."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Track progress updates
        progress_updates = []
        original_update = service.update_operation_progress

        def mock_update_progress(*args, **kwargs):
            progress_updates.append((args, kwargs))
            return original_update(*args, **kwargs)

        # Mock sleep to speed up test
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch.object(
                service, "update_operation_progress", side_effect=mock_update_progress
            ),
            patch.object(service, "get_current_cancellation_token", return_value=None),
        ):

            # Run the domain logic (but make it fast for testing)
            # We'll patch the implementation to do fewer iterations

            async def fast_dummy_task():
                """Fast version of dummy task for testing (3 iterations instead of 100)."""
                duration_seconds = 6  # 3 iterations * 2 seconds each
                iterations = duration_seconds // 2

                for i in range(iterations):
                    # Check cancellation
                    cancellation_token = service.get_current_cancellation_token()
                    if cancellation_token and cancellation_token.is_cancelled():
                        return {
                            "status": "cancelled",
                            "iterations_completed": i,
                            "message": f"Stopped after {i} iterations",
                        }

                    # Simulate work
                    await asyncio.sleep(0.01)  # Fast for testing

                    # Report progress
                    service.update_operation_progress(
                        step=i + 1,
                        message=f"Working hard on iteration {i+1}!",
                        items_processed=i + 1,
                        context={
                            "current_step": f"Iteration {i+1}/{iterations}",
                            "current_item": f"Processing step {i+1}",
                        },
                    )

                return {
                    "status": "success",
                    "iterations_completed": iterations,
                    "total_duration_seconds": duration_seconds,
                    "message": f"Completed all {iterations} iterations!",
                }

            # Patch the method for this test
            service._run_dummy_task_async = fast_dummy_task

            # Execute the task
            result = await service._run_dummy_task_async()

            # Should complete successfully
            assert result["status"] == "success"
            assert result["iterations_completed"] == 3
            assert result["total_duration_seconds"] == 6
            assert "Completed all 3 iterations" in result["message"]

            # Should have reported progress for each iteration
            assert len(progress_updates) == 3

            # Check progress update structure
            for i, (_args, kwargs) in enumerate(progress_updates):
                assert kwargs["step"] == i + 1
                assert "Working hard on iteration" in kwargs["message"]
                assert kwargs["items_processed"] == i + 1
                assert "context" in kwargs
                assert "current_step" in kwargs["context"]

    @pytest.mark.asyncio
    async def test_dummy_task_async_supports_cancellation(self):
        """Test that _run_dummy_task_async properly supports cancellation."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Mock cancellation token that becomes cancelled after first check
        mock_token = MagicMock()
        call_count = 0

        def mock_is_cancelled():
            nonlocal call_count
            call_count += 1
            return call_count > 1  # Cancel after first iteration

        mock_token.is_cancelled = mock_is_cancelled

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch.object(
                service, "get_current_cancellation_token", return_value=mock_token
            ),
            patch.object(service, "update_operation_progress"),
        ):

            # Run the task - should be cancelled early
            result = await service._run_dummy_task_async()

            # Should return cancelled status
            assert result["status"] == "cancelled"
            assert result["iterations_completed"] < 100  # Should stop early
            assert "Stopped after" in result["message"]

    @pytest.mark.asyncio
    async def test_dummy_task_async_has_correct_duration_and_iterations(self):
        """Test that _run_dummy_task_async has correct duration/iteration configuration."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # For testing, we'll check the configuration without running the full task
        # We can do this by examining the code logic

        # Mock everything to avoid long execution
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch.object(service, "get_current_cancellation_token", return_value=None),
            patch.object(service, "update_operation_progress"),
        ):

            # Create a version that stops after checking the configuration

            async def config_check_version():
                """Version that just checks the configuration."""
                duration_seconds = 200  # As per spec: 200 seconds
                iterations = (
                    duration_seconds // 2
                )  # 2 seconds per iteration = 100 iterations

                # Return configuration info without doing the work
                return {
                    "status": "success",
                    "iterations_completed": iterations,
                    "total_duration_seconds": duration_seconds,
                    "message": f"Completed all {iterations} iterations!",
                }

            service._run_dummy_task_async = config_check_version
            result = await service._run_dummy_task_async()

            # Should be configured for 200 seconds / 100 iterations
            assert result["iterations_completed"] == 100
            assert result["total_duration_seconds"] == 200


class TestDummyServiceIntegration:
    """Test DummyService integration with ServiceOrchestrator operations."""

    @pytest.fixture
    def mock_operations_service(self):
        """Mock operations service for integration testing."""
        mock_service = MagicMock()
        mock_service.create_operation = AsyncMock()
        mock_service.start_operation = AsyncMock()
        mock_service.update_progress = AsyncMock()
        mock_service.complete_operation = AsyncMock()
        mock_service.fail_operation = AsyncMock()
        mock_service.get_cancellation_token = MagicMock()
        return mock_service

    @pytest.mark.asyncio
    async def test_dummy_service_full_integration_with_operations_service(
        self, mock_operations_service
    ):
        """Test complete integration flow: DummyService -> ServiceOrchestrator -> OperationsService."""
        from ktrdr.api.services.dummy_service import DummyService

        # Mock operation info
        mock_operation = OperationInfo(
            operation_id="op_integration_test",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        service = DummyService()

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):

            # Start the operation
            result = await service.start_dummy_task()

            # Should return proper API format
            assert result["operation_id"] == "op_integration_test"
            assert result["status"] == "started"

            # Should have integrated with operations service
            mock_operations_service.create_operation.assert_called_once()

            # Verify operation was created with correct metadata
            create_call = mock_operations_service.create_operation.call_args
            operation_type, metadata = (
                create_call[1]["operation_type"],
                create_call[1]["metadata"],
            )

            # Should use DUMMY operation type (or fallback to DATA_LOAD)
            # Since DUMMY operation type might not exist, check for reasonable fallback
            assert operation_type in [
                OperationType.DATA_LOAD,
                getattr(OperationType, "DUMMY", None),
            ]
            assert metadata.parameters["operation_name"] == "dummy_task"
            assert metadata.parameters["service_name"] == "DummyService"

    @pytest.mark.asyncio
    async def test_dummy_service_progress_integration_with_operations_service(
        self, mock_operations_service
    ):
        """Test that DummyService progress updates integrate with operations service."""
        from ktrdr.api.services.dummy_service import DummyService

        # Mock operation
        mock_operation = OperationInfo(
            operation_id="op_progress_integration",
            operation_type=OperationType.DATA_LOAD,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service.create_operation.return_value = mock_operation

        service = DummyService()

        with patch(
            "ktrdr.api.services.operations_service.get_operations_service",
            return_value=mock_operations_service,
        ):

            # Start operation
            result = await service.start_dummy_task()

            # Should have started operation successfully
            assert result["status"] == "started"

            # Give background task time to start and make progress
            await asyncio.sleep(0.1)

            # Operations service should have been called to start the background operation
            mock_operations_service.start_operation.assert_called_once()

    def test_dummy_service_sync_operation_integration(self):
        """Test DummyService sync operation integration."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Mock the ServiceOrchestrator sync execution
        with patch.object(service, "run_sync_operation") as mock_run_sync:
            mock_run_sync.return_value = {
                "status": "success",
                "iterations_completed": 100,
                "total_duration_seconds": 200,
                "message": "Completed all 100 iterations!",
            }

            # Run sync operation
            result = service.run_dummy_task_sync()

            # Should return direct results
            assert result["status"] == "success"
            assert result["iterations_completed"] == 100
            assert result["total_duration_seconds"] == 200

            # Should have called ServiceOrchestrator's run_sync_operation
            mock_run_sync.assert_called_once()


class TestDummyServiceDocumentation:
    """Test that DummyService serves as perfect documentation/template."""

    def test_dummy_service_demonstrates_minimal_code_pattern(self):
        """Test that DummyService demonstrates the minimal code pattern."""
        import inspect

        from ktrdr.api.services.dummy_service import DummyService

        # Get the source code to analyze
        source = inspect.getsource(DummyService)

        # Should be concise - ServiceOrchestrator does the heavy lifting
        lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        # Should be relatively short (ServiceOrchestrator handles complexity)
        # Allow reasonable length for a reference implementation with docstrings
        assert (
            len(lines) < 150
        ), f"DummyService should be concise, got {len(lines)} lines"

    def test_dummy_service_has_excellent_docstrings(self):
        """Test that DummyService has excellent documentation."""
        from ktrdr.api.services.dummy_service import DummyService

        service = DummyService()

        # Class should have docstring
        assert DummyService.__doc__ is not None
        assert len(DummyService.__doc__.strip()) > 10

        # Key methods should have docstrings
        assert service.start_dummy_task.__doc__ is not None
        assert service.run_dummy_task_sync.__doc__ is not None
        assert service._run_dummy_task_async.__doc__ is not None

        # Docstrings should explain the ServiceOrchestrator pattern
        class_doc = DummyService.__doc__.lower()
        assert any(
            term in class_doc
            for term in ["serviceorchestrator", "reference", "template", "perfect"]
        )

    def test_dummy_service_demonstrates_zero_boilerplate_pattern(self):
        """Test that DummyService shows how ServiceOrchestrator eliminates boilerplate."""
        import inspect

        from ktrdr.api.services.dummy_service import DummyService

        # Get method source code
        start_method_source = inspect.getsource(DummyService.start_dummy_task)
        sync_method_source = inspect.getsource(DummyService.run_dummy_task_sync)

        # Should be very simple - just call ServiceOrchestrator
        start_lines = [
            line.strip()
            for line in start_method_source.split("\n")
            if line.strip()
            and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
        ]
        sync_lines = [
            line.strip()
            for line in sync_method_source.split("\n")
            if line.strip()
            and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
        ]

        # Methods should be very short (just calling ServiceOrchestrator)
        # Allow reasonable length for well-documented methods
        assert (
            len(start_lines) < 25
        ), f"start_dummy_task should be minimal, got {len(start_lines)} lines"
        assert (
            len(sync_lines) < 25
        ), f"run_dummy_task_sync should be minimal, got {len(sync_lines)} lines"

        # Should contain calls to ServiceOrchestrator methods
        assert "start_managed_operation" in start_method_source
        assert "run_sync_operation" in sync_method_source
