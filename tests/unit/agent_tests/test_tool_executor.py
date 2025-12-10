"""
Unit tests for ToolExecutor (Task 1.11).

Tests the ToolExecutor class that handles tool calls from the Anthropic API.
The executor routes tool calls to appropriate handlers and returns results.

Test Categories:
1. Tool execution - routing to correct handlers
2. Error handling - graceful failures for unknown tools, exceptions
3. Tool handlers - individual handler tests
4. Integration - full tool call flow
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# Import modules under test
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import AGENT_TOOLS


class TestAgentToolsSchema:
    """Tests for AGENT_TOOLS schema definitions."""

    def test_agent_tools_is_list(self):
        """AGENT_TOOLS should be a list."""
        assert isinstance(AGENT_TOOLS, list)

    def test_agent_tools_has_required_tools(self):
        """AGENT_TOOLS should include all required tools."""
        tool_names = {tool["name"] for tool in AGENT_TOOLS}
        required_tools = {
            "save_strategy_config",
            "get_available_indicators",
            "get_available_symbols",
            "get_recent_strategies",
        }
        assert required_tools.issubset(
            tool_names
        ), f"Missing tools: {required_tools - tool_names}"

    def test_each_tool_has_name(self):
        """Each tool should have a name field."""
        for tool in AGENT_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert isinstance(tool["name"], str)

    def test_each_tool_has_description(self):
        """Each tool should have a description field."""
        for tool in AGENT_TOOLS:
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert isinstance(tool["description"], str)
            assert len(tool["description"]) > 10, "Description too short"

    def test_each_tool_has_input_schema(self):
        """Each tool should have an input_schema field."""
        for tool in AGENT_TOOLS:
            assert "input_schema" in tool, f"Tool missing 'input_schema': {tool}"
            assert isinstance(tool["input_schema"], dict)
            assert tool["input_schema"].get("type") == "object"

    def test_save_strategy_config_schema(self):
        """save_strategy_config tool should have correct schema."""
        tool = next(t for t in AGENT_TOOLS if t["name"] == "save_strategy_config")
        schema = tool["input_schema"]
        props = schema.get("properties", {})

        # Required properties
        assert "name" in props
        assert "config" in props
        assert "description" in props

        # Required fields
        required = schema.get("required", [])
        assert "name" in required
        assert "config" in required

    def test_get_recent_strategies_schema(self):
        """get_recent_strategies tool should have correct schema."""
        tool = next(t for t in AGENT_TOOLS if t["name"] == "get_recent_strategies")
        schema = tool["input_schema"]
        props = schema.get("properties", {})

        # Should have optional 'n' parameter
        assert "n" in props
        assert props["n"].get("type") == "integer"


class TestToolExecutorCreation:
    """Tests for ToolExecutor instantiation."""

    def test_create_executor(self):
        """Should create executor with default settings."""
        executor = ToolExecutor()
        assert executor is not None

    def test_executor_has_handlers(self):
        """Executor should have handler mappings for all tools."""
        executor = ToolExecutor()
        required_tools = {
            "save_strategy_config",
            "get_available_indicators",
            "get_available_symbols",
            "get_recent_strategies",
        }
        assert hasattr(executor, "handlers")
        for tool in required_tools:
            assert tool in executor.handlers, f"Missing handler for: {tool}"


class TestToolExecutorExecution:
    """Tests for ToolExecutor.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_error(self):
        """Executing unknown tool should return error dict."""
        executor = ToolExecutor()
        result = await executor.execute("unknown_tool", {})

        assert isinstance(result, dict)
        assert "error" in result
        assert "unknown" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self):
        """Execute should always return a dict."""
        executor = ToolExecutor()

        # Mock a successful handler
        executor.handlers["test_tool"] = AsyncMock(return_value={"success": True})

        result = await executor.execute("test_tool", {})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_catches_handler_exceptions(self):
        """Handler exceptions should be caught and returned as error."""
        executor = ToolExecutor()

        # Mock a handler that raises
        executor.handlers["failing_tool"] = AsyncMock(
            side_effect=ValueError("Test error")
        )

        result = await executor.execute("failing_tool", {})

        assert isinstance(result, dict)
        assert "error" in result
        assert "Test error" in result["error"]


class TestSaveStrategyConfigHandler:
    """Tests for save_strategy_config tool handler."""

    @pytest.mark.asyncio
    async def test_save_strategy_calls_service(self):
        """save_strategy_config should call strategy service."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._save_strategy_config") as mock_save:
            mock_save.return_value = {
                "success": True,
                "path": "/tmp/test.yaml",
            }

            result = await executor.execute(
                "save_strategy_config",
                {
                    "name": "test_strategy",
                    "config": {"scope": "universal"},
                    "description": "Test strategy",
                },
            )

            mock_save.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_strategy_passes_parameters(self):
        """save_strategy_config should pass correct parameters."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._save_strategy_config") as mock_save:
            mock_save.return_value = {"success": True}

            await executor.execute(
                "save_strategy_config",
                {
                    "name": "my_strategy",
                    "config": {"indicators": []},
                    "description": "My test",
                },
            )

            # Check the call arguments
            call_kwargs = mock_save.call_args.kwargs
            assert call_kwargs.get("name") == "my_strategy"
            assert call_kwargs.get("description") == "My test"


