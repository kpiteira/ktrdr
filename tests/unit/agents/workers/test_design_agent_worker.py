"""Unit tests for DesignAgentWorker.

Tests the containerized design agent worker that uses AgentRuntime
to invoke Claude Code with MCP for strategy design.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.agents.runtime.protocol import AgentResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runtime():
    """Create a mock AgentRuntime for testing."""
    runtime = AsyncMock()
    runtime.invoke = AsyncMock()
    return runtime


def _make_transcript_with_save(strategy_name: str = "momentum_rsi_1h") -> list[dict]:
    """Build a transcript that contains a save_strategy_config tool call."""
    return [
        {
            "role": "assistant",
            "type": "text",
            "content": "I'll design a momentum strategy.",
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__get_available_indicators",
            "input": {},
            "id": "tu_1",
        },
        {
            "role": "tool",
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": '{"indicators": ["rsi", "macd"]}',
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__save_strategy_config",
            "input": {
                "strategy_name": strategy_name,
                "config": {"indicators": {"rsi": {"period": 14}}},
            },
            "id": "tu_2",
        },
        {
            "role": "tool",
            "type": "tool_result",
            "tool_use_id": "tu_2",
            "content": f'{{"strategy_name": "{strategy_name}", "strategy_path": "strategies/{strategy_name}.yaml"}}',
        },
    ]


def _make_transcript_no_save() -> list[dict]:
    """Build a transcript without a save_strategy_config call."""
    return [
        {
            "role": "assistant",
            "type": "text",
            "content": "I tried but couldn't create a valid strategy.",
        },
        {
            "role": "assistant",
            "type": "tool_use",
            "tool": "mcp__ktrdr__get_available_indicators",
            "input": {},
            "id": "tu_1",
        },
    ]


@pytest.fixture
def mock_ops():
    """Create a mock OperationsService."""
    ops = MagicMock()
    ops.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_test_123"))
    ops.update_operation_progress = AsyncMock()
    ops.complete_operation = AsyncMock()
    ops.fail_operation = AsyncMock()
    return ops


@pytest.fixture
def worker(mock_runtime, mock_ops):
    """Create a DesignAgentWorker with mocked dependencies."""
    from ktrdr.agents.workers.design_agent_worker import DesignAgentWorker

    w = DesignAgentWorker(
        runtime=mock_runtime,
        worker_port=5010,
        backend_url="http://backend:8000",
    )
    # Override operations service with mock (same pattern as test_base.py)
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
    """Tests for POST /designs/start."""

    def test_start_creates_operation_and_returns(self, client):
        """Start endpoint returns operation_id and started status."""
        response = client.post(
            "/designs/start",
            json={
                "task_id": "op_backend_456",
                "brief": "Design a momentum strategy using RSI",
                "symbol": "EURUSD",
                "timeframe": "1h",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_backend_456"
        assert data["status"] == "started"

    def test_start_generates_id_when_no_task_id(self, client):
        """Start endpoint generates operation_id when task_id not provided."""
        response = client.post(
            "/designs/start",
            json={
                "brief": "Design a strategy",
                "symbol": "EURUSD",
                "timeframe": "1h",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"].startswith("worker_design_")

    def test_start_requires_brief(self, client):
        """Start endpoint requires brief field."""
        response = client.post(
            "/designs/start",
            json={
                "task_id": "op_123",
                "symbol": "EURUSD",
                "timeframe": "1h",
            },
        )
        assert response.status_code == 422

    def test_start_requires_symbol(self, client):
        """Start endpoint requires symbol field."""
        response = client.post(
            "/designs/start",
            json={
                "task_id": "op_123",
                "brief": "Design a strategy",
                "timeframe": "1h",
            },
        )
        assert response.status_code == 422

    def test_start_requires_timeframe(self, client):
        """Start endpoint requires timeframe field."""
        response = client.post(
            "/designs/start",
            json={
                "task_id": "op_123",
                "brief": "Design a strategy",
                "symbol": "EURUSD",
            },
        )
        assert response.status_code == 422

    def test_start_accepts_experiment_context(self, client):
        """Start endpoint accepts optional experiment_context."""
        response = client.post(
            "/designs/start",
            json={
                "task_id": "op_123",
                "brief": "Design a strategy",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "experiment_context": "Previous attempts used RSI only.",
            },
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Result Extraction
# ---------------------------------------------------------------------------


class TestResultExtraction:
    """Tests for extracting strategy info from SDK transcript."""

    def test_extract_strategy_from_transcript(self, worker):
        """Extracts strategy_name from save_strategy_config tool call."""
        transcript = _make_transcript_with_save("my_strategy_v1")
        result = worker.extract_strategy_from_transcript(transcript)
        assert result is not None
        assert result["strategy_name"] == "my_strategy_v1"

    def test_extract_returns_none_when_no_save(self, worker):
        """Returns None when transcript has no save_strategy_config call."""
        transcript = _make_transcript_no_save()
        result = worker.extract_strategy_from_transcript(transcript)
        assert result is None

    def test_extract_uses_last_save_call(self, worker):
        """When multiple save calls exist, uses the last one (final iteration)."""
        transcript = _make_transcript_with_save("first_attempt")
        transcript.extend(
            [
                {
                    "role": "assistant",
                    "type": "tool_use",
                    "tool": "mcp__ktrdr__save_strategy_config",
                    "input": {"strategy_name": "final_version"},
                    "id": "tu_3",
                },
                {
                    "role": "tool",
                    "type": "tool_result",
                    "tool_use_id": "tu_3",
                    "content": '{"strategy_name": "final_version", "strategy_path": "strategies/final_version.yaml"}',
                },
            ]
        )
        result = worker.extract_strategy_from_transcript(transcript)
        assert result is not None
        assert result["strategy_name"] == "final_version"

    def test_extract_from_empty_transcript(self, worker):
        """Returns None for empty transcript."""
        result = worker.extract_strategy_from_transcript([])
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Background Execution
# ---------------------------------------------------------------------------


class TestBackgroundExecution:
    """Tests for the background design execution task."""

    @pytest.mark.asyncio
    async def test_successful_design_completes_operation(self, worker, mock_runtime):
        """Successful design invocation completes the operation with result."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Strategy designed successfully.",
            cost_usd=0.08,
            turns=5,
            transcript=_make_transcript_with_save("test_strategy"),
            session_id="sess_abc",
        )

        await worker._execute_design_work(
            operation_id="op_test_123",
            brief="Design a momentum strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        ops = worker.get_operations_service()
        ops.complete_operation.assert_called_once()
        call_kwargs = ops.complete_operation.call_args[1]
        assert call_kwargs["operation_id"] == "op_test_123"
        result = call_kwargs["result_summary"]
        assert result["strategy_name"] == "test_strategy"

    @pytest.mark.asyncio
    async def test_design_without_save_fails_operation(self, worker, mock_runtime):
        """Design that produces no save_strategy_config call fails."""
        mock_runtime.invoke.return_value = AgentResult(
            output="I couldn't produce a valid strategy.",
            cost_usd=0.05,
            turns=3,
            transcript=_make_transcript_no_save(),
            session_id="sess_def",
        )

        await worker._execute_design_work(
            operation_id="op_test_456",
            brief="Design something",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()
        call_kwargs = ops.fail_operation.call_args[1]
        assert call_kwargs["operation_id"] == "op_test_456"
        assert "save_strategy_config" in call_kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_runtime_error_fails_operation(self, worker, mock_runtime):
        """Runtime invoke() raising an exception fails the operation."""
        mock_runtime.invoke.side_effect = RuntimeError("SDK connection failed")

        await worker._execute_design_work(
            operation_id="op_test_789",
            brief="Design a strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()
        call_kwargs = ops.fail_operation.call_args[1]
        assert "SDK connection failed" in call_kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_runtime_passes_correct_params(self, worker, mock_runtime):
        """Runtime invoke() called with correct system prompt and MCP config."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.05,
            turns=2,
            transcript=_make_transcript_with_save("test_strat"),
        )

        await worker._execute_design_work(
            operation_id="op_test_abc",
            brief="Design a momentum strategy using RSI and MACD",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context="Previous experiments favored RSI.",
        )

        mock_runtime.invoke.assert_called_once()
        call_kwargs = mock_runtime.invoke.call_args[1]
        # System prompt should be provided
        assert call_kwargs.get("system_prompt") is not None
        # MCP servers should be configured
        assert call_kwargs.get("mcp_servers") is not None
        assert "ktrdr" in call_kwargs["mcp_servers"]
        # Brief should be in the prompt (positional arg)
        prompt = mock_runtime.invoke.call_args[0][0]
        assert "RSI and MACD" in prompt
        assert "EURUSD" in prompt

    @pytest.mark.asyncio
    async def test_experiment_context_included_in_prompt(self, worker, mock_runtime):
        """Experiment context is included in the user prompt when provided."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.05,
            turns=2,
            transcript=_make_transcript_with_save("ctx_strat"),
        )

        await worker._execute_design_work(
            operation_id="op_ctx_test",
            brief="Design a strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context="RSI-only strategies underperformed. Try combining indicators.",
        )

        prompt = mock_runtime.invoke.call_args[0][0]
        assert "RSI-only strategies underperformed" in prompt


# ---------------------------------------------------------------------------
# Tests: Health Endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
