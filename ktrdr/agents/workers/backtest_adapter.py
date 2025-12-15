"""Backtest worker adapter for agent orchestrator.

Adapts the existing BacktestingService for use by the agent orchestrator,
handling the polling loop and result transformation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Protocol

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus
from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class BacktestServiceProtocol(Protocol):
    """Protocol for BacktestingService to enable dependency injection."""

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: str | None,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> dict[str, Any]: ...


class WorkerError(Exception):
    """Error during worker execution."""

    pass


class BacktestWorkerAdapter:
    """Adapts BacktestingService for orchestrator use.

    This adapter:
    1. Starts backtest via BacktestingService
    2. Polls the backtest operation until complete
    3. Returns backtest metrics for gate evaluation
    """

    POLL_INTERVAL = 10.0  # seconds between status checks

    def __init__(
        self,
        operations_service: OperationsService,
        backtest_service: BacktestServiceProtocol | None = None,
    ):
        """Initialize the backtest worker adapter.

        Args:
            operations_service: Service for operation tracking and queries.
            backtest_service: Backtest service instance (created if not provided).
        """
        self.ops = operations_service
        self._backtest_service = backtest_service

    @property
    def backtest(self) -> BacktestServiceProtocol:
        """Get backtest service, creating lazily if needed."""
        if self._backtest_service is None:
            # Lazy import to avoid circular dependency
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.backtesting.backtesting_service import BacktestingService

            registry = get_worker_registry()
            self._backtest_service = BacktestingService(worker_registry=registry)  # type: ignore[assignment]
        return self._backtest_service  # type: ignore[return-value]

    async def run(
        self,
        parent_operation_id: str,
        model_path: str,
    ) -> dict[str, Any]:
        """Run backtest phase.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            model_path: Path to trained model.

        Returns:
            Backtest metrics including sharpe_ratio, win_rate, max_drawdown.

        Raises:
            WorkerError: If backtest fails.
            asyncio.CancelledError: If cancelled.
        """
        logger.info(
            f"Starting backtest phase for parent {parent_operation_id} "
            f"with model {model_path}"
        )

        # Get parent operation for strategy info
        parent_op = await self.ops.get_operation(parent_operation_id)
        if parent_op is None:
            raise WorkerError(f"Parent operation {parent_operation_id} not found")

        # Extract strategy info from parent metadata
        metadata = parent_op.metadata
        strategy_name = metadata.parameters.get("strategy_name", "unknown")
        strategy_path = metadata.parameters.get("strategy_path", "")
        symbol = metadata.symbol or "EURUSD"
        timeframe = metadata.timeframe or "1h"

        logger.info(
            f"Backtest config: strategy={strategy_name}, symbol={symbol}, "
            f"timeframe={timeframe}"
        )

        # Start backtest with held-out period (different from training)
        backtest_result = await self.backtest.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            strategy_config_path=strategy_path,
            model_path=model_path,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        backtest_op_id = backtest_result["operation_id"]
        logger.info(f"Backtest started with operation {backtest_op_id}")

        # Poll until complete
        try:
            result = await self._poll_until_complete(backtest_op_id)
            return result
        except asyncio.CancelledError:
            # Cancel the backtest operation too
            logger.info(f"Cancelling backtest operation {backtest_op_id}")
            await self.ops.cancel_operation(backtest_op_id, "Parent cancelled")
            raise

    async def _poll_until_complete(self, backtest_op_id: str) -> dict[str, Any]:
        """Poll backtest operation until it completes.

        Args:
            backtest_op_id: The backtest operation ID to poll.

        Returns:
            Backtest metrics dict.

        Raises:
            WorkerError: If backtest fails.
            asyncio.CancelledError: If backtest was cancelled.
        """
        while True:
            op = await self.ops.get_operation(backtest_op_id)

            if op is None:
                raise WorkerError(f"Backtest operation {backtest_op_id} not found")

            if op.status == OperationStatus.COMPLETED:
                result_summary = op.result_summary or {}
                metrics = result_summary.get("metrics", {})

                logger.info(
                    f"Backtest completed for {backtest_op_id} "
                    f"with sharpe_ratio {metrics.get('sharpe_ratio')}"
                )

                return {
                    "success": True,
                    "backtest_op_id": backtest_op_id,
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    # Use max_drawdown_pct (percentage) for gate evaluation
                    "max_drawdown": metrics.get("max_drawdown_pct", 1.0),
                    "total_return": metrics.get("total_return", 0),
                    "total_trades": metrics.get("total_trades", 0),
                }

            if op.status == OperationStatus.FAILED:
                error = op.error_message or "Unknown error"
                logger.error(f"Backtest failed for {backtest_op_id}: {error}")
                raise WorkerError(f"Backtest failed: {error}")

            if op.status == OperationStatus.CANCELLED:
                raise asyncio.CancelledError("Backtest was cancelled")

            # Log progress
            if op.progress:
                logger.debug(
                    f"Backtest progress for {backtest_op_id}: "
                    f"{op.progress.percentage:.1f}% - {op.progress.current_step}"
                )

            await asyncio.sleep(self.POLL_INTERVAL)
