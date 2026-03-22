"""GRU implementation for temporal trading strategies."""

import pandas as pd
import torch
import torch.nn as nn

from .base_model import BaseNeuralModel


class GRUNetwork(nn.Module):
    """GRU network that processes sequences of fuzzy features.

    Input: (batch, sequence_length, features)
    Output: (batch, num_classes)

    Same pattern as LSTMNetwork but uses GRU (no cell state, fewer parameters).
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        num_classes: int,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, sequence_length, features)

        Returns:
            Output tensor of shape (batch, num_classes)
        """
        # h_n: (num_layers, batch, hidden_size)
        _, h_n = self.gru(x)
        out = self.dropout(h_n[-1])
        out = self.fc(out)
        return out


class GRUTradingModel(BaseNeuralModel):
    """GRU-based trading model for sequence input.

    Identical interface to LSTMTradingModel but uses GRU cells.
    """

    @property
    def sequence_length(self) -> int:
        """Get sequence length from config."""
        return self.config["architecture"]["sequence_length"]

    def build_model(self, input_size: int) -> nn.Module:
        """Build GRU network from config.

        Args:
            input_size: Number of input features per timestep

        Returns:
            GRUNetwork module

        Raises:
            ValueError: If sequence_length is not specified in architecture config
        """
        self.input_size = input_size
        arch = self.config["architecture"]

        if "sequence_length" not in arch:
            raise ValueError(
                "sequence_length must be specified in architecture config for GRU models"
            )

        hidden_size = arch.get("hidden_size", 64)
        num_layers = arch.get("num_layers", 2)
        dropout = arch.get("dropout", 0.2)

        output_format = self.config.get("output_format", "classification")
        if output_format == "regression":
            num_classes = 1
        else:
            num_classes = self.config.get("num_classes", 3)

        return GRUNetwork(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            num_classes=num_classes,
            dropout=dropout,
        )

    def prepare_features(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame, saved_scaler=None
    ) -> torch.Tensor:
        """Prepare features — same as MLP (2D tensor)."""
        feature_config = self.config.get("features", {})
        disable_temporal = len(fuzzy_data) == 1

        from ...training.fuzzy_neural_processor import FuzzyNeuralProcessor

        processor = FuzzyNeuralProcessor(
            feature_config, disable_temporal=disable_temporal
        )
        features_tensor, _ = processor.prepare_input(fuzzy_data)

        device = self._get_device()
        return features_tensor.to(device)
