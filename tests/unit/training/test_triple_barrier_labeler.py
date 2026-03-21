"""Tests for TripleBarrierLabeler."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch", reason="torch required for training module imports")

from ktrdr.errors import DataError
from ktrdr.training.triple_barrier_labeler import TripleBarrierLabeler

# --- Fixtures ---


@pytest.fixture
def uptrend_data():
    """Synthetic uptrending OHLCV data (200 bars)."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    # Steady uptrend: 0.1% per bar + small noise
    close = 100.0 * np.cumprod(1 + 0.001 + np.random.normal(0, 0.001, n))
    noise = np.random.uniform(0.001, 0.005, n)
    return pd.DataFrame(
        {
            "open": close * (1 - noise * 0.5),
            "high": close * (1 + noise),
            "low": close * (1 - noise),
            "close": close,
            "volume": np.random.randint(100, 1000, n),
        },
        index=dates,
    )


@pytest.fixture
def downtrend_data():
    """Synthetic downtrending OHLCV data (200 bars)."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    # Steady downtrend: -0.1% per bar + small noise
    close = 100.0 * np.cumprod(1 - 0.001 + np.random.normal(0, 0.001, n))
    noise = np.random.uniform(0.001, 0.005, n)
    return pd.DataFrame(
        {
            "open": close * (1 + noise * 0.5),
            "high": close * (1 + noise),
            "low": close * (1 - noise),
            "close": close,
            "volume": np.random.randint(100, 1000, n),
        },
        index=dates,
    )


@pytest.fixture
def sideways_data():
    """Synthetic sideways OHLCV data (200 bars) — tight range, mean-reverting."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    # Oscillate around 100 with small amplitude
    close = 100.0 + np.random.normal(0, 0.05, n).cumsum() * 0.01
    noise = np.random.uniform(0.0005, 0.001, n)
    return pd.DataFrame(
        {
            "open": close * (1 - noise * 0.5),
            "high": close * (1 + noise),
            "low": close * (1 - noise),
            "close": close,
            "volume": np.random.randint(100, 1000, n),
        },
        index=dates,
    )


@pytest.fixture
def simple_ohlcv():
    """Small OHLCV dataset for precise barrier testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="h")
    return pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [
                100.5,
                101.0,
                103.0,
                101.0,
                100.5,
                100.5,
                100.5,
                100.5,
                100.5,
                100.5,
            ],
            "low": [99.5, 99.0, 99.5, 99.0, 99.5, 99.5, 99.5, 99.5, 99.5, 99.5],
            "close": [
                100.0,
                100.5,
                102.0,
                100.5,
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
            ],
            "volume": [1000] * 10,
        },
        index=dates,
    )


# --- Core Behavior ---


class TestTripleBarrierLabelerCore:
    """Core label generation tests."""

    def test_output_is_series_with_three_classes(self, uptrend_data):
        """Labels should be a Series with values in {-1, 0, +1}."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)

        assert isinstance(labels, pd.Series)
        assert set(labels.dropna().unique()).issubset({-1, 0, 1})

    def test_output_length_trimmed(self, uptrend_data):
        """Last max_holding_period bars are trimmed (no future data)."""
        max_hold = 20
        labeler = TripleBarrierLabeler(max_holding_period=max_hold)
        labels = labeler.generate_labels(uptrend_data)

        assert len(labels) == len(uptrend_data) - max_hold

    def test_uptrend_mostly_positive(self, uptrend_data):
        """Uptrending data should produce mostly +1 (take-profit) labels."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)

        positive_pct = (labels == 1).sum() / len(labels)
        assert (
            positive_pct > 0.4
        ), f"Expected >40% positive labels in uptrend, got {positive_pct:.1%}"

    def test_downtrend_mostly_negative(self, downtrend_data):
        """Downtrending data should produce mostly -1 (stop-loss) labels."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(downtrend_data)

        negative_pct = (labels == -1).sum() / len(labels)
        assert (
            negative_pct > 0.4
        ), f"Expected >40% negative labels in downtrend, got {negative_pct:.1%}"

    def test_sideways_mostly_expiry(self):
        """Sideways data with unreachable barriers should produce mostly 0 (time expiry)."""
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Random walk with moderate vol for barrier computation
        close = 100.0 * np.cumprod(1 + np.random.normal(0, 0.003, n))
        # Tight high/low so barriers are never crossed intrabar
        high = close + 0.01
        low = close - 0.01

        data = pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(100, 1000, n),
            },
            index=dates,
        )

        # Massive multipliers → barriers unreachable → all vertical hits
        labeler = TripleBarrierLabeler(
            pt_multiplier=100.0,
            sl_multiplier=100.0,
            max_holding_period=10,
            vol_method="close",
        )
        labels = labeler.generate_labels(data)

        # With short holding period, returns are small → many should be 0 (expiry)
        expiry_pct = (labels == 0).sum() / len(labels)
        assert (
            expiry_pct > 0.1
        ), f"Expected >10% expiry labels with unreachable barriers, got {expiry_pct:.1%}"

    def test_index_preserved(self, uptrend_data):
        """Labels index matches the first N-max_holding bars of input."""
        max_hold = 20
        labeler = TripleBarrierLabeler(max_holding_period=max_hold)
        labels = labeler.generate_labels(uptrend_data)

        expected_index = uptrend_data.index[: len(uptrend_data) - max_hold]
        pd.testing.assert_index_equal(labels.index, expected_index)


