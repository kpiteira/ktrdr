"""
HostTrainingOrchestrator - Coordinate training with host service mechanisms.

This orchestrator uses TrainingPipeline for all work while managing host-specific
coordination (session-based progress, HTTP cancellation).

CRITICAL PERFORMANCE FIX: This orchestrator removes the 14-minute sleep overhead
that was destroying GPU performance by implementing intelligent throttling instead.
"""

import sys
from pathlib import Path
from typing import Any

import torch

# Add parent directory to path for ktrdr imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ktrdr import get_logger
from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.config.feature_resolver import FeatureResolver
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.data.repository import DataRepository
from ktrdr.training.model_storage import ModelStorage
from ktrdr.training.training_pipeline import TrainingPipeline, TrainingPipelineV3

logger = get_logger(__name__)


class SessionCancellationToken(CancellationToken):
    """
    Cancellation token that checks session.stop_requested flag.

    This allows TrainingPipeline to check cancellation without knowing about
    the host service session concept.
    """

    def __init__(self, session):
        """
        Initialize token with session reference.

        Args:
            session: TrainingSession instance
        """
        self._session = session

    def is_cancelled(self) -> bool:
        """
        Check if training should be cancelled.

        Returns:
            True if session.stop_requested is set
        """
        return self._session.stop_requested

    def cancel(self, reason: str = "Operation cancelled") -> None:
        """
        Request cancellation by setting session.stop_requested.

        Args:
            reason: Reason for cancellation (logged but not stored)
        """
        logger.info(
            f"Cancellation requested for session {self._session.session_id}: {reason}"
        )
        self._session.stop_requested = True

    async def wait_for_cancellation(self) -> None:
        """
        Async wait for cancellation signal.

        Note: This is a compatibility method. In host service context,
        cancellation is checked synchronously via is_cancelled().
        """
        import asyncio

        while not self._session.stop_requested:
            await asyncio.sleep(0.1)

    @property
    def is_cancelled_requested(self) -> bool:
        """
        Compatibility property for ServiceOrchestrator integration.

        Returns:
            True if session.stop_requested is set
        """
        return self._session.stop_requested


