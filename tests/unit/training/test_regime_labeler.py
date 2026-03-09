"""Tests for RegimeLabeler."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError

# Import regime_labeler directly to avoid ktrdr.training.__init__ pulling in torch.
# RegimeLabeler is pure pandas/numpy — no torch dependency.
_spec = importlib.util.spec_from_file_location(
    "ktrdr.training.regime_labeler",
    str(Path(__file__).parents[3] / "ktrdr" / "training" / "regime_labeler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["ktrdr.training.regime_labeler"] = _mod
_spec.loader.exec_module(_mod)
RegimeLabeler = _mod.RegimeLabeler
RegimeLabelStats = _mod.RegimeLabelStats


def _make_price_data(close: list[float], freq: str = "h") -> pd.DataFrame:
    """Helper to create OHLCV DataFrame from close prices."""
    dates = pd.date_range("2024-01-01", periods=len(close), freq=freq)
    return pd.DataFrame(
        {
            "open": close,
            "high": [c * 1.01 for c in close],
            "low": [c * 0.99 for c in close],
            "close": close,
            "volume": [1000] * len(close),
        },
        index=dates,
    )


class TestComputeSignedEfficiencyRatio:
    """Tests for SER computation."""

    def test_perfect_uptrend(self) -> None:
        """Monotonically increasing prices → SER = +1.0."""
        # Each bar increases by 1.0 → net = path length
        close = pd.Series([100.0 + i for i in range(30)])
        labeler = RegimeLabeler(horizon=5)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=5)

        # For any bar T: net = close[T+5] - close[T] = 5.0
        # path = Σ|close[t+1] - close[t]| = 5 * 1.0 = 5.0
        # SER = 5.0 / 5.0 = 1.0
        valid = ser.dropna()
        assert len(valid) > 0
        for val in valid:
            assert val == pytest.approx(1.0)

    def test_perfect_downtrend(self) -> None:
        """Monotonically decreasing prices → SER = -1.0."""
        close = pd.Series([200.0 - i for i in range(30)])
        labeler = RegimeLabeler(horizon=5)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=5)

        valid = ser.dropna()
        assert len(valid) > 0
        for val in valid:
            assert val == pytest.approx(-1.0)

    def test_oscillating_prices(self) -> None:
        """Prices that oscillate without net direction → SER near 0."""
        # Up 1, down 1, up 1, down 1... (even horizon → net = 0)
        close = pd.Series([100.0 + (i % 2) for i in range(30)])
        labeler = RegimeLabeler(horizon=4)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=4)

        valid = ser.dropna()
        assert len(valid) > 0
        for val in valid:
            assert abs(val) < 0.1  # Near zero

    def test_ser_range(self) -> None:
        """SER values should be in [-1.0, +1.0]."""
        np.random.seed(42)
        close = pd.Series(100.0 + np.cumsum(np.random.randn(200)))
        labeler = RegimeLabeler(horizon=10)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=10)

        valid = ser.dropna()
        assert (valid >= -1.0 - 1e-10).all()
        assert (valid <= 1.0 + 1e-10).all()

    def test_last_horizon_bars_are_nan(self) -> None:
        """Last `horizon` values should be NaN (no future data)."""
        close = pd.Series([100.0 + i for i in range(20)])
        labeler = RegimeLabeler(horizon=5)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=5)

        assert len(ser) == len(close)
        assert ser.iloc[-5:].isna().all()
        assert ser.iloc[:-5].notna().all()

    def test_constant_price_zero_division(self) -> None:
        """Constant price → path = 0 → SER should be 0 (not error)."""
        close = pd.Series([100.0] * 20)
        labeler = RegimeLabeler(horizon=5)
        ser = labeler.compute_signed_efficiency_ratio(close, horizon=5)

        valid = ser.dropna()
        # Net move is 0, path is 0, SER should be 0
        for val in valid:
            assert val == pytest.approx(0.0)


class TestComputeRealizedVolatilityRatio:
    """Tests for RV ratio computation."""

    def test_stable_volatility(self) -> None:
        """Constant volatility → RV_ratio ≈ 1.0."""
        np.random.seed(42)
        # Generate random walk with stable volatility
        returns = np.random.randn(300) * 0.01
        close = pd.Series(100.0 * np.exp(np.cumsum(returns)))
        labeler = RegimeLabeler(horizon=24, vol_lookback=120)
        rv_ratio = labeler.compute_realized_volatility_ratio(
            close, horizon=24, lookback=120
        )

        # After warm-up (lookback period), ratio should be around 1.0
        valid = rv_ratio.dropna()
        assert len(valid) > 0
        # Allow reasonable tolerance — stochastic data
        median_ratio = valid.median()
        assert 0.5 < median_ratio < 2.0

    def test_volatility_spike(self) -> None:
        """Sudden volatility increase → RV_ratio >> 1."""
        np.random.seed(42)
        # Low vol period, then high vol period
        low_vol = np.random.randn(200) * 0.001
        high_vol = np.random.randn(50) * 0.01  # 10x volatility
        returns = np.concatenate([low_vol, high_vol])
        close = pd.Series(100.0 * np.exp(np.cumsum(returns)))

        labeler = RegimeLabeler(horizon=10, vol_lookback=50)
        rv_ratio = labeler.compute_realized_volatility_ratio(
            close, horizon=10, lookback=50
        )

        # At the transition point, forward vol >> historical vol
        # Check that some values exceed 2.0 (crisis threshold)
        valid = rv_ratio.dropna()
        assert valid.max() > 2.0

    def test_rv_ratio_positive(self) -> None:
        """RV ratio should always be non-negative."""
        np.random.seed(42)
        close = pd.Series(100.0 + np.cumsum(np.random.randn(200)))
        labeler = RegimeLabeler(horizon=10, vol_lookback=50)
        rv_ratio = labeler.compute_realized_volatility_ratio(
            close, horizon=10, lookback=50
        )

        valid = rv_ratio.dropna()
        assert (valid >= 0).all()


class TestGenerateLabels:
    """Tests for the full label generation pipeline."""

    def test_perfect_uptrend_labels(self) -> None:
        """Monotonically increasing prices → all TRENDING_UP (0)."""
        close = [100.0 + i * 0.5 for i in range(200)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=24, trending_threshold=0.5, vol_lookback=120)
        labels = labeler.generate_labels(data)

        valid = labels.dropna()
        assert len(valid) > 0
        # All should be TRENDING_UP (0) since it's a perfect uptrend
        assert (valid == 0).all()

    def test_perfect_downtrend_labels(self) -> None:
        """Monotonically decreasing prices → all TRENDING_DOWN (1)."""
        close = [200.0 - i * 0.5 for i in range(200)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=24, trending_threshold=0.5, vol_lookback=120)
        labels = labeler.generate_labels(data)

        valid = labels.dropna()
        assert len(valid) > 0
        assert (valid == 1).all()

    def test_oscillating_labels(self) -> None:
        """Flat/oscillating data → predominantly RANGING (2)."""
        # Small oscillation around 100
        close = [100.0 + 0.1 * np.sin(i * 0.5) for i in range(300)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=24, trending_threshold=0.5, vol_lookback=120)
        labels = labeler.generate_labels(data)

        valid = labels.dropna()
        assert len(valid) > 0
        # Most should be RANGING (2)
        ranging_frac = (valid == 2).sum() / len(valid)
        assert ranging_frac > 0.8

    def test_volatile_labels(self) -> None:
        """Extreme volatility spike → VOLATILE (3) labels appear."""
        np.random.seed(42)
        # Calm period then extreme volatility
        calm = np.random.randn(200) * 0.001
        crisis = np.random.randn(50) * 0.02  # 20x volatility
        tail = np.random.randn(50) * 0.001
        returns = np.concatenate([calm, crisis, tail])
        close = list(100.0 * np.exp(np.cumsum(returns)))
        data = _make_price_data(close)

        labeler = RegimeLabeler(horizon=10, vol_crisis_threshold=2.0, vol_lookback=50)
        labels = labeler.generate_labels(data)

        valid = labels.dropna()
        # Should have some VOLATILE labels during crisis period
        volatile_count = (valid == 3).sum()
        assert volatile_count > 0

    def test_last_horizon_bars_nan(self) -> None:
        """Last `horizon` bars should be NaN."""
        close = [100.0 + i * 0.1 for i in range(200)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=10, vol_lookback=50)
        labels = labeler.generate_labels(data)

        assert len(labels) == len(data)
        assert labels.iloc[-10:].isna().all()

    def test_label_values_in_range(self) -> None:
        """Labels should only contain values 0, 1, 2, 3, or NaN."""
        np.random.seed(42)
        close = list(100.0 + np.cumsum(np.random.randn(200)))
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=10)
        labels = labeler.generate_labels(data)

        valid = labels.dropna()
        unique_vals = set(valid.unique())
        assert unique_vals.issubset({0, 1, 2, 3})

    def test_volatile_takes_priority_over_trending(self) -> None:
        """VOLATILE classification should override trending even with high SER."""
        # Directly test the classification priority using compute methods
        # rather than relying on synthetic data that may not hit exact thresholds
        close = pd.Series([100.0 + i * 0.5 for i in range(200)])
        labeler = RegimeLabeler(
            horizon=10,
            trending_threshold=0.3,
            vol_crisis_threshold=2.0,
            vol_lookback=50,
        )

        ser = labeler.compute_signed_efficiency_ratio(close, horizon=10)

        # Verify SER is high (trending) at some point
        valid_ser = ser.dropna()
        assert (valid_ser > 0.3).any(), "Need some trending bars for this test"

        # Now manually verify the priority logic:
        # Create data where both SER > threshold AND RV > threshold
        # The label should be VOLATILE, not TRENDING
        # We test this by checking generate_labels on data with known vol spike
        np.random.seed(42)
        calm = np.random.randn(200) * 0.0005
        # Extreme upward spike — high SER AND high RV ratio
        crisis = np.array(
            [0.05, -0.04, 0.06, -0.03, 0.05] * 10
        )  # net positive, very volatile
        returns = np.concatenate([calm, crisis])
        close_vals = list(100.0 * np.exp(np.cumsum(returns)))
        data = _make_price_data(close_vals)

        labels = labeler.generate_labels(data)

        # In the crisis region (bars 195-210), check that VOLATILE appears
        crisis_labels = labels.iloc[195:215].dropna()
        has_volatile = (crisis_labels == 3).any()
        assert (
            has_volatile
        ), "VOLATILE should override trending when RV ratio > threshold"

    def test_output_is_series(self) -> None:
        """Output should be a pandas Series."""
        close = [100.0 + i * 0.1 for i in range(200)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=10, vol_lookback=50)
        labels = labeler.generate_labels(data)

        assert isinstance(labels, pd.Series)

    def test_index_matches_input(self) -> None:
        """Labels index should match input DataFrame index."""
        close = [100.0 + i * 0.1 for i in range(200)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=10, vol_lookback=50)
        labels = labeler.generate_labels(data)

        pd.testing.assert_index_equal(labels.index, data.index)

    def test_default_parameters(self) -> None:
        """Default parameters match specification."""
        labeler = RegimeLabeler()
        assert labeler.horizon == 24
        assert labeler.trending_threshold == 0.5
        assert labeler.vol_crisis_threshold == 2.0
        assert labeler.vol_lookback == 120

    def test_missing_close_column_raises(self) -> None:
        """DataError raised when 'close' column is missing."""
        dates = pd.date_range("2024-01-01", periods=50, freq="h")
        data = pd.DataFrame({"open": [100.0] * 50}, index=dates)
        labeler = RegimeLabeler(horizon=5)
        with pytest.raises(DataError, match="close"):
            labeler.generate_labels(data)

    def test_data_too_short_raises(self) -> None:
        """DataError raised when data shorter than horizon + lookback."""
        close = [100.0 + i for i in range(10)]
        data = _make_price_data(close)
        labeler = RegimeLabeler(horizon=24)
        with pytest.raises(DataError):
            labeler.generate_labels(data)


class TestAnalyzeLabels:
    """Tests for analyze_labels and RegimeLabelStats."""

    def _make_simple_labels(self) -> tuple[pd.Series, pd.DataFrame]:
        """Create labels with known properties for testing.

        Pattern: 10 TRENDING_UP, 5 RANGING, 10 TRENDING_DOWN, 5 RANGING = 30 bars
        """
        pattern = (
            [0] * 10  # TRENDING_UP
            + [2] * 5  # RANGING
            + [1] * 10  # TRENDING_DOWN
            + [2] * 5  # RANGING
        )
        dates = pd.date_range("2024-01-01", periods=30, freq="h")
        labels = pd.Series(pattern, index=dates, dtype=float)
        # Create price data with close values that match regime expectations
        close = []
        price = 100.0
        for label in pattern:
            if label == 0:  # TRENDING_UP
                price += 0.5
            elif label == 1:  # TRENDING_DOWN
                price -= 0.5
            else:  # RANGING
                price += 0.01
            close.append(price)
        data = _make_price_data(close)
        return labels, data

    def test_returns_dataclass(self) -> None:
        """analyze_labels returns a RegimeLabelStats dataclass."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)
        assert isinstance(stats, RegimeLabelStats)

    def test_distribution_sums_to_one(self) -> None:
        """Distribution fractions should sum to ~1.0."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        total = sum(stats.distribution.values())
        assert total == pytest.approx(1.0)

    def test_distribution_values_correct(self) -> None:
        """Distribution matches known label counts."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        # 10/30 TRENDING_UP, 10/30 TRENDING_DOWN, 10/30 RANGING
        assert stats.distribution["trending_up"] == pytest.approx(10 / 30)
        assert stats.distribution["trending_down"] == pytest.approx(10 / 30)
        assert stats.distribution["ranging"] == pytest.approx(10 / 30)

    def test_mean_duration_positive(self) -> None:
        """Mean duration > 0 for all regimes present."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        for regime, duration in stats.mean_duration_bars.items():
            assert duration > 0, f"Duration for {regime} should be > 0"

    def test_mean_duration_correct(self) -> None:
        """Mean duration matches known run lengths."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        # TRENDING_UP: one run of 10 → mean = 10
        assert stats.mean_duration_bars["trending_up"] == pytest.approx(10.0)
        # TRENDING_DOWN: one run of 10 → mean = 10
        assert stats.mean_duration_bars["trending_down"] == pytest.approx(10.0)
        # RANGING: two runs of 5 → mean = 5
        assert stats.mean_duration_bars["ranging"] == pytest.approx(5.0)

    def test_transition_matrix_rows_sum_to_one(self) -> None:
        """Transition matrix rows should sum to ~1.0."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        for from_regime, to_probs in stats.transition_matrix.items():
            row_sum = sum(to_probs.values())
            assert row_sum == pytest.approx(
                1.0
            ), f"Row for {from_regime} sums to {row_sum}"

    def test_transition_matrix_correct(self) -> None:
        """Transition matrix matches known transitions."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        # Transitions: TRENDING_UP→RANGING, RANGING→TRENDING_DOWN, TRENDING_DOWN→RANGING
        # TRENDING_UP transitions only to RANGING
        assert stats.transition_matrix["trending_up"]["ranging"] == pytest.approx(1.0)
        # TRENDING_DOWN transitions only to RANGING
        assert stats.transition_matrix["trending_down"]["ranging"] == pytest.approx(1.0)
        # RANGING transitions to both TRENDING_DOWN (1st time) and end (2nd run is last)
        # Actually: RANGING→TRENDING_DOWN is the only transition from RANGING
        assert stats.transition_matrix["ranging"]["trending_down"] == pytest.approx(1.0)

    def test_return_by_regime_signs(self) -> None:
        """Trending up should have positive return, trending down negative."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        assert stats.mean_return_by_regime["trending_up"] > 0
        assert stats.mean_return_by_regime["trending_down"] < 0

    def test_total_bars(self) -> None:
        """total_bars matches label count."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        assert stats.total_bars == 30

    def test_total_transitions(self) -> None:
        """total_transitions matches known count."""
        labels, data = self._make_simple_labels()
        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        # TRENDING_UP→RANGING, RANGING→TRENDING_DOWN, TRENDING_DOWN→RANGING = 3
        assert stats.total_transitions == 3

    def test_absent_regime_excluded(self) -> None:
        """Regime with 0 bars excluded from stats."""
        # All TRENDING_UP — no other regimes
        dates = pd.date_range("2024-01-01", periods=20, freq="h")
        labels = pd.Series([0.0] * 20, index=dates)
        close = [100.0 + i for i in range(20)]
        data = _make_price_data(close)

        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        assert "trending_up" in stats.distribution
        assert "trending_down" not in stats.distribution
        assert "volatile" not in stats.distribution

    def test_handles_nan_labels(self) -> None:
        """NaN labels (last horizon bars) are excluded from analysis."""
        pattern = [0.0] * 15 + [float("nan")] * 5
        dates = pd.date_range("2024-01-01", periods=20, freq="h")
        labels = pd.Series(pattern, index=dates)
        close = [100.0 + i for i in range(20)]
        data = _make_price_data(close)

        labeler = RegimeLabeler(horizon=5)
        stats = labeler.analyze_labels(labels, data)

        assert stats.total_bars == 15
        assert stats.distribution["trending_up"] == pytest.approx(1.0)
