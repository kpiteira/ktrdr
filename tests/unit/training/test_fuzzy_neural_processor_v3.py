"""
Tests for FuzzyNeuralProcessor v3 support.

Tests the v3 feature naming validation and configuration support.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor


def create_v3_fuzzy_data():
    """Create test fuzzy membership data with v3 naming convention.

    V3 feature naming: {timeframe}_{fuzzy_set_id}_{membership}
    Example: 5m_rsi_fast_oversold, 1h_macd_signal_positive
    """
    dates = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(20)]

    # V3 naming: {timeframe}_{fuzzy_set_id}_{membership}
    fuzzy_data = pd.DataFrame(
        {
            "5m_rsi_fast_oversold": np.random.random(20) * 0.8,
            "5m_rsi_fast_neutral": np.random.random(20) * 0.6,
            "5m_rsi_fast_overbought": np.random.random(20) * 0.7,
            "1h_macd_signal_positive": np.random.random(20) * 0.9,
            "1h_macd_signal_negative": np.random.random(20) * 0.5,
        },
        index=dates,
    )

    return fuzzy_data


class TestFuzzyNeuralProcessorV3Init:
    """Test v3 initialization patterns."""

    def test_init_with_resolved_features(self):
        """Processor accepts resolved feature list in v3 mode."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
            "1h_macd_signal_positive",
            "1h_macd_signal_negative",
        ]
        config = {"lookback_periods": 0}

        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        assert processor.resolved_features == resolved_features
        assert processor.n_features == 5

    def test_init_without_resolved_features_uses_none(self):
        """Processor without resolved_features works in legacy mode."""
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(config=config)

        assert processor.resolved_features is None
        assert processor.n_features is None


class TestFuzzyNeuralProcessorV3Validation:
    """Test v3 feature validation."""

    def test_validate_features_all_present(self):
        """Validates successfully when all expected features present."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        features_df = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.5, 0.6],
                "5m_rsi_fast_neutral": [0.3, 0.4],
                "5m_rsi_fast_overbought": [0.2, 0.1],
            }
        )

        # Should not raise
        processor.validate_features(features_df)

    def test_validate_features_missing_raises_error(self):
        """Errors when required features are missing."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        # Missing 5m_rsi_fast_overbought
        features_df = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.5, 0.6],
                "5m_rsi_fast_neutral": [0.3, 0.4],
            }
        )

        with pytest.raises(ValueError, match="Missing features"):
            processor.validate_features(features_df)

    def test_validate_features_extra_warns(self, caplog):
        """Warns when extra columns present (but doesn't fail)."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        # Extra column: extra_column
        features_df = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.5, 0.6],
                "5m_rsi_fast_neutral": [0.3, 0.4],
                "extra_column": [0.1, 0.2],
            }
        )

        import logging

        with caplog.at_level(logging.WARNING):
            processor.validate_features(features_df)

        assert "Extra columns will be ignored" in caplog.text
        assert "extra_column" in caplog.text

    def test_validate_features_not_called_without_resolved_features(self):
        """Validation is a no-op when not in v3 mode."""
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(config=config)

        # Any DataFrame is accepted when not in v3 mode
        features_df = pd.DataFrame(
            {
                "any_column": [0.5, 0.6],
            }
        )

        # Should not raise - validation skipped
        processor.validate_features(features_df)


class TestFuzzyNeuralProcessorV3NamingConvention:
    """Test v3 feature naming conventions."""

    def test_v3_naming_pattern_recognized(self):
        """V3 naming pattern {timeframe}_{fuzzy_set}_{membership} is processed."""
        fuzzy_data = create_v3_fuzzy_data()
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(config)

        features, names = processor.prepare_input(fuzzy_data)

        # All v3 columns should be recognized as fuzzy features
        assert len(names) == 5
        assert "5m_rsi_fast_oversold" in names
        assert "5m_rsi_fast_neutral" in names
        assert "5m_rsi_fast_overbought" in names
        assert "1h_macd_signal_positive" in names
        assert "1h_macd_signal_negative" in names

    def test_feature_order_matches_resolved_features(self):
        """Output columns match order from resolved_features."""
        resolved_features = [
            "1h_macd_signal_positive",  # Different order than DataFrame
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        # DataFrame columns in different order
        features_df = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.5, 0.6],
                "5m_rsi_fast_neutral": [0.3, 0.4],
                "1h_macd_signal_positive": [0.9, 0.8],
            }
        )

        # When getting ordered features, they should match resolved_features order
        ordered = processor.get_ordered_features(features_df)

        assert list(ordered.columns) == resolved_features


class TestFuzzyNeuralProcessorV3Integration:
    """Integration tests for v3 processor usage."""

    def test_prepare_input_validates_when_resolved_features_set(self):
        """prepare_input validates features when in v3 mode."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        # Missing feature
        bad_data = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.5, 0.6],
                "5m_rsi_fast_neutral": [0.3, 0.4],
                # Missing: 5m_rsi_fast_overbought
            }
        )

        with pytest.raises(ValueError, match="Missing features"):
            processor.prepare_input(bad_data)

    def test_prepare_input_reorders_to_resolved_features(self):
        """prepare_input returns features in resolved_features order."""
        resolved_features = [
            "col_c",  # Intentionally different order
            "col_a",
            "col_b",
        ]
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(
            config=config, resolved_features=resolved_features
        )

        dates = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(5)]
        features_df = pd.DataFrame(
            {
                "col_a": [0.1] * 5,
                "col_b": [0.2] * 5,
                "col_c": [0.3] * 5,
            },
            index=dates,
        )

        tensor, names = processor.prepare_input(features_df)

        # Names should be in resolved_features order
        assert names == resolved_features

        # Values should match the order
        assert tensor[0, 0].item() == pytest.approx(0.3, rel=0.01)  # col_c
        assert tensor[0, 1].item() == pytest.approx(0.1, rel=0.01)  # col_a
        assert tensor[0, 2].item() == pytest.approx(0.2, rel=0.01)  # col_b
