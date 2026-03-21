"""Tests for triple barrier training integration.

Verifies that purged split, CUSUM alignment, and sample weights
are correctly wired into the training orchestrator for TB labels.
"""

import numpy as np
import pandas as pd
import pytest
import torch

from ktrdr.training.sample_weights import purged_train_val_split
from ktrdr.training.training_pipeline import TrainingPipeline


class TestPurgedSplitIntegration:
    """Test that purged split is correctly integrated with TB labels."""

    def test_tb_labels_produce_holding_periods(self):
        """Triple barrier labeler must expose holding periods for purging."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        close = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        high = close + np.abs(np.random.randn(n) * 0.0005)
        low = close - np.abs(np.random.randn(n) * 0.0005)
        price_data = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close, "volume": 1000},
            index=dates,
        )

        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
            "vol_method": "atr",
            "compute_weights": True,
        }

        labels = TrainingPipeline.create_labels({"1h": price_data}, label_config)
        weights = TrainingPipeline.get_sample_weights()

        # Labels should be shorter than input (trimmed by max_holding_period)
        assert len(labels) < n
        assert len(labels) == n - 50  # trimmed by max_holding_period

        # Weights should be computed
        assert weights is not None
        assert len(weights) == len(labels)

    def test_purged_split_with_real_holding_periods(self):
        """Purged split with realistic TB holding periods removes boundary leakage."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        # Simulate variable holding periods (typical TB output)
        labels = pd.Series(np.random.choice([0, 1, 2], n), index=dates)
        holding_periods = pd.Series(np.random.randint(1, 50, n), index=dates)

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.01
        )

        val_start = val_idx.min()

        # Verify no leakage: no training sample's active period reaches into val
        for i in train_idx:
            hold = int(holding_periods.iloc[i])
            assert i + hold <= val_start, (
                f"Leakage: training sample {i} with hold={hold} "
                f"extends to {i + hold}, past val_start={val_start}"
            )

    def test_purged_split_retains_reasonable_train_size(self):
        """Purged split shouldn't remove too many samples with typical TB parameters."""
        n = 1000
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        labels = pd.Series(np.random.choice([0, 1, 2], n), index=dates)
        # Average hold of 15 bars (typical for hourly data)
        holding_periods = pd.Series(np.random.randint(5, 25, n), index=dates)

        train_idx, val_idx = purged_train_val_split(
            labels, holding_periods, val_ratio=0.2, embargo_pct=0.01
        )

        # Should retain at least 70% of unpurged training set
        unpurged_train_size = int(n * 0.8)
        assert len(train_idx) >= unpurged_train_size * 0.7, (
            f"Purging removed too many: {len(train_idx)} < "
            f"{unpurged_train_size * 0.7:.0f} (70% of {unpurged_train_size})"
        )


class TestCUSUMFeatureAlignment:
    """Test CUSUM-filtered feature/label alignment."""

    def test_cusum_event_mask_stored(self):
        """CUSUM filtering stores event mask for feature alignment."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        close = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        high = close + np.abs(np.random.randn(n) * 0.0005)
        low = close - np.abs(np.random.randn(n) * 0.0005)
        price_data = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close, "volume": 1000},
            index=dates,
        )

        label_config = {
            "source": "triple_barrier",
            "pt_multiplier": 2.0,
            "sl_multiplier": 1.5,
            "max_holding_period": 50,
            "vol_span": 50,
            "cusum_threshold": 0,  # auto-threshold
            "cusum_multiplier": 0.5,
        }

        labels = TrainingPipeline.create_labels({"1h": price_data}, label_config)
        mask = TrainingPipeline.get_cusum_event_mask()

        assert mask is not None
        assert isinstance(mask, pd.Series)
        assert mask.dtype == bool
        # CUSUM should select a subset of bars
        assert mask.sum() < len(mask)
        # Labels should match CUSUM-selected bars (after TB trimming)
        assert len(labels) <= mask.sum()

    def test_cusum_labels_fewer_than_all_bar_labels(self):
        """CUSUM-filtered labels should be fewer than all-bar labels."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        close = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        high = close + np.abs(np.random.randn(n) * 0.0005)
        low = close - np.abs(np.random.randn(n) * 0.0005)
        price_data = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close, "volume": 1000},
            index=dates,
        )

        # Without CUSUM
        labels_all = TrainingPipeline.create_labels(
            {"1h": price_data},
            {
                "source": "triple_barrier",
                "pt_multiplier": 2.0,
                "sl_multiplier": 1.5,
                "max_holding_period": 50,
                "vol_span": 50,
            },
        )

        # With CUSUM
        labels_cusum = TrainingPipeline.create_labels(
            {"1h": price_data},
            {
                "source": "triple_barrier",
                "pt_multiplier": 2.0,
                "sl_multiplier": 1.5,
                "max_holding_period": 50,
                "vol_span": 50,
                "cusum_threshold": 0,
                "cusum_multiplier": 0.5,
            },
        )

        assert len(labels_cusum) < len(
            labels_all
        ), f"CUSUM should reduce labels: {len(labels_cusum)} >= {len(labels_all)}"


