"""Tests for Agent Resume Logic (M7 Task 7.5).

Tests agent resume functionality:
- Resume from checkpoint loads correct state
- Resume restarts worker from correct phase
- Resume handles missing checkpoint gracefully
- Resume handles non-resumable states
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.checkpoint.schemas import AgentCheckpointState


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    def create_op(operation_type, metadata=None, parent_operation_id=None, status=None):
        """Create operation helper."""
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=status or OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None
    ):
        return create_op(operation_type, metadata, parent_operation_id)

    async def async_get_operation(operation_id):
        return operations.get(operation_id)

    async def async_complete_operation(operation_id, result=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.COMPLETED
            operations[operation_id].result_summary = result
            operations[operation_id].completed_at = datetime.now(timezone.utc)

    async def async_fail_operation(operation_id, error=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.FAILED
            operations[operation_id].error_message = error

    async def async_cancel_operation(operation_id, reason=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.CANCELLED
            operations[operation_id].error_message = reason

    async def async_start_operation(operation_id, task):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING
            operations[operation_id].started_at = datetime.now(timezone.utc)

    async def async_update_status(operation_id, status, **kwargs):
        if operation_id in operations:
            if isinstance(status, str):
                status = OperationStatus(status.upper())
            operations[operation_id].status = status

    async def async_try_resume(operation_id):
        """Optimistic lock for resume - returns True if status changed."""
        if operation_id not in operations:
            return False
        op = operations[operation_id]
        if op.status in [OperationStatus.CANCELLED, OperationStatus.FAILED]:
            op.status = OperationStatus.RESUMING
            return True
        return False

    async def async_list_operations(
        operation_type=None, status=None, limit=100, offset=0, active_only=False
    ):
        """List operations with filtering."""
        filtered = list(operations.values())

        if operation_type:
            filtered = [op for op in filtered if op.operation_type == operation_type]

        if status:
            filtered = [op for op in filtered if op.status == status]

        if active_only:
            filtered = [
                op
                for op in filtered
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]

        # Sort by created_at descending
        filtered.sort(key=lambda op: op.created_at, reverse=True)

        total_count = len(filtered)
        active_count = len(
            [
                op
                for op in operations.values()
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]
        )

        return filtered[offset : offset + limit], total_count, active_count

    async def async_update_progress(operation_id, progress):
        if operation_id in operations:
            operations[operation_id].progress = progress

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.cancel_operation = async_cancel_operation
    service.start_operation = async_start_operation
    service.update_status = async_update_status
    service.try_resume = async_try_resume
    service.list_operations = async_list_operations
    service.update_progress = async_update_progress
    service._operations = operations
    # Helper to directly add operations in specific states
    service._create_op = create_op

    return service


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock checkpoint service for testing."""
    service = AsyncMock()
    service.save_checkpoint = AsyncMock()
    service.load_checkpoint = AsyncMock(return_value=None)
    service.delete_checkpoint = AsyncMock()
    return service


@pytest.fixture(autouse=True)
def mock_budget():
    """Mock budget tracker to allow triggers in tests."""
    mock_tracker = MagicMock()
    mock_tracker.can_spend.return_value = (True, None)
    mock_tracker.record_spend = MagicMock()

    with patch(
        "ktrdr.api.services.agent_service.get_budget_tracker",
        return_value=mock_tracker,
    ):
        yield mock_tracker


class TestAgentResumeBasicFlow:
    """Test basic agent resume flow."""

    @pytest.mark.asyncio
    async def test_resume_loads_checkpoint(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume loads checkpoint and returns success."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a cancelled operation
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "test_strategy",
                }
            ),
            status=OperationStatus.CANCELLED,
        )

        # Set up checkpoint to return
        checkpoint_state = AgentCheckpointState(
            phase="training",
            strategy_name="test_strategy",
            strategy_path="/strategies/test.yaml",
            training_operation_id="op_training_123",
        )
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "cancellation"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume(op.operation_id)

        # Should have loaded checkpoint
        mock_checkpoint_service.load_checkpoint.assert_called_once_with(
            op.operation_id, load_artifacts=False
        )

        # Should return success
        assert result["success"] is True
        assert result["operation_id"] == op.operation_id
        assert result["resumed_from_phase"] == "training"

    @pytest.mark.asyncio
    async def test_resume_fails_when_no_checkpoint(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume fails gracefully when no checkpoint exists."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a failed operation
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
            status=OperationStatus.FAILED,
        )

        # No checkpoint exists
        mock_checkpoint_service.load_checkpoint.return_value = None

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume(op.operation_id)

        # Should return failure
        assert result["success"] is False
        assert result["reason"] == "no_checkpoint"
        assert "checkpoint" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_resume_fails_when_operation_not_found(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume fails when operation does not exist."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume("nonexistent_op_id")

        assert result["success"] is False
        assert result["reason"] == "not_found"


class TestAgentResumeStateValidation:
    """Test resume validates operation state correctly."""

    @pytest.mark.asyncio
    async def test_resume_fails_when_operation_running(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume fails when operation is already running."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a running operation
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
            status=OperationStatus.RUNNING,
        )

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume(op.operation_id)

        assert result["success"] is False
        assert result["reason"] == "not_resumable"
        assert "running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_resume_fails_when_operation_completed(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume fails when operation is already completed."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a completed operation
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "assessing"}),
            status=OperationStatus.COMPLETED,
        )

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume(op.operation_id)

        assert result["success"] is False
        assert result["reason"] == "not_resumable"
        assert "completed" in result["message"].lower()


