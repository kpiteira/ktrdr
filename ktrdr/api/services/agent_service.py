"""Agent API service - operations-only, no sessions.

This service manages agent research cycles using the worker pattern.
All state is tracked through OperationsService, not a separate database.

Environment Variables:
    USE_STUB_WORKERS: Set to "true" to use stub workers for all phases.
                      Useful for E2E testing without Claude API or real training.
"""

import asyncio
import os
from typing import Any

from ktrdr import get_logger
from ktrdr.agents.budget import get_budget_tracker
from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubDesignWorker,
)
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)
from ktrdr.monitoring.service_telemetry import trace_service_method

logger = get_logger(__name__)


def _use_stub_workers() -> bool:
    """Check if stub workers should be used instead of real ones."""
    return os.getenv("USE_STUB_WORKERS", "").lower() in ("true", "1", "yes")


class AgentService:
    """Service layer for agent API operations.

    Manages research cycles through OperationsService. Each cycle runs as an
    AGENT_RESEARCH operation with child operations for each phase.
    """

    def __init__(self, operations_service: OperationsService | None = None):
        """Initialize the agent service.

        Args:
            operations_service: Optional OperationsService instance (for testing).
        """
        self.ops = operations_service or get_operations_service()
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

    @trace_service_method("agent.trigger")
    async def trigger(self) -> dict[str, Any]:
        """Start a new research cycle.

        Returns immediately with operation_id. Cycle runs in background.

        Returns:
            Dict with triggered status and operation_id or rejection reason.
        """
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

        # Create operation
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),  # type: ignore[call-arg]
        )

        # Start worker in background
        worker = self._get_worker()
        task = asyncio.create_task(self._run_worker(op.operation_id, worker))
        await self.ops.start_operation(op.operation_id, task)

        logger.info(f"Research cycle triggered: {op.operation_id}")

        return {
            "triggered": True,
            "operation_id": op.operation_id,
            "message": "Research cycle started",
        }

    async def _run_worker(self, operation_id: str, worker: AgentResearchWorker) -> None:
        """Run worker and handle completion/failure.

        Args:
            operation_id: The operation ID to run.
            worker: The worker instance to run.
        """
        try:
            result = await worker.run(operation_id)
            await self.ops.complete_operation(operation_id, result)
            # Budget spend is recorded per-phase in the worker

        except asyncio.CancelledError:
            await self.ops.cancel_operation(operation_id, "Cancelled by user")
            raise
        except Exception as e:
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

        # Also check for PENDING (just created, not yet started)
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
            limit=1,
        )
        return ops[0] if ops else None

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

    Returns:
        AgentService singleton instance.
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
