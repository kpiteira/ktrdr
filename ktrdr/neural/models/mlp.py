"""Multi-Layer Perceptron implementation for trading decisions."""

from typing import Any, Optional, Union

import pandas as pd
import torch
import torch.nn as nn

from .base_model import BaseNeuralModel


class MLPTradingModel(BaseNeuralModel):
    """Multi-Layer Perceptron for neuro-fuzzy trading strategies."""

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

        # Output layer (3 classes: BUY=0, HOLD=1, SELL=2)
        layers.append(nn.Linear(prev_size, 3))

        # CLASSIFICATION MODELS ALWAYS OUTPUT RAW LOGITS
        # - CrossEntropyLoss expects raw logits and applies softmax internally
        # - This prevents dangerous double-softmax bugs
        # - Config "output_activation" is IGNORED for classification tasks
        # - Inference code handles logit-to-probability conversion

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

    def train(
        self, X: torch.Tensor, y: torch.Tensor, validation_data: Optional[tuple] = None
    ) -> dict[str, Any]:
        """Train the MLP model.

        Args:
            X: Training features
            y: Training labels (0=BUY, 1=HOLD, 2=SELL)
            validation_data: Optional (X_val, y_val) tuple

        Returns:
            Training history dictionary
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")

        # Get training parameters
        training_config = self.config.get("training", {})
        learning_rate = training_config.get("learning_rate", 0.001)
        training_config.get("batch_size", 32)
        epochs = training_config.get("epochs", 100)

        # Setup optimizer and loss
        optimizer_name = training_config.get("optimizer", "adam").lower()
        optimizer: Union[torch.optim.Adam, torch.optim.SGD]
        if optimizer_name == "adam":
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        elif optimizer_name == "sgd":
            optimizer = torch.optim.SGD(
                self.model.parameters(), lr=learning_rate, momentum=0.9
            )
        else:
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)

        criterion = nn.CrossEntropyLoss()

        # Training history
        history: dict[str, list[float]] = {
            "train_loss": [],
            "train_accuracy": [],
            "val_loss": [],
            "val_accuracy": [],
        }

        # Convert labels to LongTensor for CrossEntropyLoss
        y = y.long()

        # Simple training loop (placeholder - would be more sophisticated in production)
        self.model.train()
        for _epoch in range(epochs):
            # Forward pass
            outputs = self.model(X)
            loss = criterion(outputs, y)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Calculate accuracy
            _, predicted = torch.max(outputs.data, 1)
            accuracy = (predicted == y).float().mean()

            history["train_loss"].append(float(loss))
            history["train_accuracy"].append(float(accuracy))

            # Validation
            if validation_data is not None:
                X_val, y_val = validation_data
                y_val = y_val.long()

                self.model.eval()
                with torch.no_grad():
                    val_outputs = self.model(X_val)
                    val_loss = criterion(val_outputs, y_val)
                    _, val_predicted = torch.max(val_outputs.data, 1)
                    val_accuracy = (val_predicted == y_val).float().mean()

                history["val_loss"].append(float(val_loss))
                history["val_accuracy"].append(float(val_accuracy))

                self.model.train()

        self.is_trained = True
        return history
