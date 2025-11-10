"""
Backtesting Service - Orchestrator for backtesting operations.

Follows the ServiceOrchestrator pattern for async operations support,
matching the architecture of TrainingService.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import httpx

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.async_infrastructure import ServiceOrchestrator
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge

if TYPE_CHECKING:
    from ktrdr.api.services.worker_registry import WorkerRegistry

logger = logging.getLogger(__name__)


class BacktestingService(ServiceOrchestrator[None]):
    """
    Backtesting orchestration service with async operations support.

    Follows the same pattern as TrainingService:
    - Inherits from ServiceOrchestrator
    - Creates operations in OperationsService
    - Registers bridges (local) or proxies (remote)
    - Returns immediately, clients poll for progress

    Unlike TrainingService, backtesting doesn't need an adapter
    (no GPU requirements), so the generic type is None.
    """

    def __init__(self, worker_registry: "WorkerRegistry") -> None:
        """Initialize backtesting service (distributed-only mode).

        Args:
            worker_registry: WorkerRegistry for distributed worker selection (required).
        """
        super().__init__()
        self.operations_service = get_operations_service()
        self.worker_registry = worker_registry  # Required, not optional

        # Track which worker is handling which operation for cleanup
        # operation_id → worker_id mapping
        self._operation_workers: dict[str, str] = {}

        logger.info("Backtesting service initialized (distributed mode)")

    def _initialize_adapter(self) -> None:
        """
        Initialize adapter (required by ServiceOrchestrator).

        Backtesting doesn't need an adapter since it doesn't require
        special hardware access like training (GPU). Returns None.
        """
        return None

    def _get_service_name(self) -> str:
        """Get service name for logging."""
        return "Backtesting"

    def _get_default_host_url(self) -> str:
        """Get default host URL (not used in distributed-only mode)."""
        return ""

    def _get_env_var_prefix(self) -> str:
        """Get environment variable prefix (not used in distributed-only mode)."""
        return ""

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the backtesting service.

        Returns:
            Dict with health check information
        """
        active_operations, _, _ = await self.operations_service.list_operations(
            operation_type=OperationType.BACKTESTING, active_only=True
        )
        return {
            "service": "BacktestingService",
            "status": "ok",
            "active_backtests": len(active_operations),
            "mode": "distributed",
        }

    def cleanup_worker(self, operation_id: str) -> None:
        """
        Mark worker as available after operation completes.

        This is a manual cleanup method. In normal operation, workers are
        automatically cleaned up by the health check system (workers report
        idle status when operations complete).

        Args:
            operation_id: Operation identifier
        """
        if operation_id not in self._operation_workers:
            logger.debug(f"No worker mapping found for operation {operation_id}")
            return

        worker_id = self._operation_workers[operation_id]

        self.worker_registry.mark_available(worker_id)
        logger.info(
            f"Manually marked worker {worker_id} as AVAILABLE "
            f"after operation {operation_id} completed"
        )

        # Remove from tracking
        del self._operation_workers[operation_id]

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: Optional[str],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.001,
    ) -> dict[str, Any]:
        """
        Run backtest with async operations support.

        Returns operation_id immediately. Clients poll for progress via:
          GET /operations/{operation_id}

        Args:
            symbol: Trading symbol
            timeframe: Timeframe for backtest
            strategy_config_path: Path to strategy configuration
            model_path: Path to trained model
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Initial capital amount
            commission: Commission rate
            slippage: Slippage rate

        Returns:
            Dictionary with operation_id and status
        """
        # Create context for the operation
        context = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_config_path": strategy_config_path,
            "model_path": model_path,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
        }

        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            mode="distributed",
            start_date=start_date,
            end_date=end_date,
            parameters={
                "strategy_config_path": strategy_config_path,
                "model_path": model_path,
                "initial_capital": initial_capital,
                "commission": commission,
                "slippage": slippage,
            },
        )

        # Use ServiceOrchestrator's start_managed_operation
        operation_result = await self.start_managed_operation(
            operation_name="backtest",
            operation_type=OperationType.BACKTESTING.value,
            operation_func=self._operation_entrypoint,
            context=context,
            metadata=metadata,
            total_steps=100,  # Default estimate
        )

        operation_id = operation_result["operation_id"]

        return {
            "success": True,
            "operation_id": operation_id,
            "status": "started",
            "message": f"Backtest started for {symbol} {timeframe}",
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": "distributed",
        }

    async def _operation_entrypoint(
        self,
        *,
        operation_id: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Entry point for backtest operations (called by ServiceOrchestrator).

        Always dispatches to worker (distributed-only mode).

        Args:
            operation_id: Operation identifier
            context: Operation context with parameters

        Returns:
            Results dictionary or None for async operations
        """
        logger.info("=" * 80)
        logger.info("🚀 EXECUTING BACKTEST: DISTRIBUTED MODE")
        logger.info(f"   Operation ID: {operation_id}")
        logger.info(f"   Symbol: {context['symbol']}")
        logger.info(f"   Timeframe: {context['timeframe']}")
        logger.info("=" * 80)
        return await self.run_backtest_on_worker(
            operation_id=operation_id,
            symbol=context["symbol"],
            timeframe=context["timeframe"],
            strategy_config_path=context["strategy_config_path"],
            model_path=context["model_path"],
            start_date=datetime.fromisoformat(context["start_date"]),
            end_date=datetime.fromisoformat(context["end_date"]),
            initial_capital=context["initial_capital"],
            commission=context.get("commission", 0.001),
            slippage=context.get("slippage", 0.001),
        )

    async def run_backtest_on_worker(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        commission: float = 0.001,
        slippage: float = 0.001,
    ) -> dict[str, Any]:
        """
        Run backtest on worker using distributed execution pattern.

        Distributed-only mode: always dispatches to worker via WorkerRegistry.

        Workflow:
        1. Select available worker from WorkerRegistry
        2. Start backtest on worker (HTTP POST)
        3. Get remote operation ID
        4. Create OperationServiceProxy
        5. Register proxy with OperationsService
        6. Return immediately (no waiting)

        Args:
            operation_id: Backend operation identifier
            symbol: Trading symbol
            timeframe: Timeframe
            strategy_config_path: Strategy configuration path
            model_path: Model file path
            start_date: Start date
            end_date: End date
            initial_capital: Initial capital
            commission: Commission rate
            slippage: Slippage rate

        Returns:
            Dictionary with status="started" (worker operation continues independently)

        Raises:
            RuntimeError: If no workers are available
        """
        # (1) Select worker from registry with retry on 503 (worker busy)
        worker_id: Optional[str] = None
        remote_url: str
        max_retries = 3
        attempted_workers: list[str] = []

        for attempt in range(max_retries):
            worker = self.worker_registry.select_worker(WorkerType.BACKTESTING)
            if not worker:
                if attempt == 0:
                    raise RuntimeError(
                        "No available backtest workers. All workers are busy or unavailable."
                    )
                # All workers have been tried, none available
                raise RuntimeError(
                    f"All backtest workers are busy. Tried {len(attempted_workers)} workers: {attempted_workers}"
                )

            # Skip workers we've already tried
            if worker.worker_id in attempted_workers:
                continue

            worker_id = worker.worker_id
            remote_url = worker.endpoint_url
            attempted_workers.append(worker_id)

            logger.info(
                f"Selected worker {worker_id} for operation {operation_id} "
                f"(symbol={symbol}, timeframe={timeframe}, attempt={attempt + 1}/{max_retries})"
            )
            break  # Worker selected, exit retry loop to try dispatching
        else:
            raise RuntimeError(
                f"Could not select unique worker after {max_retries} attempts"
            )

        # (2) Dispatch to worker with retry on 503
        # Extract strategy_name from strategy_config_path (e.g., "strategies/test.yaml" -> "test")
        import os

        strategy_name = os.path.splitext(os.path.basename(strategy_config_path))[0]

        request_payload = {
            "strategy_name": strategy_name,  # Remote API expects strategy_name, not path
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
        }

        remote_response = None
        remote_operation_id = None

        # Retry loop: Try selected worker, if 503 (busy), select different worker
        for retry_attempt in range(max_retries):
            try:
                logger.info(
                    f"Dispatching backtest to worker {worker_id} at {remote_url}/backtests/start "
                    f"(attempt {retry_attempt + 1}/{max_retries})"
                )

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{remote_url}/backtests/start",
                        json=request_payload,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    remote_response = response.json()

                # Success! Break retry loop
                remote_operation_id = remote_response.get("operation_id")
                if not remote_operation_id:
                    raise RuntimeError("Remote service did not return operation_id")

                logger.info(
                    f"✅ Backtest accepted by worker {worker_id}: remote_op={remote_operation_id}"
                )
                break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    # Worker is busy, try different worker
                    logger.warning(
                        f"Worker {worker_id} is busy (503), selecting different worker "
                        f"(attempt {retry_attempt + 1}/{max_retries})"
                    )

                    if retry_attempt < max_retries - 1:
                        # Select a different worker for next attempt
                        worker = self.worker_registry.select_worker(
                            WorkerType.BACKTESTING
                        )
                        if worker and worker.worker_id not in attempted_workers:
                            worker_id = worker.worker_id
                            remote_url = worker.endpoint_url
                            attempted_workers.append(worker_id)
                            logger.info(f"Retrying with worker {worker_id}")
                            continue  # Retry with new worker
                        else:
                            # No more unique workers available
                            raise RuntimeError(
                                f"All workers busy or unavailable after {retry_attempt + 1} attempts. "
                                f"Tried workers: {attempted_workers}"
                            ) from e
                    else:
                        # Last retry failed
                        raise RuntimeError(
                            f"All workers busy after {max_retries} attempts. "
                            f"Tried workers: {attempted_workers}"
                        ) from e
                else:
                    # Other HTTP error, don't retry
                    raise

        if not remote_operation_id:
            raise RuntimeError("Failed to start backtest on any worker")

        logger.info(
            f"Remote backtest started: backend_op={operation_id}, "
            f"remote_op={remote_operation_id}"
        )

        # (3) Mark worker as busy
        if worker_id is not None:
            self.worker_registry.mark_busy(worker_id, operation_id)
            self._operation_workers[operation_id] = worker_id
            logger.info(
                f"Marked worker {worker_id} as BUSY for operation {operation_id}"
            )
            logger.info(
                "Worker cleanup will be handled by health check system "
                "(worker reports idle when backtest completes)"
            )

        # (4) Create OperationServiceProxy for remote service
        proxy = OperationServiceProxy(base_url=remote_url)

        # (5) Register proxy with OperationsService
        self.operations_service.register_remote_proxy(
            backend_operation_id=operation_id,
            proxy=proxy,
            host_operation_id=remote_operation_id,
        )

        logger.info(f"Registered remote proxy: {operation_id} → {remote_operation_id}")

        # (6) Return immediately with status="started"
        # Backend doesn't know completion status - client discovers via queries
        # TODO: Add callback to mark worker as available when operation completes
        return {
            "remote_operation_id": remote_operation_id,
            "backend_operation_id": operation_id,
            "status": "started",
            "message": f"Backtest started on remote service: {symbol} {timeframe}",
            "worker_id": worker_id,  # Include worker_id in response for visibility
        }