class TestGetRecentStrategiesHandler:
    """Tests for get_recent_strategies tool handler."""

    @pytest.mark.asyncio
    async def test_get_recent_strategies_calls_service(self):
        """get_recent_strategies should call strategy service."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._get_recent_strategies") as mock_get:
            mock_get.return_value = [
                {"name": "strat1", "outcome": "success"},
                {"name": "strat2", "outcome": "failed"},
            ]

            result = await executor.execute("get_recent_strategies", {"n": 5})

            mock_get.assert_called_once_with(n=5)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_recent_strategies_default_n(self):
        """get_recent_strategies should use default n=5 if not provided."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._get_recent_strategies") as mock_get:
            mock_get.return_value = []

            await executor.execute("get_recent_strategies", {})

            mock_get.assert_called_once_with(n=5)


class TestGetAvailableIndicatorsHandler:
    """Tests for get_available_indicators tool handler."""

    @pytest.mark.asyncio
    async def test_get_indicators_calls_api(self):
        """get_available_indicators should call API client."""
        executor = ToolExecutor()

        # Mock the API client
        mock_indicators = [
            {"name": "RSI", "category": "momentum"},
            {"name": "MACD", "category": "momentum"},
        ]

        with patch("ktrdr.agents.executor.get_indicators_from_api") as mock_get:
            mock_get.return_value = mock_indicators

            result = await executor.execute("get_available_indicators", {})

            mock_get.assert_called_once()
            assert len(result) == 2
            assert result[0]["name"] == "RSI"


class TestGetAvailableSymbolsHandler:
    """Tests for get_available_symbols tool handler."""

    @pytest.mark.asyncio
    async def test_get_symbols_calls_api(self):
        """get_available_symbols should call API client."""
        executor = ToolExecutor()

        mock_symbols = [
            {"symbol": "EURUSD", "instrument_type": "forex"},
            {"symbol": "AAPL", "instrument_type": "stock"},
        ]

        with patch("ktrdr.agents.executor.get_symbols_from_api") as mock_get:
            mock_get.return_value = mock_symbols

            result = await executor.execute("get_available_symbols", {})

            mock_get.assert_called_once()
            assert len(result) == 2


class TestToolExecutorCallableInterface:
    """Tests for using ToolExecutor as callable (for invoker compatibility)."""

    @pytest.mark.asyncio
    async def test_executor_is_callable(self):
        """ToolExecutor should be callable (support __call__)."""
        executor = ToolExecutor()

        # Mock handler
        executor.handlers["test_tool"] = AsyncMock(return_value={"ok": True})

        # Should be callable with (tool_name, tool_input)
        result = await executor("test_tool", {})
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_callable_matches_execute_signature(self):
        """__call__ should have same behavior as execute()."""
        executor = ToolExecutor()

        # Test unknown tool via callable
        result = await executor("nonexistent_tool", {})
        assert "error" in result


class TestToolExecutorWithRealServices:
    """Integration-style tests with mocked services.

    These tests verify the executor correctly integrates with the
    underlying services without calling real databases or APIs.
    """

    @pytest.mark.asyncio
    async def test_full_save_flow(self):
        """Test full save_strategy_config flow."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._save_strategy_config") as mock_save:
            mock_save.return_value = {
                "success": True,
                "path": "/path/to/strategy.yaml",
                "message": "Saved successfully",
            }

            result = await executor.execute(
                "save_strategy_config",
                {
                    "name": "momentum_v1",
                    "config": {
                        "scope": "universal",
                        "indicators": [{"name": "rsi", "period": 14}],
                    },
                    "description": "Momentum strategy with RSI",
                },
            )

            assert result["success"] is True
            assert "path" in result

    @pytest.mark.asyncio
    async def test_validation_failure_returned(self):
        """Test that validation failures are returned correctly."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor._save_strategy_config") as mock_save:
            mock_save.return_value = {
                "success": False,
                "errors": ["Invalid indicator: xyz"],
                "suggestions": ["Did you mean 'rsi'?"],
            }

            result = await executor.execute(
                "save_strategy_config",
                {
                    "name": "bad_strategy",
                    "config": {"indicators": [{"name": "xyz"}]},
                    "description": "Bad strategy",
                },
            )

            assert result["success"] is False
            assert "errors" in result
            assert len(result["errors"]) > 0
