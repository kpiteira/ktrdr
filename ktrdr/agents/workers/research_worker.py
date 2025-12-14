"""Orchestrator worker for agent research cycles.

This worker manages the state machine loop for research cycles, coordinating
child workers through the design → training → backtest → assessment phases.

Uses a polling loop pattern (per ARCHITECTURE.md) to monitor child operation
status rather than directly awaiting workers. This supports distributed workers.

Environment Variables:
    AGENT_POLL_INTERVAL: Seconds between status checks (default: 5 for stubs)
"""

import asyncio
import os
from typing import Any, Protocol

from ktrdr import get_logger
from ktrdr.agents.gates import check_backtest_gate, check_training_gate
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)

logger = get_logger(__name__)


class ChildWorker(Protocol):
    """Protocol for child workers."""

    async def run(self, operation_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Run the worker and return results."""
        ...


class WorkerError(Exception):
    """Exception raised when a child worker fails."""

    pass


class GateFailedError(Exception):
    """Exception raised when a quality gate check fails.

    Quality gates are deterministic checks between phases to filter
    poor strategies before expensive operations (like training or assessment).
    """

    pass


def _get_poll_interval() -> float:
    """Get the poll interval from environment.

    Returns:
        Poll interval in seconds. Default 5.0 for stub workers.
    """
    try:
        return float(os.getenv("AGENT_POLL_INTERVAL", "5"))
    except ValueError:
        return 5.0


class AgentResearchWorker:
    """Orchestrator for research cycles. Runs as AGENT_RESEARCH operation.

    This worker manages the full research cycle using a polling loop that
    monitors child operation status. The cycle runs:
    designing → training → backtesting → assessing → complete

    The polling loop allows the orchestrator to work with distributed workers
    that run as separate processes/containers.

    Attributes:
        PHASES: List of phase names in execution order.
        POLL_INTERVAL: Seconds between status checks (read from env).
    """

    PHASES = ["designing", "training", "backtesting", "assessing"]

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

        # Read poll interval from environment
        self.POLL_INTERVAL = _get_poll_interval()

        # Track current child for cancellation propagation
        self._current_child_op_id: str | None = None
        self._current_child_task: asyncio.Task | None = None

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Main orchestrator loop using polling pattern.

        Polls child operation status in a loop rather than directly awaiting
        workers. This supports distributed workers that run independently.

        Args:
            operation_id: The parent AGENT_RESEARCH operation ID.

        Returns:
            Result dict with success, strategy_name, and verdict.

        Raises:
            asyncio.CancelledError: If the operation is cancelled.
            WorkerError: If any child worker fails.
        """
        logger.info(f"Starting research cycle: {operation_id}")

        try:
            while True:
                # Get current parent state
                op = await self.ops.get_operation(operation_id)
                if op is None:
                    raise WorkerError(f"Parent operation not found: {operation_id}")

                phase = op.metadata.parameters.get("phase", "idle")

                # Get current child operation if any
                child_op_id = self._get_child_op_id(op, phase)
                child_op = None
                if child_op_id:
                    child_op = await self.ops.get_operation(child_op_id)

                # State machine logic
                if phase == "idle" or child_op is None:
                    # Start the first phase (designing)
                    await self._start_phase_worker(operation_id, "designing")

                elif child_op.status == OperationStatus.PENDING:
                    # Child created but not started yet, wait for it
                    pass

                elif child_op.status == OperationStatus.RUNNING:
                    # Child still running, update parent progress
                    await self._update_parent_progress(operation_id, phase, child_op)

                elif child_op.status == OperationStatus.COMPLETED:
                    # Child completed, check gate and advance
                    result = child_op.result_summary or {}

                    if phase == "assessing":
                        # All phases complete
                        parent = await self.ops.get_operation(operation_id)
                        strategy_name = parent.metadata.parameters.get(
                            "strategy_name", "unknown"
                        )
                        return {
                            "success": True,
                            "strategy_name": strategy_name,
                            "verdict": result.get("verdict", "unknown"),
                        }
                    else:
                        # Advance to next phase
                        await self._advance_to_next_phase(operation_id, phase, result)

                elif child_op.status == OperationStatus.FAILED:
                    raise WorkerError(
                        f"Child operation failed: {child_op.error_message}"
                    )

                elif child_op.status == OperationStatus.CANCELLED:
                    raise asyncio.CancelledError("Child operation was cancelled")

                # Poll interval
                await self._cancellable_sleep(self.POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info(f"Research cycle cancelled: {operation_id}")
            # Propagate cancellation to active child
            await self._cancel_current_child()
            raise
        except WorkerError:
            raise
        except Exception as e:
            logger.error(f"Research cycle failed: {operation_id}, error={e}")
            raise

    def _get_child_op_id(self, op: Any, phase: str) -> str | None:
        """Get child operation ID for current phase.

        Args:
            op: Parent operation.
            phase: Current phase name.

        Returns:
            Child operation ID or None.
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

    async def _start_phase_worker(self, operation_id: str, phase: str) -> None:
        """Start a worker for the given phase.

        Creates child operation, starts worker as asyncio task, and
        registers with operations service.

        Args:
            operation_id: Parent operation ID.
            phase: Phase to start (designing, training, etc).
        """
        # Update parent phase
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters["phase"] = phase
        logger.info(f"Phase started: {operation_id}, phase={phase}")

        # Create child operation
        child_name = self._phase_to_child_name(phase)
        child_op = await self.ops.create_operation(
            operation_type=self._get_child_op_type(child_name),
            metadata=OperationMetadata(),  # type: ignore[call-arg]
            parent_operation_id=operation_id,
        )

        # Track child in parent metadata
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters[f"{child_name}_op_id"] = child_op.operation_id

        # Get worker and args for this phase
        worker, args = await self._get_worker_and_args(operation_id, phase)

        # Create task wrapper that completes the child operation
        async def run_child():
            try:
                result = await worker.run(child_op.operation_id, *args)
                await self.ops.complete_operation(child_op.operation_id, result)
            except asyncio.CancelledError:
                # Don't mark as failed on cancellation
                raise
            except Exception as e:
                await self.ops.fail_operation(child_op.operation_id, str(e))
                raise

        # Start as asyncio task
        task = asyncio.create_task(run_child())
        self._current_child_op_id = child_op.operation_id
        self._current_child_task = task

        # Register task with operations service
        await self.ops.start_operation(child_op.operation_id, task)

    async def _get_worker_and_args(
        self, operation_id: str, phase: str
    ) -> tuple[ChildWorker, tuple]:
        """Get worker instance and arguments for a phase.

        Args:
            operation_id: Parent operation ID.
            phase: Phase name.

        Returns:
            Tuple of (worker, args tuple).
        """
        parent_op = await self.ops.get_operation(operation_id)
        params = parent_op.metadata.parameters if parent_op else {}

        if phase == "designing":
            return self.design_worker, ()

        elif phase == "training":
            strategy_path = params.get("strategy_path", "/app/strategies/unknown.yaml")
            return self.training_worker, (strategy_path,)

        elif phase == "backtesting":
            model_path = params.get("model_path", "/app/models/unknown/model.pt")
            return self.backtest_worker, (model_path,)

        elif phase == "assessing":
            training_result = params.get("training_result", {})
            backtest_result = params.get("backtest_result", {})
            return self.assessment_worker, (
                {"training": training_result, "backtest": backtest_result},
            )

        raise ValueError(f"Unknown phase: {phase}")

    async def _advance_to_next_phase(
        self, operation_id: str, current_phase: str, result: dict
    ) -> None:
        """Advance to the next phase after current completes.

        Stores result in parent metadata, checks quality gates, and starts
        next phase worker.

        Quality gates are checked:
        - After training: check_training_gate (before backtesting)
        - After backtesting: check_backtest_gate (before assessment)

        Args:
            operation_id: Parent operation ID.
            current_phase: Phase that just completed.
            result: Result from completed phase.

        Raises:
            GateFailedError: If a quality gate check fails.
        """
        parent_op = await self.ops.get_operation(operation_id)
        if not parent_op:
            return

        # Store result in parent metadata
        if current_phase == "designing":
            parent_op.metadata.parameters["strategy_name"] = result.get("strategy_name")
            parent_op.metadata.parameters["strategy_path"] = result.get("strategy_path")
            next_phase = "training"

        elif current_phase == "training":
            parent_op.metadata.parameters["training_result"] = result
            parent_op.metadata.parameters["model_path"] = result.get("model_path")

            # Check training gate before proceeding to backtest
            passed, reason = check_training_gate(result)
            if not passed:
                logger.warning(f"Training gate failed: {operation_id}, reason={reason}")
                raise GateFailedError(f"Training gate failed: {reason}")

            next_phase = "backtesting"

        elif current_phase == "backtesting":
            parent_op.metadata.parameters["backtest_result"] = result

            # Check backtest gate before proceeding to assessment
            passed, reason = check_backtest_gate(result)
            if not passed:
                logger.warning(f"Backtest gate failed: {operation_id}, reason={reason}")
                raise GateFailedError(f"Backtest gate failed: {reason}")

            next_phase = "assessing"

        else:
            return  # No next phase

        # Start next phase
        await self._start_phase_worker(operation_id, next_phase)

    async def _update_parent_progress(
        self, operation_id: str, phase: str, child_op: Any
    ) -> None:
        """Update parent operation progress based on child.

        Args:
            operation_id: Parent operation ID.
            phase: Current phase.
            child_op: Child operation info.
        """
        # For now, just log that child is still running
        # Future: aggregate progress from child to parent
        pass

    async def _cancel_current_child(self) -> None:
        """Cancel the currently running child operation.

        Called when parent is cancelled to propagate cancellation.
        """
        if self._current_child_op_id:
            try:
                await self.ops.cancel_operation(
                    self._current_child_op_id, "Parent cancelled"
                )
            except Exception as e:
                logger.warning(f"Failed to cancel child operation: {e}")

        if self._current_child_task and not self._current_child_task.done():
            self._current_child_task.cancel()
            try:
                await self._current_child_task
            except asyncio.CancelledError:
                pass

    def _phase_to_child_name(self, phase: str) -> str:
        """Convert phase name to child operation name.

        Args:
            phase: Phase name (designing, training, etc).

        Returns:
            Child name (design, training, etc).
        """
        return {
            "designing": "design",
            "training": "training",
            "backtesting": "backtest",
            "assessing": "assessment",
        }[phase]

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
        if seconds <= 0:
            # Always yield at least once to allow other tasks to run
            await asyncio.sleep(0)
            return

        interval = min(0.1, seconds)
        elapsed = 0.0
        while elapsed < seconds:
            await asyncio.sleep(interval)
            elapsed += interval
