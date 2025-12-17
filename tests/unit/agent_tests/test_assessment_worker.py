"""Unit tests for AgentAssessmentWorker.

Tests for Task 5.3: Assessment worker using Claude.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker, WorkerError
from ktrdr.api.models.operations import OperationStatus, OperationType


@pytest.fixture
def mock_operations_service():
    """Create mock operations service."""
    service = AsyncMock()

    # Mock operation creation
    mock_op = MagicMock()
    mock_op.operation_id = "op_agent_assessment_123"
    mock_op.status = OperationStatus.PENDING
    service.create_operation.return_value = mock_op

    # Mock parent operation lookup
    parent_op = MagicMock()
    parent_op.operation_id = "op_agent_research_456"
    parent_op.metadata = MagicMock()
    parent_op.metadata.parameters = {
        "strategy_name": "test_strategy_v1",
        "strategy_path": "/app/strategies/test_strategy_v1.yaml",
    }
    service.get_operation.return_value = parent_op

    return service


@pytest.fixture
def mock_invoker():
    """Create mock AnthropicAgentInvoker."""
    invoker = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.error = None
    mock_result.input_tokens = 3000
    mock_result.output_tokens = 1500
    invoker.run = AsyncMock(return_value=mock_result)
    return invoker


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


class TestAgentAssessmentWorkerCreation:
    """Tests for AssessmentWorker creation."""

    def test_creates_with_operations_service(self, mock_operations_service):
        """Worker can be created with operations service."""
        worker = AgentAssessmentWorker(mock_operations_service)
        assert worker.ops == mock_operations_service

    def test_creates_with_custom_invoker(self, mock_operations_service, mock_invoker):
        """Worker accepts custom invoker."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)
        assert worker.invoker == mock_invoker


class TestAgentAssessmentWorkerRun:
    """Tests for AssessmentWorker.run()."""

    @pytest.mark.asyncio
    async def test_creates_agent_assessment_operation(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Creates AGENT_ASSESSMENT operation."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        # Mock tool executor to have assessment
        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good"],
            "weaknesses": ["Limited"],
            "suggestions": ["Try more"],
        }
        worker.tool_executor.last_saved_assessment_path = (
            "/app/strategies/test/assessment.json"
        )

        await worker.run("op_agent_research_456", sample_results)

        # Verify operation was created with correct type
        mock_operations_service.create_operation.assert_called_once()
        call_args = mock_operations_service.create_operation.call_args
        assert call_args.kwargs["operation_type"] == OperationType.AGENT_ASSESSMENT

    @pytest.mark.asyncio
    async def test_passes_training_and_backtest_metrics_to_prompt(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Training and backtest metrics are passed to prompt builder."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "mediocre",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        await worker.run("op_agent_research_456", sample_results)

        # Verify invoker was called with prompt containing metrics
        mock_invoker.run.assert_called_once()
        call_args = mock_invoker.run.call_args
        prompt = call_args.kwargs.get(
            "prompt", call_args.args[0] if call_args.args else ""
        )

        # Prompt should contain metrics
        assert "62" in prompt or "0.62" in prompt  # accuracy
        assert "1.5" in prompt or "1.50" in prompt  # sharpe_ratio

    @pytest.mark.asyncio
    async def test_returns_verdict_from_save_assessment_tool(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Returns verdict from the save_assessment tool."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["A", "B"],
            "weaknesses": ["C"],
            "suggestions": ["D"],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        result = await worker.run("op_agent_research_456", sample_results)

        assert result["verdict"] == "promising"
        assert result["strengths"] == ["A", "B"]
        assert result["weaknesses"] == ["C"]
        assert result["suggestions"] == ["D"]

    @pytest.mark.asyncio
    async def test_returns_token_counts(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Returns input and output token counts."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "poor",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        result = await worker.run("op_agent_research_456", sample_results)

        assert result["input_tokens"] == 3000
        assert result["output_tokens"] == 1500

    @pytest.mark.asyncio
    async def test_raises_worker_error_if_assessment_not_saved(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Raises WorkerError if Claude didn't save assessment."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        # Don't set last_saved_assessment - simulating Claude not using tool
        worker.tool_executor.last_saved_assessment = None

        with pytest.raises(WorkerError, match="did not save"):
            await worker.run("op_agent_research_456", sample_results)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(
        self, mock_operations_service, sample_results
    ):
        """CancelledError propagates correctly."""
        mock_invoker = MagicMock()
        mock_invoker.run = AsyncMock(side_effect=asyncio.CancelledError())

        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_agent_research_456", sample_results)

        # Should cancel the operation
        mock_operations_service.cancel_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_completes_child_operation_on_success(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Completes child operation on success."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        await worker.run("op_agent_research_456", sample_results)

        mock_operations_service.complete_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_fails_child_operation_on_error(
        self, mock_operations_service, sample_results
    ):
        """Fails child operation when Claude fails."""
        mock_invoker = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "API error"
        mock_invoker.run = AsyncMock(return_value=mock_result)

        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        with pytest.raises(WorkerError):
            await worker.run("op_agent_research_456", sample_results)

        mock_operations_service.fail_operation.assert_called_once()
