"""Tests for research worker progress updates (M9 Task 9.1).

Tests that the AgentResearchWorker calls update_progress() with correct
percentages and messages when transitioning between phases.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service that tracks update_progress calls."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}
    progress_updates: list[tuple[str, OperationProgress]] = []

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

    async def async_update_progress(operation_id, progress):
        """Track progress updates for verification."""
        progress_updates.append((operation_id, progress))
        if operation_id in operations:
            operations[operation_id].progress = progress

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.start_operation = async_start_operation
    service.cancel_operation = async_cancel_operation
    service.update_progress = async_update_progress
    service._operations = operations
    service._progress_updates = progress_updates

    return service


@pytest.fixture
def stub_workers():
    """Create stub workers for testing (design and assessment only)."""
    from ktrdr.agents.workers.stubs import (
        StubAssessmentWorker,
        StubDesignWorker,
    )

    return {
        "design": StubDesignWorker(),
        "assessment": StubAssessmentWorker(),
    }


@pytest.fixture
def mock_training_service(mock_operations_service):
    """Mock TrainingService that creates real operations."""
    service = AsyncMock()

    async def start_training(**kwargs):
        """Create a real training operation and return its ID."""
        training_op = await mock_operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        # Immediately complete with good results
        await mock_operations_service.complete_operation(
            training_op.operation_id,
            {
                "success": True,
                "accuracy": 0.65,
                "final_loss": 0.35,
                "initial_loss": 0.75,
                "model_path": "/tmp/model.pt",
            },
        )
        return {"operation_id": training_op.operation_id}

    service.start_training = start_training
    return service


@pytest.fixture
def mock_backtest_service(mock_operations_service):
    """Mock BacktestingService that creates real operations."""
    service = AsyncMock()

    async def run_backtest(**kwargs):
        """Create a real backtest operation and return its ID."""
        backtest_op = await mock_operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        # Immediately complete with good results (metrics nested)
        await mock_operations_service.complete_operation(
            backtest_op.operation_id,
            {
                "success": True,
                "metrics": {
                    "sharpe_ratio": 1.2,
                    "win_rate": 0.55,
                    "max_drawdown_pct": 0.15,
                    "total_return": 0.23,
                    "total_trades": 42,
                },
            },
        )
        return {"operation_id": backtest_op.operation_id}

    service.run_backtest = run_backtest
    return service


class TestProgressUpdatesOnPhaseTransitions:
    """Test that update_progress() is called with correct values per phase."""

    @pytest.mark.asyncio
    async def test_update_progress_called_with_5_percent_for_designing(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """update_progress() called with 5% when entering designing phase."""
        # conftest.py already sets STUB_WORKER_DELAY=0.001 and AGENT_POLL_INTERVAL=0.01

        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        # Run to completion
        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        # Verify 5% progress was set for designing phase
        progress_updates = mock_operations_service._progress_updates
        designing_updates = [
            (op_id, prog)
            for op_id, prog in progress_updates
            if prog.percentage == 5.0 and prog.current_step == "Designing strategy..."
        ]
        assert len(designing_updates) >= 1, (
            f"Expected at least one 5% progress update for designing phase. "
            f"Got updates: {[(op_id, prog.percentage, prog.current_step) for op_id, prog in progress_updates]}"
        )

    @pytest.mark.asyncio
    async def test_update_progress_called_with_20_percent_for_training(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """update_progress() called with 20% when entering training phase."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        progress_updates = mock_operations_service._progress_updates
        training_updates = [
            (op_id, prog)
            for op_id, prog in progress_updates
            if prog.percentage == 20.0 and prog.current_step == "Training model..."
        ]
        assert len(training_updates) >= 1, (
            f"Expected at least one 20% progress update for training phase. "
            f"Got updates: {[(op_id, prog.percentage, prog.current_step) for op_id, prog in progress_updates]}"
        )

    @pytest.mark.asyncio
    async def test_update_progress_called_with_65_percent_for_backtesting(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """update_progress() called with 65% when entering backtesting phase."""

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        progress_updates = mock_operations_service._progress_updates
        backtest_updates = [
            (op_id, prog)
            for op_id, prog in progress_updates
            if prog.percentage == 65.0 and prog.current_step == "Running backtest..."
        ]
        assert len(backtest_updates) >= 1, (
            f"Expected at least one 65% progress update for backtesting phase. "
            f"Got updates: {[(op_id, prog.percentage, prog.current_step) for op_id, prog in progress_updates]}"
        )

    @pytest.mark.asyncio
    async def test_update_progress_called_with_90_percent_for_assessing(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """update_progress() called with 90% when entering assessing phase."""

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        progress_updates = mock_operations_service._progress_updates
        assessing_updates = [
            (op_id, prog)
            for op_id, prog in progress_updates
            if prog.percentage == 90.0 and prog.current_step == "Assessing results..."
        ]
        assert len(assessing_updates) >= 1, (
            f"Expected at least one 90% progress update for assessing phase. "
            f"Got updates: {[(op_id, prog.percentage, prog.current_step) for op_id, prog in progress_updates]}"
        )

    @pytest.mark.asyncio
    async def test_update_progress_called_with_100_percent_on_completion(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """update_progress() called with 100% on successful completion."""

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        progress_updates = mock_operations_service._progress_updates
        completion_updates = [
            (op_id, prog)
            for op_id, prog in progress_updates
            if prog.percentage == 100.0 and prog.current_step == "Complete"
        ]
        assert len(completion_updates) >= 1, (
            f"Expected at least one 100% progress update on completion. "
            f"Got updates: {[(op_id, prog.percentage, prog.current_step) for op_id, prog in progress_updates]}"
        )


class TestProgressUpdateSequence:
    """Test that progress updates happen in the correct sequence."""

    @pytest.mark.asyncio
    async def test_progress_sequence_is_ascending(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service,
        mock_backtest_service,
    ):
        """Progress percentages should increase monotonically through the cycle."""

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service,
            backtest_service=mock_backtest_service,
        )

        try:
            await asyncio.wait_for(worker.run(parent_op.operation_id), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Worker timed out")

        # Get parent operation progress updates only
        progress_updates = [
            prog
            for op_id, prog in mock_operations_service._progress_updates
            if op_id == parent_op.operation_id
        ]

        # Verify we have all expected percentages
        percentages = [prog.percentage for prog in progress_updates]
        assert 5.0 in percentages, "Missing 5% for designing phase"
        assert 20.0 in percentages, "Missing 20% for training phase"
        assert 65.0 in percentages, "Missing 65% for backtesting phase"
        assert 90.0 in percentages, "Missing 90% for assessing phase"
        assert 100.0 in percentages, "Missing 100% for completion"

        # Verify the sequence is ascending (each update >= previous)
        for i in range(1, len(percentages)):
            assert (
                percentages[i] >= percentages[i - 1]
            ), f"Progress went backwards: {percentages[i - 1]} -> {percentages[i]}"
