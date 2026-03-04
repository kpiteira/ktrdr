"""Tests for ClaudeAgentRuntime — claude-agent-sdk backed AgentRuntime."""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ktrdr.agents.runtime.protocol import AgentResult, AgentRuntime, AgentRuntimeConfig


def _make_mock_sdk(
    *,
    result_output: str = "done",
    result_session_id: str | None = None,
    result_cost: float | None = 0.0,
    result_turns: int = 0,
    assistant_blocks: list | None = None,
    query_side_effect: Exception | None = None,
):
    """Build a mock SDK module with configurable query behavior."""
    sdk = SimpleNamespace()

    # Exception types
    sdk.CLIConnectionError = type("CLIConnectionError", (Exception,), {})

    # Message types as real classes for isinstance checks
    class _ResultMessage:
        pass

    class _AssistantMessage:
        pass

    class _TextBlock:
        pass

    class _ToolUseBlock:
        pass

    class _ToolResultBlock:
        pass

    sdk.ResultMessage = _ResultMessage
    sdk.AssistantMessage = _AssistantMessage
    sdk.TextBlock = _TextBlock
    sdk.ToolUseBlock = _ToolUseBlock
    sdk.ToolResultBlock = _ToolResultBlock

    # Options captures args
    class _Options:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.env = {}

    sdk.ClaudeAgentOptions = _Options

    # Build result message instance
    result_msg = _ResultMessage()
    result_msg.session_id = result_session_id
    result_msg.total_cost_usd = result_cost
    result_msg.num_turns = result_turns
    result_msg.result = result_output

    # Build assistant messages
    assistant_msgs = []
    if assistant_blocks:
        msg = _AssistantMessage()
        msg.content = assistant_blocks
        assistant_msgs.append(msg)

    # Query as async generator
    async def _query(prompt, options, **kwargs):
        if query_side_effect:
            raise query_side_effect
        for amsg in assistant_msgs:
            yield amsg
        yield result_msg

    sdk.query = _query

    return sdk


class TestClaudeAgentRuntimeProtocol:
    """Verify ClaudeAgentRuntime satisfies AgentRuntime protocol."""

    def test_satisfies_protocol(self) -> None:
        """ClaudeAgentRuntime is an instance of AgentRuntime."""
        mock_sdk = _make_mock_sdk()
        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            config = AgentRuntimeConfig()
            runtime = ClaudeAgentRuntime(config=config)
            assert isinstance(runtime, AgentRuntime)


class TestClaudeAgentRuntimeInvoke:
    """Tests for invoke() with mocked SDK."""

    @pytest.mark.asyncio()
    async def test_invoke_returns_agent_result(self) -> None:
        """invoke() returns an AgentResult from SDK response."""
        mock_sdk = _make_mock_sdk(
            result_output="Strategy designed",
            result_session_id="sess_123",
            result_cost=0.05,
            result_turns=3,
        )
        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("design a strategy")

        assert isinstance(result, AgentResult)
        assert result.output == "Strategy designed"
        assert result.cost_usd == 0.05
        assert result.turns == 3
        assert result.session_id == "sess_123"

    @pytest.mark.asyncio()
    async def test_invoke_with_custom_parameters(self) -> None:
        """invoke() passes custom parameters to SDK options."""
        captured = {}
        mock_sdk = _make_mock_sdk()

        original_query = mock_sdk.query

        async def capturing_query(prompt, options, **kwargs):
            captured["model"] = options.model
            captured["max_turns"] = options.max_turns
            captured["max_budget_usd"] = options.max_budget_usd
            async for msg in original_query(prompt, options, **kwargs):
                yield msg

        mock_sdk.query = capturing_query

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            await runtime.invoke(
                "test",
                model="claude-opus-4-6",
                max_turns=5,
                max_budget_usd=2.0,
            )

        assert captured["model"] == "claude-opus-4-6"
        assert captured["max_turns"] == 5
        assert captured["max_budget_usd"] == 2.0

    @pytest.mark.asyncio()
    async def test_invoke_uses_config_model_as_default(self) -> None:
        """invoke() uses config model when no model param is passed."""
        captured = {}
        mock_sdk = _make_mock_sdk()
        original_query = mock_sdk.query

        async def capturing_query(prompt, options, **kwargs):
            captured["model"] = options.model
            async for msg in original_query(prompt, options, **kwargs):
                yield msg

        mock_sdk.query = capturing_query

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(
                config=AgentRuntimeConfig(model="claude-sonnet-4-6")
            )
            await runtime.invoke("test")

        assert captured["model"] == "claude-sonnet-4-6"


