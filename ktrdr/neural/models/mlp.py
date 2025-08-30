"""Multi-Layer Perceptron implementation for trading decisions."""

from typing import Any, Optional

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
        history = {
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


class MultiSymbolMLPTradingModel(BaseNeuralModel):
    """Multi-Layer Perceptron with symbol embeddings for multi-symbol trading strategies."""

    def build_model(self, input_size: int) -> nn.Module:
        """Build MLP with symbol embeddings.

        Args:
            input_size: Number of input features (before symbol embeddings)

        Returns:
            Multi-symbol neural network model with embeddings
        """
        self.input_size = input_size

        # Get symbol embedding config
        num_symbols = self.config["num_symbols"]
        symbol_embedding_dim = self.config.get("symbol_embedding_dim", 16)

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

        return MultiSymbolMLP(
            input_size=input_size,
            num_symbols=num_symbols,
            symbol_embedding_dim=symbol_embedding_dim,
            hidden_layers=hidden_layers,
            dropout=dropout,
            activation_fn=activation_fn,
            num_classes=3,
        )

    def prepare_features(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame, saved_scaler=None
    ) -> torch.Tensor:
        """Create feature vector from pure fuzzy memberships (same as single-symbol).

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values (not used in pure fuzzy mode)
            saved_scaler: Not used - pure fuzzy values don't need scaling

        Returns:
            Tensor of prepared fuzzy features
        """
        # Same feature preparation as single-symbol model
        feature_config = self.config.get("features", {})

        # CRITICAL FIX: Disable temporal features in backtesting mode
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


class MultiSymbolMLP(nn.Module):
    """Neural network with symbol embeddings for multi-symbol trading."""

    def __init__(
        self,
        input_size: int,
        num_symbols: int,
        symbol_embedding_dim: int,
        hidden_layers: list[int],
        dropout: float,
        activation_fn: type,
        num_classes: int = 3,
    ):
        """Initialize multi-symbol MLP.

        Args:
            input_size: Number of input features
            num_symbols: Number of symbols for embedding
            symbol_embedding_dim: Dimension of symbol embeddings
            hidden_layers: List of hidden layer sizes
            dropout: Dropout probability
            activation_fn: Activation function class
            num_classes: Number of output classes
        """
        super().__init__()

        self.input_size = input_size
        self.num_symbols = num_symbols
        self.symbol_embedding_dim = symbol_embedding_dim

        # Symbol embedding layer
        self.symbol_embedding = nn.Embedding(num_symbols, symbol_embedding_dim)

        # Combined input size: features + symbol embedding
        combined_input_size = input_size + symbol_embedding_dim

        # Build MLP layers
        layers = []
        prev_size = combined_input_size
        for hidden_size in hidden_layers:
            layers.extend(
                [
                    nn.Linear(prev_size, hidden_size),
                    activation_fn(),
                    nn.Dropout(dropout),
                ]
            )
            prev_size = hidden_size

        # Output layer
        layers.append(nn.Linear(prev_size, num_classes))

        self.mlp = nn.Sequential(*layers)

    def forward(
        self, x: torch.Tensor, symbol_indices: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Forward pass with symbol embeddings.

        Args:
            x: Input features [batch_size, input_size]
            symbol_indices: Symbol indices for embedding lookup [batch_size]
                          If None, uses symbol index 0 for all samples

        Returns:
            Output logits [batch_size, num_classes]
        """
        batch_size = x.size(0)

        # If no symbol indices provided, use symbol 0 for all samples
        if symbol_indices is None:
            symbol_indices = torch.zeros(batch_size, dtype=torch.long, device=x.device)

        # Get symbol embeddings
        symbol_embeds = self.symbol_embedding(
            symbol_indices
        )  # [batch_size, symbol_embedding_dim]

        # Concatenate features and symbol embeddings
        combined_input = torch.cat(
            [x, symbol_embeds], dim=1
        )  # [batch_size, input_size + symbol_embedding_dim]

        # Pass through MLP
        return self.mlp(combined_input)
