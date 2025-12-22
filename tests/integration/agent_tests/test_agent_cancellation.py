"""Integration tests for agent cancellation - M6 Task 6.5.

Tests the full cancellation flow through AgentService:
- Cancellation works from any phase
- Child operations cleaned up
- New cycle can start after cancel
- Cancellation completes in <500ms

These tests use stub workers for speed and determinism.
"""

import asyncio
import time
from datetime import datetime, timezone

import pytest

from ktrdr.agents.workers.stubs import StubAssessmentWorker, StubDesignWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.agent_service import AgentService


class InMemoryOperationsService:
    """In-memory operations service for integration testing.

    Provides the same interface as OperationsService but keeps
    everything in memory for fast, isolated tests.
    """

    def __init__(self):
        self._operations: dict[str, OperationInfo] = {}
        self._counter = 0
        self._tasks: dict[str, asyncio.Task] = {}

    async def create_operation(
        self, operation_type, metadata=None, parent_operation_id=None
    ):
        """Create a new operation."""
        self._counter += 1
        op_id = f"op_{operation_type.value}_{self._counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        self._operations[op_id] = op
        return op

    async def get_operation(self, operation_id):
        """Get operation by ID."""
        return self._operations.get(operation_id)

    async def start_operation(self, operation_id, task):
        """Mark operation as running and track the task."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.RUNNING
            self._operations[operation_id].started_at = datetime.now(timezone.utc)
            self._tasks[operation_id] = task

    async def complete_operation(self, operation_id, result=None):
        """Mark operation as completed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.COMPLETED
            self._operations[operation_id].result_summary = result
            self._operations[operation_id].completed_at = datetime.now(timezone.utc)

    async def fail_operation(self, operation_id, error=None):
        """Mark operation as failed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.FAILED
            self._operations[operation_id].error_message = error
            self._operations[operation_id].completed_at = datetime.now(timezone.utc)

    async def cancel_operation(self, operation_id, reason=None):
        """Mark operation as cancelled and cancel the task."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.CANCELLED
            self._operations[operation_id].completed_at = datetime.now(timezone.utc)
            # Cancel the task if it exists
            task = self._tasks.get(operation_id)
            if task and not task.done():
                task.cancel()

    async def update_operation_metadata(self, operation_id, params: dict):
        """Update operation metadata parameters."""
        if operation_id in self._operations:
            op = self._operations[operation_id]
            if op.metadata.parameters is None:
                op.metadata.parameters = {}
            op.metadata.parameters.update(params)

    async def list_operations(
        self,
        status=None,
        operation_type=None,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False,
    ) -> tuple[list[OperationInfo], int, int]:
        """List operations with filtering.

        Returns:
            Tuple of (operations, total_count, active_count)
        """
        all_operations = list(self._operations.values())
        filtered_operations = all_operations

        if active_only:
            filtered_operations = [
                op
                for op in filtered_operations
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]

        if status:
            filtered_operations = [
                op for op in filtered_operations if op.status == status
            ]

        if operation_type:
            filtered_operations = [
                op for op in filtered_operations if op.operation_type == operation_type
            ]

        # Sort by creation date (newest first)
        filtered_operations.sort(key=lambda op: op.created_at, reverse=True)

        # Apply pagination
        total_count = len(filtered_operations)
        paginated_operations = filtered_operations[offset : offset + limit]

        # Count active operations
        active_count = len(
            [
                op
                for op in all_operations
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]
        )

        return paginated_operations, total_count, active_count


class MockTrainingService:
    """Mock training service that creates operations."""

    def __init__(self, ops_service, slow=False, metrics=None):
        self.ops = ops_service
        self.slow = slow
        self.metrics = metrics or {
            "success": True,
            "accuracy": 0.65,
            "final_loss": 0.35,
            "initial_loss": 0.85,
            "model_path": "/app/models/stub/model.pt",
        }

    async def start_training(self, **kwargs):
        """Start training operation."""
        op = await self.ops.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        if self.slow:
            # Don't complete immediately - let it run slowly
            async def slow_complete():
                for _ in range(100):
                    await asyncio.sleep(0.1)
                await self.ops.complete_operation(op.operation_id, self.metrics)

            asyncio.create_task(slow_complete())
        else:
            await self.ops.complete_operation(op.operation_id, self.metrics)
        return {"operation_id": op.operation_id}


