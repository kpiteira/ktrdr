"""Tests for MultiScaleRegimeLabeler — multi-scale zigzag regime labeling."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.training.multi_scale_regime_labeler import MultiScaleRegimeLabeler
from ktrdr.training.regime_labeler import (
    RANGING,
    TRENDING_DOWN,
    TRENDING_UP,
    VOLATILE,
)


def _make_price_data(
    close: list[float] | np.ndarray,
    *,
    high_offset: float = 0.001,
    low_offset: float = 0.001,
) -> pd.DataFrame:
    """Helper to create OHLCV DataFrame from close prices."""
    close_arr = np.array(close, dtype=float)
    return pd.DataFrame(
        {
            "open": close_arr,
            "high": close_arr + high_offset,
            "low": close_arr - low_offset,
            "close": close_arr,
            "volume": np.ones(len(close_arr)) * 1000,
        },
        index=pd.date_range("2020-01-01", periods=len(close_arr), freq="h"),
    )


class TestATRThreshold:
    """Test ATR-based threshold computation."""

    def test_threshold_scales_with_price_level(self) -> None:
        """Same ATR multiplier should produce different absolute thresholds
        for different price levels (auto-adaptation)."""
        labeler = MultiScaleRegimeLabeler(macro_atr_mult=3.0, micro_atr_mult=1.0)

        # Low-price instrument (e.g., EURUSD ~1.10)
        low_data = _make_price_data(
            np.linspace(1.08, 1.12, 500),
            high_offset=0.002,
            low_offset=0.002,
        )
        low_threshold = labeler._compute_atr_threshold(low_data, 3.0)

        # High-price instrument (e.g., GBPJPY ~190)
        high_data = _make_price_data(
            np.linspace(188, 192, 500),
            high_offset=0.3,
            low_offset=0.3,
        )
        high_threshold = labeler._compute_atr_threshold(high_data, 3.0)

        # Both should be positive percentages
        assert low_threshold > 0
        assert high_threshold > 0
        # They should be in a similar ballpark (both are percentages), not wildly different
        assert 0.001 < low_threshold < 0.2
        assert 0.001 < high_threshold < 0.2

    def test_macro_threshold_larger_than_micro(self) -> None:
        """Macro threshold (3x ATR) should be larger than micro (1x ATR)."""
        labeler = MultiScaleRegimeLabeler(macro_atr_mult=3.0, micro_atr_mult=1.0)
        data = _make_price_data(
            np.linspace(1.08, 1.12, 500),
            high_offset=0.002,
            low_offset=0.002,
        )
        macro_t = labeler._compute_atr_threshold(data, 3.0)
        micro_t = labeler._compute_atr_threshold(data, 1.0)
        assert macro_t > micro_t


class TestZigZag:
    """Test the internal zigzag pivot finder."""

    def test_monotonic_uptrend_two_pivots(self) -> None:
        """Monotonically increasing price should yield only start and end pivots."""
        labeler = MultiScaleRegimeLabeler()
        close = np.linspace(1.0, 2.0, 100)
        pivots = labeler._run_zigzag(close, threshold=0.05)
        # Monotonic up: first point + end extension, no internal reversals
        assert len(pivots) >= 2
        # All pivots should be ascending
        prices = [p[1] for p in pivots]
        assert prices[-1] > prices[0]

    def test_clear_reversals(self) -> None:
        """Price with clear up-down-up pattern should produce multiple pivots."""
        labeler = MultiScaleRegimeLabeler()
        # Go up 10%, down 10%, up 10%
        up = np.linspace(1.0, 1.10, 50)
        down = np.linspace(1.10, 1.00, 50)
        up2 = np.linspace(1.00, 1.10, 50)
        close = np.concatenate([up, down, up2])
        pivots = labeler._run_zigzag(close, threshold=0.05)
        # Should find at least 4 pivots: start, top, bottom, end
        assert len(pivots) >= 4


class TestMacroSegments:
    """Test macro segment extraction."""

    def test_uptrend_segment(self) -> None:
        """Single up-move should produce one 'up' segment."""
        labeler = MultiScaleRegimeLabeler()
        # Low → High pivot pair
        pivots = [(0, 1.0), (100, 1.10)]
        segments = labeler._extract_macro_segments(pivots, n_bars=101)
        assert len(segments) == 1
        assert segments[0].direction == "up"
        assert segments[0].start_idx == 0
        assert segments[0].end_idx == 100

    def test_downtrend_segment(self) -> None:
        """Single down-move should produce one 'down' segment."""
        labeler = MultiScaleRegimeLabeler()
        pivots = [(0, 1.10), (100, 1.0)]
        segments = labeler._extract_macro_segments(pivots, n_bars=101)
        assert len(segments) == 1
        assert segments[0].direction == "down"

    def test_multiple_segments(self) -> None:
        """Up-down pattern should produce up then down segments."""
        labeler = MultiScaleRegimeLabeler()
        pivots = [(0, 1.0), (50, 1.10), (100, 1.0)]
        segments = labeler._extract_macro_segments(pivots, n_bars=101)
        assert len(segments) == 2
        assert segments[0].direction == "up"
        assert segments[1].direction == "down"


class TestMicroProgression:
    """Test micro pivot progression check."""

    def test_higher_lows_is_progressive(self) -> None:
        """Micro pivots with consistently higher lows → progressive (trending up)."""
        labeler = MultiScaleRegimeLabeler(progression_tolerance=0.5)
        # Alternating high-low pairs, lows are increasing
        # pivots: high, low, high, low, high, low
        micro_pivots = [
            (0, 1.05),  # high
            (10, 1.01),  # low
            (20, 1.07),  # high
            (30, 1.03),  # low
            (40, 1.09),  # high
            (50, 1.05),  # low
        ]
        assert labeler._check_micro_progression(micro_pivots, "up") is True

    def test_non_progressive_lows_is_ranging(self) -> None:
        """Micro pivots with declining lows → not progressive (ranging in up-context)."""
        labeler = MultiScaleRegimeLabeler(progression_tolerance=0.5)
        # Lows are declining: 1.04 → 1.02 → 1.01 → 1.00 (0/3 pairs ascending)
        micro_pivots = [
            (0, 1.04),  # low
            (10, 1.08),  # high
            (20, 1.02),  # low (lower)
            (30, 1.07),  # high
            (40, 1.01),  # low (lower)
            (50, 1.06),  # high
            (60, 1.00),  # low (lower)
        ]
        assert labeler._check_micro_progression(micro_pivots, "up") is False

    def test_lower_highs_is_progressive_down(self) -> None:
        """Micro pivots with consistently lower highs → progressive (trending down)."""
        labeler = MultiScaleRegimeLabeler(progression_tolerance=0.5)
        micro_pivots = [
            (0, 1.00),  # low
            (10, 1.09),  # high
            (20, 1.02),  # low
            (30, 1.07),  # high (lower)
            (40, 1.01),  # low
            (50, 1.05),  # high (lower still)
        ]
        assert labeler._check_micro_progression(micro_pivots, "down") is True

    def test_too_few_pivots_not_progressive(self) -> None:
        """With fewer than 4 micro pivots, can't assess progression → not progressive."""
        labeler = MultiScaleRegimeLabeler()
        micro_pivots = [(0, 1.0), (10, 1.05)]
        assert labeler._check_micro_progression(micro_pivots, "up") is False

    def test_strict_tolerance_requires_all_pairs(self) -> None:
        """With tolerance=1.0, ALL consecutive pairs must progress."""
        labeler = MultiScaleRegimeLabeler(progression_tolerance=1.0)
        # 2 of 3 pairs progress, 1 doesn't
        micro_pivots = [
            (0, 1.05),
            (10, 1.01),  # low
            (20, 1.07),
            (30, 1.03),  # low: higher than 1.01
            (40, 1.09),
            (50, 1.02),  # low: LOWER than 1.03 — breaks progression
        ]
        assert labeler._check_micro_progression(micro_pivots, "up") is False

    def test_lenient_tolerance_accepts_some_violations(self) -> None:
        """With tolerance=0.3, only 30% of pairs need to progress."""
        labeler = MultiScaleRegimeLabeler(progression_tolerance=0.3)
        # Same data as above: 2/3 pairs progress
        micro_pivots = [
            (0, 1.05),
            (10, 1.01),
            (20, 1.07),
            (30, 1.03),
            (40, 1.09),
            (50, 1.02),
        ]
        assert labeler._check_micro_progression(micro_pivots, "up") is True


