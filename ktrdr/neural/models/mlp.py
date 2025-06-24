"""Multi-Layer Perceptron implementation for trading decisions."""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

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
        """Create feature vector from fuzzy memberships and context.

        IMPORTANT: This must create the same features as training FeatureEngineer!

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values
            saved_scaler: Pre-trained scaler from model training (for consistent scaling)

        Returns:
            Tensor of prepared features
        """
        # Use the same feature processing logic as training to avoid dimension mismatch
        feature_config = self.config.get("features", {})
        
        # Check if this model uses pure fuzzy processing (Phase 3 of feature engineering removal)
        use_pure_fuzzy = (
            not feature_config.get("include_raw_indicators", False) and
            not feature_config.get("include_price_context", False) and 
            not feature_config.get("include_volume_context", False) and
            not feature_config.get("scale_features", True)
        )
        
        if use_pure_fuzzy:
            # Use FuzzyNeuralProcessor for pure neuro-fuzzy models
            from ...training.fuzzy_neural_processor import FuzzyNeuralProcessor
            processor = FuzzyNeuralProcessor(feature_config)
            features_tensor, _ = processor.prepare_input(fuzzy_data)
            # No need for scaler - fuzzy values are already 0-1
            device = self._get_device()
            return features_tensor.to(device)
        else:
            # Use legacy FeatureEngineer for backward compatibility
            from ...training.feature_engineering import FeatureEngineer
            
            # Ensure the same defaults as training
            feature_config.setdefault("include_price_context", True)
            feature_config.setdefault("include_volume_context", True)
            feature_config.setdefault("include_raw_indicators", False)
            feature_config.setdefault("lookback_periods", 1)
            feature_config.setdefault("scale_features", True)

            # Create FeatureEngineer with the same config
            engineer = FeatureEngineer(feature_config)

            # CRITICAL: Use the saved scaler from training to ensure consistent scaling
            if saved_scaler is not None:
                engineer.scaler = saved_scaler

            # Create a dummy price_data DataFrame from indicators if needed
            # For inference, we typically only have the current bar, so create minimal price data
            if "close" in indicators.columns:
                price_data = (
                    indicators[["open", "high", "low", "close", "volume"]].copy()
                    if "volume" in indicators.columns
                    else indicators[["open", "high", "low", "close"]].copy()
                )
            else:
                # Fallback: create minimal price data
                price_data = pd.DataFrame(
                    {
                        "open": indicators.get("open", 0),
                        "high": indicators.get("high", 0),
                        "low": indicators.get("low", 0),
                        "close": indicators.get("close", 0),
                        "volume": indicators.get("volume", 0),
                    },
                    index=indicators.index,
                )

            # Use the same feature preparation as training
            features_tensor, feature_names = engineer.prepare_features(
                fuzzy_data=fuzzy_data, indicators=indicators, price_data=price_data
            )

            # Ensure tensor is on the correct device for GPU acceleration
            device = self._get_device()
            features_tensor = features_tensor.to(device)

        return features_tensor

    def train(
        self, X: torch.Tensor, y: torch.Tensor, validation_data: Optional[tuple] = None
    ) -> Dict[str, Any]:
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
        batch_size = training_config.get("batch_size", 32)
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
        for epoch in range(epochs):
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
