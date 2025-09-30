"""Local training runner that integrates StrategyTrainer with the orchestrator."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.api.services.training.result_aggregator import from_local_run
from ktrdr.async_infrastructure.cancellation import CancellationError, CancellationToken
from ktrdr.training.train_strategy import StrategyTrainer

logger = get_logger(__name__)


class LocalTrainingRunner:
    """Execute training locally while forwarding progress to the orchestrator."""

    def __init__(
        self,
        *,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        strategy_trainer: StrategyTrainer | None = None,
    ) -> None:
        self._context = context
        self._bridge = progress_bridge
        self._cancellation_token = cancellation_token
        self._trainer = strategy_trainer or StrategyTrainer()

    async def run(self) -> dict[str, Any]:
        """Run the synchronous training workflow in a worker thread."""
        self._bridge.on_phase("initializing", message="Preparing training environment")
        self._raise_if_cancelled()

        try:
            raw_result = await asyncio.to_thread(self._execute_training)
        except CancellationError:
            logger.info("Local training cancelled for %s", self._context.strategy_name)
            self._bridge.on_phase("cancelled", message="Training cancelled")
            raise

        # Aggregate result into standardized format
        aggregated_result = from_local_run(self._context, raw_result or {})

        self._bridge.on_complete()
        return aggregated_result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute_training(self) -> dict[str, Any]:
        self._bridge.on_phase("data_preparation", message="Loading market data")
        self._raise_if_cancelled()

        progress_callback = self._build_progress_callback()

        return self._trainer.train_multi_symbol_strategy(
            strategy_config_path=str(self._context.strategy_path),
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            start_date=self._context.start_date or "2020-01-01",
            end_date=self._context.end_date or datetime.utcnow().strftime("%Y-%m-%d"),
            validation_split=self._context.training_config.get("validation_split", 0.2),
            data_mode=self._context.training_config.get("data_mode", "local"),
            progress_callback=progress_callback,
            cancellation_token=self._cancellation_token,
        )

    def _build_progress_callback(
        self,
    ) -> Callable[[int, int, dict[str, Any] | None], None]:
        def _callback(
            epoch: int, total_epochs: int, metrics: dict[str, Any] | None = None
        ) -> None:
            self._raise_if_cancelled()
            metrics = metrics or {}
            progress_type = metrics.get("progress_type")

            if progress_type == "batch":
                self._bridge.on_batch(
                    epoch=epoch,
                    batch=metrics.get("batch", 0),
                    total_batches=metrics.get("total_batches_per_epoch"),
                    metrics=metrics,
                )
            elif progress_type == "epoch":
                self._bridge.on_epoch(
                    epoch=epoch,
                    total_epochs=total_epochs,
                    metrics=metrics,
                )
            else:
                message = metrics.get("message") or "Training update"
                self._bridge.on_phase(progress_type or "update", message=message)

        return _callback

    def _raise_if_cancelled(self) -> None:
        if self._cancellation_token and self._cancellation_token.is_cancelled():
            raise CancellationError("Training operation cancelled")
