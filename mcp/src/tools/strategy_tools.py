"""
MCP tools for strategy management.

Provides MCP tool wrappers for strategy operations:
- save_strategy_config: Validate and save strategy to disk

The actual business logic is in research_agents.services.strategy_service
to allow proper unit testing.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from research_agents.services.strategy_service import (
    save_strategy_config as _save_strategy_config,
)

from ..telemetry import trace_mcp_tool


def register_strategy_tools(mcp: FastMCP) -> None:
    """Register strategy management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
    """

    @trace_mcp_tool("save_strategy_config")
    @mcp.tool()
    async def save_strategy_config(
        name: str,
        config: dict[str, Any],
        description: str,
    ) -> dict[str, Any]:
        """
        Validate and save a strategy configuration to disk.

        Use this tool to save agent-designed strategies. The strategy will be
        validated against KTRDR's requirements before saving.

        Args:
            name: Strategy name (file saved as strategies/{name}.yaml)
            config: Complete strategy configuration dictionary including:
                - indicators: List of technical indicators
                - fuzzy_sets: Fuzzy membership functions for each indicator
                - model: Neural network configuration
                - decisions: Decision output configuration
                - training: Training methodology configuration
            description: Human-readable description of the strategy

        Returns:
            Dict with structure:
            {
                "success": bool,
                "path": str,        # Absolute path to saved file (if success)
                "message": str,     # Success or error message
                "errors": list,     # List of error messages (if failed)
                "suggestions": list # Suggestions for fixing errors (if failed)
            }

        Examples:
            # Save a momentum-based strategy
            result = await save_strategy_config(
                name="momentum_rsi_macd",
                config={
                    "scope": "universal",
                    "indicators": [...],
                    "fuzzy_sets": {...},
                    "model": {...},
                    "decisions": {...},
                    "training": {...}
                },
                description="Momentum strategy using RSI and MACD"
            )

            if result["success"]:
                print(f"Saved to: {result['path']}")
            else:
                print(f"Errors: {result['errors']}")

        See Also:
            - get_available_indicators(): See available indicators
            - get_available_strategies(): List existing strategies

        Notes:
            - Strategy names must be unique
            - Indicator types are validated against KTRDR's registry
            - Fuzzy membership parameters are validated
            - Strategy saved to strategies/ folder
        """
        return await _save_strategy_config(
            name=name,
            config=config,
            description=description,
        )
