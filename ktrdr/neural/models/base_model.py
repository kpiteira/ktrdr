"""Base neural network model interface for trading strategies."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class BaseNeuralModel(ABC):
    """Abstract base class for neural network models in trading strategies."""

    def __init__(self, config: dict[str, Any]):
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
        validation_data: Optional[tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> dict[str, Any]:
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

    def predict(
        self, features: torch.Tensor, market_timestamp: Optional[pd.Timestamp] = None
    ) -> dict[str, Any]:
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

        # Ensure model and features are on the same device
        device = self._get_device()
        self.model = self.model.to(device)
        features = features.to(device)

        # DEBUG: Log device and model state (only log once to avoid spam)
        if not hasattr(self, "_device_state_logged"):
            from ... import get_logger

            debug_logger = get_logger(__name__)
            debug_logger.debug(
                f"🔬 Model device: {device}, Features device: {features.device}, Model training: {self.model.training}"
            )
            self._device_state_logged = True

        self.model.eval()
        with torch.no_grad():
            # DEBUG: Log input features for model collapse analysis
            from ... import get_logger

            debug_logger = get_logger(__name__)
            ts_str = (
                market_timestamp.strftime("%Y-%m-%d %H:%M")
                if market_timestamp
                else "Unknown"
            )

            # Check for degenerate inputs
            feature_stats = {
                "mean": float(features.mean()),
                "std": float(features.std()),
                "min": float(features.min()),
                "max": float(features.max()),
                "shape": features.shape,
            }
            debug_logger.debug(f"🔬 [{ts_str}] Input features - {feature_stats}")

            # CRITICAL: Log first few feature values to detect identical inputs
            if features.shape[1] >= 3:  # If we have at least 3 features
                first_features = features[0, : min(5, features.shape[1])].cpu().numpy()
                # debug_logger.info(f"🔍 [{ts_str}] First 5 features: {first_features}")  # Commented for performance

            # CRITICAL: Track feature diversity
            feature_variance = float(features.var())
            if feature_variance < 1e-8:
                debug_logger.error(
                    f"🚨 [{ts_str}] DEGENERATE INPUTS: Feature variance {feature_variance:.2e} - all features nearly identical!"
                )

            # Sample a few individual feature values to track patterns
            if features.shape[1] > 10:
                sample_features = (
                    features[0, [0, features.shape[1] // 4, features.shape[1] // 2, -1]]
                    .cpu()
                    .numpy()
                )
                debug_logger.debug(
                    f"🔍 [{ts_str}] Sample features [0, 25%, 50%, 100%]: {sample_features}"
                )

            # Check for NaN or infinite values
            if torch.isnan(features).any():
                debug_logger.error(
                    f"🚨 [{ts_str}] NaN values detected in input features!"
                )
            if torch.isinf(features).any():
                debug_logger.error(
                    f"🚨 [{ts_str}] Infinite values detected in input features!"
                )

            outputs = self.model(features)

            # Raw outputs will be logged later in the processing section

        # Convert outputs to probabilities and decision
        if len(outputs.shape) == 1:
            outputs = outputs.unsqueeze(0)

        # Move back to CPU for numpy conversion
        raw_outputs = outputs[0].cpu().numpy()

        # CRITICAL DEBUG: Check if softmax was already applied
        raw_sum = np.sum(raw_outputs)
        is_already_softmax = abs(raw_sum - 1.0) < 1e-6

        # CRITICAL: Log raw model outputs before any processing
        from ... import get_logger

        debug_logger = get_logger(__name__)
        ts_str = (
            market_timestamp.strftime("%Y-%m-%d %H:%M")
            if market_timestamp
            else "Unknown"
        )
        # debug_logger.info(f"🔬 [{ts_str}] Raw model outputs: {raw_outputs}")  # Commented for performance
        debug_logger.debug(
            f"🔬 [{ts_str}] Raw sum: {raw_sum:.6f}, Is already softmax: {is_already_softmax}"
        )

        if is_already_softmax:
            # Outputs are already probabilities from softmax layer
            probs = raw_outputs
            debug_logger.debug(f"🔬 [{ts_str}] Using raw outputs as probabilities")
        else:
            # Apply softmax manually if not already applied
            exp_outputs = np.exp(
                raw_outputs - np.max(raw_outputs)
            )  # Numerical stability
            probs = exp_outputs / np.sum(exp_outputs)
            debug_logger.debug(f"🔬 [{ts_str}] Applied manual softmax: {probs}")

        signal_idx = np.argmax(probs)
        confidence = float(probs[signal_idx])

        # Check if outputs are stuck/identical
        if abs(probs[0] - 1.0) < 1e-6:  # BUY probability = 1.0
            debug_logger.warning(
                f"🚨 [{ts_str}] MODEL STUCK: Always predicting BUY with prob {probs[0]:.6f}"
            )

        debug_logger.debug(
            f"🔬 [{ts_str}] Final probs: BUY={probs[0]:.6f}, HOLD={probs[1]:.6f}, SELL={probs[2]:.6f}"
        )

        signal_map = {0: "BUY", 1: "HOLD", 2: "SELL"}

        # DEBUG: Log prediction details to identify model collapse
        from ... import get_logger

        logger = get_logger(__name__)

        # CRITICAL DEBUG: Check for model collapse patterns
        prob_range = probs.max() - probs.min()
        entropy = -np.sum(
            probs * np.log(probs + 1e-8)
        )  # Add small epsilon to avoid log(0)

        # Format timestamp for logging
        ts_str = (
            market_timestamp.strftime("%Y-%m-%d %H:%M")
            if market_timestamp
            else "Unknown"
        )

        # logger.info(
        #     f"🧠 [{ts_str}] Neural prediction - Raw probs: BUY={probs[0]:.6f}, HOLD={probs[1]:.6f}, SELL={probs[2]:.6f}"
        # )  # Commented for performance
        # logger.info(
        #     f"🧠 [{ts_str}] Neural prediction - Signal: {signal_map[signal_idx]}, Confidence: {confidence:.6f}"
        # )  # Commented for performance
        logger.debug(
            f"🧠 [{ts_str}] Neural analysis - Prob range: {prob_range:.6f}, Entropy: {entropy:.6f}"
        )

        # Flag potential model collapse scenarios (moved to DEBUG to reduce noise)
        if confidence > 0.99:
            logger.debug(
                f"🚨 [{ts_str}] SUSPICIOUS: Extremely high confidence {confidence:.6f} - possible model collapse"
            )
        if prob_range < 0.01:
            logger.debug(
                f"🚨 [{ts_str}] SUSPICIOUS: Low probability range {prob_range:.6f} - model may be stuck"
            )
        if entropy < 0.1:
            logger.debug(
                f"🚨 [{ts_str}] SUSPICIOUS: Low entropy {entropy:.6f} - model output too deterministic"
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

    def _get_device(self) -> torch.device:
        """Get the appropriate device for computation.

        Returns:
            PyTorch device (CUDA, MPS, or CPU)
        """
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")

        # DEBUG: Only log device selection once per model
        if not hasattr(self, "_device_logged"):
            from ... import get_logger

            logger = get_logger(__name__)
            logger.info(f"🚀 Neural model using device: {device}")
            self._device_logged = True

        return device
