"""
Unit tests for AnthropicAgentInvoker.

Tests cover:
- AgentResult dataclass
- AnthropicInvokerConfig loading from environment
- Anthropic API invocation with agentic loop
- Tool execution within the loop
- Token tracking
- Error handling
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result with token counts."""
        from ktrdr.agents.invoker import AgentResult

        result = AgentResult(
            success=True,
            output="Strategy designed successfully.",
            input_tokens=1500,
            output_tokens=800,
            error=None,
        )
        assert result.success is True
        assert result.output == "Strategy designed successfully."
        assert result.input_tokens == 1500
        assert result.output_tokens == 800
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed result with error."""
        from ktrdr.agents.invoker import AgentResult

        result = AgentResult(
            success=False,
            output=None,
            input_tokens=100,
            output_tokens=0,
            error="API rate limit exceeded",
        )
        assert result.success is False
        assert result.output is None
        assert result.error == "API rate limit exceeded"

    def test_total_tokens_property(self):
        """Test that total tokens can be calculated."""
        from ktrdr.agents.invoker import AgentResult

        result = AgentResult(
            success=True,
            output="Done",
            input_tokens=1000,
            output_tokens=500,
            error=None,
        )
        # Total tokens = input + output
        assert result.input_tokens + result.output_tokens == 1500


class TestAnthropicInvokerConfig:
    """Tests for AnthropicInvokerConfig."""

    def test_default_config(self):
        """Test default configuration values.

        Note: Default changed from Sonnet to Opus in Task 8.3 for production quality.
        """
        from ktrdr.agents.invoker import DEFAULT_MODEL, AnthropicInvokerConfig

        config = AnthropicInvokerConfig()
        assert config.model == DEFAULT_MODEL
        assert config.model == "claude-opus-4-5-20250514"
        assert config.max_tokens == 4096

    def test_config_with_opus_model(self):
        """Test configuration with Opus model."""
        from ktrdr.agents.invoker import AnthropicInvokerConfig

        config = AnthropicInvokerConfig(model="claude-opus-4-5-20250514")
        assert config.model == "claude-opus-4-5-20250514"

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        from ktrdr.agents.invoker import AnthropicInvokerConfig

        with patch.dict(
            "os.environ",
            {
                "AGENT_MODEL": "claude-opus-4-5-20250514",
                "AGENT_MAX_TOKENS": "8192",
            },
        ):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == "claude-opus-4-5-20250514"
            assert config.max_tokens == 8192

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults.

        Note: Default changed from Sonnet to Opus in Task 8.3.
        """
        from ktrdr.agents.invoker import DEFAULT_MODEL, AnthropicInvokerConfig

        with patch.dict("os.environ", {}, clear=False):
            # Remove specific keys if they exist
            import os

            for key in ["AGENT_MODEL", "AGENT_MAX_TOKENS"]:
                os.environ.pop(key, None)

            config = AnthropicInvokerConfig.from_env()
            assert config.model == DEFAULT_MODEL
            assert config.max_tokens == 4096


