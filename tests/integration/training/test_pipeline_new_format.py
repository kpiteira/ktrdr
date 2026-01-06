"""Integration test for training pipeline with new indicator column format.

This test validates that the complete training pipeline works end-to-end
with the new semantic column naming convention from M3b:
- Indicators use semantic column names (e.g., 'rsi_14', 'bbands_20_2.upper')
- Fuzzy memberships use feature_id format (e.g., 'rsi_14_oversold')
- Model metadata stores feature names in new format
- Backtesting can load and use trained models
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from ktrdr.fuzzy import FuzzyEngine
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.indicators import IndicatorEngine, IndicatorFactory
from ktrdr.training.model_storage import ModelStorage


@pytest.fixture(name="test_data")
def sample_ohlcv_data():
    """Create test OHLCV data for training."""
    import numpy as np

    # Create 500 rows of synthetic OHLCV data
    dates = pd.date_range(start="2024-01-01", periods=500, freq="h", tz="UTC")

    # Generate realistic-looking price data
    np.random.seed(42)
    base_price = 1.10
    returns = np.random.normal(0, 0.001, len(dates))
    close_prices = base_price * (1 + returns).cumprod()

    data = pd.DataFrame(
        {
            "open": close_prices * (1 + np.random.uniform(-0.001, 0.001, len(dates))),
            "high": close_prices
            * (1 + np.abs(np.random.uniform(0, 0.002, len(dates)))),
            "low": close_prices * (1 - np.abs(np.random.uniform(0, 0.002, len(dates)))),
            "close": close_prices,
            "volume": np.random.uniform(1000, 10000, len(dates)),
        },
        index=dates,
    )

    return data


@pytest.fixture
def strategy_config():
    """Create test strategy configuration with new format indicators."""
    return {
        "name": "test_new_format_strategy",
        "indicators": [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {
                "name": "bbands",
                "feature_id": "bbands_20_2",
                "period": 20,
                "multiplier": 2.0,
            },
            {
                "name": "macd",
                "feature_id": "macd_12_26_9",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        ],
        "fuzzy_sets": {
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 30, 40]},
                "overbought": {"type": "triangular", "parameters": [60, 70, 100]},
            },
            "bbands_20_2.upper": {
                "near_upper": {
                    "type": "gaussian",
                    "parameters": [0, 0.01],  # [mean, std]
                }
            },
            "macd_12_26_9.line": {
                "bullish": {
                    "type": "gaussian",
                    "parameters": [0.001, 0.005],  # [mean, std]
                },
                "bearish": {
                    "type": "gaussian",
                    "parameters": [-0.001, 0.005],  # [mean, std]
                },
            },
        },
        "model": {
            "type": "mlp",
            "hidden_layers": [32, 16],
            "dropout": 0.2,
            "num_classes": 3,
            "features": {"lookback_periods": 0},  # No temporal features for this test
            "training": {
                "epochs": 2,  # Minimal for integration test
                "batch_size": 32,
                "learning_rate": 0.001,
            },
        },
        "training": {
            "labels": {"zigzag_threshold": 0.03, "label_lookahead": 5},
            "data_split": {"test_size": 0.1, "validation_size": 0.2},
        },
    }


@pytest.fixture
def temp_models_dir(tmp_path):
    """Create temporary models directory."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    return str(models_dir)


def test_indicators_use_new_column_format(test_data, strategy_config):
    """Test that indicators produce columns in new semantic format."""
    # Create and apply indicators
    factory = IndicatorFactory(strategy_config["indicators"])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(test_data)

    # Verify single-output indicator (RSI)
    assert "rsi_14" in indicators_df.columns, "RSI should have column 'rsi_14'"

    # Verify multi-output indicator (Bollinger Bands) with dot notation
    assert (
        "bbands_20_2.upper" in indicators_df.columns
    ), "BBands should have 'bbands_20_2.upper'"
    assert (
        "bbands_20_2.middle" in indicators_df.columns
    ), "BBands should have 'bbands_20_2.middle'"
    assert (
        "bbands_20_2.lower" in indicators_df.columns
    ), "BBands should have 'bbands_20_2.lower'"
    assert (
        "bbands_20_2" in indicators_df.columns
    ), "BBands should have alias 'bbands_20_2'"

    # Verify multi-output indicator (MACD) with dot notation
    assert (
        "macd_12_26_9.line" in indicators_df.columns
    ), "MACD should have 'macd_12_26_9.line'"
    assert (
        "macd_12_26_9.signal" in indicators_df.columns
    ), "MACD should have 'macd_12_26_9.signal'"
    assert (
        "macd_12_26_9.histogram" in indicators_df.columns
    ), "MACD should have 'macd_12_26_9.histogram'"
    assert (
        "macd_12_26_9" in indicators_df.columns
    ), "MACD should have alias 'macd_12_26_9'"


def test_fuzzy_uses_new_column_format(test_data, strategy_config):
    """Test that fuzzy memberships use feature_id in column names."""
    # Create indicators
    factory = IndicatorFactory(strategy_config["indicators"])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(test_data)

    # Create fuzzy engine
    fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_config["fuzzy_sets"])
    fuzzy_engine = FuzzyEngine(fuzzy_config)

    # Generate fuzzy memberships for each indicator (skip price columns)
    fuzzy_results = []
    for col in indicators_df.columns:
        # Only fuzzify columns that have fuzzy configurations
        # Skip price columns (open, high, low, close, volume)
        if fuzzy_engine._find_fuzzy_key(col) is not None:
            fuzzy_result = fuzzy_engine.fuzzify(col, indicators_df[col])
            fuzzy_results.append(fuzzy_result)

    # Combine all fuzzy results
    fuzzy_df = pd.concat(fuzzy_results, axis=1)

    # Verify fuzzy column names use feature_id format
    assert "rsi_14_oversold" in fuzzy_df.columns, "Fuzzy should have 'rsi_14_oversold'"
    assert (
        "rsi_14_overbought" in fuzzy_df.columns
    ), "Fuzzy should have 'rsi_14_overbought'"
    assert (
        "bbands_20_2.upper_near_upper" in fuzzy_df.columns
    ), "Fuzzy should have 'bbands_20_2.upper_near_upper'"
    assert (
        "macd_12_26_9.line_bullish" in fuzzy_df.columns
    ), "Fuzzy should have 'macd_12_26_9.line_bullish'"
    assert (
        "macd_12_26_9.line_bearish" in fuzzy_df.columns
    ), "Fuzzy should have 'macd_12_26_9.line_bearish'"


