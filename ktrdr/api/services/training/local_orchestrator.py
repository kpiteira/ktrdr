"""Local training orchestrator that uses TrainingPipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError, CancellationToken
from ktrdr.training.model_storage import ModelStorage
from ktrdr.training.training_pipeline import TrainingPipeline

if TYPE_CHECKING:
    from ktrdr.training.checkpoint_restore import TrainingResumeContext

logger = get_logger(__name__)


class LocalTrainingOrchestrator:
    """
    Orchestrate local training using TrainingPipeline.

    This orchestrator delegates all training work to TrainingPipeline while
    managing local-specific coordination:
    - Progress reporting via TrainingProgressBridge
    - Cancellation via in-memory CancellationToken
    - Async execution via asyncio.to_thread()
    """

    def __init__(
        self,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        model_storage: ModelStorage,
        checkpoint_callback=None,
        resume_context: TrainingResumeContext | None = None,
    ):
        """
        Initialize the local training orchestrator.

        Args:
            context: Training operation context
            progress_bridge: Bridge for progress reporting
            cancellation_token: Optional cancellation token
            model_storage: Model storage for saving trained models
            checkpoint_callback: Optional callback for checkpointing after each epoch.
                Called with kwargs: epoch, model, optimizer, scheduler, trainer.
            resume_context: Optional resume context for resumed training from checkpoint.
        """
        self._context = context
        self._bridge = progress_bridge
        self._token = cancellation_token
        self._model_storage = model_storage
        self._checkpoint_callback = checkpoint_callback
        self._resume_context = resume_context

    async def run(self) -> dict[str, Any]:
        """
        Execute training via TrainingPipeline.

        Returns:
            Training result with standardized format including session metadata

        Raises:
            CancellationError: If training is cancelled
        """
        self._bridge.on_phase("initializing", message="Preparing training environment")
        self._check_cancellation()

        try:
            # Wrap entire execution in thread pool (preserve current async pattern)
            result = await asyncio.to_thread(self._execute_training)
        except CancellationError:
            logger.info("Local training cancelled for %s", self._context.strategy_name)
            self._bridge.on_cancellation(message="Training cancelled")
            raise

        self._bridge.on_complete()
        return result

    def _execute_training(self) -> dict[str, Any]:
        """
        Execute training synchronously in worker thread.

        Returns:
            Training result with session metadata
        """
        # Step 1: Load strategy config from filesystem
        self._bridge.on_phase(
            "loading_config", message="Loading strategy configuration"
        )
        self._check_cancellation()

        config = self._load_strategy_config(self._context.strategy_path)

        # Step 2: Create progress callback adapter
        progress_callback = self._create_progress_callback()

        # Step 3: Call TrainingPipeline.train_strategy() with all parameters
        self._bridge.on_phase("training", message="Starting training pipeline")
        self._check_cancellation()

        result = TrainingPipeline.train_strategy(
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            strategy_config=config,
            start_date=self._context.start_date or "2020-01-01",
            end_date=self._context.end_date or "2024-12-31",
            model_storage=self._model_storage,
            progress_callback=progress_callback,
            cancellation_token=self._token,
            repository=None,  # Let pipeline create it (cached data only)
            checkpoint_callback=self._checkpoint_callback,
            resume_context=self._resume_context,
        )

        # Step 4: Add session metadata to result
        result["session_info"] = {
            "operation_id": self._context.operation_id,
            "strategy_name": self._context.strategy_name,
            "symbols": self._context.symbols,
            "timeframes": self._context.timeframes,
            "training_mode": "local",
            "use_host_service": False,
            "start_date": self._context.start_date,
            "end_date": self._context.end_date,
        }

        # Ensure resource_usage includes training_mode
        if "resource_usage" not in result:
            result["resource_usage"] = {}
        result["resource_usage"]["training_mode"] = "local"

        # TASK 3.3: Verification logging for result harmonization
        logger.info("=" * 80)
        logger.info("LOCAL TRAINING RESULT STRUCTURE")
        logger.info(f"  Keys: {list(result.keys())}")
        logger.info(f"  model_path: {result.get('model_path')}")
        logger.info(
            f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}"
        )
        logger.info(
            f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}"
        )
        logger.info(f"  artifacts keys: {list(result.get('artifacts', {}).keys())}")
        logger.info(
            f"  session_info keys: {list(result.get('session_info', {}).keys())}"
        )
        logger.info("=" * 80)

        return result

    def _load_strategy_config(self, config_path: Path) -> dict[str, Any]:
        """
        Load strategy configuration from YAML file.

        Args:
            config_path: Path to strategy YAML file

        Returns:
            Parsed configuration dictionary

        Raises:
            ValueError: If required sections are missing
        """
        logger.info(f"Loading strategy config from {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Validate required sections
        required_sections = ["indicators", "fuzzy_sets", "model", "training"]
        missing = [s for s in required_sections if s not in config]
        if missing:
            raise ValueError(f"Missing required sections in strategy config: {missing}")

        return config

    def _create_progress_callback(
        self,
    ) -> Callable[[int, int, dict[str, Any] | None], None]:
        """
        Create progress callback adapter.

        Translates TrainingPipeline progress callbacks to ProgressBridge updates.

        Returns:
            Progress callback function
        """

        def callback(
            epoch: int, total_epochs: int, metrics: dict[str, Any] | None = None
        ) -> None:
            """
            Handle progress update from TrainingPipeline.

            Args:
                epoch: Current epoch number
                total_epochs: Total number of epochs
                metrics: Optional metrics dictionary with progress_type
            """
            self._check_cancellation()

            metrics = metrics or {}
            progress_type = metrics.get("progress_type")

            if progress_type == "indicator_computation":
                # Per-indicator computation progress
                self._bridge.on_indicator_computation(
                    symbol=metrics.get("symbol", "Unknown"),
                    symbol_index=metrics.get("symbol_index", 1),
                    total_symbols=metrics.get("total_symbols", 1),
                    timeframe=metrics.get("timeframe", "unknown"),
                    indicator_name=metrics.get("indicator_name", "unknown"),
                    indicator_index=metrics.get("indicator_index", 1),
                    total_indicators=metrics.get("total_indicators", 1),
                )
            elif progress_type == "fuzzy_generation":
                # Per-fuzzy-set generation progress
                self._bridge.on_fuzzy_generation(
                    symbol=metrics.get("symbol", "Unknown"),
                    symbol_index=metrics.get("symbol_index", 1),
                    total_symbols=metrics.get("total_symbols", 1),
                    timeframe=metrics.get("timeframe", "unknown"),
                    fuzzy_set_name=metrics.get("fuzzy_set_name", "unknown"),
                    fuzzy_index=metrics.get("fuzzy_index", 1),
                    total_fuzzy_sets=metrics.get("total_fuzzy_sets", 1),
                )
            elif progress_type == "preprocessing":
                # Symbol-level preprocessing progress
                symbol = metrics.get("symbol", "Unknown")
                symbol_index = metrics.get("symbol_index", 1)
                total_symbols = metrics.get("total_symbols", 1)
                step = metrics.get("step", "processing")

                context = {}
                if "timeframes" in metrics:
                    context["timeframes"] = metrics["timeframes"]
                if "total_indicators" in metrics:
                    context["total_indicators"] = metrics["total_indicators"]
                if "total_fuzzy_sets" in metrics:
                    context["total_fuzzy_sets"] = metrics["total_fuzzy_sets"]

                self._bridge.on_symbol_processing(
                    symbol=symbol,
                    symbol_index=symbol_index,
                    total_symbols=total_symbols,
                    step=step,
                    context=context,
                )
            elif progress_type == "preparation":
                # Preparation phase progress (combining data, splitting, creating model)
                phase = metrics.get("phase", "preparing")
                message = None

                if phase == "combining_data":
                    total_symbols = metrics.get("total_symbols", 0)
                    message = f"Combining data from {total_symbols} symbol(s)"
                elif phase == "splitting_data":
                    total_samples = metrics.get("total_samples", 0)
                    message = f"Splitting {total_samples} samples (train/val/test)"
                elif phase == "creating_model":
                    input_dim = metrics.get("input_dim", 0)
                    message = f"Creating model (input_dim={input_dim})"

                self._bridge.on_preparation_phase(phase=phase, message=message)
            elif progress_type == "batch":
                # Batch-level progress
                self._bridge.on_batch(
                    epoch=epoch,
                    batch=metrics.get("batch", 0),
                    total_batches=metrics.get("total_batches_per_epoch"),
                    metrics=metrics,
                )
            elif progress_type == "epoch":
                # Epoch-level progress
                self._bridge.on_epoch(
                    epoch=epoch,
                    total_epochs=total_epochs,
                    metrics=metrics,
                )
            else:
                # Phase change or general update
                message = metrics.get("message") or "Training update"
                self._bridge.on_phase(progress_type or "update", message=message)

        return callback

    def _check_cancellation(self) -> None:
        """
        Check if training has been cancelled.

        Raises:
            CancellationError: If cancellation token is set
        """
        if self._token and self._token.is_cancelled():
            raise CancellationError("Training operation cancelled")