class TestAnthropicAgentInvoker:
    """Tests for AnthropicAgentInvoker."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        mock_client = MagicMock()
        return mock_client

    @pytest.fixture
    def invoker_with_mock_client(self, mock_anthropic_client):
        """Create invoker with mocked Anthropic client."""
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig

        config = AnthropicInvokerConfig(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
        )
        invoker = AnthropicAgentInvoker(config=config)
        invoker.client = mock_anthropic_client
        return invoker

    def _create_mock_response(
        self,
        content: list[dict[str, Any]],
        input_tokens: int = 100,
        output_tokens: int = 50,
        stop_reason: str = "end_turn",
    ):
        """Helper to create a mock Anthropic API response."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = input_tokens
        mock_response.usage.output_tokens = output_tokens
        mock_response.stop_reason = stop_reason

        # Create content blocks
        mock_blocks = []
        for item in content:
            block = MagicMock()
            block.type = item.get("type", "text")
            if block.type == "text":
                block.text = item.get("text", "")
            elif block.type == "tool_use":
                block.id = item.get("id", "tool_123")
                block.name = item.get("name", "test_tool")
                block.input = item.get("input", {})
            mock_blocks.append(block)

        mock_response.content = mock_blocks
        return mock_response

    @pytest.mark.asyncio
    async def test_invoke_simple_text_response(self, invoker_with_mock_client):
        """Test invocation that returns a simple text response (no tools)."""
        invoker = invoker_with_mock_client

        # Setup mock response
        mock_response = self._create_mock_response(
            content=[{"type": "text", "text": "I've designed a strategy."}],
            input_tokens=500,
            output_tokens=200,
        )
        invoker.client.messages.create = MagicMock(return_value=mock_response)

        result = await invoker.run(
            prompt="Design a trading strategy",
            tools=[],
            system_prompt="You are a strategy designer.",
        )

        assert result.success is True
        assert "designed a strategy" in result.output
        assert result.input_tokens == 500
        assert result.output_tokens == 200
        assert result.error is None

    @pytest.mark.asyncio
    async def test_invoke_with_tool_call(self, invoker_with_mock_client):
        """Test invocation with a single tool call that executes."""
        invoker = invoker_with_mock_client

        # First response: tool call
        tool_call_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_abc123",
                    "name": "get_available_indicators",
                    "input": {},
                }
            ],
            input_tokens=300,
            output_tokens=100,
            stop_reason="tool_use",
        )

        # Second response: final text after tool result
        final_response = self._create_mock_response(
            content=[
                {"type": "text", "text": "Based on the indicators, I designed..."}
            ],
            input_tokens=400,
            output_tokens=150,
        )

        # Setup mock to return different responses
        call_count = 0

        def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tool_call_response
            return final_response

        invoker.client.messages.create = mock_create

        # Mock tool executor
        async def mock_execute(tool_name: str, tool_input: dict) -> dict:
            if tool_name == "get_available_indicators":
                return {"indicators": ["rsi", "macd", "ema"]}
            return {"error": "Unknown tool"}

        result = await invoker.run(
            prompt="Design a strategy using available indicators",
            tools=[
                {
                    "name": "get_available_indicators",
                    "description": "Get available indicators",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
            system_prompt="You are a strategy designer.",
            tool_executor=mock_execute,
        )

        assert result.success is True
        assert "designed" in result.output.lower()
        # Token counts should be accumulated
        assert result.input_tokens == 700  # 300 + 400
        assert result.output_tokens == 250  # 100 + 150

    @pytest.mark.asyncio
    async def test_invoke_multiple_tool_calls(self, invoker_with_mock_client):
        """Test invocation with multiple sequential tool calls."""
        invoker = invoker_with_mock_client

        # Response 1: first tool call
        resp1 = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "get_available_indicators",
                    "input": {},
                }
            ],
            input_tokens=200,
            output_tokens=50,
            stop_reason="tool_use",
        )

        # Response 2: second tool call
        resp2 = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_2",
                    "name": "get_available_symbols",
                    "input": {},
                }
            ],
            input_tokens=300,
            output_tokens=60,
            stop_reason="tool_use",
        )

        # Response 3: final text
        resp3 = self._create_mock_response(
            content=[{"type": "text", "text": "Strategy complete."}],
            input_tokens=400,
            output_tokens=100,
        )

        responses = [resp1, resp2, resp3]
        call_idx = 0

        def mock_create(*args, **kwargs):
            nonlocal call_idx
            resp = responses[call_idx]
            call_idx += 1
            return resp

        invoker.client.messages.create = mock_create

        async def mock_execute(tool_name: str, tool_input: dict) -> dict:
            return {"result": f"data from {tool_name}"}

        result = await invoker.run(
            prompt="Design strategy",
            tools=[
                {
                    "name": "get_available_indicators",
                    "description": "Get indicators",
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_available_symbols",
                    "description": "Get symbols",
                    "input_schema": {"type": "object", "properties": {}},
                },
            ],
            system_prompt="Design a strategy.",
            tool_executor=mock_execute,
        )

        assert result.success is True
        # Total tokens accumulated across all calls
        assert result.input_tokens == 900  # 200 + 300 + 400
        assert result.output_tokens == 210  # 50 + 60 + 100

    @pytest.mark.asyncio
    async def test_invoke_api_error_handling(self, invoker_with_mock_client):
        """Test handling of Anthropic API errors."""
        invoker = invoker_with_mock_client

        # Simulate API error
        invoker.client.messages.create = MagicMock(
            side_effect=Exception("API rate limit exceeded")
        )

        result = await invoker.run(
            prompt="Design a strategy",
            tools=[],
            system_prompt="You are a designer.",
        )

        assert result.success is False
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_tool_execution_error(self, invoker_with_mock_client):
        """Test handling of tool execution errors."""
        invoker = invoker_with_mock_client

        # Tool call response
        tool_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "failing_tool",
                    "input": {},
                }
            ],
            input_tokens=100,
            output_tokens=50,
            stop_reason="tool_use",
        )

        # Final response after error
        final_response = self._create_mock_response(
            content=[{"type": "text", "text": "I encountered an error with the tool."}],
            input_tokens=200,
            output_tokens=75,
        )

        responses = [tool_response, final_response]
        idx = 0

        def mock_create(*args, **kwargs):
            nonlocal idx
            r = responses[idx]
            idx += 1
            return r

        invoker.client.messages.create = mock_create

        async def failing_executor(tool_name: str, tool_input: dict) -> dict:
            return {"error": "Tool execution failed: database connection error"}

        result = await invoker.run(
            prompt="Use a tool",
            tools=[
                {
                    "name": "failing_tool",
                    "description": "A tool that fails",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
            system_prompt="Test.",
            tool_executor=failing_executor,
        )

        # Agent should still complete, but with error communicated in loop
        assert result.success is True
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_invoke_no_tool_executor_skips_tools(self, invoker_with_mock_client):
        """Test that tool calls without executor return error results."""
        invoker = invoker_with_mock_client

        # Tool call response
        tool_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "some_tool",
                    "input": {},
                }
            ],
            input_tokens=100,
            output_tokens=50,
            stop_reason="tool_use",
        )

        final_response = self._create_mock_response(
            content=[{"type": "text", "text": "Continuing without tool."}],
            input_tokens=150,
            output_tokens=50,
        )

        responses = [tool_response, final_response]
        idx = 0

        def mock_create(*args, **kwargs):
            nonlocal idx
            r = responses[idx]
            idx += 1
            return r

        invoker.client.messages.create = mock_create

        # No tool executor provided
        result = await invoker.run(
            prompt="Design",
            tools=[{"name": "some_tool", "description": "Test", "input_schema": {}}],
            system_prompt="Test.",
            tool_executor=None,
        )

        # Should complete, with tool result indicating no executor
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_extracts_text_from_response(self, invoker_with_mock_client):
        """Test that text is correctly extracted from mixed content."""
        invoker = invoker_with_mock_client

        # Response with text
        mock_response = self._create_mock_response(
            content=[
                {"type": "text", "text": "First part. "},
                {"type": "text", "text": "Second part."},
            ],
            input_tokens=100,
            output_tokens=50,
        )
        invoker.client.messages.create = MagicMock(return_value=mock_response)

        result = await invoker.run(
            prompt="Test",
            tools=[],
            system_prompt="Test.",
        )

        assert result.success is True
        # Both text blocks should be combined
        assert "First part" in result.output
        assert "Second part" in result.output


