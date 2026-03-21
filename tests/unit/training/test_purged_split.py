"""Tests for purged train/validation split with embargo.

Ensures no information leakage between train and validation sets when
triple barrier labels have overlapping active periods.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.training.sample_weights import purged_train_val_split


@pytest.fixture
def simple_data():
    """100 bars with short holding periods (5 bars each)."""
    n = 100
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    labels = pd.Series(np.random.choice([0, 1, 2], n), index=index)
    holding_periods = pd.Series(np.full(n, 5), index=index)
    return labels, holding_periods


@pytest.fixture
def long_hold_data():
    """100 bars with long holding periods (30 bars each)."""
    n = 100
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    labels = pd.Series(np.random.choice([0, 1, 2], n), index=index)
    holding_periods = pd.Series(np.full(n, 30), index=index)
    return labels, holding_periods


class TestPurgedTrainValSplit:
    """Test purged train/validation split."""

    def test_returns_train_and_val_indices(self, simple_data):
        """Split returns two numpy arrays of indices."""
        labels, holding_periods = simple_data
        train_idx, val_idx = purged_train_val_split(labels, holding_periods)

        assert isinstance(train_idx, np.ndarray)
        assert isinstance(val_idx, np.ndarray)
        assert train_idx.dtype in (np.int64, np.int32, np.intp)
        assert val_idx.dtype in (np.int64, np.int32, np.intp)

    def test_val_set_is_last_fraction(self, simple_data):
        """Validation set should be the last val_ratio fraction of data."""
        labels, holding_periods = simple_data
        val_ratio = 0.2
        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=val_ratio
        )

        n = len(labels)
        val_start = int(n * (1 - val_ratio))

        # All val indices should be >= val_start
        assert (val_idx >= val_start).all()
        # Val set should contain all indices from val_start onwards
        assert len(val_idx) == n - val_start

    def test_no_overlap_between_train_and_val(self, simple_data):
        """Train and val index sets must not overlap."""
        labels, holding_periods = simple_data
        train_idx, val_idx = purged_train_val_split(labels, holding_periods)

        overlap = np.intersect1d(train_idx, val_idx)
        assert len(overlap) == 0, f"Found {len(overlap)} overlapping indices"

    def test_purging_removes_leaking_samples(self):
        """Training samples whose active periods overlap val set are purged."""
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.ones(n, dtype=int), index=index)
        # Long holding period: bar 75 has active period [75, 75+20) = [75, 95)
        # With val_ratio=0.2, val starts at bar 80
        # So bars 61-79 with hold=20 overlap val set and should be purged
        holding_periods = pd.Series(np.full(n, 20), index=index)

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.0
        )

        val_start = 80  # int(100 * 0.8)
        # Bar 60 has active period [60, 80) — overlaps val start at 80? No, 80 is excluded.
        # Bar 61 has active period [61, 81) — overlaps val at bar 80. Should be purged.
        # So bars 61-79 should be purged from training set
        for i in range(61, val_start):
            assert (
                i not in train_idx
            ), f"Bar {i} should be purged (active period overlaps val)"

        # Bar 60 should NOT be purged: active period [60, 80) doesn't overlap [80, 100)
        assert 60 in train_idx, "Bar 60 should NOT be purged"

    def test_embargo_removes_additional_buffer(self):
        """Embargo removes extra training samples before the purge boundary."""
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.ones(n, dtype=int), index=index)
        # Hold=1 so purging removes nothing — isolates embargo effect
        holding_periods = pd.Series(np.full(n, 1), index=index)

        # Without embargo
        train_no_emb, _ = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.0
        )

        # With 5% embargo (5 bars)
        train_with_emb, _ = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.05
        )

        # Embargo should remove exactly 5 additional samples
        assert len(train_no_emb) - len(train_with_emb) == 5
        # Bars 75-79 should be embargoed (val starts at 80, embargo=5)
        for i in range(75, 80):
            assert i not in train_with_emb
        # Bar 74 should still be in training set
        assert 74 in train_with_emb

    def test_no_leakage_with_active_periods(self):
        """No training sample's active period extends into the validation set."""
        n = 200
        index = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.random.choice([0, 1, 2], n), index=index)
        # Variable holding periods
        rng = np.random.default_rng(42)
        holding_periods = pd.Series(rng.integers(1, 50, n), index=index)

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.01
        )

        val_start = val_idx.min()

        # For each training sample, its active period must not overlap val set
        for i in train_idx:
            hold = int(holding_periods.iloc[i])
            active_end = i + hold  # exclusive
            assert active_end <= val_start, (
                f"Training sample {i} with hold={hold} has active period "
                f"ending at {active_end}, overlapping val starting at {val_start}"
            )

    def test_short_holding_periods_minimal_purging(self):
        """Short holding periods near boundary need minimal purging."""
        n = 100
        index = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.ones(n, dtype=int), index=index)
        holding_periods = pd.Series(np.full(n, 1), index=index)  # hold=1

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.0
        )

        # With hold=1, bar i's active period is just [i, i+1).
        # Only bar 79 has active period [79, 80) which doesn't overlap [80, 100).
        # So no purging needed — all 80 training samples retained.
        assert len(train_idx) == 80

    def test_long_holding_periods_significant_purging(self, long_hold_data):
        """Long holding periods cause significant purging."""
        labels, holding_periods = long_hold_data

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.0
        )

        # With hold=30 and val starting at bar 80:
        # Bar i has active period [i, i+30). Overlaps [80, 100) when i+30 > 80, i.e., i > 50.
        # So bars 51-79 are purged (29 bars), leaving 51 training samples (bars 0-50).
        assert len(train_idx) == 51

    def test_holding_period_longer_than_data(self):
        """Edge case: holding period longer than entire dataset."""
        n = 20
        index = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.ones(n, dtype=int), index=index)
        holding_periods = pd.Series(np.full(n, 100), index=index)  # hold >> n

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.0
        )

        # Val starts at bar 16. Every training bar [0, 16) has active period
        # extending well past bar 16, so ALL are purged.
        assert len(train_idx) == 0

    def test_output_indices_are_valid(self, simple_data):
        """All returned indices must be valid positions in the original data."""
        labels, holding_periods = simple_data
        n = len(labels)
        train_idx, val_idx = purged_train_val_split(labels, holding_periods)

        assert train_idx.min() >= 0
        assert train_idx.max() < n
        assert val_idx.min() >= 0
        assert val_idx.max() < n

    def test_custom_val_ratio(self, simple_data):
        """Different val_ratio values work correctly."""
        labels, holding_periods = simple_data

        for ratio in [0.1, 0.3, 0.5]:
            train_idx, val_idx = purged_train_val_split(
                labels, holding_periods, val_ratio=ratio
            )
            n = len(labels)
            expected_val_size = n - int(n * (1 - ratio))
            assert len(val_idx) == expected_val_size

    def test_empty_labels(self):
        """Empty input returns empty arrays."""
        labels = pd.Series([], dtype=int)
        holding_periods = pd.Series([], dtype=int)

        train_idx, val_idx = purged_train_val_split(labels, holding_periods)

        assert len(train_idx) == 0
        assert len(val_idx) == 0
