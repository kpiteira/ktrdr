"""
Agent state management service.

Provides functions for managing agent session state:
- create_agent_session: Create new session
- get_agent_state: Get session state
- update_agent_state: Update session state

These functions are used by MCP tools and can be tested independently.
"""

from typing import Any

import structlog

from research_agents.database.queries import get_agent_db
from research_agents.database.schema import SessionPhase

logger = structlog.get_logger(__name__)


async def create_agent_session() -> dict[str, Any]:
    """
    Create a new agent research session.

    Returns:
        Dict with session_id, phase, and status.
    """
    try:
        db = await get_agent_db()
        session = await db.create_session()

        result = {
            "success": True,
            "session_id": session.id,
            "phase": session.phase.value,
            "message": f"Created new session {session.id}",
        }

        # Log the action
        await db.log_action(
            session_id=session.id,
            tool_name="create_agent_session",
            tool_args={},
            result=result,
        )

        logger.info("Agent session created", session_id=session.id)
        return result

    except Exception as e:
        logger.error("Failed to create agent session", error=str(e), exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create session",
        }


async def get_agent_state(session_id: int) -> dict[str, Any]:
    """
    Get the current state of an agent session.

    Args:
        session_id: The session ID to retrieve.

    Returns:
        Dict with session data or error.
    """
    try:
        db = await get_agent_db()
        session = await db.get_session(session_id)

        if session is None:
            return {
                "success": False,
                "error": f"Session {session_id} not found",
                "message": "Session does not exist",
            }

        logger.info(
            "Agent state retrieved", session_id=session_id, phase=session.phase.value
        )
        return {
            "success": True,
            "session": {
                "id": session.id,
                "phase": session.phase.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
                if session.updated_at
                else None,
                "strategy_name": session.strategy_name,
                "operation_id": session.operation_id,
                "outcome": session.outcome.value if session.outcome else None,
            },
        }

    except Exception as e:
        logger.error(
            "Failed to get agent state",
            session_id=session_id,
            error=str(e),
            exc_info=True,
        )
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get session state",
        }


async def update_agent_state(
    session_id: int,
    phase: str,
    strategy_name: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """
    Update the state of an agent session.

    Args:
        session_id: The session ID to update.
        phase: New phase for the session.
        strategy_name: Optional strategy name.
        operation_id: Optional KTRDR operation ID.

    Returns:
        Dict with updated session data or error.
    """
    # Validate phase
    try:
        session_phase = SessionPhase(phase)
    except ValueError:
        valid_phases = [p.value for p in SessionPhase]
        return {
            "success": False,
            "error": f"Invalid phase '{phase}'. Valid phases: {valid_phases}",
            "message": "Invalid phase value",
        }

    try:
        db = await get_agent_db()
        session = await db.update_session(
            session_id=session_id,
            phase=session_phase,
            strategy_name=strategy_name,
            operation_id=operation_id,
        )

        result = {
            "success": True,
            "session": {
                "id": session.id,
                "phase": session.phase.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
                if session.updated_at
                else None,
                "strategy_name": session.strategy_name,
                "operation_id": session.operation_id,
                "outcome": session.outcome.value if session.outcome else None,
            },
            "message": f"Session {session_id} updated to phase '{phase}'",
        }

        # Log the action
        await db.log_action(
            session_id=session_id,
            tool_name="update_agent_state",
            tool_args={
                "session_id": session_id,
                "phase": phase,
                "strategy_name": strategy_name,
                "operation_id": operation_id,
            },
            result=result,
        )

        logger.info(
            "Agent state updated",
            session_id=session_id,
            phase=phase,
            strategy_name=strategy_name,
        )
        return result

    except ValueError as e:
        # Session not found
        return {
            "success": False,
            "error": str(e),
            "message": f"Session {session_id} not found",
        }

    except Exception as e:
        logger.error(
            "Failed to update agent state",
            session_id=session_id,
            phase=phase,
            error=str(e),
            exc_info=True,
        )
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to update session state",
        }