class TestSampleWeightsPassThrough:
    """Test that sample weights are accessible after label creation."""

    def test_weights_computed_when_requested(self):
        """compute_weights=True produces normalized weights."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        close = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        high = close + np.abs(np.random.randn(n) * 0.0005)
        low = close - np.abs(np.random.randn(n) * 0.0005)
        price_data = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close, "volume": 1000},
            index=dates,
        )

        labels = TrainingPipeline.create_labels(
            {"1h": price_data},
            {
                "source": "triple_barrier",
                "pt_multiplier": 2.0,
                "sl_multiplier": 1.5,
                "max_holding_period": 50,
                "vol_span": 50,
                "compute_weights": True,
            },
        )

        weights = TrainingPipeline.get_sample_weights()
        assert weights is not None
        assert isinstance(weights, torch.Tensor)
        assert len(weights) == len(labels)
        # Normalized: mean ≈ 1.0
        assert weights.mean().item() == pytest.approx(1.0, abs=0.1)

    def test_weights_not_computed_when_not_requested(self):
        """compute_weights=False (default) produces no weights."""
        n = 500
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        close = 1.1 + np.cumsum(np.random.randn(n) * 0.001)
        high = close + np.abs(np.random.randn(n) * 0.0005)
        low = close - np.abs(np.random.randn(n) * 0.0005)
        price_data = pd.DataFrame(
            {"open": close, "high": high, "low": low, "close": close, "volume": 1000},
            index=dates,
        )

        TrainingPipeline.create_labels(
            {"1h": price_data},
            {
                "source": "triple_barrier",
                "pt_multiplier": 2.0,
                "sl_multiplier": 1.5,
                "max_holding_period": 50,
                "vol_span": 50,
            },
        )

        weights = TrainingPipeline.get_sample_weights()
        assert weights is None


class TestModelTrainerSampleWeights:
    """Test that ModelTrainer accepts and uses sample weights."""

    def test_trainer_accepts_sample_weights(self):
        """ModelTrainer.train() should accept sample_weights parameter."""
        from ktrdr.training.model_trainer import ModelTrainer

        trainer = ModelTrainer(
            config={"epochs": 2, "batch_size": 16, "learning_rate": 0.01},
        )

        # Simple model
        model = torch.nn.Sequential(
            torch.nn.Linear(4, 8),
            torch.nn.ReLU(),
            torch.nn.Linear(8, 3),
        )

        n = 100
        X_train = torch.randn(n, 4)
        y_train = torch.randint(0, 3, (n,))
        X_val = torch.randn(20, 4)
        y_val = torch.randint(0, 3, (20,))
        weights = torch.ones(n)

        # Should not raise
        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            sample_weights=weights,
        )

        assert "final_train_loss" in result

    def test_weighted_training_changes_gradients(self):
        """Weighted samples should affect training differently than uniform."""
        from ktrdr.training.model_trainer import ModelTrainer

        torch.manual_seed(42)
        n = 200
        X_train = torch.randn(n, 4)
        y_train = torch.randint(0, 3, (n,))
        X_val = torch.randn(40, 4)
        y_val = torch.randint(0, 3, (40,))

        # Highly skewed weights: first half matters 10x more
        weights = torch.ones(n)
        weights[: n // 2] = 10.0

        # Train with uniform weights
        torch.manual_seed(42)
        model_uniform = torch.nn.Sequential(
            torch.nn.Linear(4, 8), torch.nn.ReLU(), torch.nn.Linear(8, 3)
        )
        trainer_u = ModelTrainer(
            config={"epochs": 5, "batch_size": 32, "learning_rate": 0.01}
        )
        trainer_u.train(
            model=model_uniform,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )

        # Train with skewed weights
        torch.manual_seed(42)
        model_weighted = torch.nn.Sequential(
            torch.nn.Linear(4, 8), torch.nn.ReLU(), torch.nn.Linear(8, 3)
        )
        trainer_w = ModelTrainer(
            config={"epochs": 5, "batch_size": 32, "learning_rate": 0.01}
        )
        trainer_w.train(
            model=model_weighted,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            sample_weights=weights,
        )

        # Models should produce different weights after training
        params_u = list(model_uniform.parameters())
        params_w = list(model_weighted.parameters())
        different = any(
            not torch.allclose(pu, pw, atol=1e-4) for pu, pw in zip(params_u, params_w)
        )
        assert different, "Weighted training should produce different model parameters"
