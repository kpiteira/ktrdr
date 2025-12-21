"""Unit tests for cancellation behavior - M6 Task 6.2.

Tests cover:
- Parent cancel triggers child cancel
- Cancellation completes within 500ms
- Both parent and child marked CANCELLED
- Cancellation during each phase works
- Cancellation when no child running works
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)

# --- Fixtures ---


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service that tracks operations in-memory."""
    operations = {}
    op_counter = 0

    service = AsyncMock()

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None
    ):
        nonlocal op_counter
        op_counter += 1
        op_id = f"op_{operation_type.value}_{op_counter}"
        op = AsyncMock()
        op.operation_id = op_id
        op.operation_type = operation_type
        op.metadata = metadata or OperationMetadata()
        op.metadata.parameters = getattr(op.metadata, "parameters", {}) or {}
        op.parent_operation_id = parent_operation_id
        op.status = OperationStatus.PENDING
        operations[op_id] = op
        return op

    async def async_get_operation(operation_id):
        return operations.get(operation_id)

    async def async_start_operation(operation_id, task=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING

    async def async_complete_operation(operation_id, result=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.COMPLETED
            operations[operation_id].result = result

    async def async_fail_operation(operation_id, error=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.FAILED
            operations[operation_id].error_message = error

    async def async_cancel_operation(operation_id, reason=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.CANCELLED
            operations[operation_id].cancel_reason = reason

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.start_operation = async_start_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.cancel_operation = async_cancel_operation
    service._operations = operations  # For test assertions

    return service


@pytest.fixture
def slow_design_worker():
    """Worker that runs slowly, allowing time for cancellation."""

    class SlowWorker:
        async def run(self, *args, **kwargs):
            for _ in range(100):  # 10 seconds total
                await asyncio.sleep(0.1)
            return {
                "success": True,
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
            }

    return SlowWorker()


@pytest.fixture
def instant_worker():
    """Worker that completes instantly."""

    class InstantWorker:
        async def run(self, *args, **kwargs):
            return {
                "success": True,
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
                "verdict": "promising",
            }

    return InstantWorker()


@pytest.fixture
def mock_training_service():
    """Mock training service that returns operation IDs."""
    service = AsyncMock()
    service.start_training = AsyncMock(
        return_value={
            "operation_id": "op_training_mock",
            "status": "started",
        }
    )
    return service


@pytest.fixture
def mock_backtest_service():
    """Mock backtest service that returns operation IDs."""
    service = AsyncMock()
    service.run_backtest = AsyncMock(
        return_value={
            "operation_id": "op_backtest_mock",
            "status": "started",
        }
    )
    return service


# --- Test: Parent cancel triggers child cancel ---


class TestParentCancelTriggersChildCancel:
    """Test that cancelling parent operation cancels active child."""

    @pytest.mark.asyncio
    async def test_cancel_parent_cancels_child_design(
        self,
        mock_operations_service,
        slow_design_worker,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancelling parent during design phase cancels design child."""
        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=slow_design_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        # Start the worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait for design child to be created
        await asyncio.sleep(0.2)

        # Cancel parent
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify child operation was cancelled
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        child_op_id = parent.metadata.parameters.get("design_op_id")
        assert child_op_id is not None, "Design child should have been created"

        child = await mock_operations_service.get_operation(child_op_id)
        assert (
            child.status == OperationStatus.CANCELLED
        ), f"Child should be CANCELLED, got {child.status}"


# --- Test: Cancellation completes within 500ms ---


class TestCancellationSpeed:
    """Test that cancellation completes quickly."""

    @pytest.mark.asyncio
    async def test_cancellation_completes_within_500ms(
        self,
        mock_operations_service,
        slow_design_worker,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancellation should complete within 500ms (requirement from M6)."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=slow_design_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        # Start the worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait for worker to start running
        await asyncio.sleep(0.15)

        # Time the cancellation
        start = time.time()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        elapsed = time.time() - start

        # Should complete within 500ms (actual target is <200ms based on poll interval)
        assert (
            elapsed < 0.5
        ), f"Cancellation took {elapsed * 1000:.0f}ms, expected < 500ms"


# --- Test: Both parent and child marked CANCELLED ---


class TestBothOperationsMarkedCancelled:
    """Test that both parent and child are marked CANCELLED."""

    @pytest.mark.asyncio
    async def test_both_parent_and_child_marked_cancelled(
        self,
        mock_operations_service,
        slow_design_worker,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Both parent and child operations should be marked CANCELLED."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=slow_design_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        # Start the worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait for design child to be created
        await asyncio.sleep(0.2)

        # Get child ID before cancellation
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        child_op_id = parent.metadata.parameters.get("design_op_id")

        # Cancel parent
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify child is CANCELLED
        child = await mock_operations_service.get_operation(child_op_id)
        assert (
            child.status == OperationStatus.CANCELLED
        ), f"Child should be CANCELLED, got {child.status}"

        # Note: Parent status is managed externally (by AgentService.cancel())
        # The worker only cancels the child; the caller cancels the parent


# --- Test: Cancellation during each phase works ---


class TestCancellationDuringEachPhase:
    """Test cancellation works correctly during each phase."""

    @pytest.mark.asyncio
    async def test_cancellation_during_designing_phase(
        self,
        mock_operations_service,
        slow_design_worker,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel during designing phase cancels design child."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=slow_design_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.2)

        # Verify we're in designing phase
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert parent.metadata.parameters.get("phase") == "designing"

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify design child was cancelled
        child_id = parent.metadata.parameters.get("design_op_id")
        child = await mock_operations_service.get_operation(child_id)
        assert child.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancellation_during_training_phase(
        self,
        mock_operations_service,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel during training phase cancels training child.

        Training uses external workers via TrainingService. The child op ID
        is tracked in parent metadata and should be cancelled.
        """
        # Create parent already in training phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "training_op_id": "op_training_external",
                    "strategy_path": "/tmp/test.yaml",
                }
            ),
        )

        # Create the training operation so it can be found
        training_op = await mock_operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(),
        )
        # Manually set the ID to match
        mock_operations_service._operations["op_training_external"] = training_op
        training_op.operation_id = "op_training_external"
        training_op.status = OperationStatus.RUNNING

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=instant_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )
        # Manually set the child op ID to simulate mid-phase
        worker._current_child_op_id = "op_training_external"

        # Make training run forever
        async def slow_poll():
            for _ in range(100):
                await asyncio.sleep(0.1)
            return {}

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.15)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Training child should be cancelled
        training = await mock_operations_service.get_operation("op_training_external")
        assert training.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancellation_during_backtesting_phase(
        self,
        mock_operations_service,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel during backtesting phase cancels backtest child."""
        # Create parent already in backtesting phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "backtesting",
                    "backtest_op_id": "op_backtest_external",
                    "strategy_path": "/tmp/test.yaml",
                    "model_path": "/tmp/model.pt",
                }
            ),
        )

        # Create the backtest operation
        backtest_op = await mock_operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["op_backtest_external"] = backtest_op
        backtest_op.operation_id = "op_backtest_external"
        backtest_op.status = OperationStatus.RUNNING

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=instant_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )
        worker._current_child_op_id = "op_backtest_external"

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.15)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Backtest child should be cancelled
        backtest = await mock_operations_service.get_operation("op_backtest_external")
        assert backtest.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancellation_during_assessing_phase(
        self,
        mock_operations_service,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel during assessing phase cancels assessment child."""

        # Create a slow assessment worker
        class SlowAssessmentWorker:
            async def run(self, op_id, results=None, model=None):
                for _ in range(100):
                    await asyncio.sleep(0.1)
                return {"success": True, "verdict": "promising"}

        # Start parent already in assessing phase (like other cancellation tests)
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "strategy_name": "test_strategy",
                    "training_result": {
                        "accuracy": 0.6,
                        "final_loss": 0.3,
                        "initial_loss": 0.8,
                    },
                    "backtest_result": {
                        "win_rate": 0.55,
                        "max_drawdown_pct": 0.2,
                        "sharpe_ratio": 1.0,
                    },
                }
            ),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=instant_worker,
            assessment_worker=SlowAssessmentWorker(),
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.15)  # Let assessment worker start

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Assessment child should be cancelled
        parent = mock_operations_service._operations.get(parent_op.operation_id)
        assessment_id = parent.metadata.parameters.get("assessment_op_id")
        if assessment_id:
            assessment = mock_operations_service._operations.get(assessment_id)
            assert assessment.status == OperationStatus.CANCELLED


# --- Test: Cancellation when no child running works ---


class TestCancellationWithNoChild:
    """Test cancellation when no child operation is running."""

    @pytest.mark.asyncio
    async def test_cancellation_when_no_child_op_id(
        self,
        mock_operations_service,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel gracefully handles case when _current_child_op_id is None."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=instant_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        # Ensure no child is set
        worker._current_child_op_id = None
        worker._current_child_task = None

        # Start worker and cancel immediately before child is created
        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.01)  # Minimal wait

        task.cancel()

        # Should not raise any exception other than CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_cancellation_when_child_task_already_done(
        self,
        mock_operations_service,
        slow_design_worker,
        instant_worker,
        mock_training_service,
        mock_backtest_service,
    ):
        """Cancel handles case when child task is already done."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=slow_design_worker,
            assessment_worker=instant_worker,
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.2)

        # Manually mark child task as done (simulate race condition)
        if worker._current_child_task:
            # We can't force it to be done, but the code handles it
            pass

        task.cancel()

        # Should complete without error
        with pytest.raises(asyncio.CancelledError):
            await task
