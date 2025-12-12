"""
Trigger service for research agents.

This service runs on an interval and checks if a new agent research cycle
should be started.

Phase 1 behavior:
- Creates session BEFORE invoking Claude
- Sets phase to DESIGNING immediately
- Uses strategy designer prompt with full context
- Marks session as failed on invocation errors

Task 1.10 updates:
- Supports AnthropicAgentInvoker with tools
- Accepts optional tool_executor for tool execution
- Background loop integration with API startup

Task 1.11 updates:
- Uses AGENT_TOOLS from ktrdr.agents.tools (centralized tool definitions)
- ToolExecutor from ktrdr.agents.executor used by startup.py
- Removed duplicate DEFAULT_AGENT_TOOLS definition

Future phases will add:
- Quality gate checks
- Budget verification
- Time-of-day constraints
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import structlog

# Import tool definitions from ktrdr.agents (Task 1.11)
# Note: ToolExecutor is imported where needed (e.g., ktrdr/api/startup.py)
from ktrdr.agents.tools import AGENT_TOOLS

if TYPE_CHECKING:
    from research_agents.database.schema import SessionOutcome, SessionPhase
    from research_agents.services.invoker import InvocationResult

logger = structlog.get_logger(__name__)

# Type alias for tool executor function result type
# Tool results can be dict or list (for tools returning collections)
ToolExecutorResult = dict[str, Any] | list[dict[str, Any]]

# Type alias for tool executor function
ToolExecutorFunc = Callable[[str, dict[str, Any]], Coroutine[Any, Any, ToolExecutorResult]]


# Backward compatibility alias for DEFAULT_AGENT_TOOLS
# New code should import directly from ktrdr.agents.tools
DEFAULT_AGENT_TOOLS = AGENT_TOOLS


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

    This protocol supports two invocation patterns:
    - Legacy: `invoke(prompt, system_prompt)` for Phase 0 ClaudeCodeInvoker
    - Modern: `run(prompt, tools, system_prompt, tool_executor)` for AnthropicAgentInvoker

    The TriggerService detects which pattern is supported and uses the appropriate one.
    """

    async def invoke(
        self, prompt: str, system_prompt: str | None = None
    ) -> InvocationResult:
        """Legacy: Invoke the agent with the given prompt (Phase 0).

        Args:
            prompt: The user prompt to send to the agent.
            system_prompt: Optional system prompt.

        Returns:
            InvocationResult with success status, output, and any errors.
        """
        ...


class ModernAgentInvoker(Protocol):
    """Protocol for modern agent invocation with tool support.

    This is the preferred pattern for AnthropicAgentInvoker.
    """

    async def run(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        tool_executor: ToolExecutorFunc | None = None,
    ) -> Any:
        """Invoke the agent with tools.

        Args:
            prompt: The user prompt to send to the agent.
            tools: List of tool definitions in Anthropic format.
            system_prompt: System prompt for the agent.
            tool_executor: Async function to execute tool calls.

        Returns:
            AgentResult with success status, output, token counts, and errors.
        """
        ...


class AgentDatabase(Protocol):
    """Protocol for agent database operations.

    This matches the interface from research_agents.database.queries.AgentDatabase.
    """

    async def get_active_session(self) -> Any:
        """Get the currently active session, if any."""
        ...

    async def create_session(self) -> Any:
        """Create a new session in IDLE phase."""
        ...

    async def update_session(
        self,
        session_id: int,
        phase: SessionPhase | None = None,
        strategy_name: str | None = None,
        operation_id: str | None = None,
    ) -> Any:
        """Update session state."""
        ...

    async def complete_session(
        self,
        session_id: int,
        outcome: SessionOutcome,
    ) -> Any:
        """Complete a session with the given outcome."""
        ...

    async def get_recent_completed_sessions(self, n: int = 5) -> list[dict[str, Any]]:
        """Get recent completed sessions for context."""
        ...

    async def get_sessions_by_phase(self, phases: list[str]) -> list[Any]:
        """Get sessions in specific phases (Task 1.13b)."""
        ...


class ContextProvider(Protocol):
    """Protocol for fetching context data for prompts.

    This allows different implementations:
    - MCP API client (production)
    - Mock provider (testing)
    """

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        """Get list of available indicators."""
        ...

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """Get list of available symbols with timeframes."""
        ...