class MockBacktestService:
    """Mock backtest service that creates operations."""

    def __init__(self, ops_service, slow=False, metrics=None):
        self.ops = ops_service
        self.slow = slow
        self.metrics = metrics or {
            "success": True,
            "metrics": {
                "sharpe_ratio": 1.2,
                "win_rate": 0.55,
                "max_drawdown_pct": 0.15,
                "total_return": 0.23,
            },
        }

    async def run_backtest(self, **kwargs):
        """Run backtest operation."""
        op = await self.ops.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        if self.slow:

            async def slow_complete():
                for _ in range(100):
                    await asyncio.sleep(0.1)
                await self.ops.complete_operation(op.operation_id, self.metrics)

            asyncio.create_task(slow_complete())
        else:
            await self.ops.complete_operation(op.operation_id, self.metrics)
        return {"operation_id": op.operation_id}


class SlowDesignWorker:
    """Design worker that runs slowly to allow cancellation testing."""

    def __init__(self, duration: float = 5.0):
        self.duration = duration

    async def run(self, *args, **kwargs):
        """Run slowly, checking for cancellation periodically."""
        steps = int(self.duration / 0.1)
        for _ in range(steps):
            await asyncio.sleep(0.1)
        return {
            "success": True,
            "strategy_name": "slow_strategy_v1",
            "strategy_path": "/app/strategies/slow_strategy_v1.yaml",
        }


@pytest.fixture
def ops_service():
    """Create an in-memory operations service."""
    return InMemoryOperationsService()


@pytest.fixture
def agent_service(ops_service):
    """Create AgentService with in-memory ops and stub workers."""
    from ktrdr.agents.workers.research_worker import AgentResearchWorker

    training = MockTrainingService(ops_service)
    backtest = MockBacktestService(ops_service)

    def create_worker():
        return AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=training,
            backtest_service=backtest,
        )

    service = AgentService(operations_service=ops_service)
    # Override worker creation
    service._get_worker = create_worker
    return service


@pytest.fixture
def slow_agent_service(ops_service):
    """Create AgentService with slow design worker for cancellation testing."""
    from ktrdr.agents.workers.research_worker import AgentResearchWorker

    training = MockTrainingService(ops_service)
    backtest = MockBacktestService(ops_service)

    def create_worker():
        return AgentResearchWorker(
            operations_service=ops_service,
            design_worker=SlowDesignWorker(duration=5.0),
            assessment_worker=StubAssessmentWorker(),
            training_service=training,
            backtest_service=backtest,
        )

    service = AgentService(operations_service=ops_service)
    service._get_worker = create_worker
    return service


@pytest.fixture
def slow_training_agent_service(ops_service):
    """Create AgentService with slow training for cancellation testing."""
    from ktrdr.agents.workers.research_worker import AgentResearchWorker

    training = MockTrainingService(ops_service, slow=True)
    backtest = MockBacktestService(ops_service)

    def create_worker():
        return AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=training,
            backtest_service=backtest,
        )

    service = AgentService(operations_service=ops_service)
    service._get_worker = create_worker
    return service


class TestCancelDuringDesigning:
    """Test cancellation during design phase."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_during_designing_phase(self, slow_agent_service, ops_service):
        """Cancel during design phase cancels the cycle."""
        # Trigger cycle
        result = await slow_agent_service.trigger()
        assert result["triggered"] is True
        op_id = result["operation_id"]

        # Wait for designing phase to start
        for _ in range(30):
            status = await slow_agent_service.get_status()
            if status.get("phase") == "designing":
                break
            await asyncio.sleep(0.1)

        assert status.get("phase") == "designing", "Should be in designing phase"

        # Cancel
        cancel_result = await slow_agent_service.cancel()
        assert cancel_result["success"] is True
        assert cancel_result["operation_id"] == op_id

        # Wait for cancellation to complete
        await asyncio.sleep(0.5)

        # Verify parent is cancelled
        op = await ops_service.get_operation(op_id)
        assert op.status == OperationStatus.CANCELLED


class TestCancelDuringTraining:
    """Test cancellation during training phase."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_during_training_phase(
        self, slow_training_agent_service, ops_service
    ):
        """Cancel during training phase cancels the cycle."""
        # Trigger cycle
        result = await slow_training_agent_service.trigger()
        assert result["triggered"] is True
        op_id = result["operation_id"]

        # Wait for training phase
        for _ in range(50):
            status = await slow_training_agent_service.get_status()
            if status.get("phase") == "training":
                break
            await asyncio.sleep(0.1)

        # Cancel
        cancel_result = await slow_training_agent_service.cancel()
        assert cancel_result["success"] is True

        # Wait for cancellation
        await asyncio.sleep(0.5)

        # Verify parent is cancelled
        parent_op = await ops_service.get_operation(op_id)
        assert parent_op.status == OperationStatus.CANCELLED


