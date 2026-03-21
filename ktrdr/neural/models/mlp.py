"""Multi-Layer Perceptron implementation for trading decisions."""

import pandas as pd
import torch
import torch.nn as nn

from .base_model import BaseNeuralModel


class MLPTradingModel(BaseNeuralModel):
    """Multi-Layer Perceptron for neuro-fuzzy trading strategies.

    This class defines the MLP topology and feature preparation.
    Training is handled by ModelTrainer, which is topology-agnostic.
    """

    def build_model(self, input_size: int) -> nn.Module:
        """Build MLP with configurable architecture.

        Args:
            input_size: Number of input features

        Returns:
            Sequential neural network model
        """
        self.input_size = input_size
        layers = []

        # Get architecture config
        hidden_layers = self.config["architecture"]["hidden_layers"]
        dropout = self.config["architecture"].get("dropout", 0.2)
        activation = self.config["architecture"].get("activation", "relu")

        # Map activation functions
        activation_fn = {
            "relu": nn.ReLU,
            "tanh": nn.Tanh,
            "sigmoid": nn.Sigmoid,
            "leaky_relu": nn.LeakyReLU,
        }.get(activation.lower(), nn.ReLU)

        # Build layers
        prev_size = input_size
        for hidden_size in hidden_layers:
            layers.extend(
                [
                    nn.Linear(prev_size, hidden_size),
                    activation_fn(),
                    nn.Dropout(dropout),
                ]
            )
            prev_size = hidden_size

        # Output layer: 1 neuron for regression, configurable for classification
        output_format = self.config.get("output_format", "classification")
        if output_format == "regression":
            layers.append(nn.Linear(prev_size, 1))
        elif output_format == "classification":
            num_classes = self.config.get("num_classes", 3)
            layers.append(nn.Linear(prev_size, num_classes))
        else:
            raise ValueError(
                f"Unsupported output_format '{output_format}'. Must be 'classification' or 'regression'."
            )

        return nn.Sequential(*layers)

    def prepare_features(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame, saved_scaler=None
    ) -> torch.Tensor:
        """Create feature vector from pure fuzzy memberships.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values (not used in pure fuzzy mode)
            saved_scaler: Not used - pure fuzzy values don't need scaling

        Returns:
            Tensor of prepared fuzzy features
        """
        # Pure neuro-fuzzy architecture: only fuzzy memberships as inputs
        feature_config = self.config.get("features", {})

        # CRITICAL FIX: Disable temporal features in backtesting mode
        # When fuzzy_data has only 1 row, we're in backtesting and FeatureCache provides lag features
        disable_temporal = len(fuzzy_data) == 1
        if disable_temporal:
            from ... import get_logger

            logger = get_logger(__name__)
            logger.debug(
                "Single-row fuzzy data detected - disabling temporal feature generation (FeatureCache provides lag features)"
            )

        # Use FuzzyNeuralProcessor for pure neuro-fuzzy models
        from ...training.fuzzy_neural_processor import FuzzyNeuralProcessor

        processor = FuzzyNeuralProcessor(
            feature_config, disable_temporal=disable_temporal
        )
        features_tensor, _ = processor.prepare_input(fuzzy_data)

        device = self._get_device()
        return features_tensor.to(device)
