"""Agent API service - operations-only, no sessions.

This service manages agent research cycles using the worker pattern.
All state is tracked through OperationsService, not a separate database.

Environment Variables:
    USE_STUB_WORKERS: Set to "true" to use stub workers for all phases.
                      Useful for E2E testing without Claude API or real training.
"""

import asyncio
import os
from typing import TYPE_CHECKING, Any

from ktrdr import get_logger
from ktrdr.agents.budget import get_budget_tracker
from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state
from ktrdr.agents.invoker import resolve_model
from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubDesignWorker,
)
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)
from ktrdr.monitoring.service_telemetry import trace_service_method

if TYPE_CHECKING:
    from ktrdr.checkpoint import CheckpointService

logger = get_logger(__name__)


def _use_stub_workers() -> bool:
    """Check if stub workers should be used instead of real ones."""
    return os.getenv("USE_STUB_WORKERS", "").lower() in ("true", "1", "yes")


class AgentService:
    """Service layer for agent API operations.

    Manages research cycles through OperationsService. Each cycle runs as an
    AGENT_RESEARCH operation with child operations for each phase.

    M7: Supports checkpoint save on failure/cancellation for resume capability.
    """

    def __init__(
        self,
        operations_service: OperationsService | None = None,
        checkpoint_service: "CheckpointService | None" = None,
    ):
        """Initialize the agent service.

        Args:
            operations_service: Optional OperationsService instance (for testing).
            checkpoint_service: Optional CheckpointService instance (for testing).
                               If not provided, lazily created when needed.
        """
        self.ops = operations_service or get_operations_service()
        self._checkpoint_service = checkpoint_service
        self._worker: AgentResearchWorker | None = None
        self._coordinator_task: asyncio.Task | None = None

    def _get_worker(self) -> AgentResearchWorker:
        """Get or create the research worker.

        Returns:
            The configured AgentResearchWorker with real or stub workers
            depending on USE_STUB_WORKERS environment variable.

        Note:
            Design and Assessment are workers (Claude API calls).
            Training and Backtest are services (lazy-loaded inside orchestrator).
        """
        if self._worker is None:
            checkpoint_svc = self._get_checkpoint_service()
            if _use_stub_workers():
                logger.info("Using stub workers (USE_STUB_WORKERS=true)")
                self._worker = AgentResearchWorker(
                    operations_service=self.ops,
                    design_worker=StubDesignWorker(),
                    assessment_worker=StubAssessmentWorker(),
                    # Services will be stubbed via mock injection in tests
                    training_service=None,
                    backtest_service=None,
                    checkpoint_service=checkpoint_svc,
                )
            else:
                self._worker = AgentResearchWorker(
                    operations_service=self.ops,
                    design_worker=AgentDesignWorker(self.ops),  # Real Claude
                    assessment_worker=AgentAssessmentWorker(self.ops),  # Real Claude
                    # Services lazy-loaded inside orchestrator
                    training_service=None,
                    backtest_service=None,
                    checkpoint_service=checkpoint_svc,
                )
        return self._worker

    def _get_checkpoint_service(self) -> "CheckpointService":
        """Get or create the checkpoint service.

        Returns:
            CheckpointService instance for checkpoint operations.
        """
        if self._checkpoint_service is None:
            from ktrdr.api.database import get_session_factory
            from ktrdr.checkpoint import CheckpointService

            self._checkpoint_service = CheckpointService(
                session_factory=get_session_factory(),
            )
        return self._checkpoint_service

    async def _save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
    ) -> None:
        """Save checkpoint for agent operation.

        Builds checkpoint state from the operation metadata and saves it.

        Args:
            operation_id: The operation ID to checkpoint.
            checkpoint_type: Type of checkpoint (failure, cancellation, etc.).
        """
        # Skip if checkpoint service not available (e.g., in unit tests)
        if self._checkpoint_service is None:
            logger.debug(
                f"Checkpoint service not available, skipping checkpoint save: {operation_id}"
            )
            return

        try:
            # Get the operation to build checkpoint state
            op = await self.ops.get_operation(operation_id)
            if op is None:
                logger.warning(
                    f"Cannot save checkpoint - operation not found: {operation_id}"
                )
                return

            # Build checkpoint state using the builder function
            checkpoint_state = build_agent_checkpoint_state(op)

            # Save checkpoint (no artifacts for agent operations)
            await self._checkpoint_service.save_checkpoint(
                operation_id=operation_id,
                checkpoint_type=checkpoint_type,
                state=checkpoint_state.to_dict(),
                artifacts=None,
            )

            logger.info(
                f"Agent checkpoint saved: {operation_id} "
                f"(type={checkpoint_type}, phase={checkpoint_state.phase})"
            )

        except Exception as e:
            # Don't fail the operation if checkpoint save fails
            logger.warning(f"Failed to save agent checkpoint: {e}")

    @trace_service_method("agent.trigger")
    async def trigger(
        self,
        model: str | None = None,
        brief: str | None = None,
        strategy: str | None = None,
        bypass_gates: bool = False,
    ) -> dict[str, Any]:
        """Start a new research cycle.

        Args:
            model: Model to use ('opus', 'sonnet', 'haiku' or full ID).
                   If None, uses AGENT_MODEL env var or default (opus).
            brief: Natural language guidance for the strategy designer.
                   Injected into the agent's prompt to guide design decisions.
            strategy: Name of an existing v3 strategy to train directly.
                      Skips the design phase. Mutually exclusive with brief.
            bypass_gates: If True, skip quality gates between phases (for testing).

        Returns:
            Dict with triggered status, operation_id, model, or rejection reason.

        Raises:
            ValueError: If model is invalid or strategy not found/invalid.
        """
        # Resolve model (validates and converts alias to full ID)
        resolved_model = resolve_model(model)

        # Validate strategy if provided (skip-design mode)
        strategy_path: str | None = None
        if strategy is not None:
            strategy_path = self._validate_and_resolve_strategy(strategy)

        # Check budget first
        budget = get_budget_tracker()
        can_spend, reason = budget.can_spend()
        if not can_spend:
            logger.warning(f"Budget exhausted: {reason}")
            return {
                "triggered": False,
                "reason": "budget_exhausted",
                "message": f"Daily budget exhausted: {reason}",
            }

        # Check capacity (multiple researches allowed up to limit)
        active_ops = await self._get_all_active_research_ops()
        limit = self._get_concurrency_limit()
        if len(active_ops) >= limit:
            return {
                "triggered": False,
                "reason": "at_capacity",
                "active_count": len(active_ops),
                "limit": limit,
                "message": f"At capacity ({len(active_ops)}/{limit} researches active)",
            }

        # Create operation with model, brief/strategy, and bypass_gates in metadata
        # Agent operations are backend-local (run in backend process, not workers)
        if strategy is not None:
            # Skip-design mode: start at "designing" with design_complete flag
            params: dict[str, Any] = {
                "phase": "designing",
                "design_complete": True,
                "model": resolved_model,
                "strategy_name": strategy,
                "strategy_path": strategy_path,
            }
        else:
            # Normal mode: start at "idle" for design phase
            params = {"phase": "idle", "model": resolved_model}
            if brief is not None:
                params["brief"] = brief
        if bypass_gates:
            params["bypass_gates"] = True
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters=params),
            is_backend_local=True,  # M7 Task 7.1: Mark as backend-local for checkpoint handling
        )

        # Start operation (transition to RUNNING)
        await self.ops.start_operation(op.operation_id)

        # Start coordinator if not running
        if self._coordinator_task is None or self._coordinator_task.done():
            self._start_coordinator()

        logger.info(
            f"Research cycle triggered: {op.operation_id}, model: {resolved_model}"
        )

        return {
            "triggered": True,
            "operation_id": op.operation_id,
            "model": resolved_model,
            "message": "Research cycle started",
        }

    def _start_coordinator(self) -> None:
        """Start the coordinator loop task if not already running.

        Creates a single coordinator task that discovers and processes all
        active research operations. Only one coordinator runs at a time.
        """
        worker = self._get_worker()
        self._coordinator_task = asyncio.create_task(self._run_coordinator(worker))
        logger.info("Coordinator task started")

    async def _run_coordinator(self, worker: AgentResearchWorker) -> None:
        """Run the coordinator loop.

        The coordinator discovers and processes all active researches.
        Individual operation completion/failure is handled inside the loop.

        Args:
            worker: The worker instance to run.
        """
        try:
            await worker.run()
            logger.info("Coordinator completed (no active researches)")
        except asyncio.CancelledError:
            logger.info("Coordinator cancelled")
            raise
        except Exception as e:
            logger.error(f"Coordinator error: {e}")
            raise

    @trace_service_method("agent.get_status")
    async def get_status(self) -> dict[str, Any]:
        """Get status of all active researches with worker/budget/capacity info.

        Returns a comprehensive status including:
        - List of all active researches with phases and durations
        - Worker utilization by type (busy/total)
        - Budget status (remaining/limit)
        - Capacity info (active count/limit)

        Returns:
            Dict with status, active_researches list, workers, budget, capacity.
        """
        from datetime import datetime, timezone

        active_ops = await self._get_all_active_research_ops()

        # Common fields for both idle and active states
        workers = self._get_worker_status()
        budget = self._get_budget_status()
        capacity = {
            "active": len(active_ops),
            "limit": self._get_concurrency_limit(),
        }

        if not active_ops:
            # Return idle status with last completed
            last = await self._get_last_research_op()
            return {
                "status": "idle",
                "active_researches": [],
                "last_cycle": self._format_last_cycle(last) if last else None,
                "workers": workers,
                "budget": budget,
                "capacity": capacity,
            }

        # Build active research list
        active_researches = []
        now = datetime.now(timezone.utc)
        for op in active_ops:
            phase = op.metadata.parameters.get("phase", "unknown")
            child_op_id = self._get_child_op_id_for_phase(op, phase)
            started_at = op.started_at or op.created_at

            duration_seconds = int((now - started_at).total_seconds())

            active_researches.append(
                {
                    "operation_id": op.operation_id,
                    "phase": phase,
                    "strategy_name": op.metadata.parameters.get("strategy_name"),
                    "duration_seconds": duration_seconds,
                    "child_operation_id": child_op_id,
                }
            )

        return {
            "status": "active",
            "active_researches": active_researches,
            "workers": workers,
            "budget": budget,
            "capacity": capacity,
        }

    def _get_worker_status(self) -> dict[str, dict[str, int]]:
        """Get worker utilization by type.

        Returns:
            Dict mapping worker type to busy/total counts.
        """
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerStatus, WorkerType

        registry = get_worker_registry()
        result = {}

        for worker_type in [WorkerType.TRAINING, WorkerType.BACKTESTING]:
            all_workers = registry.list_workers(worker_type=worker_type)
            busy_workers = [w for w in all_workers if w.status == WorkerStatus.BUSY]
            result[worker_type.value] = {
                "busy": len(busy_workers),
                "total": len(all_workers),
            }

        return result

    def _get_budget_status(self) -> dict[str, float]:
        """Get budget remaining and limit.

        Returns:
            Dict with remaining budget and daily limit.
        """
        budget = get_budget_tracker()
        return {
            "remaining": budget.get_remaining(),
            "daily_limit": budget.daily_limit,
        }

    def _format_last_cycle(self, op: OperationInfo) -> dict[str, Any]:
        """Format last completed/failed cycle info.

        Args:
            op: The last operation.

        Returns:
            Dict with operation_id, outcome, strategy_name, completed_at.
        """
        return {
            "operation_id": op.operation_id,
            "outcome": op.status.value,
            "strategy_name": (
                op.result_summary.get("strategy_name") if op.result_summary else None
            ),
            "completed_at": (op.completed_at.isoformat() if op.completed_at else None),
        }

    @trace_service_method("agent.cancel")
    async def cancel(self, operation_id: str) -> dict[str, Any]:
        """Cancel a specific research by operation_id.

        Args:
            operation_id: The operation ID to cancel.

        Returns:
            Dict with cancellation result. Includes:
            - success: True if cancelled, False otherwise
            - operation_id: The operation that was cancelled (on success)
            - child_cancelled: Child operation ID if any (on success)
            - reason: Error reason code (on failure)
            - message: Human-readable message
        """
        # Get the operation
        op = await self.ops.get_operation(operation_id)

        if op is None:
            return {
                "success": False,
                "reason": "not_found",
                "message": f"Operation not found: {operation_id}",
            }

        # Verify it's an agent research
        if op.operation_type != OperationType.AGENT_RESEARCH:
            return {
                "success": False,
                "reason": "not_research",
                "message": f"Operation is not a research: {operation_id}",
            }

        # Verify it's cancellable (RUNNING or PENDING)
        if op.status not in [OperationStatus.RUNNING, OperationStatus.PENDING]:
            return {
                "success": False,
                "reason": "not_cancellable",
                "message": f"Cannot cancel {op.status.value} operation",
            }

        # Get child operation ID for cancellation propagation
        phase = op.metadata.parameters.get("phase", "")
        child_op_id = self._get_child_op_id_for_phase(op, phase)

        # Cancel the parent operation
        await self.ops.cancel_operation(operation_id, "Cancelled by user")

        # Also cancel child operation directly for faster propagation
        # (worker will also detect parent cancellation, but this is more immediate)
        if child_op_id:
            try:
                await self.ops.cancel_operation(child_op_id, "Parent cancelled by user")
            except Exception as e:
                logger.warning(f"Failed to cancel child operation {child_op_id}: {e}")

        logger.info(f"Research cancelled: {operation_id}, child: {child_op_id}")

        return {
            "success": True,
            "operation_id": operation_id,
            "child_cancelled": child_op_id,
            "message": "Research cancelled",
        }

    @trace_service_method("agent.resume")
    async def resume(self, operation_id: str) -> dict[str, Any]:
        """Resume a cancelled or failed research cycle from checkpoint.

        Loads checkpoint state, verifies the operation is resumable, and
        restarts the worker from the checkpointed phase.

        Args:
            operation_id: The operation ID to resume.

        Returns:
            Dict with resume result including phase resumed from.
        """
        from ktrdr.checkpoint.schemas import AgentCheckpointState

        # 1. Check if operation exists
        op = await self.ops.get_operation(operation_id)
        if op is None:
            logger.warning(f"Cannot resume - operation not found: {operation_id}")
            return {
                "success": False,
                "reason": "not_found",
                "message": f"Operation not found: {operation_id}",
            }

        # 2. Check if operation is in a resumable state
        # Note: RESUMING is allowed because the operations endpoint calls
        # try_resume() before calling this method, which sets status to RESUMING
        if op.status not in [
            OperationStatus.CANCELLED,
            OperationStatus.FAILED,
            OperationStatus.RESUMING,
        ]:
            status_name = op.status.value.lower()
            logger.warning(
                f"Cannot resume - operation not resumable: {operation_id} "
                f"(status: {status_name})"
            )
            return {
                "success": False,
                "reason": "not_resumable",
                "message": f"Cannot resume operation that is {status_name}",
            }

        # 3. Check for active cycles (can't resume if one is already running)
        active = await self._get_active_research_op()
        if active:
            logger.warning(
                f"Cannot resume - active cycle exists: {active.operation_id}"
            )
            return {
                "success": False,
                "reason": "active_cycle_exists",
                "active_operation_id": active.operation_id,
                "message": f"Cannot resume while another cycle is active: {active.operation_id}",
            }

        # 4. Load checkpoint
        checkpoint_service = self._get_checkpoint_service()
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=False
        )

        if checkpoint is None:
            logger.warning(f"Cannot resume - no checkpoint: {operation_id}")
            return {
                "success": False,
                "reason": "no_checkpoint",
                "message": f"No checkpoint available for operation {operation_id}",
            }

        # 5. Deserialize checkpoint state
        checkpoint_state = AgentCheckpointState.from_dict(checkpoint.state)
        resumed_from_phase = checkpoint_state.phase

        logger.info(
            f"Resuming agent operation {operation_id} from phase: {resumed_from_phase}"
        )

        # 6. Update operation metadata with checkpoint state
        # Merge checkpoint state back into operation metadata
        updated_params = dict(op.metadata.parameters)
        updated_params["phase"] = checkpoint_state.phase
        if checkpoint_state.strategy_name:
            updated_params["strategy_name"] = checkpoint_state.strategy_name
        if checkpoint_state.strategy_path:
            updated_params["strategy_path"] = checkpoint_state.strategy_path
        if checkpoint_state.training_operation_id:
            updated_params["training_op_id"] = checkpoint_state.training_operation_id
        if checkpoint_state.backtest_operation_id:
            updated_params["backtest_op_id"] = checkpoint_state.backtest_operation_id
        if checkpoint_state.token_counts:
            updated_params["token_counts"] = checkpoint_state.token_counts
        if checkpoint_state.original_request:
            for key, value in checkpoint_state.original_request.items():
                if key not in updated_params:
                    updated_params[key] = value

        # Update operation metadata
        op.metadata.parameters = updated_params

        # 7. Start operation (transition to RUNNING)
        await self.ops.start_operation(operation_id)

        # Start coordinator if not running
        if self._coordinator_task is None or self._coordinator_task.done():
            self._start_coordinator()

        logger.info(
            f"Research cycle resumed: {operation_id}, phase: {resumed_from_phase}"
        )

        # 8. Build response with resume info
        result: dict[str, Any] = {
            "success": True,
            "operation_id": operation_id,
            "resumed_from_phase": resumed_from_phase,
            "message": f"Research cycle resumed from phase: {resumed_from_phase}",
        }

        # Include child operation info if available
        if checkpoint_state.training_operation_id:
            result["training_operation_id"] = checkpoint_state.training_operation_id
        if checkpoint_state.backtest_operation_id:
            result["backtest_operation_id"] = checkpoint_state.backtest_operation_id

        return result

    async def _get_active_research_op(self):
        """Get active AGENT_RESEARCH operation if any.

        Returns:
            The active operation or None.
        """
        # Check for RUNNING first
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            limit=1,
        )
        if ops:
            return ops[0]

        # Check for RESUMING (resume in progress, prevents concurrent resumes)
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RESUMING,
            limit=1,
        )
        if ops:
            return ops[0]

        # Also check for PENDING (just created, not yet started)
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
            limit=1,
        )
        return ops[0] if ops else None

    async def _get_all_active_research_ops(self) -> list[OperationInfo]:
        """Get all active AGENT_RESEARCH operations.

        Returns all operations with RUNNING, RESUMING, or PENDING status.
        Used by the multi-research coordinator to iterate over all active researches.

        Note: On startup, the in-memory cache may be empty, so we also query
        the database repository directly to find operations that need resuming.

        Returns:
            List of active operations (may be empty).
        """
        result: list[OperationInfo] = []
        active_statuses = [
            OperationStatus.RUNNING,
            OperationStatus.RESUMING,
            OperationStatus.PENDING,
        ]

        # First check in-memory cache via list_operations
        for status in active_statuses:
            ops, _, _ = await self.ops.list_operations(
                operation_type=OperationType.AGENT_RESEARCH,
                status=status,
            )
            result.extend(ops)

        # If cache is empty and repository is available, query database directly
        # This handles the startup case where cache hasn't been populated yet
        if not result and hasattr(self.ops, "_repository") and self.ops._repository:
            for status in active_statuses:
                db_ops = await self.ops._repository.list(status=status.value)
                # Filter to only AGENT_RESEARCH operations
                for op in db_ops:
                    if op.operation_type == OperationType.AGENT_RESEARCH:
                        result.append(op)

        return result

    def _validate_and_resolve_strategy(self, strategy_name: str) -> str:
        """Validate an existing strategy exists and is v3 format.

        Args:
            strategy_name: Name of the strategy (without .yaml extension).

        Returns:
            Resolved absolute path to the strategy file.

        Raises:
            ValueError: If strategy not found or not v3 format.
        """
        from ktrdr.api.services.training.context import (
            DEFAULT_STRATEGY_PATHS,
            _resolve_strategy_path,
        )
        from ktrdr.config.strategy_loader import strategy_loader
        from ktrdr.errors import ValidationError as KtrdrValidationError

        # Resolve strategy path
        try:
            strategy_path = _resolve_strategy_path(
                strategy_name, DEFAULT_STRATEGY_PATHS
            )
        except KtrdrValidationError as e:
            raise ValueError(f"Strategy not found: {strategy_name}. {e}") from e

        # Validate it's v3 format (required for training)
        try:
            strategy_loader.load_v3_strategy(strategy_path)
        except ValueError as e:
            raise ValueError(
                f"Strategy '{strategy_name}' is not v3 format. "
                f"Run 'ktrdr strategy migrate' to upgrade. Error: {e}"
            ) from e
        except FileNotFoundError as e:
            raise ValueError(f"Strategy not found: {strategy_name}") from e

        logger.info(
            f"Validated strategy for skip-design: {strategy_name} at {strategy_path}"
        )
        return str(strategy_path)

    def _get_concurrency_limit(self) -> int:
        """Calculate max concurrent researches from worker pool.

        Checks for manual override via AGENT_MAX_CONCURRENT_RESEARCHES env var first.
        Otherwise calculates: training_workers + backtest_workers + buffer.

        Returns:
            Maximum number of concurrent researches allowed (minimum 1).
        """
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerType

        # Check manual override
        override = os.getenv("AGENT_MAX_CONCURRENT_RESEARCHES", "0")
        if override != "0":
            try:
                return int(override)
            except ValueError:
                pass  # Fall through to calculation

        # Calculate from workers
        registry = get_worker_registry()
        training = len(registry.list_workers(worker_type=WorkerType.TRAINING))
        backtest = len(registry.list_workers(worker_type=WorkerType.BACKTESTING))
        buffer = int(os.getenv("AGENT_CONCURRENCY_BUFFER", "1"))

        # Minimum of 1 to allow at least one research
        return max(1, training + backtest + buffer)

    async def _get_last_research_op(self):
        """Get most recent completed/failed AGENT_RESEARCH operation.

        Returns:
            The last operation or None.
        """
        for status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
            ops, _, _ = await self.ops.list_operations(
                operation_type=OperationType.AGENT_RESEARCH,
                status=status,
                limit=1,
            )
            if ops:
                return ops[0]
        return None

    def _get_child_op_id_for_phase(self, op: Any, phase: str) -> str | None:
        """Get child operation ID for the given phase.

        Args:
            op: Parent operation with metadata.
            phase: Current phase name.

        Returns:
            Child operation ID or None if not found.
        """
        phase_to_key = {
            "designing": "design_op_id",
            "training": "training_op_id",
            "backtesting": "backtest_op_id",
            "assessing": "assessment_op_id",
        }
        key = phase_to_key.get(phase)
        if key:
            return op.metadata.parameters.get(key)
        return None

    async def resume_if_needed(self) -> None:
        """Start coordinator if active researches exist.

        Called on backend startup to resume processing of any researches
        that were in progress when the backend last shut down.

        Handles gracefully if database tables don't exist yet (fresh install
        before alembic migrations run).
        """
        try:
            active_ops = await self._get_all_active_research_ops()
            if active_ops and (
                self._coordinator_task is None or self._coordinator_task.done()
            ):
                logger.info(
                    f"Resuming coordinator for {len(active_ops)} active researches"
                )
                self._start_coordinator()
        except Exception as e:
            # Handle cases where database isn't ready:
            # - Tables don't exist yet (fresh install before migrations)
            # - Database not reachable (CI environment, no DB configured)
            error_str = str(e).lower()
            is_db_not_ready = (
                "does not exist" in error_str
                or "undefined" in error_str
                or "connect call failed" in error_str
                or "connection refused" in error_str
            )
            if is_db_not_ready:
                logger.warning(
                    "Database not ready for coordinator resume, skipping. "
                    "This is expected on first startup or in test environments."
                )
            else:
                # Re-raise unexpected errors
                raise


# Singleton
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get the agent service singleton.

    In production, initializes checkpoint service for checkpoint/resume support.

    Returns:
        AgentService singleton instance.
    """
    global _agent_service
    if _agent_service is None:
        # Import here to avoid circular imports at module load time
        from ktrdr.api.database import get_session_factory
        from ktrdr.checkpoint import CheckpointService

        checkpoint_service = CheckpointService(session_factory=get_session_factory())
        _agent_service = AgentService(checkpoint_service=checkpoint_service)
    return _agent_service
