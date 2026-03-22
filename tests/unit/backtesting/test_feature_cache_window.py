"""Tests for FeatureCache.get_feature_window() method."""

import numpy as np
import pandas as pd


class TestFeatureCacheWindow:
    """Test the sliding window method for temporal models."""

    def _create_cache_with_data(self, n_rows=50, n_features=4):
        """Create a FeatureCache with pre-populated cached features."""
        from unittest.mock import MagicMock

        from ktrdr.backtesting.feature_cache import FeatureCache

        # Mock the config and metadata to avoid real indicator/fuzzy setup
        mock_config = MagicMock()
        mock_config.indicators = {}
        mock_config.fuzzy_sets = {}
        mock_metadata = MagicMock()
        mock_metadata.resolved_features = [f"feat_{i}" for i in range(n_features)]
        mock_metadata.normalization_params = {}

        cache = FeatureCache.__new__(FeatureCache)
        cache.config = mock_config
        cache.metadata = mock_metadata
        cache.expected_features = mock_metadata.resolved_features

        # Create cached features DataFrame
        dates = pd.date_range("2024-01-01", periods=n_rows, freq="1h")
        data = np.arange(n_rows * n_features).reshape(n_rows, n_features).astype(float)
        cache._cached_features = pd.DataFrame(
            data, index=dates, columns=cache.expected_features
        )
        return cache, dates

    def test_returns_correct_window_size(self):
        """get_feature_window returns DataFrame with correct number of rows."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[25], sequence_length=10)
        assert window is not None
        assert len(window) == 10

    def test_returns_none_for_insufficient_history(self):
        """Returns None when fewer than sequence_length bars available."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[3], sequence_length=10)
        assert window is None

    def test_exact_boundary(self):
        """Exactly sequence_length bars available returns valid window."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[9], sequence_length=10)
        assert window is not None
        assert len(window) == 10

    def test_column_order_matches_expected(self):
        """Returned DataFrame has columns in expected feature order."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[20], sequence_length=5)
        assert window is not None
        assert list(window.columns) == cache.expected_features

    def test_window_contains_correct_timestamps(self):
        """Window ends at the requested timestamp."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[15], sequence_length=5)
        assert window is not None
        assert window.index[-1] == dates[15]
        assert window.index[0] == dates[11]

    def test_window_values_match_cached_data(self):
        """Window values are exact slices of the cached features."""
        cache, dates = self._create_cache_with_data(50, 4)
        window = cache.get_feature_window(dates[15], sequence_length=5)
        assert window is not None
        expected = cache._cached_features.iloc[11:16]
        pd.testing.assert_frame_equal(window, expected)

    def test_returns_none_for_unknown_timestamp(self):
        """Returns None for a timestamp not in the index."""
        cache, dates = self._create_cache_with_data(50, 4)
        unknown_ts = pd.Timestamp("2099-01-01")
        window = cache.get_feature_window(unknown_ts, sequence_length=5)
        assert window is None
