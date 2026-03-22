"""Tests for DecisionFunction sequence-aware inference."""

import numpy as np
import pandas as pd
import torch.nn as nn

from ktrdr.backtesting.decision_function import DecisionFunction
from ktrdr.backtesting.position_manager import PositionStatus


class SimpleLSTM(nn.Module):
    """Minimal LSTM for testing."""

    def __init__(self, input_size=4, hidden_size=8, num_classes=3):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.fc(h_n[-1])


class TestDecisionFunctionSequence:
    """Test that DecisionFunction handles both dict and DataFrame inputs."""

    def _make_df(self, model, feature_names):
        """Create DecisionFunction with given model."""
        return DecisionFunction(
            model=model,
            feature_names=feature_names,
            decisions_config={"confidence_threshold": 0.5},
            output_type="classification",
        )

    def test_mlp_path_unchanged(self):
        """MLP path: dict input produces valid decision."""
        model = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 3))
        model.eval()
        features = ["f0", "f1", "f2", "f3"]
        df = self._make_df(model, features)

        bar = pd.Series({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05})
        bar.name = pd.Timestamp("2024-01-01")

        result = df(
            features={"f0": 0.5, "f1": 0.3, "f2": 0.7, "f3": 0.1},
            position=PositionStatus.FLAT,
            bar=bar,
        )
        assert result.signal is not None
        assert 0 <= result.confidence <= 1

    def test_sequence_path_with_dataframe(self):
        """LSTM path: DataFrame input produces valid decision."""
        model = SimpleLSTM(input_size=4, num_classes=3)
        model.eval()
        features = ["f0", "f1", "f2", "f3"]
        df = self._make_df(model, features)

        bar = pd.Series({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05})
        bar.name = pd.Timestamp("2024-01-01")

        # Pass DataFrame (sequence window) instead of dict
        window = pd.DataFrame(
            np.random.rand(10, 4),
            columns=features,
        )

        result = df(
            features=window,
            position=PositionStatus.FLAT,
            bar=bar,
        )
        assert result.signal is not None
        assert 0 <= result.confidence <= 1

    def test_sequence_preserves_feature_order(self):
        """DataFrame columns are reordered to match feature_names if needed."""
        model = SimpleLSTM(input_size=4, num_classes=3)
        model.eval()
        features = ["f0", "f1", "f2", "f3"]
        df = self._make_df(model, features)

        bar = pd.Series({"open": 1.0})
        bar.name = pd.Timestamp("2024-01-01")

        # Columns in different order
        window = pd.DataFrame(
            np.random.rand(5, 4),
            columns=["f3", "f1", "f0", "f2"],
        )

        # Should not error — reorders to match feature_names
        result = df(
            features=window,
            position=PositionStatus.FLAT,
            bar=bar,
        )
        assert result.signal is not None
