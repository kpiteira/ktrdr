"""Tests for Phase 2: Training System."""

import pytest
import torch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path

from ktrdr.training import (
    ZigZagLabeler,
    ModelTrainer,
    ModelStorage,
    StrategyTrainer,
)


class TestZigZagLabeler:
    """Test ZigZag label generation."""

    def test_zigzag_basic_labeling(self):
        """Test basic ZigZag labeling functionality."""
        # Create synthetic price data with clear patterns
        dates = pd.date_range("2024-01-01", periods=100, freq="1h")

        # Create a trending price pattern
        base_price = 100
        prices = []
        for i in range(100):
            if i < 20:
                # Uptrend
                prices.append(base_price + i * 0.5)
            elif i < 40:
                # Downtrend
                prices.append(base_price + 10 - (i - 20) * 0.3)
            else:
                # Sideways
                prices.append(base_price + 4 + np.sin(i * 0.1) * 2)

        price_data = pd.DataFrame(
            {
                "close": prices,
                "open": [p * 0.999 for p in prices],
                "high": [p * 1.002 for p in prices],
                "low": [p * 0.998 for p in prices],
                "volume": [1000] * 100,
            },
            index=dates,
        )

        labeler = ZigZagLabeler(threshold=0.05, lookahead=10)
        labels = labeler.generate_labels(price_data)

        assert len(labels) == len(price_data)
        assert all(label in [0, 1, 2] for label in labels)

        # Check that we have some buy/sell signals
        unique_labels = set(labels)
        assert len(unique_labels) > 1  # Should have some variation

    def test_label_distribution(self):
        """Test label distribution calculation."""
        labeler = ZigZagLabeler()
        labels = pd.Series([0, 0, 1, 1, 1, 2, 2])

        distribution = labeler.get_label_distribution(labels)

        assert distribution["buy_count"] == 2
        assert distribution["hold_count"] == 3
        assert distribution["sell_count"] == 2
        assert abs(distribution["buy_pct"] - 28.57) < 0.1

    def test_fitness_labels(self):
        """Test fitness label generation with returns."""
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")
        price_data = pd.DataFrame(
            {
                "close": random_walk(50, start=100, volatility=0.02),
                "open": random_walk(50, start=100, volatility=0.02),
                "high": random_walk(50, start=102, volatility=0.02),
                "low": random_walk(50, start=98, volatility=0.02),
                "volume": [1000] * 50,
            },
            index=dates,
        )

        labeler = ZigZagLabeler(threshold=0.03, lookahead=5)
        fitness_labels = labeler.generate_fitness_labels(price_data)

        assert "label" in fitness_labels.columns
        assert "expected_return" in fitness_labels.columns
        assert len(fitness_labels) == len(price_data)


class TestModelTrainer:
    """Test neural network training functionality."""

    def test_trainer_initialization(self):
        """Test trainer initialization with config."""
        config = {
            "learning_rate": 0.01,
            "batch_size": 16,
            "epochs": 10,
            "optimizer": "adam",
        }

        trainer = ModelTrainer(config)
        assert trainer.config == config
        assert trainer.history == []

    def test_simple_training(self):
        """Test basic training loop."""
        # Create simple model
        model = torch.nn.Sequential(
            torch.nn.Linear(5, 10),
            torch.nn.ReLU(),
            torch.nn.Linear(10, 3),
            torch.nn.Softmax(dim=1),
        )

        # Create sample data
        X_train = torch.randn(100, 5)
        y_train = torch.randint(0, 3, (100,))
        X_val = torch.randn(20, 5)
        y_val = torch.randint(0, 3, (20,))

        config = {
            "learning_rate": 0.01,
            "batch_size": 32,
            "epochs": 5,
            "optimizer": "adam",
        }

        trainer = ModelTrainer(config)
        results = trainer.train(model, X_train, y_train, X_val, y_val)

        assert "train_loss" in results["history"]
        assert "train_accuracy" in results["history"]
        assert len(trainer.history) == 5  # 5 epochs


class TestModelStorage:
    """Test model storage and versioning."""

    def setup_method(self):
        """Set up temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = ModelStorage(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_model_saving(self):
        """Test saving a model with metadata."""
        # Create simple model
        model = torch.nn.Sequential(torch.nn.Linear(5, 3), torch.nn.Softmax(dim=1))

        config = {"test": "config"}
        metrics = {"accuracy": 0.85}
        features = ["feature1", "feature2", "feature3"]

        model_path = self.storage.save_model(
            model=model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe="1h",
            config=config,
            training_metrics=metrics,
            feature_names=features,
        )

        assert Path(model_path).exists()
        assert (Path(model_path) / "model.pt").exists()
        assert (Path(model_path) / "config.json").exists()
        assert (Path(model_path) / "metadata.json").exists()

    def test_model_loading(self):
        """Test loading a saved model."""
        # First save a model
        model = torch.nn.Sequential(torch.nn.Linear(5, 3))

        self.storage.save_model(
            model=model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe="1h",
            config={"test": "config"},
            training_metrics={"accuracy": 0.85},
            feature_names=["f1", "f2", "f3"],
        )

        # Then load it
        loaded = self.storage.load_model("test_strategy", "AAPL", "1h")

        assert "model" in loaded
        assert "config" in loaded
        assert "metadata" in loaded
        assert loaded["config"]["test"] == "config"

    def test_model_versioning(self):
        """Test that models are versioned correctly."""
        model = torch.nn.Sequential(torch.nn.Linear(5, 3))

        # Save first version
        path1 = self.storage.save_model(
            model=model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe="1h",
            config={"version": 1},
            training_metrics={},
            feature_names=[],
        )

        # Save second version
        path2 = self.storage.save_model(
            model=model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe="1h",
            config={"version": 2},
            training_metrics={},
            feature_names=[],
        )

        assert "v1" in path1
        assert "v2" in path2
        assert path1 != path2


def create_sample_data():
    """Create sample data for testing."""
    dates = pd.date_range("2024-01-01", periods=100, freq="1h")

    price_data = pd.DataFrame(
        {
            "close": 100 + np.cumsum(np.random.randn(100) * 0.01),
            "open": 100 + np.cumsum(np.random.randn(100) * 0.01),
            "high": 102 + np.cumsum(np.random.randn(100) * 0.01),
            "low": 98 + np.cumsum(np.random.randn(100) * 0.01),
            "volume": np.random.uniform(800, 1200, 100),
        },
        index=dates,
    )

    return price_data


def random_walk(n, start=0, volatility=1):
    """Generate random walk data."""
    steps = np.random.randn(n) * volatility
    return start + np.cumsum(steps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
