"""Unit tests for AssessmentAgentWorker.

Tests the containerized assessment agent worker that uses AgentRuntime
to invoke Claude Code with MCP for strategy assessment.

Coverage:
- Start endpoint: valid requests, validation errors, optional fields
- Result extraction: save_assessment tool call parsing, multiple saves, empty transcript
- Background execution: success, no save, runtime error, timeout
- Health endpoint
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ktrdr.agents.runtime.protocol import AgentResult
from ktrdr.api.models.operations import OperationType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runtime():
    """Create a mock AgentRuntime for testing."""
    runtime = AsyncMock()
    runtime.invoke = AsyncMock()
    return runtime


def _make_transcript_with_assessment(
    verdict: str = "promising",
) -> list[dict]:
    """Build a transcript that contains a save_assessment tool call."""
    return [
        {
            "role": "assistant",
            "type": "text",
            "content": "I'll analyze the strategy results.",
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__get_model_performance",
            "input": {"strategy_name": "test_strategy"},
            "id": "tu_1",
        },
        {
            "role": "tool",
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": '{"accuracy": 0.72, "loss": 0.31}',
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__save_assessment",
            "input": {
                "strategy_name": "test_strategy",
                "verdict": verdict,
                "strengths": ["Good Sharpe ratio", "Low drawdown"],
                "weaknesses": ["Low trade count"],
                "suggestions": [
                    "Increase trade frequency by relaxing entry conditions"
                ],
                "hypotheses": [
                    {
                        "text": "Wider RSI bands will increase trade count",
                        "rationale": "Current RSI thresholds too conservative",
                    }
                ],
            },
            "id": "tu_2",
        },
        {
            "role": "tool",
            "type": "tool_result",
            "tool_use_id": "tu_2",
            "content": '{"strategy_name": "test_strategy", "assessment_path": "assessments/test_strategy_20260304.json"}',
        },
    ]


def _make_transcript_no_assessment() -> list[dict]:
    """Build a transcript without a save_assessment call."""
    return [
        {
            "role": "assistant",
            "type": "text",
            "content": "I couldn't complete the assessment.",
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__get_model_performance",
            "input": {"strategy_name": "test"},
            "id": "tu_1",
        },
    ]


@pytest.fixture
def mock_ops():
    """Create a mock OperationsService."""
    ops = MagicMock()
    ops.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_test_123"))
    ops.start_operation = AsyncMock()
    ops.update_operation_progress = AsyncMock()
    ops.complete_operation = AsyncMock()
    ops.fail_operation = AsyncMock()
    return ops


@pytest.fixture
def worker(mock_runtime, mock_ops):
    """Create an AssessmentAgentWorker with mocked dependencies."""
    from ktrdr.agents.workers.assessment_agent_worker import AssessmentAgentWorker

    w = AssessmentAgentWorker(
        runtime=mock_runtime,
        worker_port=5020,
        backend_url="http://backend:8000",
    )
    w._operations_service = mock_ops
    return w


@pytest.fixture
def client(worker):
    """Create a test client for the worker's FastAPI app."""
    return TestClient(worker.app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: Start Endpoint
# ---------------------------------------------------------------------------


class TestStartEndpoint:
    """Tests for POST /assessments/start."""

    def test_start_creates_operation_and_returns(self, client, mock_ops):
        """Start endpoint registers operation and returns started status."""
        response = client.post(
            "/assessments/start",
            json={
                "task_id": "op_backend_456",
                "strategy_name": "momentum_rsi_1h",
                "strategy_config": {"indicators": {"rsi": {"period": 14}}},
                "training_metrics": {"accuracy": 0.72, "loss": 0.31},
                "backtest_results": {
                    "sharpe": 1.2,
                    "max_dd": 0.15,
                    "total_trades": 145,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_backend_456"
        assert data["status"] == "started"

        mock_ops.create_operation.assert_called_once()
        create_kwargs = mock_ops.create_operation.call_args[1]
        assert create_kwargs["operation_id"] == "op_backend_456"
        assert create_kwargs["operation_type"] == OperationType.AGENT_ASSESSMENT
        mock_ops.start_operation.assert_called_once()

    def test_start_generates_id_when_no_task_id(self, client):
        """Start endpoint generates operation_id when task_id not provided."""
        response = client.post(
            "/assessments/start",
            json={
                "strategy_name": "test_strat",
                "training_metrics": {"accuracy": 0.5},
                "backtest_results": {"sharpe": 0.8},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"].startswith("worker_assessment_")

    def test_start_requires_strategy_name(self, client):
        """Start endpoint requires strategy_name field."""
        response = client.post(
            "/assessments/start",
            json={
                "task_id": "op_123",
                "training_metrics": {"accuracy": 0.72},
                "backtest_results": {"sharpe": 1.2},
            },
        )
        assert response.status_code == 422

    def test_start_requires_training_metrics(self, client):
        """Start endpoint requires training_metrics field."""
        response = client.post(
            "/assessments/start",
            json={
                "task_id": "op_123",
                "strategy_name": "test_strat",
                "backtest_results": {"sharpe": 1.2},
            },
        )
        assert response.status_code == 422

    def test_start_requires_backtest_results(self, client):
        """Start endpoint requires backtest_results field."""
        response = client.post(
            "/assessments/start",
            json={
                "task_id": "op_123",
                "strategy_name": "test_strat",
                "training_metrics": {"accuracy": 0.72},
            },
        )
        assert response.status_code == 422

    def test_start_accepts_optional_fields(self, client):
        """Start endpoint accepts optional strategy_config and experiment_history."""
        response = client.post(
            "/assessments/start",
            json={
                "task_id": "op_123",
                "strategy_name": "test_strat",
                "strategy_config": {"indicators": {"rsi": {}}},
                "training_metrics": {"accuracy": 0.72},
                "backtest_results": {"sharpe": 1.2},
                "experiment_history": "Previous experiments showed RSI works.",
            },
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Result Extraction
# ---------------------------------------------------------------------------


class TestResultExtraction:
    """Tests for extracting assessment info from SDK transcript."""

    def test_extract_assessment_from_transcript(self, worker):
        """Extracts verdict and fields from save_assessment tool call."""
        transcript = _make_transcript_with_assessment("promising")
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is not None
        assert result["verdict"] == "promising"
        assert result["strategy_name"] == "test_strategy"

    def test_extract_returns_none_when_no_save(self, worker):
        """Returns None when transcript has no save_assessment call."""
        transcript = _make_transcript_no_assessment()
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is None

    def test_extract_uses_last_save_call(self, worker):
        """When multiple save calls exist, uses the last one."""
        transcript = _make_transcript_with_assessment("neutral")
        transcript.extend(
            [
                {
                    "role": "assistant",
                    "type": "tool_use",
                    "tool": "mcp__ktrdr__save_assessment",
                    "input": {
                        "strategy_name": "test_strategy",
                        "verdict": "promising",
                        "strengths": ["Revised analysis"],
                        "weaknesses": [],
                        "suggestions": [],
                    },
                    "id": "tu_3",
                },
                {
                    "role": "tool",
                    "type": "tool_result",
                    "tool_use_id": "tu_3",
                    "content": '{"strategy_name": "test_strategy", "assessment_path": "assessments/revised.json"}',
                },
            ]
        )
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is not None
        assert result["verdict"] == "promising"

    def test_extract_from_empty_transcript(self, worker):
        """Returns None for empty transcript."""
        result = worker.extract_assessment_from_transcript([])
        assert result is None

    def test_extract_returns_assessment_path(self, worker):
        """Extracts assessment_path from tool_result content."""
        transcript = _make_transcript_with_assessment("promising")
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is not None
        assert result["assessment_path"] == "assessments/test_strategy_20260304.json"

    def test_extract_handles_malformed_tool_result(self, worker):
        """Handles tool_result with non-JSON content gracefully."""
        transcript = [
            {
                "type": "tool_use",
                "tool": "mcp__ktrdr__save_assessment",
                "input": {
                    "strategy_name": "malformed_test",
                    "verdict": "poor",
                    "strengths": [],
                    "weaknesses": ["Everything"],
                    "suggestions": [],
                },
                "id": "tu_bad",
            },
            {
                "type": "tool_result",
                "tool_use_id": "tu_bad",
                "content": "Error: validation failed",
            },
        ]
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is not None
        assert result["verdict"] == "poor"
        assert result["assessment_path"] is None

    def test_extract_requires_both_verdict_and_strategy_name(self, worker):
        """Extraction returns None if verdict is missing (strategy_name alone is not enough)."""
        transcript = [
            {
                "type": "tool_use",
                "tool": "mcp__ktrdr__save_assessment",
                "input": {
                    "strategy_name": "test_strategy",
                    # verdict is missing
                    "strengths": [],
                    "weaknesses": [],
                    "suggestions": [],
                },
                "id": "tu_no_verdict",
            },
        ]
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is None

    def test_extract_ignores_non_assessment_tools(self, worker):
        """Other tool calls are ignored during extraction."""
        transcript = [
            {
                "type": "tool_use",
                "tool": "mcp__ktrdr__get_model_performance",
                "input": {"strategy_name": "ignore_me"},
                "id": "tu_perf",
            },
            {
                "type": "tool_result",
                "tool_use_id": "tu_perf",
                "content": '{"accuracy": 0.72}',
            },
        ]
        result = worker.extract_assessment_from_transcript(transcript)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Background Execution
# ---------------------------------------------------------------------------


class TestBackgroundExecution:
    """Tests for the background assessment execution task."""

    @pytest.mark.asyncio
    async def test_successful_assessment_completes_operation(
        self, worker, mock_runtime
    ):
        """Successful assessment invocation completes the operation with result."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Assessment complete.",
            cost_usd=0.06,
            turns=4,
            transcript=_make_transcript_with_assessment("promising"),
            session_id="sess_abc",
        )

        await worker._execute_assessment_work(
            operation_id="op_test_123",
            strategy_name="momentum_rsi_1h",
            strategy_config={"indicators": {"rsi": {"period": 14}}},
            training_metrics={"accuracy": 0.72, "loss": 0.31},
            backtest_results={"sharpe": 1.2, "max_dd": 0.15, "total_trades": 145},
            experiment_history=None,
        )

        ops = worker.get_operations_service()
        ops.complete_operation.assert_called_once()
        call_kwargs = ops.complete_operation.call_args[1]
        assert call_kwargs["operation_id"] == "op_test_123"
        result = call_kwargs["result_summary"]
        assert result["verdict"] == "promising"
        assert result["strategy_name"] == "test_strategy"

    @pytest.mark.asyncio
    async def test_assessment_without_save_fails_operation(self, worker, mock_runtime):
        """Assessment that produces no save_assessment call fails."""
        mock_runtime.invoke.return_value = AgentResult(
            output="I couldn't complete the assessment.",
            cost_usd=0.03,
            turns=2,
            transcript=_make_transcript_no_assessment(),
            session_id="sess_def",
        )

        await worker._execute_assessment_work(
            operation_id="op_test_456",
            strategy_name="test_strat",
            strategy_config=None,
            training_metrics={"accuracy": 0.5},
            backtest_results={"sharpe": 0.3},
            experiment_history=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()
        call_kwargs = ops.fail_operation.call_args[1]
        assert call_kwargs["operation_id"] == "op_test_456"
        assert "save_assessment" in call_kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_runtime_error_fails_operation(self, worker, mock_runtime):
        """Runtime invoke() raising an exception fails the operation."""
        mock_runtime.invoke.side_effect = RuntimeError("SDK connection failed")

        await worker._execute_assessment_work(
            operation_id="op_test_789",
            strategy_name="test_strat",
            strategy_config=None,
            training_metrics={"accuracy": 0.5},
            backtest_results={"sharpe": 0.3},
            experiment_history=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()
        call_kwargs = ops.fail_operation.call_args[1]
        assert "SDK connection failed" in call_kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_timeout_error_fails_operation(self, worker, mock_runtime):
        """Runtime invoke() timeout is caught and fails the operation."""
        mock_runtime.invoke.side_effect = asyncio.TimeoutError()

        await worker._execute_assessment_work(
            operation_id="op_timeout",
            strategy_name="test_strat",
            strategy_config=None,
            training_metrics={"accuracy": 0.5},
            backtest_results={"sharpe": 0.3},
            experiment_history=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_summary_contains_all_fields(self, worker, mock_runtime):
        """Completed operation result_summary includes cost, turns, session_id."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.10,
            turns=6,
            transcript=_make_transcript_with_assessment("neutral"),
            session_id="sess_xyz",
        )

        await worker._execute_assessment_work(
            operation_id="op_fields",
            strategy_name="test_strat",
            strategy_config=None,
            training_metrics={"accuracy": 0.6},
            backtest_results={"sharpe": 0.9},
            experiment_history=None,
        )

        ops = worker.get_operations_service()
        result = ops.complete_operation.call_args[1]["result_summary"]
        assert result["verdict"] == "neutral"
        assert result["cost_usd"] == 0.10
        assert result["turns"] == 6
        assert result["session_id"] == "sess_xyz"
        assert "assessment_path" in result
        assert "strengths" in result
        assert "weaknesses" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_runtime_passes_correct_params(self, worker, mock_runtime):
        """Runtime invoke() called with correct system prompt and MCP config."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.05,
            turns=2,
            transcript=_make_transcript_with_assessment("poor"),
        )

        await worker._execute_assessment_work(
            operation_id="op_params",
            strategy_name="momentum_rsi_1h",
            strategy_config={"indicators": {"rsi": {"period": 14}}},
            training_metrics={"accuracy": 0.72, "loss": 0.31},
            backtest_results={"sharpe": 1.2, "max_dd": 0.15},
            experiment_history="Previous RSI strategies underperformed.",
        )

        mock_runtime.invoke.assert_called_once()
        call_kwargs = mock_runtime.invoke.call_args[1]
        assert call_kwargs.get("system_prompt") is not None
        assert call_kwargs.get("mcp_servers") is not None
        assert "ktrdr" in call_kwargs["mcp_servers"]
        # User prompt should contain strategy and metrics info
        prompt = mock_runtime.invoke.call_args[0][0]
        assert "momentum_rsi_1h" in prompt
        assert "0.72" in prompt  # accuracy
        assert "1.2" in prompt  # sharpe


# ---------------------------------------------------------------------------
# Tests: Memory Integration
# ---------------------------------------------------------------------------


class TestMemoryIntegration:
    """Tests for experiment record and hypothesis saving after assessment."""

    @pytest.mark.asyncio
    async def test_experiment_record_saved_after_assessment(self, worker, mock_runtime):
        """Successful assessment saves an experiment record."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Assessment complete.",
            cost_usd=0.06,
            turns=4,
            transcript=_make_transcript_with_assessment("promising"),
            session_id="sess_abc",
        )

        with patch(
            "ktrdr.agents.workers.assessment_agent_worker.memory"
        ) as mock_memory:
            mock_memory.generate_experiment_id.return_value = "exp_test_123"
            mock_memory.save_experiment.return_value = Path(
                "/app/memory/experiments/exp_test_123.yaml"
            )

            await worker._execute_assessment_work(
                operation_id="op_mem_test",
                strategy_name="momentum_rsi_1h",
                strategy_config=None,
                training_metrics={"accuracy": 0.72, "loss": 0.31},
                backtest_results={"sharpe": 1.2, "max_dd": 0.15, "total_trades": 145},
                experiment_history=None,
            )

            mock_memory.save_experiment.assert_called_once()
            record = mock_memory.save_experiment.call_args[0][0]
            assert record.strategy_name == "momentum_rsi_1h"
            assert record.assessment["verdict"] == "promising"
            assert record.results["sharpe"] == 1.2

    @pytest.mark.asyncio
    async def test_hypotheses_saved_after_assessment(self, worker, mock_runtime):
        """Successful assessment saves new hypotheses."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Assessment complete.",
            cost_usd=0.06,
            turns=4,
            transcript=_make_transcript_with_assessment("promising"),
            session_id="sess_abc",
        )

        with patch(
            "ktrdr.agents.workers.assessment_agent_worker.memory"
        ) as mock_memory:
            mock_memory.generate_experiment_id.return_value = "exp_test_456"
            mock_memory.generate_hypothesis_id.side_effect = ["H_001", "H_002"]
            mock_memory.save_experiment.return_value = Path("/tmp/test.yaml")

            await worker._execute_assessment_work(
                operation_id="op_hyp_test",
                strategy_name="test_strat",
                strategy_config=None,
                training_metrics={"accuracy": 0.72},
                backtest_results={"sharpe": 1.2},
                experiment_history=None,
            )

            # The transcript fixture has 1 hypothesis
            assert mock_memory.save_hypothesis.call_count >= 1

    @pytest.mark.asyncio
    async def test_memory_failure_does_not_fail_operation(self, worker, mock_runtime):
        """Memory save failure doesn't prevent operation completion."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Assessment complete.",
            cost_usd=0.06,
            turns=4,
            transcript=_make_transcript_with_assessment("promising"),
            session_id="sess_abc",
        )

        with patch(
            "ktrdr.agents.workers.assessment_agent_worker.memory"
        ) as mock_memory:
            mock_memory.generate_experiment_id.return_value = "exp_fail"
            mock_memory.save_experiment.side_effect = OSError("Disk full")

            await worker._execute_assessment_work(
                operation_id="op_mem_fail",
                strategy_name="test_strat",
                strategy_config=None,
                training_metrics={"accuracy": 0.72},
                backtest_results={"sharpe": 1.2},
                experiment_history=None,
            )

            # Operation should still complete despite memory failure
            ops = worker.get_operations_service()
            ops.complete_operation.assert_called_once()
            ops.fail_operation.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_memory_save_on_failed_assessment(self, worker, mock_runtime):
        """Memory is not saved when assessment fails (no save_assessment call)."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Failed.",
            cost_usd=0.03,
            turns=2,
            transcript=_make_transcript_no_assessment(),
            session_id="sess_fail",
        )

        with patch(
            "ktrdr.agents.workers.assessment_agent_worker.memory"
        ) as mock_memory:
            await worker._execute_assessment_work(
                operation_id="op_no_mem",
                strategy_name="test_strat",
                strategy_config=None,
                training_metrics={"accuracy": 0.5},
                backtest_results={"sharpe": 0.3},
                experiment_history=None,
            )

            mock_memory.save_experiment.assert_not_called()
            mock_memory.save_hypothesis.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Prompt Composition
# ---------------------------------------------------------------------------


class TestPromptComposition:
    """Tests for _build_user_prompt method."""

    def test_prompt_contains_strategy_name(self, worker):
        """User prompt includes strategy name."""
        prompt = worker._build_user_prompt(
            strategy_name="momentum_rsi_1h",
            strategy_config=None,
            training_metrics={"accuracy": 0.72},
            backtest_results={"sharpe": 1.2},
            experiment_history=None,
        )
        assert "momentum_rsi_1h" in prompt

    def test_prompt_contains_training_metrics(self, worker):
        """User prompt includes training metrics."""
        prompt = worker._build_user_prompt(
            strategy_name="test",
            strategy_config=None,
            training_metrics={"accuracy": 0.72, "loss": 0.31},
            backtest_results={"sharpe": 1.2},
            experiment_history=None,
        )
        assert "Training Metrics" in prompt
        assert "accuracy" in prompt

    def test_prompt_contains_backtest_results(self, worker):
        """User prompt includes backtest results."""
        prompt = worker._build_user_prompt(
            strategy_name="test",
            strategy_config=None,
            training_metrics={"accuracy": 0.72},
            backtest_results={"sharpe": 1.2, "max_dd": 0.15},
            experiment_history=None,
        )
        assert "Backtest Results" in prompt
        assert "sharpe" in prompt

    def test_prompt_includes_strategy_config_when_provided(self, worker):
        """User prompt includes strategy config YAML when provided."""
        prompt = worker._build_user_prompt(
            strategy_name="test",
            strategy_config={"indicators": {"rsi": {"period": 14}}},
            training_metrics={"accuracy": 0.72},
            backtest_results={"sharpe": 1.2},
            experiment_history=None,
        )
        assert "Strategy Configuration" in prompt
        assert "rsi" in prompt

    def test_prompt_includes_experiment_history(self, worker):
        """User prompt includes experiment history when provided."""
        prompt = worker._build_user_prompt(
            strategy_name="test",
            strategy_config=None,
            training_metrics={"accuracy": 0.72},
            backtest_results={"sharpe": 1.2},
            experiment_history="RSI-only strategies underperformed.",
        )
        assert "Experiment History" in prompt
        assert "RSI-only strategies underperformed" in prompt

    def test_prompt_excludes_optional_sections_when_none(self, worker):
        """User prompt excludes strategy_config and experiment_history when None."""
        prompt = worker._build_user_prompt(
            strategy_name="test",
            strategy_config=None,
            training_metrics={"accuracy": 0.72},
            backtest_results={"sharpe": 1.2},
            experiment_history=None,
        )
        assert "Strategy Configuration" not in prompt
        assert "Experiment History" not in prompt


# ---------------------------------------------------------------------------
# Tests: Health Endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
