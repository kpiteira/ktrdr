"""
Unit tests for multi-symbol data alignment in TrainingPipeline.

These tests verify the critical invariants that must hold for multi-symbol
training to work correctly:

1. Features and labels must have matching row counts per symbol
2. All symbols must produce valid (non-empty) tensors
3. Combined data must preserve all samples

Related to: Task 4.1 - Debugging Multi-Symbol Data Combination
"""

import numpy as np
import pandas as pd
import pytest
import torch

from ktrdr.training.training_pipeline import TrainingPipeline


class TestFeatureLabelSizeConsistency:
    """Test that features and labels have consistent sizes per symbol."""

    def test_single_symbol_features_labels_match_length(self):
        """For a single symbol, features and labels must have same row count."""
        # Arrange - create mock price data with DatetimeIndex
        dates = pd.date_range("2024-01-01", periods=100, freq="1D")
        price_data = {
            "1d": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 200, 100),
                    "high": np.random.uniform(100, 200, 100),
                    "low": np.random.uniform(100, 200, 100),
                    "close": np.random.uniform(100, 200, 100),
                    "volume": np.random.uniform(1000, 10000, 100),
                },
                index=dates,
            )
        }

        # Create fuzzy data (same size as price data)
        fuzzy_data = {
            "1d": pd.DataFrame(
                {
                    "rsi_oversold": np.random.uniform(0, 1, 100),
                    "rsi_overbought": np.random.uniform(0, 1, 100),
                    "sma_above": np.random.uniform(0, 1, 100),
                    "sma_below": np.random.uniform(0, 1, 100),
                },
                index=dates,
            )
        }

        # Act
        features, feature_names = TrainingPipeline.create_features(fuzzy_data, {})
        labels = TrainingPipeline.create_labels(
            price_data,
            {"zigzag_threshold": 0.03, "label_lookahead": 5},
        )

        # Assert - Critical invariant: features and labels must match
        assert features.shape[0] == labels.shape[0], (
            f"Feature/label size mismatch: features={features.shape[0]}, labels={labels.shape[0]}. "
            f"This is the root cause of multi-symbol training failures."
        )

    def test_fuzzy_data_with_different_row_count_than_price_data(self):
        """Detect when fuzzy processing changes row count from price data.

        This test documents the root cause: if fuzzy processing drops rows
        (due to NaN handling), features will have fewer rows than labels.
        """
        # Arrange - price data with 100 rows
        dates = pd.date_range("2024-01-01", periods=100, freq="1D")
        price_data = {
            "1d": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 200, 100),
                    "high": np.random.uniform(100, 200, 100),
                    "low": np.random.uniform(100, 200, 100),
                    "close": np.random.uniform(100, 200, 100),
                    "volume": np.random.uniform(1000, 10000, 100),
                },
                index=dates,
            )
        }

        # Fuzzy data with 95 rows (simulating 5 rows lost to NaN during indicator warmup)
        fuzzy_dates = dates[5:]  # Skip first 5 rows
        fuzzy_data = {
            "1d": pd.DataFrame(
                {
                    "rsi_oversold": np.random.uniform(0, 1, 95),
                    "rsi_overbought": np.random.uniform(0, 1, 95),
                },
                index=fuzzy_dates,
            )
        }

        # Act
        features, _ = TrainingPipeline.create_features(fuzzy_data, {})
        labels = TrainingPipeline.create_labels(
            price_data,
            {"zigzag_threshold": 0.03, "label_lookahead": 5},
        )

        # Assert - Document the mismatch (this is the bug we're exposing)
        assert features.shape[0] != labels.shape[0], (
            "Expected size mismatch when fuzzy data has fewer rows than price data. "
            "This test documents the root cause of multi-symbol failures."
        )

        # Log the mismatch details for debugging
        size_diff = labels.shape[0] - features.shape[0]
        print("\n[DEBUG] Feature/label size mismatch detected:")
        print(f"  - Features: {features.shape[0]} rows (from fuzzy_data)")
        print(f"  - Labels: {labels.shape[0]} rows (from price_data)")
        print(f"  - Difference: {size_diff} rows lost in fuzzy processing")


