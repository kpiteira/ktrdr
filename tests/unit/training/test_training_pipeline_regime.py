"""Tests for TrainingPipeline regime label support (Task 4.1)."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from ktrdr.training.training_pipeline import TrainingPipeline  # noqa: E402


@pytest.fixture
def sample_price_data():
    """Create sample price data dict (timeframe -> DataFrame) with enough bars for regime labeling."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    close = 100.0 + np.cumsum(np.random.randn(200) * 0.5)
    df = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.randint(100, 1000, 200),
        },
        index=dates,
    )
    return {"1h": df}


class TestCreateLabelsRegime:
    """Test create_labels with source=regime."""

    def test_returns_long_tensor(self, sample_price_data):
        """Regime labels produce LongTensor (classification, not regression)."""
        label_config = {"source": "regime", "horizon": 24}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert labels.dtype == torch.int64

    def test_four_class_labels(self, sample_price_data):
        """Regime labels have values in range 0-3."""
        label_config = {"source": "regime", "horizon": 24}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        unique_vals = torch.unique(labels)
        for v in unique_vals:
            assert 0 <= v.item() <= 3

    def test_correct_length(self, sample_price_data):
        """Regime labels drop last `horizon` bars (no future data)."""
        horizon = 24
        label_config = {"source": "regime", "horizon": horizon}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        # RegimeLabeler drops last `horizon` bars as NaN, create_labels should filter them
        assert len(labels) == 200 - horizon

    def test_default_params(self, sample_price_data):
        """Default params used when not specified in config."""
        label_config = {"source": "regime"}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        # Default horizon=24, so length should be 200-24=176
        assert len(labels) == 200 - 24
        assert labels.dtype == torch.int64

    def test_custom_params(self, sample_price_data):
        """Custom params override defaults."""
        label_config = {
            "source": "regime",
            "horizon": 10,
            "trending_threshold": 0.3,
            "vol_crisis_threshold": 3.0,
            "vol_lookback": 60,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert len(labels) == 200 - 10
        assert labels.dtype == torch.int64

    def test_multi_timeframe_uses_base(self):
        """Multi-timeframe data uses base (most frequent) timeframe for labels."""
        np.random.seed(42)
        # 5m data (more bars)
        dates_5m = pd.date_range("2024-01-01", periods=500, freq="5min")
        close_5m = 100.0 + np.cumsum(np.random.randn(500) * 0.1)
        df_5m = pd.DataFrame(
            {
                "open": close_5m - 0.1,
                "high": close_5m + 0.2,
                "low": close_5m - 0.2,
                "close": close_5m,
                "volume": np.random.randint(100, 1000, 500),
            },
            index=dates_5m,
        )
        # 1h data (fewer bars)
        dates_1h = pd.date_range("2024-01-01", periods=200, freq="h")
        close_1h = 100.0 + np.cumsum(np.random.randn(200) * 0.5)
        df_1h = pd.DataFrame(
            {
                "open": close_1h - 0.1,
                "high": close_1h + 0.5,
                "low": close_1h - 0.5,
                "close": close_1h,
                "volume": np.random.randint(100, 1000, 200),
            },
            index=dates_1h,
        )
        price_data = {"5m": df_5m, "1h": df_1h}
        label_config = {"source": "regime", "horizon": 24}
        labels = TrainingPipeline.create_labels(price_data, label_config)
        # Should use 5m (base timeframe): 500 - 24 = 476
        assert len(labels) == 500 - 24


class TestCreateLabelsUnknownSource:
    """Test create_labels with unknown source raises clear error."""

    def test_unknown_source_raises_error(self, sample_price_data):
        """Unknown label source should raise ValueError with descriptive message."""
        label_config = {"source": "nonexistent_source"}
        with pytest.raises(ValueError, match="Unknown label source"):
            TrainingPipeline.create_labels(sample_price_data, label_config)
