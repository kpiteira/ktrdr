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

from ktrdr.api.models.backtesting import ResumeRequest
from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge
from ktrdr.checkpoint.service import CheckpointService
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

    def __init__(
        self,
        worker_port: int = 5003,
        backend_url: str = "http://backend:8000",
    ):
        """Initialize backtest worker."""
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Initialize CheckpointService for autonomous checkpoint loading
        self._checkpoint_service = CheckpointService()
        logger.info("CheckpointService initialized in backtest worker")

        # Register domain-specific endpoint: /backtests/start
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

        # Register domain-specific endpoint: /backtests/resume
        @self.app.post("/backtests/resume")
        async def resume_backtest(request: ResumeRequest):
            """
            Resume a backtest operation from checkpoint.

            Worker autonomy pattern:
            - Receives only operation IDs from backend (minimal payload)
            - Loads checkpoint autonomously from database
            - Returns operation_id back to backend
            - Starts work in background, returns immediately
            """
            # Use backend's task_id
            operation_id = request.task_id

            # Start resume work in background (non-blocking!)
            asyncio.create_task(
                self._execute_resume_backtest_work(operation_id, request)
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "started",
            }

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
        """

        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Build strategy config path
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

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

        # 3. Execute actual work (Engine, not Service!)
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

            # Run engine in thread pool (blocking operation)
            results = await asyncio.to_thread(
                engine.run,
                bridge=bridge,
                cancellation_token=cancellation_token,
            )

            # 4. Complete operation
            results_dict = results.to_dict()
            await self._operations_service.complete_operation(
                operation_id,
                results_dict,
            )

            logger.info(
                f"Backtest completed for {request.symbol} {request.timeframe}: "
                f"{results_dict.get('total_return', 0):.2%} return"
            )

            return {
                "result_summary": results_dict.get("result_summary", {}),
            }

        except Exception as e:
            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise

    async def _execute_resume_backtest_work(
        self,
        operation_id: str,
        request: ResumeRequest,
    ) -> dict[str, Any]:
        """
        Execute resumed backtest work from checkpoint.

        Worker autonomy pattern:
        1. Load checkpoint from database (autonomous)
        2. Load original operation metadata
        3. Extract parameters and rebuild request
        4. Call shared backtest execution logic

        Args:
            operation_id: New operation ID for resumed backtest
            request: Resume request with original_operation_id

        Returns:
            Result dictionary
        """
        try:
            # 1. Load checkpoint autonomously from database
            checkpoint = self._checkpoint_service.load_checkpoint(
                request.original_operation_id
            )

            if checkpoint is None:
                error_msg = f"No checkpoint found for {request.original_operation_id}"
                logger.error(error_msg)
                await self._operations_service.fail_operation(operation_id, error_msg)
                raise ValueError(error_msg)

            logger.info(
                f"Loaded checkpoint for {request.original_operation_id}: "
                f"type={checkpoint.get('checkpoint_type')}, "
                f"bar_index={checkpoint.get('current_bar_index')}"
            )

            # 2. Load original operation metadata to get parameters
            original_operation = await self._operations_service.get_operation(
                request.original_operation_id
            )

            if original_operation is None:
                error_msg = (
                    f"Original operation not found: {request.original_operation_id}"
                )
                logger.error(error_msg)
                await self._operations_service.fail_operation(operation_id, error_msg)
                raise ValueError(error_msg)

            # 3. Extract parameters and rebuild BacktestStartRequest
            metadata = original_operation.metadata
            params = metadata.parameters

            # Rebuild request from original operation metadata + checkpoint state
            resume_request = BacktestStartRequest(
                task_id=operation_id,
                symbol=metadata.symbol,
                timeframe=metadata.timeframe,
                strategy_name=params.get("strategy_name", ""),
                start_date=(
                    metadata.start_date.isoformat()
                    if hasattr(metadata.start_date, "isoformat")
                    else metadata.start_date
                ),
                end_date=(
                    metadata.end_date.isoformat()
                    if hasattr(metadata.end_date, "isoformat")
                    else metadata.end_date
                ),
                initial_capital=params.get("initial_capital", 100000.0),
                commission=params.get("commission", 0.001),
                slippage=params.get("slippage", 0.0),
            )

            # 4. Execute backtest work with checkpoint state
            # NOTE: In a full implementation, we'd pass checkpoint_state to the engine
            # For now, execute as fresh start (engine resume logic is separate task)
            logger.warning(
                f"Resume executing as fresh start for {operation_id}. "
                "Engine-level checkpoint resume not yet implemented."
            )

            result = await self._execute_backtest_work(operation_id, resume_request)

            return result

        except Exception as e:
            logger.error(f"Resume backtest failed for {operation_id}: {e}")
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
