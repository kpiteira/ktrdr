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
    OperationMetadata,
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
            logger.warning(
                f"Failed to load strategy config: {strategy_path}, error={e}"
            )
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
        cycle_start_time = time.time()

        with tracer.start_as_current_span("agent.research_cycle") as span:
            span.set_attribute("operation.id", operation_id)
            span.set_attribute("operation.type", "agent_research")

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
                        result = await self._handle_assessing_phase(
                            operation_id, child_op
                        )
                        if result is not None:
                            # Record successful cycle metrics
                            cycle_duration = time.time() - cycle_start_time
                            record_cycle_duration(cycle_duration)
                            record_cycle_outcome("completed")
                            span.set_attribute("outcome", "completed")
                            return result

                    # Poll interval
                    await self._cancellable_sleep(self.POLL_INTERVAL)

            except asyncio.CancelledError:
                logger.info(f"Research cycle cancelled: {operation_id}")
                # Record cancelled cycle metrics
                cycle_duration = time.time() - cycle_start_time
                record_cycle_duration(cycle_duration)
                record_cycle_outcome("cancelled")
                span.set_attribute("outcome", "cancelled")
                # Propagate cancellation to active child
                await self._cancel_current_child()
                raise
            except (WorkerError, GateFailedError) as e:
                # Record failed cycle metrics
                cycle_duration = time.time() - cycle_start_time
                record_cycle_duration(cycle_duration)
                record_cycle_outcome("failed")
                span.set_attribute("outcome", "failed")
                span.set_attribute("error", str(e))
                span.record_exception(e)
                raise
            except Exception as e:
                # Record failed cycle metrics
                cycle_duration = time.time() - cycle_start_time
                record_cycle_duration(cycle_duration)
                record_cycle_outcome("failed")
                span.set_attribute("outcome", "failed")
                span.set_attribute("error", str(e))
                span.record_exception(e)
                logger.error(f"Research cycle failed: {operation_id}, error={e}")
                raise

    async def _start_design(self, operation_id: str) -> None:
        """Start the design phase with design worker.

        Args:
            operation_id: Parent operation ID.
        """
        parent_op = await self.ops.get_operation(operation_id)
        # Get model from parent metadata (Task 8.3 runtime selection)
        model = None
        if parent_op:
            model = parent_op.metadata.parameters.get("model")
            parent_op.metadata.parameters["phase"] = "designing"
            parent_op.metadata.parameters["phase_start_time"] = time.time()
        logger.info(f"Phase started: {operation_id}, phase=designing, model={model}")

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
                # Pass model to design worker (Task 8.3 runtime selection)
                result = await self.design_worker.run(
                    child_op.operation_id, model=model
                )
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

    async def _handle_designing_phase(self, operation_id: str, child_op: Any) -> None:
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
        parent_op.metadata.parameters["phase_start_time"] = time.time()
        self._current_child_op_id = training_op_id

        logger.info(f"Training started: {training_op_id}")

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

            # Check training gate
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
                logger.warning(f"Training gate failed: {operation_id}, reason={reason}")
                raise GateError(
                    message=f"Training gate failed: {reason}",
                    gate="training",
                    metrics=result,
                )

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
        self._current_child_op_id = backtest_op_id

        logger.info(f"Backtest started: {backtest_op_id}")

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

            # Check backtest gate
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

            parent_op = await self.ops.get_operation(operation_id)
            if parent_op:
                parent_op.metadata.parameters["backtest_result"] = backtest_result

                # Record backtesting phase duration
                phase_start = parent_op.metadata.parameters.get("phase_start_time")
                if phase_start:
                    record_phase_duration("backtesting", time.time() - phase_start)

            record_gate_result("backtest", passed)
            if not passed:
                logger.warning(f"Backtest gate failed: {operation_id}, reason={reason}")
                raise GateError(
                    message=f"Backtest gate failed: {reason}",
                    gate="backtest",
                    metrics=backtest_result,
                )

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
        # Get model from parent metadata (Task 8.3 runtime selection)
        model = None
        if parent_op:
            model = parent_op.metadata.parameters.get("model")
            parent_op.metadata.parameters["phase"] = "assessing"
            parent_op.metadata.parameters["phase_start_time"] = time.time()
        logger.info(f"Phase started: {operation_id}, phase=assessing, model={model}")

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
                # Pass model to assessment worker (Task 8.3 runtime selection)
                result = await self.assessment_worker.run(
                    child_op.operation_id, results, model=model
                )
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
