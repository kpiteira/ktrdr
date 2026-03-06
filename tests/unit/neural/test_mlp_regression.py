"""Tests for MLPTradingModel regression support."""

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.neural.models.mlp import MLPTradingModel  # noqa: E402


def make_config(
    output_format: str = "classification",
    loss: str = "huber",
    huber_delta: float = 0.01,
) -> dict:
    """Create a model config dict."""
    config = {
        "architecture": {
            "hidden_layers": [32, 16],
            "dropout": 0.1,
            "activation": "relu",
        },
        "training": {
            "learning_rate": 0.001,
            "epochs": 5,
        },
        "output_format": output_format,
    }
    if output_format == "regression":
        config["loss"] = loss
        config["huber_delta"] = huber_delta
    return config


class TestMLPRegressionBuildModel:
    """Test build_model regression vs classification output."""

    def test_regression_model_has_1_output(self):
        """Regression model has 1 output neuron."""
        model = MLPTradingModel(make_config("regression"))
        net = model.build_model(input_size=4)
        # Get last Linear layer
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 1

    def test_classification_model_has_3_outputs(self):
        """Classification model has 3 output neurons (unchanged)."""
        model = MLPTradingModel(make_config("classification"))
        net = model.build_model(input_size=4)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 3

    def test_default_is_classification(self):
        """No output_format defaults to classification (3 outputs)."""
        config = make_config("classification")
        del config["output_format"]
        model = MLPTradingModel(config)
        net = model.build_model(input_size=4)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 3


class TestMLPRegressionTraining:
    """Test MLP training in regression mode."""

    @pytest.fixture
    def regression_model(self):
        """Create a regression model ready to train."""
        model = MLPTradingModel(make_config("regression", loss="huber"))
        model.model = model.build_model(input_size=4)
        return model

    @pytest.fixture
    def regression_data(self):
        """Create training data for regression."""
        X = torch.randn(100, 4)
        y = torch.randn(100) * 0.01  # Small return values
        return X, y

    def test_regression_huber_loss_trains(self, regression_model, regression_data):
        """Regression training with Huber loss runs without error."""
        X, y = regression_data
        history = regression_model.train(X, y)
        assert len(history["train_loss"]) == 5
        assert all(v > 0 for v in history["train_loss"])

    def test_regression_mse_loss_trains(self, regression_data):
        """Regression training with MSE loss runs without error."""
        model = MLPTradingModel(make_config("regression", loss="mse"))
        model.model = model.build_model(input_size=4)
        X, y = regression_data
        history = model.train(X, y)
        assert len(history["train_loss"]) == 5

    def test_directional_accuracy_computed(self, regression_model, regression_data):
        """Directional accuracy is computed during regression training."""
        X, y = regression_data
        history = regression_model.train(X, y)
        assert "train_accuracy" in history
        # Directional accuracy should be between 0 and 1
        for acc in history["train_accuracy"]:
            assert 0.0 <= acc <= 1.0

    def test_float_labels_accepted(self, regression_model):
        """Float labels are accepted without .long() conversion."""
        X = torch.randn(50, 4)
        y = torch.tensor([0.01, -0.02, 0.005] * 16 + [0.01, -0.02])  # float labels
        history = regression_model.train(X, y)
        assert len(history["train_loss"]) > 0

    def test_classification_unchanged(self):
        """Classification training still works with integer labels."""
        model = MLPTradingModel(make_config("classification"))
        model.model = model.build_model(input_size=4)
        X = torch.randn(50, 4)
        y = torch.tensor([0, 1, 2] * 16 + [0, 1])  # classification labels
        history = model.train(X, y)
        assert len(history["train_loss"]) == 5

    def test_regression_with_validation(self, regression_data):
        """Regression training works with validation data."""
        model = MLPTradingModel(make_config("regression"))
        model.model = model.build_model(input_size=4)
        X, y = regression_data
        X_val = torch.randn(20, 4)
        y_val = torch.randn(20) * 0.01
        history = model.train(X, y, validation_data=(X_val, y_val))
        assert len(history["val_loss"]) == 5
        assert len(history["val_accuracy"]) == 5
