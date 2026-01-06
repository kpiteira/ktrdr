"""
Integration test for full pipeline with new indicator format.

This test validates the complete flow from indicator computation
through feature caching and fuzzification, ensuring all components
work together with the new semantic column naming convention.

Tests cover:
- Indicator computation produces correct column names
- FeatureCache uses O(1) direct lookup
- FuzzyEngine works with both single and multi-output indicators
- End-to-end pipeline integration
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.indicators import IndicatorEngine, IndicatorFactory


def create_sample_ohlcv(rows: int = 200) -> pd.DataFrame:
    """
    Create sample OHLCV data for testing.

    Args:
        rows: Number of rows to generate

    Returns:
        DataFrame with OHLCV columns and datetime index
    """
    dates = pd.date_range("2024-01-01", periods=rows, freq="h")
    np.random.seed(42)  # For reproducible tests

    # Generate realistic price series with trend and volatility
    start_price = 1.0850  # Typical EURUSD range
    price_changes = np.random.normal(0, 1, rows)
    prices = [start_price]
    for change in price_changes[1:]:
        prices.append(prices[-1] * (1 + change * 0.001))  # 0.1% typical change

    # Generate high/low variations
    high_variations = np.abs(np.random.normal(0, 0.0005, rows))
    low_variations = np.abs(np.random.normal(0, 0.0005, rows))

    data = pd.DataFrame(
        {
            "open": prices,
            "high": [p * (1 + v) for p, v in zip(prices, high_variations)],
            "low": [p * (1 - v) for p, v in zip(prices, low_variations)],
            "close": prices,
            "volume": np.random.randint(1000, 10000, rows),
        },
        index=dates,
    )

    return data


@pytest.fixture
def sample_price_data():
    """Create sample OHLCV data for testing."""
    return create_sample_ohlcv(rows=200)


def test_full_pipeline_new_format(sample_price_data):
    """Test complete flow from indicators to fuzzification."""
    # 1. Create and apply indicators
    factory = IndicatorFactory(
        [
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
        ]
    )
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(sample_price_data)

    # 2. Verify column format (semantic names with indicator_id prefix)
    assert "rsi_14" in indicators_df.columns, "Missing single-output column"

    # Multi-output: dot notation columns
    assert "bbands_20_2.upper" in indicators_df.columns, "Missing multi-output column"
    assert "bbands_20_2.middle" in indicators_df.columns, "Missing multi-output column"
    assert "bbands_20_2.lower" in indicators_df.columns, "Missing multi-output column"
    assert "bbands_20_2" in indicators_df.columns, "Missing alias column"

    assert "macd_12_26_9.line" in indicators_df.columns, "Missing MACD line column"
    assert "macd_12_26_9.signal" in indicators_df.columns, "Missing MACD signal column"
    assert (
        "macd_12_26_9.histogram" in indicators_df.columns
    ), "Missing MACD histogram column"
    assert "macd_12_26_9" in indicators_df.columns, "Missing MACD alias column"

    # 3. Test FeatureCache with new format
    cache = FeatureCache.from_dataframe(indicators_df)
    idx = 50  # Test at a specific index with sufficient warmup

    # Single-output: direct lookup
    rsi_val = cache.get_indicator_value("rsi_14", idx)
    assert rsi_val is not None, "Failed to get RSI value"
    assert 0 <= rsi_val <= 100, f"RSI out of range: {rsi_val}"

    # Multi-output: dot notation lookup
    upper_val = cache.get_indicator_value("bbands_20_2.upper", idx)
    assert upper_val is not None, "Failed to get Bollinger upper band"
    assert upper_val > 0, f"Upper band should be positive: {upper_val}"

    middle_val = cache.get_indicator_value("bbands_20_2.middle", idx)
    assert middle_val is not None, "Failed to get Bollinger middle band"
    assert middle_val > 0, f"Middle band should be positive: {middle_val}"

    lower_val = cache.get_indicator_value("bbands_20_2.lower", idx)
    assert lower_val is not None, "Failed to get Bollinger lower band"
    assert lower_val > 0, f"Lower band should be positive: {lower_val}"

    # Verify band ordering (upper > middle > lower)
    assert upper_val > middle_val > lower_val, "Bollinger bands ordering incorrect"

    # Multi-output: alias lookup (should return primary output)
    bbands_alias_val = cache.get_indicator_value("bbands_20_2", idx)
    assert bbands_alias_val is not None, "Failed to get Bollinger alias"
    assert bbands_alias_val == upper_val, "Alias should return primary output (upper)"

    # MACD multi-output
    macd_line = cache.get_indicator_value("macd_12_26_9.line", idx)
    assert macd_line is not None, "Failed to get MACD line"

    macd_signal = cache.get_indicator_value("macd_12_26_9.signal", idx)
    assert macd_signal is not None, "Failed to get MACD signal"

    # 4. Test FuzzyEngine with new format
    fuzzy_config_dict = {
        "rsi_14": {
            "oversold": {"type": "triangular", "parameters": [0, 30, 40]},
            "overbought": {"type": "triangular", "parameters": [60, 70, 100]},
        },
        "bbands_20_2.upper": {
            "price_at_upper": {"type": "gaussian", "parameters": [0, 0.01]},
        },
        "bbands_20_2.lower": {
            "price_at_lower": {"type": "gaussian", "parameters": [0, 0.01]},
        },
    }

    fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_config_dict)
    fuzzy_engine = FuzzyEngine(fuzzy_config)

    # Fuzzify each indicator (per API design)
    rsi_fuzzy = fuzzy_engine.fuzzify("rsi_14", indicators_df["rsi_14"])
    bbands_upper_fuzzy = fuzzy_engine.fuzzify(
        "bbands_20_2.upper", indicators_df["bbands_20_2.upper"]
    )
    bbands_lower_fuzzy = fuzzy_engine.fuzzify(
        "bbands_20_2.lower", indicators_df["bbands_20_2.lower"]
    )

    # Verify fuzzy membership DataFrames were created
    assert isinstance(rsi_fuzzy, pd.DataFrame), "RSI fuzzify should return DataFrame"
    assert isinstance(
        bbands_upper_fuzzy, pd.DataFrame
    ), "Bollinger upper fuzzify should return DataFrame"
    assert isinstance(
        bbands_lower_fuzzy, pd.DataFrame
    ), "Bollinger lower fuzzify should return DataFrame"

    # Check for fuzzy set membership columns
    assert (
        "rsi_14_oversold" in rsi_fuzzy.columns
    ), "Missing RSI oversold fuzzy membership"
    assert (
        "rsi_14_overbought" in rsi_fuzzy.columns
    ), "Missing RSI overbought fuzzy membership"

    assert (
        "bbands_20_2.upper_price_at_upper" in bbands_upper_fuzzy.columns
    ), "Missing upper band fuzzy membership"
    assert (
        "bbands_20_2.lower_price_at_lower" in bbands_lower_fuzzy.columns
    ), "Missing lower band fuzzy membership"

    # Verify fuzzy memberships are in valid range [0, 1]
    for fuzzy_df in [rsi_fuzzy, bbands_upper_fuzzy, bbands_lower_fuzzy]:
        for col in fuzzy_df.columns:
            values = fuzzy_df[col].dropna()
            assert values.between(
                0, 1
            ).all(), f"Fuzzy membership {col} out of range [0, 1]"


def test_feature_cache_error_handling(sample_price_data):
    """Test that FeatureCache provides clear errors for missing columns."""
    factory = IndicatorFactory(
        [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
        ]
    )
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(sample_price_data)

    cache = FeatureCache.from_dataframe(indicators_df)

    # Test missing column error
    with pytest.raises(KeyError) as exc_info:
        cache.get_indicator_value("nonexistent_indicator", 50)

    # Error message should mention the column name
    assert "nonexistent_indicator" in str(exc_info.value).lower()


def test_fuzzy_engine_with_alias_reference(sample_price_data):
    """Test FuzzyEngine works with bare indicator_id (alias reference)."""
    factory = IndicatorFactory(
        [
            {
                "name": "bbands",
                "feature_id": "bbands_20_2",
                "period": 20,
                "multiplier": 2.0,
            },
        ]
    )
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(sample_price_data)

    # Reference multi-output indicator without dot notation
    # Should use alias column (primary output)
    fuzzy_config_dict = {
        "bbands_20_2": {  # Bare reference (alias)
            "at_band": {"type": "triangular", "parameters": [1.08, 1.09, 1.10]},
        }
    }

    fuzzy_config = FuzzyConfigLoader.load_from_dict(fuzzy_config_dict)
    fuzzy_engine = FuzzyEngine(fuzzy_config)

    # Fuzzify using alias column (bare indicator_id references primary output)
    fuzzy_df = fuzzy_engine.fuzzify("bbands_20_2", indicators_df["bbands_20_2"])

    # Should create fuzzy membership column
    assert isinstance(fuzzy_df, pd.DataFrame), "Fuzzify should return DataFrame"
    fuzzy_columns = [col for col in fuzzy_df.columns if "at_band" in col]
    assert len(fuzzy_columns) > 0, "Fuzzy engine failed with alias reference"
