"""MCP (Model Context Protocol) business logic for KTRDR.

This module contains the business logic used by MCP tools.
The actual MCP tool wrappers are in mcp/src/tools/.

Separating business logic from MCP wrappers allows:
1. Unit testing without FastMCP dependencies
2. Reuse of logic across different contexts
"""

from ktrdr.mcp.strategy_service import validate_strategy

__all__ = ["validate_strategy"]
