"""
MCP tools for strategy management.

Provides MCP tool wrappers for strategy operations:
- validate_strategy: Validate a strategy file (v3 format detection)

The actual business logic is in ktrdr.mcp.strategy_service
to allow proper unit testing without FastMCP dependencies.
"""

from typing import Any

from ktrdr.mcp.strategy_service import validate_strategy as _validate_strategy
from mcp.server.fastmcp import FastMCP

from ..telemetry import trace_mcp_tool

# Re-export validate_strategy for direct access (e.g., in smoke tests)
# This allows: from mcp.src.tools.strategy_tools import validate_strategy
validate_strategy = _validate_strategy


def register_strategy_tools(mcp: FastMCP) -> None:
    """Register strategy management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
    """

    @trace_mcp_tool("validate_strategy")
    @mcp.tool()
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
