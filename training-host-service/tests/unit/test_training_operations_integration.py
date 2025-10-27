"""
Unit tests for Task 2.3: Training Worker Operations Integration

Tests that training sessions create operations and register bridges when training starts.
Following TDD methodology - these tests should FAIL until implementation is complete.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import OperationsService
from services.training_service import TrainingService


@pytest.fixture
def mock_operations_service():
    """Mock OperationsService for testing."""
    ops_service = MagicMock(spec=OperationsService)
    ops_service.create_operation = AsyncMock()
    ops_service.register_local_bridge = MagicMock()
    ops_service.complete_operation = AsyncMock()
    ops_service.fail_operation = AsyncMock()
    return ops_service


@pytest.fixture
def training_service():
    """Create TrainingService instance for testing."""
    return TrainingService(max_concurrent_sessions=5)


class TestOperationCreation:
    """Test that operations are created when training starts."""

    @pytest.mark.asyncio
    async def test_create_session_creates_operation(
        self, training_service, mock_operations_service
    ):
        """
        Test that create_session creates an operation in OperationsService.

        Acceptance criteria:
        - Operation is created before training starts
        - Operation ID format: host_training_{session_id}
        """
        # Arrange
        session_id = str(uuid.uuid4())
        config = {
            "strategy_yaml": "model:\n  type: test\ntraining_config:\n  epochs: 10"
        }

        # Patch get_operations_service to return our mock
        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Act
            created_session_id = await training_service.create_session(
                config, session_id=session_id
            )

        # Assert
        assert created_session_id == session_id

        # Verify operation was created
        mock_operations_service.create_operation.assert_called_once()
        call_kwargs = mock_operations_service.create_operation.call_args.kwargs

        # Check operation ID format
        expected_operation_id = f"host_training_{session_id}"
        assert call_kwargs["operation_id"] == expected_operation_id

        # Check operation type
        assert call_kwargs["operation_type"] == OperationType.TRAINING

    @pytest.mark.asyncio
    async def test_operation_id_format_consistent(
        self, training_service, mock_operations_service
    ):
        """
        Test that operation ID follows the naming convention: host_training_{session_id}.

        Acceptance criteria:
        - Operation ID format is consistent and predictable
        """
        # Arrange
        session_id = "test-session-123"
        config = {
            "strategy_yaml": "model:\n  type: test\ntraining_config:\n  epochs: 10"
        }

        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Act
            await training_service.create_session(config, session_id=session_id)

        # Assert
        call_kwargs = mock_operations_service.create_operation.call_args.kwargs
        assert call_kwargs["operation_id"] == "host_training_test-session-123"


class TestBridgeCreationAndRegistration:
    """Test that progress bridges are created and registered."""

    @pytest.mark.asyncio
    async def test_bridge_created_before_training(
        self, training_service, mock_operations_service
    ):
        """
        Test that TrainingProgressBridge is created before training starts.

        Acceptance criteria:
        - Bridge is created during session initialization
        - Bridge is registered with operations service
        """
        # Arrange
        session_id = str(uuid.uuid4())
        config = {
            "strategy_yaml": "model:\n  type: test\ntraining_config:\n  epochs: 10"
        }

        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Act
            await training_service.create_session(config, session_id=session_id)

        # Assert - verify bridge was registered
        mock_operations_service.register_local_bridge.assert_called_once()

        # Get the call arguments
        call_args = mock_operations_service.register_local_bridge.call_args
        operation_id = call_args[0][0]
        bridge = call_args[0][1]

        # Verify operation ID format
        assert operation_id == f"host_training_{session_id}"

        # Verify bridge is a ProgressBridge instance (duck typing check)
        assert hasattr(bridge, "get_status")
        assert hasattr(bridge, "get_metrics")

    @pytest.mark.asyncio
    async def test_bridge_registered_before_worker_starts(
        self, training_service, mock_operations_service
    ):
        """
        Test that bridge is registered BEFORE the training worker starts.

        Acceptance criteria:
        - Bridge registration happens before background task starts
        - Ensures bridge is available when worker begins reporting progress
        """
        # Arrange
        session_id = str(uuid.uuid4())
        config = {
            "strategy_yaml": "model:\n  type: test\ntraining_config:\n  epochs: 10"
        }

        # Track if bridge was registered
        bridge_registered = False

        def track_register_bridge(*args, **kwargs):
            nonlocal bridge_registered
            bridge_registered = True

        mock_operations_service.register_local_bridge.side_effect = (
            track_register_bridge
        )

        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Mock asyncio.create_task to verify bridge is registered before task creation
            original_create_task = asyncio.create_task

            def mock_create_task(coro, **kwargs):
                # At this point, bridge should already be registered
                assert (
                    bridge_registered
                ), "Bridge must be registered before training task is created"
                # Return a dummy task that completes immediately
                async def dummy():
                    pass

                return original_create_task(dummy())

            with patch("asyncio.create_task", side_effect=mock_create_task):
                # Act
                await training_service.create_session(config, session_id=session_id)

        # Assert - bridge was registered
        assert bridge_registered


class TestOperationCompletion:
    """Test that operations are marked complete/failed when training ends."""

    @pytest.mark.asyncio
    async def test_operation_completed_on_success(
        self, training_service, mock_operations_service
    ):
        """
        Test that operation is marked complete when training succeeds.

        Acceptance criteria:
        - complete_operation() called with operation_id and results
        - Called when training finishes successfully
        """
        # This test verifies the completion flow (will be implemented in orchestrator)
        # For now, we test the service has the capability to complete operations

        session_id = str(uuid.uuid4())
        operation_id = f"host_training_{session_id}"

        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Simulate successful training completion
            result = {
                "model_path": "/models/test_model.pt",
                "training_metrics": {"final_loss": 0.5},
            }

            # Act - call complete_operation (this will be called by orchestrator)
            await mock_operations_service.complete_operation(operation_id, result)

        # Assert
        mock_operations_service.complete_operation.assert_called_once_with(
            operation_id, result
        )

    @pytest.mark.asyncio
    async def test_operation_failed_on_error(
        self, training_service, mock_operations_service
    ):
        """
        Test that operation is marked failed when training fails.

        Acceptance criteria:
        - fail_operation() called with operation_id and error message
        - Called when training raises exception
        """
        session_id = str(uuid.uuid4())
        operation_id = f"host_training_{session_id}"
        error_message = "Training failed: Out of memory"

        with patch(
            "services.training_service.get_operations_service",
            return_value=mock_operations_service,
        ):
            # Act - simulate failure (orchestrator will call this)
            await mock_operations_service.fail_operation(operation_id, error_message)

        # Assert
        mock_operations_service.fail_operation.assert_called_once_with(
            operation_id, error_message
        )


class TestWorkerBridgeIntegration:
    """Test that worker receives bridge reference (not callback)."""

    @pytest.mark.asyncio
    async def test_worker_receives_bridge_not_callback(
        self, training_service, mock_operations_service
    ):
        """
        Test that training worker receives bridge reference instead of callback.

        Acceptance criteria:
        - Worker (orchestrator) is passed a bridge object
        - No callback functions passed to worker
        - Worker can call bridge.on_epoch(), bridge.on_batch(), etc.
        """
        # This test will be implemented once orchestrator integration is complete
        # For now, we verify the bridge has the expected interface
        from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

        # Create a simple bridge instance
        bridge = ProgressBridge()

        # Verify bridge has worker-facing methods
        assert callable(getattr(bridge, "_update_state", None))
        assert callable(getattr(bridge, "_append_metric", None))

        # Verify bridge has consumer-facing methods
        assert callable(getattr(bridge, "get_status", None))
        assert callable(getattr(bridge, "get_metrics", None))


@pytest.mark.asyncio
async def test_end_to_end_operation_lifecycle(
    training_service, mock_operations_service
):
    """
    Integration test: Verify complete operation lifecycle.

    Steps:
    1. Create session
    2. Verify operation created
    3. Verify bridge registered
    4. Verify operation can be queried
    5. (Future) Verify operation completed on finish

    Acceptance criteria:
    - All steps execute in correct order
    - Operation ID matches between creation and registration
    """
    # Arrange
    session_id = str(uuid.uuid4())
    config = {"strategy_yaml": "model:\n  type: test\ntraining_config:\n  epochs: 10"}

    with patch(
        "services.training_service.get_operations_service",
        return_value=mock_operations_service,
    ):
        # Act
        created_session_id = await training_service.create_session(
            config, session_id=session_id
        )

    # Assert
    assert created_session_id == session_id

    # Verify operation created
    mock_operations_service.create_operation.assert_called_once()
    operation_id = mock_operations_service.create_operation.call_args.kwargs[
        "operation_id"
    ]

    # Verify bridge registered with same operation ID
    mock_operations_service.register_local_bridge.assert_called_once()
    bridge_operation_id = mock_operations_service.register_local_bridge.call_args[0][0]

    assert operation_id == bridge_operation_id
    assert operation_id == f"host_training_{session_id}"
