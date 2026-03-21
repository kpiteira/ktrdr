"""Tests for CUSUM event filter."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.training.cusum_filter import CUSUMFilter

# --- Fixtures ---


@pytest.fixture
def rising_prices():
    """Monotonically rising prices (200 bars)."""
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    close = 100.0 * np.cumprod(1 + np.full(200, 0.002))
    return pd.DataFrame({"close": close}, index=dates)


@pytest.fixture
def flat_prices():
    """Nearly flat prices with tiny noise."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    close = 100.0 + np.random.normal(0, 0.001, 200).cumsum()
    return pd.DataFrame({"close": close}, index=dates)


@pytest.fixture
def volatile_prices():
    """Highly volatile prices."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    close = 100.0 * np.cumprod(1 + np.random.normal(0, 0.02, 200))
    return pd.DataFrame({"close": close}, index=dates)


# --- Core Behavior ---


class TestCUSUMFilterCore:
    """Core CUSUM filter behavior."""

    def test_output_is_boolean_series(self, rising_prices):
        """Filter output should be a boolean Series aligned with input."""
        filt = CUSUMFilter(threshold=0.01)
        events = filt.filter(rising_prices)

        assert isinstance(events, pd.Series)
        assert events.dtype == bool
        assert len(events) == len(rising_prices)
        pd.testing.assert_index_equal(events.index, rising_prices.index)

    def test_rising_prices_emit_events_at_intervals(self, rising_prices):
        """Monotonically rising prices should emit events at regular intervals."""
        # 0.2% per bar log return, so threshold must be < 0.002 to accumulate
        filt = CUSUMFilter(threshold=0.001)
        events = filt.filter(rising_prices)

        n_events = events.sum()
        assert n_events > 0, "Should emit at least one event for steady rise"
        assert n_events < len(rising_prices), "Should not emit on every bar"

    def test_flat_prices_emit_few_events(self, flat_prices):
        """Nearly flat prices should emit very few events."""
        filt = CUSUMFilter(threshold=0.01)
        events = filt.filter(flat_prices)

        n_events = events.sum()
        assert n_events < 5, f"Expected <5 events for flat prices, got {n_events}"

    def test_volatile_prices_emit_more_events(self, volatile_prices, flat_prices):
        """Volatile prices should emit more events than flat prices."""
        filt = CUSUMFilter(threshold=0.005)
        events_vol = filt.filter(volatile_prices)
        events_flat = filt.filter(flat_prices)

        assert events_vol.sum() > events_flat.sum()


# --- Threshold Sensitivity ---


class TestThresholdSensitivity:
    """Test that threshold parameter controls event frequency."""

    def test_higher_threshold_fewer_events(self, volatile_prices):
        """Higher threshold → fewer events."""
        filt_low = CUSUMFilter(threshold=0.005)
        filt_high = CUSUMFilter(threshold=0.05)

        events_low = filt_low.filter(volatile_prices)
        events_high = filt_high.filter(volatile_prices)

        assert events_low.sum() >= events_high.sum()

    def test_zero_threshold_events_on_most_bars(self, volatile_prices):
        """With threshold=0 (or very small), nearly every bar fires."""
        filt = CUSUMFilter(threshold=1e-10)
        events = filt.filter(volatile_prices)

        # Most bars should fire with near-zero threshold
        assert events.sum() > len(volatile_prices) * 0.5


# --- Reset Behavior ---


class TestResetBehavior:
    """Test that CUSUM sums reset after event fires."""

    def test_reset_after_event(self):
        """After positive event fires, S_pos resets to zero."""
        dates = pd.date_range("2024-01-01", periods=20, freq="h")
        # Steady rise then flat — ~1% per bar rise, threshold 0.005
        close = np.concatenate(
            [
                100.0 * np.cumprod(1 + np.full(10, 0.01)),  # ~1% per bar rise
                np.full(10, 100.0 * (1.01**10)),  # Flat
            ]
        )
        data = pd.DataFrame({"close": close}, index=dates)

        filt = CUSUMFilter(threshold=0.005)
        events = filt.filter(data)

        # Should have events during rise, then stop during flat
        rise_events = events.iloc[:10].sum()
        flat_events = events.iloc[10:].sum()
        assert rise_events > 0
        assert flat_events == 0

    def test_both_branches_fire_independently(self):
        """Positive and negative CUSUM branches fire independently."""
        dates = pd.date_range("2024-01-01", periods=30, freq="h")
        # Big rise then big fall
        close = np.concatenate(
            [
                100.0 * np.cumprod(1 + np.full(10, 0.01)),  # ~1% per bar rise
                100.0 * (1.01**10) * np.cumprod(1 + np.full(10, -0.01)),  # ~1% fall
                np.full(10, 100.0),  # Flat
            ]
        )
        data = pd.DataFrame({"close": close}, index=dates)

        filt = CUSUMFilter(threshold=0.005)
        events = filt.filter(data)

        # Should have events in both rising and falling phases
        assert events.sum() >= 2  # At least one in each phase


# --- Auto-Threshold ---


class TestAutoThreshold:
    """Test automatic threshold from volatility."""

    def test_cusum_multiplier_mode(self, volatile_prices):
        """When threshold is None, compute from vol estimate."""
        filt = CUSUMFilter(threshold=None, cusum_multiplier=1.0, vol_span=50)
        events = filt.filter(volatile_prices)

        # Should still work and produce events
        assert events.sum() > 0

    def test_higher_cusum_multiplier_fewer_events(self, volatile_prices):
        """Higher cusum_multiplier → higher threshold → fewer events."""
        filt_low = CUSUMFilter(threshold=None, cusum_multiplier=0.5, vol_span=50)
        filt_high = CUSUMFilter(threshold=None, cusum_multiplier=3.0, vol_span=50)

        events_low = filt_low.filter(volatile_prices)
        events_high = filt_high.filter(volatile_prices)

        assert events_low.sum() >= events_high.sum()

    def test_explicit_threshold_overrides_multiplier(self, volatile_prices):
        """When threshold is explicit, cusum_multiplier is ignored."""
        filt = CUSUMFilter(threshold=0.01, cusum_multiplier=100.0)
        events = filt.filter(volatile_prices)

        # Should use threshold=0.01, not 100.0 * vol
        assert events.sum() > 0
