"""
Tests for the FuzzyNeuralProcessor.
"""

import pytest
import pandas as pd
import numpy as np
import torch
from datetime import datetime, timedelta

from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor


def create_test_fuzzy_data():
    """Create test fuzzy membership data."""
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(20)]

    # Create fuzzy membership values (should be 0-1 range)
    np.random.seed(42)  # For reproducible tests
    fuzzy_data = pd.DataFrame(
        {
            "rsi_oversold": np.random.random(20) * 0.8,
            "rsi_neutral": np.random.random(20) * 0.6,
            "rsi_overbought": np.random.random(20) * 0.7,
            "macd_positive": np.random.random(20) * 0.9,
            "macd_negative": np.random.random(20) * 0.5,
            "sma_above": np.random.random(20) * 0.8,
            "distance_from_ma_near": np.random.random(20) * 0.4,
        },
        index=dates,
    )

    return fuzzy_data


class TestFuzzyNeuralProcessor:
    """Test cases for FuzzyNeuralProcessor."""

    def test_initialization(self):
        """Test processor initialization with different configs."""
        config = {"lookback_periods": 2}
        processor = FuzzyNeuralProcessor(config)
        assert processor.config["lookback_periods"] == 2
        assert processor.feature_names == []

    def test_prepare_input_basic(self):
        """Test basic fuzzy input preparation."""
        fuzzy_data = create_test_fuzzy_data()
        config = {"lookback_periods": 0}
        processor = FuzzyNeuralProcessor(config)

        features, feature_names = processor.prepare_input(fuzzy_data)

        # Check return types
        assert isinstance(features, torch.Tensor)
        assert isinstance(feature_names, list)

        # Check shapes
        assert features.shape[0] == len(fuzzy_data)  # Same number of rows
        assert features.shape[1] == len(
            fuzzy_data.columns
        )  # One feature per fuzzy column
        assert len(feature_names) == len(fuzzy_data.columns)

        # Check fuzzy range (0-1)
        assert features.min() >= 0.0
        assert features.max() <= 1.0

    def test_prepare_input_with_temporal(self):
        """Test fuzzy input preparation with temporal features."""
        fuzzy_data = create_test_fuzzy_data()
        config = {"lookback_periods": 2}
        processor = FuzzyNeuralProcessor(config)

        features, feature_names = processor.prepare_input(fuzzy_data)

        # With 2 lookback periods, we should have base + (base * 2) features
        base_features = len(fuzzy_data.columns)
        expected_features = base_features + (base_features * 2)

        assert features.shape[1] == expected_features
        assert len(feature_names) == expected_features

        # Check that temporal feature names are generated correctly
        temporal_names = [name for name in feature_names if "_lag_" in name]
        expected_temporal = base_features * 2  # 2 lag periods
        assert len(temporal_names) == expected_temporal

    def test_fuzzy_feature_extraction(self):
        """Test fuzzy feature extraction method."""
        fuzzy_data = create_test_fuzzy_data()
        processor = FuzzyNeuralProcessor({})

        features, names = processor._extract_fuzzy_features(fuzzy_data)

        assert isinstance(features, np.ndarray)
        assert len(names) == len(fuzzy_data.columns)
        assert features.shape == (len(fuzzy_data), len(fuzzy_data.columns))

        # All feature names should be from fuzzy columns
        for name in names:
            assert "_" in name  # Standard fuzzy naming: indicator_fuzzyset

    def test_temporal_feature_extraction(self):
        """Test temporal feature extraction."""
        fuzzy_data = create_test_fuzzy_data()
        processor = FuzzyNeuralProcessor({})

        # Test with 2 lag periods
        temporal_features, temporal_names = processor._extract_temporal_features(
            fuzzy_data, lookback=2
        )

        base_features = len(fuzzy_data.columns)
        expected_temporal = base_features * 2  # 2 lag periods

        assert temporal_features.shape == (len(fuzzy_data), expected_temporal)
        assert len(temporal_names) == expected_temporal

        # Check temporal naming
        for name in temporal_names:
            assert "_lag_" in name
            assert any(base_name in name for base_name in fuzzy_data.columns)

    def test_temporal_feature_extraction_no_lookback(self):
        """Test temporal extraction with no lookback."""
        fuzzy_data = create_test_fuzzy_data()
        processor = FuzzyNeuralProcessor({})

        temporal_features, temporal_names = processor._extract_temporal_features(
            fuzzy_data, lookback=0
        )

        assert temporal_features.size == 0
        assert len(temporal_names) == 0

    def test_validate_fuzzy_range(self):
        """Test fuzzy range validation."""
        processor = FuzzyNeuralProcessor({})

        # Valid fuzzy data (0-1 range)
        valid_data = np.random.random((10, 5))
        feature_names = ["test1", "test2", "test3", "test4", "test5"]

        # Should not raise any exceptions
        processor._validate_fuzzy_range(valid_data, feature_names)

    def test_validate_fuzzy_range_out_of_bounds(self):
        """Test validation with out-of-bounds values."""
        processor = FuzzyNeuralProcessor({})

        # Data with values outside 0-1 range
        invalid_data = np.array([[0.5, 1.5, -0.1], [0.8, 0.9, 2.0]])
        feature_names = ["test1", "test2", "test3"]

        # Should log warnings but not fail
        processor._validate_fuzzy_range(invalid_data, feature_names)

    def test_empty_fuzzy_data_error(self):
        """Test error handling for empty fuzzy data."""
        empty_data = pd.DataFrame()
        processor = FuzzyNeuralProcessor({})

        with pytest.raises(ValueError, match="No fuzzy membership columns found"):
            processor.prepare_input(empty_data)

    def test_non_fuzzy_columns_ignored(self):
        """Test that non-fuzzy columns are ignored."""
        dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(5)]

        # Mix fuzzy and non-fuzzy columns
        mixed_data = pd.DataFrame(
            {
                "rsi_oversold": [0.8, 0.7, 0.6, 0.5, 0.4],  # Fuzzy
                "price": [100, 101, 102, 103, 104],  # Not fuzzy
                "volume": [1000, 1100, 1200, 1300, 1400],  # Not fuzzy
                "macd_positive": [0.3, 0.4, 0.5, 0.6, 0.7],  # Fuzzy
            },
            index=dates,
        )

        processor = FuzzyNeuralProcessor({})
        features, feature_names = processor.prepare_input(mixed_data)

        # Should only include fuzzy columns
        assert len(feature_names) == 2
        assert "rsi_oversold" in feature_names
        assert "macd_positive" in feature_names
        assert "price" not in feature_names
        assert "volume" not in feature_names

    def test_nan_handling(self):
        """Test NaN value handling."""
        fuzzy_data = create_test_fuzzy_data()

        # Introduce some NaN values
        fuzzy_data.iloc[5:8, 1] = np.nan
        fuzzy_data.iloc[10, :] = np.nan

        processor = FuzzyNeuralProcessor({})
        features, feature_names = processor.prepare_input(fuzzy_data)

        # NaN values should be converted to 0.0
        assert not torch.isnan(features).any()

    def test_get_feature_count(self):
        """Test feature count calculation."""
        config = {"lookback_periods": 3}
        processor = FuzzyNeuralProcessor(config)

        # Simulate having 5 base features
        processor.feature_names = ["f1", "f2", "f3", "f4", "f5"]

        # 5 base + (5 * 3 lookback) = 20 total
        expected_count = 5 + (5 * 3)
        assert processor.get_feature_count() == expected_count

    def test_get_config_summary(self):
        """Test configuration summary."""
        config = {"lookback_periods": 2}
        processor = FuzzyNeuralProcessor(config)
        processor.feature_names = ["f1", "f2", "f3"]

        summary = processor.get_config_summary()

        assert summary["type"] == "FuzzyNeuralProcessor"
        assert summary["lookback_periods"] == 2
        assert summary["pure_fuzzy"] is True
        assert summary["scaling"] is False
        assert summary["raw_features"] is False

    def test_feature_name_consistency(self):
        """Test that feature names are consistent across calls."""
        fuzzy_data = create_test_fuzzy_data()
        processor = FuzzyNeuralProcessor({"lookback_periods": 1})

        features1, names1 = processor.prepare_input(fuzzy_data)
        features2, names2 = processor.prepare_input(fuzzy_data)

        assert names1 == names2
        assert torch.equal(features1, features2)

    def test_different_lookback_periods(self):
        """Test different lookback period configurations."""
        fuzzy_data = create_test_fuzzy_data()
        base_features = len(fuzzy_data.columns)

        for lookback in [0, 1, 2, 3, 5]:
            processor = FuzzyNeuralProcessor({"lookback_periods": lookback})
            features, feature_names = processor.prepare_input(fuzzy_data)

            if lookback == 0:
                expected_features = base_features
            else:
                expected_features = base_features + (base_features * lookback)

            assert features.shape[1] == expected_features
            assert len(feature_names) == expected_features
