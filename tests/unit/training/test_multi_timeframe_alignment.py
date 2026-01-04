"""Tests for multi-timeframe data alignment in training pipeline.

These tests verify that:
1. 1h and 5m data align correctly
2. Features are prefixed with timeframe to avoid collision
3. Edge cases (5m bars at 1h boundaries) are handled correctly
"""

import numpy as np
import pandas as pd
import pytest
import torch

from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor


@pytest.fixture
def sample_1h_fuzzy_data() -> pd.DataFrame:
    """Create sample 1h fuzzy data with typical fuzzy membership columns."""
    # 24 hourly bars for one day
    timestamps = pd.date_range("2024-01-01 00:00", periods=24, freq="1h", tz="UTC")

    # Fuzzy membership values for RSI (low, neutral, high)
    data = {
        "rsi_low": np.random.uniform(0, 1, 24),
        "rsi_neutral": np.random.uniform(0, 1, 24),
        "rsi_high": np.random.uniform(0, 1, 24),
    }

    return pd.DataFrame(data, index=timestamps)


@pytest.fixture
def sample_5m_fuzzy_data() -> pd.DataFrame:
    """Create sample 5m fuzzy data with typical fuzzy membership columns."""
    # 288 5-minute bars for one day (24 hours * 12 bars/hour)
    timestamps = pd.date_range("2024-01-01 00:00", periods=288, freq="5min", tz="UTC")

    # Fuzzy membership values for RSI (low, neutral, high)
    data = {
        "rsi_low": np.random.uniform(0, 1, 288),
        "rsi_neutral": np.random.uniform(0, 1, 288),
        "rsi_high": np.random.uniform(0, 1, 288),
    }

    return pd.DataFrame(data, index=timestamps)


@pytest.fixture
def processor() -> FuzzyNeuralProcessor:
    """Create FuzzyNeuralProcessor with minimal config."""
    config = {
        "lookback_periods": 0,  # No temporal features for simpler testing
    }
    return FuzzyNeuralProcessor(config)


class TestMultiTimeframeAlignment:
    """Tests for multi-timeframe feature alignment."""

    def test_single_timeframe_passthrough(
        self, processor: FuzzyNeuralProcessor, sample_1h_fuzzy_data: pd.DataFrame
    ):
        """Single timeframe should pass through without modification."""
        multi_fuzzy = {"1h": sample_1h_fuzzy_data}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # Should have same number of samples
        assert features.shape[0] == len(sample_1h_fuzzy_data)

        # Should have same number of features
        assert features.shape[1] == len(sample_1h_fuzzy_data.columns)

    def test_multi_timeframe_aligns_to_base(
        self,
        processor: FuzzyNeuralProcessor,
        sample_1h_fuzzy_data: pd.DataFrame,
        sample_5m_fuzzy_data: pd.DataFrame,
    ):
        """Multi-timeframe should align to base (lowest frequency in list)."""
        # 5m should be base (higher frequency = more rows)
        multi_fuzzy = {"5m": sample_5m_fuzzy_data, "1h": sample_1h_fuzzy_data}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # Should have 5m row count (288 bars, the base timeframe)
        assert features.shape[0] == len(sample_5m_fuzzy_data)

        # Should have combined features from both timeframes
        # 5m: 3 features + 1h: 3 features = 6 total
        assert features.shape[1] == 6

    def test_feature_names_prefixed_with_timeframe(
        self,
        processor: FuzzyNeuralProcessor,
        sample_1h_fuzzy_data: pd.DataFrame,
        sample_5m_fuzzy_data: pd.DataFrame,
    ):
        """Feature names should be prefixed with timeframe to avoid collision."""
        multi_fuzzy = {"5m": sample_5m_fuzzy_data, "1h": sample_1h_fuzzy_data}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # All names should have timeframe prefix
        for name in names:
            assert name.startswith("5m_") or name.startswith("1h_"), (
                f"Feature name '{name}' missing timeframe prefix"
            )

        # Should have no duplicates
        assert len(names) == len(set(names)), "Feature names should be unique"

        # Should have both timeframe prefixes
        assert any(name.startswith("5m_") for name in names)
        assert any(name.startswith("1h_") for name in names)

    def test_no_nan_values_in_output(
        self,
        processor: FuzzyNeuralProcessor,
        sample_1h_fuzzy_data: pd.DataFrame,
        sample_5m_fuzzy_data: pd.DataFrame,
    ):
        """Aligned features should have no NaN values."""
        multi_fuzzy = {"5m": sample_5m_fuzzy_data, "1h": sample_1h_fuzzy_data}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # No NaN values in output
        assert not torch.isnan(features).any(), "Output features contain NaN values"

    def test_1h_values_forward_filled_to_5m(
        self,
        processor: FuzzyNeuralProcessor,
        sample_5m_fuzzy_data: pd.DataFrame,
    ):
        """1h features should be forward-filled to match 5m timestamps."""
        # Create minimal 1h data with known values
        timestamps_1h = pd.date_range(
            "2024-01-01 00:00", periods=2, freq="1h", tz="UTC"
        )
        data_1h = pd.DataFrame(
            {
                "rsi_low": [0.1, 0.9],  # Changes at hour boundary
                "rsi_neutral": [0.5, 0.5],
                "rsi_high": [0.4, 0.1],
            },
            index=timestamps_1h,
        )

        # Create 5m data covering the same period (24 5-minute bars = 2 hours)
        timestamps_5m = pd.date_range(
            "2024-01-01 00:00", periods=24, freq="5min", tz="UTC"
        )
        data_5m = pd.DataFrame(
            {
                "rsi_low": np.ones(24) * 0.3,
                "rsi_neutral": np.ones(24) * 0.4,
                "rsi_high": np.ones(24) * 0.3,
            },
            index=timestamps_5m,
        )

        multi_fuzzy = {"5m": data_5m, "1h": data_1h}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # Find 1h_rsi_low column index
        rsi_low_1h_idx = names.index("1h_rsi_low")

        # First 12 5m bars (0:00-0:55) should have 1h value 0.1
        for i in range(12):
            assert features[i, rsi_low_1h_idx].item() == pytest.approx(0.1, abs=0.01), (
                f"Row {i} should have forward-filled value 0.1"
            )

        # Next 12 5m bars (1:00-1:55) should have 1h value 0.9
        for i in range(12, 24):
            assert features[i, rsi_low_1h_idx].item() == pytest.approx(0.9, abs=0.01), (
                f"Row {i} should have forward-filled value 0.9"
            )

    def test_5m_at_1h_boundary_uses_correct_1h_bar(
        self,
        processor: FuzzyNeuralProcessor,
    ):
        """5m bars at exact 1h boundaries should use that hour's values."""
        # Create 1h data with fuzzy-like column names
        timestamps_1h = pd.date_range(
            "2024-01-01 00:00", periods=3, freq="1h", tz="UTC"
        )
        data_1h = pd.DataFrame(
            {
                "rsi_low": [1.0, 2.0, 3.0],  # Clear distinction between hours
                "rsi_high": [0.0, 0.0, 0.0],
            },
            index=timestamps_1h,
        )

        # Create 5m data covering 2 hours with fuzzy-like column names
        timestamps_5m = pd.date_range(
            "2024-01-01 00:00", periods=24, freq="5min", tz="UTC"
        )
        data_5m = pd.DataFrame(
            {
                "macd_bullish": np.ones(24),
                "macd_bearish": np.zeros(24),
            },
            index=timestamps_5m,
        )

        multi_fuzzy = {"5m": data_5m, "1h": data_1h}

        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # Find 1h_rsi_low column
        value_idx = names.index("1h_rsi_low")

        # 00:00 is exactly at hour boundary - should use hour 0's value (1.0)
        assert features[0, value_idx].item() == pytest.approx(1.0, abs=0.01)

        # 01:00 (index 12) is exactly at hour boundary - should use hour 1's value (2.0)
        assert features[12, value_idx].item() == pytest.approx(2.0, abs=0.01)