class TestTokenBudgetLimitsEnforcement:
    """Tests for token budget limits enforcement in run() (Task 8.5)."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        mock_client = MagicMock()
        return mock_client

    @pytest.fixture
    def invoker_with_low_limits(self, mock_anthropic_client):
        """Create invoker with low limits for testing."""
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig

        config = AnthropicInvokerConfig(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            max_iterations=3,  # Low limit for testing
            max_input_tokens=1000,  # Low limit for testing
        )
        invoker = AnthropicAgentInvoker(config=config)
        invoker.client = mock_anthropic_client
        return invoker

    def _create_mock_response(
        self,
        content: list[dict],
        input_tokens: int = 100,
        output_tokens: int = 50,
        stop_reason: str = "end_turn",
    ):
        """Helper to create a mock Anthropic API response."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = input_tokens
        mock_response.usage.output_tokens = output_tokens
        mock_response.stop_reason = stop_reason

        mock_blocks = []
        for item in content:
            block = MagicMock()
            block.type = item.get("type", "text")
            if block.type == "text":
                block.text = item.get("text", "")
            elif block.type == "tool_use":
                block.id = item.get("id", "tool_123")
                block.name = item.get("name", "test_tool")
                block.input = item.get("input", {})
            mock_blocks.append(block)

        mock_response.content = mock_blocks
        return mock_response

    @pytest.mark.asyncio
    async def test_max_iterations_prevents_infinite_loop(self, invoker_with_low_limits):
        """Max iterations prevents infinite tool call loops."""
        invoker = invoker_with_low_limits

        # Create a response that always requests a tool (infinite loop)
        tool_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "infinite_tool",
                    "input": {},
                }
            ],
            input_tokens=100,
            output_tokens=50,
            stop_reason="tool_use",
        )

        # Always return tool call (would be infinite without limit)
        invoker.client.messages.create = MagicMock(return_value=tool_response)

        async def mock_execute(tool_name: str, tool_input: dict) -> dict:
            return {"result": "ok"}

        result = await invoker.run(
            prompt="Do something",
            tools=[
                {"name": "infinite_tool", "description": "Test", "input_schema": {}}
            ],
            system_prompt="Test.",
            tool_executor=mock_execute,
        )

        # Should fail with clear error message about iteration limit
        assert result.success is False
        assert "iteration" in result.error.lower() or "loop" in result.error.lower()
        assert "3" in result.error  # Should mention the limit

    @pytest.mark.asyncio
    async def test_max_input_tokens_circuit_breaker(self, invoker_with_low_limits):
        """Max input tokens prevents expensive API calls."""
        invoker = invoker_with_low_limits

        # Create a response that reports high input tokens on second call
        first_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "growing_tool",
                    "input": {},
                }
            ],
            input_tokens=500,  # Under limit
            output_tokens=50,
            stop_reason="tool_use",
        )

        second_response = self._create_mock_response(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_2",
                    "name": "growing_tool",
                    "input": {},
                }
            ],
            input_tokens=2000,  # Over the 1000 limit
            output_tokens=100,
            stop_reason="tool_use",
        )

        responses = [first_response, second_response]
        idx = 0

        def mock_create(*args, **kwargs):
            nonlocal idx
            r = responses[idx]
            idx += 1
            return r

        invoker.client.messages.create = mock_create

        async def mock_execute(tool_name: str, tool_input: dict) -> dict:
            return {"result": "large data " * 100}  # Returns lots of data

        result = await invoker.run(
            prompt="Do something",
            tools=[{"name": "growing_tool", "description": "Test", "input_schema": {}}],
            system_prompt="Test.",
            tool_executor=mock_execute,
        )

        # Should fail with clear error about input tokens
        assert result.success is False
        assert "token" in result.error.lower() or "input" in result.error.lower()

    @pytest.mark.asyncio
    async def test_iteration_error_message_is_clear(self, invoker_with_low_limits):
        """Iteration limit error message is clear and actionable."""
        invoker = invoker_with_low_limits

        tool_response = self._create_mock_response(
            content=[{"type": "tool_use", "id": "t1", "name": "tool", "input": {}}],
            stop_reason="tool_use",
        )
        invoker.client.messages.create = MagicMock(return_value=tool_response)

        async def mock_execute(tool_name: str, tool_input: dict) -> dict:
            return {"result": "ok"}

        result = await invoker.run(
            prompt="Do",
            tools=[{"name": "tool", "description": "Test", "input_schema": {}}],
            system_prompt="Test.",
            tool_executor=mock_execute,
        )

        assert result.success is False
        # Error should mention iterations and the limit
        assert "iteration" in result.error.lower() or "exceeded" in result.error.lower()


class TestAnthropicAgentInvokerProtocol:
    """Test that AnthropicAgentInvoker implements the AgentInvoker protocol."""

    def test_implements_invoke_method(self):
        """Verify the invoker has the required invoke method signature."""
        from ktrdr.agents.invoker import AnthropicAgentInvoker

        # Check that the class has run method (our implementation)
        assert hasattr(AnthropicAgentInvoker, "run")

        # Check it's callable
        invoker = AnthropicAgentInvoker.__new__(AnthropicAgentInvoker)
        assert callable(getattr(invoker, "run", None))

    def test_result_type_matches_protocol(self):
        """Verify AgentResult has required fields for the protocol."""
        from ktrdr.agents.invoker import AgentResult

        # Check required attributes
        result = AgentResult(
            success=True,
            output="test",
            input_tokens=0,
            output_tokens=0,
            error=None,
        )

        assert hasattr(result, "success")
        assert hasattr(result, "output")
        assert hasattr(result, "input_tokens")
        assert hasattr(result, "output_tokens")
        assert hasattr(result, "error")
