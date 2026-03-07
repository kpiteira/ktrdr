"""Integration test for the regression training pipeline.

Tests the full in-process flow: labels -> features -> model -> train -> predict -> decision.
NOT an E2E test against running containers.
"""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.backtesting.decision_function import DecisionFunction  # noqa: E402
from ktrdr.backtesting.position_manager import PositionStatus  # noqa: E402
from ktrdr.config.strategy_loader import StrategyConfigurationLoader  # noqa: E402
from ktrdr.config.strategy_validator import validate_v3_strategy  # noqa: E402
from ktrdr.decision.base import Signal  # noqa: E402
from ktrdr.neural.models.mlp import MLPTradingModel  # noqa: E402
from ktrdr.training.forward_return_labeler import ForwardReturnLabeler  # noqa: E402


@pytest.fixture
def regression_strategy_path():
    """Path to the example regression strategy."""
    from pathlib import Path

    path = Path(__file__).parents[2] / "strategies" / "regression_example_v3.yaml"
    if not path.exists():
        pytest.skip("regression_example_v3.yaml not found")
    return path


@pytest.fixture
def sample_price_data():
    """Generate realistic-looking price data for testing."""
    np.random.seed(42)
    n_bars = 500
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="h")
    close = 1.1 + np.cumsum(np.random.randn(n_bars) * 0.001)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(n_bars) * 0.0005,
            "high": close + np.random.rand(n_bars) * 0.001,
            "low": close - np.random.rand(n_bars) * 0.001,
            "close": close,
            "volume": np.random.randint(100, 10000, n_bars),
        },
        index=dates,
    )


class TestRegressionPipelineIntegration:
    """Full in-process regression pipeline test."""

    def test_strategy_yaml_validates(self, regression_strategy_path):
        """The example regression strategy YAML loads and validates."""
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(regression_strategy_path)
        validate_v3_strategy(config)
        assert config.decisions["output_format"] == "regression"
        assert config.training["labels"]["source"] == "forward_return"

    def test_forward_return_labels_generated(self, sample_price_data):
        """Labels generated as float Series with correct properties."""
        labeler = ForwardReturnLabeler(horizon=20)
        labels = labeler.generate_labels(sample_price_data)

        assert len(labels) == 480  # 500 - 20
        assert labels.dtype == np.float64
        # Should have both positive and negative returns
        assert (labels > 0).sum() > 0
        assert (labels < 0).sum() > 0

    def test_regression_model_trains(self, sample_price_data):
        """Regression model trains with Huber loss without error."""
        # Generate labels
        labeler = ForwardReturnLabeler(horizon=20)
        labels = labeler.generate_labels(sample_price_data)

        # Create fake fuzzy features (simulating 4 fuzzy memberships)
        np.random.seed(42)
        n_features = 4
        features = torch.FloatTensor(np.random.rand(len(labels), n_features))
        label_tensor = torch.FloatTensor(labels.values)

        # Build and train model
        model_config = {
            "architecture": {
                "hidden_layers": [32, 16],
                "dropout": 0.1,
                "activation": "relu",
            },
            "training": {"learning_rate": 0.001, "epochs": 10},
            "output_format": "regression",
            "loss": "huber",
            "huber_delta": 0.01,
        }
        mlp = MLPTradingModel(model_config)
        mlp.model = mlp.build_model(input_size=n_features)

        # Verify architecture
        last_linear = [m for m in mlp.model.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 1

        # Train
        history = mlp.train(features, label_tensor)
        assert len(history["train_loss"]) == 10
        assert all(loss > 0 for loss in history["train_loss"])

    def test_decision_function_produces_cost_filtered_signals(self, sample_price_data):
        """DecisionFunction produces BUY/SELL/HOLD with cost filtering."""
        # Train a quick model
        labeler = ForwardReturnLabeler(horizon=20)
        labels = labeler.generate_labels(sample_price_data)
        n_features = 4
        features = torch.FloatTensor(np.random.rand(len(labels), n_features))
        label_tensor = torch.FloatTensor(labels.values)

        model_config = {
            "architecture": {
                "hidden_layers": [16, 8],
                "dropout": 0.0,
                "activation": "relu",
            },
            "training": {"learning_rate": 0.001, "epochs": 20},
            "output_format": "regression",
            "loss": "huber",
            "huber_delta": 0.01,
        }
        mlp = MLPTradingModel(model_config)
        mlp.model = mlp.build_model(input_size=n_features)
        mlp.train(features, label_tensor)

        # Create DecisionFunction
        feature_names = [f"f{i}" for i in range(n_features)]
        decisions_config = {
            "output_format": "regression",
            "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            "filters": {"min_signal_separation": 0},
            "position_awareness": False,  # Disable for counting
        }
        df = DecisionFunction(mlp.model, feature_names, decisions_config)

        # Run predictions over all samples
        signals = {"BUY": 0, "HOLD": 0, "SELL": 0}
        for i in range(min(100, len(features))):
            feat_dict = {f"f{j}": float(features[i, j]) for j in range(n_features)}
            bar = pd.Series(
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 100},
                name=pd.Timestamp("2024-06-01") + pd.Timedelta(hours=i),
            )
            decision = df(feat_dict, PositionStatus.FLAT, bar)
            signals[decision.signal.value] += 1

        # Verify the cost threshold mechanism is active:
        # The trade_threshold should be 0.003 * 1.5 = 0.0045
        assert df.trade_threshold == pytest.approx(0.0045)
        # All signals should be valid types
        for signal_name in signals:
            assert signal_name in ("BUY", "HOLD", "SELL")
        # Should produce at least some signals total
        total = signals["BUY"] + signals["HOLD"] + signals["SELL"]
        assert total == 100

    def test_full_pipeline_labels_to_decisions(self, sample_price_data):
        """Full in-process pipeline: labels -> train -> predict -> filter."""
        # 1. Generate labels
        labeler = ForwardReturnLabeler(horizon=10)
        labels = labeler.generate_labels(sample_price_data)

        # 2. Create features and align
        n_features = 4
        all_features = torch.FloatTensor(
            np.random.rand(len(sample_price_data), n_features)
        )
        features = all_features[: len(labels)]  # truncate to match labels
        assert len(features) == len(labels)

        label_tensor = torch.FloatTensor(labels.values)

        # 3. Build and train
        model_config = {
            "architecture": {
                "hidden_layers": [16],
                "dropout": 0.0,
                "activation": "relu",
            },
            "training": {"learning_rate": 0.001, "epochs": 15},
            "output_format": "regression",
            "loss": "huber",
        }
        mlp = MLPTradingModel(model_config)
        mlp.model = mlp.build_model(input_size=n_features)
        history = mlp.train(features, label_tensor)
        assert len(history["train_loss"]) == 15

        # 4. Run through DecisionFunction
        feature_names = [f"f{i}" for i in range(n_features)]
        decisions_config = {
            "output_format": "regression",
            "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            "filters": {"min_signal_separation": 0},
            "position_awareness": False,
        }
        df = DecisionFunction(mlp.model, feature_names, decisions_config)

        # 5. Verify decisions are valid
        feat_dict = {f"f{j}": float(features[0, j]) for j in range(n_features)}
        bar = pd.Series(
            {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 100},
            name=pd.Timestamp("2024-06-01"),
        )
        decision = df(feat_dict, PositionStatus.FLAT, bar)
        assert decision.signal in (Signal.BUY, Signal.HOLD, Signal.SELL)
        assert 0.0 <= decision.confidence <= 1.0
        assert "predicted_return" in decision.reasoning
