"""
Agent API service layer with OperationsService integration (Task 1.13a).

This service wraps the TriggerService to provide API-compatible responses
for agent management endpoints. Agent operations follow the same patterns
as training/backtesting operations:
- Operations tracked via OperationsService
- Progress queryable via standard operations API
- Token counts visible in result_summary
- OpenTelemetry spans for observability
"""

import asyncio
from typing import Any, Optional

from ktrdr import get_logger
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationProgress,
    OperationType,
)
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.monitoring.service_telemetry import create_service_span, trace_service_method
from research_agents.database.queries import get_agent_db
from research_agents.services.trigger import TriggerConfig

logger = get_logger(__name__)


class AgentService:
    """Service layer for agent API operations.

    This class provides methods that map to the API endpoints:
    - trigger: Trigger a research cycle (returns operation_id)
    - get_status: Get current agent status
    - list_sessions: List recent sessions

    The service integrates with OperationsService for unified operation tracking,
    following the same patterns as training and backtesting operations.
    """

    def __init__(self, operations_service: Optional[Any] = None):
        """Initialize the agent service.

        Args:
            operations_service: Optional OperationsService instance (for testing).
                               If not provided, uses the global singleton.
        """
        self._config = TriggerConfig.from_env()
        self._db = None  # Lazy initialization
        self._operations_service = operations_service or get_operations_service()

    async def _get_db(self):
        """Get database instance (lazy initialization)."""
        if self._db is None:
            self._db = await get_agent_db()
        return self._db

    @trace_service_method("agent.trigger")
    async def trigger(self, dry_run: bool = False) -> dict[str, Any]:
        """Trigger a research cycle.

        Returns operation_id immediately. Agent execution runs in background.
        Progress can be queried via GET /operations/{operation_id}.

        Args:
            dry_run: If True, check conditions but don't actually trigger.

        Returns:
            Dict with trigger result including:
            - success: Whether the operation completed
            - triggered: Whether a new cycle was started
            - operation_id: Operation ID for tracking (if triggered)
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

        # Task 1.15: Create AGENT_SESSION parent operation for the full research cycle
        session_operation = await self._operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=OperationMetadata(
                symbol="N/A",  # Agent session doesn't operate on specific symbols
                timeframe="N/A",
                mode="research_cycle",
                start_date=None,
                end_date=None,
                parameters={
                    "trigger_reason": "start_new_cycle",
                    "agent_enabled": self._config.enabled,
                },
            ),
        )
        session_operation_id = session_operation.operation_id

        # Start the session operation (it stays RUNNING until session completes/cancels)
        # Create a placeholder task for cancellation tracking
        session_task = asyncio.create_task(
            self._session_lifecycle_tracker(session_operation_id),
            name=f"agent_session_{session_operation_id}",
        )
        await self._operations_service.start_operation(
            session_operation_id, session_task
        )

        # Task 1.15: Create AGENT_DESIGN child operation
        design_operation = await self._operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(
                symbol="N/A",  # Agent doesn't operate on specific symbols
                timeframe="N/A",
                mode="strategy_design",
                start_date=None,
                end_date=None,
                parameters={
                    "trigger_reason": "start_new_cycle",
                    "agent_enabled": self._config.enabled,
                    "session_operation_id": session_operation_id,
                },
            ),
            parent_operation_id=session_operation_id,  # Task 1.15: Link to parent
        )
        design_operation_id = design_operation.operation_id

        # Create background task for agent execution
        task = asyncio.create_task(
            self._run_agent_with_tracking(
                design_operation_id, db, session_operation_id
            ),
            name=f"agent_design_{design_operation_id}",
        )

        # Start design operation (registers task for cancellation)
        await self._operations_service.start_operation(design_operation_id, task)

        logger.info(
            f"Started agent session: {session_operation_id} "
            f"with design operation: {design_operation_id}"
        )

        # Return session operation_id (parent) for tracking
        return {
            "success": True,
            "triggered": True,
            "operation_id": session_operation_id,  # Return parent ID for tracking
            "design_operation_id": design_operation_id,  # Also include child ID
            "status": "started",
            "message": "Research cycle started - query progress via /operations/{operation_id}",
        }

    async def _session_lifecycle_tracker(self, session_operation_id: str) -> None:
        """Track session lifecycle - keeps session operation alive (Task 1.15).

        This async task runs in background, keeping the AGENT_SESSION operation
        in RUNNING state until the session completes or is cancelled.
        The actual work is done by child operations (design, train, backtest).

        Args:
            session_operation_id: The parent session operation ID
        """
        try:
            # Just wait indefinitely - cancellation happens via cancel_operation
            # which will cancel this task
            while True:
                await asyncio.sleep(60)  # Check every minute
                # Update progress from children if needed
                progress = await self._operations_service.get_aggregated_progress(
                    session_operation_id
                )
                await self._operations_service.update_progress(
                    session_operation_id, progress
                )
        except asyncio.CancelledError:
            logger.info(
                f"Session operation {session_operation_id} lifecycle tracker cancelled"
            )
            raise

    async def _run_agent_with_tracking(
        self,
        operation_id: str,
        db: Any,
        session_operation_id: Optional[str] = None,
    ) -> None:
        """Execute agent with progress tracking (Task 1.13b: cancellation & error handling).

        This method runs in background and tracks progress through OperationsService.
        On cancellation/timeout/error, updates both operation and session state.

        Args:
            operation_id: Design operation ID for progress tracking
            db: Agent database instance
            session_operation_id: Parent session operation ID (Task 1.15)
        """
        from research_agents.database.schema import SessionOutcome

        session_id: Optional[int] = None
        partial_tokens: dict[str, int] = {"input": 0, "output": 0}

        # Task 1.13b: Get cancellation token for checking during execution
        cancellation_token = self._operations_service.get_cancellation_token(
            operation_id
        )

        async def _check_cancellation() -> None:
            """Check if operation was cancelled and raise if so."""
            if cancellation_token and cancellation_token.is_cancelled():
                raise asyncio.CancelledError("Operation cancelled by user")

        async def _get_active_session_id() -> Optional[int]:
            """Get the active session ID (for error handling when session_id not yet captured)."""
            active = await db.get_active_session()
            return active.id if active else None

        async def _complete_session_with_outcome(outcome: SessionOutcome) -> None:
            """Complete the active session with the given outcome."""
            sid = session_id or await _get_active_session_id()
            if sid:
                try:
                    await db.complete_session(session_id=sid, outcome=outcome)
                    logger.info(
                        f"Session {sid} completed with outcome: {outcome.value}"
                    )
                except Exception as e:
                    logger.error(f"Failed to complete session {sid}: {e}")

        try:
            with create_service_span(
                "agent.design_strategy",
                operation_id=operation_id,
            ) as span:
                # Check cancellation before starting
                await _check_cancellation()

                # Progress: Preparing context (5%)
                await self._operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=5.0,
                        current_step="Preparing agent context",
                        steps_completed=1,
                        steps_total=5,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                # Import components (done here to avoid circular imports)
                from ktrdr.agents.executor import ToolExecutor
                from ktrdr.agents.invoker import (
                    AnthropicAgentInvoker,
                    AnthropicInvokerConfig,
                )
                from ktrdr.api.services.agent_context import AgentMCPContextProvider
                from research_agents.services.trigger import TriggerService

                # Check cancellation after imports
                await _check_cancellation()

                # Create invoker and tools
                invoker_config = AnthropicInvokerConfig.from_env()
                invoker = AnthropicAgentInvoker(config=invoker_config)
                context_provider = AgentMCPContextProvider()
                tool_executor = ToolExecutor()

                # Progress: Creating session (10%)
                await self._operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=10.0,
                        current_step="Creating agent session",
                        steps_completed=1,
                        steps_total=5,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                # Check cancellation before API call
                await _check_cancellation()

                service = TriggerService(
                    config=self._config,
                    db=db,
                    invoker=invoker,
                    context_provider=context_provider,
                    tool_executor=tool_executor,
                )

                # Progress: Calling Anthropic API (20%)
                await self._operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step="Calling Anthropic API",
                        steps_completed=2,
                        steps_total=5,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )
                span.set_attribute("agent.phase", "invoking_anthropic")

                # Execute trigger (this does the actual work)
                # Pass operation_id so it's saved to session for restart recovery
                result = await service.check_and_trigger(operation_id=operation_id)

                session_id = result.get("session_id")
                if session_id:
                    span.set_attribute("agent.session_id", session_id)

                # Capture token counts from invocation_result
                invocation = result.get("invocation_result", {})
                partial_tokens["input"] = invocation.get("input_tokens", 0)
                partial_tokens["output"] = invocation.get("output_tokens", 0)

                # Check cancellation after API call
                await _check_cancellation()

                # Progress: Processing response (80%)
                await self._operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=80.0,
                        current_step="Processing agent response",
                        steps_completed=4,
                        steps_total=5,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                # Get token counts from result (if available)
                input_tokens = partial_tokens["input"]
                output_tokens = partial_tokens["output"]
                total_tokens = input_tokens + output_tokens

                if total_tokens > 0:
                    span.set_attribute("agent.input_tokens", input_tokens)
                    span.set_attribute("agent.output_tokens", output_tokens)
                    span.set_attribute("agent.total_tokens", total_tokens)

                # Complete operation with result summary
                await self._operations_service.complete_operation(
                    operation_id,
                    result_summary={
                        "session_id": session_id,
                        "strategy_name": result.get("strategy_name"),
                        "triggered": result.get("triggered", False),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    },
                )

                logger.info(
                    f"Agent design operation {operation_id} completed: "
                    f"session_id={session_id}, tokens={total_tokens}"
                )

        except asyncio.CancelledError:
            # Task 1.13b: Handle cancellation - update session state
            logger.info(f"Agent operation {operation_id} cancelled")
            await _complete_session_with_outcome(SessionOutcome.CANCELLED)
            # OperationsService handles marking operation as CANCELLED
            raise

        except asyncio.TimeoutError:
            # Task 1.13b: Handle timeout - update session state
            logger.error(f"Agent operation {operation_id} timed out")
            await _complete_session_with_outcome(SessionOutcome.FAILED_TIMEOUT)
            # Fail operation with partial token info
            await self._operations_service.fail_operation(
                operation_id,
                f"Anthropic API timeout (tokens used: {partial_tokens['input']}in/{partial_tokens['output']}out)",
            )
            raise

        except Exception as e:
            # Task 1.13b: Handle other errors - update session state
            logger.error(f"Agent operation {operation_id} failed: {e}")
            await _complete_session_with_outcome(SessionOutcome.FAILED_DESIGN)
            # Fail operation with error message
            await self._operations_service.fail_operation(operation_id, str(e))
            raise

    @trace_service_method("agent.get_status")
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

    @trace_service_method("agent.list_sessions")
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
