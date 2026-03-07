"""Tests for ForwardReturnLabeler."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch", reason="torch required for training module imports")

from ktrdr.errors import DataError
from ktrdr.training.forward_return_labeler import ForwardReturnLabeler


@pytest.fixture
def sample_price_data():
    """Create sample price data with known close prices."""
    dates = pd.date_range("2024-01-01", periods=10, freq="h")
    return pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [
                100.0,
                102.0,
                101.0,
                103.0,
                105.0,
                104.0,
                106.0,
                108.0,
                107.0,
                110.0,
            ],
            "volume": [1000] * 10,
        },
        index=dates,
    )


class TestForwardReturnLabeler:
    """Tests for ForwardReturnLabeler label generation."""

    def test_correct_return_calculation(self, sample_price_data):
        """Verify returns are computed correctly against manual calculation."""
        labeler = ForwardReturnLabeler(horizon=2)
        labels = labeler.generate_labels(sample_price_data)

        # close[0]=100, close[2]=101 -> (101-100)/100 = 0.01
        assert labels.iloc[0] == pytest.approx(0.01)
        # close[1]=102, close[3]=103 -> (103-102)/102
        assert labels.iloc[1] == pytest.approx((103.0 - 102.0) / 102.0)
        # close[2]=101, close[4]=105 -> (105-101)/101
        assert labels.iloc[2] == pytest.approx((105.0 - 101.0) / 101.0)

    def test_output_length(self, sample_price_data):
        """Output length is len(data) - horizon."""
        labeler = ForwardReturnLabeler(horizon=3)
        labels = labeler.generate_labels(sample_price_data)
        assert len(labels) == len(sample_price_data) - 3

    def test_horizon_1_simple_returns(self, sample_price_data):
        """Horizon=1 produces simple 1-bar returns."""
        labeler = ForwardReturnLabeler(horizon=1)
        labels = labeler.generate_labels(sample_price_data)

        assert len(labels) == 9
        # close[0]=100, close[1]=102 -> 0.02
        assert labels.iloc[0] == pytest.approx(0.02)
        # close[1]=102, close[2]=101 -> (101-102)/102
        assert labels.iloc[1] == pytest.approx((101.0 - 102.0) / 102.0)

    def test_horizon_max_produces_single_label(self, sample_price_data):
        """Horizon=len(data)-1 produces exactly one label."""
        labeler = ForwardReturnLabeler(horizon=9)
        labels = labeler.generate_labels(sample_price_data)
        assert len(labels) == 1
        # close[0]=100, close[9]=110 -> 0.10
        assert labels.iloc[0] == pytest.approx(0.10)

    def test_data_too_short_raises_error(self):
        """DataError raised when data has fewer than horizon + 1 bars."""
        dates = pd.date_range("2024-01-01", periods=3, freq="h")
        short_data = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0]},
            index=dates,
        )
        labeler = ForwardReturnLabeler(horizon=5)
        with pytest.raises(DataError, match="fewer than"):
            labeler.generate_labels(short_data)

    def test_nan_in_close_propagates(self):
        """NaN in close column propagates to output without crashing."""
        dates = pd.date_range("2024-01-01", periods=5, freq="h")
        data = pd.DataFrame(
            {"close": [100.0, np.nan, 102.0, 103.0, 104.0]},
            index=dates,
        )
        labeler = ForwardReturnLabeler(horizon=1)
        labels = labeler.generate_labels(data)
        assert len(labels) == 4
        # NaN at index 0 (100 -> NaN) and index 1 (NaN -> 102)
        assert np.isnan(labels.iloc[0])  # (NaN - 100) / 100 ... shift produces NaN
        assert np.isnan(labels.iloc[1])  # (102 - NaN) / NaN
        # Valid values should still compute
        assert labels.iloc[2] == pytest.approx((103.0 - 102.0) / 102.0)

    def test_missing_close_column_raises_error(self):
        """Raise error when close column is missing."""
        dates = pd.date_range("2024-01-01", periods=5, freq="h")
        data = pd.DataFrame({"open": [100.0] * 5}, index=dates)
        labeler = ForwardReturnLabeler(horizon=1)
        with pytest.raises((DataError, ValueError)):
            labeler.generate_labels(data)

    def test_zero_close_price_raises_error(self):
        """Guard against division by zero close price."""
        dates = pd.date_range("2024-01-01", periods=5, freq="h")
        data = pd.DataFrame(
            {"close": [100.0, 0.0, 102.0, 103.0, 104.0]},
            index=dates,
        )
        labeler = ForwardReturnLabeler(horizon=1)
        with pytest.raises(DataError, match="zero"):
            labeler.generate_labels(data)

    def test_default_horizon(self):
        """Default horizon is 20."""
        labeler = ForwardReturnLabeler()
        assert labeler.horizon == 20

    def test_index_preserved(self, sample_price_data):
        """Labels should have the correct index (first N-horizon bars)."""
        labeler = ForwardReturnLabeler(horizon=3)
        labels = labeler.generate_labels(sample_price_data)
        expected_index = sample_price_data.index[:7]
        pd.testing.assert_index_equal(labels.index, expected_index)


class TestForwardReturnLabelerStatistics:
    """Tests for get_label_statistics."""

    def test_statistics_correct(self):
        """Verify statistics are computed correctly."""
        labels = pd.Series([0.01, -0.02, 0.03, -0.01, 0.005])
        labeler = ForwardReturnLabeler()
        stats = labeler.get_label_statistics(labels)

        assert stats["mean"] == pytest.approx(labels.mean())
        assert stats["std"] == pytest.approx(labels.std())
        assert stats["min"] == pytest.approx(-0.02)
        assert stats["max"] == pytest.approx(0.03)
        assert stats["pct_positive"] == pytest.approx(60.0)
        assert stats["pct_negative"] == pytest.approx(40.0)

    def test_all_positive(self):
        """All positive returns."""
        labels = pd.Series([0.01, 0.02, 0.03])
        labeler = ForwardReturnLabeler()
        stats = labeler.get_label_statistics(labels)
        assert stats["pct_positive"] == pytest.approx(100.0)
        assert stats["pct_negative"] == pytest.approx(0.0)

    def test_all_negative(self):
        """All negative returns."""
        labels = pd.Series([-0.01, -0.02, -0.03])
        labeler = ForwardReturnLabeler()
        stats = labeler.get_label_statistics(labels)
        assert stats["pct_positive"] == pytest.approx(0.0)
        assert stats["pct_negative"] == pytest.approx(100.0)

    def test_with_zeros(self):
        """Zero returns are neither positive nor negative."""
        labels = pd.Series([0.01, 0.0, -0.01])
        labeler = ForwardReturnLabeler()
        stats = labeler.get_label_statistics(labels)
        assert stats["pct_positive"] == pytest.approx(100.0 / 3)
        assert stats["pct_negative"] == pytest.approx(100.0 / 3)
