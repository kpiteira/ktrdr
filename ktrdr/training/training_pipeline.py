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

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.data.multi_timeframe_coordinator import MultiTimeframeCoordinator
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
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
        price_data: dict[str, pd.DataFrame], indicator_configs: list[dict[str, Any]]
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate technical indicators with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._calculate_indicators() (train_strategy.py:596-800)

        Args:
            price_data: Dictionary mapping timeframes to OHLCV DataFrames
            indicator_configs: List of indicator configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with indicators
        """
        # Handle single timeframe case (backward compatibility)
        if len(price_data) == 1:
            timeframe, tf_price_data = next(iter(price_data.items()))
            indicators = TrainingPipeline._calculate_indicators_single_timeframe(
                tf_price_data, indicator_configs
            )
            return {timeframe: indicators}

        # Multi-timeframe case
        return TrainingPipeline._calculate_indicators_multi_timeframe(
            price_data, indicator_configs
        )

    @staticmethod
    def _calculate_indicators_single_timeframe(
        price_data: pd.DataFrame, indicator_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Calculate indicators for a single timeframe.

        EXTRACTED FROM: StrategyTrainer._calculate_indicators_single_timeframe()
        (train_strategy.py:625-712)
        """
        # Fix indicator configs to add 'type' field if missing
        fixed_configs = []

        # Mapping from strategy names to registry names
        name_mapping = {
            "bollinger_bands": "BollingerBands",
            "keltner_channels": "KeltnerChannels",
            "momentum": "Momentum",
            "volume_sma": "SMA",  # Use SMA for volume_sma for now
            "atr": "ATR",
            "rsi": "RSI",
            "sma": "SMA",
            "ema": "EMA",
            "macd": "MACD",
        }

        for config in indicator_configs:
            if isinstance(config, dict) and "type" not in config:
                # Infer type from name using proper mapping
                config = config.copy()
                indicator_name = config["name"].lower()
                if indicator_name in name_mapping:
                    config["type"] = name_mapping[indicator_name]
                else:
                    # Fallback: convert snake_case to PascalCase
                    config["type"] = "".join(
                        word.capitalize() for word in indicator_name.split("_")
                    )
            fixed_configs.append(config)

        # Initialize indicator engine with configs
        indicator_engine = IndicatorEngine(indicators=fixed_configs)
        # Apply indicators to price data
        indicator_results = indicator_engine.apply(price_data)

        # Create a mapping from original indicator names to calculated column names
        # This allows fuzzy sets to match the original indicator names
        mapped_results = pd.DataFrame(index=indicator_results.index)

        # Copy price data columns first
        for col in price_data.columns:
            if col in indicator_results.columns:
                mapped_results[col] = indicator_results[col]

        # Map indicator results to original names for fuzzy matching
        for config in indicator_configs:
            original_name = config["name"]  # e.g., 'rsi'
            indicator_type = config["name"].upper()  # e.g., 'RSI'

            # Find the calculated column that matches this indicator
            # Look for columns that start with the indicator type
            for col in indicator_results.columns:
                if col.upper().startswith(indicator_type):
                    if indicator_type in ["SMA", "EMA"]:
                        # For moving averages, create a ratio (price / moving_average)
                        # This makes the fuzzy sets meaningful (1.0 = at MA, >1.0 = above, <1.0 = below)
                        mapped_results[original_name] = (
                            price_data["close"] / indicator_results[col]
                        )
                    elif indicator_type == "MACD":
                        # For MACD, use the main MACD line (not signal or histogram)
                        # Look for the column that matches the MACD pattern
                        if (
                            col.startswith("MACD_")
                            and "_signal_" not in col
                            and "_hist_" not in col
                        ):
                            mapped_results[original_name] = indicator_results[col]
                            break
                    else:
                        # For other indicators, use the raw values
                        mapped_results[original_name] = indicator_results[col]
                        break

                    # If we found a non-MACD indicator, break
                    if indicator_type != "MACD":
                        break

        # Final safety check: replace any inf values with NaN, then fill NaN with 0
        # This prevents overflow from propagating to feature scaling
        mapped_results = mapped_results.replace([np.inf, -np.inf], np.nan)
        mapped_results = mapped_results.fillna(0.0)

        return mapped_results

    @staticmethod
    def _calculate_indicators_multi_timeframe(
        price_data: dict[str, pd.DataFrame],
        indicator_configs: list[dict[str, Any]],
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate indicators for multiple timeframes.

        EXTRACTED FROM: StrategyTrainer._calculate_indicators_multi_timeframe()
        (train_strategy.py:714-800)
        """
        # Fix indicator configs to add 'type' field if missing (same as single timeframe)
        fixed_configs = []

        # Mapping from strategy names to registry names
        name_mapping = {
            "bollinger_bands": "BollingerBands",
            "keltner_channels": "KeltnerChannels",
            "momentum": "Momentum",
            "volume_sma": "SMA",  # Use SMA for volume_sma for now
            "sma": "SMA",
            "ema": "EMA",
            "rsi": "RSI",
            "macd": "MACD",
        }

        for config in indicator_configs:
            if isinstance(config, dict) and "type" not in config:
                # Infer type from name using proper mapping
                config = config.copy()
                indicator_name = config["name"].lower()
                if indicator_name in name_mapping:
                    config["type"] = name_mapping[indicator_name]
                else:
                    # Fallback: convert snake_case to PascalCase
                    config["type"] = "".join(
                        word.capitalize() for word in indicator_name.split("_")
                    )
            fixed_configs.append(config)

        # Initialize indicator engine with configs and use multi-timeframe method
        indicator_engine = IndicatorEngine(indicators=fixed_configs)
        indicator_results = indicator_engine.apply_multi_timeframe(
            price_data, fixed_configs
        )

        # Map results for each timeframe (similar to single timeframe but for each TF)
        mapped_results = {}

        for timeframe, tf_indicators in indicator_results.items():
            tf_price_data = price_data[timeframe]
            mapped_tf_results = pd.DataFrame(index=tf_indicators.index)

            # Copy price data columns first
            for col in tf_price_data.columns:
                if col in tf_indicators.columns:
                    mapped_tf_results[col] = tf_indicators[col]

            # Map indicator results to original names for fuzzy matching
            for config in indicator_configs:
                original_name = config["name"]  # e.g., 'rsi'
                indicator_type = config["name"].upper()  # e.g., 'RSI'

                # Find the calculated column that matches this indicator
                for col in tf_indicators.columns:
                    if col.upper().startswith(indicator_type):
                        if indicator_type in ["SMA", "EMA"]:
                            # For moving averages, create a ratio (price / moving_average)
                            mapped_tf_results[original_name] = (
                                tf_price_data["close"] / tf_indicators[col]
                            )
                        elif indicator_type == "MACD":
                            # For MACD, use the main MACD line (not signal or histogram)
                            if (
                                col.startswith("MACD_")
                                and "_signal_" not in col
                                and "_hist_" not in col
                            ):
                                mapped_tf_results[original_name] = tf_indicators[col]
                                break
                        else:
                            # For other indicators, use the raw values
                            mapped_tf_results[original_name] = tf_indicators[col]
                            break

                        # If we found a non-MACD indicator, break
                        if indicator_type != "MACD":
                            break

            mapped_results[timeframe] = mapped_tf_results

        return mapped_results

    @staticmethod
    def generate_fuzzy_memberships(
        indicators: dict[str, pd.DataFrame], fuzzy_configs: dict[str, Any]
    ) -> dict[str, pd.DataFrame]:
        """
        Generate fuzzy membership values with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._generate_fuzzy_memberships()
        (train_strategy.py:802-847)

        Args:
            indicators: Dictionary mapping timeframes to technical indicators DataFrames
            fuzzy_configs: Fuzzy set configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with fuzzy membership values
        """
        # Initialize fuzzy engine
        fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_configs)
        fuzzy_engine = FuzzyEngine(fuzzy_config)

        # Handle single timeframe case (backward compatibility)
        if len(indicators) == 1 and isinstance(
            list(indicators.values())[0], pd.DataFrame
        ):
            timeframe, tf_indicators = next(iter(indicators.items()))

            # Process each indicator (original single-timeframe logic)
            fuzzy_results: dict[str, Any] = {}
            for indicator_name, indicator_data in tf_indicators.items():
                if indicator_name in fuzzy_configs:
                    # Fuzzify the indicator
                    membership_values = fuzzy_engine.fuzzify(
                        str(indicator_name), indicator_data
                    )
                    fuzzy_results.update(membership_values)

            return {timeframe: pd.DataFrame(fuzzy_results, index=tf_indicators.index)}

        # Multi-timeframe case - use the new multi-timeframe method
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
        # Pure neuro-fuzzy architecture: only fuzzy memberships as inputs
        processor = FuzzyNeuralProcessor(feature_config)

        # Handle single timeframe case (backward compatibility)
        if len(fuzzy_data) == 1:
            timeframe, tf_fuzzy_data = next(iter(fuzzy_data.items()))
            features, feature_names = processor.prepare_input(tf_fuzzy_data)
            return features, feature_names

        # Multi-timeframe case - use the new multi-timeframe method
        features, feature_names = processor.prepare_multi_timeframe_input(fuzzy_data)
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
        return torch.LongTensor(labels.values)

    @staticmethod
    def _sort_timeframes_by_frequency(timeframes: list[str]) -> list[str]:
        """
        Sort timeframes by frequency (highest frequency first).

        Helper method for multi-timeframe label generation.
        """
        # Timeframe frequency mapping (in minutes)
        frequency_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1D": 1440,
            "1d": 1440,
            "1W": 10080,
            "1w": 10080,
        }

        # Sort by frequency (lower minutes = higher frequency)
        return sorted(timeframes, key=lambda tf: frequency_map.get(tf, 1440))
