"""Orchestrator worker for agent research cycles.

This worker manages the state machine loop for research cycles, coordinating
child workers through the design → training → backtest → assessment phases.
"""

import asyncio
from typing import Any, Protocol

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationMetadata, OperationType

logger = get_logger(__name__)


class ChildWorker(Protocol):
    """Protocol for child workers."""

    async def run(self, operation_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Run the worker and return results."""
        ...


class AgentResearchWorker:
    """Orchestrator for research cycles. Runs as AGENT_RESEARCH operation.

    This worker manages the full research cycle, creating child operations
    for each phase and tracking their completion. The cycle runs:
    designing → training → backtesting → assessing → complete

    Attributes:
        PHASES: List of phase names in execution order.
        POLL_INTERVAL: Seconds between status checks (not used in current impl).
    """

    PHASES = ["designing", "training", "backtesting", "assessing"]
    POLL_INTERVAL = 5.0  # seconds between status checks

    def __init__(
        self,
        operations_service: Any,  # OperationsService, but we use Any to avoid circular imports
        design_worker: ChildWorker,
        training_worker: ChildWorker,
        backtest_worker: ChildWorker,
        assessment_worker: ChildWorker,
    ):
        """Initialize the orchestrator.

        Args:
            operations_service: Service for tracking operations.
            design_worker: Worker for strategy design phase.
            training_worker: Worker for model training phase.
            backtest_worker: Worker for backtest execution phase.
            assessment_worker: Worker for result assessment phase.
        """
        self.ops = operations_service
        self.design_worker = design_worker
        self.training_worker = training_worker
        self.backtest_worker = backtest_worker
        self.assessment_worker = assessment_worker

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Main orchestrator loop.

        Runs through all phases sequentially, creating child operations
        for each and tracking their results.

        Args:
            operation_id: The parent AGENT_RESEARCH operation ID.

        Returns:
            Result dict with success, strategy_name, and verdict.

        Raises:
            asyncio.CancelledError: If the operation is cancelled.
            Exception: If any child worker fails.
        """
        logger.info(f"Starting research cycle: {operation_id}")

        try:
            # Phase 1: Design
            await self._update_phase(operation_id, "designing")
            design_result = await self._run_child(
                operation_id, "design", self.design_worker.run, operation_id
            )

            # Phase 2: Training
            await self._update_phase(operation_id, "training")
            training_result = await self._run_child(
                operation_id,
                "training",
                self.training_worker.run,
                operation_id,
                design_result["strategy_path"],
            )

            # Phase 3: Backtest
            await self._update_phase(operation_id, "backtesting")
            backtest_result = await self._run_child(
                operation_id,
                "backtest",
                self.backtest_worker.run,
                operation_id,
                training_result["model_path"],
            )

            # Phase 4: Assessment
            await self._update_phase(operation_id, "assessing")
            assessment_result = await self._run_child(
                operation_id,
                "assessment",
                self.assessment_worker.run,
                operation_id,
                {
                    "training": training_result,
                    "backtest": backtest_result,
                },
            )

            # Complete
            return {
                "success": True,
                "strategy_name": design_result["strategy_name"],
                "verdict": assessment_result["verdict"],
            }

        except asyncio.CancelledError:
            logger.info(f"Research cycle cancelled: {operation_id}")
            raise
        except Exception as e:
            logger.error(f"Research cycle failed: {operation_id}, error={e}")
            raise

    async def _update_phase(self, operation_id: str, phase: str) -> None:
        """Update operation metadata with current phase.

        Args:
            operation_id: The operation ID to update.
            phase: The new phase name.
        """
        operation = await self.ops.get_operation(operation_id)
        if operation:
            operation.metadata.parameters["phase"] = phase
        logger.info(f"Phase started: {operation_id}, phase={phase}")

    async def _run_child(
        self,
        parent_op_id: str,
        child_name: str,
        worker_func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a child worker and track its operation.

        Creates a child operation, runs the worker, and marks the child
        complete or failed based on the result.

        Args:
            parent_op_id: The parent operation ID.
            child_name: Name of the child phase (design, training, etc).
            worker_func: The worker function to run.
            *args: Arguments to pass to the worker.
            **kwargs: Keyword arguments to pass to the worker.

        Returns:
            Result dict from the worker.

        Raises:
            Exception: If the worker fails.
        """
        # Create child operation
        child_op = await self.ops.create_operation(
            operation_type=self._get_child_op_type(child_name),
            metadata=OperationMetadata(),  # type: ignore[call-arg]
            parent_operation_id=parent_op_id,
        )

        # Track child in parent metadata
        parent_op = await self.ops.get_operation(parent_op_id)
        if parent_op:
            parent_op.metadata.parameters[f"{child_name}_op_id"] = child_op.operation_id

        try:
            # Run child worker
            result = await worker_func(*args, **kwargs)

            # Mark child complete
            await self.ops.complete_operation(child_op.operation_id, result)
            return result

        except Exception as e:
            await self.ops.fail_operation(child_op.operation_id, str(e))
            raise

    def _get_child_op_type(self, child_name: str) -> OperationType:
        """Get operation type for child.

        Args:
            child_name: Name of the child phase.

        Returns:
            The appropriate OperationType for this child.
        """
        return {
            "design": OperationType.AGENT_DESIGN,
            "training": OperationType.TRAINING,
            "backtest": OperationType.BACKTESTING,
            "assessment": OperationType.AGENT_ASSESSMENT,
        }[child_name]

    async def _cancellable_sleep(self, seconds: float) -> None:
        """Sleep in small intervals for cancellation responsiveness.

        Args:
            seconds: Total time to sleep.
        """
        intervals = int(seconds / 0.1)
        for _ in range(intervals):
            await asyncio.sleep(0.1)
