"""Tests for ContextLabeler."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.training.context_labeler import ContextLabeler, ContextLabelStats

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
        assert (
            valid == BULLISH
        ).all(), f"Expected all BULLISH, got: {valid.value_counts().to_dict()}"

    def test_downtrend_produces_bearish_labels(
        self, daily_downtrend_data: pd.DataFrame
    ) -> None:
        """Strongly downtrending data should produce BEARISH labels."""
        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(daily_downtrend_data)

        valid = labels.dropna()
        assert (
            valid == BEARISH
        ).all(), f"Expected all BEARISH, got: {valid.value_counts().to_dict()}"

    def test_flat_data_produces_neutral_labels(
        self, daily_flat_data: pd.DataFrame
    ) -> None:
        """Constant price should produce all NEUTRAL labels."""
        labeler = ContextLabeler(
            horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005
        )
        labels = labeler.label(daily_flat_data)

        valid = labels.dropna()
        assert (
            valid == NEUTRAL
        ).all(), f"Expected all NEUTRAL, got: {valid.value_counts().to_dict()}"

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
        assert (
            abs(bullish_pct - bearish_pct) < 0.15
        ), f"bullish={bullish_pct:.2%}, bearish={bearish_pct:.2%}"


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

    def test_zero_horizon_raises_error(self) -> None:
        """Zero horizon should raise DataError."""
        with pytest.raises(DataError, match="positive"):
            ContextLabeler(horizon=0)

    def test_negative_horizon_raises_error(self) -> None:
        """Negative horizon should raise DataError."""
        with pytest.raises(DataError, match="positive"):
            ContextLabeler(horizon=-5)

    def test_empty_dataframe_raises_error(self) -> None:
        """Empty DataFrame should raise DataError."""
        data = pd.DataFrame({"close": []})
        labeler = ContextLabeler()
        with pytest.raises(DataError):
            labeler.label(data)


# --- Task 3.2: ContextLabelStats Analysis ---


@pytest.fixture
def known_context_labels() -> pd.Series:
    """Context labels with known distribution: 5 BULLISH, 3 BEARISH, 7 NEUTRAL."""
    dates = pd.date_range("2024-01-01", periods=15, freq="B")
    values = [0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2]
    return pd.Series(values, index=dates, dtype=float)


@pytest.fixture
def alternating_labels() -> pd.Series:
    """Labels that alternate every 2 days: duration should be ~2."""
    dates = pd.date_range("2024-01-01", periods=12, freq="B")
    # BULL, BULL, BEAR, BEAR, NEUT, NEUT, BULL, BULL, BEAR, BEAR, NEUT, NEUT
    values = [0, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 2]
    return pd.Series(values, index=dates, dtype=float)


class TestContextLabelStatsDistribution:
    """Distribution computation tests."""

    def test_distribution_sums_to_one(self, known_context_labels: pd.Series) -> None:
        """Distribution fractions should sum to ~1.0."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        total = sum(stats.distribution.values())
        assert total == pytest.approx(1.0)

    def test_distribution_values_correct(self, known_context_labels: pd.Series) -> None:
        """Distribution should match known label counts."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        assert stats.distribution[BULLISH] == pytest.approx(5 / 15)
        assert stats.distribution[BEARISH] == pytest.approx(3 / 15)
        assert stats.distribution[NEUTRAL] == pytest.approx(7 / 15)

    def test_single_class_distribution(self) -> None:
        """All-bullish labels: bullish=1.0, others=0.0."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        labels = pd.Series([0.0] * 10, index=dates)
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(labels)
        assert stats.distribution[BULLISH] == pytest.approx(1.0)
        assert stats.distribution.get(BEARISH, 0.0) == pytest.approx(0.0)
        assert stats.distribution.get(NEUTRAL, 0.0) == pytest.approx(0.0)


