"""
Agent API service layer.

This service wraps the TriggerService to provide API-compatible responses
for agent management endpoints.
"""

from typing import Any

from ktrdr import get_logger
from research_agents.database.queries import get_agent_db
from research_agents.services.trigger import TriggerConfig

logger = get_logger(__name__)


class AgentService:
    """Service layer for agent API operations.

    This class provides methods that map to the API endpoints:
    - trigger: Trigger a research cycle
    - get_status: Get current agent status
    - list_sessions: List recent sessions

    The service wraps the TriggerService and AgentDatabase to provide
    API-compatible response structures.
    """

    def __init__(self):
        """Initialize the agent service."""
        self._config = TriggerConfig.from_env()
        self._db = None  # Lazy initialization

    async def _get_db(self):
        """Get database instance (lazy initialization)."""
        if self._db is None:
            self._db = await get_agent_db()
        return self._db

    async def trigger(self, dry_run: bool = False) -> dict[str, Any]:
        """Trigger a research cycle.

        Args:
            dry_run: If True, check conditions but don't actually trigger.

        Returns:
            Dict with trigger result including:
            - success: Whether the operation completed
            - triggered: Whether a new cycle was started
            - session_id: New session ID (if triggered)
            - reason: Why it wasn't triggered (if not)
            - message: Human-readable status message
        """
        db = await self._get_db()

        # Check if agent is enabled
        if not self._config.enabled:
            return {
                "success": True,
                "triggered": False,
                "reason": "disabled",
                "message": "Agent trigger is disabled",
            }

        # Check for active session
        active_session = await db.get_active_session()
        if active_session is not None:
            return {
                "success": True,
                "triggered": False,
                "reason": "active_session_exists",
                "active_session_id": active_session.id,
                "message": f"Active session exists (#{active_session.id})",
            }

        if dry_run:
            return {
                "success": True,
                "triggered": False,
                "dry_run": True,
                "would_trigger": True,
                "message": "Dry run - would trigger new cycle",
            }

        # Import here to avoid circular imports
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig
        from ktrdr.api.services.agent_context import AgentMCPContextProvider
        from research_agents.services.trigger import TriggerService

        # Create and use TriggerService with modern AnthropicAgentInvoker (Task 1.10)
        invoker_config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=invoker_config)
        context_provider = AgentMCPContextProvider()

        service = TriggerService(
            config=self._config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
            tool_executor=None,  # Task 1.11 will add ToolExecutor
        )

        try:
            result = await service.check_and_trigger()
            return {
                "success": True,
                "triggered": result.get("triggered", False),
                "session_id": result.get("session_id"),
                "reason": result.get("reason"),
                "message": (
                    "Research cycle started"
                    if result.get("triggered")
                    else result.get("reason", "Not triggered")
                ),
            }
        except Exception as e:
            logger.error(f"Failed to trigger agent: {e}")
            return {
                "success": False,
                "triggered": False,
                "error": str(e),
                "message": f"Failed to trigger: {str(e)}",
            }

    async def get_status(self, verbose: bool = False) -> dict[str, Any]:
        """Get current agent status.

        Args:
            verbose: If True, include additional details like recent actions.

        Returns:
            Dict with status information including:
            - has_active_session: Whether there's an active session
            - session: Session details if active
            - agent_enabled: Whether agent is enabled
            - recent_actions: List of recent actions (if verbose)
        """
        db = await self._get_db()

        active_session = await db.get_active_session()

        result: dict[str, Any] = {
            "has_active_session": active_session is not None,
            "agent_enabled": self._config.enabled,
        }

        if active_session is not None:
            result["session"] = {
                "id": active_session.id,
                "phase": active_session.phase.value,
                "strategy_name": active_session.strategy_name,
                "operation_id": active_session.operation_id,
                "created_at": active_session.created_at.isoformat() + "Z",
                "updated_at": (
                    active_session.updated_at.isoformat() + "Z"
                    if active_session.updated_at
                    else None
                ),
            }

            if verbose:
                # Get recent actions for this session
                actions = await db.get_session_actions(active_session.id)
                result["recent_actions"] = [
                    {
                        "tool_name": action.tool_name,
                        "result": (
                            "success" if action.result.get("success") else "failure"
                        ),
                        "created_at": action.created_at.isoformat() + "Z",
                    }
                    for action in actions[-5:]  # Last 5 actions
                ]
        else:
            result["session"] = None

        return result

    async def list_sessions(self, limit: int = 10) -> dict[str, Any]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            Dict with sessions list and total count.
        """
        db = await self._get_db()

        # Get recent completed sessions
        recent = await db.get_recent_completed_sessions(n=limit)

        sessions = []
        for session_data in recent:
            sessions.append(
                {
                    "id": session_data.get("id"),
                    "phase": session_data.get("phase"),
                    "outcome": session_data.get("outcome"),
                    "strategy_name": session_data.get("strategy_name"),
                    "created_at": session_data.get("created_at"),
                    "completed_at": session_data.get("completed_at"),
                }
            )

        return {
            "sessions": sessions,
            "total": len(sessions),
        }
