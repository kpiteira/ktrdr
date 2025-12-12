"""
Tool executor for agent tool calls.

This module provides the ToolExecutor class that handles tool calls from
the Anthropic API. It routes tool calls to appropriate handlers and
returns results in the expected format.

The ToolExecutor is passed to AnthropicAgentInvoker.run() as the tool_executor
parameter. When Claude makes a tool call, the invoker calls:
    result = await tool_executor(tool_name, tool_input)

The executor then routes to the appropriate handler and returns a dict result.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

# Import service functions for strategy operations
from research_agents.services.strategy_service import (
    get_recent_strategies as _get_recent_strategies,
)
from research_agents.services.strategy_service import (
    save_strategy_config as _save_strategy_config,
)
from research_agents.services.strategy_service import (
    validate_strategy_config as _validate_strategy_config,
)

logger = structlog.get_logger(__name__)

# Type alias for async handler functions
# Handler results can be dict or list (for tools returning collections)
HandlerResult = dict[str, Any] | list[dict[str, Any]]
HandlerFunc = Callable[..., Coroutine[Any, Any, HandlerResult]]


async def get_indicators_from_api() -> list[dict[str, Any]]:
    """Fetch available indicators from the KTRDR API.

    Returns:
        List of indicator dicts with name, category, parameters, etc.
    """
    import httpx

    # Get API URL from environment
    base_url = os.getenv("KTRDR_API_URL", "http://localhost:8000")
    api_url = f"{base_url}/api/v1/indicators/"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()
            # API returns {"success": true, "data": [...]}
            return data.get("data", [])
    except Exception as e:
        logger.error("Failed to get indicators from API", error=str(e))
        return []


async def get_symbols_from_api() -> list[dict[str, Any]]:
    """Fetch available symbols from the KTRDR API.

    Returns:
        List of symbol dicts with symbol, instrument_type, timeframes, etc.
    """
    import httpx

    # Get API URL from environment
    base_url = os.getenv("KTRDR_API_URL", "http://localhost:8000")
    api_url = f"{base_url}/api/v1/symbols"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()
            # API returns {"success": true, "data": [...]}
            return data.get("data", [])
    except Exception as e:
        logger.error("Failed to get symbols from API", error=str(e))
        return []


class ToolExecutor:
    """Executor for agent tool calls.

    Routes tool calls to appropriate handlers and returns results.
    Implements the ToolExecutor protocol expected by AnthropicAgentInvoker.

    Usage:
        executor = ToolExecutor()

        # Via execute method
        result = await executor.execute("save_strategy_config", {...})

        # Via callable interface (for invoker compatibility)
        result = await executor("save_strategy_config", {...})

    Attributes:
        handlers: Mapping of tool names to handler functions.
    """

    def __init__(self) -> None:
        """Initialize the tool executor with handler mappings."""
        self.handlers: dict[str, HandlerFunc] = {
            "validate_strategy_config": self._handle_validate_strategy_config,
            "save_strategy_config": self._handle_save_strategy_config,
            "get_available_indicators": self._handle_get_available_indicators,
            "get_available_symbols": self._handle_get_available_symbols,
            "get_recent_strategies": self._handle_get_recent_strategies,
        }

    async def execute(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> HandlerResult:
        """Execute a tool call by routing to the appropriate handler.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Result from the tool handler. On success, contains tool-specific data
            (either a dict or list of dicts). On failure, returns {"error": "message"}.
        """
        handler = self.handlers.get(tool_name)

        if handler is None:
            logger.warning("Unknown tool requested", tool_name=tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            logger.info("Executing tool", tool_name=tool_name)
            result = await handler(**tool_input)
            logger.info("Tool executed successfully", tool_name=tool_name)
            return result
        except Exception as e:
            logger.error(
                "Tool execution failed",
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return {"error": f"Tool execution failed: {str(e)}"}

    async def __call__(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> HandlerResult:
        """Execute a tool call (callable interface).

        This allows the executor to be used directly as the tool_executor
        parameter for AnthropicAgentInvoker.run().

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Result from the tool handler (dict or list of dicts).
        """
        return await self.execute(tool_name, tool_input)

    # ================
    # Handler Methods
    # ================

    async def _handle_validate_strategy_config(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle validate_strategy_config tool call.

        Validates a strategy configuration without saving.

        Args:
            config: Strategy configuration dict.

        Returns:
            Dict with valid status, errors, warnings, and suggestions.
        """
        return await _validate_strategy_config(config=config)

    async def _handle_save_strategy_config(
        self,
        name: str,
        config: dict[str, Any],
        description: str = "",
    ) -> dict[str, Any]:
        """Handle save_strategy_config tool call.

        Validates and saves a strategy configuration to disk.

        Args:
            name: Strategy name.
            config: Strategy configuration dict.
            description: Strategy description.

        Returns:
            Dict with success status, path, errors, etc.
        """
        return await _save_strategy_config(
            name=name,
            config=config,
            description=description,
        )

    async def _handle_get_available_indicators(self) -> list[dict[str, Any]]:
        """Handle get_available_indicators tool call.

        Returns:
            List of available indicators with parameters.
        """
        return await get_indicators_from_api()

    async def _handle_get_available_symbols(self) -> list[dict[str, Any]]:
        """Handle get_available_symbols tool call.

        Returns:
            List of available symbols with timeframes.
        """
        return await get_symbols_from_api()

    async def _handle_get_recent_strategies(
        self,
        n: int = 5,
    ) -> list[dict[str, Any]]:
        """Handle get_recent_strategies tool call.

        Args:
            n: Number of strategies to return.

        Returns:
            List of recent strategy summaries.
        """
        # Clamp n to valid range
        n = max(1, min(n, 20))
        return await _get_recent_strategies(n=n)


# Convenience function for creating executor
def create_tool_executor() -> ToolExecutor:
    """Create a configured ToolExecutor instance.

    Returns:
        Configured ToolExecutor ready for use with AnthropicAgentInvoker.
    """
    return ToolExecutor()