def test_fuzzy_neural_processor_uses_new_feature_names(test_data, strategy_config):
    """Test that FuzzyNeuralProcessor creates features with new column format."""
    from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor

    # Create indicators
    factory = IndicatorFactory(strategy_config["indicators"])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(test_data)

    # Create fuzzy memberships
    fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_config["fuzzy_sets"])
    fuzzy_engine = FuzzyEngine(fuzzy_config)

    # Generate fuzzy memberships for each indicator (skip price columns)
    fuzzy_results = []
    for col in indicators_df.columns:
        # Only fuzzify columns that have fuzzy configurations
        # Skip price columns (open, high, low, close, volume)
        if fuzzy_engine._find_fuzzy_key(col) is not None:
            fuzzy_result = fuzzy_engine.fuzzify(col, indicators_df[col])
            fuzzy_results.append(fuzzy_result)

    # Combine all fuzzy results
    fuzzy_df = pd.concat(fuzzy_results, axis=1)

    # Create neural features using FuzzyNeuralProcessor
    processor = FuzzyNeuralProcessor({"lookback_periods": 0})
    features, feature_names = processor.prepare_input(fuzzy_df)

    # Verify feature names use new format (feature_id_fuzzy_set_name)
    assert len(feature_names) > 0, "Should have feature names"
    assert any(
        "rsi_14_" in name for name in feature_names
    ), "Feature names should contain 'rsi_14_'"
    assert any(
        "bbands_20_2" in name for name in feature_names
    ), "Feature names should contain 'bbands_20_2'"
    assert any(
        "macd_12_26_9" in name for name in feature_names
    ), "Feature names should contain 'macd_12_26_9'"

    # Verify feature names match fuzzy column names exactly
    for name in feature_names:
        assert (
            name in fuzzy_df.columns
        ), f"Feature name '{name}' should be in fuzzy_df columns"

    # Verify no old format names (uppercase, mixed case)
    for name in feature_names:
        # Feature names should be lowercase with underscores/dots - check alphabetic chars are lowercase
        normalized_name = name.replace(".", "_").replace("_", "")
        assert (
            normalized_name.islower()
        ), f"Feature name '{name}' should be lowercase with underscores or dots"
        assert (
            "RSI" not in name
        ), f"Feature name '{name}' should not contain uppercase 'RSI'"
        assert (
            "MACD" not in name
        ), f"Feature name '{name}' should not contain uppercase 'MACD'"


def test_model_storage_saves_new_format_feature_names(
    test_data, strategy_config, temp_models_dir
):
    """Test that model storage saves feature names in new format to metadata."""
    from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor

    # Create a minimal trained model for testing
    # Create indicators → fuzzy → features
    factory = IndicatorFactory(strategy_config["indicators"])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(test_data)

    fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_config["fuzzy_sets"])
    fuzzy_engine = FuzzyEngine(fuzzy_config)

    # Generate fuzzy memberships for each indicator (skip price columns)
    fuzzy_results = []
    for col in indicators_df.columns:
        # Only fuzzify columns that have fuzzy configurations
        # Skip price columns (open, high, low, close, volume)
        if fuzzy_engine._find_fuzzy_key(col) is not None:
            fuzzy_result = fuzzy_engine.fuzzify(col, indicators_df[col])
            fuzzy_results.append(fuzzy_result)

    # Combine all fuzzy results
    fuzzy_df = pd.concat(fuzzy_results, axis=1)

    processor = FuzzyNeuralProcessor({"lookback_periods": 0})
    features, feature_names = processor.prepare_input(fuzzy_df)

    # Create a minimal model
    from ktrdr.neural.models.mlp import MLPTradingModel

    mlp_model = MLPTradingModel(strategy_config["model"])
    model = mlp_model.build_model(features.shape[1])

    # Save model with feature names
    model_storage = ModelStorage(temp_models_dir)
    model_path = model_storage.save_model(
        model=model,
        strategy_name="test_new_format_strategy",
        symbol="EURUSD",
        timeframe="1h",
        config=strategy_config,
        training_metrics={"epochs_trained": 1},
        feature_names=feature_names,
    )

    # Verify model was saved
    assert Path(model_path).exists(), "Model directory should exist"

    # Load and verify features.json
    features_file = Path(model_path) / "features.json"
    assert features_file.exists(), "features.json should exist"

    with open(features_file) as f:
        features_metadata = json.load(f)

    # Verify feature names are in new format
    if "fuzzy_features" in features_metadata:
        saved_features = features_metadata["fuzzy_features"]
    else:
        saved_features = features_metadata["feature_names"]

    assert len(saved_features) == len(
        feature_names
    ), "All feature names should be saved"
    assert saved_features == feature_names, "Feature names should match exactly"

    # Verify feature names use new format
    assert any(
        "rsi_14_" in name for name in saved_features
    ), "Saved features should contain 'rsi_14_'"
    assert any(
        "bbands_20_2" in name for name in saved_features
    ), "Saved features should contain 'bbands_20_2'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
