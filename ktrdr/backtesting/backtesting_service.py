"""
Backtesting Service - Orchestrator for backtesting operations.

Follows the ServiceOrchestrator pattern for async operations support,
matching the architecture of TrainingService.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import httpx

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.uptime import get_uptime_seconds
from ktrdr.async_infrastructure import ServiceOrchestrator
from ktrdr.errors import WorkerUnavailableError

if TYPE_CHECKING:
    from ktrdr.api.models.workers import WorkerEndpoint
    from ktrdr.api.services.worker_registry import WorkerRegistry
    from ktrdr.config.models import StrategyConfigurationV3
    from ktrdr.models.model_metadata import ModelMetadataV3

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

    def _select_backtest_worker(
        self, excluded_workers: Optional[list[str]] = None
    ) -> "WorkerEndpoint":
        """
        Select an available backtest worker.

        Encapsulates worker selection logic and error handling, matching the
        pattern used in TrainingService._select_training_worker().

        Args:
            excluded_workers: List of worker_ids to exclude from selection
                (e.g., workers that have already been tried and returned 503)

        Returns:
            Selected WorkerEndpoint

        Raises:
            WorkerUnavailableError: If no backtest workers are available (HTTP 503)
        """
        # Get registered worker count for error context
        all_registered = self.worker_registry.list_workers(
            worker_type=WorkerType.BACKTESTING
        )
        registered_count = len(all_registered)

        # Select worker (registry handles load balancing)
        worker = self.worker_registry.select_worker(WorkerType.BACKTESTING)

        if not worker:
            raise WorkerUnavailableError(
                worker_type="backtesting",
                registered_count=registered_count,
                backend_uptime_seconds=get_uptime_seconds(),
            )

        # Check if this worker should be excluded
        if excluded_workers and worker.worker_id in excluded_workers:
            # All available workers have been tried
            raise WorkerUnavailableError(
                worker_type="backtesting",
                registered_count=registered_count,
                backend_uptime_seconds=get_uptime_seconds(),
                hint=f"All workers busy. Tried: {excluded_workers}",
            )

        return worker

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

        Task 3.10 Fix: For distributed operations, bypass start_managed_operation.
        The worker creates the operation in DB (not the backend) to avoid duplicate
        key errors. Backend just dispatches to worker and registers a proxy.

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
        # Task 3.10: Generate operation_id here, bypass start_managed_operation
        # The worker creates the operation in its DB (distributed-only mode)
        operation_id = self.operations_service.generate_operation_id(
            OperationType.BACKTESTING
        )

        logger.info(
            f"Starting backtest (distributed mode): {operation_id} "
            f"for {symbol} {timeframe}"
        )

        # Dispatch directly to worker (no start_managed_operation)
        # Worker will create the operation in DB
        worker_result = await self.run_backtest_on_worker(
            operation_id=operation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_config_path=strategy_config_path,
            model_path=model_path,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
        )

        # Return with the operation_id (backend_operation_id from worker)
        return {
            "success": True,
            "operation_id": worker_result.get("backend_operation_id", operation_id),
            "status": "started",
            "message": f"Backtest started for {symbol} {timeframe}",
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": "distributed",
            "worker_id": worker_result.get("worker_id"),
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
        model_path: Optional[str],
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
        # (1) Select worker from registry
        max_retries = 3
        attempted_workers: list[str] = []

        worker = self._select_backtest_worker()
        worker_id = worker.worker_id
        remote_url = worker.endpoint_url
        attempted_workers.append(worker_id)

        logger.info(
            f"Selected worker {worker_id} for operation {operation_id} "
            f"(symbol={symbol}, timeframe={timeframe})"
        )

        # (2) Dispatch to worker with retry on 503
        # Extract strategy_name from strategy_config_path (e.g., "strategies/test.yaml" -> "test")
        strategy_name = os.path.splitext(os.path.basename(strategy_config_path))[0]

        request_payload = {
            "task_id": operation_id,  # ← CRITICAL: Synchronize operation IDs (training-host pattern)
            "strategy_name": strategy_name,  # Remote API expects strategy_name, not path
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
            "model_path": model_path,  # Pass model_path to worker for v3 detection
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
                        # _select_backtest_worker raises WorkerUnavailableError if all tried
                        worker = self._select_backtest_worker(
                            excluded_workers=attempted_workers
                        )
                        worker_id = worker.worker_id
                        remote_url = worker.endpoint_url
                        attempted_workers.append(worker_id)
                        logger.info(f"Retrying with worker {worker_id}")
                        continue  # Retry with new worker
                    else:
                        # Last retry failed - let _select_backtest_worker raise the error
                        self._select_backtest_worker(excluded_workers=attempted_workers)
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

    # =========================================================================
    # V3 Model Support Methods (Static)
    # =========================================================================

    @staticmethod
    def load_v3_metadata(model_path: Union[str, Path]) -> "ModelMetadataV3":
        """Load v3 model metadata from model directory.

        V3 models store metadata in 'metadata_v3.json' file within
        the model directory.

        Args:
            model_path: Path to model directory

        Returns:
            ModelMetadataV3 instance

        Raises:
            FileNotFoundError: If metadata_v3.json doesn't exist
        """
        from ktrdr.models.model_metadata import ModelMetadataV3

        model_path = Path(model_path)
        metadata_path = model_path / "metadata_v3.json"

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"V3 metadata not found at {metadata_path}. "
                f"This model may not be a v3 model or may need to be retrained."
            )

        with open(metadata_path) as f:
            data = json.load(f)

        return ModelMetadataV3.from_dict(data)

    @staticmethod
    def is_v3_model(model_path: Union[str, Path]) -> bool:
        """Check if a model directory contains v3 metadata.

        Args:
            model_path: Path to model directory

        Returns:
            True if metadata_v3.json exists, False otherwise
        """
        model_path = Path(model_path)
        metadata_path = model_path / "metadata_v3.json"
        return metadata_path.exists()

    @staticmethod
    def validate_v3_model(model_path: Union[str, Path]) -> None:
        """Validate that a model is v3 format.

        Args:
            model_path: Path to model directory

        Raises:
            ValueError: If model is not v3 format
        """
        if not BacktestingService.is_v3_model(model_path):
            raise ValueError(
                f"Model at {model_path} is not a v3 model. "
                f"Expected metadata_v3.json file to exist. "
                f"This model may need to be retrained with v3 strategy grammar."
            )

        # Also validate strategy_version field
        metadata = BacktestingService.load_v3_metadata(model_path)
        if metadata.strategy_version != "3.0":
            raise ValueError(
                f"Model uses strategy version {metadata.strategy_version}, "
                f"expected 3.0. This model may need to be retrained."
            )

    @staticmethod
    def reconstruct_config_from_metadata(
        metadata: "ModelMetadataV3",
    ) -> "StrategyConfigurationV3":
        """Reconstruct StrategyConfigurationV3 from model metadata.

        V3 metadata stores the full strategy configuration for reproducibility.
        This method reconstructs the config for use in backtesting.

        Args:
            metadata: ModelMetadataV3 instance

        Returns:
            StrategyConfigurationV3 that matches the training configuration
        """
        from ktrdr.config.models import (
            FuzzySetDefinition,
            IndicatorDefinition,
            NNInputSpec,
            StrategyConfigurationV3,
            SymbolConfiguration,
            SymbolMode,
            TimeframeConfiguration,
            TimeframeMode,
            TrainingDataConfiguration,
        )

        # Reconstruct indicators
        indicators: dict[str, IndicatorDefinition] = {}
        for indicator_id, indicator_data in metadata.indicators.items():
            indicators[indicator_id] = IndicatorDefinition(**indicator_data)

        # Reconstruct fuzzy sets
        fuzzy_sets: dict[str, FuzzySetDefinition] = {}
        for fuzzy_set_id, fuzzy_data in metadata.fuzzy_sets.items():
            fuzzy_sets[fuzzy_set_id] = FuzzySetDefinition(**fuzzy_data)

        # Reconstruct nn_inputs
        nn_inputs = [NNInputSpec(**inp) for inp in metadata.nn_inputs]

        # Build training_data config from metadata training context
        # Use first symbol if available, otherwise a placeholder
        symbols = metadata.training_symbols or ["UNKNOWN"]
        timeframes = metadata.training_timeframes or ["1h"]

        if len(symbols) == 1:
            symbol_config = SymbolConfiguration(
                mode=SymbolMode.SINGLE, symbol=symbols[0]
            )
        else:
            symbol_config = SymbolConfiguration(
                mode=SymbolMode.MULTI_SYMBOL, symbols=symbols
            )

        if len(timeframes) == 1:
            timeframe_config = TimeframeConfiguration(
                mode=TimeframeMode.SINGLE, timeframe=timeframes[0]
            )
        else:
            timeframe_config = TimeframeConfiguration(
                mode=TimeframeMode.MULTI_TIMEFRAME,
                timeframes=timeframes,
                base_timeframe=timeframes[0],
            )

        training_data = TrainingDataConfiguration(
            symbols=symbol_config,
            timeframes=timeframe_config,
            history_required=100,  # Default value
        )

        return StrategyConfigurationV3(
            name=metadata.strategy_name,
            version=metadata.strategy_version,
            description=f"Reconstructed from model {metadata.model_name}",
            indicators=indicators,
            fuzzy_sets=fuzzy_sets,
            nn_inputs=nn_inputs,
            model={"type": "mlp"},  # Default, actual architecture in model file
            decisions={"output_format": "classification"},  # Default
            training={"epochs": 1},  # Placeholder
            training_data=training_data,
        )
