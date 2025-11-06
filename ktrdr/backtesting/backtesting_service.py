"""
Backtesting Service - Orchestrator for backtesting operations.

Follows the ServiceOrchestrator pattern for async operations support,
matching the architecture of TrainingService.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

import httpx

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.async_infrastructure import ServiceOrchestrator
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge

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

    def __init__(self) -> None:
        """Initialize backtesting service."""
        super().__init__()
        self.operations_service = get_operations_service()
        self._use_remote = self._should_use_remote_service()
        logger.info(
            f"Backtesting service initialized (mode: {'remote' if self._use_remote else 'local'})"
        )

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
        """Get default remote service URL."""
        return "http://localhost:5003"

    def _get_env_var_prefix(self) -> str:
        """Get environment variable prefix."""
        return "BACKTEST"

    def _should_use_remote_service(self) -> bool:
        """Check if should use remote backtest service."""
        env_value = os.getenv("USE_REMOTE_BACKTEST_SERVICE", "false").lower()
        return env_value in ("true", "1", "yes")

    def _get_remote_service_url(self) -> str:
        """Get remote backtest service URL."""
        return os.getenv("REMOTE_BACKTEST_SERVICE_URL", "http://localhost:5003")

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
            "mode": "remote" if self._use_remote else "local",
        }

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: str,
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
            "use_remote": self._use_remote,
        }

        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            mode="remote" if self._use_remote else "local",
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
            "mode": "remote" if self._use_remote else "local",
        }

    async def _operation_entrypoint(
        self,
        *,
        operation_id: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Entry point for backtest operations (called by ServiceOrchestrator).

        Args:
            operation_id: Operation identifier
            context: Operation context with parameters

        Returns:
            Results dictionary or None for async operations
        """
        if context.get("use_remote"):
            logger.info("=" * 80)
            logger.info("🚀 EXECUTING BACKTEST: REMOTE MODE")
            logger.info(f"   Operation ID: {operation_id}")
            logger.info(f"   Symbol: {context['symbol']}")
            logger.info(f"   Timeframe: {context['timeframe']}")
            logger.info("=" * 80)
            return await self._run_remote_backtest(
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
        else:
            logger.info("=" * 80)
            logger.info("💻 EXECUTING BACKTEST: LOCAL MODE")
            logger.info(f"   Operation ID: {operation_id}")
            logger.info(f"   Symbol: {context['symbol']}")
            logger.info(f"   Timeframe: {context['timeframe']}")
            logger.info("=" * 80)
            return await self._run_local_backtest(
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

    async def _run_local_backtest(
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
        Run backtest locally via thread pool.

        Follows training's pattern:
        1. Create BacktestProgressBridge
        2. Register bridge with OperationsService
        3. Run engine in thread (blocking operation)
        4. Return results

        Args:
            operation_id: Operation identifier
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
            Backtest results dictionary
        """
        # Create progress bridge for this operation
        # Estimate total bars (rough approximation)
        days = (end_date - start_date).days
        bars_per_day = {"1h": 24, "4h": 6, "1d": 1, "1w": 0.2}
        total_bars = int(days * bars_per_day.get(timeframe, 1))

        bridge = BacktestProgressBridge(
            operation_id=operation_id,
            symbol=symbol,
            timeframe=timeframe,
            total_bars=max(total_bars, 100),  # Minimum 100 bars estimate
        )

        # Register bridge with OperationsService for pull-based progress
        self.operations_service.register_local_bridge(operation_id, bridge)
        logger.info(f"Registered local backtest bridge for operation {operation_id}")

        # Build engine configuration
        engine_config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            strategy_config_path=strategy_config_path,
            model_path=model_path,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
        )

        # Create engine
        engine = BacktestingEngine(config=engine_config)

        # Get cancellation token from operations service
        cancellation_token = self.operations_service.get_cancellation_token(
            operation_id
        )

        # Run engine in thread pool (blocking operation)
        logger.info(f"Starting backtest engine in thread pool for {symbol} {timeframe}")
        results = await asyncio.to_thread(
            engine.run,
            bridge=bridge,
            cancellation_token=cancellation_token,
        )

        # Convert results to dictionary
        results_dict = results.to_dict()
        logger.info(
            f"Backtest completed for {symbol} {timeframe}: {results_dict.get('total_return', 0):.2%} return"
        )

        return results_dict

    async def _run_remote_backtest(
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
        Run backtest on remote service using proxy pattern.

        Follows training's remote pattern:
        1. Start backtest on remote service (HTTP POST)
        2. Get remote operation ID
        3. Create OperationServiceProxy
        4. Register proxy with OperationsService
        5. Return immediately (no waiting)

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
            Dictionary with status="started" (remote operation continues independently)
        """
        remote_url = self._get_remote_service_url()

        # (1) Start backtest on remote service
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

        logger.info(f"Starting remote backtest at {remote_url}/backtests/start")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{remote_url}/backtests/start",
                json=request_payload,
                timeout=30.0,
            )
            response.raise_for_status()
            remote_response = response.json()

        # (2) Get remote operation ID
        remote_operation_id = remote_response.get("operation_id")
        if not remote_operation_id:
            raise RuntimeError("Remote service did not return operation_id")

        logger.info(
            f"Remote backtest started: backend_op={operation_id}, "
            f"remote_op={remote_operation_id}"
        )

        # (3) Create OperationServiceProxy for remote service
        proxy = OperationServiceProxy(base_url=remote_url)

        # (4) Register proxy with OperationsService
        self.operations_service.register_remote_proxy(
            backend_operation_id=operation_id,
            proxy=proxy,
            host_operation_id=remote_operation_id,
        )

        logger.info(f"Registered remote proxy: {operation_id} → {remote_operation_id}")

        # (5) Return immediately with status="started"
        # Backend doesn't know completion status - client discovers via queries
        return {
            "remote_operation_id": remote_operation_id,
            "backend_operation_id": operation_id,
            "status": "started",
            "message": f"Backtest started on remote service: {symbol} {timeframe}",
        }
