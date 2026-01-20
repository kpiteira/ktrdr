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
            if _use_stub_workers():
                logger.info("Using stub workers (USE_STUB_WORKERS=true)")
                self._worker = AgentResearchWorker(
                    operations_service=self.ops,
                    design_worker=StubDesignWorker(),
                    assessment_worker=StubAssessmentWorker(),
                    # Services will be stubbed via mock injection in tests
                    training_service=None,
                    backtest_service=None,
                )
            else:
                self._worker = AgentResearchWorker(
                    operations_service=self.ops,
                    design_worker=AgentDesignWorker(self.ops),  # Real Claude
                    assessment_worker=AgentAssessmentWorker(self.ops),  # Real Claude
                    # Services lazy-loaded inside orchestrator
                    training_service=None,
                    backtest_service=None,
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
        bypass_gates: bool = False,
    ) -> dict[str, Any]:
        """Start a new research cycle.

        Args:
            model: Model to use ('opus', 'sonnet', 'haiku' or full ID).
                   If None, uses AGENT_MODEL env var or default (opus).
            brief: Natural language guidance for the strategy designer.
                   Injected into the agent's prompt to guide design decisions.
            bypass_gates: If True, skip quality gates between phases (for testing).

        Returns:
            Dict with triggered status, operation_id, model, or rejection reason.

        Raises:
            ValueError: If model is invalid.
        """
        # Resolve model (validates and converts alias to full ID)
        resolved_model = resolve_model(model)

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

        # Check for active cycle
        active = await self._get_active_research_op()
        if active:
            return {
                "triggered": False,
                "reason": "active_cycle_exists",
                "operation_id": active.operation_id,
                "message": f"Active cycle exists: {active.operation_id}",
            }

        # Create operation with model, brief, and bypass_gates in metadata
        # Agent operations are backend-local (run in backend process, not workers)
        params: dict[str, Any] = {"phase": "idle", "model": resolved_model}
        if brief is not None:
            params["brief"] = brief
        if bypass_gates:
            params["bypass_gates"] = True
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters=params),
            is_backend_local=True,  # M7 Task 7.1: Mark as backend-local for checkpoint handling
        )

        # Start worker in background
        worker = self._get_worker()
        task = asyncio.create_task(self._run_worker(op.operation_id, worker))
        await self.ops.start_operation(op.operation_id, task)

        logger.info(
            f"Research cycle triggered: {op.operation_id}, model: {resolved_model}"
        )

        return {
            "triggered": True,
            "operation_id": op.operation_id,
            "model": resolved_model,
            "message": "Research cycle started",
        }

    async def _run_worker(self, operation_id: str, worker: AgentResearchWorker) -> None:
        """Run worker and handle completion/failure.

        M7: Saves checkpoint on failure/cancellation for resume capability.
        Deletes checkpoint on successful completion.

        Args:
            operation_id: The operation ID to run.
            worker: The worker instance to run.
        """
        try:
            result = await worker.run(operation_id)

            # M7: Delete checkpoint on successful completion (if checkpoint service available)
            if self._checkpoint_service is not None:
                await self._checkpoint_service.delete_checkpoint(operation_id)

            await self.ops.complete_operation(operation_id, result)
            # Budget spend is recorded per-phase in the worker

        except asyncio.CancelledError:
            # M7: Save checkpoint before marking cancelled
            await self._save_checkpoint(operation_id, "cancellation")
            await self.ops.cancel_operation(operation_id, "Cancelled by user")
            raise

        except Exception as e:
            # M7: Save checkpoint before marking failed
            await self._save_checkpoint(operation_id, "failure")
            await self.ops.fail_operation(operation_id, str(e))
            raise

    @trace_service_method("agent.get_status")
    async def get_status(self) -> dict[str, Any]:
        """Get current agent status.

        Returns:
            Dict with current status, phase, and last cycle info.
        """
        active = await self._get_active_research_op()

        if active:
            # Get child operation ID for current phase
            phase = active.metadata.parameters.get("phase", "unknown")
            child_op_id = self._get_child_op_id_for_phase(active, phase)

            return {
                "status": "active",
                "operation_id": active.operation_id,
                "phase": phase,
                "child_operation_id": child_op_id,
                "progress": active.progress.model_dump() if active.progress else None,
                "strategy_name": active.metadata.parameters.get("strategy_name"),
                "started_at": (
                    active.started_at.isoformat() if active.started_at else None
                ),
            }

        # Find last completed/failed
        last = await self._get_last_research_op()
        if last:
            return {
                "status": "idle",
                "last_cycle": {
                    "operation_id": last.operation_id,
                    "outcome": last.status.value,
                    "strategy_name": (
                        last.result_summary.get("strategy_name")
                        if last.result_summary
                        else None
                    ),
                    "completed_at": (
                        last.completed_at.isoformat() if last.completed_at else None
                    ),
                },
            }

        return {"status": "idle", "last_cycle": None}

    @trace_service_method("agent.cancel")
    async def cancel(self) -> dict[str, Any]:
        """Cancel the active research cycle.

        Returns:
            Dict with cancellation result including operation IDs cancelled.
        """
        active = await self._get_active_research_op()

        if not active:
            return {
                "success": False,
                "reason": "no_active_cycle",
                "message": "No active research cycle to cancel",
            }

        # Get current child operation ID based on phase
        child_op_id = self._get_child_op_id_for_phase(
            active, active.metadata.parameters.get("phase", "")
        )

        # Cancel the parent operation
        await self.ops.cancel_operation(active.operation_id, "Cancelled by user")

        logger.info(
            f"Research cycle cancelled: {active.operation_id}, child: {child_op_id}"
        )

        return {
            "success": True,
            "operation_id": active.operation_id,
            "child_cancelled": child_op_id,
            "message": "Research cycle cancelled",
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

        # 7. Start worker in background
        worker = self._get_worker()
        task = asyncio.create_task(self._run_worker(operation_id, worker))
        await self.ops.start_operation(operation_id, task)

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

        Returns:
            List of active operations (may be empty).
        """
        result: list[OperationInfo] = []
        for status in [
            OperationStatus.RUNNING,
            OperationStatus.RESUMING,
            OperationStatus.PENDING,
        ]:
            ops, _, _ = await self.ops.list_operations(
                operation_type=OperationType.AGENT_RESEARCH,
                status=status,
            )
            result.extend(ops)
        return result

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
