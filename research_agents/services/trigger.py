"""
Trigger service for research agents.

This service runs on an interval and checks if a new agent research cycle
should be started. For Phase 0, this is a simple check for active sessions.

Future phases will add:
- Quality gate checks
- Budget verification
- Time-of-day constraints
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from research_agents.services.invoker import InvocationResult

logger = structlog.get_logger(__name__)


@dataclass
class TriggerConfig:
    """Configuration for the trigger service.

    Attributes:
        interval_seconds: How often to check for triggering (default: 5 minutes)
        enabled: Whether the trigger service is enabled
    """

    interval_seconds: int = 300  # 5 minutes
    enabled: bool = True

    @classmethod
    def from_env(cls) -> TriggerConfig:
        """Load configuration from environment variables.

        Environment variables:
            AGENT_TRIGGER_INTERVAL_SECONDS: Interval between checks (default: 300)
            AGENT_ENABLED: Whether agent is enabled (default: true)

        Returns:
            TriggerConfig instance with values from environment.
        """
        interval = int(os.getenv("AGENT_TRIGGER_INTERVAL_SECONDS", "300"))
        enabled = os.getenv("AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
        return cls(interval_seconds=interval, enabled=enabled)


class AgentInvoker(Protocol):
    """Protocol for agent invocation.

    This allows different implementations:
    - Phase 0: subprocess call to Claude CLI
    - Future: Direct API calls to Anthropic
    """

    async def invoke(
        self, prompt: str, system_prompt: str | None = None
    ) -> InvocationResult:
        """Invoke the agent with the given prompt.

        Args:
            prompt: The user prompt to send to the agent.
            system_prompt: Optional system prompt.

        Returns:
            InvocationResult with success status, output, and any errors.
        """
        ...


class AgentDatabase(Protocol):
    """Protocol for agent database operations.

    This matches the interface from research_agents.database.queries.AgentDatabase.
    """

    async def get_active_session(self) -> Any:
        """Get the currently active session, if any."""
        ...


class TriggerService:
    """Service that triggers agent research cycles on an interval.

    The service runs a loop that:
    1. Checks if the service is enabled
    2. Checks if there's an active session
    3. If no active session, invokes the agent to start a new cycle

    Usage:
        config = TriggerConfig.from_env()
        service = TriggerService(config=config, db=db, invoker=invoker)
        await service.start()  # Runs until stop() is called
    """

    def __init__(
        self,
        config: TriggerConfig,
        db: AgentDatabase,
        invoker: AgentInvoker,
    ):
        """Initialize the trigger service.

        Args:
            config: Service configuration.
            db: Database interface for checking sessions.
            invoker: Agent invoker for starting new cycles.
        """
        self.config = config
        self.db = db
        self.invoker = invoker
        self._running = False
        self._stop_event = asyncio.Event()

    async def check_and_trigger(self) -> dict:
        """Check conditions and potentially trigger an agent cycle.

        Returns:
            Dict with:
                - triggered: Whether the agent was invoked
                - reason: Why it was or wasn't triggered
                - session_id: New session ID if triggered
        """
        # Check if service is enabled
        if not self.config.enabled:
            logger.debug("Trigger service disabled, skipping check")
            return {"triggered": False, "reason": "disabled"}

        # Check for active session
        active_session = await self.db.get_active_session()
        if active_session is not None:
            logger.info(
                "Active session exists, skipping trigger",
                session_id=active_session.id,
                phase=active_session.phase,
            )
            return {
                "triggered": False,
                "reason": "active_session_exists",
                "active_session_id": active_session.id,
            }

        # No active session - invoke the agent
        logger.info("No active session, triggering new research cycle")

        try:
            from research_agents.prompts.phase0_test import get_phase0_prompt

            prompts = get_phase0_prompt()
            result = await self.invoker.invoke(
                prompt=prompts["user"],
                system_prompt=prompts["system"],
            )

            # Extract session_id from output if available
            session_id = None
            if result.output and isinstance(result.output, dict):
                session_id = result.output.get("session_id")

            logger.info(
                "Agent invocation completed",
                success=result.success,
                session_id=session_id,
            )

            return {
                "triggered": True,
                "reason": "no_active_session",
                "session_id": session_id,
                "invocation_result": {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "error": result.error,
                },
            }

        except Exception as e:
            logger.error("Failed to invoke agent", error=str(e))
            return {
                "triggered": False,
                "reason": "invocation_failed",
                "error": str(e),
            }

    async def start(self) -> None:
        """Start the trigger service loop.

        Runs until stop() is called. Checks for trigger conditions
        at the configured interval.
        """
        self._running = True
        self._stop_event.clear()
        logger.info(
            "Starting trigger service",
            interval_seconds=self.config.interval_seconds,
            enabled=self.config.enabled,
        )

        while self._running:
            try:
                await self.check_and_trigger()
            except Exception as e:
                logger.error("Error in trigger check", error=str(e))

            # Wait for interval or stop signal
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.interval_seconds,
                )
                # Stop event was set
                break
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                pass

        logger.info("Trigger service stopped")

    def stop(self) -> None:
        """Signal the service to stop."""
        logger.info("Stopping trigger service")
        self._running = False
        self._stop_event.set()
