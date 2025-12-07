"""
MCP tools for agent state management.

Provides MCP tool wrappers for agent session management:
- create_agent_session: Create new session
- get_agent_state: Get session state
- update_agent_state: Update session state

The actual business logic is in research_agents.services.agent_state
to allow proper unit testing.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from research_agents.services.agent_state import (
    create_agent_session as _create_session,
)
from research_agents.services.agent_state import (
    get_agent_state as _get_state,
)
from research_agents.services.agent_state import (
    update_agent_state as _update_state,
)

from ..telemetry import trace_mcp_tool


def register_agent_tools(mcp: FastMCP) -> None:
    """Register agent state management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
    """

    @trace_mcp_tool("create_agent_session")
    @mcp.tool()
    async def create_agent_session() -> dict[str, Any]:
        """
        Create a new agent research session.

        Initializes a new session in IDLE phase. Call this at the start of
        a new research cycle before designing a strategy.

        Returns:
            Dict with structure:
            {
                "success": bool,
                "session_id": int,   # Use this ID for all subsequent calls
                "phase": str,        # "idle"
                "message": str
            }

        Examples:
            # Start a new research cycle
            result = await create_agent_session()
            session_id = result["session_id"]
            # Now use session_id with update_agent_state()

        Notes:
            - Creates session in IDLE phase
            - Session ID is required for all state updates
            - One active session at a time (complete or fail before starting new)
        """
        return await _create_session()

    @trace_mcp_tool("get_agent_state")
    @mcp.tool()
    async def get_agent_state(session_id: int) -> dict[str, Any]:
        """
        Get the current state of an agent session.

        Retrieves the full session state including phase, strategy name,
        operation ID, and any outcome.

        Args:
            session_id: The session ID returned from create_agent_session()

        Returns:
            Dict with structure:
            {
                "success": bool,
                "session": {
                    "id": int,
                    "phase": str,           # idle/designing/training/backtesting/assessing/complete
                    "created_at": str,      # ISO timestamp
                    "updated_at": str,      # ISO timestamp or null
                    "strategy_name": str,   # Strategy being designed or null
                    "operation_id": str,    # KTRDR operation ID or null
                    "outcome": str          # Final outcome or null
                }
            }

        Examples:
            # Check current session state
            result = await get_agent_state(session_id=42)
            if result["success"]:
                phase = result["session"]["phase"]
                print(f"Current phase: {phase}")

        Notes:
            - Returns error if session_id not found
            - Use to check state before transitions
        """
        return await _get_state(session_id)

    @trace_mcp_tool("update_agent_state")
    @mcp.tool()
    async def update_agent_state(
        session_id: int,
        phase: str,
        strategy_name: str | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update the state of an agent session.

        Transitions the session to a new phase and optionally sets strategy name
        or operation ID. Use this to progress through the research cycle.

        Args:
            session_id: The session ID to update
            phase: New phase for the session. Valid values:
                - "idle": Initial state
                - "designing": Designing a strategy
                - "training": Training neural network
                - "backtesting": Running backtest
                - "assessing": Assessing results
                - "complete": Cycle complete
            strategy_name: Optional strategy name being worked on
            operation_id: Optional KTRDR operation ID (for training/backtest)

        Returns:
            Dict with structure:
            {
                "success": bool,
                "session": {
                    "id": int,
                    "phase": str,
                    "strategy_name": str,
                    "operation_id": str,
                    ...
                },
                "message": str
            }

        Examples:
            # Transition to designing phase
            await update_agent_state(session_id=42, phase="designing")

            # Start training with operation tracking
            await update_agent_state(
                session_id=42,
                phase="training",
                strategy_name="neuro_mean_reversion",
                operation_id="op_training_123"
            )

        Notes:
            - Invalid phase values return error
            - Session must exist
            - State changes are logged for observability
        """
        return await _update_state(session_id, phase, strategy_name, operation_id)