# --- Barrier Mechanics ---


class TestBarrierMechanics:
    """Test barrier hit detection using high/low."""

    def test_intrabar_high_triggers_take_profit(self):
        """High crossing upper barrier triggers +1 even if close doesn't."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Flat close with small oscillation for vol estimation
        np.random.seed(42)
        close = np.full(n, 100.0) + np.random.normal(0, 0.1, n)
        high = close + 0.2
        low = close - 0.2
        # Bar 5 has a massive high spike — way above any barrier
        high[5] = 200.0

        data = pd.DataFrame(
            {
                "open": close.copy(),
                "high": high,
                "low": low,
                "close": close,
                "volume": np.full(n, 1000),
            },
            index=dates,
        )

        labeler = TripleBarrierLabeler(
            pt_multiplier=1.0,
            sl_multiplier=100.0,
            max_holding_period=30,
            vol_span=10,
            vol_method="close",
        )
        labels = labeler.generate_labels(data)

        # Bar 0 should hit upper barrier at bar 5 (high=200 >> upper barrier)
        # sl_multiplier=100 ensures lower barrier is never hit
        assert labels.iloc[0] == 1

    def test_intrabar_low_triggers_stop_loss(self):
        """Low crossing lower barrier triggers -1 even if close doesn't."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        np.random.seed(42)
        close = 100.0 + np.random.normal(0, 0.05, n).cumsum()
        high = close + 0.1
        low = close - 0.1
        # Bar 15 has a massive low spike
        low[15] = 50.0  # Way below any reasonable barrier

        data = pd.DataFrame(
            {
                "open": close.copy(),
                "high": high,
                "low": low,
                "close": close,
                "volume": np.full(n, 1000),
            },
            index=dates,
        )

        labeler = TripleBarrierLabeler(
            pt_multiplier=1.0,
            sl_multiplier=1.0,
            max_holding_period=30,
            vol_span=10,
            vol_method="close",
        )
        labels = labeler.generate_labels(data)

        # Bar 0's label should be -1 because bar 15's low crosses the lower barrier
        assert labels.iloc[0] == -1

    def test_simultaneous_barrier_hit_uses_close(self):
        """When both high and low cross barriers in the same bar, use close direction."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        np.random.seed(42)
        close = 100.0 + np.random.normal(0, 0.05, n).cumsum()
        high = close + 0.1
        low = close - 0.1

        # Bar 10: both barriers crossed, but close is above entry
        high[10] = 200.0
        low[10] = 50.0
        close[10] = 105.0  # Close above entry → +1

        data = pd.DataFrame(
            {
                "open": close.copy(),
                "high": high,
                "low": low,
                "close": close,
                "volume": np.full(n, 1000),
            },
            index=dates,
        )

        labeler = TripleBarrierLabeler(
            pt_multiplier=1.0,
            sl_multiplier=1.0,
            max_holding_period=30,
            vol_span=10,
            vol_method="close",
        )
        labels = labeler.generate_labels(data)
        assert labels.iloc[0] == 1

    def test_simultaneous_barrier_hit_negative_close(self):
        """Simultaneous hit with close below entry → -1."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        np.random.seed(42)
        close = 100.0 + np.random.normal(0, 0.05, n).cumsum()
        high = close + 0.1
        low = close - 0.1

        high[10] = 200.0
        low[10] = 50.0
        close[10] = 95.0  # Close below entry → -1

        data = pd.DataFrame(
            {
                "open": close.copy(),
                "high": high,
                "low": low,
                "close": close,
                "volume": np.full(n, 1000),
            },
            index=dates,
        )

        labeler = TripleBarrierLabeler(
            pt_multiplier=1.0,
            sl_multiplier=1.0,
            max_holding_period=30,
            vol_span=10,
            vol_method="close",
        )
        labels = labeler.generate_labels(data)
        assert labels.iloc[0] == -1

    def test_vertical_barrier_uses_close_direction(self):
        """When no barrier hit within max_holding_period, label based on close."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Moderate random walk with enough vol to set wide barriers
        np.random.seed(42)
        close = 100.0 * np.cumprod(1 + np.random.normal(0, 0.005, n))
        # Tight high/low so barriers are never touched via intrabar
        high = close + 0.01
        low = close - 0.01

        data = pd.DataFrame(
            {
                "open": close.copy(),
                "high": high,
                "low": low,
                "close": close,
                "volume": np.full(n, 1000),
            },
            index=dates,
        )

        # With massive multipliers, barriers are at ~50x daily vol — unreachable
        labeler = TripleBarrierLabeler(
            pt_multiplier=100.0,
            sl_multiplier=100.0,
            max_holding_period=5,
            vol_span=10,
            vol_method="close",
        )
        labeler.generate_labels(data)

        # All should hit vertical barrier — some will get 0 (tiny return), some +1/-1
        # But none should be from upper/lower barrier hits
        holding_periods = labeler.get_holding_periods()
        # All holding periods should be max_holding_period (vertical barrier)
        assert (holding_periods == 5).all(), "Expected all bars to hit vertical barrier"


# --- Volatility Scaling ---


class TestVolatilityScaling:
    """Test that barriers adapt to volatility."""

    def test_higher_vol_span_changes_barrier_width(self):
        """Different vol_span parameters produce different barrier widths."""
        # Need more bars and more volatility variation so vol estimates differ
        np.random.seed(123)
        n = 500
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Create data with varying volatility regimes
        close = np.ones(n) * 100.0
        for i in range(1, n):
            # First half low vol, second half high vol
            vol = 0.001 if i < 250 else 0.005
            close[i] = close[i - 1] * (1 + np.random.normal(0.0001, vol))
        noise = np.random.uniform(0.001, 0.003, n)
        data = pd.DataFrame(
            {
                "open": close * (1 - noise * 0.5),
                "high": close * (1 + noise),
                "low": close * (1 - noise),
                "close": close,
                "volume": np.random.randint(100, 1000, n),
            },
            index=dates,
        )

        labeler_short = TripleBarrierLabeler(vol_span=10, max_holding_period=20)
        labeler_long = TripleBarrierLabeler(vol_span=100, max_holding_period=20)

        labels_short = labeler_short.generate_labels(data)
        labels_long = labeler_long.generate_labels(data)

        # Different vol estimates should produce different barrier widths
        stats_short = labeler_short.get_label_statistics(labels_short)
        stats_long = labeler_long.get_label_statistics(labels_long)
        assert stats_short["avg_upper_barrier_pct"] != pytest.approx(
            stats_long["avg_upper_barrier_pct"], abs=0.001
        )

    def test_higher_pt_multiplier_fewer_take_profits(self, uptrend_data):
        """Higher pt_multiplier → wider upper barrier → fewer take-profit hits."""
        labeler_tight = TripleBarrierLabeler(pt_multiplier=0.5, max_holding_period=20)
        labeler_wide = TripleBarrierLabeler(pt_multiplier=5.0, max_holding_period=20)

        labels_tight = labeler_tight.generate_labels(uptrend_data)
        labels_wide = labeler_wide.generate_labels(uptrend_data)

        tp_tight = (labels_tight == 1).sum()
        tp_wide = (labels_wide == 1).sum()

        assert (
            tp_tight >= tp_wide
        ), f"Tighter barriers should have >= take-profits: {tp_tight} vs {tp_wide}"


# --- Error Handling ---


class TestTripleBarrierErrors:
    """Test error handling and validation."""

    def test_insufficient_data_raises_error(self):
        """Data shorter than max_holding_period + vol_span should raise DataError."""
        dates = pd.date_range("2024-01-01", periods=5, freq="h")
        data = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.0] * 5,
                "volume": [1000] * 5,
            },
            index=dates,
        )
        labeler = TripleBarrierLabeler(max_holding_period=50, vol_span=50)
        with pytest.raises(DataError):
            labeler.generate_labels(data)

    def test_missing_ohlc_columns_raises_error(self):
        """Missing required OHLC columns should raise DataError."""
        dates = pd.date_range("2024-01-01", periods=100, freq="h")
        # Only has close, missing high and low
        data = pd.DataFrame({"close": [100.0] * 100}, index=dates)
        labeler = TripleBarrierLabeler(max_holding_period=20)
        with pytest.raises(DataError):
            labeler.generate_labels(data)

    def test_missing_close_column_raises_error(self):
        """Missing close column raises DataError."""
        dates = pd.date_range("2024-01-01", periods=100, freq="h")
        data = pd.DataFrame(
            {"open": [100.0] * 100, "high": [101.0] * 100, "low": [99.0] * 100},
            index=dates,
        )
        labeler = TripleBarrierLabeler(max_holding_period=20)
        with pytest.raises(DataError):
            labeler.generate_labels(data)


# --- Statistics ---


class TestTripleBarrierStatistics:
    """Test get_label_statistics output."""

    def test_statistics_include_distribution(self, uptrend_data):
        """Statistics should include class distribution percentages."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)
        stats = labeler.get_label_statistics(labels)

        assert "take_profit_pct" in stats
        assert "stop_loss_pct" in stats
        assert "time_expiry_pct" in stats
        # Percentages should sum to 100
        total = (
            stats["take_profit_pct"] + stats["stop_loss_pct"] + stats["time_expiry_pct"]
        )
        assert total == pytest.approx(100.0, abs=0.1)

    def test_statistics_include_holding_period(self, uptrend_data):
        """Statistics should include mean holding period."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)
        stats = labeler.get_label_statistics(labels)

        assert "mean_holding_period" in stats
        assert stats["mean_holding_period"] > 0
        assert stats["mean_holding_period"] <= 20

    def test_statistics_include_barrier_width(self, uptrend_data):
        """Statistics should include average barrier width."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)
        stats = labeler.get_label_statistics(labels)

        assert "avg_upper_barrier_pct" in stats
        assert "avg_lower_barrier_pct" in stats
        assert stats["avg_upper_barrier_pct"] > 0
        assert stats["avg_lower_barrier_pct"] > 0


