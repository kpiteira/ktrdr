"""Strategy training orchestrator that coordinates the complete training pipeline."""

from typing import Any, Optional

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.metrics import f1_score, precision_score, recall_score

from ..data.data_manager import DataManager
from ..fuzzy.engine import FuzzyEngine
from ..indicators.indicator_engine import IndicatorEngine
from ..logging import get_logger
from ..neural.models.mlp import MLPTradingModel
from .fuzzy_neural_processor import FuzzyNeuralProcessor
from .model_storage import ModelStorage
from .model_trainer import ModelTrainer
from .zigzag_labeler import ZigZagLabeler

logger = get_logger(__name__)


class StrategyTrainer:
    """Coordinate the complete training pipeline from data to trained model."""

    def __init__(self, models_dir: str = "models"):
        """Initialize the strategy trainer.

        Args:
            models_dir: Directory to store trained models
        """
        self.model_storage = ModelStorage(models_dir)
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = None  # Will be initialized with strategy config

    def train_multi_symbol_strategy(
        self,
        strategy_config_path: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        progress_callback=None,
    ) -> dict[str, Any]:
        """Train a neuro-fuzzy strategy on multiple symbols simultaneously.

        Args:
            strategy_config_path: Path to strategy YAML configuration
            symbols: List of trading symbols to train on (e.g., ['EURUSD', 'GBPUSD', 'USDJPY'])
            timeframes: List of timeframes for multi-timeframe training
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Fraction of data to use for validation
            data_mode: Data loading mode ('local', 'tail', 'backfill', 'full')
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with training results and per-symbol metrics
        """
        print(f"Starting multi-symbol training for {len(symbols)} symbols: {symbols}")
        print(f"Timeframes: {timeframes}")
        print(f"Data range: {start_date} to {end_date}")

        # Load strategy configuration
        config = self._load_strategy_config(strategy_config_path)
        strategy_name = config["name"]
        print(f"Strategy: {strategy_name}")

        # Step 1: Load data for all symbols
        print("\n1. Loading market data for all symbols...")
        all_symbols_data = {}
        for symbol in symbols:
            print(f"  Loading data for {symbol}...")
            symbol_data = self._load_price_data(
                symbol, timeframes, start_date, end_date, data_mode
            )
            all_symbols_data[symbol] = symbol_data

            # Print data summary for this symbol
            if len(timeframes) == 1:
                data_count = len(list(symbol_data.values())[0])
                print(f"    {symbol}: {data_count} bars")
            else:
                total_bars = sum(len(df) for df in symbol_data.values())
                print(
                    f"    {symbol}: {total_bars} total bars across {len(timeframes)} timeframes"
                )

        # Step 2: Calculate indicators for all symbols
        print("\n2. Calculating technical indicators for all symbols...")
        all_symbols_indicators = {}
        for symbol in symbols:
            print(f"  Calculating indicators for {symbol}...")
            symbol_indicators = self._calculate_indicators(
                all_symbols_data[symbol], config["indicators"]
            )
            all_symbols_indicators[symbol] = symbol_indicators

        # Step 3: Generate fuzzy memberships for all symbols
        print("\n3. Generating fuzzy memberships for all symbols...")
        all_symbols_fuzzy = {}
        for symbol in symbols:
            print(f"  Generating fuzzy memberships for {symbol}...")
            symbol_fuzzy = self._generate_fuzzy_memberships(
                all_symbols_indicators[symbol], config["fuzzy_sets"]
            )
            all_symbols_fuzzy[symbol] = symbol_fuzzy

        # Step 4: Engineer features for all symbols
        print("\n4. Engineering features for all symbols...")
        all_symbols_features = {}
        all_symbols_feature_names = {}
        for symbol in symbols:
            print(f"  Engineering features for {symbol}...")
            symbol_features, symbol_feature_names, _ = self._engineer_features(
                all_symbols_fuzzy[symbol],
                all_symbols_indicators[symbol],
                all_symbols_data[symbol],
                config.get("model", {}).get("features", {}),
            )
            all_symbols_features[symbol] = symbol_features
            all_symbols_feature_names[symbol] = symbol_feature_names

        # Validate that all symbols have the same feature structure
        feature_counts = [
            features.shape[1] for features in all_symbols_features.values()
        ]
        if not all(count == feature_counts[0] for count in feature_counts):
            raise ValueError(
                f"Feature count mismatch across symbols: {dict(zip(symbols, feature_counts))}"
            )

        # Step 5: Generate labels for all symbols
        print("\n5. Generating training labels for all symbols...")
        all_symbols_labels = {}
        for symbol in symbols:
            print(f"  Generating labels for {symbol}...")
            symbol_labels = self._generate_labels(
                all_symbols_data[symbol], config["training"]["labels"]
            )
            all_symbols_labels[symbol] = symbol_labels

        # Step 6: Combine all symbols' data with balanced sampling
        print("\n6. Combining multi-symbol data with balanced sampling...")
        combined_features, combined_labels, symbol_indices = (
            self._combine_multi_symbol_data(
                all_symbols_features, all_symbols_labels, symbols
            )
        )

        print(f"Combined dataset: {len(combined_features)} total samples")
        symbol_counts = {
            symbol: (symbol_indices == i).sum() for i, symbol in enumerate(symbols)
        }
        for symbol, count in symbol_counts.items():
            print(
                f"  {symbol}: {count} samples ({count/len(combined_features)*100:.1f}%)"
            )

        # Step 7: Prepare training datasets (including symbol indices)
        print("\n7. Preparing training datasets...")
        train_data, val_data, test_data = self._split_multi_symbol_data(
            combined_features,
            combined_labels,
            symbol_indices,
            validation_split,
            config["training"]["data_split"],
        )
        print(
            f"Data splits - Train: {len(train_data[0])}, Val: {len(val_data[0])}, Test: {len(test_data[0]) if test_data else 0}"
        )

        # Step 8: Create model with symbol embeddings
        print("\n8. Creating multi-symbol neural network...")
        model = self._create_multi_symbol_model(
            config["model"], combined_features.shape[1], len(symbols)
        )

        # Step 9: Train model
        print("\n9. Training multi-symbol neural network...")
        training_results = self._train_model(
            model, train_data, val_data, config, symbols, timeframes, progress_callback
        )

        # Step 10: Evaluate model
        print("\n10. Evaluating multi-symbol model...")
        test_metrics = self._evaluate_model(model, test_data)
        if test_data is not None:
            print(
                f"Test accuracy: {test_metrics['test_accuracy']:.4f}, Test loss: {test_metrics['test_loss']:.4f}"
            )

        # Step 11: Calculate per-symbol performance
        print("\n11. Calculating per-symbol performance...")
        # For multi-symbol training, val_data already contains symbol indices as third element
        val_features, val_labels, val_symbol_indices = (
            val_data  # Unpack all three elements
        )
        val_features_labels = (val_features, val_labels)  # Create tuple for evaluation
        per_symbol_metrics = self._evaluate_per_symbol_performance(
            model, val_features_labels, val_symbol_indices, symbols
        )

        # Step 12: Calculate feature importance
        print("\n12. Calculating feature importance...")
        # Use the feature names from the first symbol (they should all be the same)
        feature_names = list(all_symbols_feature_names.values())[0]
        feature_importance = self._calculate_feature_importance(
            model, val_features, val_labels, feature_names
        )

        # Step 13: Save trained model
        print("\n13. Saving multi-symbol trained model...")
        model_config = config.copy()
        model_config["model"]["input_size"] = combined_features.shape[1]
        model_config["model"]["num_symbols"] = len(symbols)
        model_config["model"]["symbol_embedding_dim"] = config["model"].get(
            "symbol_embedding_dim", 16
        )

        # For multi-symbol models, use a composite identifier
        symbols_str = "_".join(symbols)
        primary_timeframe = timeframes[0] if timeframes else "1h"
        model_path = self.model_storage.save_model(
            model=model,
            strategy_name=strategy_name,
            symbol=symbols_str,  # Use combined symbol string
            timeframe=primary_timeframe,
            config=model_config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=feature_importance,
            scaler=None,
        )

        print(f"\nMulti-symbol training completed! Model saved to: {model_path}")

        # Calculate model info
        model_info = {}
        if model is not None:
            total_params = sum(p.numel() for p in model.parameters())
            trainable_params = sum(
                p.numel() for p in model.parameters() if p.requires_grad
            )

            model_info = {
                "model_size_bytes": int(total_params * 4),
                "parameters_count": int(total_params),
                "trainable_parameters": int(trainable_params),
                "architecture": f"multi_symbol_mlp_{len(symbols)}symbols",
                "symbol_embedding_dim": config["model"].get("symbol_embedding_dim", 16),
            }

        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
            "per_symbol_metrics": per_symbol_metrics,
            "feature_importance": feature_importance,
            "model_info": model_info,
            "data_summary": {
                "symbols": symbols,
                "timeframes": timeframes,
                "start_date": start_date,
                "end_date": end_date,
                "total_samples": len(combined_features),
                "feature_count": combined_features.shape[1],
                "symbol_distribution": symbol_counts,
            },
        }

    def train_strategy(
        self,
        strategy_config_path: str,
        symbol: str,
        timeframes: list[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        progress_callback=None,
    ) -> dict[str, Any]:
        """Train a complete neuro-fuzzy strategy with multi-timeframe support.

        Args:
            strategy_config_path: Path to strategy YAML configuration
            symbol: Trading symbol to train on
            timeframes: List of timeframes for multi-timeframe training (e.g., ['15m', '1h', '4h'])
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Fraction of data to use for validation
            data_mode: Data loading mode ('local', 'tail', 'backfill', 'full')
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with training results and model information
        """
        # Handle single timeframe case (backward compatibility)
        if len(timeframes) == 1:
            print(f"Starting training for {symbol} {timeframes[0]} strategy...")
        else:
            print(
                f"Starting multi-timeframe training for {symbol} {timeframes} strategy..."
            )

        # Load strategy configuration
        config = self._load_strategy_config(strategy_config_path)
        strategy_name = config["name"]

        print(f"Strategy: {strategy_name}")
        print(f"Data range: {start_date} to {end_date}")

        # Step 1: Load and prepare data
        print("\n1. Loading market data...")
        price_data = self._load_price_data(
            symbol, timeframes, start_date, end_date, data_mode
        )

        # Print data loading summary
        if len(timeframes) == 1:
            data_count = len(list(price_data.values())[0])
            print(f"Loaded {data_count} bars of data for {timeframes[0]}")
        else:
            total_data = sum(len(df) for df in price_data.values())
            print(
                f"Loaded {total_data} total bars across {len(timeframes)} timeframes:"
            )
            for tf, df in price_data.items():
                print(f"  {tf}: {len(df)} bars")

        # Step 2: Calculate indicators
        print("\n2. Calculating technical indicators...")
        indicators = self._calculate_indicators(price_data, config["indicators"])

        # Check for critical NaN values that could break training
        if isinstance(indicators, dict):
            # Multi-timeframe case: check each timeframe
            total_nan_count = 0
            for tf, tf_indicators in indicators.items():
                tf_nan_count = tf_indicators.isna().sum().sum()
                total_nan_count += tf_nan_count
            indicators_nan_count = total_nan_count
        else:
            # Single timeframe case: direct DataFrame
            indicators_nan_count = indicators.isna().sum().sum()

        if indicators_nan_count > 0:
            print(
                f"⚠️ Warning: {indicators_nan_count} NaN values in indicators - will be filled with 0"
            )

        print(f"Calculated {len(config['indicators'])} indicators")

        # Step 3: Generate fuzzy memberships
        print("\n3. Generating fuzzy memberships...")
        fuzzy_data = self._generate_fuzzy_memberships(indicators, config["fuzzy_sets"])
        print(f"Generated fuzzy sets for {len(config['fuzzy_sets'])} indicators")

        # Step 4: Engineer features
        print("\n4. Engineering features...")

        # Check for critical NaN values in fuzzy data
        if isinstance(fuzzy_data, dict):
            # Multi-timeframe case: check each timeframe
            total_fuzzy_nan_count = 0
            for tf, tf_fuzzy in fuzzy_data.items():
                tf_fuzzy_nan_count = tf_fuzzy.isna().sum().sum()
                total_fuzzy_nan_count += tf_fuzzy_nan_count
            fuzzy_nan_count = total_fuzzy_nan_count
        else:
            # Single timeframe case: direct DataFrame
            fuzzy_nan_count = fuzzy_data.isna().sum().sum()

        if fuzzy_nan_count > 0:
            print(f"⚠️ Warning: {fuzzy_nan_count} NaN values in fuzzy data")

        features, feature_names, feature_scaler = self._engineer_features(
            fuzzy_data,
            indicators,
            price_data,
            config.get("model", {}).get("features", {}),
        )

        # Validate final features
        if hasattr(features, "isna"):  # pandas DataFrame
            features_nan_count = features.isna().sum().sum()
        else:  # numpy array or tensor
            features_nan_count = (
                np.isnan(features).sum() if hasattr(features, "shape") else 0
            )

        if features_nan_count > 0:
            print(
                f"❌ Error: {features_nan_count} NaN values detected in final features"
            )
            raise ValueError("Features contain NaN values that would break training")

        print(
            f"Created {features.shape[1]} features from {len(feature_names)} components"
        )

        # Step 5: Generate training labels
        print("\n5. Generating training labels...")
        labels = self._generate_labels(price_data, config["training"]["labels"])
        label_dist = self._get_label_distribution(labels)
        print(
            f"Label distribution: BUY={label_dist['buy_pct']:.1f}%, "
            f"HOLD={label_dist['hold_pct']:.1f}%, SELL={label_dist['sell_pct']:.1f}%"
        )

        # Step 6: Prepare training datasets
        print("\n6. Preparing training datasets...")
        train_data, val_data, test_data = self._split_data(
            features, labels, validation_split, config["training"]["data_split"]
        )
        print(
            f"Data splits - Train: {len(train_data[0])}, Val: {len(val_data[0])}, Test: {len(test_data[0]) if test_data else 0}"
        )

        # Step 7: Create and train neural network
        print("\n7. Training neural network...")

        # Final validation before training
        if np.isnan(train_data[0]).any() or np.isnan(train_data[1]).any():
            raise ValueError("Training data contains NaN values")
        if np.isinf(train_data[0]).any():
            raise ValueError("Training data contains infinite values")

        model = self._create_model(config["model"], features.shape[1])
        training_results = self._train_model(
            model, train_data, val_data, config, symbol, timeframes, progress_callback
        )

        # Step 8: Evaluate model
        print("\n8. Evaluating model...")
        test_metrics = self._evaluate_model(model, test_data)
        if test_data is not None:
            print(
                f"Test accuracy: {test_metrics['test_accuracy']:.4f}, Test loss: {test_metrics['test_loss']:.4f}"
            )
        else:
            print("No test data available - returning zero metrics")

        # Step 9: Calculate feature importance
        print("\n9. Calculating feature importance...")
        feature_importance = self._calculate_feature_importance(
            model, val_data[0], val_data[1], feature_names
        )

        # Step 10: Save trained model
        print("\n10. Saving trained model...")

        # Add model architecture info to config for proper loading
        model_config = config.copy()
        model_config["model"]["input_size"] = features.shape[1]

        # Use first timeframe for model storage compatibility
        primary_timeframe = timeframes[0] if timeframes else "1h"
        model_path = self.model_storage.save_model(
            model=model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=primary_timeframe,
            config=model_config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=feature_importance,
            scaler=feature_scaler,
        )

        print(f"\nTraining completed! Model saved to: {model_path}")

        # Calculate model info (size and parameters)
        model_info = {}
        if model is not None:
            total_params = sum(p.numel() for p in model.parameters())
            trainable_params = sum(
                p.numel() for p in model.parameters() if p.requires_grad
            )

            model_info = {
                "model_size_bytes": int(
                    total_params * 4
                ),  # Assume float32 = 4 bytes per param
                "parameters_count": int(total_params),
                "trainable_parameters": int(trainable_params),
                "architecture": f"mlp_{'_'.join(map(str, config['model']['architecture']['hidden_layers']))}",
            }

        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
            "feature_importance": feature_importance,
            "label_distribution": label_dist,
            "model_info": model_info,
            "data_summary": {
                "symbol": symbol,
                "timeframes": timeframes,
                "start_date": start_date,
                "end_date": end_date,
                "total_samples": len(features),
                "feature_count": features.shape[1],
            },
        }

    def _load_strategy_config(self, config_path: str) -> dict[str, Any]:
        """Load strategy configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Strategy configuration dictionary
        """
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Validate required sections
        required_sections = ["name", "indicators", "fuzzy_sets", "model", "training"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        return config

    def _load_price_data(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: str,
        end_date: str,
        data_mode: str = "local",
    ) -> dict[str, pd.DataFrame]:
        """Load price data for training with multi-timeframe support.

        Args:
            symbol: Trading symbol
            timeframes: List of timeframes for multi-timeframe training
            start_date: Start date
            end_date: End date
            data_mode: Data loading mode

        Returns:
            Dictionary mapping timeframes to OHLCV DataFrames
        """
        # Handle single timeframe case (backward compatibility)
        if len(timeframes) == 1:
            timeframe = timeframes[0]
            data = self.data_manager.load_data(symbol, timeframe, mode=data_mode)

            # Filter by date range if possible
            if hasattr(data.index, "to_pydatetime"):
                data = self._filter_data_by_date_range(data, start_date, end_date)

            return {timeframe: data}

        # Multi-timeframe case - use first timeframe (highest frequency) as base
        base_timeframe = timeframes[0]  # Always use first timeframe as base
        multi_data = self.data_manager.load_multi_timeframe_data(
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

    def _filter_data_by_date_range(
        self, data: pd.DataFrame, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Helper method to filter data by date range."""
        # Convert dates to timezone-aware if the data index is timezone-aware
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        # Make dates timezone-aware if needed
        if data.index.tz is not None:
            if start.tz is None:
                start = start.tz_localize("UTC")
            if end.tz is None:
                end = end.tz_localize("UTC")

        return data.loc[start:end]

    def _calculate_indicators(
        self,
        price_data: dict[str, pd.DataFrame],
        indicator_configs: list[dict[str, Any]],
    ) -> dict[str, pd.DataFrame]:
        """Calculate technical indicators with multi-timeframe support.

        Args:
            price_data: Dictionary mapping timeframes to OHLCV data
            indicator_configs: List of indicator configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with calculated indicators
        """
        # Handle single timeframe case (backward compatibility)
        if len(price_data) == 1:
            timeframe, data = next(iter(price_data.items()))
            indicators = self._calculate_indicators_single_timeframe(
                data, indicator_configs
            )
            return {timeframe: indicators}

        # Multi-timeframe case
        return self._calculate_indicators_multi_timeframe(price_data, indicator_configs)

    def _calculate_indicators_single_timeframe(
        self, price_data: pd.DataFrame, indicator_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Calculate indicators for a single timeframe (original implementation)."""
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
        self.indicator_engine = IndicatorEngine(indicators=fixed_configs)
        # Apply indicators to price data
        indicator_results = self.indicator_engine.apply(price_data)

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

    def _calculate_indicators_multi_timeframe(
        self,
        price_data: dict[str, pd.DataFrame],
        indicator_configs: list[dict[str, Any]],
    ) -> dict[str, pd.DataFrame]:
        """Calculate indicators for multiple timeframes using the new multi-timeframe method."""
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
        self.indicator_engine = IndicatorEngine(indicators=fixed_configs)
        indicator_results = self.indicator_engine.apply_multi_timeframe(
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

    def _generate_fuzzy_memberships(
        self, indicators: dict[str, pd.DataFrame], fuzzy_configs: dict[str, Any]
    ) -> dict[str, pd.DataFrame]:
        """Generate fuzzy membership values with multi-timeframe support.

        Args:
            indicators: Dictionary mapping timeframes to technical indicators DataFrames
            fuzzy_configs: Fuzzy set configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with fuzzy membership values
        """
        # Initialize fuzzy engine if not already done
        if self.fuzzy_engine is None:
            from ..fuzzy.config import FuzzyConfigLoader

            # The fuzzy_configs from strategy file are already in the correct format
            # Just pass them directly to FuzzyConfigLoader
            fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_configs)
            self.fuzzy_engine = FuzzyEngine(fuzzy_config)

        # Handle single timeframe case (backward compatibility)
        if len(indicators) == 1 and isinstance(
            list(indicators.values())[0], pd.DataFrame
        ):
            timeframe, tf_indicators = next(iter(indicators.items()))

            # Process each indicator (original single-timeframe logic)
            fuzzy_results = {}
            for indicator_name, indicator_data in tf_indicators.items():
                if indicator_name in fuzzy_configs:
                    # Fuzzify the indicator
                    membership_values = self.fuzzy_engine.fuzzify(
                        indicator_name, indicator_data
                    )
                    fuzzy_results.update(membership_values)

            return {timeframe: pd.DataFrame(fuzzy_results, index=tf_indicators.index)}

        # Multi-timeframe case - use the new multi-timeframe method
        return self.fuzzy_engine.generate_multi_timeframe_memberships(
            indicators, fuzzy_configs
        )

    def _engineer_features(
        self,
        fuzzy_data: dict[str, pd.DataFrame],
        indicators: dict[str, pd.DataFrame],
        price_data: dict[str, pd.DataFrame],
        feature_config: dict[str, Any],
    ) -> tuple[torch.Tensor, list[str], Any]:
        """Engineer features for neural network training using pure fuzzy approach with multi-timeframe support.

        Args:
            fuzzy_data: Dictionary mapping timeframes to fuzzy membership values
            indicators: Dictionary mapping timeframes to technical indicators (not used in pure fuzzy mode)
            price_data: Dictionary mapping timeframes to OHLCV data (not used in pure fuzzy mode)
            feature_config: Feature engineering configuration

        Returns:
            Tuple of (features tensor, feature names, None for scaler)
        """
        # Pure neuro-fuzzy architecture: only fuzzy memberships as inputs
        processor = FuzzyNeuralProcessor(feature_config)

        # Handle single timeframe case (backward compatibility)
        if len(fuzzy_data) == 1:
            timeframe, tf_fuzzy_data = next(iter(fuzzy_data.items()))
            features, feature_names = processor.prepare_input(tf_fuzzy_data)
            return features, feature_names, None  # No scaler needed for fuzzy values

        # Multi-timeframe case - use the new multi-timeframe method
        features, feature_names = processor.prepare_multi_timeframe_input(fuzzy_data)
        return features, feature_names, None  # No scaler needed for fuzzy values

    def _generate_labels(
        self, price_data: dict[str, pd.DataFrame], label_config: dict[str, Any]
    ) -> torch.Tensor:
        """Generate training labels using ZigZag method with multi-timeframe support.

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
            print(f"Generating labels from {timeframe} data")
        else:
            # Multi-timeframe case - use SAME base timeframe as features (highest frequency)
            # Features use frequency-based ordering, so we must match that
            timeframe_list = sorted(price_data.keys())
            # Convert to frequency-based order (highest frequency first)
            frequency_order = self._sort_timeframes_by_frequency(timeframe_list)
            base_timeframe = frequency_order[
                0
            ]  # Use highest frequency (same as features)
            tf_price_data = price_data[base_timeframe]
            print(
                f"Generating labels from base timeframe {base_timeframe} (out of {frequency_order}) - matching features"
            )

        labeler = ZigZagLabeler(
            threshold=label_config["zigzag_threshold"],
            lookahead=label_config["label_lookahead"],
        )

        # Use segment-based labeling for better class balance
        print(
            "Using ZigZag segment labeling (balanced) instead of sparse extreme labeling..."
        )
        labels = labeler.generate_segment_labels(tf_price_data)
        return torch.LongTensor(labels.values)

    def _get_label_distribution(self, labels: torch.Tensor) -> dict[str, Any]:
        """Get label distribution statistics.

        Args:
            labels: Label tensor

        Returns:
            Distribution statistics
        """
        unique, counts = torch.unique(labels, return_counts=True)
        total = len(labels)

        dist = {f"class_{int(u)}": int(c) for u, c in zip(unique, counts)}

        return {
            "buy_count": dist.get("class_0", 0),
            "hold_count": dist.get("class_1", 0),
            "sell_count": dist.get("class_2", 0),
            "buy_pct": dist.get("class_0", 0) / total * 100,
            "hold_pct": dist.get("class_1", 0) / total * 100,
            "sell_pct": dist.get("class_2", 0) / total * 100,
            "total": total,
        }

    def _split_data(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        validation_split: float,
        split_config: dict[str, float],
    ) -> tuple:
        """Split data into train/validation/test sets.

        Args:
            features: Feature tensor
            labels: Label tensor
            validation_split: Validation split ratio
            split_config: Split configuration from strategy

        Returns:
            Tuple of (train_data, val_data, test_data)
        """
        total_size = len(features)

        # Use strategy config if available, otherwise use validation_split
        if split_config:
            train_size = int(total_size * split_config["train"])
            val_size = int(total_size * split_config["validation"])
            test_size = total_size - train_size - val_size
        else:
            train_size = int(total_size * (1 - validation_split))
            val_size = total_size - train_size
            test_size = 0

        # Split data chronologically (important for time series)
        train_data = (features[:train_size], labels[:train_size])
        val_data = (
            features[train_size : train_size + val_size],
            labels[train_size : train_size + val_size],
        )

        if test_size > 0:
            test_data = (
                features[train_size + val_size :],
                labels[train_size + val_size :],
            )
        else:
            test_data = None

        return train_data, val_data, test_data

    def _create_model(
        self, model_config: dict[str, Any], input_size: int
    ) -> torch.nn.Module:
        """Create neural network model.

        Args:
            model_config: Model configuration
            input_size: Number of input features

        Returns:
            Neural network model
        """
        model_type = model_config.get("type", "mlp").lower()

        if model_type == "mlp":
            model = MLPTradingModel(model_config)
            model.model = model.build_model(input_size)
            return model.model
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def _train_model(
        self,
        model: torch.nn.Module,
        train_data: tuple,
        val_data: tuple,
        config: dict[str, Any],
        symbol_or_symbols,  # Can be str (single) or List[str] (multi-symbol)
        timeframes: list[str],
        progress_callback=None,
    ) -> dict[str, Any]:
        """Train the neural network model (supports both single and multi-symbol).

        Args:
            model: Neural network model
            train_data: Training data tuple (features, labels) or (features, labels, symbol_indices)
            val_data: Validation data tuple (features, labels) or (features, labels, symbol_indices)
            config: Full strategy configuration
            symbol_or_symbols: Single symbol string or list of symbols for multi-symbol training
            timeframes: List of timeframes
            progress_callback: Optional callback for progress updates

        Returns:
            Training results
        """
        # Extract training config and merge with full config for analytics access
        training_config = config["model"]["training"].copy()

        # Add metadata for analytics
        config_with_metadata = config.copy()

        # Check if this is multi-symbol training
        # Can be determined by symbol count OR by data structure (having symbol indices)
        is_multi_symbol = (
            isinstance(symbol_or_symbols, list) and len(symbol_or_symbols) > 1
        ) or (len(train_data) == 3 and len(val_data) == 3)

        if is_multi_symbol:
            # Multi-symbol case
            config_with_metadata["symbols"] = symbol_or_symbols
            config_with_metadata["symbol"] = "_".join(
                symbol_or_symbols
            )  # For legacy compatibility
        else:
            # Single symbol case
            symbol = (
                symbol_or_symbols
                if isinstance(symbol_or_symbols, str)
                else symbol_or_symbols[0]
            )
            config_with_metadata["symbol"] = symbol

        config_with_metadata["timeframes"] = timeframes
        training_config["full_config"] = config_with_metadata

        trainer = ModelTrainer(training_config, progress_callback=progress_callback)

        if is_multi_symbol:
            # Multi-symbol training with symbol indices
            return trainer.train_multi_symbol(
                model=model,
                X_train=train_data[0],
                y_train=train_data[1],
                symbol_indices_train=train_data[2],
                symbols=symbol_or_symbols,
                X_val=val_data[0],
                y_val=val_data[1],
                symbol_indices_val=val_data[2],
            )
        else:
            # Single symbol training (standard case)
            return trainer.train(
                model, train_data[0], train_data[1], val_data[0], val_data[1]
            )

    def _evaluate_model(
        self, model: torch.nn.Module, test_data: Optional[tuple]
    ) -> dict[str, Any]:
        """Evaluate model on test set.

        Args:
            model: Trained model
            test_data: Test data tuple

        Returns:
            Test metrics including accuracy, loss, precision, recall, and f1_score
        """
        if test_data is None:
            return {
                "test_accuracy": 0.0,
                "test_loss": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
            }

        model.eval()
        with torch.no_grad():
            # Handle both 2-element (single-symbol) and 3-element (multi-symbol) tuples
            if len(test_data) == 3:
                X_test, y_test, symbol_indices = test_data
            else:
                X_test, y_test = test_data
            outputs = model(X_test)

            # Calculate accuracy
            _, predicted = torch.max(outputs, 1)
            accuracy = (predicted == y_test).float().mean().item()

            # Calculate loss
            criterion = torch.nn.CrossEntropyLoss()
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

        return {
            "test_accuracy": accuracy,
            "test_loss": loss,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

    def _calculate_feature_importance(
        self,
        model: torch.nn.Module,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        feature_names: list[str],
    ) -> dict[str, float]:
        """Calculate feature importance scores using permutation importance.

        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation labels
            feature_names: List of feature names

        Returns:
            Feature importance dictionary
        """
        from sklearn.metrics import accuracy_score

        model.eval()
        device = next(model.parameters()).device

        # Get baseline accuracy
        with torch.no_grad():
            X_val = X_val.to(device)
            y_val = y_val.to(device)
            outputs = model(X_val)
            predictions = torch.argmax(outputs, dim=1)
            baseline_accuracy = accuracy_score(
                y_val.cpu().numpy(), predictions.cpu().numpy()
            )

        importance_scores = {}

        # Permutation importance for each feature
        for i, feature_name in enumerate(feature_names):
            # Create a copy and shuffle the i-th feature
            X_permuted = X_val.clone()
            idx = torch.randperm(X_permuted.size(0))
            X_permuted[:, i] = X_permuted[idx, i]

            # Calculate accuracy with permuted feature
            with torch.no_grad():
                outputs = model(X_permuted)
                predictions = torch.argmax(outputs, dim=1)
                permuted_accuracy = accuracy_score(
                    y_val.cpu().numpy(), predictions.cpu().numpy()
                )

            # Importance is the drop in accuracy
            importance_scores[feature_name] = baseline_accuracy - permuted_accuracy

        return importance_scores

    def _sort_timeframes_by_frequency(self, timeframes: list[str]) -> list[str]:
        """
        Sort timeframes by frequency (highest frequency first).

        This ensures proper temporal alignment where the highest frequency
        timeframe drives the neural network input resolution.

        Args:
            timeframes: List of timeframe strings (e.g., ['1h', '1d', '4h'])

        Returns:
            List of timeframes sorted by frequency (highest first)

        Example:
            ['1h', '1d'] → ['1h', '1d']  # 1h is higher frequency
            ['1d', '4h', '1h'] → ['1h', '4h', '1d']  # 1h > 4h > 1d
        """

        def timeframe_to_minutes(tf: str) -> int:
            """Convert timeframe string to minutes for comparison."""
            tf = tf.lower().strip()
            if tf.endswith("m"):
                return int(tf[:-1])
            elif tf.endswith("h"):
                return int(tf[:-1]) * 60
            elif tf.endswith("d"):
                return int(tf[:-1]) * 60 * 24
            elif tf.endswith("w"):
                return int(tf[:-1]) * 60 * 24 * 7
            else:
                # Default to hours if no suffix
                return int(tf) * 60

        # Sort by minutes (ascending = highest frequency first)
        sorted_timeframes = sorted(timeframes, key=timeframe_to_minutes)

        return sorted_timeframes

    def _combine_multi_symbol_data(
        self,
        all_symbols_features: dict[str, torch.Tensor],
        all_symbols_labels: dict[str, torch.Tensor],
        symbols: list[str],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Combine features and labels from multiple symbols with balanced sampling.

        Args:
            all_symbols_features: Dictionary mapping symbols to feature tensors
            all_symbols_labels: Dictionary mapping symbols to label tensors
            symbols: List of symbol names

        Returns:
            Tuple of (combined_features, combined_labels, symbol_indices)
        """
        # Find the minimum number of samples across all symbols for balanced sampling
        min_samples = min(len(features) for features in all_symbols_features.values())

        # Collect balanced samples from each symbol
        combined_features_list = []
        combined_labels_list = []
        symbol_indices_list = []

        for symbol_idx, symbol in enumerate(symbols):
            symbol_features = all_symbols_features[symbol]
            symbol_labels = all_symbols_labels[symbol]

            # Sample uniformly from the symbol's data
            if len(symbol_features) > min_samples:
                # Randomly sample min_samples from this symbol
                indices = torch.randperm(len(symbol_features))[:min_samples]
                sampled_features = symbol_features[indices]
                sampled_labels = symbol_labels[indices]
            else:
                # Use all available samples
                sampled_features = symbol_features
                sampled_labels = symbol_labels

            combined_features_list.append(sampled_features)
            combined_labels_list.append(sampled_labels)
            symbol_indices_list.append(
                torch.full((len(sampled_features),), symbol_idx, dtype=torch.long)
            )

        # Combine all symbols' data
        combined_features = torch.cat(combined_features_list, dim=0)
        combined_labels = torch.cat(combined_labels_list, dim=0)
        symbol_indices = torch.cat(symbol_indices_list, dim=0)

        # Shuffle the combined data to mix symbols
        perm = torch.randperm(len(combined_features))
        combined_features = combined_features[perm]
        combined_labels = combined_labels[perm]
        symbol_indices = symbol_indices[perm]

        return combined_features, combined_labels, symbol_indices

    def _create_multi_symbol_model(
        self, model_config: dict[str, Any], input_size: int, num_symbols: int
    ) -> torch.nn.Module:
        """Create neural network model with symbol embeddings.

        Args:
            model_config: Model configuration
            input_size: Number of input features
            num_symbols: Number of symbols for embedding

        Returns:
            Neural network model with symbol embeddings
        """
        model_type = model_config.get("type", "mlp").lower()

        if model_type == "mlp":
            # Add symbol embedding configuration
            model_config_with_embeddings = model_config.copy()
            model_config_with_embeddings["num_symbols"] = num_symbols
            model_config_with_embeddings["symbol_embedding_dim"] = model_config.get(
                "symbol_embedding_dim", 16
            )

            from ..neural.models.mlp import MultiSymbolMLPTradingModel

            model = MultiSymbolMLPTradingModel(model_config_with_embeddings)
            model.model = model.build_model(input_size)
            return model.model
        else:
            raise ValueError(
                f"Unknown model type for multi-symbol training: {model_type}"
            )

    def _evaluate_per_symbol_performance(
        self,
        model: torch.nn.Module,
        val_data: tuple[torch.Tensor, torch.Tensor],
        symbol_indices: torch.Tensor,
        symbols: list[str],
    ) -> dict[str, dict[str, float]]:
        """Evaluate model performance for each symbol separately.

        Args:
            model: Trained model
            val_data: Validation data (features, labels)
            symbol_indices: Tensor indicating which symbol each sample belongs to
            symbols: List of symbol names

        Returns:
            Dictionary mapping symbol names to their performance metrics
        """
        model.eval()
        per_symbol_metrics = {}

        with torch.no_grad():
            # Handle both 2-element (single-symbol) and 3-element (multi-symbol) tuples
            if len(val_data) == 3:
                X_val, y_val, _ = (
                    val_data  # Ignore symbol_indices since passed separately
                )
            else:
                X_val, y_val = val_data
            outputs = model(X_val)
            _, predicted = torch.max(outputs, 1)

            for symbol_idx, symbol in enumerate(symbols):
                # Get indices for this symbol
                symbol_mask = symbol_indices == symbol_idx

                if symbol_mask.sum() == 0:
                    # No samples for this symbol in validation set
                    per_symbol_metrics[symbol] = {
                        "accuracy": 0.0,
                        "precision": 0.0,
                        "recall": 0.0,
                        "f1_score": 0.0,
                        "sample_count": 0,
                    }
                    continue

                # Get predictions and labels for this symbol
                symbol_predicted = predicted[symbol_mask]
                symbol_labels = y_val[symbol_mask]

                # Calculate accuracy
                accuracy = (symbol_predicted == symbol_labels).float().mean().item()

                # Convert to numpy for sklearn metrics
                y_true = symbol_labels.cpu().numpy()
                y_pred = symbol_predicted.cpu().numpy()

                # Calculate precision, recall, and f1_score
                from sklearn.metrics import f1_score, precision_score, recall_score

                precision = precision_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
                recall = recall_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
                f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

                per_symbol_metrics[symbol] = {
                    "accuracy": accuracy,
                    "precision": precision,
                    "recall": recall,
                    "f1_score": f1,
                    "sample_count": int(symbol_mask.sum()),
                }

        return per_symbol_metrics

    def _split_multi_symbol_data(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        symbol_indices: torch.Tensor,
        validation_split: float,
        split_config: dict[str, float],
    ) -> tuple:
        """Split multi-symbol data into train/validation/test sets including symbol indices.

        Args:
            features: Feature tensor
            labels: Label tensor
            symbol_indices: Symbol index tensor
            validation_split: Validation split ratio
            split_config: Split configuration from strategy

        Returns:
            Tuple of (train_data, val_data, test_data) where each contains (features, labels, symbol_indices)
        """
        total_size = len(features)

        # Use strategy config if available, otherwise use validation_split
        if split_config:
            train_size = int(total_size * split_config["train"])
            val_size = int(total_size * split_config["validation"])
            test_size = total_size - train_size - val_size
        else:
            train_size = int(total_size * (1 - validation_split))
            val_size = total_size - train_size
            test_size = 0

        # Split data chronologically (important for time series)
        train_data = (
            features[:train_size],
            labels[:train_size],
            symbol_indices[:train_size],
        )
        val_data = (
            features[train_size : train_size + val_size],
            labels[train_size : train_size + val_size],
            symbol_indices[train_size : train_size + val_size],
        )

        if test_size > 0:
            test_data = (
                features[train_size + val_size :],
                labels[train_size + val_size :],
                symbol_indices[train_size + val_size :],
            )
        else:
            test_data = None

        return train_data, val_data, test_data
