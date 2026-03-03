"""
MCP tools for strategy management.

Provides MCP tool wrappers for strategy operations:
- validate_strategy: Validate a strategy file (v3 format detection)
- save_strategy_config: Validate and save a v3 strategy atomically
- get_recent_strategies: List recent strategies with context

The actual business logic is in ktrdr.mcp.strategy_service
to allow proper unit testing without FastMCP dependencies.
"""

from typing import Any

from ktrdr.mcp.strategy_service import get_recent_strategies as _get_recent_strategies
from ktrdr.mcp.strategy_service import save_strategy_config as _save_strategy_config
from ktrdr.mcp.strategy_service import validate_strategy as _validate_strategy
from mcp.server.fastmcp import FastMCP

from ..telemetry import trace_mcp_tool

# Re-export for direct access (e.g., in smoke tests)
validate_strategy = _validate_strategy
save_strategy_config = _save_strategy_config
get_recent_strategies = _get_recent_strategies


def register_strategy_tools(mcp: FastMCP) -> None:
    """Register strategy management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
    """

    @trace_mcp_tool("validate_strategy")
    @mcp.tool(name="validate_strategy")
    async def validate_strategy_tool(path: str) -> dict[str, Any]:
        """
        Validate a strategy file.

        Use this tool to check if a strategy configuration file is valid
        and get information about its format (v3 vs v2).

        Args:
            path: Path to the strategy YAML file

        Returns:
            Dict with structure:
            {
                "valid": bool,         # True if strategy is valid v3
                "format": str,         # "v3", "v2", or "unknown"
                "features": list,      # Feature IDs (if v3 valid)
                "feature_count": int,  # Number of features (if v3 valid)
                "errors": list,        # Error messages (if invalid)
                "suggestion": str      # Migration suggestion (if v2)
            }

        Examples:
            # Validate a v3 strategy
            result = await validate_strategy("strategies/momentum_v3.yaml")
            if result["valid"]:
                print(f"Valid v3 strategy with {result['feature_count']} features")
            else:
                print(f"Errors: {result['errors']}")

            # Check if migration is needed
            if result["format"] == "v2":
                print(result["suggestion"])  # Run 'ktrdr strategy migrate' to upgrade

        Notes:
            - V3 format has indicators as dict + nn_inputs section
            - V2 format has indicators as list + feature_id per indicator
            - Use 'ktrdr strategy migrate' to upgrade v2 to v3
        """
        return await _validate_strategy(path)

    @trace_mcp_tool("save_strategy_config")
    @mcp.tool(name="save_strategy_config")
    async def save_strategy_config_tool(
        strategy_name: str,
        strategy_yaml: str,
    ) -> dict[str, Any]:
        """
        Save a validated v3 strategy configuration.

        Validates the strategy YAML as v3 format first, then saves atomically.
        Invalid strategies are rejected — no file is created.

        Args:
            strategy_name: Name for the strategy (used as filename)
            strategy_yaml: Complete strategy configuration as YAML string

        Returns:
            Dict with structure on success:
            {
                "success": true,
                "strategy_name": str,
                "strategy_path": str
            }
            On failure:
            {
                "success": false,
                "errors": list[str]
            }

        Examples:
            # Save a new strategy
            result = await save_strategy_config(
                strategy_name="my_rsi_strategy",
                strategy_yaml="name: my_rsi_strategy\\n..."
            )
            if result["success"]:
                print(f"Saved to {result['strategy_path']}")

        Notes:
            - Only v3 format strategies are accepted
            - Validates before saving (atomic: validate-then-write)
            - Overwrites existing strategy with same name
            - Strategy is saved to the strategies/ directory
        """
        return await _save_strategy_config(
            strategy_name=strategy_name,
            strategy_yaml=strategy_yaml,
        )

    @trace_mcp_tool("get_recent_strategies")
    @mcp.tool(name="get_recent_strategies")
    async def get_recent_strategies_tool(
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recent strategies sorted by date with context.

        Returns recently created/modified strategies with their indicators,
        creation date, and last assessment outcome. Use this to see what
        strategies have been tried and their results.

        Args:
            limit: Maximum number of strategies to return (default 10)

        Returns:
            List of dicts with structure:
            [
                {
                    "name": str,
                    "description": str,
                    "indicators": list[str],
                    "created_date": str,          # ISO timestamp
                    "assessment_verdict": str|null, # "promising"|"neutral"|"poor"|null
                    "path": str
                }
            ]

        Examples:
            # See recent strategies
            strategies = await get_recent_strategies(limit=5)
            for s in strategies:
                verdict = s["assessment_verdict"] or "not assessed"
                print(f"{s['name']}: {verdict}")

        Notes:
            - Sorted by modification date, newest first
            - Includes assessment verdict if available
            - Returns all YAML strategies (v2 and v3)
        """
        return await _get_recent_strategies(limit=limit)