class TestClaudeCodeEnvVar:
    """Tests for CLAUDECODE env var removal and restoration."""

    @pytest.mark.asyncio()
    async def test_claudecode_removed_before_spawn(self) -> None:
        """CLAUDECODE is removed from env before SDK query runs."""
        env_during_query = {}
        mock_sdk = _make_mock_sdk()
        original_query = mock_sdk.query

        async def capturing_query(prompt, options, **kwargs):
            env_during_query["CLAUDECODE"] = os.environ.get("CLAUDECODE")
            async for msg in original_query(prompt, options, **kwargs):
                yield msg

        mock_sdk.query = capturing_query

        os.environ["CLAUDECODE"] = "1"
        try:
            with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
                from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

                runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
                await runtime.invoke("test")

            assert env_during_query["CLAUDECODE"] is None
        finally:
            os.environ.pop("CLAUDECODE", None)

    @pytest.mark.asyncio()
    async def test_claudecode_restored_after_invoke(self) -> None:
        """CLAUDECODE is restored after invoke completes."""
        mock_sdk = _make_mock_sdk()

        os.environ["CLAUDECODE"] = "1"
        try:
            with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
                from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

                runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
                await runtime.invoke("test")

            assert os.environ.get("CLAUDECODE") == "1"
        finally:
            os.environ.pop("CLAUDECODE", None)

    @pytest.mark.asyncio()
    async def test_claudecode_restored_after_error(self) -> None:
        """CLAUDECODE is restored even when query raises."""
        mock_sdk = _make_mock_sdk(query_side_effect=RuntimeError("SDK crash"))

        os.environ["CLAUDECODE"] = "1"
        try:
            with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
                from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

                runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
                result = await runtime.invoke("test")

            assert "error" in result.output.lower()
            assert os.environ.get("CLAUDECODE") == "1"
        finally:
            os.environ.pop("CLAUDECODE", None)


class TestTranscriptConversion:
    """Tests for SDK block to transcript dict conversion."""

    @pytest.mark.asyncio()
    async def test_text_block_in_transcript(self) -> None:
        """TextBlock is converted to transcript entry."""
        mock_sdk = _make_mock_sdk(result_output="done", result_turns=1)

        # Create a proper TextBlock instance
        text_block = mock_sdk.TextBlock()
        text_block.text = "I will design a strategy"

        # Rebuild with assistant blocks
        mock_sdk_with_blocks = _make_mock_sdk(
            result_output="done",
            result_turns=1,
            assistant_blocks=[text_block],
        )
        # Use the same TextBlock class so isinstance works
        mock_sdk_with_blocks.TextBlock = mock_sdk.TextBlock

        with patch(
            "ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk_with_blocks
        ):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert len(result.transcript) == 1
        assert result.transcript[0]["role"] == "assistant"
        assert result.transcript[0]["type"] == "text"
        assert result.transcript[0]["content"] == "I will design a strategy"

    @pytest.mark.asyncio()
    async def test_tool_use_block_in_transcript(self) -> None:
        """ToolUseBlock is converted to transcript entry with tool details."""
        mock_sdk = _make_mock_sdk()

        tool_block = mock_sdk.ToolUseBlock()
        tool_block.name = "mcp__ktrdr__get_available_indicators"
        tool_block.input = {"category": "momentum"}
        tool_block.id = "tool_123"

        mock_sdk_with_blocks = _make_mock_sdk(
            result_output="done",
            result_turns=1,
            assistant_blocks=[tool_block],
        )
        mock_sdk_with_blocks.ToolUseBlock = mock_sdk.ToolUseBlock

        with patch(
            "ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk_with_blocks
        ):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert len(result.transcript) == 1
        assert result.transcript[0]["type"] == "tool_use"
        assert result.transcript[0]["tool"] == "mcp__ktrdr__get_available_indicators"
        assert result.transcript[0]["id"] == "tool_123"

    @pytest.mark.asyncio()
    async def test_tool_result_block_in_transcript(self) -> None:
        """ToolResultBlock is converted to transcript entry."""
        mock_sdk = _make_mock_sdk()

        result_block = mock_sdk.ToolResultBlock()
        result_block.tool_use_id = "tool_123"
        result_block.content = "RSI, MACD, Bollinger"

        mock_sdk_with_blocks = _make_mock_sdk(
            result_output="done",
            result_turns=1,
            assistant_blocks=[result_block],
        )
        mock_sdk_with_blocks.ToolResultBlock = mock_sdk.ToolResultBlock

        with patch(
            "ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk_with_blocks
        ):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert len(result.transcript) == 1
        assert result.transcript[0]["type"] == "tool_result"
        assert result.transcript[0]["tool_use_id"] == "tool_123"