# --- Holding Periods ---


class TestHoldingPeriods:
    """Test that holding periods are returned alongside labels."""

    def test_generate_labels_returns_holding_periods(self, uptrend_data):
        """generate_labels should also make holding periods available."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)
        holding_periods = labeler.get_holding_periods()

        assert holding_periods is not None
        assert len(holding_periods) == len(labels)
        assert (holding_periods >= 1).all()
        assert (holding_periods <= 20).all()

    def test_holding_periods_index_matches_labels(self, uptrend_data):
        """Holding periods should have same index as labels."""
        labeler = TripleBarrierLabeler(max_holding_period=20)
        labels = labeler.generate_labels(uptrend_data)
        holding_periods = labeler.get_holding_periods()

        pd.testing.assert_index_equal(labels.index, holding_periods.index)


# --- Realistic Data (JTBD) ---


class TestRealisticData:
    """Test with realistic FX-like data to verify balanced class distribution."""

    def test_realistic_fx_data_balanced_distribution(self):
        """Real-ish EURUSD data should produce balanced labels (no class >60%).

        This is the key JTBD validation: TB labels should be more balanced
        than forward returns, which collapsed to 68%+ single-class.
        """
        np.random.seed(42)
        n = 2000
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Simulate FX-like random walk with realistic hourly vol (~0.0008)
        log_returns = np.random.normal(0, 0.0008, n)
        # Add trend regime shifts to make it interesting
        log_returns[:500] += 0.0002  # Uptrend
        log_returns[500:1000] -= 0.0002  # Downtrend
        # 1000-2000: mean-reverting sideways
        close = 1.10 * np.exp(np.cumsum(log_returns))
        noise = np.random.uniform(0.0002, 0.001, n)

        data = pd.DataFrame(
            {
                "open": close * (1 - noise * 0.3),
                "high": close * (1 + noise),
                "low": close * (1 - noise),
                "close": close,
                "volume": np.random.randint(100, 10000, n),
            },
            index=dates,
        )

        labeler = TripleBarrierLabeler(
            pt_multiplier=2.0, sl_multiplier=1.5, max_holding_period=50, vol_span=50
        )
        labels = labeler.generate_labels(data)
        stats = labeler.get_label_statistics(labels)

        # Key JTBD assertion: no single class should dominate (>60%)
        assert (
            stats["take_profit_pct"] <= 60.0
        ), f"TP too dominant: {stats['take_profit_pct']:.1f}%"
        assert (
            stats["stop_loss_pct"] <= 60.0
        ), f"SL too dominant: {stats['stop_loss_pct']:.1f}%"
        assert (
            stats["time_expiry_pct"] <= 60.0
        ), f"Expiry too dominant: {stats['time_expiry_pct']:.1f}%"

        # Both TP and SL should be present (not collapsed to one class)
        assert (
            stats["take_profit_pct"] > 10.0
        ), f"TP too low: {stats['take_profit_pct']:.1f}%"
        assert (
            stats["stop_loss_pct"] > 10.0
        ), f"SL too low: {stats['stop_loss_pct']:.1f}%"

        # Mean holding period should be reasonable (not 1, not max)
        assert stats["mean_holding_period"] > 1
        assert stats["mean_holding_period"] < 45
