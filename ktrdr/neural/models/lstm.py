"""LSTM implementation for temporal trading strategies."""

import pandas as pd
import torch
import torch.nn as nn

from .base_model import BaseNeuralModel


class LSTMNetwork(nn.Module):
    """LSTM network that processes sequences of fuzzy features.

    Input: (batch, sequence_length, features)
    Output: (batch, num_classes)

    Takes the last hidden state from the LSTM and projects it
    to the output dimension via a linear layer.
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
        self.lstm = nn.LSTM(
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
        # lstm_out: (batch, seq_len, hidden_size)
        # h_n: (num_layers, batch, hidden_size) — last hidden state per layer
        _, (h_n, _) = self.lstm(x)
        # Take the last layer's hidden state
        out = self.dropout(h_n[-1])
        out = self.fc(out)
        return out


class LSTMTradingModel(BaseNeuralModel):
    """LSTM-based trading model for sequence input.

    Reads sequence_length from config to define the temporal lookback.
    Feature preparation delegates to FuzzyNeuralProcessor (same as MLP) —
    sequence windowing happens at the DataLoader level via SequenceDataset.
    """

    @property
    def sequence_length(self) -> int:
        """Get sequence length from config."""
        return self.config["architecture"]["sequence_length"]

    def build_model(self, input_size: int) -> nn.Module:
        """Build LSTM network from config.

        Args:
            input_size: Number of input features per timestep

        Returns:
            LSTMNetwork module

        Raises:
            ValueError: If sequence_length is not specified in architecture config
        """
        self.input_size = input_size
        arch = self.config["architecture"]

        if "sequence_length" not in arch:
            raise ValueError(
                "sequence_length must be specified in architecture config for LSTM models"
            )

        hidden_size = arch.get("hidden_size", 64)
        num_layers = arch.get("num_layers", 2)
        dropout = arch.get("dropout", 0.2)

        output_format = self.config.get("output_format", "classification")
        if output_format == "regression":
            num_classes = 1
        else:
            num_classes = self.config.get("num_classes", 3)

        return LSTMNetwork(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            num_classes=num_classes,
            dropout=dropout,
        )

    def prepare_features(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame, saved_scaler=None
    ) -> torch.Tensor:
        """Prepare features — same as MLP (2D tensor).

        Sequence windowing is handled by SequenceDataset at DataLoader level,
        not here. This returns the standard 2D (timestamps, features) tensor.
        """
        feature_config = self.config.get("features", {})
        disable_temporal = len(fuzzy_data) == 1

        from ...training.fuzzy_neural_processor import FuzzyNeuralProcessor

        processor = FuzzyNeuralProcessor(
            feature_config, disable_temporal=disable_temporal
        )
        features_tensor, _ = processor.prepare_input(fuzzy_data)

        device = self._get_device()
        return features_tensor.to(device)