class TestContextLabelStatsDuration:
    """Persistence / duration computation tests."""

    def test_duration_positive_for_present_classes(
        self, known_context_labels: pd.Series
    ) -> None:
        """Duration should be > 0 for all classes present in labels."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        for cls in [BULLISH, BEARISH, NEUTRAL]:
            assert stats.mean_duration_days[cls] > 0

    def test_known_alternating_durations(self, alternating_labels: pd.Series) -> None:
        """Alternating 2-day runs should have mean duration = 2.0."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(alternating_labels)
        for cls in [BULLISH, BEARISH, NEUTRAL]:
            assert stats.mean_duration_days[cls] == pytest.approx(2.0)

    def test_single_long_run(self) -> None:
        """One continuous run = mean duration equals run length."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        labels = pd.Series([0.0] * 10, index=dates)
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(labels)
        assert stats.mean_duration_days[BULLISH] == pytest.approx(10.0)


class TestContextLabelStatsHourlyReturns:
    """Hourly return by context tests."""

    def test_hourly_returns_grouped_by_context(self) -> None:
        """Mean hourly return should be computed per context class."""
        # 4 days of daily labels (Mon-Thu)
        daily_dates = pd.date_range("2024-01-01", periods=4, freq="B")
        daily_labels = pd.Series(
            [0.0, 0.0, 1.0, 1.0],
            index=daily_dates,  # 2 bull, 2 bear
        )

        # Hourly data covering all 4 business days (96 hours)
        hourly_dates = pd.date_range("2024-01-01", periods=96, freq="h")
        hourly_closes = []
        base = 100.0
        for i in range(96):
            day_idx = i // 24
            if day_idx < 2:  # bullish days — price rises
                base += 0.1
            else:  # bearish days — price falls
                base -= 0.1
            hourly_closes.append(base)
        hourly_data = pd.DataFrame({"close": hourly_closes}, index=hourly_dates)

        labeler = ContextLabeler()
        stats = labeler.analyze_labels(daily_labels, hourly_data=hourly_data)

        assert stats.mean_hourly_return_by_context is not None
        assert stats.mean_hourly_return_by_context[BULLISH] > 0
        assert stats.mean_hourly_return_by_context[BEARISH] < 0

    def test_no_hourly_data_returns_none(self, known_context_labels: pd.Series) -> None:
        """Without hourly data, hourly return stats should be None."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        assert stats.mean_hourly_return_by_context is None


class TestContextLabelStatsRegimeCorrelation:
    """Regime correlation tests."""

    def test_identical_labels_high_correlation(self) -> None:
        """Identical label series (mapped) should have high correlation."""
        dates = pd.date_range("2024-01-01", periods=20, freq="B")
        context = pd.Series([0, 0, 1, 1, 2, 2] * 3 + [0, 0], index=dates, dtype=float)
        # Regime mirrors context pattern (different label space but same grouping)
        regime = pd.Series([0, 0, 1, 1, 2, 2] * 3 + [0, 0], index=dates, dtype=float)

        labeler = ContextLabeler()
        stats = labeler.analyze_labels(context, regime_labels=regime)
        assert stats.regime_correlation is not None
        assert stats.regime_correlation > 0.5

    def test_independent_labels_low_correlation(self) -> None:
        """Independent label series should have low correlation."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        context = pd.Series(
            np.random.choice([0, 1, 2], size=200), index=dates, dtype=float
        )
        regime = pd.Series(
            np.random.choice([0, 1, 2, 3], size=200), index=dates, dtype=float
        )

        labeler = ContextLabeler()
        stats = labeler.analyze_labels(context, regime_labels=regime)
        assert stats.regime_correlation is not None
        assert stats.regime_correlation < 0.3

    def test_no_regime_labels_returns_none(
        self, known_context_labels: pd.Series
    ) -> None:
        """Without regime labels, correlation should be None."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        assert stats.regime_correlation is None

    def test_stats_is_dataclass(self, known_context_labels: pd.Series) -> None:
        """analyze_labels returns a ContextLabelStats instance."""
        labeler = ContextLabeler()
        stats = labeler.analyze_labels(known_context_labels)
        assert isinstance(stats, ContextLabelStats)
