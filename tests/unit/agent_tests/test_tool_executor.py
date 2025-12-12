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


class TestValidateStrategyConfigTool:
    """Tests for validate_strategy_config tool (Task 1.14 optional)."""

    def test_validate_strategy_config_in_tools(self):
        """validate_strategy_config tool should be in AGENT_TOOLS."""
        tool_names = {tool["name"] for tool in AGENT_TOOLS}
        assert "validate_strategy_config" in tool_names

    def test_validate_strategy_config_schema(self):
        """validate_strategy_config tool should have correct schema."""
        tool = next(
            (t for t in AGENT_TOOLS if t["name"] == "validate_strategy_config"), None
        )
        assert tool is not None, "validate_strategy_config tool not found"

        schema = tool["input_schema"]
        props = schema.get("properties", {})

        # Should have config property
        assert "config" in props
        assert props["config"]["type"] == "object"

        # config should be required
        required = schema.get("required", [])
        assert "config" in required

    def test_validate_strategy_config_has_handler(self):
        """ToolExecutor should have handler for validate_strategy_config."""
        executor = ToolExecutor()
        assert "validate_strategy_config" in executor.handlers

    @pytest.mark.asyncio
    async def test_validate_strategy_config_returns_validation_result(self):
        """validate_strategy_config should return validation result."""
        executor = ToolExecutor()

        # Valid config should pass
        valid_config = {
            "name": "test_strategy",
            "scope": "universal",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {
                "rsi_14": {"low": {"type": "triangular", "parameters": [0, 30, 50]}}
            },
            "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
            "decisions": {"output_format": "classification"},
            "training": {"method": "supervised"},
        }

        with patch("ktrdr.agents.executor._validate_strategy_config") as mock_validate:
            mock_validate.return_value = {"valid": True, "errors": []}

            result = await executor.execute(
                "validate_strategy_config", {"config": valid_config}
            )

            mock_validate.assert_called_once()
            assert "valid" in result

    @pytest.mark.asyncio
    async def test_validate_strategy_config_returns_errors(self):
        """validate_strategy_config should return errors for invalid config."""
        executor = ToolExecutor()

        invalid_config = {
            "name": "bad_strategy",
            "indicators": [{"name": "unknown_indicator"}],  # Missing feature_id
        }

        with patch("ktrdr.agents.executor._validate_strategy_config") as mock_validate:
            mock_validate.return_value = {
                "valid": False,
                "errors": [
                    "Unknown indicator: unknown_indicator",
                    "Missing feature_id",
                ],
                "suggestions": ["Did you mean 'RSI'?"],
            }

            result = await executor.execute(
                "validate_strategy_config", {"config": invalid_config}
            )

            assert result["valid"] is False
            assert len(result["errors"]) > 0
            assert "suggestions" in result


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


class TestStartTrainingToolSchema:
    """Tests for start_training tool schema (Task 2.1)."""

    def test_start_training_in_agent_tools(self):
        """start_training tool should be in AGENT_TOOLS."""
        tool_names = {tool["name"] for tool in AGENT_TOOLS}
        assert "start_training" in tool_names

    def test_start_training_schema(self):
        """start_training tool should have correct schema."""
        tool = next((t for t in AGENT_TOOLS if t["name"] == "start_training"), None)
        assert tool is not None, "start_training tool not found"

        schema = tool["input_schema"]
        props = schema.get("properties", {})

        # Should have required properties
        assert "strategy_name" in props
        assert props["strategy_name"]["type"] == "string"

        # Should have optional properties
        assert "symbols" in props
        assert props["symbols"]["type"] == "array"

        assert "timeframes" in props
        assert props["timeframes"]["type"] == "array"

        assert "start_date" in props
        assert props["start_date"]["type"] == "string"

        assert "end_date" in props
        assert props["end_date"]["type"] == "string"

        # strategy_name should be required
        required = schema.get("required", [])
        assert "strategy_name" in required

    def test_start_training_has_description(self):
        """start_training tool should have meaningful description."""
        tool = next((t for t in AGENT_TOOLS if t["name"] == "start_training"), None)
        assert tool is not None
        assert "description" in tool
        assert "training" in tool["description"].lower()
        assert len(tool["description"]) > 20


class TestStartTrainingToolHandler:
    """Tests for start_training tool handler (Task 2.1)."""

    def test_start_training_has_handler(self):
        """ToolExecutor should have handler for start_training."""
        executor = ToolExecutor()
        assert "start_training" in executor.handlers

    @pytest.mark.asyncio
    async def test_start_training_calls_training_service(self):
        """start_training should call training service."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.return_value = {
                "success": True,
                "operation_id": "op_training_123",
                "status": "started",
            }

            result = await executor.execute(
                "start_training",
                {
                    "strategy_name": "test_strategy",
                    "symbols": ["EURUSD"],
                    "timeframes": ["1h"],
                },
            )

            mock_start.assert_called_once()
            assert result["success"] is True
            assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_start_training_passes_all_parameters(self):
        """start_training should pass all parameters correctly."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.return_value = {
                "success": True,
                "operation_id": "op_training_456",
            }

            await executor.execute(
                "start_training",
                {
                    "strategy_name": "momentum_v1",
                    "symbols": ["EURUSD", "GBPUSD"],
                    "timeframes": ["1h", "4h"],
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                },
            )

            # Verify all parameters passed
            call_kwargs = mock_start.call_args.kwargs
            assert call_kwargs.get("strategy_name") == "momentum_v1"
            assert call_kwargs.get("symbols") == ["EURUSD", "GBPUSD"]
            assert call_kwargs.get("timeframes") == ["1h", "4h"]
            assert call_kwargs.get("start_date") == "2024-01-01"
            assert call_kwargs.get("end_date") == "2024-06-30"

    @pytest.mark.asyncio
    async def test_start_training_with_defaults(self):
        """start_training should work with only required parameters."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.return_value = {
                "success": True,
                "operation_id": "op_training_789",
            }

            result = await executor.execute(
                "start_training",
                {"strategy_name": "simple_strategy"},
            )

            mock_start.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_start_training_returns_operation_id(self):
        """start_training should return operation_id for tracking."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.return_value = {
                "success": True,
                "operation_id": "op_training_abc123",
                "status": "started",
                "message": "Training started",
            }

            result = await executor.execute(
                "start_training",
                {"strategy_name": "test_strategy"},
            )

            assert "operation_id" in result
            assert result["operation_id"] == "op_training_abc123"

    @pytest.mark.asyncio
    async def test_start_training_handles_api_error(self):
        """start_training should handle API errors gracefully."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.side_effect = Exception("API connection failed")

            result = await executor.execute(
                "start_training",
                {"strategy_name": "test_strategy"},
            )

            assert "error" in result
            assert "API connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_start_training_handles_service_failure(self):
        """start_training should return failure response from service."""
        executor = ToolExecutor()

        with patch("ktrdr.agents.executor.start_training_via_api") as mock_start:
            mock_start.return_value = {
                "success": False,
                "error": "Strategy not found: unknown_strategy",
            }

            result = await executor.execute(
                "start_training",
                {"strategy_name": "unknown_strategy"},
            )

            assert result["success"] is False
            assert "error" in result
