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
import time
from typing import Any, Protocol

import yaml
from opentelemetry import trace

from ktrdr import get_logger
from ktrdr.agents.budget import get_budget_tracker
from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state
from ktrdr.agents.gates import check_backtest_gate, check_training_gate
from ktrdr.agents.metrics import (
    record_budget_spend,
    record_cycle_duration,
    record_cycle_outcome,
    record_gate_result,
    record_phase_duration,
    record_tokens,
)
from ktrdr.api.models.operations import (
    OperationProgress,
    OperationStatus,
    OperationType,
)

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Per-model pricing (per 1M tokens) - Updated Dec 2024
# Source: https://www.anthropic.com/pricing
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-5-20251101": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
}

# Default model for pricing when AGENT_MODEL is not set
DEFAULT_PRICING_MODEL = "claude-opus-4-5-20251101"


class ChildWorker(Protocol):
    """Protocol for child workers."""

    async def run(self, operation_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Run the worker and return results."""
        ...


class CycleError(Exception):
    """Base exception for research cycle errors.

    All errors during a research cycle inherit from this class,
    allowing consistent handling at the orchestrator level.
    """

    pass


class WorkerError(CycleError):
    """Exception raised when a child worker fails.

    Inherits from CycleError for consistent error handling.
    """

    pass


class GateError(CycleError):
    """Exception raised when a quality gate check fails.

    Quality gates are deterministic checks between phases to filter
    poor strategies before expensive operations (like training or assessment).

    Attributes:
        gate: Name of the gate that failed ("training" or "backtest")
        metrics: Dict containing the actual metric values that caused failure
    """

    def __init__(self, message: str, gate: str, metrics: dict[str, Any]):
        """Initialize GateError with context.

        Args:
            message: Human-readable error message with actual vs threshold values
            gate: Name of the gate ("training" or "backtest")
            metrics: Dict of actual metric values
        """
        super().__init__(message)
        self.gate = gate
        self.metrics = metrics


# Backwards compatibility alias
GateFailedError = GateError


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
        checkpoint_service: Any = None,  # CheckpointService - for save/delete on failure/success
    ):
        """Initialize the orchestrator.

        Args:
            operations_service: Service for tracking operations.
            design_worker: Worker for strategy design phase.
            assessment_worker: Worker for result assessment phase.
            training_service: Optional TrainingService (lazy loaded if None).
            backtest_service: Optional BacktestingService (lazy loaded if None).
            checkpoint_service: Optional CheckpointService for checkpoint operations.
        """
        self.ops = operations_service
        self.design_worker = design_worker
        self.assessment_worker = assessment_worker
        self._training_service = training_service
        self._backtest_service = backtest_service
        self._checkpoint_service = checkpoint_service

        # Read poll interval from environment
        self.POLL_INTERVAL = _get_poll_interval()

        # Track current service child operation (training/backtest) for cancellation
        self._current_service_child_op_id: str | None = None
        # Track child tasks per operation (for multi-research support)
        self._child_tasks: dict[str, asyncio.Task] = {}
        # Store design results per operation (for stub worker flow)
        self._design_results: dict[str, dict] = {}

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
            logger.warning(
                f"Failed to load strategy config: {strategy_path}, error={e}"
            )
            return {}

    async def run(self) -> None:
        """Coordinator loop for all active researches.

        Queries all active AGENT_RESEARCH operations and advances each one step.
        Exits when no active operations remain.

        Uses a polling pattern: query active ops, advance each, sleep, repeat.
        This supports multiple concurrent researches running independently.

        Raises:
            asyncio.CancelledError: If the coordinator is cancelled.
            WorkerError: If any child worker fails.
            GateFailedError: If a quality gate check fails.
        """
        logger.info("Coordinator started")

        with tracer.start_as_current_span("agent.coordinator") as span:
            span.set_attribute("operation.type", "coordinator")

            # Initialize before loop to handle early cancellation
            active_ops: list = []

            try:
                while True:
                    # Query all active research operations
                    active_ops = await self._get_active_research_operations()

                    if not active_ops:
                        logger.info("No active researches, coordinator stopping")
                        break

                    # Advance each active research one step (error isolation per-research)
                    for op in active_ops:
                        try:
                            await self._advance_research(op)
                        except asyncio.CancelledError:
                            # Per-research cancellation (e.g., child operation was cancelled)
                            await self._handle_research_cancelled(op)
                        except (WorkerError, GateError) as e:
                            # Known error types - log and fail the research
                            await self._handle_research_failed(op, e)
                        except Exception as e:
                            # Unexpected errors - log with details and fail the research
                            logger.error(
                                f"Unexpected error in research {op.operation_id}: {e}"
                            )
                            await self._handle_research_failed(op, e)

                    # Poll interval
                    await self._cancellable_sleep(self.POLL_INTERVAL)

            except asyncio.CancelledError:
                logger.info("Coordinator cancelled")
                span.set_attribute("outcome", "cancelled")
                # Save checkpoints for all active operations before cancellation
                for op in active_ops:
                    await self._save_checkpoint(op.operation_id, "cancellation")
                # Propagate cancellation to active child
                await self._cancel_current_child()
                raise
            except Exception as e:
                span.set_attribute("outcome", "failed")
                span.set_attribute("error", str(e))
                span.record_exception(e)
                logger.error(f"Coordinator error: {e}")
                raise

        logger.info("Coordinator completed")

    async def _start_design(self, operation_id: str) -> None:
        """Start the design phase with design worker.

        Args:
            operation_id: Parent operation ID.
        """
        parent_op = await self.ops.get_operation(operation_id)
        # Get model and brief from parent metadata (Task 8.3 runtime selection, M3 brief)
        model = None
        brief = None
        if parent_op:
            model = parent_op.metadata.parameters.get("model")
            brief = parent_op.metadata.parameters.get("brief")
            parent_op.metadata.parameters["phase"] = "designing"
            parent_op.metadata.parameters["phase_start_time"] = time.time()
        logger.info(f"Phase started: {operation_id}, phase=designing, model={model}")

        # Update progress for CLI monitoring (M9)
        await self.ops.update_progress(
            operation_id,
            OperationProgress(percentage=5.0, current_step="Designing strategy..."),
        )

        # Create task wrapper - worker owns its child operation
        async def run_child():
            # Pass parent operation_id - worker creates and manages its own child op
            # Worker stores child op ID in parent metadata (design_op_id) for tracking
            return await self.design_worker.run(operation_id, model=model, brief=brief)

        # Start as asyncio task (keyed by operation_id for multi-research support)
        task = asyncio.create_task(run_child())
        self._child_tasks[operation_id] = task
        # Note: child op ID will be available in parent metadata after worker starts

    async def _handle_designing_phase(self, operation_id: str, child_op: Any) -> None:
        """Handle designing phase state transitions.

        Args:
            operation_id: Parent operation ID.
            child_op: Design child operation.
        """
        # Check for pre-loaded strategy (skip-design mode via --strategy CLI option)
        parent_op = await self.ops.get_operation(operation_id)
        if parent_op and parent_op.metadata.parameters.get("design_complete"):
            # Strategy was provided at trigger time, design phase is complete
            # Wait for training worker availability (natural queuing)
            if not await self._is_training_worker_available():
                logger.debug(
                    f"Research {operation_id}: design complete (pre-loaded strategy), "
                    "waiting for training worker"
                )
                return  # Retry next cycle

            # Start training directly
            logger.info(
                f"Research {operation_id}: starting training with pre-loaded strategy "
                f"{parent_op.metadata.parameters.get('strategy_name')}"
            )
            await self._start_training(operation_id)
            return

        if child_op is None:
            # Check if there's a task running for THIS operation (stub workers)
            task = self._child_tasks.get(operation_id)
            if task is not None:
                if task.done():
                    # Task completed - check for exceptions
                    exc = task.exception()
                    if exc is not None:
                        del self._child_tasks[operation_id]
                        raise exc
                    # Task completed successfully - stub worker case
                    # Get result and store for later use in training
                    result = task.result()
                    del self._child_tasks[operation_id]

                    # Store design result for stub flow (persists across get_operation calls)
                    if isinstance(result, dict):
                        self._design_results[operation_id] = result

                        # Record design phase metrics
                        parent_op = await self.ops.get_operation(operation_id)
                        if parent_op:
                            # Store strategy_path in metadata for backtest phase
                            parent_op.metadata.parameters["strategy_path"] = result.get(
                                "strategy_path"
                            )
                            phase_start = parent_op.metadata.parameters.get(
                                "phase_start_time"
                            )
                            if phase_start:
                                record_phase_duration(
                                    "designing", time.time() - phase_start
                                )

                        # Record token usage from design
                        input_tokens = result.get("input_tokens", 0) or 0
                        output_tokens = result.get("output_tokens", 0) or 0
                        if input_tokens or output_tokens:
                            record_tokens("design", input_tokens + output_tokens)

                    # Check training worker availability before transitioning
                    if not await self._is_training_worker_available():
                        logger.debug(
                            f"Research {operation_id}: design complete, waiting for training worker"
                        )
                        return  # Stay in designing, retry next cycle

                    await self._start_training(operation_id)
                    return
                else:
                    # Task still running, wait
                    return

            # Check if design already completed (retry scenario - waiting for worker)
            if operation_id in self._design_results:
                # Design completed earlier, waiting for training worker
                if await self._is_training_worker_available():
                    await self._start_training(operation_id)
                else:
                    logger.debug(
                        f"Research {operation_id}: still waiting for training worker"
                    )
                return

            # No child op, no task, no stored results - start design
            await self._start_design(operation_id)
            return

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return

        if child_op.status == OperationStatus.COMPLETED:
            # Design complete, store results and start training
            # Guard against non-dict result_summary (e.g., from mocks)
            result = (
                child_op.result_summary
                if isinstance(child_op.result_summary, dict)
                else {}
            )
            parent_op = await self.ops.get_operation(operation_id)

            # Create span for design phase completion
            with tracer.start_as_current_span("agent.phase.design") as phase_span:
                phase_span.set_attribute("operation.id", operation_id)
                phase_span.set_attribute("phase", "designing")
                phase_span.set_attribute(
                    "strategy_name", result.get("strategy_name", "unknown")
                )

                # Record token usage in span
                input_tokens = result.get("input_tokens", 0) or 0
                output_tokens = result.get("output_tokens", 0) or 0
                phase_span.set_attribute("tokens.input", input_tokens)
                phase_span.set_attribute("tokens.output", output_tokens)
                phase_span.set_attribute("tokens.total", input_tokens + output_tokens)

            if parent_op:
                parent_op.metadata.parameters["strategy_name"] = result.get(
                    "strategy_name"
                )
                parent_op.metadata.parameters["strategy_path"] = result.get(
                    "strategy_path"
                )

                # Record design phase metrics
                phase_start = parent_op.metadata.parameters.get("phase_start_time")
                if phase_start:
                    record_phase_duration("designing", time.time() - phase_start)

                # Record token usage from design
                if input_tokens or output_tokens:
                    record_tokens("design", input_tokens + output_tokens)

                    # Record budget spend immediately after design phase
                    estimated_cost = self._estimate_cost(input_tokens, output_tokens)
                    budget = get_budget_tracker()
                    budget.record_spend(estimated_cost, operation_id)
                    record_budget_spend(estimated_cost)

            # Check training worker availability before transitioning
            if not await self._is_training_worker_available():
                logger.debug(
                    f"Research {operation_id}: design complete, waiting for training worker"
                )
                return  # Stay in designing, retry next cycle

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

        # Check stub design results first (for stub worker flow)
        design_result = self._design_results.get(operation_id, {})
        strategy_path = design_result.get(
            "strategy_path"
        ) or parent_op.metadata.parameters.get("strategy_path")

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
        parent_op.metadata.parameters["phase_start_time"] = time.time()
        self._current_service_child_op_id = training_op_id

        logger.info(f"Training started: {training_op_id}")

        # Update progress for CLI monitoring (M9)
        await self.ops.update_progress(
            operation_id,
            OperationProgress(percentage=20.0, current_step="Training model..."),
        )

    async def _handle_training_phase(self, operation_id: str, child_op: Any) -> None:
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

            # Check training gate (skip if bypass_gates is True)
            bypass_gates = (
                parent_op.metadata.parameters.get("bypass_gates", False)
                if parent_op
                else False
            )
            if bypass_gates:
                passed, reason = True, "bypassed"
                logger.info(f"Training gate bypassed: {operation_id}")
            else:
                passed, reason = check_training_gate(result)

            # Create span for training phase completion
            with tracer.start_as_current_span("agent.phase.training") as phase_span:
                phase_span.set_attribute("operation.id", operation_id)
                phase_span.set_attribute("phase", "training")
                phase_span.set_attribute("gate.name", "training")
                phase_span.set_attribute("gate.passed", passed)
                phase_span.set_attribute("gate.reason", reason)

                # Record training metrics in span
                phase_span.set_attribute("accuracy", result.get("accuracy", 0))
                phase_span.set_attribute("final_loss", result.get("final_loss", 0))

            if parent_op:
                parent_op.metadata.parameters["training_result"] = result
                parent_op.metadata.parameters["model_path"] = result.get("model_path")

                # Record training phase duration
                phase_start = parent_op.metadata.parameters.get("phase_start_time")
                if phase_start:
                    record_phase_duration("training", time.time() - phase_start)

            record_gate_result("training", passed)
            if not passed:
                # Gate rejection: route to ASSESSING instead of failing
                # This allows the system to learn from failed experiments
                logger.warning(
                    f"Training gate rejected: {operation_id}, reason={reason}, "
                    "routing to assessment"
                )
                # Skip backtest, go directly to assessment with partial results
                await self._start_assessment(
                    operation_id,
                    gate_rejection_reason=f"Training gate: {reason}",
                )
                return

            # Check backtest worker availability before transitioning
            if not await self._is_backtest_worker_available():
                logger.debug(
                    f"Research {operation_id}: training complete, waiting for backtest worker"
                )
                return  # Stay in training, retry next cycle

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
        params["phase_start_time"] = time.time()
        self._current_service_child_op_id = backtest_op_id

        logger.info(f"Backtest started: {backtest_op_id}")

        # Update progress for CLI monitoring (M9)
        await self.ops.update_progress(
            operation_id,
            OperationProgress(percentage=65.0, current_step="Running backtest..."),
        )

    async def _handle_backtesting_phase(self, operation_id: str, child_op: Any) -> None:
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

            # Get parent operation for gate check and metadata update
            parent_op = await self.ops.get_operation(operation_id)

            # Check backtest gate (skip if bypass_gates is True)
            bypass_gates = (
                parent_op.metadata.parameters.get("bypass_gates", False)
                if parent_op
                else False
            )
            if bypass_gates:
                passed, reason = True, "bypassed"
                logger.info(f"Backtest gate bypassed: {operation_id}")
            else:
                passed, reason = check_backtest_gate(backtest_result)

            # Create span for backtesting phase completion
            with tracer.start_as_current_span("agent.phase.backtest") as phase_span:
                phase_span.set_attribute("operation.id", operation_id)
                phase_span.set_attribute("phase", "backtesting")
                phase_span.set_attribute("gate.name", "backtest")
                phase_span.set_attribute("gate.passed", passed)
                phase_span.set_attribute("gate.reason", reason)

                # Record backtest metrics in span
                phase_span.set_attribute(
                    "sharpe_ratio", backtest_result.get("sharpe_ratio", 0)
                )
                phase_span.set_attribute("win_rate", backtest_result.get("win_rate", 0))
                phase_span.set_attribute(
                    "max_drawdown", backtest_result.get("max_drawdown", 0)
                )
            if parent_op:
                parent_op.metadata.parameters["backtest_result"] = backtest_result

                # Record backtesting phase duration
                phase_start = parent_op.metadata.parameters.get("phase_start_time")
                if phase_start:
                    record_phase_duration("backtesting", time.time() - phase_start)

            record_gate_result("backtest", passed)
            if not passed:
                # Gate rejection: route to ASSESSING with full results
                # (both training and backtest results available)
                logger.warning(
                    f"Backtest gate rejected: {operation_id}, reason={reason}, "
                    "routing to assessment"
                )
                await self._start_assessment(
                    operation_id,
                    gate_rejection_reason=f"Backtest gate: {reason}",
                )
                return

            # Start assessment with child worker
            await self._start_assessment(operation_id)

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Backtest failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Backtest was cancelled")

    async def _start_assessment(
        self,
        operation_id: str,
        gate_rejection_reason: str | None = None,
    ) -> None:
        """Start the assessment phase with assessment worker.

        Args:
            operation_id: Parent operation ID.
            gate_rejection_reason: If set, indicates a gate rejection scenario.
                For training gate rejection, backtest_result will be None.
                For backtest gate rejection, both results are present.
        """
        parent_op = await self.ops.get_operation(operation_id)
        # Get model from parent metadata (Task 8.3 runtime selection)
        model = None
        if parent_op:
            model = parent_op.metadata.parameters.get("model")
            parent_op.metadata.parameters["phase"] = "assessing"
            parent_op.metadata.parameters["phase_start_time"] = time.time()
        logger.info(f"Phase started: {operation_id}, phase=assessing, model={model}")

        # Update progress for CLI monitoring (M9)
        await self.ops.update_progress(
            operation_id,
            OperationProgress(percentage=90.0, current_step="Assessing results..."),
        )

        # Get results for assessment from parent metadata
        params = parent_op.metadata.parameters if parent_op else {}
        training_result = params.get("training_result", {})
        # For training gate rejection, backtest_result is None (not empty dict)
        backtest_result = params.get("backtest_result")
        if backtest_result == {}:
            backtest_result = None if gate_rejection_reason else {}
        results = {"training": training_result, "backtest": backtest_result}

        # Create task wrapper - worker owns its child operation
        async def run_child():
            # Pass parent operation_id - worker creates and manages its own child op
            # Worker stores child op ID in parent metadata (assessment_op_id) for tracking
            return await self.assessment_worker.run(
                operation_id,
                results,
                model=model,
                gate_rejection_reason=gate_rejection_reason,
            )

        # Start as asyncio task (keyed by operation_id for multi-research support)
        task = asyncio.create_task(run_child())
        self._child_tasks[operation_id] = task
        # Note: child op ID will be available in parent metadata after worker starts

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
            # Check if there's a task running for THIS operation (stub workers)
            task = self._child_tasks.get(operation_id)
            if task is not None:
                if task.done():
                    # Task completed - check for exceptions
                    exc = task.exception()
                    if exc is not None:
                        del self._child_tasks[operation_id]
                        raise exc
                    # Task completed successfully but no child op - stub worker case
                    # Complete the research operation
                    del self._child_tasks[operation_id]
                    parent_op = await self.ops.get_operation(operation_id)
                    strategy_name = (
                        parent_op.metadata.parameters.get("strategy_name", "unknown")
                        if parent_op
                        else "unknown"
                    )

                    # Update progress to 100% on completion
                    await self.ops.update_progress(
                        operation_id,
                        OperationProgress(percentage=100.0, current_step="Complete"),
                    )

                    # Mark operation as complete
                    completion_result = {
                        "success": True,
                        "strategy_name": strategy_name,
                        "verdict": "stub_completed",
                    }
                    await self.ops.complete_operation(operation_id, completion_result)

                    # Clean up per-operation state to prevent memory leaks
                    self._child_tasks.pop(operation_id, None)
                    self._design_results.pop(operation_id, None)

                    # Delete checkpoint on successful completion
                    await self._delete_checkpoint(operation_id)

                    # Record cycle metrics
                    if parent_op:
                        cycle_duration = time.time() - parent_op.created_at.timestamp()
                        record_cycle_duration(cycle_duration)
                    record_cycle_outcome("completed")

                    logger.info(f"Research completed (stub): {operation_id}")
                    return completion_result
                else:
                    # Task still running, wait
                    return None

            # No child op and no task, start assessment
            await self._start_assessment(operation_id)
            return None

        if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
            # Still running, wait
            return None

        if child_op.status == OperationStatus.COMPLETED:
            # All phases complete
            # Guard against non-dict result_summary (e.g., from mocks)
            result = (
                child_op.result_summary
                if isinstance(child_op.result_summary, dict)
                else {}
            )
            parent_op = await self.ops.get_operation(operation_id)
            strategy_name = parent_op.metadata.parameters.get(
                "strategy_name", "unknown"
            )

            # Create span for assessment phase completion
            with tracer.start_as_current_span("agent.phase.assessment") as phase_span:
                phase_span.set_attribute("operation.id", operation_id)
                phase_span.set_attribute("phase", "assessing")
                phase_span.set_attribute("verdict", result.get("verdict", "unknown"))
                phase_span.set_attribute("strategy_name", strategy_name)

                # Record token usage in span
                input_tokens = result.get("input_tokens", 0) or 0
                output_tokens = result.get("output_tokens", 0) or 0
                phase_span.set_attribute("tokens.input", input_tokens)
                phase_span.set_attribute("tokens.output", output_tokens)
                phase_span.set_attribute("tokens.total", input_tokens + output_tokens)

            # Store assessment verdict in parent metadata
            parent_op.metadata.parameters["assessment_verdict"] = result.get(
                "verdict", "unknown"
            )

            # Record assessing phase duration
            phase_start = parent_op.metadata.parameters.get("phase_start_time")
            if phase_start:
                record_phase_duration("assessing", time.time() - phase_start)

            # Record token usage from assessment
            if input_tokens or output_tokens:
                record_tokens("assessment", input_tokens + output_tokens)

                # Record budget spend immediately after assessment phase
                estimated_cost = self._estimate_cost(input_tokens, output_tokens)
                budget = get_budget_tracker()
                budget.record_spend(estimated_cost, operation_id)
                record_budget_spend(estimated_cost)

            # Update progress to 100% on completion (M9)
            await self.ops.update_progress(
                operation_id,
                OperationProgress(percentage=100.0, current_step="Complete"),
            )

            # Mark operation as complete (multi-research: completion handled in loop)
            completion_result = {
                "success": True,
                "strategy_name": strategy_name,
                "verdict": result.get("verdict", "unknown"),
            }
            await self.ops.complete_operation(operation_id, completion_result)

            # Clean up per-operation state to prevent memory leaks
            self._child_tasks.pop(operation_id, None)
            self._design_results.pop(operation_id, None)

            # Delete checkpoint on successful completion (no longer needed for resume)
            await self._delete_checkpoint(operation_id)

            # Record cycle metrics (duration from created_at to now)
            cycle_duration = time.time() - parent_op.created_at.timestamp()
            record_cycle_duration(cycle_duration)
            record_cycle_outcome("completed")

            logger.info(f"Research completed: {operation_id}")

            return completion_result

        elif child_op.status == OperationStatus.FAILED:
            raise WorkerError(f"Assessment failed: {child_op.error_message}")

        elif child_op.status == OperationStatus.CANCELLED:
            raise asyncio.CancelledError("Assessment was cancelled")

        return None

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in dollars based on actual model pricing.

        Uses MODEL_PRICING for the configured AGENT_MODEL to calculate costs.
        Defaults to Opus 4.5 pricing if model is unknown.

        Pricing (per 1M tokens):
        - Opus 4.5: $5 input, $25 output
        - Sonnet 4: $3 input, $15 output
        - Haiku 4.5: $1 input, $5 output

        Args:
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens used.

        Returns:
            Estimated cost in dollars.
        """
        model = os.getenv("AGENT_MODEL", DEFAULT_PRICING_MODEL)
        pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_PRICING_MODEL])

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    async def _is_training_worker_available(self) -> bool:
        """Check if a training worker is available.

        Used by the coordinator to implement natural queuing - researches
        wait in designing phase until a training worker becomes available.

        Returns:
            True if at least one training worker is available, False otherwise.
        """
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerType

        registry = get_worker_registry()
        available = registry.get_available_workers(WorkerType.TRAINING)
        return len(available) > 0

    async def _is_backtest_worker_available(self) -> bool:
        """Check if a backtest worker is available.

        Used by the coordinator to implement natural queuing - researches
        wait in training phase until a backtest worker becomes available.

        Returns:
            True if at least one backtest worker is available, False otherwise.
        """
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerType

        registry = get_worker_registry()
        available = registry.get_available_workers(WorkerType.BACKTESTING)
        return len(available) > 0

    async def _get_active_research_operations(self) -> list[Any]:
        """Query all active AGENT_RESEARCH operations.

        Returns operations with RUNNING or PENDING status.
        Used by the multi-research coordinator to iterate over all active researches.

        Returns:
            List of active operations (may be empty).
        """
        result: list[Any] = []
        for status in [OperationStatus.RUNNING, OperationStatus.PENDING]:
            ops, _, _ = await self.ops.list_operations(
                operation_type=OperationType.AGENT_RESEARCH,
                status=status,
            )
            result.extend(ops)
        return result

    async def _advance_research(self, op: Any) -> None:
        """Advance a single research one step through its phase.

        Called by the coordinator loop for each active research operation.
        Determines the current phase and calls the appropriate handler.

        Also detects orphaned in-process tasks after backend restart.
        Design and assessment phases run as asyncio tasks - if the backend
        restarts, the task is lost but the child operation may still show
        RUNNING. This orphaned state is detected and the phase is restarted.

        Args:
            op: The research operation to advance.
        """
        operation_id = op.operation_id
        phase = op.metadata.parameters.get("phase", "idle")

        # Get current child operation if any
        child_op_id = self._get_child_op_id(op, phase)
        child_op = None
        if child_op_id:
            child_op = await self.ops.get_operation(child_op_id)

        # Check for orphaned in-process tasks (design/assessment only)
        # Training and backtest run on external workers, so they survive restarts
        if phase in ("designing", "assessing"):
            if await self._check_and_handle_orphan(operation_id, phase, child_op):
                # Orphan was detected and handled, return early
                return

        # State machine logic - advance one step
        if phase == "idle":
            await self._start_design(operation_id)

        elif phase == "designing":
            await self._handle_designing_phase(operation_id, child_op)

        elif phase == "training":
            await self._handle_training_phase(operation_id, child_op)

        elif phase == "backtesting":
            await self._handle_backtesting_phase(operation_id, child_op)

        elif phase == "assessing":
            await self._handle_assessing_phase(operation_id, child_op)

    async def _check_and_handle_orphan(
        self, operation_id: str, phase: str, child_op: Any
    ) -> bool:
        """Check for and handle orphaned in-process tasks.

        After backend restart, design/assessment child operations may show
        RUNNING but no asyncio task exists. This orphaned state needs
        detection and recovery.

        Args:
            operation_id: Parent research operation ID.
            phase: Current phase name ("designing" or "assessing").
            child_op: Child operation for this phase (may be None).

        Returns:
            True if an orphan was detected and handled, False otherwise.
        """
        # Only check if child operation exists and is RUNNING
        if child_op is None:
            return False

        if child_op.status != OperationStatus.RUNNING:
            return False

        # Check if we have an active task for this operation
        # If task exists, it's not orphaned
        if operation_id in self._child_tasks:
            return False

        # Orphaned! Child is RUNNING but no task exists
        logger.warning(f"Detected orphaned {phase} task for {operation_id}, restarting")

        # Mark old child as failed
        await self.ops.fail_operation(
            child_op.operation_id, "Orphaned by backend restart"
        )

        # Restart the phase
        if phase == "designing":
            await self._start_design(operation_id)
        else:  # assessing
            await self._start_assessment(operation_id)

        return True

    async def _handle_research_cancelled(self, op: Any) -> None:
        """Handle cancellation for a single research.

        Called when a per-research CancelledError is caught (e.g., child operation
        was cancelled). Cancels any running child task, saves checkpoint, and
        marks the research as cancelled.

        Args:
            op: The research operation that was cancelled.
        """
        operation_id = op.operation_id
        logger.info(f"Research cancelled: {operation_id}")

        # Cancel child task if running (Task 4.4: propagate cancellation)
        if operation_id in self._child_tasks:
            task = self._child_tasks[operation_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling in-progress child task
            del self._child_tasks[operation_id]

        # Clean up remaining per-operation state to prevent memory leaks
        self._design_results.pop(operation_id, None)

        # Save checkpoint for resume capability
        await self._save_checkpoint(operation_id, "cancellation")

        # Mark the operation as cancelled
        await self.ops.cancel_operation(operation_id, "Cancelled")

        # Record metrics
        record_cycle_outcome("cancelled")

    async def _handle_research_failed(self, op: Any, error: Exception) -> None:
        """Handle failure for a single research.

        Called when an error is caught per-research. Saves checkpoint,
        marks the research as failed, and records metrics.

        Args:
            op: The research operation that failed.
            error: The exception that caused the failure.
        """
        operation_id = op.operation_id
        logger.error(f"Research failed: {operation_id}, error={error}")

        # Clean up per-operation state to prevent memory leaks
        self._child_tasks.pop(operation_id, None)
        self._design_results.pop(operation_id, None)

        # Save checkpoint for resume capability
        await self._save_checkpoint(operation_id, "failure")

        # Mark the operation as failed
        await self.ops.fail_operation(operation_id, str(error))

        # Record metrics
        record_cycle_outcome("failed")

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
        """Cancel all running child operations/tasks.

        Called when coordinator is cancelled to propagate cancellation.
        """
        if self._current_service_child_op_id:
            try:
                await self.ops.cancel_operation(
                    self._current_service_child_op_id, "Parent cancelled"
                )
            except Exception as e:
                logger.warning(f"Failed to cancel child operation: {e}")

        # Cancel all active child tasks (multi-research support)
        for op_id, task in list(self._child_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    # Wait with timeout to prevent hanging on unresponsive tasks
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.CancelledError:
                    # Expected when task cancellation succeeds
                    logger.debug(f"Child task {op_id} cancelled successfully")
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Child task {op_id} did not respond to cancellation within timeout"
                    )
            del self._child_tasks[op_id]

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

    async def _save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
    ) -> None:
        """Save checkpoint for an operation.

        Builds checkpoint state from the operation metadata and saves it.

        Args:
            operation_id: The operation ID to checkpoint.
            checkpoint_type: Type of checkpoint (failure, cancellation, etc.).
        """
        if self._checkpoint_service is None:
            logger.debug(
                f"Checkpoint service not available, skipping checkpoint save: {operation_id}"
            )
            return

        try:
            op = await self.ops.get_operation(operation_id)
            if op is None:
                logger.warning(
                    f"Cannot save checkpoint - operation not found: {operation_id}"
                )
                return

            checkpoint_state = build_agent_checkpoint_state(op)

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
            logger.warning(f"Failed to save agent checkpoint: {e}")

    async def _delete_checkpoint(self, operation_id: str) -> None:
        """Delete checkpoint for an operation.

        Called when an operation completes successfully.

        Args:
            operation_id: The operation ID whose checkpoint should be deleted.
        """
        if self._checkpoint_service is None:
            return

        try:
            await self._checkpoint_service.delete_checkpoint(operation_id)
            logger.debug(f"Checkpoint deleted for completed operation: {operation_id}")
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")
