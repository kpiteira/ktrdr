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

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge
from ktrdr.logging import get_logger
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

logger = get_logger(__name__)


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


# Create worker instance
worker = BacktestWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5003")),
    backend_url=os.getenv("KTRDR_API_URL", "http://backend:8000"),
)

# Export FastAPI app for uvicorn
app: FastAPI = worker.app
