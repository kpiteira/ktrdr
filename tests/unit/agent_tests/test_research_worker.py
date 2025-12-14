"""Tests for AgentResearchWorker orchestrator.

Task 1.3 of M1: Verify the orchestrator manages phases and tracks child operations.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
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

    def create_op(operation_type, metadata=None, parent_operation_id=None):
        """Create operation helper."""
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

    async def async_fail_operation(operation_id, error=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.FAILED
            operations[operation_id].error_message = error

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service._operations = operations

    return service


@pytest.fixture
def stub_workers():
    """Create stub workers for testing."""
    from ktrdr.agents.workers.stubs import (
        StubAssessmentWorker,
        StubBacktestWorker,
        StubDesignWorker,
        StubTrainingWorker,
    )

    return {
        "design": StubDesignWorker(),
        "training": StubTrainingWorker(),
        "backtest": StubBacktestWorker(),
        "assessment": StubAssessmentWorker(),
    }


class TestAgentResearchWorkerPhases:
    """Test phase transitions through the orchestrator."""

    @pytest.mark.asyncio
    async def test_completes_all_phases(self, mock_operations_service, stub_workers):
        """Worker transitions through all phases and completes."""
        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        result = await worker.run(parent_op.operation_id)

        assert result["success"] is True
        assert "strategy_name" in result
        assert "verdict" in result

    @pytest.mark.asyncio
    async def test_phase_updates_in_metadata(
        self, mock_operations_service, stub_workers
    ):
        """Phase updates are stored in operation metadata."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        phases_seen = []

        # Track phase changes by patching
        original_get = mock_operations_service.get_operation

        async def tracking_get(op_id):
            op = await original_get(op_id)
            if op and op.operation_id == parent_op.operation_id:
                phase = op.metadata.parameters.get("phase")
                if phase and (not phases_seen or phases_seen[-1] != phase):
                    phases_seen.append(phase)
            return op

        mock_operations_service.get_operation = tracking_get

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        await worker.run(parent_op.operation_id)

        # Should see all phases
        assert "designing" in phases_seen
        assert "training" in phases_seen
        assert "backtesting" in phases_seen
        assert "assessing" in phases_seen


class TestAgentResearchWorkerChildOperations:
    """Test child operation tracking."""

    @pytest.mark.asyncio
    async def test_child_operation_ids_stored(
        self, mock_operations_service, stub_workers
    ):
        """Child operation IDs are stored in parent metadata."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        await worker.run(parent_op.operation_id)

        # Get final parent state
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        params = parent.metadata.parameters

        assert "design_op_id" in params
        assert "training_op_id" in params
        assert "backtest_op_id" in params
        assert "assessment_op_id" in params

    @pytest.mark.asyncio
    async def test_child_operations_completed(
        self, mock_operations_service, stub_workers
    ):
        """Child operations are marked as completed."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        await worker.run(parent_op.operation_id)

        # Check all child operations are completed
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        for key in [
            "design_op_id",
            "training_op_id",
            "backtest_op_id",
            "assessment_op_id",
        ]:
            child_id = parent.metadata.parameters.get(key)
            if child_id:
                child = await mock_operations_service.get_operation(child_id)
                assert child.status == OperationStatus.COMPLETED


class TestAgentResearchWorkerCancellation:
    """Test cancellation behavior."""

    @pytest.mark.asyncio
    async def test_cancellation_responsive(self, mock_operations_service):
        """Worker responds to cancellation within 200ms."""

        # Create slow worker that checks for cancellation
        class SlowWorker:
            async def run(self, *args, **kwargs):
                # Sleep in small chunks to allow cancellation
                for _ in range(50):  # 5 seconds total
                    await asyncio.sleep(0.1)
                return {"success": True}

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=SlowWorker(),
            training_worker=SlowWorker(),
            backtest_worker=SlowWorker(),
            assessment_worker=SlowWorker(),
        )

        # Start the worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait a bit then cancel
        await asyncio.sleep(0.15)
        start = time.time()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        elapsed = time.time() - start
        # Should cancel within 200ms
        assert (
            elapsed < 0.2
        ), f"Cancellation took {elapsed*1000:.0f}ms, expected < 200ms"


class TestAgentResearchWorkerErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_child_failure_propagates(
        self, mock_operations_service, stub_workers
    ):
        """Child failure causes parent to fail."""

        class FailingWorker:
            async def run(self, *args, **kwargs):
                raise ValueError("Simulated failure")

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=FailingWorker(),  # First phase fails
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        with pytest.raises(ValueError, match="Simulated failure"):
            await worker.run(parent_op.operation_id)

    @pytest.mark.asyncio
    async def test_failed_child_marked_failed(
        self, mock_operations_service, stub_workers
    ):
        """When child fails, it's marked as failed in operations."""

        class FailingWorker:
            async def run(self, *args, **kwargs):
                raise ValueError("Simulated failure")

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=FailingWorker(),
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        try:
            await worker.run(parent_op.operation_id)
        except ValueError:
            pass

        # Check design child is marked failed
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        design_op_id = parent.metadata.parameters.get("design_op_id")
        if design_op_id:
            design_op = await mock_operations_service.get_operation(design_op_id)
            assert design_op.status == OperationStatus.FAILED