class TestAgentResumeWorkerRestart:
    """Test that resume correctly restarts the worker."""

    @pytest.mark.asyncio
    async def test_resume_starts_worker_with_checkpoint_state(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume starts worker and passes checkpoint state."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a cancelled operation
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "momentum_v1",
                    "strategy_path": "/strategies/momentum.yaml",
                }
            ),
            status=OperationStatus.CANCELLED,
        )

        # Set up checkpoint
        checkpoint_state = AgentCheckpointState(
            phase="training",
            strategy_name="momentum_v1",
            strategy_path="/strategies/momentum.yaml",
            training_operation_id="op_training_789",
        )
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "cancellation"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        # Mock the worker to capture what it receives
        mock_worker = AsyncMock()
        mock_worker.run.return_value = {"success": True}
        with patch.object(service, "_get_worker", return_value=mock_worker):
            result = await service.resume(op.operation_id)

        # Should succeed
        assert result["success"] is True

        # Worker should have been started (start_operation called)
        assert mock_operations_service._operations[op.operation_id].status in [
            OperationStatus.RUNNING,
            OperationStatus.RESUMING,
        ]

    @pytest.mark.asyncio
    async def test_resume_updates_operation_metadata(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume updates operation metadata with checkpoint state."""
        from ktrdr.api.services.agent_service import AgentService

        # Create operation without full metadata (simulating state loss)
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
            status=OperationStatus.FAILED,
        )

        # Checkpoint has more complete state
        checkpoint_state = AgentCheckpointState(
            phase="backtesting",
            strategy_name="trend_follower",
            strategy_path="/strategies/trend.yaml",
            training_operation_id="op_training_abc",
            backtest_operation_id="op_backtest_def",
        )
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "failure"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        mock_worker = AsyncMock()
        mock_worker.run.return_value = {"success": True}
        with patch.object(service, "_get_worker", return_value=mock_worker):
            result = await service.resume(op.operation_id)

        assert result["success"] is True
        assert result["resumed_from_phase"] == "backtesting"


class TestAgentResumePhaseHandling:
    """Test resume handles different phases correctly."""

    @pytest.mark.asyncio
    async def test_resume_from_designing_phase(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Can resume from designing phase."""
        from ktrdr.api.services.agent_service import AgentService

        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
            status=OperationStatus.CANCELLED,
        )

        checkpoint_state = AgentCheckpointState(phase="designing")
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "cancellation"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        mock_worker = AsyncMock()
        mock_worker.run.return_value = {"success": True}
        with patch.object(service, "_get_worker", return_value=mock_worker):
            result = await service.resume(op.operation_id)

        assert result["success"] is True
        assert result["resumed_from_phase"] == "designing"

    @pytest.mark.asyncio
    async def test_resume_from_training_phase_includes_child_op(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume from training phase includes training operation ID."""
        from ktrdr.api.services.agent_service import AgentService

        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
            status=OperationStatus.FAILED,
        )

        checkpoint_state = AgentCheckpointState(
            phase="training",
            strategy_name="test",
            training_operation_id="op_training_child",
            training_checkpoint_epoch=15,
        )
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "failure"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        mock_worker = AsyncMock()
        mock_worker.run.return_value = {"success": True}
        with patch.object(service, "_get_worker", return_value=mock_worker):
            result = await service.resume(op.operation_id)

        assert result["success"] is True
        assert result["resumed_from_phase"] == "training"
        # Training child operation info should be in result
        assert "training_operation_id" in result or "child_operations" in result


class TestAgentResumeConflictHandling:
    """Test resume handles concurrent operations correctly."""

    @pytest.mark.asyncio
    async def test_resume_fails_when_active_cycle_exists(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Resume fails if there's already an active research cycle."""
        from ktrdr.api.services.agent_service import AgentService

        # Create an active operation
        active_op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
            status=OperationStatus.RUNNING,
        )

        # Create a cancelled operation to resume
        cancelled_op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
            status=OperationStatus.CANCELLED,
        )

        # Set up checkpoint for cancelled op
        checkpoint_state = AgentCheckpointState(phase="training")
        mock_checkpoint = MagicMock()
        mock_checkpoint.state = checkpoint_state.to_dict()
        mock_checkpoint.checkpoint_type = "cancellation"
        mock_checkpoint.created_at = datetime.now(timezone.utc)
        mock_checkpoint_service.load_checkpoint.return_value = mock_checkpoint

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        result = await service.resume(cancelled_op.operation_id)

        # Should fail because there's already an active cycle
        assert result["success"] is False
        assert result["reason"] == "active_cycle_exists"
        assert active_op.operation_id in result.get("active_operation_id", "")