class TestCostAndTurnTracking:
    """Tests for cost and turn tracking from SDK response."""

    @pytest.mark.asyncio()
    async def test_cost_from_result_message(self) -> None:
        """Cost and turns are extracted from ResultMessage."""
        mock_sdk = _make_mock_sdk(
            result_output="Strategy complete",
            result_session_id="sess_abc",
            result_cost=0.42,
            result_turns=7,
        )

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert result.cost_usd == 0.42
        assert result.turns == 7

    @pytest.mark.asyncio()
    async def test_null_cost_defaults_to_zero(self) -> None:
        """Null cost_usd in ResultMessage defaults to 0.0."""
        mock_sdk = _make_mock_sdk(result_cost=None)

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert result.cost_usd == 0.0


class TestErrorRecovery:
    """Tests for error handling and retry behavior."""

    @pytest.mark.asyncio()
    async def test_cli_connection_error_triggers_retry(self) -> None:
        """CLIConnectionError triggers one retry before returning error."""
        call_count = 0
        mock_sdk = _make_mock_sdk()

        async def counting_query(prompt, options, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise mock_sdk.CLIConnectionError("Connection failed")
            # Second call succeeds
            result_msg = mock_sdk.ResultMessage()
            result_msg.session_id = "sess_retry"
            result_msg.total_cost_usd = 0.01
            result_msg.num_turns = 1
            result_msg.result = "retried OK"
            yield result_msg

        mock_sdk.query = counting_query

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert call_count == 2
        assert result.output == "retried OK"

    @pytest.mark.asyncio()
    async def test_generic_error_returns_error_result(self) -> None:
        """Non-retryable errors return an error AgentResult."""
        mock_sdk = _make_mock_sdk(query_side_effect=ValueError("Something broke"))

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert isinstance(result, AgentResult)
        assert "error" in result.output.lower()
        assert result.cost_usd == 0.0
        assert result.turns == 0

    @pytest.mark.asyncio()
    async def test_cli_connection_error_both_fail(self) -> None:
        """When both attempts fail with CLIConnectionError, returns error result."""
        mock_sdk = _make_mock_sdk()

        async def always_fail(prompt, options, **kwargs):
            raise mock_sdk.CLIConnectionError("Connection failed")
            yield  # noqa: B027

        mock_sdk.query = always_fail

        with patch("ktrdr.agents.runtime.claude._get_sdk", return_value=mock_sdk):
            from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

            runtime = ClaudeAgentRuntime(config=AgentRuntimeConfig())
            result = await runtime.invoke("test")

        assert "error" in result.output.lower()
        assert "retry" in result.output.lower()