class TriggerService:
    """Service that triggers agent research cycles on an interval.

    Phase 1 behavior:
    1. Checks if the service is enabled
    2. Checks if there's an active session
    3. If no active session:
       - Creates new session
       - Sets phase to DESIGNING
       - Fetches context (indicators, symbols, recent strategies)
       - Invokes agent with strategy designer prompt
       - Handles failures by marking session as failed

    Task 1.10 additions:
    - Supports AnthropicAgentInvoker with `run()` method
    - Passes tool definitions and tool_executor to invoker
    - Background loop integration for API startup

    Usage (modern - AnthropicAgentInvoker):
        config = TriggerConfig.from_env()
        service = TriggerService(
            config=config,
            db=db,
            invoker=AnthropicAgentInvoker(),
            context_provider=context_provider,
            tool_executor=my_tool_executor,
        )
        await service.start()  # Runs until stop() is called

    Usage (legacy - ClaudeCodeInvoker):
        service = TriggerService(
            config=config,
            db=db,
            invoker=ClaudeCodeInvoker(),
            context_provider=context_provider,
        )
    """

    def __init__(
        self,
        config: TriggerConfig,
        db: AgentDatabase,
        invoker: AgentInvoker | ModernAgentInvoker,
        context_provider: ContextProvider | None = None,
        tool_executor: ToolExecutorFunc | None = None,
        tools: list[dict[str, Any]] | None = None,
    ):
        """Initialize the trigger service.

        Args:
            config: Service configuration.
            db: Database interface for managing sessions.
            invoker: Agent invoker for starting new cycles.
                Can be either legacy AgentInvoker (with invoke()) or
                modern ModernAgentInvoker (with run()).
            context_provider: Optional context provider for indicators/symbols.
                If None, uses Phase 0 behavior (for backward compatibility).
            tool_executor: Optional async function to execute tool calls.
                Required for modern invokers (AnthropicAgentInvoker).
            tools: Optional list of tool definitions. If None, uses DEFAULT_AGENT_TOOLS.
        """
        self.config = config
        self.db = db
        self.invoker = invoker
        self.context_provider = context_provider
        self.tool_executor = tool_executor
        self.tools = tools or DEFAULT_AGENT_TOOLS
        self._running = False
        self._stop_event = asyncio.Event()

        # Detect if invoker is modern (has run() method)
        self._is_modern_invoker = hasattr(invoker, "run") and callable(invoker.run)

    async def check_and_trigger(self, operation_id: str | None = None) -> dict:
        """Check conditions and potentially trigger an agent cycle.

        Args:
            operation_id: Optional operation ID to link with session for tracking.
                         This enables operation recovery after backend restart.

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

        # No active session - start a new cycle
        logger.info("No active session, triggering new research cycle")

        # Use Phase 1 behavior if context_provider is available
        if self.context_provider is not None:
            return await self._trigger_design_phase(operation_id=operation_id)
        else:
            # Fallback to Phase 0 behavior for backward compatibility
            return await self._trigger_phase0()

    async def _trigger_design_phase(self, operation_id: str | None = None) -> dict:
        """Trigger a new design phase cycle (Phase 1 behavior).

        This method:
        1. Creates session BEFORE invoking Claude
        2. Sets phase to DESIGNING immediately (with operation_id for tracking)
        3. Fetches context data (indicators, symbols, recent strategies)
        4. Invokes agent with strategy designer prompt
        5. Handles failures by marking session as failed

        Args:
            operation_id: Optional operation ID to link with session for tracking.

        Returns:
            Dict with trigger result.
        """
        from research_agents.database.schema import SessionOutcome, SessionPhase
        from research_agents.prompts.strategy_designer import (
            TriggerReason,
            get_strategy_designer_prompt,
        )

        # Step 1: Create session BEFORE invoking Claude
        session = await self.db.create_session()
        session_id = session.id
        logger.info("Created new session", session_id=session_id)

        # Step 2: Set phase to DESIGNING immediately (with operation_id for restart recovery)
        await self.db.update_session(
            session_id=session_id,
            phase=SessionPhase.DESIGNING,
            operation_id=operation_id,  # Link operation for tracking
        )
        logger.info(
            "Set session phase to DESIGNING",
            session_id=session_id,
            operation_id=operation_id,
        )

        try:
            # Step 3: Fetch context data
            indicators = await self.context_provider.get_available_indicators()
            symbols = await self.context_provider.get_available_symbols()
            recent_sessions = await self.db.get_recent_completed_sessions(n=5)

            # Convert recent sessions to strategy format for prompt
            recent_strategies = self._convert_sessions_to_strategies(recent_sessions)

            logger.info(
                "Fetched context for prompt",
                indicator_count=len(indicators),
                symbol_count=len(symbols),
                recent_strategy_count=len(recent_strategies),
            )

            # Step 4: Build strategy designer prompt
            prompts = get_strategy_designer_prompt(
                trigger_reason=TriggerReason.START_NEW_CYCLE,
                session_id=session_id,
                phase="designing",
                available_indicators=indicators,
                available_symbols=symbols,
                recent_strategies=recent_strategies,
            )

            # Step 5: Invoke agent (use modern or legacy pattern)
            if self._is_modern_invoker:
                # Modern pattern: AnthropicAgentInvoker with tools
                result = await self.invoker.run(
                    prompt=prompts["user"],
                    tools=self.tools,
                    system_prompt=prompts["system"],
                    tool_executor=self.tool_executor,
                )
                logger.info(
                    "Agent invocation completed (modern)",
                    success=result.success,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    session_id=session_id,
                )

                # Step 6: Update session to DESIGNED if successful
                if result.success:
                    # Find the most recently saved strategy
                    from research_agents.services.strategy_service import (
                        get_recent_strategies,
                    )

                    recent = await get_recent_strategies(n=1)
                    strategy_name = recent[0]["name"] if recent else None

                    await self.db.update_session(
                        session_id=session_id,
                        phase=SessionPhase.DESIGNED,
                        strategy_name=strategy_name,
                    )
                    logger.info(
                        "Session updated to DESIGNED",
                        session_id=session_id,
                        strategy_name=strategy_name,
                    )

                return {
                    "triggered": True,
                    "reason": "no_active_session",
                    "session_id": session_id,
                    "invocation_result": {
                        "success": result.success,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "error": result.error,
                    },
                }
            else:
                # Legacy pattern: ClaudeCodeInvoker
                result = await self.invoker.invoke(
                    prompt=prompts["user"],
                    system_prompt=prompts["system"],
                )
                logger.info(
                    "Agent invocation completed (legacy)",
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
            # Step 6: Handle failure by marking session as failed
            logger.error(
                "Failed to invoke agent, marking session as failed",
                error=str(e),
                session_id=session_id,
            )
            await self.db.complete_session(
                session_id=session_id,
                outcome=SessionOutcome.FAILED_DESIGN,
            )
            return {
                "triggered": False,
                "reason": "invocation_failed",
                "session_id": session_id,
                "error": str(e),
            }

    async def _trigger_phase0(self) -> dict:
        """Trigger using Phase 0 behavior (backward compatibility).

        This is the original behavior where session is created by Claude.
        """
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
                "Agent invocation completed (phase0)",
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
            logger.error("Failed to invoke agent (phase0)", error=str(e))
            return {
                "triggered": False,
                "reason": "invocation_failed",
                "error": str(e),
            }

    def _convert_sessions_to_strategies(
        self, sessions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert recent session data to strategy format for prompt.

        Args:
            sessions: List of session dicts from database.

        Returns:
            List of strategy dicts for prompt context.
        """
        strategies = []
        for session in sessions:
            strategy_name = session.get("strategy_name")
            if strategy_name:
                strategies.append(
                    {
                        "name": strategy_name,
                        "type": None,  # Would need to load from YAML for full info
                        "outcome": session.get("outcome"),
                        "indicators": [],  # Would need to load from YAML for full info
                    }
                )
        return strategies

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
            # Wait for interval or stop signal FIRST (avoid trigger on every restart)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.interval_seconds,
                )
                # Stop event was set
                break
            except asyncio.TimeoutError:
                # Normal timeout, continue to trigger check
                pass

            try:
                await self.check_and_trigger()
            except Exception as e:
                logger.error("Error in trigger check", error=str(e))

        logger.info("Trigger service stopped")

    def stop(self) -> None:
        """Signal the service to stop."""
        logger.info("Stopping trigger service")
        self._running = False
        self._stop_event.set()

    async def recover_orphaned_sessions(self) -> int:
        """Recover orphaned sessions after backend restart (Task 1.13b).

        Sessions can be orphaned when:
        - Backend crashes or restarts during agent execution
        - Operation completes but session state wasn't updated

        This method finds sessions stuck in non-idle phases and resets them
        to allow new cycles to start.

        Returns:
            Number of sessions recovered.
        """
        from research_agents.database.schema import SessionOutcome

        # Non-terminal phases that indicate an interrupted operation
        # IDLE and COMPLETE are terminal states, all others are active
        active_phases = ["designing", "designed", "training", "backtesting", "assessing"]

        orphaned = await self.db.get_sessions_by_phase(active_phases)

        if not orphaned:
            logger.info("No orphaned sessions found")
            return 0

        logger.info(f"Found {len(orphaned)} orphaned sessions to recover")

        for session in orphaned:
            try:
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_INTERRUPTED,
                )
                logger.info(
                    "Recovered orphaned session",
                    session_id=session.id,
                    original_phase=session.phase.value if hasattr(session.phase, 'value') else session.phase,
                )
            except Exception as e:
                logger.error(
                    f"Failed to recover session {session.id}: {e}",
                    session_id=session.id,
                    error=str(e),
                )

        return len(orphaned)
