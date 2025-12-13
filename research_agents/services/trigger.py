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
        auto_start_new_sessions: Whether to automatically start new sessions from IDLE
                                 When False, only manual triggers via CLI will start sessions,
                                 but the background loop still runs to progress existing sessions.
    """

    interval_seconds: int = 300  # 5 minutes
    enabled: bool = True
    auto_start_new_sessions: bool = False  # Default to manual triggering

    @classmethod
    def from_env(cls) -> TriggerConfig:
        """Load configuration from environment variables.

        Environment variables:
            AGENT_TRIGGER_INTERVAL_SECONDS: Interval between checks (default: 300)
            AGENT_ENABLED: Whether agent is enabled (default: true)
            AGENT_AUTO_START_NEW_SESSIONS: Whether to auto-start sessions (default: false)

        Returns:
            TriggerConfig instance with values from environment.
        """
        interval = int(os.getenv("AGENT_TRIGGER_INTERVAL_SECONDS", "300"))
        enabled = os.getenv("AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
        auto_start = os.getenv("AGENT_AUTO_START_NEW_SESSIONS", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        return cls(
            interval_seconds=interval, enabled=enabled, auto_start_new_sessions=auto_start
        )


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
        operations_service: Any | None = None,
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
            operations_service: Optional OperationsService for checking operation status.
                Used for orphan detection during trigger checks.
        """
        self.config = config
        self.db = db
        self.invoker = invoker
        self.context_provider = context_provider
        self.tool_executor = tool_executor
        self.tools = tools or DEFAULT_AGENT_TOOLS
        self.operations_service = operations_service
        self._running = False
        self._stop_event = asyncio.Event()

        # Detect if invoker is modern (has run() method)
        self._is_modern_invoker = hasattr(invoker, "run") and callable(invoker.run)

    async def check_and_trigger(
        self, operation_id: str | None = None, force: bool = False
    ) -> dict:
        """Check conditions and potentially trigger an agent cycle.

        Args:
            operation_id: Optional operation ID to link with session for tracking.
                         This enables operation recovery after backend restart.
            force: If True, bypass auto_start_new_sessions check (for manual triggers).

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
            # Route to phase-specific handler (Phase 2: full state machine)
            return await self._handle_active_session(active_session)

        # No active session - check if auto-start is enabled (unless forced)
        if not force and not self.config.auto_start_new_sessions:
            logger.debug(
                "No active session and auto_start_new_sessions=False, skipping"
            )
            return {"triggered": False, "reason": "auto_start_disabled"}

        # Start a new cycle (auto-start enabled or forced)
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

    # =========================================================================
    # Phase 2: Full State Machine Handlers
    # =========================================================================

    async def _handle_active_session(self, session: Any) -> dict:
        """Route active session to appropriate phase handler.

        Args:
            session: Active session from database.

        Returns:
            Dict with handling result.
        """
        from research_agents.database.schema import SessionOutcome, SessionPhase

        phase = session.phase
        logger.info(
            "Handling active session",
            session_id=session.id,
            phase=phase.value if hasattr(phase, "value") else phase,
        )

        # Orphan detection: Check if session's operation still exists
        if session.operation_id and self.operations_service is not None:
            operation = await self.operations_service.get_operation(session.operation_id)
            if operation is None:
                # Orphan detected - operation disappeared
                logger.warning(
                    f"Orphan session {session.id} detected: "
                    f"operation {session.operation_id} not found. Marking as failed.",
                    session_id=session.id,
                    operation_id=session.operation_id,
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_ORPHAN,
                )
                return {
                    "triggered": False,
                    "reason": "orphan_recovered",
                    "session_id": session.id,
                    "operation_id": session.operation_id,
                }

        # Route based on phase
        if phase == SessionPhase.DESIGNED:
            return await self._handle_designed_session(session)
        elif phase == SessionPhase.TRAINING:
            return await self._handle_training_session(session)
        elif phase == SessionPhase.BACKTESTING:
            return await self._handle_backtesting_session(session)
        elif phase == SessionPhase.ASSESSING:
            return await self._handle_assessing_session(session)
        elif phase == SessionPhase.DESIGNING:
            # Design still in progress - no action needed
            return {
                "triggered": False,
                "reason": "design_in_progress",
                "session_id": session.id,
            }
        else:
            # Unknown/unexpected phase
            logger.warning(
                "Unknown session phase",
                session_id=session.id,
                phase=phase,
            )
            return {
                "triggered": False,
                "reason": "unknown_phase",
                "session_id": session.id,
            }

    async def _handle_designed_session(self, session: Any) -> dict:
        """Handle session in DESIGNED phase - start training.

        Loads the strategy config to extract symbols/timeframes for training.

        Args:
            session: Session in DESIGNED phase.

        Returns:
            Dict with handling result.
        """
        from pathlib import Path

        from ktrdr.agents.executor import start_training_via_api
        from ktrdr.config.strategy_loader import strategy_loader
        from research_agents.database.schema import SessionOutcome, SessionPhase

        logger.info(
            "Starting training for designed strategy",
            session_id=session.id,
            strategy_name=session.strategy_name,
        )

        try:
            # Load strategy config to get symbols/timeframes
            strategy_path = Path("strategies") / f"{session.strategy_name}.yaml"
            if not strategy_path.exists():
                logger.error(
                    "Strategy config file not found",
                    session_id=session.id,
                    strategy_name=session.strategy_name,
                    path=str(strategy_path),
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_TRAINING,
                )
                return {
                    "triggered": False,
                    "reason": "strategy_config_not_found",
                    "session_id": session.id,
                    "error": f"Strategy config not found: {strategy_path}",
                }

            # Load and parse the strategy config
            config, is_v2 = strategy_loader.load_strategy_config(str(strategy_path))

            # Extract symbols and timeframes from config
            symbols: list[str] = []
            timeframes: list[str] = []

            if is_v2:
                # V2 config has training_data.symbols and training_data.timeframes
                training_data = config.training_data
                symbol_config = training_data.symbols
                timeframe_config = training_data.timeframes

                # Handle symbol configuration based on mode
                if symbol_config.symbols:
                    symbols = symbol_config.symbols
                elif symbol_config.symbol:
                    symbols = [symbol_config.symbol]

                # Handle timeframe configuration based on mode
                if timeframe_config.timeframes:
                    timeframes = timeframe_config.timeframes
                elif timeframe_config.timeframe:
                    timeframes = [timeframe_config.timeframe]
            else:
                # Legacy v1 config - look in 'data' section
                config_dict = config.model_dump()
                data_section = config_dict.get("data", {})
                if data_section.get("symbol"):
                    symbols = [data_section["symbol"]]
                if data_section.get("timeframe"):
                    timeframes = [data_section["timeframe"]]

            if not symbols:
                logger.error(
                    "No symbols found in strategy config",
                    session_id=session.id,
                    strategy_name=session.strategy_name,
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_TRAINING,
                )
                return {
                    "triggered": False,
                    "reason": "no_symbols_in_config",
                    "session_id": session.id,
                    "error": "Strategy config has no symbols defined",
                }

            if not timeframes:
                logger.error(
                    "No timeframes found in strategy config",
                    session_id=session.id,
                    strategy_name=session.strategy_name,
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_TRAINING,
                )
                return {
                    "triggered": False,
                    "reason": "no_timeframes_in_config",
                    "session_id": session.id,
                    "error": "Strategy config has no timeframes defined",
                }

            logger.info(
                "Starting training with config",
                session_id=session.id,
                strategy_name=session.strategy_name,
                symbols=symbols,
                timeframes=timeframes,
            )

            # Start training via API with symbols and timeframes
            result = await start_training_via_api(
                strategy_name=session.strategy_name,
                symbols=symbols,
                timeframes=timeframes,
            )

            if not result.get("success"):
                # Training failed to start
                logger.error(
                    "Failed to start training",
                    session_id=session.id,
                    error=result.get("error"),
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_TRAINING,
                )
                return {
                    "triggered": False,
                    "reason": "training_start_failed",
                    "session_id": session.id,
                    "error": result.get("error"),
                }

            # Update session to TRAINING phase with operation ID
            operation_id = result.get("operation_id")
            await self.db.update_session(
                session_id=session.id,
                phase=SessionPhase.TRAINING,
                operation_id=operation_id,
            )

            logger.info(
                "Training started",
                session_id=session.id,
                operation_id=operation_id,
            )
            return {
                "triggered": False,
                "reason": "handled_designed_session",
                "session_id": session.id,
                "operation_id": operation_id,
            }

        except Exception as e:
            logger.error(
                "Exception starting training",
                session_id=session.id,
                error=str(e),
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_TRAINING,
            )
            return {
                "triggered": False,
                "reason": "training_start_exception",
                "session_id": session.id,
                "error": str(e),
            }

    async def _handle_training_session(self, session: Any) -> dict:
        """Handle session in TRAINING phase - check operation and apply gate.

        Args:
            session: Session in TRAINING phase.

        Returns:
            Dict with handling result.
        """
        from ktrdr.agents.executor import start_backtest_via_api
        from ktrdr.api.services.operations_service import get_operations_service
        from research_agents.database.schema import SessionOutcome, SessionPhase
        from research_agents.gates.training_gate import (
            TrainingGateConfig,
            evaluate_training_gate,
        )

        # Check if operation ID exists
        if not session.operation_id:
            logger.error(
                "Training session missing operation_id",
                session_id=session.id,
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_TRAINING,
            )
            return {
                "triggered": False,
                "reason": "missing_operation_id",
                "session_id": session.id,
            }

        # Check operation status
        ops_service = get_operations_service()
        operation = await ops_service.get_operation(session.operation_id)

        if operation is None:
            logger.error(
                "Training operation not found",
                session_id=session.id,
                operation_id=session.operation_id,
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_TRAINING,
            )
            return {
                "triggered": False,
                "reason": "operation_not_found",
                "session_id": session.id,
            }

        status = operation.status
        logger.info(
            "Checking training operation status",
            session_id=session.id,
            operation_id=session.operation_id,
            status=status,
        )

        # Handle based on status
        if status in ("PENDING", "RUNNING"):
            # Still in progress
            return {
                "triggered": False,
                "reason": "operation_in_progress",
                "session_id": session.id,
                "operation_id": session.operation_id,
            }

        if status == "FAILED":
            # Operation failed
            logger.error(
                "Training operation failed",
                session_id=session.id,
                operation_id=session.operation_id,
                error=getattr(operation, "error_message", None),
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_TRAINING,
            )
            return {
                "triggered": False,
                "reason": "training_operation_failed",
                "session_id": session.id,
            }

        if status == "COMPLETED":
            # Apply training gate
            results = operation.result_summary or {}
            gate_config = TrainingGateConfig.from_env()
            passed, reason = evaluate_training_gate(results, gate_config)

            logger.info(
                "Training gate evaluation",
                session_id=session.id,
                passed=passed,
                reason=reason,
                accuracy=results.get("accuracy"),
                final_loss=results.get("final_loss"),
            )

            if not passed:
                # Gate failed
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_TRAINING_GATE,
                )
                return {
                    "triggered": False,
                    "reason": "training_gate_failed",
                    "session_id": session.id,
                    "gate_reason": reason,
                }

            # Gate passed - start backtest
            model_path = results.get("model_path", "")
            try:
                backtest_result = await start_backtest_via_api(
                    strategy_name=session.strategy_name,
                    model_path=model_path,
                )

                if not backtest_result.get("success"):
                    logger.error(
                        "Failed to start backtest",
                        session_id=session.id,
                        error=backtest_result.get("error"),
                    )
                    await self.db.complete_session(
                        session_id=session.id,
                        outcome=SessionOutcome.FAILED_BACKTEST,
                    )
                    return {
                        "triggered": False,
                        "reason": "backtest_start_failed",
                        "session_id": session.id,
                    }

                # Update session to BACKTESTING
                backtest_op_id = backtest_result.get("operation_id")
                await self.db.update_session(
                    session_id=session.id,
                    phase=SessionPhase.BACKTESTING,
                    operation_id=backtest_op_id,
                )

                logger.info(
                    "Backtest started after training gate passed",
                    session_id=session.id,
                    operation_id=backtest_op_id,
                )
                return {
                    "triggered": False,
                    "reason": "training_gate_passed_backtest_started",
                    "session_id": session.id,
                    "operation_id": backtest_op_id,
                }

            except Exception as e:
                logger.error(
                    "Exception starting backtest",
                    session_id=session.id,
                    error=str(e),
                )
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_BACKTEST,
                )
                return {
                    "triggered": False,
                    "reason": "backtest_start_exception",
                    "session_id": session.id,
                    "error": str(e),
                }

        # Unknown status
        logger.warning(
            "Unknown operation status",
            session_id=session.id,
            status=status,
        )
        return {
            "triggered": False,
            "reason": "unknown_operation_status",
            "session_id": session.id,
        }

    async def _handle_backtesting_session(self, session: Any) -> dict:
        """Handle session in BACKTESTING phase - check operation and apply gate.

        Args:
            session: Session in BACKTESTING phase.

        Returns:
            Dict with handling result.
        """
        from ktrdr.api.services.operations_service import get_operations_service
        from research_agents.database.schema import SessionOutcome, SessionPhase
        from research_agents.gates.backtest_gate import (
            BacktestGateConfig,
            evaluate_backtest_gate,
        )

        # Check if operation ID exists
        if not session.operation_id:
            logger.error(
                "Backtest session missing operation_id",
                session_id=session.id,
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_BACKTEST,
            )
            return {
                "triggered": False,
                "reason": "missing_operation_id",
                "session_id": session.id,
            }

        # Check operation status
        ops_service = get_operations_service()
        operation = await ops_service.get_operation(session.operation_id)

        if operation is None:
            logger.error(
                "Backtest operation not found",
                session_id=session.id,
                operation_id=session.operation_id,
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_BACKTEST,
            )
            return {
                "triggered": False,
                "reason": "operation_not_found",
                "session_id": session.id,
            }

        status = operation.status
        logger.info(
            "Checking backtest operation status",
            session_id=session.id,
            operation_id=session.operation_id,
            status=status,
        )

        # Handle based on status
        if status in ("PENDING", "RUNNING"):
            return {
                "triggered": False,
                "reason": "operation_in_progress",
                "session_id": session.id,
                "operation_id": session.operation_id,
            }

        if status == "FAILED":
            logger.error(
                "Backtest operation failed",
                session_id=session.id,
                operation_id=session.operation_id,
                error=getattr(operation, "error_message", None),
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_BACKTEST,
            )
            return {
                "triggered": False,
                "reason": "backtest_operation_failed",
                "session_id": session.id,
            }

        if status == "COMPLETED":
            # Apply backtest gate
            results = operation.result_summary or {}
            gate_config = BacktestGateConfig.from_env()
            passed, reason = evaluate_backtest_gate(results, gate_config)

            logger.info(
                "Backtest gate evaluation",
                session_id=session.id,
                passed=passed,
                reason=reason,
                win_rate=results.get("win_rate"),
                max_drawdown=results.get("max_drawdown"),
                sharpe_ratio=results.get("sharpe_ratio"),
            )

            if not passed:
                await self.db.complete_session(
                    session_id=session.id,
                    outcome=SessionOutcome.FAILED_BACKTEST_GATE,
                )
                return {
                    "triggered": False,
                    "reason": "backtest_gate_failed",
                    "session_id": session.id,
                    "gate_reason": reason,
                }

            # Gate passed - invoke agent for assessment
            await self.db.update_session(
                session_id=session.id,
                phase=SessionPhase.ASSESSING,
            )

            # Trigger assessment invocation
            return await self._invoke_assessment(session, results)

        # Unknown status
        return {
            "triggered": False,
            "reason": "unknown_operation_status",
            "session_id": session.id,
        }

    async def _handle_assessing_session(self, session: Any) -> dict:
        """Handle session in ASSESSING phase - invoke assessment if needed.

        Args:
            session: Session in ASSESSING phase.

        Returns:
            Dict with handling result.
        """
        # Session is already in ASSESSING - invoke assessment
        # Get backtest results from last operation (would need to be stored)
        return await self._invoke_assessment(session, {})

    async def _invoke_assessment(self, session: Any, backtest_results: dict) -> dict:
        """Invoke agent to assess results and complete the cycle.

        Args:
            session: Current session.
            backtest_results: Results from backtesting.

        Returns:
            Dict with assessment result.
        """
        from research_agents.database.schema import SessionOutcome
        from research_agents.prompts.strategy_designer import (
            TriggerReason,
            get_strategy_designer_prompt,
        )

        logger.info(
            "Invoking agent for assessment",
            session_id=session.id,
            strategy_name=session.strategy_name,
        )

        try:
            # Get context for assessment prompt
            recent_sessions = await self.db.get_recent_completed_sessions(n=5)
            recent_strategies = self._convert_sessions_to_strategies(recent_sessions)

            # Build assessment prompt
            prompts = get_strategy_designer_prompt(
                trigger_reason=TriggerReason.BACKTEST_COMPLETED,
                session_id=session.id,
                phase="assessing",
                available_indicators=[],  # Not needed for assessment
                available_symbols=[],
                recent_strategies=recent_strategies,
                backtest_results=backtest_results,
            )

            # Invoke agent
            if self._is_modern_invoker:
                result = await self.invoker.run(
                    prompt=prompts["user"],
                    tools=self.tools,
                    system_prompt=prompts["system"],
                    tool_executor=self.tool_executor,
                )

                if result.success:
                    # Assessment complete - mark as success
                    await self.db.complete_session(
                        session_id=session.id,
                        outcome=SessionOutcome.SUCCESS,
                    )
                    logger.info(
                        "Assessment completed successfully",
                        session_id=session.id,
                    )
                    return {
                        "triggered": True,
                        "reason": "assessment_completed",
                        "session_id": session.id,
                        "outcome": "success",
                    }
                else:
                    # Assessment failed
                    await self.db.complete_session(
                        session_id=session.id,
                        outcome=SessionOutcome.FAILED_ASSESSMENT,
                    )
                    logger.error(
                        "Assessment invocation failed",
                        session_id=session.id,
                        error=result.error,
                    )
                    return {
                        "triggered": True,
                        "reason": "assessment_failed",
                        "session_id": session.id,
                        "error": result.error,
                    }
            else:
                # Legacy invoker
                result = await self.invoker.invoke(
                    prompt=prompts["user"],
                    system_prompt=prompts["system"],
                )
                if result.success:
                    await self.db.complete_session(
                        session_id=session.id,
                        outcome=SessionOutcome.SUCCESS,
                    )
                    return {
                        "triggered": True,
                        "reason": "assessment_completed",
                        "session_id": session.id,
                    }
                else:
                    await self.db.complete_session(
                        session_id=session.id,
                        outcome=SessionOutcome.FAILED_ASSESSMENT,
                    )
                    return {
                        "triggered": True,
                        "reason": "assessment_failed",
                        "session_id": session.id,
                    }

        except Exception as e:
            logger.error(
                "Exception during assessment",
                session_id=session.id,
                error=str(e),
            )
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.FAILED_ASSESSMENT,
            )
            return {
                "triggered": False,
                "reason": "assessment_exception",
                "session_id": session.id,
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
