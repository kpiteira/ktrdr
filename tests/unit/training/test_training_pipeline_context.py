"""Tests for TrainingPipeline context label dispatch (source=context)."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from ktrdr.training.training_pipeline import TrainingPipeline  # noqa: E402


@pytest.fixture
def daily_price_data():
    """Create sample daily price data dict (timeframe -> DataFrame)."""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    close = 100.0 + np.cumsum(np.random.randn(100) * 0.5)
    df = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.randint(100, 1000, 100),
        },
        index=dates,
    )
    return {"1d": df}


class TestCreateLabelsContext:
    """Test create_labels with source=context."""

    def test_returns_long_tensor(self, daily_price_data):
        """Context labels produce LongTensor (3-class classification)."""
        label_config = {"source": "context", "horizon": 5}
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        assert labels.dtype == torch.int64

    def test_three_classes(self, daily_price_data):
        """Context labels contain only values 0, 1, 2."""
        label_config = {"source": "context", "horizon": 5}
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        unique_values = set(labels.numpy().tolist())
        assert unique_values.issubset({0, 1, 2})

    def test_drops_nan_trailing_bars(self, daily_price_data):
        """Labels exclude trailing NaN bars (last `horizon` bars)."""
        horizon = 5
        label_config = {"source": "context", "horizon": horizon}
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        # ContextLabeler produces NaN for last `horizon` bars
        # create_labels should drop those, resulting in N - horizon labels
        assert len(labels) == 100 - horizon

    def test_default_params(self, daily_price_data):
        """Default horizon=5 used when not specified."""
        label_config = {"source": "context"}
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        # Default horizon is 5, so length = 100 - 5 = 95
        assert len(labels) == 95

    def test_custom_params(self, daily_price_data):
        """Custom horizon and thresholds are passed through."""
        label_config = {
            "source": "context",
            "horizon": 10,
            "bullish_threshold": 0.01,
            "bearish_threshold": -0.01,
        }
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        # horizon=10 means length = 100 - 10 = 90
        assert len(labels) == 90
        assert labels.dtype == torch.int64

    def test_no_nan_in_output(self, daily_price_data):
        """Output tensor must not contain NaN values."""
        label_config = {"source": "context", "horizon": 5}
        labels = TrainingPipeline.create_labels(daily_price_data, label_config)
        assert not torch.isnan(labels.float()).any()
