"""Strategy training orchestrator that coordinates the complete training pipeline."""

import yaml
import pandas as pd
import torch
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import numpy as np

from .zigzag_labeler import ZigZagLabeler
from .feature_engineering import FeatureEngineer
from .model_trainer import ModelTrainer
from .model_storage import ModelStorage
from ..neural.models.mlp import MLPTradingModel
from ..data.data_manager import DataManager
from ..indicators.indicator_engine import IndicatorEngine
from ..fuzzy.engine import FuzzyEngine


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

    def train_strategy(
        self,
        strategy_config_path: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Train a complete neuro-fuzzy strategy.

        Args:
            strategy_config_path: Path to strategy YAML configuration
            symbol: Trading symbol to train on
            timeframe: Timeframe for training data
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Fraction of data to use for validation

        Returns:
            Dictionary with training results and model information
        """
        print(f"Starting training for {symbol} {timeframe} strategy...")

        # Load strategy configuration
        config = self._load_strategy_config(strategy_config_path)
        strategy_name = config["name"]

        print(f"Strategy: {strategy_name}")
        print(f"Data range: {start_date} to {end_date}")

        # Step 1: Load and prepare data
        print("\n1. Loading market data...")
        price_data = self._load_price_data(
            symbol, timeframe, start_date, end_date, data_mode
        )
        print(f"Loaded {len(price_data)} bars of data")

        # Step 2: Calculate indicators
        print("\n2. Calculating technical indicators...")
        indicators = self._calculate_indicators(price_data, config["indicators"])
        
        # DEBUG: Check indicators for NaN
        print(f"🔍 DEBUG: Indicators shape: {indicators.shape}")
        indicators_nan_count = indicators.isna().sum().sum()
        print(f"🔍 DEBUG: Indicators NaN count: {indicators_nan_count}")
        if indicators_nan_count > 0:
            print(f"🔍 DEBUG: Indicator columns with NaN:")
            for col in indicators.columns:
                nan_col_count = indicators[col].isna().sum()
                if nan_col_count > 0:
                    print(f"  - {col}: {nan_col_count} NaN values")
        
        print(f"Calculated {len(config['indicators'])} indicators")

        # Step 3: Generate fuzzy memberships
        print("\n3. Generating fuzzy memberships...")
        fuzzy_data = self._generate_fuzzy_memberships(indicators, config["fuzzy_sets"])
        print(f"Generated fuzzy sets for {len(config['fuzzy_sets'])} indicators")

        # Step 4: Engineer features
        print("\n4. Engineering features...")
        
        # DEBUG: Check fuzzy data for NaN
        print(f"🔍 DEBUG: Fuzzy data shape: {fuzzy_data.shape}")
        fuzzy_nan_count = fuzzy_data.isna().sum().sum()
        print(f"🔍 DEBUG: Fuzzy data NaN count: {fuzzy_nan_count}")
        if fuzzy_nan_count > 0:
            print(f"🔍 DEBUG: Fuzzy columns with NaN:")
            for col in fuzzy_data.columns:
                nan_col_count = fuzzy_data[col].isna().sum()
                if nan_col_count > 0:
                    print(f"  - {col}: {nan_col_count} NaN values")
        
        features, feature_names, feature_scaler = self._engineer_features(
            fuzzy_data,
            indicators,
            price_data,
            config.get("model", {}).get("features", {}),
        )
        
        # DEBUG: Check engineered features for NaN
        if hasattr(features, 'isna'):  # pandas DataFrame
            features_nan_count = features.isna().sum().sum()
            print(f"🔍 DEBUG: Engineered features NaN count: {features_nan_count}")
            if features_nan_count > 0:
                print(f"🔍 DEBUG: Feature columns with NaN:")
                for col in features.columns:
                    nan_col_count = features[col].isna().sum()
                    if nan_col_count > 0:
                        print(f"  - {col}: {nan_col_count} NaN values")
        else:  # numpy array or tensor
            features_nan_count = np.isnan(features).sum() if hasattr(features, 'shape') else 0
            print(f"🔍 DEBUG: Engineered features NaN count: {features_nan_count}")
            print(f"🔍 DEBUG: Features type: {type(features)}")
            if hasattr(features, 'shape'):
                print(f"🔍 DEBUG: Features shape: {features.shape}")
                print(f"🔍 DEBUG: Features min/max: {np.nanmin(features):.6f}/{np.nanmax(features):.6f}")
                print(f"🔍 DEBUG: Features contains inf: {np.isinf(features).any()}")
        
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

        # Step 7: Create and train neural network
        print("\n7. Training neural network...")
        
        # DEBUG: Check features for NaN values before training
        print(f"🔍 DEBUG: Features shape: {features.shape}")
        if hasattr(features, 'isna'):  # pandas DataFrame
            nan_count = features.isna().sum().sum()
            print(f"🔍 DEBUG: Total NaN values in features: {nan_count}")
            if nan_count > 0:
                print(f"🔍 DEBUG: Features with NaN:")
                for col in features.columns:
                    nan_col_count = features[col].isna().sum()
                    if nan_col_count > 0:
                        print(f"  - {col}: {nan_col_count} NaN values")
        else:  # numpy array or tensor
            nan_count = np.isnan(features).sum() if hasattr(features, 'shape') else 0
            print(f"🔍 DEBUG: Total NaN values in features: {nan_count}")
            print(f"🔍 DEBUG: Features type: {type(features)}")
            if hasattr(features, 'shape'):
                print(f"🔍 DEBUG: Features min/max: {np.nanmin(features):.6f}/{np.nanmax(features):.6f}")
                print(f"🔍 DEBUG: Features contains inf: {np.isinf(features).any()}")
        
        print(f"🔍 DEBUG: Train data X shape: {train_data[0].shape}, y shape: {train_data[1].shape}")
        print(f"🔍 DEBUG: Train X contains NaN: {np.isnan(train_data[0]).any()}")
        print(f"🔍 DEBUG: Train y contains NaN: {np.isnan(train_data[1]).any()}")
        print(f"🔍 DEBUG: Val X contains NaN: {np.isnan(val_data[0]).any()}")
        print(f"🔍 DEBUG: Val y contains NaN: {np.isnan(val_data[1]).any()}")
        
        # DEBUG: Check for extreme values that could cause overflow
        print(f"🔍 DEBUG: Train X min/max: {train_data[0].min():.6f}/{train_data[0].max():.6f}")
        print(f"🔍 DEBUG: Train X contains inf: {np.isinf(train_data[0]).any()}")
        if np.isinf(train_data[0]).any():
            inf_count = np.isinf(train_data[0]).sum()
            print(f"🔍 DEBUG: Train X has {inf_count} inf values")
        
        model = self._create_model(config["model"], features.shape[1])
        training_results = self._train_model(
            model, train_data, val_data, config["model"]["training"], progress_callback
        )

        # Step 8: Evaluate model
        print("\n8. Evaluating model...")
        test_metrics = self._evaluate_model(model, test_data)
        training_results.update(test_metrics)

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

        model_path = self.model_storage.save_model(
            model=model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            config=model_config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=feature_importance,
            scaler=feature_scaler,
        )

        print(f"\nTraining completed! Model saved to: {model_path}")

        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "feature_importance": feature_importance,
            "label_distribution": label_dist,
            "data_summary": {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "total_samples": len(features),
                "feature_count": features.shape[1],
            },
        }

    def _load_strategy_config(self, config_path: str) -> Dict[str, Any]:
        """Load strategy configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Strategy configuration dictionary
        """
        with open(config_path, "r") as f:
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
        timeframe: str,
        start_date: str,
        end_date: str,
        data_mode: str = "local",
    ) -> pd.DataFrame:
        """Load price data for training.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Start date
            end_date: End date

        Returns:
            OHLCV DataFrame
        """
        # Load data using specified mode
        data = self.data_manager.load_data(symbol, timeframe, mode=data_mode)

        # Filter by date range if possible
        if hasattr(data.index, "to_pydatetime"):
            # Convert dates to timezone-aware if the data index is timezone-aware
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)

            # Make dates timezone-aware if needed
            if data.index.tz is not None:
                if start.tz is None:
                    start = start.tz_localize("UTC")
                if end.tz is None:
                    end = end.tz_localize("UTC")

            data = data.loc[start:end]

        return data

    def _calculate_indicators(
        self, price_data: pd.DataFrame, indicator_configs: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """Calculate technical indicators.

        Args:
            price_data: OHLCV data
            indicator_configs: List of indicator configurations

        Returns:
            DataFrame with calculated indicators
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
            "macd": "MACD"
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
                    config["type"] = "".join(word.capitalize() for word in indicator_name.split("_"))
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
                    elif indicator_type == "BollingerBands":
                        # For Bollinger Bands, compute derived metrics
                        bb_cols = [c for c in indicator_results.columns if c.startswith("BollingerBands")]
                        if len(bb_cols) >= 3:  # Should have upper, middle, lower
                            upper_col = next((c for c in bb_cols if "upper" in c), None)
                            middle_col = next((c for c in bb_cols if "middle" in c), None)
                            lower_col = next((c for c in bb_cols if "lower" in c), None)
                            
                            if upper_col and middle_col and lower_col:
                                # Compute BB width as percentage of middle band (safe division)
                                upper_vals = indicator_results[upper_col]
                                lower_vals = indicator_results[lower_col] 
                                middle_vals = indicator_results[middle_col]
                                
                                # Safe division: avoid division by zero or very small values
                                mapped_results["bb_width"] = np.where(
                                    np.abs(middle_vals) > 1e-10,  # Avoid tiny denominators
                                    (upper_vals - lower_vals) / middle_vals,
                                    0.0  # Default width when middle is ~0
                                )
                        break
                    elif indicator_type == "KeltnerChannels":
                        # Store for later squeeze calculation
                        kc_cols = [c for c in indicator_results.columns if c.startswith("KeltnerChannels")]
                        if len(kc_cols) >= 3:
                            upper_col = next((c for c in kc_cols if "upper" in c), None)
                            lower_col = next((c for c in kc_cols if "lower" in c), None)
                            if upper_col and lower_col:
                                # Store KC bands for squeeze calculation
                                mapped_results["_kc_upper"] = indicator_results[upper_col]
                                mapped_results["_kc_lower"] = indicator_results[lower_col]
                        break
                    else:
                        # For other indicators, use the raw values
                        mapped_results[original_name] = indicator_results[col]
                        break

                    # If we found a non-MACD indicator, break
                    if indicator_type != "MACD":
                        break

        # Compute additional derived metrics
        # Volume ratio (current volume / volume SMA) - safe division
        if "volume" in mapped_results.columns and "volume_sma" in mapped_results.columns:
            volume_vals = mapped_results["volume"]
            volume_sma_vals = mapped_results["volume_sma"]
            
            # Safe division: avoid division by zero or very small values
            mapped_results["volume_ratio"] = np.where(
                np.abs(volume_sma_vals) > 1e-10,  # Avoid tiny denominators
                volume_vals / volume_sma_vals,
                1.0  # Default ratio when SMA is ~0
            )
        
        # Squeeze intensity (BB inside KC channels)
        if "bb_width" in mapped_results.columns and "_kc_upper" in mapped_results.columns and "_kc_lower" in mapped_results.columns:
            # Get BB bands for squeeze calculation
            bb_cols = [c for c in indicator_results.columns if c.startswith("BollingerBands")]
            if len(bb_cols) >= 3:
                bb_upper_col = next((c for c in bb_cols if "upper" in c), None)
                bb_lower_col = next((c for c in bb_cols if "lower" in c), None)
                
                if bb_upper_col and bb_lower_col:
                    # Squeeze occurs when BB is inside KC
                    bb_upper = indicator_results[bb_upper_col]
                    bb_lower = indicator_results[bb_lower_col]
                    kc_upper = mapped_results["_kc_upper"]
                    kc_lower = mapped_results["_kc_lower"]
                    
                    # Calculate squeeze intensity: 1.0 when BB completely inside KC, 0.0 when outside
                    # Safe division to avoid overflow when KC range is very small
                    kc_range = kc_upper - kc_lower
                    
                    # Only calculate when KC range is meaningful (not zero or tiny)
                    squeeze_intensity = np.where(
                        np.abs(kc_range) > 1e-10,  # Avoid tiny denominators
                        np.maximum(0, np.minimum(
                            (kc_upper - bb_upper) / kc_range,
                            (bb_lower - kc_lower) / kc_range
                        )),
                        0.0  # Default to no squeeze when KC range is ~0
                    )
                    mapped_results["squeeze_intensity"] = squeeze_intensity
        
        # Clean up temporary columns
        mapped_results = mapped_results.drop(columns=[col for col in mapped_results.columns if col.startswith("_")], errors='ignore')

        # Final safety check: replace any inf values with NaN, then fill NaN with 0
        # This prevents overflow from propagating to feature scaling
        mapped_results = mapped_results.replace([np.inf, -np.inf], np.nan)
        mapped_results = mapped_results.fillna(0.0)
        
        return mapped_results

    def _generate_fuzzy_memberships(
        self, indicators: pd.DataFrame, fuzzy_configs: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate fuzzy membership values.

        Args:
            indicators: Technical indicators DataFrame
            fuzzy_configs: Fuzzy set configurations

        Returns:
            DataFrame with fuzzy membership values
        """
        # Initialize fuzzy engine if not already done
        if self.fuzzy_engine is None:
            from ..fuzzy.config import FuzzyConfigLoader

            # The fuzzy_configs from strategy file are already in the correct format
            # Just pass them directly to FuzzyConfigLoader
            fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_configs)
            self.fuzzy_engine = FuzzyEngine(fuzzy_config)

        # Process each indicator
        fuzzy_results = {}
        for indicator_name, indicator_data in indicators.items():
            if indicator_name in fuzzy_configs:
                # Fuzzify the indicator
                membership_values = self.fuzzy_engine.fuzzify(
                    indicator_name, indicator_data
                )
                fuzzy_results.update(membership_values)

        return pd.DataFrame(fuzzy_results, index=indicators.index)

    def _engineer_features(
        self,
        fuzzy_data: pd.DataFrame,
        indicators: pd.DataFrame,
        price_data: pd.DataFrame,
        feature_config: Dict[str, Any],
    ) -> Tuple[torch.Tensor, List[str], Any]:
        """Engineer features for neural network training.

        Args:
            fuzzy_data: Fuzzy membership values
            indicators: Technical indicators
            price_data: OHLCV data
            feature_config: Feature engineering configuration

        Returns:
            Tuple of (features tensor, feature names, scaler)
        """
        engineer = FeatureEngineer(feature_config)
        features, feature_names = engineer.prepare_features(
            fuzzy_data, indicators, price_data
        )
        return features, feature_names, engineer.scaler

    def _generate_labels(
        self, price_data: pd.DataFrame, label_config: Dict[str, Any]
    ) -> torch.Tensor:
        """Generate training labels using ZigZag method.

        Args:
            price_data: OHLCV data
            label_config: Label generation configuration

        Returns:
            Tensor of labels
        """
        labeler = ZigZagLabeler(
            threshold=label_config["zigzag_threshold"],
            lookahead=label_config["label_lookahead"],
        )

        # Use segment-based labeling for better class balance
        # This should fix the neural network collapse issue
        print(
            "Using ZigZag segment labeling (balanced) instead of sparse extreme labeling..."
        )
        labels = labeler.generate_segment_labels(price_data)
        return torch.LongTensor(labels.values)

    def _get_label_distribution(self, labels: torch.Tensor) -> Dict[str, Any]:
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
        split_config: Dict[str, float],
    ) -> Tuple:
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
        self, model_config: Dict[str, Any], input_size: int
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
        train_data: Tuple,
        val_data: Tuple,
        training_config: Dict[str, Any],
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Train the neural network model.

        Args:
            model: Neural network model
            train_data: Training data tuple
            val_data: Validation data tuple
            training_config: Training configuration
            progress_callback: Optional callback for progress updates

        Returns:
            Training results
        """
        trainer = ModelTrainer(training_config, progress_callback=progress_callback)
        return trainer.train(
            model, train_data[0], train_data[1], val_data[0], val_data[1]
        )

    def _evaluate_model(
        self, model: torch.nn.Module, test_data: Optional[Tuple]
    ) -> Dict[str, Any]:
        """Evaluate model on test set.

        Args:
            model: Trained model
            test_data: Test data tuple

        Returns:
            Test metrics
        """
        if test_data is None:
            return {"test_accuracy": None, "test_loss": None}

        model.eval()
        with torch.no_grad():
            X_test, y_test = test_data
            outputs = model(X_test)

            # Calculate accuracy
            _, predicted = torch.max(outputs, 1)
            accuracy = (predicted == y_test).float().mean().item()

            # Calculate loss
            criterion = torch.nn.CrossEntropyLoss()
            loss = criterion(outputs, y_test).item()

        return {"test_accuracy": accuracy, "test_loss": loss}

    def _calculate_feature_importance(
        self,
        model: torch.nn.Module,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        feature_names: List[str],
    ) -> Dict[str, float]:
        """Calculate feature importance scores.

        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation labels
            feature_names: List of feature names

        Returns:
            Feature importance dictionary
        """
        engineer = FeatureEngineer({})
        engineer.feature_names = feature_names
        return engineer.calculate_feature_importance(model, X_val, y_val)
