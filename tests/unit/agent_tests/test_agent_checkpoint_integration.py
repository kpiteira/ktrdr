"""Tests for Agent Checkpoint Integration (M7 Task 7.4, updated for v2.6 multi-research).

Tests checkpoint saving at:
- Failure in coordinator loop (in AgentResearchWorker)
- Cancellation (in AgentResearchWorker)
- Successful completion (checkpoint deleted in AgentResearchWorker)
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

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

    async def async_start_operation(operation_id, task=None):
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


class TestResearchWorkerCheckpointOnFailure:
    """Test checkpoint saved on failure in AgentResearchWorker coordinator loop."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_when_research_fails(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint is saved when a research operation fails in the coordinator loop."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        # Create worker with mock checkpoint service
        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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
        # Mark as running so it's picked up by the coordinator
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Mock _advance_research to raise an error
        worker._advance_research = AsyncMock(side_effect=WorkerError("Training failed"))

        # Run coordinator - it should save checkpoint on failure
        await worker.run()

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
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        worker._advance_research = AsyncMock(side_effect=WorkerError("Backtest failed"))

        await worker.run()

        # Verify checkpoint state includes phase info
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]
        assert state["phase"] == "backtesting"
        assert state["strategy_name"] == "momentum_v2"
        assert state["backtest_operation_id"] == "op_backtest_789"


class TestResearchWorkerCheckpointOnCancellation:
    """Test checkpoint saved on cancellation in AgentResearchWorker.

    M2 Error Isolation: Per-research CancelledError is handled per-research
    (mark cancelled, save checkpoint, continue others). Coordinator-level
    cancellation (task.cancel()) still saves checkpoints for all and re-raises.
    """

    @pytest.mark.asyncio
    async def test_checkpoint_saved_when_research_cancelled(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint is saved when a single research is cancelled (per-research handling).

        M2: CancelledError from _advance_research is handled per-research.
        The research is marked CANCELLED, checkpoint saved, and loop continues.
        """
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Mock _advance_research to raise CancelledError (per-research cancellation)
        worker._advance_research = AsyncMock(side_effect=asyncio.CancelledError())

        # M2: Per-research CancelledError is caught, does NOT propagate
        await worker.run()  # Should complete without raising

        # Checkpoint should have been saved with type "cancellation"
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == op.operation_id
        assert call_args[1]["checkpoint_type"] == "cancellation"

        # Operation should be marked CANCELLED
        assert (
            mock_operations_service._operations[op.operation_id].status
            == OperationStatus.CANCELLED
        )

    @pytest.mark.asyncio
    async def test_per_research_cancellation_continues_others(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Per-research cancellation doesn't stop other researches (M2 error isolation).

        When CancelledError is raised from _advance_research for one operation,
        only that operation gets checkpointed and cancelled. Others continue.
        """
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01  # Fast for testing

        # Create two active operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "backtesting"}),
        )
        mock_operations_service._operations[op1.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op2.operation_id].status = (
            OperationStatus.RUNNING
        )

        call_count = {op1.operation_id: 0, op2.operation_id: 0}

        async def selective_cancel(op):
            """Cancel op1 on first call, complete op2 on second call."""
            call_count[op.operation_id] += 1
            if op.operation_id == op1.operation_id:
                raise asyncio.CancelledError("Child cancelled")
            # op2 completes after 2 calls
            if call_count[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        worker._advance_research = AsyncMock(side_effect=selective_cancel)

        # Should complete without raising (per-research handling)
        await worker.run()

        # op1 should be cancelled with checkpoint
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.CANCELLED
        )
        # op2 should have continued and completed
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )
        # Only op1 should have checkpoint saved (op2 completed successfully)
        assert mock_checkpoint_service.save_checkpoint.call_count == 1
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == op1.operation_id


class TestResearchWorkerCheckpointStateShape:
    """Test that checkpoint state matches AgentCheckpointState schema."""

    @pytest.mark.asyncio
    async def test_checkpoint_state_has_required_fields(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Checkpoint state has all required AgentCheckpointState fields."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        worker._advance_research = AsyncMock(side_effect=WorkerError("Test failure"))

        await worker.run()

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
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )
        from ktrdr.checkpoint.schemas import AgentCheckpointState

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        worker._advance_research = AsyncMock(side_effect=WorkerError("Test failure"))

        await worker.run()

        call_args = mock_checkpoint_service.save_checkpoint.call_args
        state = call_args[1]["state"]

        # Should be able to deserialize without error
        checkpoint_state = AgentCheckpointState.from_dict(state)
        assert checkpoint_state.phase == "training"
        assert checkpoint_state.operation_type == "agent"


class TestResearchWorkerCheckpointOnSuccess:
    """Test that checkpoint is deleted when operation completes successfully."""

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_on_successful_completion(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Existing checkpoint is deleted when operation completes successfully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Call _delete_checkpoint directly to test
        await worker._delete_checkpoint(op.operation_id)

        # delete_checkpoint should have been called
        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
            op.operation_id
        )

    @pytest.mark.asyncio
    async def test_no_checkpoint_saved_on_success(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """No checkpoint is saved when research completes successfully (only deleted)."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )

        # Create operation that will complete on first advance
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Mock _advance_research to complete the operation (set status to COMPLETED)
        async def complete_op(operation):
            mock_operations_service._operations[operation.operation_id].status = (
                OperationStatus.COMPLETED
            )

        worker._advance_research = AsyncMock(side_effect=complete_op)

        await worker.run()

        # save_checkpoint should NOT have been called (no failure/cancellation)
        mock_checkpoint_service.save_checkpoint.assert_not_called()


class TestResearchWorkerCheckpointHelpers:
    """Test the checkpoint helper methods directly."""

    @pytest.mark.asyncio
    async def test_save_checkpoint_handles_missing_service(
        self, mock_operations_service
    ):
        """_save_checkpoint handles missing checkpoint service gracefully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        # Create worker WITHOUT checkpoint service
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=None,  # No checkpoint service
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )

        # Should not raise - just skip checkpoint save
        await worker._save_checkpoint(op.operation_id, "failure")
        # No assertion needed - we're just verifying it doesn't raise

    @pytest.mark.asyncio
    async def test_delete_checkpoint_handles_missing_service(
        self, mock_operations_service
    ):
        """_delete_checkpoint handles missing checkpoint service gracefully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        # Create worker WITHOUT checkpoint service
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=None,
        )

        # Should not raise - just skip checkpoint delete
        await worker._delete_checkpoint("op_123")
        # No assertion needed - we're just verifying it doesn't raise

    @pytest.mark.asyncio
    async def test_save_checkpoint_handles_missing_operation(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """_save_checkpoint handles non-existent operation gracefully."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design_worker = AsyncMock()
        mock_assessment_worker = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )

        # Try to save checkpoint for non-existent operation
        await worker._save_checkpoint("non_existent_op", "failure")

        # save_checkpoint should NOT have been called (operation not found)
        mock_checkpoint_service.save_checkpoint.assert_not_called()
