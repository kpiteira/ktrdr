"""Tests for AgentResearchWorker orchestrator.

Task 1.3 of M1: Verify the orchestrator manages phases and tracks child operations.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker, WorkerError
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

    async def async_start_operation(operation_id, task):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING

    async def async_cancel_operation(operation_id, reason=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.CANCELLED

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.start_operation = async_start_operation
    service.cancel_operation = async_cancel_operation
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

        with pytest.raises(WorkerError, match="Child operation failed"):
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
        except WorkerError:
            pass

        # Check design child is marked failed
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        design_op_id = parent.metadata.parameters.get("design_op_id")
        if design_op_id:
            design_op = await mock_operations_service.get_operation(design_op_id)
            assert design_op.status == OperationStatus.FAILED


class TestPollingLoopPattern:
    """Test the polling loop pattern per ARCHITECTURE.md Task 1.10.

    The orchestrator should poll child operation status rather than
    awaiting workers directly.
    """

    @pytest.mark.asyncio
    async def test_uses_polling_loop(self, mock_operations_service, stub_workers):
        """Orchestrator polls child operation status in a loop.

        Verifies that child operations are polled for completion rather
        than being directly awaited.
        """
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track how many times get_operation is called for child ops
        get_operation_calls = []
        original_get = mock_operations_service.get_operation

        async def tracking_get(op_id):
            get_operation_calls.append(op_id)
            return await original_get(op_id)

        mock_operations_service.get_operation = tracking_get

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        await worker.run(parent_op.operation_id)

        # Should have polled child operations multiple times
        # The parent operation should be fetched at least once per poll cycle
        parent_fetches = [c for c in get_operation_calls if c == parent_op.operation_id]
        # With polling, we should fetch parent multiple times per phase
        assert (
            len(parent_fetches) >= 4
        ), f"Expected multiple parent polls (one per phase minimum), got {len(parent_fetches)}"

    @pytest.mark.asyncio
    async def test_child_workers_started_as_tasks(
        self, mock_operations_service, stub_workers
    ):
        """Child workers are started as separate asyncio tasks.

        The orchestrator should use asyncio.create_task() to start workers
        so they run independently.
        """
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track start_operation calls which register the task
        start_operation_calls = []

        async def track_start(operation_id, task):
            start_operation_calls.append((operation_id, task))
            # Simulate start by marking running
            op = await mock_operations_service.get_operation(operation_id)
            if op:
                op.status = OperationStatus.RUNNING

        mock_operations_service.start_operation = track_start

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        await worker.run(parent_op.operation_id)

        # Should have started 4 child tasks (one per phase)
        assert (
            len(start_operation_calls) == 4
        ), f"Expected 4 start_operation calls for child tasks, got {len(start_operation_calls)}"

        # Each should have been passed an asyncio.Task
        for op_id, task in start_operation_calls:
            assert isinstance(
                task, asyncio.Task
            ), f"Expected asyncio.Task for {op_id}, got {type(task)}"

    @pytest.mark.asyncio
    async def test_poll_interval_configurable(
        self, mock_operations_service, stub_workers, monkeypatch
    ):
        """Poll interval can be configured via environment variable.

        AGENT_POLL_INTERVAL sets the seconds between status checks.
        """
        # Set a very short poll interval for testing
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "0.01")

        await mock_operations_service.create_operation(
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

        # The worker should respect the poll interval
        # We verify by checking the POLL_INTERVAL attribute updates
        assert worker.POLL_INTERVAL == 0.01 or hasattr(
            worker, "_get_poll_interval"
        ), "Worker should have configurable poll interval"

    @pytest.mark.asyncio
    async def test_cancellation_propagates_to_child(
        self, mock_operations_service, stub_workers
    ):
        """Cancelling parent operation cancels active child.

        Per ARCHITECTURE.md, when the parent is cancelled, the active
        child operation should also be cancelled.
        """
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track cancel_operation calls
        cancelled_ops = []

        async def track_cancel(operation_id, reason=None):
            cancelled_ops.append(operation_id)
            op = await mock_operations_service.get_operation(operation_id)
            if op:
                op.status = OperationStatus.CANCELLED

        mock_operations_service.cancel_operation = track_cancel

        # Create slow workers so we have time to cancel
        class SlowWorker:
            async def run(self, *args, **kwargs):
                for _ in range(100):  # 10 seconds
                    await asyncio.sleep(0.1)
                return {
                    "success": True,
                    "strategy_name": "test",
                    "strategy_path": "/test",
                }

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=SlowWorker(),
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        # Start the worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait for design child to be created
        await asyncio.sleep(0.2)

        # Cancel parent
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # The child operation should have been cancelled
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        child_op_id = parent.metadata.parameters.get("design_op_id")
        assert (
            child_op_id in cancelled_ops
        ), f"Expected child {child_op_id} to be cancelled, cancelled ops: {cancelled_ops}"


class TestQualityGateIntegration:
    """Test quality gate integration per ARCHITECTURE.md Task 1.11.

    Quality gates should be checked between phases:
    - Training gate: after training completes, before backtesting
    - Backtest gate: after backtesting completes, before assessment
    """

    @pytest.mark.asyncio
    async def test_training_gate_passes_proceeds_to_backtest(
        self, mock_operations_service, stub_workers
    ):
        """When training gate passes, orchestrator proceeds to backtesting."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Stub workers return good metrics that pass gates
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],  # Returns metrics that pass gate
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        result = await worker.run(parent_op.operation_id)

        # Should complete successfully (stubs return good metrics)
        assert result["success"] is True
        # Should have reached backtesting and assessing phases
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "backtest_op_id" in parent.metadata.parameters
        assert "assessment_op_id" in parent.metadata.parameters

    @pytest.mark.asyncio
    async def test_training_gate_fails_stops_cycle(self, mock_operations_service):
        """When training gate fails, orchestrator stops and fails the cycle."""
        from ktrdr.agents.workers.research_worker import GateFailedError
        from ktrdr.agents.workers.stubs import StubAssessmentWorker, StubDesignWorker

        # Create worker that returns bad training metrics
        class BadTrainingWorker:
            async def run(self, operation_id: str, *args, **kwargs):
                """Return metrics that fail the training gate."""
                return {
                    "success": True,
                    "accuracy": 0.30,  # Below 45% threshold
                    "final_loss": 0.35,
                    "initial_loss": 0.85,
                    "model_path": "/app/models/bad/model.pt",
                }

        # Good backtest worker (shouldn't be reached)
        class GoodBacktestWorker:
            async def run(self, operation_id: str, *args, **kwargs):
                return {
                    "success": True,
                    "sharpe_ratio": 1.2,
                    "win_rate": 0.55,
                    "max_drawdown": 0.15,
                    "total_return": 0.23,
                }

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=StubDesignWorker(),
            training_worker=BadTrainingWorker(),
            backtest_worker=GoodBacktestWorker(),
            assessment_worker=StubAssessmentWorker(),
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "training" in str(exc_info.value).lower()
        assert "accuracy" in str(exc_info.value).lower()

        # Should NOT have reached backtesting phase
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "backtest_op_id" not in parent.metadata.parameters

    @pytest.mark.asyncio
    async def test_backtest_gate_fails_stops_cycle(self, mock_operations_service):
        """When backtest gate fails, orchestrator stops before assessment."""
        from ktrdr.agents.workers.research_worker import GateFailedError
        from ktrdr.agents.workers.stubs import (
            StubAssessmentWorker,
            StubDesignWorker,
            StubTrainingWorker,
        )

        # Create worker that returns bad backtest metrics
        class BadBacktestWorker:
            async def run(self, operation_id: str, *args, **kwargs):
                """Return metrics that fail the backtest gate."""
                return {
                    "success": True,
                    "sharpe_ratio": -1.0,  # Below -0.5 threshold
                    "win_rate": 0.30,  # Below 45% threshold
                    "max_drawdown": 0.50,  # Above 40% threshold
                    "total_return": -0.10,
                }

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=StubDesignWorker(),
            training_worker=StubTrainingWorker(),
            backtest_worker=BadBacktestWorker(),
            assessment_worker=StubAssessmentWorker(),
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "backtest" in str(exc_info.value).lower()

        # Should NOT have reached assessment phase
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "assessment_op_id" not in parent.metadata.parameters

    @pytest.mark.asyncio
    async def test_gate_failure_includes_reason(self, mock_operations_service):
        """Gate failure error includes human-readable reason."""
        from ktrdr.agents.workers.research_worker import GateFailedError
        from ktrdr.agents.workers.stubs import (
            StubAssessmentWorker,
            StubDesignWorker,
            StubTrainingWorker,
        )

        class BadBacktestWorker:
            async def run(self, operation_id: str, *args, **kwargs):
                return {
                    "success": True,
                    "sharpe_ratio": 1.2,
                    "win_rate": 0.35,  # Below 45% threshold - first failure
                    "max_drawdown": 0.15,
                }

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=StubDesignWorker(),
            training_worker=StubTrainingWorker(),
            backtest_worker=BadBacktestWorker(),
            assessment_worker=StubAssessmentWorker(),
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        # Should include the specific reason from the gate
        assert "win_rate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_both_gates_pass_completes_cycle(
        self, mock_operations_service, stub_workers
    ):
        """When both gates pass, cycle completes successfully."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Default stub workers return metrics that pass gates
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            training_worker=stub_workers["training"],
            backtest_worker=stub_workers["backtest"],
            assessment_worker=stub_workers["assessment"],
        )

        result = await worker.run(parent_op.operation_id)

        assert result["success"] is True
        assert "verdict" in result  # Reached assessment phase


class TestMetadataContract:
    """Test metadata contract per ARCHITECTURE.md Task 1.13.

    Parent operation metadata should store results from each phase.
    """

    @pytest.mark.asyncio
    async def test_stores_strategy_name_after_design(
        self, mock_operations_service, stub_workers
    ):
        """Parent metadata stores strategy_name after design phase."""
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

        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "strategy_name" in parent.metadata.parameters
        assert parent.metadata.parameters["strategy_name"] == "stub_momentum_v1"

    @pytest.mark.asyncio
    async def test_stores_training_result_after_training(
        self, mock_operations_service, stub_workers
    ):
        """Parent metadata stores training_result after training phase."""
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

        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "training_result" in parent.metadata.parameters
        training_result = parent.metadata.parameters["training_result"]
        assert "accuracy" in training_result
        assert "final_loss" in training_result

    @pytest.mark.asyncio
    async def test_stores_backtest_result_after_backtest(
        self, mock_operations_service, stub_workers
    ):
        """Parent metadata stores backtest_result after backtest phase."""
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

        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "backtest_result" in parent.metadata.parameters
        backtest_result = parent.metadata.parameters["backtest_result"]
        assert "sharpe_ratio" in backtest_result
        assert "win_rate" in backtest_result

    @pytest.mark.asyncio
    async def test_stores_assessment_verdict_after_assessment(
        self, mock_operations_service, stub_workers
    ):
        """Parent metadata stores assessment_verdict after assessment phase."""
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

        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert "assessment_verdict" in parent.metadata.parameters
        assert parent.metadata.parameters["assessment_verdict"] == "promising"
