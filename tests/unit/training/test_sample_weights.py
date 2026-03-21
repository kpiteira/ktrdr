"""Tests for sample uniqueness weighting."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.training.sample_weights import compute_uniqueness_weights

# --- Fixtures ---


@pytest.fixture
def non_overlapping():
    """Labels and holding periods with no overlap.

    Positions 0, 2, 4 with hold=1 → active at [0], [2], [4] — no overlap.
    Note: 'non-overlapping' means samples whose active periods don't share
    any index positions, regardless of the datetime index.
    """
    # Use 3 samples spaced apart so active periods [0..0], [2..2], [4..4] don't overlap
    index = pd.date_range("2024-01-01", periods=3, freq="10h")
    labels = pd.Series([1, -1, 1], index=index, name="label")
    holding_periods = pd.Series([1, 1, 1], index=index, name="holding_period")
    return labels, holding_periods


@pytest.fixture
def fully_overlapping():
    """Labels with maximum overlap (consecutive bars, long holding periods)."""
    index = pd.date_range("2024-01-01", periods=10, freq="h")
    labels = pd.Series([1, -1, 1, 0, -1, 1, -1, 0, 1, -1], index=index, name="label")
    holding_periods = pd.Series(
        [10, 10, 10, 10, 10, 10, 10, 10, 10, 10], index=index, name="holding_period"
    )
    return labels, holding_periods


# --- Core Behavior ---


class TestUniquenessWeights:
    """Test uniqueness weight computation."""

    def test_non_overlapping_weights_are_one(self, non_overlapping):
        """Non-overlapping labels should all have weight 1.0."""
        labels, holding_periods = non_overlapping
        weights = compute_uniqueness_weights(labels, holding_periods)

        assert len(weights) == len(labels)
        np.testing.assert_allclose(weights.values, 1.0, atol=0.01)

    def test_overlapping_weights_less_than_one(self, fully_overlapping):
        """Overlapping labels should have weights < 1.0."""
        labels, holding_periods = fully_overlapping
        weights = compute_uniqueness_weights(labels, holding_periods)

        assert (weights < 1.0).all(), "All weights should be < 1.0 with full overlap"

    def test_high_concurrency_gets_lower_weight(self):
        """Bars in high-concurrency regions get lower weights than isolated bars."""
        # Two bars far apart: bar 0 with hold=1 (isolated), bar 1 also hold=1
        # vs two bars close together with long holds (overlapping)
        index_iso = pd.date_range("2024-01-01", periods=2, freq="h")
        labels_iso = pd.Series([1, 1], index=index_iso)
        holds_iso = pd.Series([1, 1], index=index_iso)
        weights_iso = compute_uniqueness_weights(labels_iso, holds_iso)

        # Now two bars that fully overlap
        index_overlap = pd.date_range("2024-01-01", periods=2, freq="h")
        labels_overlap = pd.Series([1, 1], index=index_overlap)
        holds_overlap = pd.Series([5, 5], index=index_overlap)
        weights_overlap = compute_uniqueness_weights(labels_overlap, holds_overlap)

        # Isolated bars should have higher average weight
        assert weights_iso.mean() > weights_overlap.mean()

    def test_single_label_weight_is_one(self):
        """Single label should have weight 1.0."""
        index = pd.date_range("2024-01-01", periods=1, freq="h")
        labels = pd.Series([1], index=index)
        holding_periods = pd.Series([5], index=index)

        weights = compute_uniqueness_weights(labels, holding_periods)
        assert weights.iloc[0] == pytest.approx(1.0)

    def test_weight_length_matches_labels(self, fully_overlapping):
        """Weights array should have same length and index as labels."""
        labels, holding_periods = fully_overlapping
        weights = compute_uniqueness_weights(labels, holding_periods)

        assert len(weights) == len(labels)
        pd.testing.assert_index_equal(weights.index, labels.index)

    def test_weights_are_positive(self, fully_overlapping):
        """All weights should be positive."""
        labels, holding_periods = fully_overlapping
        weights = compute_uniqueness_weights(labels, holding_periods)

        assert (weights > 0).all()

    def test_weights_normalized_mean_approx_one(self):
        """Normalized weights should have mean approximately 1."""
        index = pd.date_range("2024-01-01", periods=20, freq="h")
        labels = pd.Series(np.random.choice([-1, 0, 1], 20), index=index)
        holding_periods = pd.Series(np.random.randint(1, 10, 20), index=index)

        weights = compute_uniqueness_weights(labels, holding_periods, normalize=True)
        assert weights.mean() == pytest.approx(1.0, abs=0.01)

    def test_overlapping_weight_sum_less_than_count(self, fully_overlapping):
        """Overlapping samples: weight sum < sample count (reduced effective N)."""
        labels, holding_periods = fully_overlapping
        weights = compute_uniqueness_weights(labels, holding_periods)

        assert weights.sum() < len(
            labels
        ), f"Weight sum {weights.sum():.2f} should be < sample count {len(labels)}"
