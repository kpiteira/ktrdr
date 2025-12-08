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
    get_recent_strategies as _get_recent_strategies,
)
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

    @trace_mcp_tool("get_recent_strategies")
    @mcp.tool()
    async def get_recent_strategies(n: int = 5) -> list[dict[str, Any]]:
        """
        Get the N most recent strategies designed by the agent.

        Use this tool to see what strategies have been tried recently.
        Helps avoid repeating similar strategies and enables novelty.

        Args:
            n: Number of recent strategies to return (default 5, max 20)

        Returns:
            List of strategy summaries with structure:
            [
                {
                    "name": str,        # Strategy name
                    "type": str | None, # Model type (e.g., "mlp", "lstm")
                    "indicators": list, # List of indicator names used
                    "outcome": str,     # Session outcome (success, failed_training, etc.)
                    "created_at": str   # ISO timestamp of when strategy was created
                }
            ]

        Examples:
            # Get last 5 strategies (default)
            strategies = await get_recent_strategies()

            # Check what was tried recently
            for s in strategies:
                print(f"{s['name']}: {s['outcome']} - {s['indicators']}")

            # Get more history
            strategies = await get_recent_strategies(n=10)

        Notes:
            - Strategies are ordered by creation date (most recent first)
            - Failed sessions may have partial info (null type/indicators)
            - Use this before designing to ensure novelty
        """
        # Clamp n to reasonable range
        n = max(1, min(n, 20))
        return await _get_recent_strategies(n=n)
