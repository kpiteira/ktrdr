"""Tests for Agent Checkpoint Integration (M7 Task 7.4).

Tests checkpoint saving at:
- Phase transitions (in AgentResearchWorker)
- Cancellation (in AgentService._run_worker)
- Failure (in AgentService._run_worker)
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    def create_op(operation_type, metadata=None, parent_operation_id=None):
        """Create operation helper."""
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
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
    service.list_operations = async_list_operations
    service.update_progress = async_update_progress
    service._operations = operations

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


class TestAgentCheckpointOnFailure:
    """Test checkpoint saved on failure in AgentService._run_worker."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_when_worker_fails(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint is saved when worker raises an exception."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        # Create a mock worker that fails
        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = Exception("Worker failed")

        # Inject checkpoint service via constructor
        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        # Create an operation with phase state
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "test_strategy",
                    "training_op_id": "op_training_123",
                }
            ),
        )

        with pytest.raises(Exception, match="Worker failed"):
            await service._run_worker(op.operation_id, mock_worker)

        # Checkpoint should have been saved with type "failure"
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == op.operation_id
        assert call_args[1]["checkpoint_type"] == "failure"

    @pytest.mark.asyncio
    async def test_checkpoint_includes_phase_state_on_failure(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint state includes current phase and strategy info on failure."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = Exception("Worker failed")

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "backtesting",
                    "strategy_name": "momentum_v2",
                    "strategy_path": "/strategies/momentum_v2.yaml",
                    "training_op_id": "op_training_456",
                    "backtest_op_id": "op_backtest_789",
                }
            ),
        )

        with pytest.raises(Exception, match="Worker failed"):
            await service._run_worker(op.operation_id, mock_worker)

        # Verify checkpoint state includes phase info
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]
        assert state["phase"] == "backtesting"
        assert state["strategy_name"] == "momentum_v2"
        assert state["backtest_operation_id"] == "op_backtest_789"


class TestAgentCheckpointOnCancellation:
    """Test checkpoint saved on cancellation in AgentService._run_worker."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_when_worker_cancelled(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint is saved when worker is cancelled."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = asyncio.CancelledError()

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "model": "claude-opus-4-5-20251101",
                }
            ),
        )

        with pytest.raises(asyncio.CancelledError):
            await service._run_worker(op.operation_id, mock_worker)

        # Checkpoint should have been saved with type "cancellation"
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == op.operation_id
        assert call_args[1]["checkpoint_type"] == "cancellation"

    @pytest.mark.asyncio
    async def test_checkpoint_includes_phase_state_on_cancellation(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint state includes current phase on cancellation."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = asyncio.CancelledError()

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "rsi_crossover",
                    "training_op_id": "op_training_001",
                }
            ),
        )

        with pytest.raises(asyncio.CancelledError):
            await service._run_worker(op.operation_id, mock_worker)

        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]
        assert state["phase"] == "training"
        assert state["training_operation_id"] == "op_training_001"


class TestAgentCheckpointStateShape:
    """Test that checkpoint state matches AgentCheckpointState schema."""

    @pytest.mark.asyncio
    async def test_checkpoint_state_has_required_fields(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint state has all required AgentCheckpointState fields."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = Exception("Test failure")

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "strategy_name": "test_strat",
                    "strategy_path": "/path/to/strat.yaml",
                }
            ),
        )

        with pytest.raises(Exception, match="Test failure"):
            await service._run_worker(op.operation_id, mock_worker)

        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]

        # Verify required fields from AgentCheckpointState
        assert "phase" in state
        assert "operation_type" in state
        assert state["operation_type"] == "agent"

    @pytest.mark.asyncio
    async def test_checkpoint_state_can_be_deserialized(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint state can be deserialized to AgentCheckpointState."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService
        from ktrdr.checkpoint.schemas import AgentCheckpointState

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = Exception("Test failure")

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "my_strategy",
                    "training_op_id": "op_training_x",
                }
            ),
        )

        with pytest.raises(Exception, match="Test failure"):
            await service._run_worker(op.operation_id, mock_worker)

        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]

        # Should be able to deserialize without error
        checkpoint_state = AgentCheckpointState.from_dict(state)
        assert checkpoint_state.phase == "training"
        assert checkpoint_state.operation_type == "agent"


class TestAgentCheckpointNotSavedOnSuccess:
    """Test that checkpoint is NOT saved when operation completes successfully."""

    @pytest.mark.asyncio
    async def test_no_checkpoint_on_successful_completion(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """No checkpoint is saved when worker completes successfully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.return_value = {
            "success": True,
            "strategy_name": "completed_strategy",
        }

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        await service._run_worker(op.operation_id, mock_worker)

        # save_checkpoint should NOT have been called
        mock_checkpoint_service.save_checkpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_on_successful_completion(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Existing checkpoint is deleted when operation completes successfully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.return_value = {"success": True}

        service = AgentService(
            operations_service=mock_operations_service,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        await service._run_worker(op.operation_id, mock_worker)

        # delete_checkpoint should have been called to clean up
        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
            op.operation_id
        )


class TestAgentCheckpointAtPhaseTransitions:
    """Test checkpoint saved at phase transitions in AgentResearchWorker."""

    @pytest.fixture
    def mock_worker_dependencies(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Set up mock dependencies for AgentResearchWorker."""
        mock_design_worker = AsyncMock()
        mock_design_worker.run.return_value = {
            "success": True,
            "strategy_name": "test_strategy",
            "strategy_path": "/strategies/test.yaml",
        }

        mock_assessment_worker = AsyncMock()
        mock_training_service = AsyncMock()
        mock_backtest_service = AsyncMock()

        return {
            "ops": mock_operations_service,
            "checkpoint_service": mock_checkpoint_service,
            "design_worker": mock_design_worker,
            "assessment_worker": mock_assessment_worker,
            "training_service": mock_training_service,
            "backtest_service": mock_backtest_service,
        }

    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_design_phase_completes(
        self, mock_worker_dependencies
    ):
        """Checkpoint is saved after design phase transitions to training."""
        # This test verifies that when design phase completes,
        # a checkpoint is saved before starting training.
        # The implementation should add checkpoint save in _handle_designing_phase
        # or _start_training in AgentResearchWorker.
        pytest.skip("Test to be implemented after verifying worker structure")

    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_training_phase_completes(
        self, mock_worker_dependencies
    ):
        """Checkpoint is saved after training phase transitions to backtesting."""
        pytest.skip("Test to be implemented after verifying worker structure")

    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_backtest_phase_completes(
        self, mock_worker_dependencies
    ):
        """Checkpoint is saved after backtest phase transitions to assessment."""
        pytest.skip("Test to be implemented after verifying worker structure")
