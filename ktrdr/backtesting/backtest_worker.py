"""
Backtest Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but for
backtesting operations.
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge
from ktrdr.logging import get_logger
from ktrdr.monitoring.setup import instrument_app, setup_monitoring
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

logger = get_logger(__name__)

# Get worker ID for unique service identification
worker_id = os.getenv("WORKER_ID", uuid.uuid4().hex[:8])

# Setup monitoring BEFORE creating worker
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
setup_monitoring(
    service_name=f"ktrdr-backtest-worker-{worker_id}",
    otlp_endpoint=otlp_endpoint,
    console_output=os.getenv("ENVIRONMENT") == "development",
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

    def _get_checkpoint_service(self):
        """Lazily initialize and return checkpoint service."""
        if self._checkpoint_service is None:
            from ktrdr.checkpoint import CheckpointService

            self._checkpoint_service = CheckpointService()
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

        def checkpoint_callback(**kwargs):
            """Called periodically from engine's bar loop.

            Runs in thread pool, so we need to use a new event loop.
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

                    # Run async checkpoint save from sync context
                    # Since we're in a thread pool, we need to create a new event loop
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(
                            checkpoint_service.save_checkpoint(
                                operation_id=operation_id,
                                checkpoint_type="periodic",
                                state=state.to_dict(),
                                artifacts=None,  # No artifacts for backtesting
                            )
                        )
                        checkpoint_policy.record_checkpoint(bar_index)
                        logger.info(
                            f"Periodic checkpoint saved for {operation_id} at bar {bar_index}"
                        )
                    finally:
                        loop.close()

                except Exception as e:
                    logger.warning(f"Failed to save periodic checkpoint: {e}")

        # 4. Execute actual work (Engine, not Service!)
        try:
            # Build engine configuration
            engine_config = BacktestConfig(
                symbol=request.symbol,
                timeframe=request.timeframe,
                strategy_config_path=strategy_config_path,
                model_path=None,  # Auto-discovery
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


# Create worker instance
worker = BacktestWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5003")),
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
