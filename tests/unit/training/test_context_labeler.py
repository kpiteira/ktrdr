"""Tests for ContextLabeler."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch", reason="torch required for training module imports")

from ktrdr.errors import DataError
from ktrdr.training.context_labeler import ContextLabeler

# Label constants for readability
BULLISH = 0
BEARISH = 1
NEUTRAL = 2


@pytest.fixture
def daily_uptrend_data() -> pd.DataFrame:
    """Strongly uptrending daily OHLCV data (20 days, ~1% daily gain)."""
    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    closes = [100.0 * (1.01**i) for i in range(20)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.005 for c in closes],
            "low": [c * 0.995 for c in closes],
            "close": closes,
            "volume": [1000] * 20,
        },
        index=dates,
    )


@pytest.fixture
def daily_downtrend_data() -> pd.DataFrame:
    """Strongly downtrending daily OHLCV data (20 days, ~1% daily loss)."""
    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    closes = [100.0 * (0.99**i) for i in range(20)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.005 for c in closes],
            "low": [c * 0.995 for c in closes],
            "close": closes,
            "volume": [1000] * 20,
        },
        index=dates,
    )


@pytest.fixture
def daily_flat_data() -> pd.DataFrame:
    """Flat daily data — constant price."""
    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [100.5] * 20,
            "low": [99.5] * 20,
            "close": [100.0] * 20,
            "volume": [1000] * 20,
        },
        index=dates,
    )


class TestContextLabelerBasic:
    """Basic labeling behavior."""

    def test_uptrend_produces_bullish_labels(
        self, daily_uptrend_data: pd.DataFrame
    ) -> None:
        """Strongly uptrending data should produce BULLISH labels."""
        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(daily_uptrend_data)

        # All non-NaN labels should be BULLISH (5-day return of ~5% >> 0.5%)
        valid = labels.dropna()
        assert (valid == BULLISH).all(), (
            f"Expected all BULLISH, got: {valid.value_counts().to_dict()}"
        )

    def test_downtrend_produces_bearish_labels(
        self, daily_downtrend_data: pd.DataFrame
    ) -> None:
        """Strongly downtrending data should produce BEARISH labels."""
        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(daily_downtrend_data)

        valid = labels.dropna()
        assert (valid == BEARISH).all(), (
            f"Expected all BEARISH, got: {valid.value_counts().to_dict()}"
        )

    def test_flat_data_produces_neutral_labels(
        self, daily_flat_data: pd.DataFrame
    ) -> None:
        """Constant price should produce all NEUTRAL labels."""
        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(daily_flat_data)

        valid = labels.dropna()
        assert (valid == NEUTRAL).all(), (
            f"Expected all NEUTRAL, got: {valid.value_counts().to_dict()}"
        )

    def test_last_horizon_bars_are_nan(self, daily_uptrend_data: pd.DataFrame) -> None:
        """Last `horizon` bars should be NaN (no future data available)."""
        horizon = 5
        labeler = ContextLabeler(horizon=horizon)
        labels = labeler.label(daily_uptrend_data)

        # Series length should match input
        assert len(labels) == len(daily_uptrend_data)
        # Last horizon bars are NaN
        assert labels.iloc[-horizon:].isna().all()
        # Other bars are not NaN
        assert labels.iloc[:-horizon].notna().all()

    def test_returns_integer_labels(self, daily_uptrend_data: pd.DataFrame) -> None:
        """Valid labels should be integers 0, 1, or 2."""
        labeler = ContextLabeler(horizon=5)
        labels = labeler.label(daily_uptrend_data)
        valid = labels.dropna()
        assert set(valid.unique()).issubset({BULLISH, BEARISH, NEUTRAL})

    def test_output_is_series_with_matching_index(
        self, daily_uptrend_data: pd.DataFrame
    ) -> None:
        """Output Series should have same index as input DataFrame."""
        labeler = ContextLabeler(horizon=5)
        labels = labeler.label(daily_uptrend_data)
        assert isinstance(labels, pd.Series)
        pd.testing.assert_index_equal(labels.index, daily_uptrend_data.index)


class TestContextLabelerThresholds:
    """Threshold behavior."""

    def test_custom_thresholds_override_defaults(self) -> None:
        """Custom thresholds should be used instead of defaults."""
        labeler = ContextLabeler(
            horizon=5,
            bullish_threshold=0.01,
            bearish_threshold=-0.01,
        )
        assert labeler.bullish_threshold == 0.01
        assert labeler.bearish_threshold == -0.01

    def test_default_parameters(self) -> None:
        """Defaults match design: horizon=5, thresholds=±0.005."""
        labeler = ContextLabeler()
        assert labeler.horizon == 5
        assert labeler.bullish_threshold == 0.005
        assert labeler.bearish_threshold == -0.005

    def test_wider_threshold_produces_more_neutral(self) -> None:
        """Wider thresholds should produce more NEUTRAL labels."""
        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        # Small random walk with modest moves
        np.random.seed(42)
        closes = 100.0 + np.cumsum(np.random.randn(30) * 0.3)
        data = pd.DataFrame(
            {
                "close": closes,
                "open": closes,
                "high": closes + 0.5,
                "low": closes - 0.5,
                "volume": [1000] * 30,
            },
            index=dates,
        )

        narrow = ContextLabeler(
            horizon=5, bullish_threshold=0.001, bearish_threshold=-0.001
        )
        wide = ContextLabeler(
            horizon=5, bullish_threshold=0.05, bearish_threshold=-0.05
        )

        narrow_labels = narrow.label(data).dropna()
        wide_labels = wide.label(data).dropna()

        narrow_neutral_pct = (narrow_labels == NEUTRAL).sum() / len(narrow_labels)
        wide_neutral_pct = (wide_labels == NEUTRAL).sum() / len(wide_labels)
        assert wide_neutral_pct >= narrow_neutral_pct

    def test_symmetric_thresholds_on_random_walk(self) -> None:
        """Symmetric thresholds on random walk should produce roughly symmetric distribution."""
        dates = pd.date_range("2024-01-01", periods=1000, freq="B")
        np.random.seed(123)
        closes = 100.0 + np.cumsum(np.random.randn(1000) * 0.5)
        # Ensure no zero prices
        closes = np.maximum(closes, 1.0)
        data = pd.DataFrame({"close": closes}, index=dates)

        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(data).dropna()

        bullish_pct = (labels == BULLISH).sum() / len(labels)
        bearish_pct = (labels == BEARISH).sum() / len(labels)
        # Should be roughly equal (within 15 percentage points)
        assert abs(bullish_pct - bearish_pct) < 0.15, (
            f"bullish={bullish_pct:.2%}, bearish={bearish_pct:.2%}"
        )


class TestContextLabelerEdgeCases:
    """Edge case handling."""

    def test_very_short_data_all_nan(self) -> None:
        """Data shorter than horizon produces all NaN."""
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        data = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=dates)
        labeler = ContextLabeler(horizon=5)
        labels = labeler.label(data)
        assert labels.isna().all()

    def test_data_exactly_horizon_plus_one(self) -> None:
        """Data with exactly horizon+1 bars produces one valid label."""
        dates = pd.date_range("2024-01-01", periods=6, freq="B")
        data = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]}, index=dates
        )
        labeler = ContextLabeler(horizon=5, bullish_threshold=0.005)
        labels = labeler.label(data)
        # First bar: (110-100)/100 = 0.10 > 0.005 → BULLISH
        assert labels.iloc[0] == BULLISH
        # Last 5 are NaN
        assert labels.iloc[1:].isna().all()

    def test_missing_close_column_raises_error(self) -> None:
        """Raise DataError when close column is missing."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        data = pd.DataFrame({"open": [100.0] * 10}, index=dates)
        labeler = ContextLabeler()
        with pytest.raises(DataError, match="close"):
            labeler.label(data)

    def test_zero_close_price_raises_error(self) -> None:
        """Guard against division by zero."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        data = pd.DataFrame({"close": [100.0, 0.0] + [101.0] * 8}, index=dates)
        labeler = ContextLabeler()
        with pytest.raises(DataError, match="zero"):
            labeler.label(data)

    def test_empty_dataframe_raises_error(self) -> None:
        """Empty DataFrame should raise DataError."""
        data = pd.DataFrame({"close": []})
        labeler = ContextLabeler()
        with pytest.raises(DataError):
            labeler.label(data)
