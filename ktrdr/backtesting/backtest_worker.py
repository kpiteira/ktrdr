"""
Backtest Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but for
backtesting operations.
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from fastapi import FastAPI
from opentelemetry import trace

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge
from ktrdr.config import validate_all, warn_deprecated_env_vars
from ktrdr.config.settings import get_observability_settings, get_worker_settings
from ktrdr.logging import get_logger
from ktrdr.monitoring.setup import instrument_app, setup_monitoring
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

if TYPE_CHECKING:
    from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

logger = get_logger(__name__)

# =============================================================================
# Startup Validation (M4: Config System)
# =============================================================================
# These MUST run before any other initialization to fail fast on invalid config.
# 1. warn_deprecated_env_vars() emits DeprecationWarning for old env var names
# 2. validate_all("worker") raises ConfigurationError if config is invalid
warn_deprecated_env_vars()
validate_all("worker")


def _translate_model_path(model_path: str | None) -> str | None:
    """Translate host model path to container path if needed.

    CLI passes host paths like ~/.ktrdr/shared/models/... but inside Docker,
    paths are at /app/models/...

    Args:
        model_path: Original path (may be host path or container path)

    Returns:
        Translated container path, or original path if no translation needed
    """
    if not model_path:
        return model_path

    original_path = model_path

    # Pattern 1: ~/.ktrdr/shared/models/ → /app/models/
    ktrdr_shared_marker = "/.ktrdr/shared/models/"
    if ktrdr_shared_marker in model_path:
        marker_idx = model_path.index(ktrdr_shared_marker)
        relative = model_path[marker_idx + len(ktrdr_shared_marker) :]
        model_path = f"/app/models/{relative}"
        logger.info(f"Translated model path: {original_path} → {model_path}")
        return model_path

    # Pattern 2: Generic /*/models/ → /app/models/ (but not already /app/)
    if (
        model_path.startswith("/")
        and "/models/" in model_path
        and not model_path.startswith("/app/")
    ):
        marker_idx = model_path.index("/models/")
        relative = model_path[marker_idx + len("/models/") :]
        model_path = f"/app/models/{relative}"
        logger.info(f"Translated model path: {original_path} → {model_path}")
        return model_path

    return model_path


# Get worker ID for unique service identification (from settings, or generate if None)
_worker_settings = get_worker_settings()
worker_id = _worker_settings.worker_id or uuid.uuid4().hex[:8]

# Setup monitoring BEFORE creating worker
otel_settings = get_observability_settings()
setup_monitoring(
    service_name=f"ktrdr-backtest-worker-{worker_id}",
    otlp_endpoint=otel_settings.otlp_endpoint if otel_settings.enabled else None,
    console_output=otel_settings.console_output,
)


class BacktestStartRequest(WorkerOperationMixin):
    """Request to start a backtest (following training-host pattern)."""

    # task_id inherited from WorkerOperationMixin
    symbol: str
    timeframe: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0
    model_path: Optional[str] = None  # Explicit model path for v3 models


class BacktestResumeRequest(WorkerOperationMixin):
    """Request to resume a backtest from checkpoint.

    Sent by backend's POST /operations/{id}/resume endpoint.
    """

    operation_id: str


class BacktestWorker(WorkerAPIBase):
    """Backtest worker using WorkerAPIBase."""

    # Default checkpoint interval (bars)
    DEFAULT_CHECKPOINT_BAR_INTERVAL = 10000

    def __init__(
        self,
        worker_port: int = 5003,
        backend_url: str = "http://backend:8000",
        checkpoint_bar_interval: int = DEFAULT_CHECKPOINT_BAR_INTERVAL,
    ):
        """Initialize backtest worker."""
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Checkpoint configuration
        self.checkpoint_bar_interval = checkpoint_bar_interval
        self._checkpoint_service: Any | None = None  # Set lazily

        # Register domain-specific endpoint
        @self.app.post("/backtests/start")
        async def start_backtest(request: BacktestStartRequest):
            """
            Start a backtest operation.

            Follows training-host-service pattern:
            - Accepts task_id from backend for ID synchronization
            - Returns operation_id back to backend
            - Starts work in background, returns immediately
            """
            # Use backend's task_id if provided, generate if not
            operation_id = request.task_id or f"worker_backtest_{uuid.uuid4().hex[:12]}"

            # Start work in background (non-blocking!) - training-host pattern
            asyncio.create_task(self._execute_backtest_work(operation_id, request))

            return {
                "success": True,
                "operation_id": operation_id,  # ← Return same ID to backend!
                "status": "started",
            }

        # Register resume endpoint (M5 Task 5.5)
        @self.app.post("/backtests/resume")
        async def resume_backtest(request: BacktestResumeRequest):
            """
            Resume a backtest operation from checkpoint.

            Called by backend's POST /operations/{id}/resume endpoint.
            Worker must update status to RUNNING when starting.

            Follows M4's RESUMING status pattern:
            1. Backend sets status to RESUMING before calling this
            2. This endpoint loads checkpoint and starts work in background
            3. Worker updates status to RUNNING when it actually starts
            """
            from fastapi import HTTPException

            from ktrdr.backtesting.checkpoint_restore import CheckpointNotFoundError

            operation_id = request.operation_id

            try:
                # Load checkpoint context
                context = await self.restore_from_checkpoint(operation_id)

                # Start resumed backtest in background (non-blocking!)
                asyncio.create_task(
                    self._execute_resumed_backtest_work(operation_id, context)
                )

                return {
                    "success": True,
                    "operation_id": operation_id,
                    "status": "started",
                }

            except CheckpointNotFoundError as e:
                logger.error(f"No checkpoint found for resume: {operation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"No checkpoint available for operation {operation_id}",
                ) from e

    def _get_checkpoint_service(self):
        """Lazily initialize and return checkpoint service.

        Note: Backtesting checkpoints have no artifacts (all state in DB),
        but we still need to provide artifacts_dir for the service.
        The default "data/checkpoints" is used even though backtesting
        doesn't use it.
        """
        if self._checkpoint_service is None:
            from ktrdr.api.database import get_session_factory
            from ktrdr.checkpoint import CheckpointService

            self._checkpoint_service = CheckpointService(
                session_factory=get_session_factory(),
                # Use default artifacts_dir - backtesting doesn't use it
                # but service requires a valid path
            )
        return self._checkpoint_service

    async def restore_from_checkpoint(self, operation_id: str):
        """Restore backtest context from a checkpoint.

        Args:
            operation_id: The operation ID to restore.

        Returns:
            BacktestResumeContext with all state needed to resume.

        Raises:
            CheckpointNotFoundError: If no checkpoint exists for the operation.
        """
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        checkpoint_service = self._get_checkpoint_service()
        return await restore_from_checkpoint(
            checkpoint_service=checkpoint_service,
            operation_id=operation_id,
        )

    async def _execute_backtest_work(
        self,
        operation_id: str,
        request: BacktestStartRequest,
    ) -> dict[str, Any]:
        """
        Execute backtest work.

        Follows training-host-service pattern:
        1. Create operation in worker's OperationsService
        2. Create and register progress bridge
        3. Execute actual work (Engine, not Service!)
        4. Complete operation

        Checkpoint integration (M5):
        - Periodic checkpoint every N bars (configurable)
        - Cancellation checkpoint on cancel
        - Delete checkpoint on success
        """

        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Build strategy config path
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

        # Build original request for checkpoint (needed for resume)
        original_request = {
            "strategy_name": request.strategy_name,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "initial_capital": request.initial_capital,
            "commission": request.commission,
            "slippage": request.slippage,
        }

        # 1. Create operation in worker's OperationsService
        await self._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol=request.symbol,
                timeframe=request.timeframe,
                mode="backtesting",
                start_date=start_date,
                end_date=end_date,
                parameters={
                    "strategy_name": request.strategy_name,
                    "initial_capital": request.initial_capital,
                    "commission": request.commission,
                    "slippage": request.slippage,
                    "worker_id": self.worker_id,
                },
            ),
        )

        # 2. Create and register progress bridge
        days = (end_date - start_date).days
        bars_per_day = {"1h": 24, "4h": 6, "1d": 1, "5m": 288, "1w": 0.2}
        total_bars = int(days * bars_per_day.get(request.timeframe, 1))

        bridge = BacktestProgressBridge(
            operation_id=operation_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            total_bars=max(total_bars, 100),
        )

        self._operations_service.register_local_bridge(operation_id, bridge)
        logger.info(f"Registered backtest bridge for operation {operation_id}")

        # 2.5. Mark operation as RUNNING (CRITICAL for progress reporting!)
        # Create a dummy task - actual work happens in asyncio.to_thread below
        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await self._operations_service.start_operation(operation_id, dummy_task)
        logger.info(f"Marked operation {operation_id} as RUNNING")

        # 3. Setup checkpoint infrastructure
        checkpoint_service = self._get_checkpoint_service()

        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state
        from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy

        checkpoint_policy = CheckpointPolicy(
            unit_interval=self.checkpoint_bar_interval,
            time_interval_seconds=300,  # Also checkpoint every 5 minutes
        )

        # Track latest state for cancellation checkpoint
        last_checkpoint_state: dict[str, Any] = {}

        # Capture main event loop for use in checkpoint callback (Task 5.8 fix)
        # The callback runs in a thread pool via asyncio.to_thread(), but database
        # connections have Futures attached to this main loop. Using new_event_loop()
        # in the callback causes "Task got Future attached to a different loop" errors.
        main_loop = asyncio.get_running_loop()

        def checkpoint_callback(**kwargs):
            """Called periodically from engine's bar loop.

            Runs in thread pool (via asyncio.to_thread), so we use
            run_coroutine_threadsafe() to schedule saves on the main event loop.
            This avoids the "Future attached to different loop" error.
            """
            bar_index = kwargs["bar_index"]
            timestamp = kwargs["timestamp"]
            engine = kwargs["engine"]

            # Always update last state for potential cancellation checkpoint
            last_checkpoint_state["bar_index"] = bar_index
            last_checkpoint_state["timestamp"] = timestamp
            last_checkpoint_state["engine"] = engine

            # Check if we should save a periodic checkpoint
            if checkpoint_policy.should_checkpoint(bar_index):
                try:
                    # Build checkpoint state
                    state = build_backtest_checkpoint_state(
                        engine=engine,
                        bar_index=bar_index,
                        current_timestamp=timestamp,
                        original_request=original_request,
                    )

                    # Schedule checkpoint save on main event loop (Task 5.8 fix)
                    # This ensures database operations use the correct event loop
                    future = asyncio.run_coroutine_threadsafe(
                        checkpoint_service.save_checkpoint(
                            operation_id=operation_id,
                            checkpoint_type="periodic",
                            state=state.to_dict(),
                            artifacts=None,  # No artifacts for backtesting
                        ),
                        main_loop,
                    )
                    # Wait for completion with timeout
                    future.result(timeout=30.0)
                    checkpoint_policy.record_checkpoint(bar_index)
                    logger.info(
                        f"Periodic checkpoint saved for {operation_id} at bar {bar_index}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to save periodic checkpoint: {e}")

        # 4. Execute actual work (Engine, not Service!)
        try:
            # Translate model_path from host path to container path if needed
            model_path = _translate_model_path(request.model_path)

            # Build engine configuration
            engine_config = BacktestConfig(
                symbol=request.symbol,
                timeframe=request.timeframe,
                strategy_config_path=strategy_config_path,
                model_path=model_path,  # Use explicit path if provided (for v3)
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                initial_capital=request.initial_capital,
                commission=request.commission,
                slippage=request.slippage,
            )

            # Create engine
            engine = BacktestingEngine(config=engine_config)

            # Get cancellation token
            cancellation_token = self._operations_service.get_cancellation_token(
                operation_id
            )

            # Run engine in thread pool (blocking operation) with checkpoint callback
            results = await asyncio.to_thread(
                engine.run,
                bridge=bridge,
                cancellation_token=cancellation_token,
                checkpoint_callback=checkpoint_callback,
            )

            # 5. Complete operation - delete checkpoint on success
            results_dict = results.to_dict()
            await self._operations_service.complete_operation(
                operation_id,
                results_dict,
            )

            # Delete checkpoint on successful completion
            try:
                await checkpoint_service.delete_checkpoint(operation_id)
                logger.info(
                    f"Checkpoint deleted after successful completion: {operation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint on success: {e}")

            logger.info(
                f"Backtest completed for {request.symbol} {request.timeframe}: "
                f"{results_dict.get('total_return', 0):.2%} return"
            )

            return {
                "result_summary": results_dict.get("result_summary", {}),
            }

        except CancellationError:
            logger.info(f"Backtest operation {operation_id} cancelled")

            # Save cancellation checkpoint if we have state
            if last_checkpoint_state:
                try:
                    state = build_backtest_checkpoint_state(
                        engine=last_checkpoint_state["engine"],
                        bar_index=last_checkpoint_state["bar_index"],
                        current_timestamp=last_checkpoint_state["timestamp"],
                        original_request=original_request,
                    )
                    await checkpoint_service.save_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type="cancellation",
                        state=state.to_dict(),
                        artifacts=None,
                    )
                    logger.info(
                        f"Cancellation checkpoint saved for {operation_id} "
                        f"at bar {last_checkpoint_state['bar_index']}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to save cancellation checkpoint: {e}")

            if bridge:
                bridge.on_cancellation("Backtest cancelled")
            return {
                "status": "cancelled",
                "operation_id": operation_id,
            }

        except asyncio.CancelledError:
            # Handle standard asyncio cancellation if it occurs
            logger.info(f"Backtest operation {operation_id} cancelled (asyncio)")

            # Save cancellation checkpoint if we have state
            if last_checkpoint_state:
                try:
                    state = build_backtest_checkpoint_state(
                        engine=last_checkpoint_state["engine"],
                        bar_index=last_checkpoint_state["bar_index"],
                        current_timestamp=last_checkpoint_state["timestamp"],
                        original_request=original_request,
                    )
                    await checkpoint_service.save_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type="cancellation",
                        state=state.to_dict(),
                        artifacts=None,
                    )
                    logger.info(
                        f"Cancellation checkpoint saved for {operation_id} "
                        f"at bar {last_checkpoint_state['bar_index']}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to save cancellation checkpoint: {e}")

            if bridge:
                bridge.on_cancellation("Backtest cancelled")
            return {
                "status": "cancelled",
                "operation_id": operation_id,
            }

        except Exception as e:
            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise

    async def _execute_resumed_backtest_work(
        self,
        operation_id: str,
        context: "BacktestResumeContext",
    ) -> dict[str, Any]:
        """
        Execute resumed backtest work from checkpoint.

        Similar to _execute_backtest_work but:
        1. Uses checkpoint context instead of fresh request
        2. Calls engine.resume_from_context() to restore state
        3. Passes resume_start_bar to engine.run()

        Uses shared infrastructure from WorkerAPIBase:
        - adopt_and_start_operation() for resume-to-different-worker support
        - create_checkpoint_callback() for proper event loop handling
        - save_cancellation_checkpoint() for cancellation checkpoints
        """
        # Extract original request from context
        original_request = context.original_request

        # Parse dates from original request
        start_date = datetime.fromisoformat(original_request["start_date"])
        end_date = datetime.fromisoformat(original_request["end_date"])

        # Build strategy config path
        strategy_config_path = f"strategies/{original_request['strategy_name']}.yaml"

        # 1. Adopt operation and transition to RUNNING
        # This handles resume-to-different-worker: loads from DB if not in cache
        await self.adopt_and_start_operation(operation_id)

        # 2. Create and register progress bridge
        days = (end_date - start_date).days
        bars_per_day = {"1h": 24, "4h": 6, "1d": 1, "5m": 288, "1w": 0.2}
        total_bars = int(days * bars_per_day.get(original_request["timeframe"], 1))

        bridge = BacktestProgressBridge(
            operation_id=operation_id,
            symbol=original_request["symbol"],
            timeframe=original_request["timeframe"],
            total_bars=max(total_bars, 100),
        )

        self._operations_service.register_local_bridge(operation_id, bridge)
        logger.info(f"Registered resumed backtest bridge for operation {operation_id}")

        # 3. Setup checkpoint infrastructure using shared patterns
        checkpoint_service = self._get_checkpoint_service()

        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state
        from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy

        checkpoint_policy = CheckpointPolicy(
            unit_interval=self.checkpoint_bar_interval,
            time_interval_seconds=300,
        )

        # Track latest state for cancellation checkpoint
        last_checkpoint_state: dict[str, Any] = {}

        # Capture main event loop for checkpoint callback
        main_loop = asyncio.get_running_loop()

        # Create state builder closure that captures original_request
        def backtest_state_builder(**kwargs):
            return build_backtest_checkpoint_state(
                engine=kwargs["engine"],
                bar_index=kwargs["bar_index"],
                current_timestamp=kwargs["timestamp"],
                original_request=original_request,
            )

        # Use shared checkpoint callback infrastructure
        checkpoint_callback = self.create_checkpoint_callback(
            operation_id=operation_id,
            checkpoint_service=checkpoint_service,
            checkpoint_policy=checkpoint_policy,
            state_builder=backtest_state_builder,
            main_loop=main_loop,
            last_checkpoint_state=last_checkpoint_state,
            artifacts_builder=None,  # No artifacts for backtesting
        )

        # 4. Execute resumed backtest
        try:
            # Translate model_path from host path to container path if needed
            model_path = _translate_model_path(original_request.get("model_path"))

            # Build engine configuration from original request
            engine_config = BacktestConfig(
                symbol=original_request["symbol"],
                timeframe=original_request["timeframe"],
                strategy_config_path=strategy_config_path,
                model_path=model_path,  # Preserve model_path for v3
                start_date=original_request["start_date"],
                end_date=original_request["end_date"],
                initial_capital=original_request.get("initial_capital", 100000.0),
                commission=original_request.get("commission", 0.001),
                slippage=original_request.get("slippage", 0.0),
            )

            # Create engine
            engine = BacktestingEngine(config=engine_config)

            # Resume from checkpoint context (loads data, computes indicators, restores portfolio)
            engine.resume_from_context(context)

            # Get cancellation token
            cancellation_token = self._operations_service.get_cancellation_token(
                operation_id
            )

            # Run engine continuing from checkpoint bar
            results = await asyncio.to_thread(
                engine.run,
                bridge=bridge,
                cancellation_token=cancellation_token,
                checkpoint_callback=checkpoint_callback,
                resume_start_bar=context.start_bar,
            )

            # 5. Complete operation - delete checkpoint on success
            results_dict = results.to_dict()
            await self._operations_service.complete_operation(
                operation_id,
                results_dict,
            )

            # Delete checkpoint on successful completion
            try:
                await checkpoint_service.delete_checkpoint(operation_id)
                logger.info(
                    f"Checkpoint deleted after successful resumed completion: {operation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint on success: {e}")

            logger.info(
                f"Resumed backtest completed for {original_request['symbol']} "
                f"{original_request['timeframe']}: "
                f"{results_dict.get('total_return', 0):.2%} return"
            )

            return {
                "result_summary": results_dict.get("result_summary", {}),
            }

        except CancellationError:
            logger.info(f"Resumed backtest operation {operation_id} cancelled")

            # Save cancellation checkpoint using shared infrastructure
            await self.save_cancellation_checkpoint(
                operation_id=operation_id,
                checkpoint_service=checkpoint_service,
                last_checkpoint_state=last_checkpoint_state,
                state_builder=backtest_state_builder,
            )

            if bridge:
                bridge.on_cancellation("Resumed backtest cancelled")
            return {
                "status": "cancelled",
                "operation_id": operation_id,
            }

        except asyncio.CancelledError:
            logger.info(
                f"Resumed backtest operation {operation_id} cancelled (asyncio)"
            )

            # Save cancellation checkpoint using shared infrastructure
            await self.save_cancellation_checkpoint(
                operation_id=operation_id,
                checkpoint_service=checkpoint_service,
                last_checkpoint_state=last_checkpoint_state,
                state_builder=backtest_state_builder,
            )

            if bridge:
                bridge.on_cancellation("Resumed backtest cancelled")
            return {
                "status": "cancelled",
                "operation_id": operation_id,
            }

        except Exception as e:
            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise


# Create worker instance (port from settings, backend URL still from env)
worker = BacktestWorker(
    worker_port=_worker_settings.port,
    backend_url=os.getenv("KTRDR_API_URL", "http://backend:8000"),
)

# Auto-instrument with OpenTelemetry
instrument_app(worker.app)

# Add worker-specific span attributes (for tracing)
tracer = trace.get_tracer(__name__)
# Note: Worker attributes will be added during actual request handling
# The worker_id, worker_type, and capabilities are already tracked in WorkerAPIBase

# Export FastAPI app for uvicorn
app: FastAPI = worker.app
