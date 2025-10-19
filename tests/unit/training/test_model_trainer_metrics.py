"""Unit tests for ModelTrainer metrics emission (M2)."""

import torch
import torch.nn as nn
from ktrdr.training.model_trainer import ModelTrainer


class SimpleModel(nn.Module):
    """Simple model for testing."""

    def __init__(self, input_dim, output_dim):
        super().__init__()
        self.fc = nn.Linear(input_dim, output_dim)

    def forward(self, x):
        return self.fc(x)


class TestModelTrainerMetricsEmission:
    """Test that ModelTrainer emits full metrics in progress callback."""

    def test_progress_callback_includes_full_metrics(self):
        """Test that progress callback includes full_metrics field."""
        # Given a model trainer with progress callback
        captured_metrics = []

        def progress_callback(epoch, total_epochs, metrics):
            captured_metrics.append(metrics)

        config = {
            "epochs": 2,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        # When training for 2 epochs
        model = SimpleModel(input_dim=10, output_dim=3)
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))
        X_val = torch.randn(32, 10)
        y_val = torch.randint(0, 3, (32,))

        trainer.train(model, X_train, y_train, X_val, y_val)

        # Then epoch-level callbacks should include metrics fields
        epoch_callbacks = [m for m in captured_metrics if m.get("progress_type") == "epoch"]
        assert len(epoch_callbacks) == 2  # 2 epochs

        for metrics in epoch_callbacks:
            # Verify all required fields are present
            assert "epoch" in metrics
            assert "train_loss" in metrics
            assert "train_accuracy" in metrics
            assert "val_loss" in metrics
            assert "val_accuracy" in metrics
            assert "learning_rate" in metrics
            assert "duration" in metrics
            assert "timestamp" in metrics

            # Verify types
            assert isinstance(metrics["epoch"], int)
            assert isinstance(metrics["train_loss"], float)
            assert isinstance(metrics["train_accuracy"], float)
            assert isinstance(metrics["duration"], float)
            assert isinstance(metrics["timestamp"], str)

            # Verify None handling for val metrics
            assert metrics["val_loss"] is None or isinstance(metrics["val_loss"], float)
            assert metrics["val_accuracy"] is None or isinstance(metrics["val_accuracy"], float)

    def test_full_metrics_contains_timestamp(self):
        """Test that metrics include ISO format timestamp."""
        # Given a model trainer
        captured_metrics = []

        def progress_callback(epoch, total_epochs, metrics):
            captured_metrics.append(metrics)

        config = {
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        # When training
        model = SimpleModel(input_dim=10, output_dim=3)
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Then timestamp should be in ISO format
        epoch_callbacks = [m for m in captured_metrics if m.get("progress_type") == "epoch"]
        assert len(epoch_callbacks) >= 1

        timestamp = epoch_callbacks[0]["timestamp"]
        # Basic ISO format check (YYYY-MM-DDTHH:MM:SSZ or similar)
        assert "T" in timestamp
        assert len(timestamp) >= 19  # Minimum ISO format length

    def test_full_metrics_with_validation_data(self):
        """Test that metrics include validation metrics when available."""
        # Given a model trainer with validation data
        captured_metrics = []

        def progress_callback(epoch, total_epochs, metrics):
            captured_metrics.append(metrics)

        config = {
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        # When training with validation data
        model = SimpleModel(input_dim=10, output_dim=3)
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))
        X_val = torch.randn(32, 10)
        y_val = torch.randint(0, 3, (32,))

        trainer.train(model, X_train, y_train, X_val, y_val)

        # Then metrics should include val_loss and val_accuracy
        epoch_callbacks = [m for m in captured_metrics if m.get("progress_type") == "epoch"]
        metrics = epoch_callbacks[0]

        assert metrics["val_loss"] is not None
        assert metrics["val_accuracy"] is not None
        assert isinstance(metrics["val_loss"], float)
        assert isinstance(metrics["val_accuracy"], float)

    def test_full_metrics_without_validation_data(self):
        """Test that metrics handle missing validation data."""
        # Given a model trainer without validation data
        captured_metrics = []

        def progress_callback(epoch, total_epochs, metrics):
            captured_metrics.append(metrics)

        config = {
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        # When training without validation data
        model = SimpleModel(input_dim=10, output_dim=3)
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Then metrics should have None for val metrics
        epoch_callbacks = [m for m in captured_metrics if m.get("progress_type") == "epoch"]
        metrics = epoch_callbacks[0]

        assert metrics["val_loss"] is None
        assert metrics["val_accuracy"] is None

    def test_full_metrics_learning_rate_matches_optimizer(self):
        """Test that metrics learning_rate matches optimizer."""
        # Given a model trainer with specific learning rate
        captured_metrics = []

        def progress_callback(epoch, total_epochs, metrics):
            captured_metrics.append(metrics)

        learning_rate = 0.005
        config = {
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": learning_rate,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        # When training
        model = SimpleModel(input_dim=10, output_dim=3)
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Then metrics learning_rate should match config
        epoch_callbacks = [m for m in captured_metrics if m.get("progress_type") == "epoch"]
        metrics = epoch_callbacks[0]

        assert metrics["learning_rate"] == learning_rate
