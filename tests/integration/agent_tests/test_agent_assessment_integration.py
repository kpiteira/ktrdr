"""Integration tests for AgentAssessmentWorker.

Tests for Task 5.5: Verify assessment worker integrates correctly.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker, WorkerError
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


class MockOperationsService:
    """In-memory operations service for testing."""

    def __init__(self):
        self._operations: dict[str, OperationInfo] = {}
        self._counter = 0

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

    async def complete_operation(self, operation_id, result=None):
        """Mark operation as completed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.COMPLETED
            self._operations[operation_id].result_summary = result

    async def fail_operation(self, operation_id, error=None):
        """Mark operation as failed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.FAILED
            self._operations[operation_id].error_message = error

    async def cancel_operation(self, operation_id, reason=None):
        """Mark operation as cancelled."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.CANCELLED


@pytest.fixture
def ops_service():
    """Create mock operations service."""
    return MockOperationsService()


@pytest.fixture
def mock_invoker():
    """Create mock invoker that simulates Claude returning assessment."""
    invoker = MagicMock()
    result = MagicMock()
    result.success = True
    result.error = None
    result.input_tokens = 3000
    result.output_tokens = 1500
    invoker.run = AsyncMock(return_value=result)
    return invoker


async def create_parent_operation(ops_service):
    """Create parent AGENT_RESEARCH operation with strategy info."""
    return await ops_service.create_operation(
        operation_type=OperationType.AGENT_RESEARCH,
        metadata=OperationMetadata(
            parameters={
                "phase": "assessing",
                "strategy_name": "momentum_rsi_v1",
                "strategy_path": "/app/strategies/momentum_rsi_v1.yaml",
            }
        ),
    )


@pytest.fixture
def sample_results():
    """Sample training and backtest results."""
    return {
        "training": {
            "accuracy": 0.62,
            "final_loss": 0.38,
            "initial_loss": 0.75,
        },
        "backtest": {
            "sharpe_ratio": 1.5,
            "win_rate": 0.58,
            "max_drawdown": 0.12,
            "total_return": 0.25,
            "total_trades": 42,
        },
    }


class TestAssessmentWorkerIntegration:
    """Integration tests for AgentAssessmentWorker."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_creates_child_operation(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker creates AGENT_ASSESSMENT child operation."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        # Pre-set the assessment as if Claude saved it
        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good win rate"],
            "weaknesses": ["Limited sample"],
            "suggestions": ["Test more timeframes"],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        await worker.run(parent_op.operation_id, sample_results)

        # Should have created an assessment operation
        all_ops = list(ops_service._operations.values())
        assessment_ops = [
            op for op in all_ops if op.operation_type == OperationType.AGENT_ASSESSMENT
        ]
        assert len(assessment_ops) == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_calls_claude_with_metrics(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker calls Claude with training/backtest metrics."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "mediocre",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        await worker.run(parent_op.operation_id, sample_results)

        # Invoker should have been called
        mock_invoker.run.assert_called_once()

        # Get the prompt that was passed
        call_args = mock_invoker.run.call_args
        prompt = call_args.kwargs.get(
            "prompt", call_args.args[0] if call_args.args else ""
        )

        # Prompt should contain metrics
        assert "62" in prompt or "0.62" in prompt  # accuracy
        assert "1.5" in prompt  # sharpe_ratio

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_returns_complete_result(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker returns verdict, strengths, weaknesses, suggestions."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["A", "B"],
            "weaknesses": ["C"],
            "suggestions": ["D", "E"],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        result = await worker.run(parent_op.operation_id, sample_results)

        assert result["success"] is True
        assert result["verdict"] == "promising"
        assert result["strengths"] == ["A", "B"]
        assert result["weaknesses"] == ["C"]
        assert result["suggestions"] == ["D", "E"]
        assert result["input_tokens"] == 3000
        assert result["output_tokens"] == 1500

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_completes_child_operation(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker completes the child operation on success."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "poor",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        await worker.run(parent_op.operation_id, sample_results)

        # Find the assessment operation
        all_ops = list(ops_service._operations.values())
        assessment_op = next(
            op for op in all_ops if op.operation_type == OperationType.AGENT_ASSESSMENT
        )

        assert assessment_op.status == OperationStatus.COMPLETED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_fails_if_no_assessment_saved(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker raises error if Claude didn't save assessment."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        # Don't set last_saved_assessment - simulating Claude not using tool

        with pytest.raises(WorkerError, match="did not save"):
            await worker.run(parent_op.operation_id, sample_results)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_cancellation_propagates(
        self, ops_service, sample_results
    ):
        """Cancellation during assessment propagates correctly."""
        parent_op = await create_parent_operation(ops_service)

        # Invoker that takes time to complete
        slow_invoker = MagicMock()

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(10)  # Will be cancelled
            return MagicMock(success=True)

        slow_invoker.run = slow_run

        worker = AgentAssessmentWorker(ops_service, invoker=slow_invoker)

        # Start task and cancel it
        task = asyncio.create_task(worker.run(parent_op.operation_id, sample_results))

        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_sets_strategy_name_for_tool(
        self, ops_service, mock_invoker, sample_results
    ):
        """Assessment worker sets strategy name for save_assessment tool."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        await worker.run(parent_op.operation_id, sample_results)

        # Check that strategy name was set for tool executor
        assert worker.tool_executor._current_strategy_name == "momentum_rsi_v1"


class TestAssessmentWorkerErrorHandling:
    """Error handling tests for AgentAssessmentWorker."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_claude_failure_fails_operation(self, ops_service, sample_results):
        """Claude failure marks operation as failed."""
        parent_op = await create_parent_operation(ops_service)
        failing_invoker = MagicMock()
        result = MagicMock()
        result.success = False
        result.error = "API rate limit exceeded"
        failing_invoker.run = AsyncMock(return_value=result)

        worker = AgentAssessmentWorker(ops_service, invoker=failing_invoker)

        with pytest.raises(WorkerError, match="assessment failed"):
            await worker.run(parent_op.operation_id, sample_results)

        # Check operation was failed
        all_ops = list(ops_service._operations.values())
        assessment_op = next(
            op for op in all_ops if op.operation_type == OperationType.AGENT_ASSESSMENT
        )
        assert assessment_op.status == OperationStatus.FAILED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_parent_not_found_raises_error(self, ops_service, sample_results):
        """Missing parent operation raises WorkerError."""
        worker = AgentAssessmentWorker(ops_service)

        with pytest.raises(WorkerError, match="not found"):
            await worker.run("nonexistent_op_id", sample_results)