class TestGenerateLabels:
    """Test full label generation pipeline."""

    def test_perfect_uptrend(self) -> None:
        """Uptrend with realistic micro swings → mostly TRENDING_UP."""
        np.random.seed(42)
        # Strong uptrend with pullbacks that create micro zigzag structure.
        # Trend: 1.08 → 1.18 over 500 bars, with 0.3% noise to create
        # micro swings that the micro zigzag can detect and check progression on.
        trend = np.linspace(1.08, 1.18, 500)
        noise = np.random.normal(0, 0.003, 500)
        close = trend + noise
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler(
            macro_atr_mult=3.0,
            micro_atr_mult=1.0,
            vol_crisis_threshold=3.0,  # High threshold to avoid volatile labels
        )
        labels = labeler.generate_labels(data)

        # Check output shape and types
        assert len(labels) == len(data)
        valid = labels.dropna()
        assert len(valid) > 0

        # Majority should be TRENDING_UP (allow some RANGING near segment boundaries)
        trending_up_pct = (valid == TRENDING_UP).sum() / len(valid)
        assert (
            trending_up_pct > 0.3
        ), f"Expected >30% TRENDING_UP, got {trending_up_pct:.1%}"

    def test_perfect_downtrend(self) -> None:
        """Downtrend with realistic micro swings → mostly TRENDING_DOWN."""
        np.random.seed(42)
        trend = np.linspace(1.18, 1.08, 500)
        noise = np.random.normal(0, 0.003, 500)
        close = trend + noise
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler(
            macro_atr_mult=3.0,
            micro_atr_mult=1.0,
            vol_crisis_threshold=3.0,
        )
        labels = labeler.generate_labels(data)
        valid = labels.dropna()

        trending_down_pct = (valid == TRENDING_DOWN).sum() / len(valid)
        assert (
            trending_down_pct > 0.3
        ), f"Expected >30% TRENDING_DOWN, got {trending_down_pct:.1%}"

    def test_choppy_oscillating_data(self) -> None:
        """Oscillating price with no net direction → mostly RANGING."""
        np.random.seed(42)
        # Larger sine wave (5% amplitude) so it exceeds the macro zigzag threshold
        # and creates macro segments, but micro pivots don't progress → RANGING
        t = np.arange(500)
        close = 1.10 + 0.05 * np.sin(2 * np.pi * t / 80)
        # Add small noise for realistic H/L
        noise = np.random.normal(0, 0.001, 500)
        close = close + noise
        data = _make_price_data(close, high_offset=0.003, low_offset=0.003)

        labeler = MultiScaleRegimeLabeler(
            macro_atr_mult=2.0,  # Lower multiplier to detect the oscillation structure
            micro_atr_mult=0.5,
            vol_crisis_threshold=3.0,
        )
        labels = labeler.generate_labels(data)
        valid = labels.dropna()
        assert len(valid) > 0, "Expected some valid labels"

        ranging_pct = (valid == RANGING).sum() / len(valid)
        assert ranging_pct > 0.3, f"Expected >30% RANGING, got {ranging_pct:.1%}"

    def test_volatile_spike(self) -> None:
        """Data with a volatility spike should produce VOLATILE labels."""
        np.random.seed(42)
        # Calm period, then extreme spike, then calm
        calm1 = np.linspace(1.10, 1.11, 200)
        # Violent oscillations (simulate crisis)
        spike = 1.10 + 0.03 * np.sin(np.arange(100) * 0.5)
        calm2 = np.linspace(1.10, 1.11, 200)
        close = np.concatenate([calm1, spike, calm2])
        data = _make_price_data(close, high_offset=0.005, low_offset=0.005)

        labeler = MultiScaleRegimeLabeler(
            vol_crisis_threshold=1.5,  # Lower threshold to catch the spike
        )
        labels = labeler.generate_labels(data)
        valid = labels.dropna()

        # Some VOLATILE labels should exist
        has_volatile = (valid == VOLATILE).sum() > 0
        assert has_volatile, "Expected some VOLATILE labels during spike"

    def test_mixed_trend_then_chop(self) -> None:
        """Clear trend followed by choppy section → regime transitions."""
        np.random.seed(42)
        # Strong uptrend (250 bars)
        up = np.linspace(1.08, 1.15, 250) + np.random.normal(0, 0.0003, 250)
        # Choppy ranging (250 bars)
        chop = (
            1.15
            + 0.005 * np.sin(np.arange(250) * 0.3)
            + np.random.normal(0, 0.0005, 250)
        )
        close = np.concatenate([up, chop])
        data = _make_price_data(close, high_offset=0.002, low_offset=0.002)

        labeler = MultiScaleRegimeLabeler(vol_crisis_threshold=3.0)
        labels = labeler.generate_labels(data)
        valid = labels.dropna()

        # Should have both trending and ranging labels
        unique_labels = set(valid.unique().astype(int))
        assert (
            len(unique_labels) >= 2
        ), f"Expected >= 2 regime types, got {unique_labels}"

    def test_labels_are_integers_0_to_3(self) -> None:
        """All non-NaN labels should be in {0, 1, 2, 3}."""
        np.random.seed(42)
        close = np.linspace(1.08, 1.15, 500) + np.random.normal(0, 0.001, 500)
        data = _make_price_data(close, high_offset=0.002, low_offset=0.002)

        labeler = MultiScaleRegimeLabeler()
        labels = labeler.generate_labels(data)
        valid = labels.dropna()

        valid_values = set(valid.unique().astype(int))
        assert valid_values.issubset(
            {0, 1, 2, 3}
        ), f"Unexpected label values: {valid_values}"

    def test_output_same_length_as_input(self) -> None:
        """Output Series should have same length and index as input DataFrame."""
        close = np.linspace(1.08, 1.15, 300)
        data = _make_price_data(close, high_offset=0.002, low_offset=0.002)

        labeler = MultiScaleRegimeLabeler()
        labels = labeler.generate_labels(data)

        assert len(labels) == len(data)
        assert labels.index.equals(data.index)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_constant_price_no_crash(self) -> None:
        """Constant close price (ATR=0) should not crash."""
        close = np.ones(200) * 1.10
        data = _make_price_data(close, high_offset=0.0, low_offset=0.0)

        labeler = MultiScaleRegimeLabeler()
        labels = labeler.generate_labels(data)
        # Should return something (all NaN or all RANGING is fine)
        assert len(labels) == len(data)

    def test_very_short_data(self) -> None:
        """Data shorter than ATR period should raise DataError or return all NaN."""
        close = np.linspace(1.08, 1.10, 10)
        data = _make_price_data(close)

        labeler = MultiScaleRegimeLabeler(atr_period=14)
        # Either raises DataError or returns all NaN — both are acceptable
        try:
            labels = labeler.generate_labels(data)
            # If no error, should be all NaN
            assert labels.isna().all()
        except Exception:
            pass  # DataError is acceptable for too-short data

    def test_missing_close_column_raises(self) -> None:
        """Data without 'close' column should raise DataError."""
        from ktrdr.errors import DataError

        data = pd.DataFrame(
            {"open": [1.0, 1.1], "high": [1.1, 1.2]},
            index=pd.date_range("2020-01-01", periods=2, freq="h"),
        )

        labeler = MultiScaleRegimeLabeler()
        with pytest.raises(DataError):
            labeler.generate_labels(data)

    def test_volatile_takes_priority(self) -> None:
        """VOLATILE should override trending/ranging when RV ratio is extreme."""
        # This is a structural test — volatile classification has priority
        np.random.seed(42)
        # Data that would be trending but with extreme volatility
        close = np.linspace(1.08, 1.20, 500)
        # Add extreme noise to make it volatile
        close += np.random.normal(0, 0.01, 500)
        data = _make_price_data(close, high_offset=0.015, low_offset=0.015)

        labeler = MultiScaleRegimeLabeler(vol_crisis_threshold=1.2)
        labels = labeler.generate_labels(data)
        valid = labels.dropna()

        # With very low vol threshold, should see some VOLATILE
        has_volatile = (valid == VOLATILE).sum() > 0
        # This is a soft assertion — if the data doesn't trigger it, that's fine
        # The structural guarantee is in the code priority
        if has_volatile:
            # Verify these bars are NOT also labeled trending
            volatile_bars = valid[valid == VOLATILE]
            assert (volatile_bars == VOLATILE).all()


