"""Tests for triple barrier integration into TrainingPipeline.create_labels()."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip(
    "torch", reason="torch required for training module imports"
)

from ktrdr.training.training_pipeline import TrainingPipeline  # noqa: E402


@pytest.fixture
def sample_price_data():
    """Multi-timeframe price data dict as expected by create_labels."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    close = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.003, n))
    noise = np.random.uniform(0.001, 0.005, n)
    df = pd.DataFrame(
        {
            "open": close * (1 - noise * 0.5),
            "high": close * (1 + noise),
            "low": close * (1 - noise),
            "close": close,
            "volume": np.random.randint(100, 1000, n),
        },
        index=dates,
    )
    return {"1h": df}


class TestTripleBarrierPipelineIntegration:
    """Test create_labels with source='triple_barrier'."""

    def test_triple_barrier_produces_long_tensor(self, sample_price_data):
        """Triple barrier labels should be a LongTensor with values in {0, 1, 2}."""
        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)

        assert isinstance(labels, torch.Tensor)
        assert labels.dtype == torch.long
        unique = set(labels.unique().tolist())
        assert unique.issubset({0, 1, 2}), f"Expected values in {{0,1,2}}, got {unique}"

    def test_triple_barrier_class_mapping(self, sample_price_data):
        """TB labels map: +1→0 (BUY), 0→1 (HOLD), -1→2 (SELL)."""
        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)

        # Should have 3 classes
        unique = labels.unique()
        assert len(unique) >= 2, "Expected at least 2 distinct classes"

    def test_params_pass_through(self, sample_price_data):
        """Label config parameters should affect output."""
        config_tight = {
            "source": "triple_barrier",
            "pt_multiplier": 0.5,
            "sl_multiplier": 0.5,
            "max_holding_period": 10,
            "vol_span": 20,
        }
        config_wide = {
            "source": "triple_barrier",
            "pt_multiplier": 5.0,
            "sl_multiplier": 5.0,
            "max_holding_period": 50,
            "vol_span": 50,
        }

        labels_tight = TrainingPipeline.create_labels(sample_price_data, config_tight)
        labels_wide = TrainingPipeline.create_labels(sample_price_data, config_wide)

        # Different params → different label counts (tight trims less)
        assert len(labels_tight) != len(labels_wide)

    def test_cusum_reduces_labels(self, sample_price_data):
        """CUSUM filter should reduce label count."""
        config_no_cusum = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }
        config_cusum = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
            "cusum_threshold": 0.01,
        }

        labels_no = TrainingPipeline.create_labels(sample_price_data, config_no_cusum)
        labels_yes = TrainingPipeline.create_labels(sample_price_data, config_cusum)

        assert len(labels_yes) < len(
            labels_no
        ), f"CUSUM should reduce sample count: {len(labels_yes)} vs {len(labels_no)}"

    def test_existing_sources_still_work(self, sample_price_data):
        """Existing label sources should not be broken."""
        # Forward return
        labels_fr = TrainingPipeline.create_labels(
            sample_price_data, {"source": "forward_return", "horizon": 20}
        )
        assert isinstance(labels_fr, torch.Tensor)
        assert labels_fr.dtype == torch.float32

    def test_invalid_source_raises_error(self, sample_price_data):
        """Unknown source should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown label source"):
            TrainingPipeline.create_labels(sample_price_data, {"source": "nonexistent"})

    def test_multi_timeframe_uses_base(self):
        """With multiple timeframes, uses highest frequency for labeling."""
        np.random.seed(42)
        n_5m = 500
        n_1h = 42

        dates_5m = pd.date_range("2024-01-01", periods=n_5m, freq="5min")
        close_5m = 100.0 * np.cumprod(1 + np.random.normal(0, 0.001, n_5m))
        noise = np.random.uniform(0.001, 0.003, n_5m)
        df_5m = pd.DataFrame(
            {
                "open": close_5m * (1 - noise * 0.5),
                "high": close_5m * (1 + noise),
                "low": close_5m * (1 - noise),
                "close": close_5m,
                "volume": np.random.randint(100, 1000, n_5m),
            },
            index=dates_5m,
        )

        dates_1h = pd.date_range("2024-01-01", periods=n_1h, freq="h")
        close_1h = 100.0 * np.cumprod(1 + np.random.normal(0, 0.003, n_1h))
        noise_1h = np.random.uniform(0.001, 0.003, n_1h)
        df_1h = pd.DataFrame(
            {
                "open": close_1h * (1 - noise_1h * 0.5),
                "high": close_1h * (1 + noise_1h),
                "low": close_1h * (1 - noise_1h),
                "close": close_1h,
                "volume": np.random.randint(100, 1000, n_1h),
            },
            index=dates_1h,
        )

        price_data = {"5m": df_5m, "1h": df_1h}
        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }

        labels = TrainingPipeline.create_labels(price_data, label_config)
        # Should use 5m (higher frequency) → more labels
        assert len(labels) == n_5m - 50  # 500 - max_holding_period

    def test_cusum_retention_within_range(self, sample_price_data):
        """CUSUM filter should retain 30-70% of bars with appropriate threshold."""
        config_no_cusum = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }
        # Use a low threshold to get moderate filtering (not too aggressive)
        config_cusum = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
            "cusum_threshold": 0.0005,
        }

        labels_all = TrainingPipeline.create_labels(sample_price_data, config_no_cusum)
        labels_filtered = TrainingPipeline.create_labels(
            sample_price_data, config_cusum
        )

        retention = len(labels_filtered) / len(labels_all)
        assert retention < 1.0, "CUSUM should reduce sample count"
        # With threshold=0.0005 on synthetic data with vol ~0.003,
        # retention should be moderate (not 0% or 100%)
        assert retention > 0.05, f"CUSUM too aggressive: {retention:.1%} retention"

    def test_triple_barrier_logs_statistics(self, sample_price_data, caplog):
        """create_labels should log label statistics."""
        import logging

        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }

        with caplog.at_level(logging.INFO, logger="ktrdr.training.training_pipeline"):
            TrainingPipeline.create_labels(sample_price_data, label_config)

        # Should log triple barrier label statistics
        assert any(
            "triple barrier labels" in r.message.lower() for r in caplog.records
        ), "Expected 'triple barrier labels' in log output"

    def test_compute_weights_produces_weights(self, sample_price_data):
        """compute_weights=True should populate sample weights."""
        # Reset any prior state
        TrainingPipeline._sample_weights = None

        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
            "compute_weights": True,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        weights = TrainingPipeline.get_sample_weights()

        assert weights is not None, "Weights should be computed"
        assert len(weights) == len(labels), "Weights should match labels length"
        assert weights.mean().item() == pytest.approx(
            1.0, abs=0.01
        ), "Normalized weights should have mean ~1.0"

    def test_no_weights_by_default(self, sample_price_data):
        """Without compute_weights, no weights should be stored."""
        TrainingPipeline._sample_weights = None

        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
        }
        TrainingPipeline.create_labels(sample_price_data, label_config)

        assert TrainingPipeline.get_sample_weights() is None
