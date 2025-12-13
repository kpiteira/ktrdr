"""
Agent API service layer (stub pending MVP implementation).

NOTE: This service is temporarily stubbed out while the agent architecture
is being rebuilt with the worker pattern. See docs/agentic/mvp/ for details.

The new architecture replaces the session database with OperationsService
for state tracking, using the same patterns as training/backtesting.
"""

from typing import Any

from ktrdr import get_logger
from ktrdr.monitoring.service_telemetry import trace_service_method

logger = get_logger(__name__)

# Message shown when agent features are accessed
MVP_PENDING_MSG = (
    "Agent service pending MVP implementation. "
    "See docs/agentic/mvp/ for new architecture."
)


class AgentService:
    """Stub service for agent API operations.

    This service is temporarily stubbed while the agent architecture is being
    rebuilt. The new MVP implementation will use the worker pattern with
    OperationsService for state tracking.

    See docs/agentic/mvp/ARCHITECTURE.md for the new design.
    """

    def __init__(self, operations_service: Any = None):
        """Initialize the agent service.

        Args:
            operations_service: Optional OperationsService instance (for testing).
        """
        self._operations_service = operations_service
        logger.info(MVP_PENDING_MSG)

    @trace_service_method("agent.trigger")
    async def trigger(self, dry_run: bool = False) -> dict[str, Any]:
        """Trigger a research cycle (stub).

        Args:
            dry_run: If True, check conditions but don't actually trigger.

        Returns:
            Dict indicating the feature is pending implementation.
        """
        return {
            "success": False,
            "triggered": False,
            "reason": "pending_mvp_implementation",
            "message": MVP_PENDING_MSG,
        }

    @trace_service_method("agent.get_status")
    async def get_status(self, verbose: bool = False) -> dict[str, Any]:
        """Get current agent status (stub).

        Args:
            verbose: If True, include additional details.

        Returns:
            Dict indicating the feature is pending implementation.
        """
        return {
            "has_active_session": False,
            "agent_enabled": False,
            "session": None,
            "message": MVP_PENDING_MSG,
        }

    @trace_service_method("agent.list_sessions")
    async def list_sessions(self, limit: int = 10) -> dict[str, Any]:
        """List recent sessions (stub).

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            Dict indicating the feature is pending implementation.
        """
        return {
            "sessions": [],
            "total": 0,
            "message": MVP_PENDING_MSG,
        }

    @trace_service_method("agent.cancel_session")
    async def cancel_session(self, session_id: int) -> dict[str, Any]:
        """Cancel a session (stub).

        Args:
            session_id: The session ID to cancel.

        Returns:
            Dict indicating the feature is pending implementation.
        """
        return {
            "success": False,
            "session_id": session_id,
            "error": MVP_PENDING_MSG,
        }
