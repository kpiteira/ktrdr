"""Tests for TrainingPipeline regression label support."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from ktrdr.training.training_pipeline import TrainingPipeline  # noqa: E402


@pytest.fixture
def sample_price_data():
    """Create sample price data dict (timeframe -> DataFrame)."""
    dates = pd.date_range("2024-01-01", periods=100, freq="h")
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
    return {"1h": df}


class TestCreateLabelsForwardReturn:
    """Test create_labels with source=forward_return."""

    def test_returns_float_tensor(self, sample_price_data):
        """Forward return labels produce FloatTensor."""
        label_config = {"source": "forward_return", "horizon": 10}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert labels.dtype == torch.float32

    def test_correct_length(self, sample_price_data):
        """Forward return labels have length = N - horizon."""
        label_config = {"source": "forward_return", "horizon": 10}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert len(labels) == 90  # 100 - 10

    def test_default_horizon(self, sample_price_data):
        """Default horizon is 20 when not specified."""
        label_config = {"source": "forward_return"}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert len(labels) == 80  # 100 - 20


class TestCreateLabelsZigzag:
    """Test create_labels with source=zigzag (unchanged)."""

    def test_returns_long_tensor(self, sample_price_data):
        """Zigzag labels produce LongTensor."""
        label_config = {
            "source": "zigzag",
            "zigzag_threshold": 0.02,
            "label_lookahead": 10,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert labels.dtype == torch.int64

    def test_default_source_is_zigzag(self, sample_price_data):
        """Default source (no key) uses zigzag."""
        label_config = {
            "zigzag_threshold": 0.02,
            "label_lookahead": 10,
        }
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)
        assert labels.dtype == torch.int64


class TestEvaluateModelRegression:
    """Test evaluate_model with regression output."""

    def test_regression_returns_directional_accuracy(self):
        """Regression evaluation uses directional accuracy, not argmax."""
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(4, 1))
        X_test = torch.randn(50, 4)
        y_test = torch.randn(50)  # float labels

        metrics = TrainingPipeline.evaluate_model(
            model, X_test, y_test, output_format="regression"
        )
        assert "test_accuracy" in metrics
        assert 0.0 <= metrics["test_accuracy"] <= 1.0

    def test_regression_uses_huber_loss(self):
        """Regression evaluation uses HuberLoss, not CrossEntropyLoss."""
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(4, 1))
        X_test = torch.randn(50, 4)
        y_test = torch.randn(50)

        # Should not raise "expected scalar type Long but found Float"
        metrics = TrainingPipeline.evaluate_model(
            model, X_test, y_test, output_format="regression"
        )
        assert "test_loss" in metrics
        assert metrics["test_loss"] > 0

    def test_regression_returns_mae(self):
        """Regression evaluation includes MAE metric."""
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(4, 1))
        X_test = torch.randn(50, 4)
        y_test = torch.randn(50)

        metrics = TrainingPipeline.evaluate_model(
            model, X_test, y_test, output_format="regression"
        )
        assert "mae" in metrics
        assert metrics["mae"] >= 0

    def test_classification_unchanged(self):
        """Classification evaluation still uses CrossEntropyLoss and argmax."""
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(4, 3))
        X_test = torch.randn(50, 4)
        y_test = torch.randint(0, 3, (50,))

        metrics = TrainingPipeline.evaluate_model(
            model, X_test, y_test, output_format="classification"
        )
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics

    def test_default_output_format_is_classification(self):
        """Default output_format is classification (backward compatible)."""
        import torch.nn as nn

        model = nn.Sequential(nn.Linear(4, 3))
        X_test = torch.randn(50, 4)
        y_test = torch.randint(0, 3, (50,))

        # No output_format arg — should use classification
        metrics = TrainingPipeline.evaluate_model(model, X_test, y_test)
        assert "precision" in metrics


class TestFeatureLabelAlignment:
    """Test feature-label alignment for forward return labels."""

    def test_features_truncated_to_match_labels(self, sample_price_data):
        """Features should be truncatable to match forward return label length."""
        label_config = {"source": "forward_return", "horizon": 20}
        labels = TrainingPipeline.create_labels(sample_price_data, label_config)

        # Simulate features tensor (100 samples)
        features = torch.randn(100, 4)

        # Truncation (as done in local_orchestrator)
        features_aligned = features[: len(labels)]

        assert len(features_aligned) == len(labels)
        assert len(features_aligned) == 80
