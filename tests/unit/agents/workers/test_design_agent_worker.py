"""Unit tests for DesignAgentWorker.

Tests the containerized design agent worker that uses AgentRuntime
to invoke Claude Code with MCP for strategy design.

Comprehensive coverage per Task 3.4:
- Start endpoint: valid requests, validation errors, optional fields
- Result extraction: save tool call parsing, multiple saves, empty transcript, path extraction
- Background execution: success, no save, runtime error, timeout, prompt composition
- Health endpoint
"""

import asyncio
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


class TestBackgroundExecutionExtended:
    """Extended tests for background execution — timeout, result fields, prompt composition."""

    @pytest.mark.asyncio
    async def test_timeout_error_fails_operation(self, worker, mock_runtime):
        """Runtime invoke() timeout is caught and fails the operation."""
        mock_runtime.invoke.side_effect = asyncio.TimeoutError()

        await worker._execute_design_work(
            operation_id="op_timeout",
            brief="Design a strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        ops = worker.get_operations_service()
        ops.fail_operation.assert_called_once()
        call_kwargs = ops.fail_operation.call_args[1]
        assert call_kwargs["operation_id"] == "op_timeout"

    @pytest.mark.asyncio
    async def test_result_summary_contains_all_fields(self, worker, mock_runtime):
        """Completed operation result_summary includes cost, turns, session_id."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.12,
            turns=7,
            transcript=_make_transcript_with_save("full_fields_strategy"),
            session_id="sess_xyz_123",
        )

        await worker._execute_design_work(
            operation_id="op_fields",
            brief="Design a strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        ops = worker.get_operations_service()
        result = ops.complete_operation.call_args[1]["result_summary"]
        assert result["strategy_name"] == "full_fields_strategy"
        assert result["strategy_path"] == "strategies/full_fields_strategy.yaml"
        assert result["cost_usd"] == 0.12
        assert result["turns"] == 7
        assert result["session_id"] == "sess_xyz_123"

    @pytest.mark.asyncio
    async def test_system_prompt_is_design_prompt(self, worker, mock_runtime):
        """System prompt passed to runtime is the DESIGN_SYSTEM_PROMPT."""
        from ktrdr.agents.design_sdk_prompt import DESIGN_SYSTEM_PROMPT

        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.01,
            turns=1,
            transcript=_make_transcript_with_save("prompt_test"),
        )

        await worker._execute_design_work(
            operation_id="op_prompt",
            brief="Test brief",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        call_kwargs = mock_runtime.invoke.call_args[1]
        assert call_kwargs["system_prompt"] == DESIGN_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_mcp_servers_include_ktrdr(self, worker, mock_runtime):
        """MCP servers config includes ktrdr server with correct command."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.01,
            turns=1,
            transcript=_make_transcript_with_save("mcp_test"),
        )

        await worker._execute_design_work(
            operation_id="op_mcp",
            brief="Test",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )

        mcp_servers = mock_runtime.invoke.call_args[1]["mcp_servers"]
        assert "ktrdr" in mcp_servers
        assert mcp_servers["ktrdr"]["command"] == "bash"

    @pytest.mark.asyncio
    async def test_user_prompt_without_context(self, worker, mock_runtime):
        """User prompt contains brief, symbol, timeframe but no context section."""
        mock_runtime.invoke.return_value = AgentResult(
            output="Done.",
            cost_usd=0.01,
            turns=1,
            transcript=_make_transcript_with_save("no_ctx"),
        )

        await worker._execute_design_work(
            operation_id="op_no_ctx",
            brief="Design a mean reversion strategy",
            symbol="GBPJPY",
            timeframe="4h",
            experiment_context=None,
        )

        prompt = mock_runtime.invoke.call_args[0][0]
        assert "mean reversion" in prompt
        assert "GBPJPY" in prompt
        assert "4h" in prompt
        assert "Experiment Context" not in prompt


# ---------------------------------------------------------------------------
# Tests: Result Extraction Extended
# ---------------------------------------------------------------------------


class TestResultExtractionExtended:
    """Extended tests for transcript parsing edge cases."""

    def test_extract_returns_strategy_path(self, worker):
        """Extracts strategy_path from tool_result content."""
        transcript = _make_transcript_with_save("path_test")
        result = worker.extract_strategy_from_transcript(transcript)
        assert result is not None
        assert result["strategy_path"] == "strategies/path_test.yaml"

    def test_extract_handles_malformed_tool_result(self, worker):
        """Handles tool_result with non-JSON content gracefully."""
        transcript = [
            {
                "type": "tool_use",
                "tool": "mcp__ktrdr__save_strategy_config",
                "input": {"strategy_name": "malformed_test"},
                "id": "tu_bad",
            },
            {
                "type": "tool_result",
                "tool_use_id": "tu_bad",
                "content": "Error: validation failed",
            },
        ]
        result = worker.extract_strategy_from_transcript(transcript)
        # Should still extract strategy_name from tool_use input
        assert result is not None
        assert result["strategy_name"] == "malformed_test"
        assert result["strategy_path"] is None

    def test_extract_ignores_non_save_tools(self, worker):
        """Other tool calls are ignored during extraction."""
        transcript = [
            {
                "type": "tool_use",
                "tool": "mcp__ktrdr__validate_strategy",
                "input": {"strategy_name": "ignore_me"},
                "id": "tu_validate",
            },
            {
                "type": "tool_result",
                "tool_use_id": "tu_validate",
                "content": '{"valid": true}',
            },
        ]
        result = worker.extract_strategy_from_transcript(transcript)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Prompt Composition
# ---------------------------------------------------------------------------


class TestPromptComposition:
    """Tests for _build_user_prompt method."""

    def test_prompt_contains_brief_section(self, worker):
        """User prompt includes Research Brief section."""
        prompt = worker._build_user_prompt(
            brief="Design RSI strategy",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )
        assert "## Research Brief" in prompt
        assert "Design RSI strategy" in prompt

    def test_prompt_contains_target_section(self, worker):
        """User prompt includes Target section with symbol and timeframe."""
        prompt = worker._build_user_prompt(
            brief="Test",
            symbol="USDJPY",
            timeframe="15m",
            experiment_context=None,
        )
        assert "## Target" in prompt
        assert "Symbol: USDJPY" in prompt
        assert "Timeframe: 15m" in prompt

    def test_prompt_includes_context_when_provided(self, worker):
        """User prompt includes Experiment Context section when provided."""
        prompt = worker._build_user_prompt(
            brief="Test",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context="RSI-only failed, try MACD.",
        )
        assert "## Experiment Context" in prompt
        assert "RSI-only failed, try MACD." in prompt

    def test_prompt_excludes_context_when_none(self, worker):
        """User prompt does not include Experiment Context when None."""
        prompt = worker._build_user_prompt(
            brief="Test",
            symbol="EURUSD",
            timeframe="1h",
            experiment_context=None,
        )
        assert "Experiment Context" not in prompt


# ---------------------------------------------------------------------------
# Tests: Health Endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
