"""Integration tests for complete multi-timeframe neuro-fuzzy pipeline."""

import pytest
import torch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
import tempfile
import os

from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.fuzzy.config import FuzzyConfig, FuzzyConfigLoader
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from ktrdr.training.multi_timeframe_feature_engineering import (
    MultiTimeframeFeatureEngineer,
)

# Removed adaptive components - they belong in future phases
from ktrdr.data.multi_timeframe_manager import MultiTimeframeDataManager


class TestCompleteNeuroFuzzyPipeline:
    """Test complete multi-timeframe neuro-fuzzy pipeline integration."""

    @pytest.fixture
    def sample_price_data(self):
        """Create sample multi-timeframe price data."""
        dates = pd.date_range("2024-01-01", "2024-01-31", freq="1h")

        # Generate realistic price data
        np.random.seed(42)
        base_price = 100.0
        price_changes = np.cumsum(np.random.normal(0, 0.01, len(dates)))
        prices = base_price + price_changes

        data = {
            "timestamp": dates,
            "open": prices * (1 + np.random.normal(0, 0.001, len(dates))),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.005, len(dates)))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.005, len(dates)))),
            "close": prices,
            "volume": np.random.randint(1000, 10000, len(dates)),
        }

        df_1h = pd.DataFrame(data)

        # Create 4h and 1d data by resampling
        df_4h = (
            df_1h.set_index("timestamp")
            .resample("4h")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .reset_index()
        )

        df_1d = (
            df_1h.set_index("timestamp")
            .resample("1d")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .reset_index()
        )

        return {"1h": df_1h, "4h": df_4h, "1d": df_1d}

    @pytest.fixture
    def sample_fuzzy_config(self):
        """Create sample fuzzy configuration."""
        config_dict = {
            "RSI": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                "neutral": {"type": "triangular", "parameters": [25, 50, 75]},
                "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
            },
            "SMA_cross": {
                "bullish": {
                    "type": "trapezoidal",
                    "parameters": [0.01, 0.02, 0.05, 0.1],
                },
                "neutral": {"type": "triangular", "parameters": [-0.01, 0, 0.01]},
                "bearish": {
                    "type": "trapezoidal",
                    "parameters": [-0.1, -0.05, -0.02, -0.01],
                },
            },
        }

        loader = FuzzyConfigLoader()
        return loader.load_from_dict(config_dict)

    @pytest.fixture
    def sample_neural_config(self):
        """Create sample neural network configuration."""
        return {
            "timeframe_configs": {
                "1h": {
                    "expected_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "weight": 1.0,
                    "enabled": True,
                },
                "4h": {
                    "expected_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "weight": 1.0,
                    "enabled": True,
                },
                "1d": {
                    "expected_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "weight": 1.0,
                    "enabled": True,
                },
            },
            "architecture": {
                "hidden_layers": [32, 16, 8],
                "dropout": 0.2,
                "activation": "relu",
                "batch_norm": False,  # Disabled for testing
                "output_activation": "softmax",
            },
            "training": {
                "learning_rate": 0.01,
                "batch_size": 16,
                "epochs": 10,  # Reduced for testing
                "early_stopping_patience": 5,
                "optimizer": "adam",
            },
            "feature_processing": {"scale_features": True, "scaler_type": "standard"},
        }

    @pytest.fixture
    def feature_engineer_config(self):
        """Create feature engineering configuration."""
        return {
            "timeframe_specs": {
                "1h": {
                    "fuzzy_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "indicator_features": [],
                    "weight": 1.0,
                    "enabled": True,
                },
                "4h": {
                    "fuzzy_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "indicator_features": [],
                    "weight": 1.0,
                    "enabled": True,
                },
                "1d": {
                    "fuzzy_features": [
                        "RSI_oversold",
                        "RSI_neutral",
                        "RSI_overbought",
                        "SMA_cross_bullish",
                        "SMA_cross_neutral",
                        "SMA_cross_bearish",
                    ],
                    "indicator_features": [],
                    "weight": 1.0,
                    "enabled": True,
                },
            },
            "validation": {"check_nan": True, "check_inf": True, "clip_outliers": True},
            "scaling": {"method": "standard", "per_timeframe": False},
        }

    def test_complete_pipeline_initialization(
        self, sample_fuzzy_config, sample_neural_config, feature_engineer_config
    ):
        """Test initialization of all pipeline components."""
        # Initialize fuzzy engine
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        assert fuzzy_engine is not None

        # Initialize neural network
        neural_model = MultiTimeframeMLP(sample_neural_config)
        assert neural_model is not None

        # Initialize feature engineer
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)
        assert feature_engineer is not None

        # Core components initialized successfully

    def test_data_flow_through_pipeline(
        self,
        sample_price_data,
        sample_fuzzy_config,
        sample_neural_config,
        feature_engineer_config,
    ):
        """Test complete data flow through the neuro-fuzzy pipeline."""

        # Step 1: Initialize components
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        neural_model = MultiTimeframeMLP(sample_neural_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Step 2: Generate sample indicators for each timeframe
        multi_timeframe_indicators = {}
        for timeframe, price_data in sample_price_data.items():
            # Calculate RSI
            close_prices = price_data["close"]
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            # Calculate SMA cross
            sma_fast = close_prices.rolling(window=10).mean()
            sma_slow = close_prices.rolling(window=20).mean()
            sma_cross = (sma_fast - sma_slow) / sma_slow

            indicators_df = pd.DataFrame(
                {"RSI": rsi, "SMA_cross": sma_cross}, index=price_data.index
            )

            multi_timeframe_indicators[timeframe] = indicators_df.fillna(0)

        # Step 3: Generate fuzzy membership values
        multi_timeframe_fuzzy = {}
        for timeframe, indicators in multi_timeframe_indicators.items():
            fuzzy_results = {}
            for _, row in indicators.iterrows():
                if pd.notna(row["RSI"]) and pd.notna(row["SMA_cross"]):
                    # Fuzzify each indicator separately and combine results
                    rsi_fuzzy = fuzzy_engine.fuzzify("RSI", row["RSI"])
                    sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", row["SMA_cross"])

                    # Combine the fuzzy results
                    fuzzy_result = {**rsi_fuzzy, **sma_fuzzy}
                    fuzzy_results[row.name] = fuzzy_result

            if fuzzy_results:
                # Convert to DataFrame
                fuzzy_df = pd.DataFrame.from_dict(fuzzy_results, orient="index")
                multi_timeframe_fuzzy[timeframe] = fuzzy_df

        assert len(multi_timeframe_fuzzy) == 3
        assert all(tf in multi_timeframe_fuzzy for tf in ["1h", "4h", "1d"])

        # Step 4: Prepare features for neural network
        if multi_timeframe_fuzzy:
            feature_result = feature_engineer.prepare_multi_timeframe_features(
                fuzzy_data=multi_timeframe_fuzzy, indicators=multi_timeframe_indicators
            )

            assert feature_result is not None
            assert feature_result.features_tensor is not None
            assert feature_result.feature_names is not None
            assert len(feature_result.features_tensor.shape) == 2  # Should be 2D

            # Step 5: Build and test neural network
            input_size = feature_result.features_tensor.shape[1]
            model = neural_model.build_model(input_size)
            assert model is not None

            # Test forward pass
            features_tensor = feature_result.features_tensor[:5]  # First 5 samples
            neural_model.model.eval()
            with torch.no_grad():
                output = neural_model.model(features_tensor)
                assert output.shape[0] == min(5, features_tensor.shape[0])  # Batch size
                assert output.shape[1] == 3  # Number of classes (BUY, HOLD, SELL)

    def test_neural_network_training_integration(
        self,
        sample_price_data,
        sample_fuzzy_config,
        sample_neural_config,
        feature_engineer_config,
    ):
        """Test neural network training with multi-timeframe fuzzy features."""

        # Initialize components
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        neural_model = MultiTimeframeMLP(sample_neural_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Generate training data
        training_features = []
        training_labels = []

        for timeframe, price_data in sample_price_data.items():
            # Calculate indicators
            close_prices = price_data["close"]
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            sma_fast = close_prices.rolling(window=10).mean()
            sma_slow = close_prices.rolling(window=20).mean()
            sma_cross = (sma_fast - sma_slow) / sma_slow

            indicators_df = pd.DataFrame(
                {"RSI": rsi, "SMA_cross": sma_cross}, index=price_data.index
            ).fillna(0)

            # Generate fuzzy membership values
            fuzzy_results = []
            for _, row in indicators_df.tail(50).iterrows():  # Last 50 samples
                # Fuzzify each indicator separately and combine results
                rsi_fuzzy = fuzzy_engine.fuzzify("RSI", row["RSI"])
                sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", row["SMA_cross"])

                # Combine the fuzzy results
                fuzzy_result = {**rsi_fuzzy, **sma_fuzzy}
                fuzzy_results.append(fuzzy_result)

            if fuzzy_results:
                fuzzy_df = pd.DataFrame(fuzzy_results)

                # For this timeframe only (simplified)
                timeframe_fuzzy = {timeframe: fuzzy_df}
                timeframe_indicators = {timeframe: indicators_df.tail(50)}

                feature_result = feature_engineer.prepare_multi_timeframe_features(
                    fuzzy_data=timeframe_fuzzy, indicators=timeframe_indicators
                )

                if feature_result.features_tensor is not None:
                    training_features.extend(feature_result.features_tensor.numpy())

                    # Generate synthetic labels based on price movement
                    price_changes = close_prices.tail(50).pct_change().fillna(0)
                    labels = []
                    for change in price_changes:
                        if change > 0.01:  # >1% up
                            labels.append(0)  # BUY
                        elif change < -0.01:  # >1% down
                            labels.append(2)  # SELL
                        else:
                            labels.append(1)  # HOLD

                    training_labels.extend(
                        labels[: len(feature_result.features_tensor)]
                    )

        # Convert to tensors
        if training_features and training_labels:
            X = torch.FloatTensor(np.array(training_features))
            y = torch.LongTensor(training_labels)

            # Ensure we have enough samples
            if len(X) >= 20:
                # Build model
                input_size = X.shape[1]
                model = neural_model.build_model(input_size)

                # Train model (reduced epochs for testing)
                training_result = neural_model.train(X, y)

                assert training_result is not None
                assert "train_loss" in training_result.training_history
                assert "train_accuracy" in training_result.training_history
                assert len(training_result.training_history["train_loss"]) > 0
                assert neural_model.is_trained

    def test_core_fuzzy_engine_functionality(self, sample_fuzzy_config):
        """Test core fuzzy engine functionality without adaptive features."""

        # Initialize standard fuzzy engine
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)

        # Test basic fuzzy operations
        rsi_result = fuzzy_engine.fuzzify("RSI", 30)
        assert rsi_result is not None
        assert "RSI_oversold" in rsi_result
        assert "RSI_neutral" in rsi_result
        assert "RSI_overbought" in rsi_result

        sma_result = fuzzy_engine.fuzzify("SMA_cross", 0.02)
        assert sma_result is not None
        assert "SMA_cross_bullish" in sma_result
        assert "SMA_cross_neutral" in sma_result
        assert "SMA_cross_bearish" in sma_result

        # Verify membership values are in valid range
        for value in rsi_result.values():
            assert 0 <= value <= 1
        for value in sma_result.values():
            assert 0 <= value <= 1

    def test_neural_network_prediction_consistency(
        self,
        sample_price_data,
        sample_fuzzy_config,
        sample_neural_config,
        feature_engineer_config,
    ):
        """Test neural network prediction consistency."""

        # Initialize components
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        neural_model = MultiTimeframeMLP(sample_neural_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Generate simple fuzzy data
        fuzzy_data = {}
        for timeframe in ["1h", "4h", "1d"]:
            rsi_fuzzy = fuzzy_engine.fuzzify("RSI", 50)  # Neutral RSI
            sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", 0)  # Neutral SMA
            combined = {**rsi_fuzzy, **sma_fuzzy}
            fuzzy_data[timeframe] = pd.DataFrame([combined])

        # Prepare features
        feature_result = feature_engineer.prepare_multi_timeframe_features(
            fuzzy_data=fuzzy_data
        )

        # Build and train model with minimal data
        input_size = feature_result.features_tensor.shape[1]
        neural_model.build_model(input_size)

        # Minimal training
        X = feature_result.features_tensor
        y = torch.LongTensor([1])  # HOLD
        neural_model.train(X, y)

        # Test prediction consistency
        prediction1 = neural_model.predict(feature_result.features_tensor)
        prediction2 = neural_model.predict(feature_result.features_tensor)

        assert prediction1["signal"] == prediction2["signal"]
        assert abs(prediction1["confidence"] - prediction2["confidence"]) < 0.001

    def test_multi_timeframe_feature_consistency(
        self, sample_fuzzy_config, feature_engineer_config
    ):
        """Test multi-timeframe feature preparation consistency."""

        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Generate consistent fuzzy data across timeframes
        test_values = [
            {"RSI": 30, "SMA_cross": 0.02},  # Oversold + bullish
            {"RSI": 50, "SMA_cross": 0.0},  # Neutral
            {"RSI": 70, "SMA_cross": -0.02},  # Overbought + bearish
        ]

        for test_value in test_values:
            fuzzy_data = {}
            for timeframe in ["1h", "4h", "1d"]:
                rsi_fuzzy = fuzzy_engine.fuzzify("RSI", test_value["RSI"])
                sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", test_value["SMA_cross"])
                combined = {**rsi_fuzzy, **sma_fuzzy}
                fuzzy_data[timeframe] = pd.DataFrame([combined])

            # Test feature preparation
            result = feature_engineer.prepare_multi_timeframe_features(
                fuzzy_data=fuzzy_data
            )

            assert result is not None
            assert result.features_tensor is not None
            assert len(result.feature_names) == result.features_tensor.shape[1]

            # Test that features are in valid range
            features = result.features_tensor.numpy()
            assert np.all(features >= -5)  # Reasonable bounds after scaling
            assert np.all(features <= 5)

    def test_end_to_end_pipeline_execution(
        self,
        sample_price_data,
        sample_fuzzy_config,
        sample_neural_config,
        feature_engineer_config,
    ):
        """Test complete end-to-end pipeline execution."""

        # Initialize core components
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        neural_model = MultiTimeframeMLP(sample_neural_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Process sample data through complete pipeline
        symbol = "AAPL"

        for i in range(min(10, len(sample_price_data["1h"]) - 20)):
            # Get current data slice
            current_data = {}
            for tf, data in sample_price_data.items():
                current_data[tf] = data.iloc[: 20 + i]  # Progressive data

            # Step 1: Calculate indicators
            multi_timeframe_indicators = {}
            for timeframe, price_data in current_data.items():
                close_prices = price_data["close"]

                # Calculate RSI
                if len(close_prices) >= 14:
                    delta = close_prices.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = pd.Series([50] * len(close_prices), index=close_prices.index)

                # Calculate SMA cross
                if len(close_prices) >= 20:
                    sma_fast = close_prices.rolling(window=10).mean()
                    sma_slow = close_prices.rolling(window=20).mean()
                    sma_cross = (sma_fast - sma_slow) / sma_slow
                else:
                    sma_cross = pd.Series(
                        [0] * len(close_prices), index=close_prices.index
                    )

                indicators_df = pd.DataFrame(
                    {"RSI": rsi, "SMA_cross": sma_cross}, index=price_data.index
                ).fillna(0)

                multi_timeframe_indicators[timeframe] = indicators_df

            # Step 2: Generate fuzzy signals (no regime detection in Phase 5)
            if len(multi_timeframe_indicators["1h"]) > 0:
                latest_indicators = {
                    tf: indicators.iloc[-1]
                    for tf, indicators in multi_timeframe_indicators.items()
                }

                # Generate fuzzy membership values
                multi_timeframe_fuzzy = {}
                for timeframe, latest_indicator in latest_indicators.items():
                    # Fuzzify each indicator separately and combine results
                    rsi_fuzzy = fuzzy_engine.fuzzify("RSI", latest_indicator["RSI"])
                    sma_fuzzy = fuzzy_engine.fuzzify(
                        "SMA_cross", latest_indicator["SMA_cross"]
                    )

                    # Combine the fuzzy results
                    fuzzy_result = {**rsi_fuzzy, **sma_fuzzy}
                    multi_timeframe_fuzzy[timeframe] = pd.DataFrame([fuzzy_result])

                # Step 4: Prepare neural network features
                feature_result = feature_engineer.prepare_multi_timeframe_features(
                    fuzzy_data=multi_timeframe_fuzzy,
                    indicators={
                        tf: pd.DataFrame([indicators.iloc[-1]])
                        for tf, indicators in multi_timeframe_indicators.items()
                    },
                )

                if feature_result.features_tensor is not None and i == 0:
                    # Build neural network on first iteration
                    input_size = feature_result.features_tensor.shape[1]
                    neural_model.build_model(input_size)

                    # Create minimal training data for testing
                    X = feature_result.features_tensor
                    y = torch.LongTensor([1])  # HOLD signal
                    neural_model.train(X, y)  # Minimal training

                # Step 5: Generate neural prediction
                if (
                    neural_model.is_trained
                    and feature_result.features_tensor is not None
                ):
                    features_tensor = feature_result.features_tensor
                    prediction = neural_model.predict_with_timeframe_breakdown(
                        features_tensor
                    )

                    # Step 6: Make trading decision
                    signal_type = prediction["signal"]
                    confidence = prediction["confidence"]

                    # Step 7: Validate prediction
                    assert signal_type in ["BUY", "HOLD", "SELL"]
                    assert 0 <= confidence <= 1

                    # Test that we can generate consistent predictions
                    prediction2 = neural_model.predict_with_timeframe_breakdown(
                        features_tensor
                    )
                    assert prediction2["signal"] == signal_type

        # Test completed successfully - core pipeline works without adaptive components

    def test_pipeline_error_handling(self, sample_fuzzy_config, sample_neural_config):
        """Test pipeline robustness with edge cases and errors."""

        # Test with empty fuzzy data
        feature_engineer_config = {
            "timeframe_specs": {
                "1h": {"fuzzy_features": ["RSI_oversold"], "enabled": True}
            }
        }
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Should handle empty data gracefully
        try:
            result = feature_engineer.prepare_multi_timeframe_features(fuzzy_data={})
            # Should either return None or raise appropriate error
        except ValueError as e:
            assert "No features extracted" in str(e)

        # Test with invalid neural config
        invalid_config = sample_neural_config.copy()
        invalid_config["architecture"]["hidden_layers"] = []  # No hidden layers

        neural_model = MultiTimeframeMLP(invalid_config)
        model = neural_model.build_model(10)  # Should still work with just output layer
        assert model is not None

        # Test with missing timeframe data
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)

        # Fuzzify each indicator separately
        rsi_fuzzy = fuzzy_engine.fuzzify("RSI", 50)
        sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", 0)
        assert rsi_fuzzy is not None
        assert sma_fuzzy is not None

        # Verify fuzzy values are in valid range
        for value in rsi_fuzzy.values():
            assert 0 <= value <= 1
        for value in sma_fuzzy.values():
            assert 0 <= value <= 1

    def test_component_integration_consistency(
        self,
        sample_price_data,
        sample_fuzzy_config,
        sample_neural_config,
        feature_engineer_config,
    ):
        """Test consistency of data flow between components."""

        # Initialize components
        fuzzy_engine = FuzzyEngine(sample_fuzzy_config)
        neural_model = MultiTimeframeMLP(sample_neural_config)
        feature_engineer = MultiTimeframeFeatureEngineer(feature_engineer_config)

        # Generate consistent indicators
        timeframes = ["1h", "4h", "1d"]
        multi_timeframe_indicators = {}

        for tf in timeframes:
            if tf in sample_price_data:
                price_data = sample_price_data[tf]
                close_prices = price_data["close"]

                # Calculate indicators consistently
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

                sma_fast = close_prices.rolling(window=10).mean()
                sma_slow = close_prices.rolling(window=20).mean()
                sma_cross = (sma_fast - sma_slow) / sma_slow

                indicators_df = pd.DataFrame(
                    {"RSI": rsi, "SMA_cross": sma_cross}, index=price_data.index
                ).fillna(0)

                multi_timeframe_indicators[tf] = indicators_df

        # Generate fuzzy data for multiple time points
        num_samples = 5
        all_fuzzy_data = {}

        for tf, indicators in multi_timeframe_indicators.items():
            fuzzy_samples = []
            for i in range(max(0, len(indicators) - num_samples), len(indicators)):
                if i >= 0:
                    row = indicators.iloc[i]
                    # Fuzzify each indicator separately and combine results
                    rsi_fuzzy = fuzzy_engine.fuzzify("RSI", row["RSI"])
                    sma_fuzzy = fuzzy_engine.fuzzify("SMA_cross", row["SMA_cross"])

                    # Combine the fuzzy results
                    fuzzy_result = {**rsi_fuzzy, **sma_fuzzy}
                    fuzzy_samples.append(fuzzy_result)

            if fuzzy_samples:
                all_fuzzy_data[tf] = pd.DataFrame(fuzzy_samples)

        # Test feature engineering consistency
        if all_fuzzy_data:
            feature_result = feature_engineer.prepare_multi_timeframe_features(
                fuzzy_data=all_fuzzy_data, indicators=multi_timeframe_indicators
            )

            assert feature_result is not None

            # Verify feature dimensions are consistent with model expectations
            expected_features_per_tf = len(
                sample_neural_config["timeframe_configs"]["1h"]["expected_features"]
            )
            expected_total_features = expected_features_per_tf * len(timeframes)

            if feature_result.features_tensor is not None:
                assert (
                    feature_result.features_tensor.shape[1] == expected_total_features
                )

                # Test neural network can handle these features
                input_size = feature_result.features_tensor.shape[1]
                model = neural_model.build_model(input_size)

                # Test forward pass
                features_tensor = feature_result.features_tensor[:1]
                neural_model.model.eval()
                with torch.no_grad():
                    output = neural_model.model(features_tensor)
                    assert output.shape == (1, 3)  # Single sample, 3 classes

                    # Verify output is a valid probability distribution
                    assert torch.allclose(output.sum(dim=1), torch.ones(1), atol=1e-6)
                    assert (output >= 0).all()
                    assert (output <= 1).all()