class HostTrainingOrchestrator:
    """
    Orchestrate host service training using TrainingPipeline.

    Key Differences from LocalTrainingOrchestrator:
    - Direct async execution (no asyncio.to_thread wrapper)
    - Session-based progress updates (not callbacks to bridge)
    - HTTP-based cancellation (session.stop_requested flag)
    - Throttled progress updates for performance (every 10 batches)

    PERFORMANCE OPTIMIZATION:
    - NO SLEEP OPERATIONS ANYWHERE
    - Progress throttling by skipping updates, not sleeping
    - Result: 14 minutes overhead → 8ms (105,000× faster!)
    """

    # Performance tuning constants
    PROGRESS_UPDATE_FREQUENCY = 10  # Update every 10 batches (not every batch)
    CANCELLATION_CHECK_FREQUENCY = 5  # Check every 5 batches

    def __init__(self, session, model_storage: ModelStorage):
        """
        Initialize orchestrator.

        Args:
            session: TrainingSession instance (host service session)
            model_storage: ModelStorage for saving trained models
        """
        self._session = session
        self._model_storage = model_storage

    async def run(self) -> dict[str, Any]:
        """
        Execute training via TrainingPipeline.

        This method loads strategy YAML and calls TrainingPipeline, matching
        LocalTrainingOrchestrator's approach. Runtime overrides are applied on top.

        Returns:
            Training result dict with model_path, metrics, and metadata
        """
        logger.info(
            f"Starting host training orchestrator for session {self._session.session_id}"
        )

        try:
            # Load strategy config from YAML string
            strategy_config = self._load_strategy_config()

            # Extract runtime configuration from session (overrides)
            symbols = self._extract_symbols(strategy_config)
            timeframes = self._extract_timeframes(strategy_config)
            start_date_str, end_date_str = self._extract_date_range()

            logger.info(
                f"Training configuration: {len(symbols)} symbols, {len(timeframes)} timeframes, "
                f"date range: {start_date_str} to {end_date_str}"
            )

            # Create DataRepository instance (cached data only)
            repository = DataRepository()

            # Create session-based cancellation token
            cancellation_token = SessionCancellationToken(self._session)

            # Create bridge-based progress callback that updates BOTH:
            # 1. Bridge's internal state (for OperationsService to pull from)
            # 2. Session progress (for /training/status endpoint)
            # The bridge is callable and receives (epoch, batch, metrics) from TrainingPipeline
            progress_bridge = self._session.progress_bridge
            if progress_bridge is None:
                raise RuntimeError(f"No progress bridge registered for session {self._session.session_id}")

            # Create adapter callback that receives TrainingPipeline callbacks
            # and translates them to bridge method calls
            progress_callback = self._create_bridge_adapter_callback(progress_bridge)

            # Update session status
            self._session.status = "running"
            self._session.message = "Starting training pipeline"

            # CRITICAL: Run training in thread pool to avoid blocking the async event loop
            # Training is CPU-bound synchronous code that takes 18+ seconds.
            # If we call it directly, it blocks the FastAPI event loop and
            # prevents /status endpoint from responding during training.
            import asyncio
            import functools

            # Use get_running_loop() instead of deprecated get_event_loop()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,  # Use default executor (ThreadPoolExecutor)
                functools.partial(
                    self._execute_v3_training,
                    strategy_config=strategy_config,
                    symbols=symbols,
                    timeframes=timeframes,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    repository=repository,
                    progress_callback=progress_callback,
                    cancellation_token=cancellation_token,
                ),
            )

            # Add host metadata
            device_info = self._get_device_info()
            result["resource_usage"] = {
                "gpu_used": device_info["device_type"] != "cpu",
                "gpu_name": device_info.get("device_name"),
                "device_type": device_info["device_type"],
                "training_mode": "host",
            }
            result["session_id"] = self._session.session_id

            # TASK 3.3: Store complete training result in session for harmonization
            # This enables the status endpoint to return the TrainingPipeline result
            # directly, eliminating the need for result_aggregator transformation
            self._session.training_result = result

            # TASK 3.3: Verification logging for result harmonization
            logger.info("=" * 80)
            logger.info("HOST TRAINING RESULT STRUCTURE (before storing)")
            logger.info(f"  Keys: {list(result.keys())}")
            logger.info(f"  model_path: {result.get('model_path')}")
            logger.info(f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}")
            logger.info(f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}")
            logger.info(f"  artifacts keys: {list(result.get('artifacts', {}).keys())}")
            logger.info(f"  resource_usage keys: {list(result.get('resource_usage', {}).keys())}")
            logger.info("=" * 80)

            # Update session status
            self._session.status = "completed"
            self._session.message = "Training completed successfully"

            logger.info(
                f"Host training completed successfully for session {self._session.session_id}"
            )

            return result

        except Exception as e:
            self._session.status = "failed"
            self._session.message = f"Training failed: {str(e)}"
            logger.error(
                f"Host training failed for session {self._session.session_id}: {str(e)}"
            )
            raise

    def _create_bridge_adapter_callback(self, bridge):
        """
        Create callback that updates both bridge state and session progress.

        This adapter receives TrainingPipeline callbacks and:
        1. Calls appropriate bridge methods (updates bridge's internal state for OperationsService)
        2. Updates session progress directly (for /training/status endpoint)

        Args:
            bridge: TrainingProgressBridge instance

        Returns:
            Callback function compatible with TrainingPipeline
        """

        def callback(epoch: int, total_epochs: int, metrics: dict[str, Any]):
            """Handle progress update from TrainingPipeline."""
            progress_type = metrics.get("progress_type")

            # Call bridge method based on progress type
            # Bridge updates its internal state (for OperationsService queries)
            try:
                if progress_type == "indicator_computation":
                    bridge.on_indicator_computation(
                        symbol=metrics.get("symbol", "Unknown"),
                        symbol_index=metrics.get("symbol_index", 1),
                        total_symbols=metrics.get("total_symbols", 1),
                        timeframe=metrics.get("timeframe", "unknown"),
                        indicator_name=metrics.get("indicator_name", "unknown"),
                        indicator_index=metrics.get("indicator_index", 1),
                        total_indicators=metrics.get("total_indicators", 1),
                    )
                elif progress_type == "fuzzy_generation":
                    bridge.on_fuzzy_generation(
                        symbol=metrics.get("symbol", "Unknown"),
                        symbol_index=metrics.get("symbol_index", 1),
                        total_symbols=metrics.get("total_symbols", 1),
                        timeframe=metrics.get("timeframe", "unknown"),
                        fuzzy_set_name=metrics.get("fuzzy_set_name", "unknown"),
                        fuzzy_index=metrics.get("fuzzy_index", 1),
                        total_fuzzy_sets=metrics.get("total_fuzzy_sets", 1),
                    )
                elif progress_type == "preprocessing":
                    bridge.on_symbol_processing(
                        symbol=metrics.get("symbol", "Unknown"),
                        symbol_index=metrics.get("symbol_index", 1),
                        total_symbols=metrics.get("total_symbols", 1),
                        step=metrics.get("step", "processing"),
                        context={
                            k: v
                            for k, v in metrics.items()
                            if k in ("timeframes", "total_indicators", "total_fuzzy_sets")
                        },
                    )
                elif progress_type == "preparation":
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
                    bridge.on_preparation_phase(phase=phase, message=message)
                elif progress_type == "batch":
                    # Let bridge handle throttling via _should_emit_batch()
                    # Always call on_batch() so state updates happen for every batch
                    # (state updates are fast <1μs, bridge decides what to emit)
                    bridge.on_batch(
                        epoch=epoch,
                        batch=metrics.get("batch", 0),
                        total_batches=metrics.get("total_batches_per_epoch"),
                        metrics=metrics,
                    )
                elif progress_type == "epoch":
                    bridge.on_epoch(epoch=epoch, total_epochs=total_epochs, metrics=metrics)
                else:
                    # Phase change or general update
                    message = metrics.get("message") or "Training update"
                    bridge.on_phase(progress_type or "update", message=message)
            except Exception as e:
                logger.warning(f"Error updating bridge: {e}")

            # Also update session directly (for /training/status endpoint)
            # This ensures backward compatibility
            self._session.update_progress(epoch=epoch, batch=metrics.get("batch", 0), metrics=metrics)

        return callback

    def _create_throttled_progress_callback(self):
        """
        Create throttled progress callback - NO SLEEP OPERATIONS!

        Key Performance Optimization:
        - Updates every PROGRESS_UPDATE_FREQUENCY batches (not every batch)
        - Throttles by SKIPPING updates, not sleeping
        - Always updates on epoch completion
        - Result: ~8ms total overhead vs 14 minutes with sleep!

        Returns:
            Callback function that updates session progress
        """

        def callback(epoch: int, total_epochs: int, metrics: dict[str, Any]):
            """
            Progress callback that throttles updates intelligently.

            CRITICAL: NO SLEEP OPERATIONS - throttling by skipping only!
            """
            progress_type = metrics.get("progress_type")

            if progress_type == "indicator_computation":
                # Per-indicator computation progress - update for granular visibility
                symbol = metrics.get("symbol", "Unknown")
                symbol_index = metrics.get("symbol_index", 1)
                total_symbols = metrics.get("total_symbols", 1)
                timeframe = metrics.get("timeframe", "unknown")
                indicator_name = metrics.get("indicator_name", "unknown")
                indicator_index = metrics.get("indicator_index", 1)
                total_indicators = metrics.get("total_indicators", 1)

                # Format message for session progress with visual indicator
                message = (
                    f"📈 Processing {symbol} ({symbol_index}/{total_symbols}) [{timeframe}] - "
                    f"Computing {indicator_name} ({indicator_index}/{total_indicators})"
                )

                logger.info(
                    f"Session {self._session.session_id}: {message}"
                )

                self._session.update_progress(
                    epoch=0,  # Pre-training phase
                    batch=symbol_index,
                    metrics={
                        **metrics,
                        "message": message,
                    },
                )

            elif progress_type == "fuzzy_generation":
                # Per-fuzzy-set generation progress - update for granular visibility
                symbol = metrics.get("symbol", "Unknown")
                symbol_index = metrics.get("symbol_index", 1)
                total_symbols = metrics.get("total_symbols", 1)
                timeframe = metrics.get("timeframe", "unknown")
                fuzzy_set_name = metrics.get("fuzzy_set_name", "unknown")
                fuzzy_index = metrics.get("fuzzy_index", 1)
                total_fuzzy_sets = metrics.get("total_fuzzy_sets", 1)

                # Format message for session progress with visual indicator
                message = (
                    f"🔀 Processing {symbol} ({symbol_index}/{total_symbols}) [{timeframe}] - "
                    f"Fuzzifying {fuzzy_set_name} ({fuzzy_index}/{total_fuzzy_sets})"
                )

                logger.info(
                    f"Session {self._session.session_id}: {message}"
                )

                self._session.update_progress(
                    epoch=0,  # Pre-training phase
                    batch=symbol_index,
                    metrics={
                        **metrics,
                        "message": message,
                    },
                )

            elif progress_type == "preprocessing":
                # Symbol-level preprocessing progress - always update for visibility
                symbol = metrics.get("symbol", "Unknown")
                symbol_index = metrics.get("symbol_index", 1)
                total_symbols = metrics.get("total_symbols", 1)
                step = metrics.get("step", "processing")

                # Format message with visual indicators matching TrainingProgressRenderer
                step_emoji = "📊"  # Default
                if step == "loading_data":
                    step_emoji = "📊"
                elif step == "computing_indicators" or step == "computing_indicator":
                    step_emoji = "📈"
                elif step == "generating_fuzzy":
                    step_emoji = "🔀"
                elif step == "creating_features":
                    step_emoji = "🔧"
                elif step == "generating_labels":
                    step_emoji = "🏷️"

                # Format base message
                step_name = step.replace('_', ' ').title()
                base_message = f"{step_emoji} Processing {symbol} ({symbol_index}/{total_symbols}) - {step_name}"

                # Add total counts to message if available
                if step == "computing_indicators" and "total_indicators" in metrics:
                    message = f"📈 Processing {symbol} ({symbol_index}/{total_symbols}) - Computing Indicators ({metrics['total_indicators']})"
                elif step == "generating_fuzzy" and "total_fuzzy_sets" in metrics:
                    message = f"🔀 Processing {symbol} ({symbol_index}/{total_symbols}) - Computing Fuzzy Memberships ({metrics['total_fuzzy_sets']})"
                else:
                    message = base_message

                logger.info(
                    f"Session {self._session.session_id}: {message}"
                )

                self._session.update_progress(
                    epoch=0,  # Pre-training phase
                    batch=symbol_index,
                    metrics={
                        **metrics,
                        "message": message,
                    },
                )

            elif progress_type == "preparation":
                # Preparation phase progress (combining data, splitting, creating model)
                phase = metrics.get("phase", "preparing")

                if phase == "combining_data":
                    total_symbols = metrics.get("total_symbols", 0)
                    message = f"⚙️ Combining data from {total_symbols} symbol(s)"
                elif phase == "splitting_data":
                    total_samples = metrics.get("total_samples", 0)
                    message = f"⚙️ Splitting {total_samples} samples (train/val/test)"
                elif phase == "creating_model":
                    input_dim = metrics.get("input_dim", 0)
                    message = f"⚙️ Creating model (input_dim={input_dim})"
                else:
                    message = f"⚙️ {phase.replace('_', ' ').title()}"

                logger.info(
                    f"Session {self._session.session_id}: {message}"
                )

                self._session.update_progress(
                    epoch=0,  # Pre-training phase
                    batch=0,
                    metrics={
                        **metrics,
                        "message": message,
                    },
                )

            elif progress_type == "batch":
                # Update session for every batch (backward compatibility)
                # Session has its own state management, no need to throttle
                batch = metrics.get("batch", 0)
                self._session.update_progress(
                    epoch=epoch,
                    batch=batch,
                    metrics=metrics,
                )

            elif progress_type == "epoch":
                # Always update on epoch completion
                logger.info(
                    f"Session {self._session.session_id}: Completed epoch {epoch}/{total_epochs} - "
                    f"train_loss: {metrics.get('train_loss', 'N/A'):.4f}, "
                    f"val_loss: {metrics.get('val_loss', 'N/A'):.4f}"
                )
                self._session.update_progress(
                    epoch=epoch,
                    batch=0,
                    metrics=metrics,
                )

        return callback

    def _load_strategy_config(self) -> dict[str, Any]:
        """
        Load and parse strategy configuration from YAML string.

        Returns:
            Parsed strategy configuration dict
        """
        import yaml

        strategy_yaml = self._session.config.get("strategy_yaml")
        if not strategy_yaml:
            raise ValueError("No strategy_yaml provided in session config")

        return yaml.safe_load(strategy_yaml)

    def _extract_symbols(self, strategy_config: dict[str, Any]) -> list[str]:
        """
        Extract symbols with runtime override support.

        Args:
            strategy_config: Parsed strategy configuration

        Returns:
            List of symbols to train on
        """
        # Runtime override takes precedence
        override_symbols = self._session.config.get("symbols")
        if override_symbols:
            return (
                override_symbols
                if isinstance(override_symbols, list)
                else [override_symbols]
            )

        # Extract from strategy YAML
        training_data = strategy_config.get("training_data", {})
        symbols_config = training_data.get("symbols", {})

        if isinstance(symbols_config, dict):
            return symbols_config.get("list", ["AAPL"])
        elif isinstance(symbols_config, list):
            return symbols_config
        else:
            return ["AAPL"]

    def _extract_timeframes(self, strategy_config: dict[str, Any]) -> list[str]:
        """
        Extract timeframes with runtime override support.

        Args:
            strategy_config: Parsed strategy configuration

        Returns:
            List of timeframes to use
        """
        # Runtime override takes precedence
        override_timeframes = self._session.config.get("timeframes")
        if override_timeframes:
            return (
                override_timeframes
                if isinstance(override_timeframes, list)
                else [override_timeframes]
            )

        # Extract from strategy YAML
        training_data = strategy_config.get("training_data", {})
        timeframes_config = training_data.get("timeframes", {})

        if isinstance(timeframes_config, dict):
            return timeframes_config.get("list", ["1d"])
        elif isinstance(timeframes_config, list):
            return timeframes_config
        else:
            return ["1d"]

    def _extract_date_range(self) -> tuple[str, str]:
        """
        Extract date range with fallback to 1 year.

        Returns:
            Tuple of (start_date, end_date) as strings
        """
        from datetime import UTC, datetime, timedelta

        # Runtime overrides
        start_date = self._session.config.get("start_date")
        end_date = self._session.config.get("end_date")

        # Fallback to 1 year if not provided
        if not start_date or not end_date:
            end_date_dt = datetime.now(UTC)
            start_date_dt = end_date_dt - timedelta(days=365)
            start_date = start_date_dt.strftime("%Y-%m-%d")
            end_date = end_date_dt.strftime("%Y-%m-%d")
            logger.warning(
                f"No date range provided, using default: {start_date} to {end_date}"
            )

        return start_date, end_date

    def _get_device_info(self) -> dict[str, Any]:
        """
        Get device information for metadata.

        Returns:
            Dict with device_type, device_name, and capabilities
        """
        device_info = {
            "device_type": "cpu",
            "device_name": "CPU",
        }

        if torch.cuda.is_available():
            device_info["device_type"] = "cuda"
            device_info["device_name"] = torch.cuda.get_device_name(0)
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device_info["device_type"] = "mps"
            device_info["device_name"] = "Apple MPS"

        return device_info

    def _execute_v3_training(
        self,
        strategy_config: dict[str, Any],
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        repository: DataRepository,
        progress_callback,
        cancellation_token,
    ) -> dict[str, Any]:
        """
        Execute v3 training using TrainingPipelineV3.

        This follows the same pattern as LocalTrainingOrchestrator._execute_v3_training(),
        using step-by-step pipeline calls instead of a single train_strategy() method.

        Args:
            strategy_config: Parsed strategy YAML configuration
            symbols: List of symbols to train on
            timeframes: List of timeframes to use
            start_date: Training start date
            end_date: Training end date
            repository: DataRepository for loading market data
            progress_callback: Callback for progress updates
            cancellation_token: Token for cancellation checking

        Returns:
            Training result dictionary with model_path, metrics, etc.
        """
        import tempfile

        import numpy as np
        import yaml

        logger.info("Starting v3 training pipeline execution")

        # Write strategy config to temp file for loader (it expects a file path)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(strategy_config, f)
            strategy_path = f.name

        try:
            # Load as typed v3 config
            loader = StrategyConfigurationLoader()
            v3_config = loader.load_v3_strategy(strategy_path)

            # Resolve features to get canonical order
            resolver = FeatureResolver()
            resolved = resolver.resolve(v3_config)
            resolved_features = [f.feature_id for f in resolved]

            logger.info(f"V3 training: {len(resolved_features)} resolved features")

            # Create v3 pipeline
            pipeline = TrainingPipelineV3(v3_config)

            # Load market data for all symbols
            all_data: dict[str, dict[str, Any]] = {}
            for i, symbol in enumerate(symbols, 1):
                if progress_callback:
                    progress_callback(0, 0, {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": i,
                        "total_symbols": len(symbols),
                        "step": "loading_data",
                    })

                symbol_data = TrainingPipeline.load_market_data(
                    symbol=symbol,
                    timeframes=timeframes,
                    start_date=start_date,
                    end_date=end_date,
                    repository=repository,
                )
                all_data[symbol] = symbol_data

            # Check cancellation
            if cancellation_token and cancellation_token.is_cancelled():
                raise RuntimeError("Training cancelled")

            # Prepare features using v3 pipeline
            logger.info("Preparing features with TrainingPipelineV3...")
            if progress_callback:
                progress_callback(0, 0, {
                    "progress_type": "preparation",
                    "phase": "preparing_features",
                })
            features_df = pipeline.prepare_features(all_data)

            # Handle NaN values before converting to tensor
            features_array = features_df.values
            nan_count = np.isnan(features_array).sum()
            if nan_count > 0:
                logger.warning(f"Replacing {nan_count} NaN values in features with 0.0")
                features_array = np.nan_to_num(features_array, nan=0.0)

            features = torch.FloatTensor(features_array)
            feature_names = list(features_df.columns)

            # Generate labels from price data (use first symbol's base timeframe)
            base_symbol = symbols[0]
            price_data = all_data[base_symbol]

            # Extract training section and label config from v3 config
            training_section = strategy_config.get("training", {})
            labels_config = training_section.get("labels", {})

            # Build v2-compatible label config for create_labels()
            label_config = {
                "zigzag_threshold": labels_config.get("zigzag_threshold", 0.02),
                "label_lookahead": labels_config.get("label_lookahead", 10),
            }

            labels = TrainingPipeline.create_labels(price_data, label_config)

            # Align features and labels
            min_len = min(len(features), len(labels))
            if min_len == 0:
                raise ValueError(
                    f"No aligned samples: features={len(features)}, labels={len(labels)}"
                )
            features_aligned = features[-min_len:]
            labels_aligned = labels[-min_len:]

            logger.info(f"V3 features: {features_aligned.shape}, labels: {labels_aligned.shape}")

            # Split data
            if progress_callback:
                progress_callback(0, 0, {
                    "progress_type": "preparation",
                    "phase": "splitting_data",
                    "total_samples": len(features_aligned),
                })

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

            logger.info(f"V3 splits: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

            # Create model
            if progress_callback:
                progress_callback(0, 0, {
                    "progress_type": "preparation",
                    "phase": "creating_model",
                    "input_dim": features.shape[1],
                })

            model_config = strategy_config.get("model", {})
            model = TrainingPipeline.create_model(
                input_dim=features.shape[1],
                output_dim=3,  # Buy, Hold, Sell
                model_config=model_config,
            )

            # Train model
            training_config = model_config.get("training", {})
            training_results = TrainingPipeline.train_model(
                model=model,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                training_config=training_config,
                progress_callback=progress_callback,
                cancellation_token=cancellation_token,
            )

            # Evaluate model
            test_metrics = TrainingPipeline.evaluate_model(
                model=model,
                X_test=X_test,
                y_test=y_test,
            )

            # Save model
            strategy_name = strategy_config.get("name", "unnamed")
            base_timeframe = timeframes[0] if timeframes else "1h"
            model_path = self._model_storage.save_model(
                strategy_name=strategy_name,
                timeframe=base_timeframe,
                model=model,
                metadata={
                    "feature_names": feature_names,
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "training_config": training_config,
                },
            )

            logger.info(f"Model saved to: {model_path}")

            # Build result
            result = {
                "model_path": str(model_path),
                "model_info": {
                    "architecture": model_config.get("architecture", "v3_mlp"),
                    "parameters_count": sum(p.numel() for p in model.parameters()),
                    "trainable_parameters": sum(
                        p.numel() for p in model.parameters() if p.requires_grad
                    ),
                },
                "training_metrics": training_results.get("training_metrics", {}),
                "test_metrics": test_metrics,
                "data_summary": {
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_samples": total_samples,
                    "feature_count": len(feature_names),
                },
                "artifacts": {
                    "feature_importance": None,
                    "per_symbol_metrics": None,
                },
            }

            return result

        finally:
            # Clean up temp file
            import os
            try:
                os.unlink(strategy_path)
            except Exception:
                pass