class TestMultiTimeframeEdgeCases:
    """Tests for edge cases in multi-timeframe processing."""

    def test_empty_timeframe_raises_error(self, processor: FuzzyNeuralProcessor):
        """Empty timeframe data should raise ValueError."""
        with pytest.raises(ValueError, match="No timeframe data"):
            processor.prepare_multi_timeframe_input({})

    def test_misaligned_date_ranges_handled(
        self,
        processor: FuzzyNeuralProcessor,
    ):
        """Timeframes with different date ranges should be handled gracefully."""
        # 5m data starts before 1h data - tests forward-fill for gaps at beginning
        timestamps_5m = pd.date_range(
            "2024-01-01 00:00", periods=36, freq="5min", tz="UTC"
        )  # 3 hours
        data_5m = pd.DataFrame(
            {
                "rsi_low": np.ones(36),
                "rsi_high": np.zeros(36),
            },
            index=timestamps_5m,
        )

        # 1h data starts 1 hour later
        timestamps_1h = pd.date_range(
            "2024-01-01 01:00", periods=2, freq="1h", tz="UTC"
        )
        data_1h = pd.DataFrame(
            {
                "macd_bullish": [2.0, 3.0],
                "macd_bearish": [0.0, 0.0],
            },
            index=timestamps_1h,
        )

        multi_fuzzy = {"5m": data_5m, "1h": data_1h}

        # Should not raise, but may log warnings about gaps
        features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)

        # Should still produce output
        assert features.shape[0] == len(timestamps_5m)

    def test_row_count_preserved_for_all_timeframe_orderings(
        self,
        processor: FuzzyNeuralProcessor,
        sample_1h_fuzzy_data: pd.DataFrame,
        sample_5m_fuzzy_data: pd.DataFrame,
    ):
        """Row count should be consistent regardless of timeframe dict order."""
        # Order 1: 5m first
        multi_fuzzy_1 = {"5m": sample_5m_fuzzy_data, "1h": sample_1h_fuzzy_data}
        features_1, _ = processor.prepare_multi_timeframe_input(multi_fuzzy_1)

        # Order 2: 1h first
        multi_fuzzy_2 = {"1h": sample_1h_fuzzy_data, "5m": sample_5m_fuzzy_data}
        features_2, _ = processor.prepare_multi_timeframe_input(multi_fuzzy_2)

        # Both should use highest frequency (5m) as base
        assert features_1.shape[0] == features_2.shape[0] == len(sample_5m_fuzzy_data)