class TestMultiSymbolDataCombination:
    """Test multi-symbol data combination with size validation."""

    def test_combine_requires_consistent_feature_dims(self):
        """All symbols must have same feature dimension to concatenate."""
        from ktrdr.training.exceptions import TrainingDataError

        # Arrange - Different feature dimensions
        symbols = ["AAPL", "MSFT"]

        # AAPL: 50 features
        all_features = {
            "AAPL": torch.randn(100, 50),
            "MSFT": torch.randn(100, 75),  # Different feature count
        }
        all_labels = {
            "AAPL": torch.randint(0, 3, (100,)),
            "MSFT": torch.randint(0, 3, (100,)),
        }

        # Act & Assert - Should fail loudly with clear error message
        with pytest.raises(TrainingDataError, match="Inconsistent feature dimensions"):
            TrainingPipeline.combine_multi_symbol_data(
                all_features, all_labels, symbols
            )

    def test_combine_handles_empty_symbol_data(self):
        """Combining should fail loudly if any symbol has empty data."""
        from ktrdr.training.exceptions import TrainingDataError

        # Arrange
        symbols = ["AAPL", "MSFT"]

        all_features = {
            "AAPL": torch.randn(100, 50),
            "MSFT": torch.empty(0, 50),  # Empty tensor
        }
        all_labels = {
            "AAPL": torch.randint(0, 3, (100,)),
            "MSFT": torch.empty(0, dtype=torch.long),  # Empty tensor
        }

        # Act & Assert - Should fail loudly with clear error message
        with pytest.raises(TrainingDataError, match="Empty data for symbol"):
            TrainingPipeline.combine_multi_symbol_data(
                all_features, all_labels, symbols
            )

    def test_combine_multi_symbol_preserves_all_data(self):
        """Verify no data is lost during multi-symbol combination."""
        # Arrange
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        sample_counts = {"EURUSD": 1000, "GBPUSD": 950, "USDJPY": 1100}
        feature_dim = 36

        all_features = {}
        all_labels = {}

        for symbol, count in sample_counts.items():
            all_features[symbol] = torch.randn(count, feature_dim)
            all_labels[symbol] = torch.randint(0, 3, (count,))

        # Act
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert - All data preserved
        expected_total = sum(sample_counts.values())
        assert (
            combined_features.shape[0] == expected_total
        ), f"Data loss detected: expected {expected_total}, got {combined_features.shape[0]}"
        assert (
            combined_labels.shape[0] == expected_total
        ), f"Label loss detected: expected {expected_total}, got {combined_labels.shape[0]}"


class TestMultiSymbolDebugLogging:
    """Tests verifying debug logging is present for multi-symbol issues."""

    def test_combine_logs_per_symbol_sample_counts(self, caplog):
        """Verify that combine logs sample counts per symbol for debugging."""
        # Arrange
        import logging

        caplog.set_level(logging.INFO)

        symbols = ["AAPL", "MSFT"]
        all_features = {
            "AAPL": torch.randn(100, 50),
            "MSFT": torch.randn(120, 50),
        }
        all_labels = {
            "AAPL": torch.randint(0, 3, (100,)),
            "MSFT": torch.randint(0, 3, (120,)),
        }

        # Act
        TrainingPipeline.combine_multi_symbol_data(all_features, all_labels, symbols)

        # Assert - Verify logging is present
        log_text = caplog.text

        # Check for combining header
        assert "Combining data from 2 symbols" in log_text

        # Check for per-symbol sample counts
        assert "AAPL: 100 samples" in log_text
        assert "MSFT: 120 samples" in log_text

        # Check for combined total
        assert "Combined total: 220 samples" in log_text