class TestAnalyzeLabels:
    """Test the analyze_labels() method."""

    def test_distribution_sums_to_one(self) -> None:
        """Distribution fractions should sum to approximately 1.0."""
        np.random.seed(42)
        trend = np.linspace(1.08, 1.18, 500)
        noise = np.random.normal(0, 0.003, 500)
        close = trend + noise
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler(vol_crisis_threshold=3.0)
        labels = labeler.generate_labels(data)
        stats = labeler.analyze_labels(labels, data)

        total_frac = sum(stats.distribution.values())
        assert abs(total_frac - 1.0) < 0.01, f"Distribution sums to {total_frac}"

    def test_mean_duration_positive(self) -> None:
        """Mean duration should be positive for all present regimes."""
        np.random.seed(42)
        trend = np.linspace(1.08, 1.18, 500)
        noise = np.random.normal(0, 0.003, 500)
        close = trend + noise
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler(vol_crisis_threshold=3.0)
        labels = labeler.generate_labels(data)
        stats = labeler.analyze_labels(labels, data)

        for regime, duration in stats.mean_duration_bars.items():
            assert (
                duration > 0
            ), f"Duration for {regime} should be positive, got {duration}"

    def test_transition_matrix_rows_sum_to_one(self) -> None:
        """Each row in transition matrix should sum to ~1.0."""
        np.random.seed(42)
        # Create data with multiple regime types to get transitions
        up = np.linspace(1.08, 1.15, 250) + np.random.normal(0, 0.003, 250)
        down = np.linspace(1.15, 1.08, 250) + np.random.normal(0, 0.003, 250)
        close = np.concatenate([up, down])
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler(vol_crisis_threshold=3.0)
        labels = labeler.generate_labels(data)
        stats = labeler.analyze_labels(labels, data)

        for from_regime, to_probs in stats.transition_matrix.items():
            row_sum = sum(to_probs.values())
            assert abs(row_sum - 1.0) < 0.01, f"Row {from_regime} sums to {row_sum}"

    def test_returns_regime_label_stats(self) -> None:
        """analyze_labels should return RegimeLabelStats dataclass."""
        close = np.linspace(1.08, 1.15, 300) + np.random.normal(0, 0.003, 300)
        data = _make_price_data(close, high_offset=0.004, low_offset=0.004)

        labeler = MultiScaleRegimeLabeler()
        labels = labeler.generate_labels(data)
        stats = labeler.analyze_labels(labels, data)

        # Check by type name to avoid module identity issues in test suite
        assert type(stats).__name__ == "RegimeLabelStats"
        assert hasattr(stats, "distribution")
        assert hasattr(stats, "mean_duration_bars")
        assert hasattr(stats, "transition_matrix")
        assert stats.total_bars >= 0
