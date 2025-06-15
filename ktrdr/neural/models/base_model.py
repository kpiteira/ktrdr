"""Base neural network model interface for trading strategies."""

from abc import ABC, abstractmethod
import torch
import torch.nn as nn
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from pathlib import Path
import json


class BaseNeuralModel(ABC):
    """Abstract base class for neural network models in trading strategies."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the model with configuration.

        Args:
            config: Model configuration dictionary containing architecture and training parameters
        """
        self.config = config
        self.model: Optional[nn.Module] = None
        self.is_trained = False
        self.feature_scaler = None
        self.input_size: Optional[int] = None

    @abstractmethod
    def build_model(self, input_size: int) -> nn.Module:
        """Build the neural network architecture.

        Args:
            input_size: Number of input features

        Returns:
            PyTorch neural network module
        """
        pass

    @abstractmethod
    def prepare_features(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame, saved_scaler=None
    ) -> torch.Tensor:
        """Convert fuzzy/indicator data to model features.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values
            saved_scaler: Pre-trained scaler for consistent feature scaling

        Returns:
            Tensor of prepared features
        """
        pass

    def train(
        self,
        X: torch.Tensor,
        y: torch.Tensor,
        validation_data: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Dict[str, Any]:
        """Train the model with fuzzy features and labels.

        Args:
            X: Training features tensor
            y: Training labels tensor
            validation_data: Optional tuple of (X_val, y_val) for validation

        Returns:
            Dictionary containing training history and metrics
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")

        # Training implementation would go here
        # For now, return placeholder
        self.is_trained = True
        return {"status": "training_not_implemented"}

    def predict(self, features: torch.Tensor) -> Dict[str, Any]:
        """Generate trading decision with confidence scores.

        Args:
            features: Input features tensor

        Returns:
            Dictionary with signal, confidence, and probability breakdown
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        if self.model is None:
            raise ValueError("Model not built.")

        self.model.eval()
        with torch.no_grad():
            outputs = self.model(features)

        # Convert outputs to probabilities and decision
        if len(outputs.shape) == 1:
            outputs = outputs.unsqueeze(0)

        probs = outputs[0].numpy()  # Assumes softmax output
        signal_idx = np.argmax(probs)
        confidence = float(probs[signal_idx])

        signal_map = {0: "BUY", 1: "HOLD", 2: "SELL"}

        # DEBUG: Log prediction details to identify model collapse
        from ..logging import get_logger

        logger = get_logger(__name__)
        logger.debug(
            f"Neural prediction - Raw probs: BUY={probs[0]:.6f}, HOLD={probs[1]:.6f}, SELL={probs[2]:.6f}"
        )
        logger.debug(
            f"Neural prediction - Signal: {signal_map[signal_idx]}, Confidence: {confidence:.6f}"
        )

        return {
            "signal": signal_map[signal_idx],
            "confidence": confidence,
            "probabilities": {
                "BUY": float(probs[0]),
                "HOLD": float(probs[1]),
                "SELL": float(probs[2]),
            },
        }

    def save_model(self, path: str):
        """Serialize model for persistence.

        Args:
            path: Directory path to save model files
        """
        if self.model is None:
            raise ValueError("No model to save")

        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save model weights
        torch.save(self.model.state_dict(), save_dir / "model.pt")

        # Save configuration
        with open(save_dir / "config.json", "w") as f:
            json.dump(self.config, f, indent=2)

        # Save metadata
        metadata = {
            "is_trained": self.is_trained,
            "input_size": self.input_size,
            "model_type": self.__class__.__name__,
        }
        with open(save_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def load_model(self, path: str):
        """Load pre-trained model.

        Args:
            path: Directory path containing saved model files
        """
        load_dir = Path(path)

        # Load configuration
        with open(load_dir / "config.json", "r") as f:
            self.config = json.load(f)

        # Load metadata
        with open(load_dir / "metadata.json", "r") as f:
            metadata = json.load(f)

        self.is_trained = metadata["is_trained"]
        self.input_size = metadata["input_size"]

        # Build and load model
        if self.input_size:
            self.model = self.build_model(self.input_size)
            self.model.load_state_dict(torch.load(load_dir / "model.pt"))
            self.model.eval()
