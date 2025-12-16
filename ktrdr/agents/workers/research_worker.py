"""Orchestrator worker for agent research cycles.

This worker manages the state machine loop for research cycles, coordinating
child workers through the design → training → backtest → assessment phases.

Uses a polling loop pattern (per ARCHITECTURE.md) to monitor child operation
status rather than directly awaiting workers. This supports distributed workers.

Training and Backtest phases call services directly rather than using adapters.
The orchestrator tracks real operation IDs and polls their status.

Environment Variables:
    AGENT_POLL_INTERVAL: Seconds between status checks (default: 5 for stubs)
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Protocol

import yaml

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

    Design and Assessment use child workers (Claude API calls).
    Training and Backtest call services directly and track real operation IDs.

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
        assessment_worker: ChildWorker,
        training_service: Any = None,  # TrainingService - lazy loaded if None
        backtest_service: Any = None,  # BacktestingService - lazy loaded if None
    ):
        """Initialize the orchestrator.

        Args:
            operations_service: Service for tracking operations.
            design_worker: Worker for strategy design phase.
            assessment_worker: Worker for result assessment phase.
            training_service: Optional TrainingService (lazy loaded if None).
            backtest_service: Optional BacktestingService (lazy loaded if None).
        """
        self.ops = operations_service
        self.design_worker = design_worker
        self.assessment_worker = assessment_worker
        self._training_service = training_service
        self._backtest_service = backtest_service

        # Read poll interval from environment
        self.POLL_INTERVAL = _get_poll_interval()

        # Track current child for cancellation propagation
        self._current_child_op_id: str | None = None
        self._current_child_task: asyncio.Task | None = None

    @property
    def training_service(self) -> Any:
        """Lazy load TrainingService."""
        if self._training_service is None:
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.api.services.training_service import TrainingService

            registry = get_worker_registry()
            self._training_service = TrainingService(worker_registry=registry)
        return self._training_service

    @property
    def backtest_service(self) -> Any:
        """Lazy load BacktestingService."""
        if self._backtest_service is None:
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.backtesting.backtesting_service import BacktestingService

            registry = get_worker_registry()
            self._backtest_service = BacktestingService(worker_registry=registry)
        return self._backtest_service

    def _load_strategy_config(self, strategy_path: str) -> dict[str, Any]:
        """Load strategy configuration from YAML file.

        Args:
            strategy_path: Path to the strategy YAML file.

        Returns:
            Strategy configuration dict.
        """
        try:
            with open(strategy_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load strategy config: {strategy_path}, error={e}")
            return {}

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Main orchestrator loop using polling pattern.

        Polls child operation status in a loop rather than directly awaiting
        workers. This supports distributed workers that run independently.

        For training and backtesting, the orchestrator calls services directly
        and tracks the real operation IDs in parent metadata.

        Args:
            operation_id: The parent AGENT_RESEARCH operation ID.

        Returns:
            Result dict with success, strategy_name, and verdict.

        Raises:
            asyncio.CancelledError: If the operation is cancelled.
            WorkerError: If any child worker fails.
            GateFailedError: If a quality gate check fails.
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
                if phase == "idle":
                    # Start the first phase (designing)
                    await self._start_design(operation_id)

                elif phase == "designing":
                    await self._handle_designing_phase(operation_id, child_op)

                elif phase == "training":
                    await self._handle_training_phase(operation_id, child_op)

                elif phase == "backtesting":
                    await self._handle_backtesting_phase(operation_id, child_op)

                elif phase == "assessing":
                    result = await self._handle_assessing_phase(operation_id, child_op)
                    if result is not None:
                        return result

                # Poll interval
                await self._cancellable_sleep(self.POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info(f"Research cycle cancelled: {operation_id}")
            # Propagate cancellation to active child
            await self._cancel_current_child()
            raise
        except (WorkerError, GateFailedError):
            raise
        except Exception as e:
            logger.error(f"Research cycle failed: {operation_id}, error={e}")
            raise

    async def _start_design(self, operation_id: str) -> None:
        """Start the design phase with design worker.

        Args:
            operation_id: Parent operation ID.
        """
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters["phase"] = "designing"
        logger.info(f"Phase started: {operation_id}, phase=designing")

        # Create child operation for design
        child_op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(),  # type: ignore[call-arg]
            parent_operation_id=operation_id,
        )

        # Track child in parent metadata
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters["design_op_id"] = child_op.operation_id

        # Create task wrapper that completes the child operation
        async def run_child():
            try:
                result = await self.design_worker.run(child_op.operation_id)
                await self.ops.complete_operation(child_op.operation_id, result)
            except asyncio.CancelledError:
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

    async def _handle_designing_phase(
        self, operation_id: str, child_op: Any
    ) -> None:
        """Handle designing phase state transitions.

        Args:
            operation_id: Parent operation ID.
            child_op: Design child operation.
        """
        if child_op is None:
            # No child yet, start design
            await self._start_design(operation_id)
            return

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return

        if child_op.status == OperationStatus.COMPLETED:
            # Design complete, store results and start training
            result = child_op.result_summary or {}
            parent_op = await self.ops.get_operation(operation_id)
            if parent_op:
                parent_op.metadata.parameters["strategy_name"] = result.get(
                    "strategy_name"
                )
                parent_op.metadata.parameters["strategy_path"] = result.get(
                    "strategy_path"
                )

            # Start training via service
            await self._start_training(operation_id)

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Design failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Design was cancelled")

    async def _start_training(self, operation_id: str) -> None:
        """Start training by calling TrainingService directly.

        Stores the real training operation ID in parent metadata.

        Date range is determined by (in priority order):
        1. Strategy config: training_data.date_range.start/end
        2. Environment variables: AGENT_TRAINING_START_DATE/END_DATE
        3. Defaults: None (training service will use its defaults)

        Args:
            operation_id: Parent operation ID.
        """
        parent_op = await self.ops.get_operation(operation_id)
        strategy_path = parent_op.metadata.parameters.get("strategy_path")

        # Load strategy config to get training params
        config = self._load_strategy_config(strategy_path)
        symbols = (
            config.get("training_data", {}).get("symbols", {}).get("list", ["EURUSD"])
        )
        timeframes = (
            config.get("training_data", {}).get("timeframes", {}).get("list", ["1h"])
        )
        strategy_name = config.get("name", "unknown")

        # Get date range from config or environment
        date_range = config.get("training_data", {}).get("date_range", {})
        start_date = date_range.get("start") or os.getenv("AGENT_TRAINING_START_DATE")
        end_date = date_range.get("end") or os.getenv("AGENT_TRAINING_END_DATE")

        # Call service directly - returns immediately with operation_id
        result = await self.training_service.start_training(
            symbols=symbols,
            timeframes=timeframes,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
        )

        training_op_id = result["operation_id"]

        # Store in parent metadata and update phase
        parent_op.metadata.parameters["phase"] = "training"
        parent_op.metadata.parameters["training_op_id"] = training_op_id
        self._current_child_op_id = training_op_id

        logger.info(f"Training started: {training_op_id}")

    async def _handle_training_phase(
        self, operation_id: str, child_op: Any
    ) -> None:
        """Handle training phase state transitions.

        Checks real training operation status directly.

        Args:
            operation_id: Parent operation ID.
            child_op: Training operation.
        """
        if child_op is None:
            # This shouldn't happen if phase is training
            logger.warning(f"Training phase but no training_op_id: {operation_id}")
            return

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return

        if child_op.status == OperationStatus.COMPLETED:
            result = child_op.result_summary or {}
            parent_op = await self.ops.get_operation(operation_id)
            if parent_op:
                parent_op.metadata.parameters["training_result"] = result
                parent_op.metadata.parameters["model_path"] = result.get("model_path")

            # Check training gate
            passed, reason = check_training_gate(result)
            if not passed:
                logger.warning(
                    f"Training gate failed: {operation_id}, reason={reason}"
                )
                raise GateFailedError(f"Training gate failed: {reason}")

            # Start backtest via service
            await self._start_backtest(operation_id)

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Training failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Training was cancelled")

    async def _start_backtest(self, operation_id: str) -> None:
        """Start backtest by calling BacktestingService directly.

        Stores the real backtest operation ID in parent metadata.

        Date range is determined by (in priority order):
        1. Strategy config: backtest.date_range.start/end
        2. Environment variables: AGENT_BACKTEST_START_DATE/END_DATE
        3. Defaults: 2024-01-01 to 2024-06-30 (6 months held-out)

        Args:
            operation_id: Parent operation ID.
        """
        from datetime import datetime

        parent_op = await self.ops.get_operation(operation_id)
        params = parent_op.metadata.parameters

        strategy_path = params.get("strategy_path")
        model_path = params.get("model_path")

        # Load strategy config for symbol/timeframe
        config = self._load_strategy_config(strategy_path)
        symbol = (
            config.get("training_data", {}).get("symbols", {}).get("list", ["EURUSD"])
        )[0]
        timeframe = (
            config.get("training_data", {}).get("timeframes", {}).get("list", ["1h"])
        )[0]

        # Get date range from config or environment or defaults
        backtest_config = config.get("backtest", {}).get("date_range", {})
        start_date_str = (
            backtest_config.get("start")
            or os.getenv("AGENT_BACKTEST_START_DATE")
            or "2024-01-01"
        )
        end_date_str = (
            backtest_config.get("end")
            or os.getenv("AGENT_BACKTEST_END_DATE")
            or "2024-06-30"
        )

        # Parse dates
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)

        # Call service directly - returns immediately with operation_id
        result = await self.backtest_service.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            strategy_config_path=strategy_path,
            model_path=model_path,
            start_date=start_date,
            end_date=end_date,
        )

        backtest_op_id = result["operation_id"]

        # Store in parent metadata and update phase
        params["phase"] = "backtesting"
        params["backtest_op_id"] = backtest_op_id
        self._current_child_op_id = backtest_op_id

        logger.info(f"Backtest started: {backtest_op_id}")

    async def _handle_backtesting_phase(
        self, operation_id: str, child_op: Any
    ) -> None:
        """Handle backtesting phase state transitions.

        Checks real backtest operation status directly.

        Args:
            operation_id: Parent operation ID.
            child_op: Backtest operation.
        """
        if child_op is None:
            logger.warning(f"Backtesting phase but no backtest_op_id: {operation_id}")
            return

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return

        if child_op.status == OperationStatus.COMPLETED:
            # Extract metrics from result_summary.metrics (nested structure)
            result_summary = child_op.result_summary or {}
            metrics = result_summary.get("metrics", {})

            backtest_result = {
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "win_rate": metrics.get("win_rate", 0),
                "max_drawdown": metrics.get("max_drawdown_pct", 1.0),
                "total_return": metrics.get("total_return", 0),
                "total_trades": metrics.get("total_trades", 0),
            }

            parent_op = await self.ops.get_operation(operation_id)
            if parent_op:
                parent_op.metadata.parameters["backtest_result"] = backtest_result

            # Check backtest gate
            passed, reason = check_backtest_gate(backtest_result)
            if not passed:
                logger.warning(
                    f"Backtest gate failed: {operation_id}, reason={reason}"
                )
                raise GateFailedError(f"Backtest gate failed: {reason}")

            # Start assessment with child worker
            await self._start_assessment(operation_id)

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Backtest failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Backtest was cancelled")

    async def _start_assessment(self, operation_id: str) -> None:
        """Start the assessment phase with assessment worker.

        Args:
            operation_id: Parent operation ID.
        """
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters["phase"] = "assessing"
        logger.info(f"Phase started: {operation_id}, phase=assessing")

        # Create child operation for assessment
        child_op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata=OperationMetadata(),  # type: ignore[call-arg]
            parent_operation_id=operation_id,
        )

        # Track child in parent metadata
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op:
            parent_op.metadata.parameters["assessment_op_id"] = child_op.operation_id

        # Get results for assessment
        params = parent_op.metadata.parameters if parent_op else {}
        training_result = params.get("training_result", {})
        backtest_result = params.get("backtest_result", {})
        results = {"training": training_result, "backtest": backtest_result}

        # Create task wrapper that completes the child operation
        async def run_child():
            try:
                result = await self.assessment_worker.run(child_op.operation_id, results)
                await self.ops.complete_operation(child_op.operation_id, result)
            except asyncio.CancelledError:
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

    async def _handle_assessing_phase(
        self, operation_id: str, child_op: Any
    ) -> dict[str, Any] | None:
        """Handle assessing phase state transitions.

        Args:
            operation_id: Parent operation ID.
            child_op: Assessment child operation.

        Returns:
            Final result dict if assessment complete, None otherwise.
        """
        if child_op is None:
            # No child yet, start assessment
            await self._start_assessment(operation_id)
            return None

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return None

        if child_op.status == OperationStatus.COMPLETED:
            # All phases complete
            result = child_op.result_summary or {}
            parent_op = await self.ops.get_operation(operation_id)
            strategy_name = parent_op.metadata.parameters.get("strategy_name", "unknown")

            # Store assessment verdict in parent metadata
            parent_op.metadata.parameters["assessment_verdict"] = result.get(
                "verdict", "unknown"
            )

            return {
                "success": True,
                "strategy_name": strategy_name,
                "verdict": result.get("verdict", "unknown"),
            }

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Assessment failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Assessment was cancelled")

        return None

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