class TestCancelNoActiveCycle:
    """Test cancellation when no active cycle exists."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_no_active_cycle_returns_error(self, agent_service):
        """Cancel when no active cycle returns appropriate error."""
        result = await agent_service.cancel()
        assert result["success"] is False
        assert result["reason"] == "no_active_cycle"


class TestTriggerAfterCancel:
    """Test that new cycles can start after cancellation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_trigger_after_cancel_succeeds(self, slow_agent_service, ops_service):
        """Can trigger a new cycle after cancelling previous one."""
        # Start and cancel a cycle
        result1 = await slow_agent_service.trigger()
        op_id1 = result1["operation_id"]

        await asyncio.sleep(0.2)

        cancel_result = await slow_agent_service.cancel()
        assert cancel_result["success"] is True

        # Wait for cancellation to complete
        await asyncio.sleep(0.5)

        # Verify first cycle is cancelled
        op1 = await ops_service.get_operation(op_id1)
        assert op1.status == OperationStatus.CANCELLED

        # Should be able to trigger again
        result2 = await slow_agent_service.trigger()
        assert result2["triggered"] is True
        assert result2["operation_id"] != op_id1

        # Clean up - cancel the second cycle
        await slow_agent_service.cancel()


class TestCancellationSpeed:
    """Test that cancellation completes within 500ms."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancellation_completes_within_500ms(
        self, slow_agent_service, ops_service
    ):
        """Cancellation should complete within 500ms."""
        # Trigger cycle
        result = await slow_agent_service.trigger()
        op_id = result["operation_id"]

        # Wait for cycle to start
        await asyncio.sleep(0.2)

        # Time the cancellation
        start = time.time()
        cancel_result = await slow_agent_service.cancel()
        assert cancel_result["success"] is True

        # Wait for operation status to reflect cancellation
        for _ in range(10):
            op = await ops_service.get_operation(op_id)
            if op.status == OperationStatus.CANCELLED:
                break
            await asyncio.sleep(0.05)

        elapsed = time.time() - start
        assert elapsed < 0.5, f"Cancellation took {elapsed:.3f}s, expected < 0.5s"

        # Verify operation is cancelled
        op = await ops_service.get_operation(op_id)
        assert op.status == OperationStatus.CANCELLED


class TestChildOperationsCleanup:
    """Test that child operations are properly cleaned up on cancel."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_child_design_op_cancelled(self, slow_agent_service, ops_service):
        """Design child operation is cancelled when parent is cancelled."""
        # Trigger cycle
        result = await slow_agent_service.trigger()
        op_id = result["operation_id"]

        # Wait for designing phase
        for _ in range(30):
            status = await slow_agent_service.get_status()
            if status.get("phase") == "designing":
                break
            await asyncio.sleep(0.1)

        # Get design op ID
        parent_op = await ops_service.get_operation(op_id)
        design_op_id = parent_op.metadata.parameters.get("design_op_id")
        assert design_op_id is not None, "Design child should be created"

        # Cancel parent
        await slow_agent_service.cancel()

        # Wait for cancellation
        await asyncio.sleep(0.5)

        # Verify design child is cancelled
        design_op = await ops_service.get_operation(design_op_id)
        assert design_op.status == OperationStatus.CANCELLED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_returns_child_op_id(self, slow_agent_service, ops_service):
        """Cancel response includes the child operation ID that was cancelled."""
        # Trigger cycle
        result = await slow_agent_service.trigger()
        op_id = result["operation_id"]

        # Wait for designing phase
        for _ in range(30):
            status = await slow_agent_service.get_status()
            if status.get("phase") == "designing":
                break
            await asyncio.sleep(0.1)

        # Get expected child ID
        parent_op = await ops_service.get_operation(op_id)
        design_op_id = parent_op.metadata.parameters.get("design_op_id")

        # Cancel and verify response includes child ID
        cancel_result = await slow_agent_service.cancel()
        assert cancel_result["success"] is True
        assert cancel_result["child_cancelled"] == design_op_id
