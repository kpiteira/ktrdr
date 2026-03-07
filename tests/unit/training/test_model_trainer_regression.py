"""Tests for ModelTrainer regression support."""

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.training.model_trainer import ModelTrainer  # noqa: E402


def make_regression_config(**overrides) -> dict:
    """Create a regression training config."""
    config = {
        "output_format": "regression",
        "loss": "huber",
        "huber_delta": 0.01,
        "batch_size": 32,
        "gradient_clip": 1.0,
        "optimizer": "adam",
        "learning_rate": 0.001,
        "epochs": 3,
    }
    config.update(overrides)
    return config


def make_classification_config() -> dict:
    """Create a classification training config."""
    return {
        "output_format": "classification",
        "batch_size": 32,
        "gradient_clip": 1.0,
        "optimizer": "adam",
        "learning_rate": 0.001,
        "epochs": 3,
    }


def build_regression_model(input_size: int = 4) -> nn.Module:
    """Build a simple 1-output regression model."""
    return nn.Sequential(
        nn.Linear(input_size, 16),
        nn.ReLU(),
        nn.Linear(16, 1),
    )


def build_classification_model(input_size: int = 4) -> nn.Module:
    """Build a simple 3-output classification model."""
    return nn.Sequential(
        nn.Linear(input_size, 16),
        nn.ReLU(),
        nn.Linear(16, 3),
    )


class TestModelTrainerRegression:
    """Test ModelTrainer regression training support."""

    def test_regression_huber_loss_trains(self):
        """ModelTrainer trains regression model with Huber loss."""
        config = make_regression_config(loss="huber")
        trainer = ModelTrainer(config=config)
        model = build_regression_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randn(100) * 0.01
        X_val = torch.randn(20, 4)
        y_val = torch.randn(20) * 0.01

        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )
        assert "final_train_loss" in result
        assert result["final_train_loss"] > 0

    def test_regression_mse_loss_trains(self):
        """ModelTrainer trains regression model with MSE loss."""
        config = make_regression_config(loss="mse")
        trainer = ModelTrainer(config=config)
        model = build_regression_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randn(100) * 0.01

        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
        )
        assert "final_train_loss" in result

    def test_directional_accuracy_in_metrics(self):
        """Directional accuracy reported in training metrics."""
        config = make_regression_config()
        trainer = ModelTrainer(config=config)
        model = build_regression_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randn(100) * 0.01

        trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
        )
        assert len(trainer.history) == 3
        for metrics in trainer.history:
            assert 0.0 <= metrics.train_accuracy <= 1.0

    def test_classification_unchanged(self):
        """Classification training still works with integer labels."""
        config = make_classification_config()
        trainer = ModelTrainer(config=config)
        model = build_classification_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randint(0, 3, (100,))

        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
        )
        assert "final_train_loss" in result

    def test_early_stopping_with_regression(self):
        """Early stopping works with regression loss."""
        config = make_regression_config(epochs=50)
        config["early_stopping"] = {"patience": 2, "monitor": "val_loss"}
        trainer = ModelTrainer(config=config)
        model = build_regression_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randn(100) * 0.01
        X_val = torch.randn(20, 4)
        y_val = torch.randn(20) * 0.01

        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )
        assert "final_train_loss" in result

    def test_progress_callback_receives_regression_metrics(self):
        """Progress callback receives regression metrics."""
        config = make_regression_config()
        callback_data = []

        def callback(epoch, total_epochs, metrics):
            callback_data.append(metrics)

        trainer = ModelTrainer(config=config, progress_callback=callback)
        model = build_regression_model()
        X_train = torch.randn(100, 4)
        y_train = torch.randn(100) * 0.01

        trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
        )
        epoch_callbacks = [
            c for c in callback_data if c.get("progress_type") == "epoch"
        ]
        assert len(epoch_callbacks) >= 1
        for cb in epoch_callbacks:
            assert "train_accuracy" in cb
