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

        Detects v2 vs v3 format and dispatches to appropriate training path.

        Returns:
            Training result with session metadata
        """
        # Step 1: Load strategy config from filesystem
        self._bridge.on_phase(
            "loading_config", message="Loading strategy configuration"
        )
        self._check_cancellation()

        config = self._load_strategy_config(self._context.strategy_path)

        # Step 2: Branch based on format
        if self._is_v3_format(config):
            logger.info("Detected v3 strategy format - using TrainingPipelineV3")
            result = self._execute_v3_training(config)
        else:
            logger.info("Detected v2 strategy format - using TrainingPipeline")
            result = self._execute_v2_training(config)

        # Step 3: Add session metadata to result
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

        # Verification logging for result harmonization
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

    def _execute_v2_training(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute v2 training using legacy TrainingPipeline.

        Args:
            config: V2 strategy configuration dictionary

        Returns:
            Training result dictionary
        """
        # Create progress callback adapter
        progress_callback = self._create_progress_callback()

        # Call TrainingPipeline.train_strategy() with all parameters
        self._bridge.on_phase("training", message="Starting v2 training pipeline")
        self._check_cancellation()

        return TrainingPipeline.train_strategy(
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

    def _execute_v3_training(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute v3 training using TrainingPipelineV3.

        This uses the v3 pipeline for feature preparation, then calls the standard
        model training/evaluation flow. After training completes, saves metadata_v3.json.

        Args:
            config: V3 strategy configuration dictionary

        Returns:
            Training result dictionary
        """
        from pathlib import Path

        from ktrdr.config.feature_resolver import FeatureResolver
        from ktrdr.config.strategy_loader import StrategyConfigurationLoader
        from ktrdr.data.repository import DataRepository
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        self._bridge.on_phase("training", message="Starting v3 training pipeline")
        self._check_cancellation()

        # Load as typed v3 config
        loader = StrategyConfigurationLoader()
        v3_config = loader.load_v3_strategy(self._context.strategy_path)

        # Resolve features to get canonical order
        resolver = FeatureResolver()
        resolved = resolver.resolve(v3_config)
        resolved_features = [f.feature_id for f in resolved]

        logger.info(f"V3 training: {len(resolved_features)} resolved features")

        # Create v3 pipeline
        pipeline = TrainingPipelineV3(v3_config)

        # Load market data for all symbols
        repository = DataRepository()
        all_data: dict[str, dict[str, Any]] = {}

        for symbol in self._context.symbols:
            symbol_data = TrainingPipeline.load_market_data(
                symbol=symbol,
                timeframes=self._context.timeframes,
                start_date=self._context.start_date or "2020-01-01",
                end_date=self._context.end_date or "2024-12-31",
                repository=repository,
            )
            all_data[symbol] = symbol_data

        # Prepare features using v3 pipeline
        logger.info("Preparing features with TrainingPipelineV3...")
        features_df = pipeline.prepare_features(all_data)

        # Convert to tensors and create labels using base pipeline methods
        import torch

        features = torch.FloatTensor(features_df.values)
        feature_names = list(features_df.columns)

        # Generate labels from price data (use first symbol's base timeframe)
        base_symbol = self._context.symbols[0]
        price_data = all_data[base_symbol]

        # Extract label config from v3 training section
        training_section = config.get("training", {})
        labels_config = training_section.get("labels", {})

        # Build v2-compatible label config for create_labels()
        label_config = {
            "zigzag_threshold": labels_config.get("zigzag_threshold", 0.02),
            "label_lookahead": labels_config.get("label_lookahead", 10),
        }

        labels = TrainingPipeline.create_labels(price_data, label_config)

        # Align features and labels (they may have different lengths due to NaN handling)
        min_len = min(len(features), len(labels))
        if min_len == 0:
            raise ValueError(
                "No aligned samples available: features or labels are empty after alignment"
            )
        features_aligned = features[-min_len:]
        labels_aligned = labels[-min_len:]

        logger.info(
            f"V3 features: {features_aligned.shape}, labels: {labels_aligned.shape}"
        )

        # Split data
        data_split = training_section.get("data_split", {})
        train_ratio = data_split.get("train", 0.7)
        val_ratio = data_split.get("validation", 0.15)

        total_samples = len(features_aligned)
        train_end = int(total_samples * train_ratio)
        val_end = int(total_samples * (train_ratio + val_ratio))

        X_train = features_aligned[:train_end]
        y_train = labels_aligned[:train_end]
        X_val = features_aligned[train_end:val_end]
        y_val = labels_aligned[train_end:val_end]
        X_test = features_aligned[val_end:]
        y_test = labels_aligned[val_end:]

        logger.info(
            f"V3 splits: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}"
        )

        # Create model
        model_config = config.get("model", {})
        model = TrainingPipeline.create_model(
            input_dim=features.shape[1],
            output_dim=3,  # Buy, Hold, Sell
            model_config=model_config,
        )

        # Train model
        progress_callback = self._create_progress_callback()
        training_config = model_config.get("training", {})

        training_results = TrainingPipeline.train_model(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            training_config=training_config,
            progress_callback=progress_callback,
            cancellation_token=self._token,
            checkpoint_callback=self._checkpoint_callback,
            resume_context=self._resume_context,
        )

        # Evaluate model
        test_metrics = TrainingPipeline.evaluate_model(model, X_test, y_test)

        # Save model
        model_path = self._model_storage.save_model(
            model=model,
            strategy_name=config.get("name", "v3_strategy"),
            symbol=(
                "MULTI" if len(self._context.symbols) > 1 else self._context.symbols[0]
            ),
            timeframe=self._context.timeframes[0],
            config=config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=None,
            scaler=None,
        )

        logger.info(f"V3 model saved to: {model_path}")

        # CRITICAL: Save v3 metadata with resolved features
        self._save_v3_metadata(
            model_path=Path(model_path),
            config=config,
            resolved_features=resolved_features,
            training_metrics=training_results,
            training_symbols=self._context.symbols,
            training_timeframes=self._context.timeframes,
        )

        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
            "artifacts": {
                "feature_importance": None,
                "per_symbol_metrics": None,
            },
            "model_info": {
                "parameters_count": sum(p.numel() for p in model.parameters()),
                "trainable_parameters": sum(
                    p.numel() for p in model.parameters() if p.requires_grad
                ),
                "architecture": "v3_mlp",
            },
            "data_summary": {
                "symbols": self._context.symbols,
                "timeframes": self._context.timeframes,
                "start_date": self._context.start_date,
                "end_date": self._context.end_date,
                "total_samples": total_samples,
                "feature_count": features_aligned.shape[1],
            },
        }

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

    @staticmethod
    def _is_v3_format(config: dict[str, Any]) -> bool:
        """
        Check if config is v3 format.

        V3 format is identified by:
        - indicators is a dict (not a list)
        - nn_inputs field is present

        Args:
            config: Strategy configuration dictionary

        Returns:
            True if config is v3 format
        """
        return isinstance(config.get("indicators"), dict) and "nn_inputs" in config

    @staticmethod
    def _save_v3_metadata(
        model_path: Path,
        config: dict[str, Any],
        resolved_features: list[str],
        training_metrics: dict[str, Any],
        training_symbols: list[str],
        training_timeframes: list[str],
    ) -> None:
        """
        Save ModelMetadataV3 to the model directory.

        Creates metadata_v3.json with v3-specific information including
        the critical resolved_features list that defines feature order.

        Args:
            model_path: Path to model directory
            config: V3 strategy configuration dict
            resolved_features: Ordered list of feature IDs from FeatureResolver
            training_metrics: Training metrics (loss, accuracy, etc.)
            training_symbols: Symbols used during training
            training_timeframes: Timeframes used during training
        """
        import json
        from pathlib import Path as PathType

        from ktrdr.models.model_metadata import ModelMetadataV3

        # Create metadata
        metadata = ModelMetadataV3(
            model_name=config.get("name", "unknown"),
            strategy_name=config.get("name", "unknown"),
            strategy_version=config.get("version", "3.0"),
            indicators=config.get("indicators", {}),
            fuzzy_sets=config.get("fuzzy_sets", {}),
            nn_inputs=config.get("nn_inputs", []),
            resolved_features=resolved_features,
            training_symbols=training_symbols,
            training_timeframes=training_timeframes,
            training_metrics=training_metrics,
        )

        # Save to model directory
        model_path = PathType(model_path)
        metadata_file = model_path / "metadata_v3.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        logger.info(f"Saved ModelMetadataV3 to {metadata_file}")
