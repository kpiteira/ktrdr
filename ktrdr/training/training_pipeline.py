"""
Training Pipeline - Pure training work functions.

This module contains pure functions for training operations, EXTRACTED from
both local (StrategyTrainer) and host (TrainingService) training paths to
eliminate code duplication.

Design Philosophy:
- NO callbacks, NO async - pure synchronous functions
- Orchestrators wrap these functions for progress reporting and cancellation
- Each function is stateless and testable in isolation
- Code is EXTRACTED from existing implementations, not rewritten
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
)

from ktrdr import get_logger
from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.data.data_manager import DataManager
from ktrdr.data.multi_timeframe_coordinator import MultiTimeframeCoordinator
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.indicators.indicator_engine import IndicatorEngine

# BUILT_IN_INDICATORS import removed - no longer needed (IndicatorEngine handles it)
from ktrdr.neural.models.mlp import MLPTradingModel
from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
from ktrdr.training.model_trainer import ModelTrainer
from ktrdr.training.zigzag_labeler import ZigZagLabeler

logger = get_logger(__name__)


class TrainingPipeline:
    """
    Pure training work functions - no callbacks, no async.

    This class provides stateless, synchronous methods for:
    - Data loading and validation
    - Feature engineering (indicators, fuzzy memberships)
    - Model creation and training
    - Model evaluation

    Orchestrators (LocalTrainingOrchestrator, HostTrainingOrchestrator) wrap
    these methods differently for their execution environments.
    """

    # ======================================================================
    # DATA LOADING METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer::_load_price_data
    # ======================================================================

    @staticmethod
    def load_market_data(
        symbol: str,
        timeframes: list[str],
        start_date: str,
        end_date: str,
        data_mode: str = "local",
        data_manager: Optional[DataManager] = None,
        multi_timeframe_coordinator: Optional[MultiTimeframeCoordinator] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Load price data for training with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._load_price_data() (train_strategy.py:563-622)

        This is the EXACT logic from the existing implementation, just extracted
        into a standalone function.

        Args:
            symbol: Trading symbol
            timeframes: List of timeframes for multi-timeframe training
            start_date: Start date
            end_date: End date
            data_mode: Data loading mode ('local', 'tail', 'backfill', 'full')
            data_manager: Optional DataManager instance (will create if not provided)
            multi_timeframe_coordinator: Optional coordinator (will create if not provided)

        Returns:
            Dictionary mapping timeframes to OHLCV DataFrames

        Raises:
            ValueError: If no timeframes successfully loaded
        """
        # Initialize components if not provided
        if data_manager is None:
            data_manager = DataManager()

        if multi_timeframe_coordinator is None:
            multi_timeframe_coordinator = MultiTimeframeCoordinator(data_manager)

        # Handle single timeframe case (backward compatibility)
        # EXTRACTED FROM: train_strategy.py:584-592
        if len(timeframes) == 1:
            timeframe = timeframes[0]
            # Pass dates to DataManager for efficient filtering
            data = data_manager.load_data(
                symbol,
                timeframe,
                start_date=start_date,
                end_date=end_date,
                mode=data_mode,
            )

            return {timeframe: data}

        # Multi-timeframe case - use first timeframe (highest frequency) as base
        # EXTRACTED FROM: train_strategy.py:594-622
        base_timeframe = timeframes[0]  # Always use first timeframe as base
        multi_data = multi_timeframe_coordinator.load_multi_timeframe_data(
            symbol=symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            base_timeframe=base_timeframe,
            mode=data_mode,
        )

        # Validate multi-timeframe loading success
        if len(multi_data) != len(timeframes):
            available_tfs = list(multi_data.keys())
            missing_tfs = set(timeframes) - set(available_tfs)
            logger.warning(
                f"⚠️ Multi-timeframe loading partial success: {len(multi_data)}/{len(timeframes)} timeframes loaded. "
                f"Missing: {missing_tfs}, Available: {available_tfs}"
            )

            # Continue with available timeframes but warn user
            if len(multi_data) == 0:
                raise ValueError(f"No timeframes successfully loaded for {symbol}")
        else:
            logger.info(
                f"✅ Multi-timeframe data loaded successfully: {', '.join(multi_data.keys())}"
            )

        return multi_data

    # _filter_data_by_date_range() method removed
    # Date filtering now handled by DataManager.load_data() which is more efficient
    # and provides consistent behavior across local and host execution paths

    @staticmethod
    def validate_data_quality(
        data: dict[str, pd.DataFrame], min_rows: int = 100
    ) -> dict[str, Any]:
        """
        Validate that loaded data has sufficient quality for training.

        This is a NEW method (not extracted) that provides basic validation
        to catch common data issues early.

        Args:
            data: Dictionary mapping timeframes to DataFrames
            min_rows: Minimum required number of rows per timeframe

        Returns:
            dict: Validation results containing:
                - valid (bool): Whether all timeframes pass validation
                - timeframes_checked (int): Number of timeframes checked
                - issues (list): List of validation issues found
                - total_rows (int): Total rows across all timeframes
        """
        result: dict[str, Any] = {
            "valid": True,
            "timeframes_checked": len(data),
            "issues": [],
            "total_rows": 0,
        }

        required_columns = ["open", "high", "low", "close", "volume"]

        for timeframe, df in data.items():
            result["total_rows"] += len(df)

            # Check row count
            if len(df) < min_rows:
                result["valid"] = False
                result["issues"].append(
                    f"{timeframe}: Only {len(df)} rows (< {min_rows} required)"
                )

            # Check required columns
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                result["valid"] = False
                result["issues"].append(f"{timeframe}: Missing columns {missing_cols}")

            # Check for excessive NaN values (only if columns exist)
            if not df.empty and not missing_cols:
                nan_pct = (
                    df[required_columns].isnull().sum().sum()
                    / (len(df) * len(required_columns))
                ) * 100
                if nan_pct > 5.0:  # More than 5% NaN is problematic
                    result["valid"] = False
                    result["issues"].append(
                        f"{timeframe}: {nan_pct:.1f}% missing values (> 5% threshold)"
                    )

        if result["valid"]:
            logger.info(
                f"Data validation passed: {result['timeframes_checked']} timeframes, "
                f"{result['total_rows']} total rows"
            )
        else:
            logger.warning(
                f"Data validation failed with {len(result['issues'])} issues: "
                f"{result['issues']}"
            )

        return result

    # ======================================================================
    # FEATURE ENGINEERING METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def calculate_indicators(
        price_data: dict[str, pd.DataFrame],
        indicator_configs: list[dict[str, Any]],
        progress_callback=None,
        symbol: str | None = None,
        symbol_index: int | None = None,
        total_symbols: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate technical indicators (unified single/multi-timeframe approach).

        Single-timeframe is just multi-timeframe with one key. This eliminates
        code duplication and ensures consistent behavior.

        ROOT CAUSE FIX: Creates IndicatorEngine ONCE and uses apply_multi_timeframe()
        without passing indicator_configs parameter, preventing duplicate engine creation.

        Args:
            price_data: Dictionary mapping timeframes to OHLCV DataFrames
            indicator_configs: List of indicator configurations
            progress_callback: Optional callback for progress reporting
            symbol: Optional symbol being processed (for progress reporting)
            symbol_index: Optional symbol index (for progress reporting)
            total_symbols: Optional total symbols count (for progress reporting)

        Returns:
            Dictionary mapping timeframes to DataFrames with indicators
        """
        logger.info(
            f"🔧 TrainingPipeline.calculate_indicators() - Processing {len(price_data)} timeframe(s) "
            f"with {len(indicator_configs)} indicator(s)"
        )

        # Create indicator engine ONCE - No computation on sample data (Phase 7)!
        indicator_engine = IndicatorEngine(indicators=indicator_configs)

        # Apply to all timeframes (single-timeframe is just a 1-item dict)
        # CRITICAL: Don't pass indicator_configs to prevent duplicate engine creation!
        indicator_results = indicator_engine.apply_multi_timeframe(
            price_data,
            progress_callback=progress_callback,
            symbol=symbol,
            symbol_index=symbol_index,
            total_symbols=total_symbols,
        )

        # Combine price data with indicator results per timeframe
        combined_results = {}

        for timeframe, tf_indicators in indicator_results.items():
            tf_price_data = price_data[timeframe]

            # Phase 3 simplified: Just combine - feature_id aliases already exist!
            result = tf_price_data.copy()
            for col in tf_indicators.columns:
                if col not in result.columns:
                    result[col] = tf_indicators[col]

            # Safety check: replace any inf values with NaN, then fill NaN with 0
            result = result.replace([np.inf, -np.inf], np.nan).fillna(0.0)

            combined_results[timeframe] = result

        return combined_results

    @staticmethod
    def generate_fuzzy_memberships(
        indicators: dict[str, pd.DataFrame], fuzzy_configs: dict[str, Any]
    ) -> dict[str, pd.DataFrame]:
        """
        Generate fuzzy membership values (unified single/multi-timeframe approach).

        Single-timeframe is just multi-timeframe with one key. This eliminates
        code duplication and ensures consistent behavior.

        ROOT CAUSE FIX: Multi-timeframe method now passes context_data to fuzzify(),
        fixing price_ratio transform errors.

        Args:
            indicators: Dictionary mapping timeframes to technical indicators DataFrames
            fuzzy_configs: Fuzzy set configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with fuzzy membership values
        """
        logger.info(
            f"🔧 TrainingPipeline.generate_fuzzy_memberships() - Processing {len(indicators)} timeframe(s) "
            f"with {len(fuzzy_configs)} fuzzy indicator(s)"
        )

        # Initialize fuzzy engine
        fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_configs)
        fuzzy_engine = FuzzyEngine(fuzzy_config)

        # Always use multi-timeframe method (single-timeframe is just a 1-item dict)
        # The fuzzy engine now passes context_data in multi-timeframe path!
        return fuzzy_engine.generate_multi_timeframe_memberships(
            indicators, fuzzy_configs
        )

    @staticmethod
    def create_features(
        fuzzy_data: dict[str, pd.DataFrame], feature_config: dict[str, Any]
    ) -> tuple[torch.Tensor, list[str]]:
        """
        Engineer features for neural network training using pure fuzzy approach.

        EXTRACTED FROM: StrategyTrainer._engineer_features()
        (train_strategy.py:849-878)

        Args:
            fuzzy_data: Dictionary mapping timeframes to fuzzy membership values
            feature_config: Feature engineering configuration

        Returns:
            Tuple of (features tensor, feature names list)
        """
        logger.info(
            f"🔧 TrainingPipeline.create_features() - Creating features from {len(fuzzy_data)} timeframe(s)"
        )

        # Pure neuro-fuzzy architecture: only fuzzy memberships as inputs
        processor = FuzzyNeuralProcessor(feature_config)

        # Handle single timeframe case (backward compatibility)
        if len(fuzzy_data) == 1:
            timeframe, tf_fuzzy_data = next(iter(fuzzy_data.items()))
            features, feature_names = processor.prepare_input(tf_fuzzy_data)
            logger.info(
                f"✅ Created {features.shape[1]} features from {features.shape[0]} samples"
            )
            return features, feature_names

        # Multi-timeframe case - use the new multi-timeframe method
        features, feature_names = processor.prepare_multi_timeframe_input(fuzzy_data)
        logger.info(
            f"✅ Created {features.shape[1]} features from {features.shape[0]} samples (multi-timeframe)"
        )
        return features, feature_names

    @staticmethod
    def create_labels(
        price_data: dict[str, pd.DataFrame], label_config: dict[str, Any]
    ) -> torch.Tensor:
        """
        Generate training labels using ZigZag method with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._generate_labels()
        (train_strategy.py:880-923)

        Args:
            price_data: Dictionary mapping timeframes to OHLCV data
            label_config: Label generation configuration

        Returns:
            Tensor of labels
        """
        logger.info(
            f"🔧 TrainingPipeline.create_labels() - Generating labels from {len(price_data)} timeframe(s) "
            f"(threshold={label_config.get('zigzag_threshold', 'N/A')}, "
            f"lookahead={label_config.get('label_lookahead', 'N/A')})"
        )

        # CRITICAL: For multi-timeframe, MUST use the same base timeframe as features
        # Features are generated from timeframes[0], so labels must also use timeframes[0]
        # This ensures tensor size consistency (same number of samples)
        if len(price_data) == 1:
            # Single timeframe case
            timeframe, tf_price_data = next(iter(price_data.items()))
            logger.debug(f"Generating labels from {timeframe} data")
        else:
            # Multi-timeframe case - use SAME base timeframe as features (highest frequency)
            # Features use frequency-based ordering, so we must match that
            timeframe_list = sorted(price_data.keys())
            # Convert to frequency-based order (highest frequency first)
            frequency_order = TrainingPipeline._sort_timeframes_by_frequency(
                timeframe_list
            )
            base_timeframe = frequency_order[
                0
            ]  # Use highest frequency (same as features)
            tf_price_data = price_data[base_timeframe]
            logger.debug(
                f"Generating labels from base timeframe {base_timeframe} "
                f"(out of {frequency_order}) - matching features"
            )

        labeler = ZigZagLabeler(
            threshold=label_config["zigzag_threshold"],
            lookahead=label_config["label_lookahead"],
        )

        # Use segment-based labeling for better class balance
        logger.debug(
            "Using ZigZag segment labeling (balanced) instead of sparse extreme labeling..."
        )
        labels = labeler.generate_segment_labels(tf_price_data)
        label_tensor = torch.LongTensor(labels.values)

        # Log label distribution
        unique, counts = torch.unique(label_tensor, return_counts=True)
        dist = {int(u): int(c) for u, c in zip(unique, counts)}
        logger.info(f"✅ Generated {len(label_tensor)} labels - Distribution: {dist}")

        return label_tensor

    @staticmethod
    def _sort_timeframes_by_frequency(timeframes: list[str]) -> list[str]:
        """
        Sort timeframes by frequency (highest frequency first).

        Helper method for multi-timeframe label generation.
        """
        # Timeframe frequency mapping (in minutes)
        # Note: Normalized to lowercase for case-insensitive lookup
        frequency_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,  # Daily
            "1w": 10080,  # Weekly
        }

        # Default to daily frequency (1440 minutes) for unknown timeframes
        DEFAULT_TIMEFRAME_MINUTES = 1440

        # Sort by frequency (lower minutes = higher frequency)
        # Normalize to lowercase for case-insensitive comparison
        return sorted(
            timeframes,
            key=lambda tf: frequency_map.get(tf.lower(), DEFAULT_TIMEFRAME_MINUTES),
        )

    # ======================================================================
    # MODEL METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def create_model(
        input_dim: int,
        output_dim: int,
        model_config: dict[str, Any],
    ) -> nn.Module:
        """
        Create neural network model.

        EXTRACTED FROM: StrategyTrainer._create_model() (train_strategy.py:921-940)

        Args:
            input_dim: Number of input features
            output_dim: Number of output classes
            model_config: Model configuration dict containing:
                - type: Model type (default: "mlp")
                - hidden_layers: List of hidden layer sizes
                - dropout: Dropout rate
                - num_classes: Number of output classes

        Returns:
            Neural network module ready for training

        Raises:
            ValueError: If model type is not supported
        """
        logger.info(
            f"🔧 TrainingPipeline.create_model() - Creating model with "
            f"input_dim={input_dim}, output_dim={output_dim}"
        )

        model_type = model_config.get("type", "mlp").lower()

        if model_type == "mlp":
            # Create MLPTradingModel and build the model
            mlp_model = MLPTradingModel(model_config)
            model = mlp_model.build_model(input_dim)
            logger.info(
                f"✅ Created MLP model with hidden_layers={model_config.get('hidden_layers', [])}"
            )
            return model
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    @staticmethod
    def train_model(
        model: nn.Module,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        training_config: dict[str, Any],
        progress_callback=None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> dict[str, Any]:
        """
        Train the neural network model (symbol-agnostic).

        EXTRACTED FROM: StrategyTrainer._train_model() (train_strategy.py:942-1019)

        This is a SYNCHRONOUS method with no async operations. Orchestrators
        wrap this method differently for their execution environments.

        SYMBOL-AGNOSTIC DESIGN: This method treats all input data the same way,
        regardless of how many symbols contributed to it. Features from 1 symbol
        or 10 symbols are handled identically - the model learns patterns in
        technical indicators and fuzzy memberships, not symbol identities.

        Args:
            model: Neural network model to train
            X_train: Training features (concatenated from all symbols)
            y_train: Training labels (concatenated from all symbols)
            X_val: Validation features (concatenated from all symbols)
            y_val: Validation labels (concatenated from all symbols)
            training_config: Training configuration dict containing:
                - epochs: Number of training epochs
                - batch_size: Batch size
                - learning_rate: Learning rate
            progress_callback: Optional callback(epoch, total_epochs, metrics)
            cancellation_token: Optional cancellation token

        Returns:
            Training results dict containing:
                - train_loss: Final training loss
                - val_loss: Final validation loss
                - train_accuracy: Final training accuracy
                - val_accuracy: Final validation accuracy
                - epochs_completed: Number of epochs completed
                - training_history: History of metrics per epoch
        """
        logger.info(
            f"🔧 TrainingPipeline.train_model() - Training model "
            f"(epochs={training_config.get('epochs', 'N/A')}, "
            f"batch_size={training_config.get('batch_size', 'N/A')})"
        )

        # Create trainer instance
        trainer = ModelTrainer(
            training_config,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )

        # Symbol-agnostic training: Always use the same path regardless of number of symbols
        # The model doesn't care if features came from 1 symbol or 10 - it just sees
        # technical indicators and fuzzy memberships concatenated together.
        logger.debug(f"Symbol-agnostic training with {len(X_train)} samples")
        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )

        # Use the actual keys returned by ModelTrainer
        train_loss = result.get("final_train_loss", None)
        val_loss = result.get("final_val_loss", None)
        if train_loss is not None and val_loss is not None:
            logger.info(
                f"✅ Training complete - "
                f"Final train_loss={train_loss:.4f}, "
                f"val_loss={val_loss:.4f}"
            )
        else:
            logger.info(
                f"✅ Training complete - "
                f"Final train_loss={train_loss}, "
                f"val_loss={val_loss}"
            )

        return result

    @staticmethod
    def evaluate_model(
        model: nn.Module,
        X_test: Optional[torch.Tensor],
        y_test: Optional[torch.Tensor],
        symbol_indices_test: Optional[torch.Tensor] = None,
    ) -> dict[str, Any]:
        """
        Evaluate model on test set.

        EXTRACTED FROM: StrategyTrainer._evaluate_model() (train_strategy.py:1021-1080)

        Args:
            model: Trained model
            X_test: Test features (None for no test data)
            y_test: Test labels (None for no test data)
            symbol_indices_test: Optional symbol indices for multi-symbol evaluation

        Returns:
            Test metrics dict containing:
                - test_accuracy: Test set accuracy
                - test_loss: Test set loss
                - precision: Weighted precision score
                - recall: Weighted recall score
                - f1_score: Weighted F1 score
        """
        logger.info(
            "🔧 TrainingPipeline.evaluate_model() - Evaluating model on test set"
        )

        # Handle no test data case
        if X_test is None or y_test is None:
            logger.warning("No test data provided - returning zero metrics")
            return {
                "test_accuracy": 0.0,
                "test_loss": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
            }

        # Move test data to the same device as the model
        device = next(model.parameters()).device
        X_test = X_test.to(device)
        y_test = y_test.to(device)

        model.eval()
        with torch.no_grad():
            outputs = model(X_test)

            # Calculate accuracy
            _, predicted = torch.max(outputs, 1)
            accuracy = (predicted == y_test).float().mean().item()

            # Calculate loss
            criterion = nn.CrossEntropyLoss()
            loss = criterion(outputs, y_test).item()

            # Convert tensors to numpy for sklearn metrics
            y_true = y_test.cpu().numpy()
            y_pred = predicted.cpu().numpy()

            # Calculate precision, recall, and f1_score using weighted average
            # This handles multi-class classification properly
            precision = precision_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
            recall = recall_score(y_true, y_pred, average="weighted", zero_division=0)
            f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

        logger.info(
            f"✅ Evaluation complete - "
            f"test_accuracy={accuracy:.4f}, test_loss={loss:.4f}, "
            f"precision={precision:.4f}, recall={recall:.4f}, f1_score={f1:.4f}"
        )

        return {
            "test_accuracy": accuracy,
            "test_loss": loss,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

    # ======================================================================
    # MULTI-SYMBOL METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def combine_multi_symbol_data(
        all_symbols_features: dict[str, torch.Tensor],
        all_symbols_labels: dict[str, torch.Tensor],
        symbols: list[str],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Combine features and labels from multiple symbols sequentially, preserving temporal order.

        DESIGN PRINCIPLE: Strategies are symbol-agnostic. A trading strategy operates on
        patterns in technical indicators and price action, not on symbol names. The model
        learns "when RSI is oversold AND MACD crosses up, buy" - this pattern is universal
        across all symbols.

        TEMPORAL PRESERVATION: Concatenates data sequentially (AAPL all → MSFT all → TSLA all)
        to preserve time series order within each symbol. This is critical for learning
        temporal patterns.

        INDICATOR RESETS: Caller must reset indicator state (moving averages, etc.) at
        symbol boundaries since each symbol's data is a separate time series. Concatenating
        AAPL's last day with MSFT's first day doesn't represent continuous time.

        NO DATA LOSS: Uses ALL data from all symbols - no sampling, no random selection.

        Args:
            all_symbols_features: Dict mapping symbol to features tensor
            all_symbols_labels: Dict mapping symbol to labels tensor
            symbols: List of symbol names in order

        Returns:
            Tuple of (combined_features, combined_labels)
            Note: No symbol_indices returned - strategies are symbol-agnostic
        """
        combined_features_list = []
        combined_labels_list = []

        for symbol in symbols:
            # Concatenate sequentially - preserves temporal order
            combined_features_list.append(all_symbols_features[symbol])
            combined_labels_list.append(all_symbols_labels[symbol])

        # Concatenate all symbols (AAPL all data, then MSFT all data, etc.)
        combined_features = torch.cat(combined_features_list, dim=0)
        combined_labels = torch.cat(combined_labels_list, dim=0)

        # NO SHUFFLE - temporal order is critical for time series
        # NO SYMBOL_INDICES - strategies don't care about symbol names
        return combined_features, combined_labels

    # ======================================================================
    # HIGH-LEVEL ORCHESTRATION METHOD
    # ======================================================================

    @staticmethod
    def train_strategy(
        symbols: list[str],
        timeframes: list[str],
        strategy_config: dict[str, Any],
        start_date: str,
        end_date: str,
        model_storage,  # ModelStorage instance
        data_mode: str = "local",
        progress_callback=None,
        cancellation_token: Optional[CancellationToken] = None,
        data_manager: Optional[DataManager] = None,
    ) -> dict[str, Any]:
        """
        Complete training pipeline from data to trained model.

        Orchestrates all steps: load data → indicators → fuzzy → features →
        labels → train → evaluate → save. Returns standardized result.

        Key: progress_callback and cancellation_token are PASSED THROUGH
        to train_model(), not handled here. This avoids the trap of trying
        to unify progress/cancellation mechanisms.

        Args:
            symbols: Trading symbols to train on
            timeframes: Timeframes for multi-timeframe training
            strategy_config: Complete strategy configuration
            start_date: Start date for training data
            end_date: End date for training data
            model_storage: ModelStorage instance for saving
            data_mode: Data loading mode ('local', 'tail', 'backfill')
            progress_callback: Optional progress callback (orchestrator-provided)
            cancellation_token: Optional cancellation token (orchestrator-provided)
            data_manager: Optional DataManager instance

        Returns:
            Standardized result dict with model_path, metrics, artifacts
        """
        logger.info(
            f"🚀 TrainingPipeline.train_strategy() - Starting training for {len(symbols)} symbol(s): {symbols}"
        )
        logger.info(f"   Timeframes: {timeframes}, Mode: {data_mode}")

        # Initialize components if needed
        if data_manager is None:
            from ktrdr.data.data_manager import DataManager as DM

            data_manager = DM()

        multi_timeframe_coordinator = None
        if len(timeframes) > 1:
            from ktrdr.data.multi_timeframe_coordinator import (
                MultiTimeframeCoordinator as MTC,
            )

            multi_timeframe_coordinator = MTC(data_manager)

        # Process each symbol
        all_symbols_features = {}
        all_symbols_labels = {}
        all_symbols_feature_names = {}

        for symbol_idx, symbol in enumerate(symbols, start=1):
            logger.info(f"📊 Processing symbol: {symbol}")

            # Check cancellation before processing each symbol
            if cancellation_token and cancellation_token.is_cancelled():
                from ktrdr.async_infrastructure.cancellation import CancellationError

                raise CancellationError("Training cancelled during preprocessing")

            # REPORT: Loading data
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": symbol_idx,
                        "total_symbols": len(symbols),
                        "step": "loading_data",
                    },
                )

            # Step 1: Load market data
            price_data = TrainingPipeline.load_market_data(
                symbol=symbol,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                data_mode=data_mode,
                data_manager=data_manager,
                multi_timeframe_coordinator=multi_timeframe_coordinator,
            )

            # REPORT: Computing indicators
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": symbol_idx,
                        "total_symbols": len(symbols),
                        "step": "computing_indicators",
                    },
                )

            # Step 2: Calculate indicators
            indicators_data = TrainingPipeline.calculate_indicators(
                price_data,
                strategy_config["indicators"],
                progress_callback=progress_callback,
                symbol=symbol,
                symbol_index=symbol_idx,
                total_symbols=len(symbols),
            )

            # REPORT: Generating fuzzy sets
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": symbol_idx,
                        "total_symbols": len(symbols),
                        "step": "generating_fuzzy",
                    },
                )

            # Step 3: Generate fuzzy memberships
            fuzzy_data = TrainingPipeline.generate_fuzzy_memberships(
                indicators_data, strategy_config["fuzzy_sets"]
            )

            # REPORT: Creating features
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": symbol_idx,
                        "total_symbols": len(symbols),
                        "step": "creating_features",
                    },
                )

            # Step 4: Engineer features
            features, feature_names = TrainingPipeline.create_features(
                fuzzy_data, strategy_config.get("model", {}).get("features", {})
            )

            # REPORT: Generating labels
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    {
                        "progress_type": "preprocessing",
                        "symbol": symbol,
                        "symbol_index": symbol_idx,
                        "total_symbols": len(symbols),
                        "step": "generating_labels",
                    },
                )

            # Step 5: Generate labels
            labels = TrainingPipeline.create_labels(
                price_data, strategy_config["training"]["labels"]
            )

            # Store for this symbol
            all_symbols_features[symbol] = features
            all_symbols_labels[symbol] = labels
            all_symbols_feature_names[symbol] = feature_names

        # Step 6: Combine multi-symbol data (or pass through for single symbol)
        logger.info(f"🔗 Combining data from {len(symbols)} symbol(s)")
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_symbols_features, all_symbols_labels, symbols
        )

        # Step 7: Split data
        data_split_config = strategy_config["training"]["data_split"]
        test_size = data_split_config.get("test_size", 0.1)
        val_size = data_split_config.get("validation_size", 0.2)

        # Calculate split indices
        total_samples = len(combined_features)
        test_split = int(total_samples * (1 - test_size))
        val_split = int(test_split * (1 - val_size))

        # Split sequentially (preserve temporal order)
        X_train = combined_features[:val_split]
        y_train = combined_labels[:val_split]

        X_val = combined_features[val_split:test_split]
        y_val = combined_labels[val_split:test_split]

        X_test = combined_features[test_split:]
        y_test = combined_labels[test_split:]

        logger.info(
            f"📊 Data splits - Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}"
        )

        # Step 8: Create model (symbol-agnostic)
        input_dim = combined_features.shape[1]
        output_dim = 3  # Buy (0), Hold (1), Sell (2)
        model = TrainingPipeline.create_model(
            input_dim=input_dim,
            output_dim=output_dim,
            model_config=strategy_config["model"],
        )

        # Step 9: Train model (PASS THROUGH callbacks/token)
        logger.info("🏋️ Training model...")
        training_results = TrainingPipeline.train_model(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            training_config=strategy_config["model"]["training"],
            progress_callback=progress_callback,  # ← Pass through
            cancellation_token=cancellation_token,  # ← Pass through
        )

        # Step 10: Evaluate model
        logger.info("📈 Evaluating model...")
        test_metrics = TrainingPipeline.evaluate_model(
            model=model, X_test=X_test, y_test=y_test
        )

        # Step 11: Save model
        logger.info("💾 Saving model...")
        feature_names = list(all_symbols_feature_names.values())[0]
        primary_timeframe = timeframes[0] if timeframes else "1h"

        # Symbol-agnostic model storage: symbol parameter is deprecated
        # Models are stored as: models/{strategy_name}/{timeframe}_v{N}/
        model_path = model_storage.save_model(
            model=model,
            strategy_name=strategy_config["name"],
            symbol="MULTI" if len(symbols) > 1 else symbols[0],  # Placeholder only
            timeframe=primary_timeframe,
            config=strategy_config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=None,  # Can be added later
            scaler=None,  # Symbol-agnostic doesn't use scaler
        )

        logger.info(f"✅ Training complete! Model saved to: {model_path}")

        # Return standardized format
        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
            "artifacts": {
                "feature_importance": None,  # Can be added later
                "per_symbol_metrics": None,  # Can be added later
            },
            "model_info": {
                "parameters_count": sum(p.numel() for p in model.parameters()),
                "trainable_parameters": sum(
                    p.numel() for p in model.parameters() if p.requires_grad
                ),
                "architecture": "symbol_agnostic_mlp",
            },
            "data_summary": {
                "symbols": symbols,
                "timeframes": timeframes,
                "start_date": start_date,
                "end_date": end_date,
                "total_samples": len(combined_features),
                "feature_count": combined_features.shape[1],
            },
        }
