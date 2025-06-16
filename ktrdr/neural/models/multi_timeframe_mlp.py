"""Multi-Timeframe MLP implementation for trading decisions."""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from sklearn.preprocessing import StandardScaler, MinMaxScaler

from .base_model import BaseNeuralModel
from ktrdr import get_logger

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class TimeframeFeatureConfig:
    """Configuration for features from a specific timeframe."""
    timeframe: str
    expected_features: List[str]
    weight: float = 1.0
    enabled: bool = True


@dataclass 
class MultiTimeframeTrainingResult:
    """Result of multi-timeframe neural network training."""
    training_history: Dict[str, List[float]]
    feature_importance: Optional[Dict[str, float]]
    timeframe_contributions: Dict[str, float]
    model_performance: Dict[str, float]
    convergence_metrics: Dict[str, Any]


class MultiTimeframeMLP(BaseNeuralModel):
    """Multi-Layer Perceptron for multi-timeframe neuro-fuzzy trading strategies."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize multi-timeframe MLP.
        
        Args:
            config: Model configuration containing:
                - timeframe_configs: Dict mapping timeframes to feature configs
                - architecture: Neural network architecture parameters
                - training: Training parameters
                - feature_processing: Feature processing parameters
        """
        super().__init__(config)
        self.timeframe_configs = self._build_timeframe_configs()
        self.feature_order = self._establish_feature_order()
        self.timeframe_encoders = None  # Will be built dynamically
        self.expected_input_size = None
        
        logger.info(f"Initialized MultiTimeframeMLP with {len(self.timeframe_configs)} timeframes")

    def _build_timeframe_configs(self) -> Dict[str, TimeframeFeatureConfig]:
        """Build timeframe feature configurations from config."""
        configs = {}
        timeframe_configs = self.config.get("timeframe_configs", {})
        
        for tf_name, tf_config in timeframe_configs.items():
            configs[tf_name] = TimeframeFeatureConfig(
                timeframe=tf_name,
                expected_features=tf_config.get("expected_features", []),
                weight=tf_config.get("weight", 1.0),
                enabled=tf_config.get("enabled", True)
            )
        
        return configs

    def _establish_feature_order(self) -> List[str]:
        """Establish consistent feature ordering for multi-timeframe inputs."""
        feature_order = []
        
        # Sort timeframes for consistency (1h, 4h, 1d order)
        timeframe_order = self._get_timeframe_order()
        
        for timeframe in timeframe_order:
            if timeframe in self.timeframe_configs:
                tf_config = self.timeframe_configs[timeframe]
                if tf_config.enabled:
                    # Add timeframe prefix to each feature
                    for feature in tf_config.expected_features:
                        feature_order.append(f"{feature}_{timeframe}")
        
        logger.debug(f"Established feature order: {feature_order}")
        return feature_order

    def _get_timeframe_order(self) -> List[str]:
        """Get consistent timeframe ordering (shortest to longest)."""
        timeframe_priority = {
            "1m": 1, "5m": 2, "15m": 3, "30m": 4,
            "1h": 5, "2h": 6, "4h": 7, "6h": 8, "8h": 9,
            "12h": 10, "1d": 11, "3d": 12, "1w": 13, "1M": 14
        }
        
        available_timeframes = list(self.timeframe_configs.keys())
        return sorted(available_timeframes, key=lambda tf: timeframe_priority.get(tf, 999))

    def build_model(self, input_size: int) -> nn.Module:
        """
        Build multi-timeframe MLP with configurable architecture.
        
        Args:
            input_size: Total number of input features across all timeframes
            
        Returns:
            Sequential neural network model
        """
        self.input_size = input_size
        self.expected_input_size = input_size
        
        # Get architecture config
        arch_config = self.config.get("architecture", {})
        hidden_layers = arch_config.get("hidden_layers", [45, 30, 15])
        dropout = arch_config.get("dropout", 0.3)
        activation = arch_config.get("activation", "relu")
        use_batch_norm = arch_config.get("batch_norm", True)
        
        # Map activation functions
        activation_fn = {
            "relu": nn.ReLU,
            "tanh": nn.Tanh,
            "sigmoid": nn.Sigmoid,
            "leaky_relu": nn.LeakyReLU,
            "elu": nn.ELU,
            "selu": nn.SELU
        }.get(activation.lower(), nn.ReLU)

        layers = []
        prev_size = input_size
        
        # Build hidden layers
        for i, hidden_size in enumerate(hidden_layers):
            # Linear layer
            layers.append(nn.Linear(prev_size, hidden_size))
            
            # Batch normalization (optional, only during training with batch_size > 1)
            if use_batch_norm:
                # Note: BatchNorm will be disabled during eval() mode for single samples
                layers.append(nn.BatchNorm1d(hidden_size))
            
            # Activation
            layers.append(activation_fn())
            
            # Dropout
            layers.append(nn.Dropout(dropout))
            
            prev_size = hidden_size

        # Output layer (3 classes: BUY=0, HOLD=1, SELL=2)
        layers.append(nn.Linear(prev_size, 3))
        
        # Output activation
        output_activation = arch_config.get("output_activation", "softmax")
        if output_activation.lower() == "softmax":
            layers.append(nn.Softmax(dim=1))

        model = nn.Sequential(*layers)
        
        # Assign to self.model
        self.model = model
        
        logger.info(f"Built MultiTimeframeMLP: {input_size} -> {hidden_layers} -> 3")
        logger.debug(f"Model architecture: {model}")
        
        return model

    def prepare_features(
        self,
        fuzzy_data: Dict[str, pd.DataFrame],
        indicators: Dict[str, pd.DataFrame],
        saved_scaler=None
    ) -> torch.Tensor:
        """
        Convert multi-timeframe fuzzy/indicator data to model features.
        
        Args:
            fuzzy_data: Dict mapping timeframes to fuzzy membership DataFrames
            indicators: Dict mapping timeframes to indicator DataFrames
            saved_scaler: Pre-trained scaler for consistent feature scaling
            
        Returns:
            Tensor of prepared features
        """
        logger.debug("Preparing multi-timeframe features")
        
        # Extract features for each timeframe
        timeframe_features = []
        feature_names = []
        
        timeframe_order = self._get_timeframe_order()
        
        for timeframe in timeframe_order:
            if timeframe not in self.timeframe_configs:
                continue
                
            tf_config = self.timeframe_configs[timeframe]
            if not tf_config.enabled:
                logger.debug(f"Skipping disabled timeframe: {timeframe}")
                continue
            
            if timeframe not in fuzzy_data:
                logger.warning(f"Missing fuzzy data for timeframe {timeframe}")
                # Create zero features for missing timeframe
                tf_features = np.zeros(len(tf_config.expected_features))
                tf_names = [f"{feat}_{timeframe}" for feat in tf_config.expected_features]
            else:
                tf_features, tf_names = self._extract_timeframe_features(
                    fuzzy_data[timeframe], 
                    timeframe, 
                    tf_config.expected_features
                )
            
            timeframe_features.extend(tf_features)
            feature_names.extend(tf_names)

        # Convert to numpy array
        feature_array = np.array(timeframe_features).reshape(1, -1)
        
        # Apply feature scaling
        if self.config.get("feature_processing", {}).get("scale_features", True):
            feature_array, _ = self._scale_features(feature_array, saved_scaler)
        
        # Convert to tensor
        features_tensor = torch.FloatTensor(feature_array)
        
        logger.debug(f"Prepared features shape: {features_tensor.shape}")
        return features_tensor

    def _extract_timeframe_features(
        self,
        fuzzy_data: pd.DataFrame,
        timeframe: str,
        expected_features: List[str]
    ) -> Tuple[List[float], List[str]]:
        """
        Extract features for a specific timeframe.
        
        Args:
            fuzzy_data: Fuzzy membership DataFrame for this timeframe
            timeframe: Timeframe identifier (e.g., "1h", "4h")
            expected_features: List of expected feature column names
            
        Returns:
            Tuple of (feature values, feature names)
        """
        features = []
        feature_names = []
        
        # Get the latest row (most recent data)
        if len(fuzzy_data) == 0:
            logger.warning(f"Empty fuzzy data for timeframe {timeframe}")
            return [0.0] * len(expected_features), [f"{feat}_{timeframe}" for feat in expected_features]
        
        latest_row = fuzzy_data.iloc[-1]
        
        # Extract expected features
        for expected_feature in expected_features:
            # Handle both direct feature names and those with timeframe suffixes
            feature_col = expected_feature
            if feature_col not in latest_row.index:
                # Try with timeframe suffix removed if it exists
                if f"_{timeframe}" in feature_col:
                    feature_col = feature_col.replace(f"_{timeframe}", "")
            
            feature_name = f"{expected_feature}"  # Keep the expected feature name as-is
            
            if feature_col in latest_row.index:
                value = float(latest_row[feature_col])
                # Ensure value is in valid range [0, 1] for fuzzy membership
                value = max(0.0, min(1.0, value))
            else:
                logger.warning(f"Missing feature {expected_feature} for timeframe {timeframe}")
                value = 0.0
            
            features.append(value)
            feature_names.append(feature_name)
        
        return features, feature_names

    def _scale_features(
        self,
        features: np.ndarray,
        scaler: Optional[Any] = None
    ) -> Tuple[np.ndarray, Any]:
        """
        Apply feature scaling with scaler persistence.
        
        Args:
            features: Feature array to scale
            scaler: Optional pre-trained scaler
            
        Returns:
            Tuple of (scaled features, scaler)
        """
        if scaler is not None:
            # Use existing scaler
            scaled_features = scaler.transform(features)
            return scaled_features, scaler
        else:
            # Create new scaler
            scaler_type = self.config.get("feature_processing", {}).get("scaler_type", "standard")
            
            if scaler_type == "standard":
                scaler = StandardScaler()
            elif scaler_type == "minmax":
                scaler = MinMaxScaler()
            else:
                scaler = StandardScaler()
            
            scaled_features = scaler.fit_transform(features)
            self.feature_scaler = scaler
            
            return scaled_features, scaler

    def train(
        self,
        X: torch.Tensor,
        y: torch.Tensor,
        validation_data: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> MultiTimeframeTrainingResult:
        """
        Train the multi-timeframe MLP model.
        
        Args:
            X: Training features tensor (batch_size, feature_count)
            y: Training labels tensor (batch_size,) with values 0=BUY, 1=HOLD, 2=SELL
            validation_data: Optional (X_val, y_val) tuple
            
        Returns:
            MultiTimeframeTrainingResult with training metrics
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")

        logger.info(f"Training MultiTimeframeMLP with {X.shape[0]} samples, {X.shape[1]} features")

        # Get training parameters
        training_config = self.config.get("training", {})
        learning_rate = training_config.get("learning_rate", 0.001)
        batch_size = training_config.get("batch_size", 32)
        epochs = training_config.get("epochs", 200)
        patience = training_config.get("early_stopping_patience", 20)
        
        # Setup optimizer and loss
        optimizer_name = training_config.get("optimizer", "adam").lower()
        if optimizer_name == "adam":
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        elif optimizer_name == "sgd":
            optimizer = torch.optim.SGD(self.model.parameters(), lr=learning_rate, momentum=0.9)
        elif optimizer_name == "adamw":
            optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        else:
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)

        criterion = nn.CrossEntropyLoss()
        
        # Learning rate scheduler
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=10
        )

        # Training history
        history = {
            "train_loss": [],
            "train_accuracy": [],
            "val_loss": [],
            "val_accuracy": [],
            "learning_rate": []
        }

        # Convert labels to LongTensor for CrossEntropyLoss
        y = y.long()
        if validation_data is not None:
            X_val, y_val = validation_data
            y_val = y_val.long()

        # Early stopping variables
        best_val_loss = float('inf')
        patience_counter = 0
        best_model_state = None

        # Training loop
        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            epoch_accuracy = 0.0
            num_batches = 0
            
            # Create batches
            for i in range(0, len(X), batch_size):
                batch_X = X[i:i + batch_size]
                batch_y = y[i:i + batch_size]
                
                # Forward pass
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                
                # Backward pass
                optimizer.zero_grad()
                loss.backward()
                
                # Gradient clipping to prevent exploding gradients
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                optimizer.step()
                
                # Calculate accuracy
                _, predicted = torch.max(outputs.data, 1)
                batch_accuracy = (predicted == batch_y).float().mean()
                
                epoch_loss += loss.item()
                epoch_accuracy += batch_accuracy.item()
                num_batches += 1

            # Average metrics for epoch
            avg_train_loss = epoch_loss / num_batches
            avg_train_accuracy = epoch_accuracy / num_batches
            
            history["train_loss"].append(avg_train_loss)
            history["train_accuracy"].append(avg_train_accuracy)
            history["learning_rate"].append(optimizer.param_groups[0]['lr'])

            # Validation
            val_loss = 0.0
            val_accuracy = 0.0
            if validation_data is not None:
                self.model.eval()
                with torch.no_grad():
                    val_outputs = self.model(X_val)
                    val_loss = criterion(val_outputs, y_val).item()
                    _, val_predicted = torch.max(val_outputs.data, 1)
                    val_accuracy = (val_predicted == y_val).float().mean().item()

                history["val_loss"].append(val_loss)
                history["val_accuracy"].append(val_accuracy)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    best_model_state = self.model.state_dict().copy()
                else:
                    patience_counter += 1
                
                # Learning rate scheduling
                scheduler.step(val_loss)
                
                self.model.train()

            # Logging
            if epoch % 20 == 0 or epoch == epochs - 1:
                if validation_data is not None:
                    logger.info(
                        f"Epoch {epoch+1}/{epochs}: "
                        f"Train Loss: {avg_train_loss:.4f}, Train Acc: {avg_train_accuracy:.4f}, "
                        f"Val Loss: {val_loss:.4f}, Val Acc: {val_accuracy:.4f}"
                    )
                else:
                    logger.info(
                        f"Epoch {epoch+1}/{epochs}: "
                        f"Train Loss: {avg_train_loss:.4f}, Train Acc: {avg_train_accuracy:.4f}"
                    )
            
            # Early stopping check
            if patience_counter >= patience and validation_data is not None:
                logger.info(f"Early stopping at epoch {epoch+1}")
                # Restore best model
                if best_model_state is not None:
                    self.model.load_state_dict(best_model_state)
                break

        self.is_trained = True
        
        # Calculate final performance metrics
        performance_metrics = self._calculate_performance_metrics(X, y, validation_data)
        
        # Calculate feature importance (placeholder)
        feature_importance = self._calculate_feature_importance()
        
        # Calculate timeframe contributions
        timeframe_contributions = self._calculate_timeframe_contributions()
        
        return MultiTimeframeTrainingResult(
            training_history=history,
            feature_importance=feature_importance,
            timeframe_contributions=timeframe_contributions,
            model_performance=performance_metrics,
            convergence_metrics={
                "converged": patience_counter < patience,
                "final_epoch": min(epoch + 1, epochs),
                "best_val_loss": best_val_loss
            }
        )

    def _calculate_performance_metrics(
        self,
        X: torch.Tensor,
        y: torch.Tensor,
        validation_data: Optional[Tuple[torch.Tensor, torch.Tensor]]
    ) -> Dict[str, float]:
        """Calculate comprehensive performance metrics."""
        self.model.eval()
        metrics = {}
        
        with torch.no_grad():
            # Training metrics
            train_outputs = self.model(X)
            _, train_predicted = torch.max(train_outputs, 1)
            train_accuracy = (train_predicted == y).float().mean().item()
            metrics["train_accuracy"] = train_accuracy
            
            # Validation metrics
            if validation_data is not None:
                X_val, y_val = validation_data
                val_outputs = self.model(X_val)
                _, val_predicted = torch.max(val_outputs, 1)
                val_accuracy = (val_predicted == y_val).float().mean().item()
                metrics["val_accuracy"] = val_accuracy
        
        return metrics

    def _calculate_feature_importance(self) -> Optional[Dict[str, float]]:
        """Calculate feature importance (placeholder implementation)."""
        # This is a simplified placeholder
        # In practice, you might use techniques like:
        # - Gradient-based feature importance
        # - Permutation importance
        # - SHAP values
        
        if len(self.feature_order) == 0:
            return None
        
        # Placeholder: uniform importance
        importance = 1.0 / len(self.feature_order)
        return {feature: importance for feature in self.feature_order}

    def _calculate_timeframe_contributions(self) -> Dict[str, float]:
        """Calculate relative contributions of each timeframe."""
        timeframe_contributions = {}
        
        for timeframe, config in self.timeframe_configs.items():
            if config.enabled:
                # Simple approach: based on number of features and weight
                num_features = len(config.expected_features)
                contribution = num_features * config.weight
                timeframe_contributions[timeframe] = contribution
        
        # Normalize to sum to 1.0
        total_contribution = sum(timeframe_contributions.values())
        if total_contribution > 0:
            timeframe_contributions = {
                tf: contrib / total_contribution 
                for tf, contrib in timeframe_contributions.items()
            }
        
        return timeframe_contributions

    def predict_with_timeframe_breakdown(
        self, 
        features: torch.Tensor
    ) -> Dict[str, Any]:
        """
        Generate prediction with timeframe contribution breakdown.
        
        Args:
            features: Input features tensor
            
        Returns:
            Dictionary with prediction, confidence, probabilities, and timeframe analysis
        """
        # Get standard prediction
        prediction = self.predict(features)
        
        # Add timeframe contribution analysis
        timeframe_contributions = self._calculate_timeframe_contributions()
        
        prediction["timeframe_analysis"] = {
            "contributions": timeframe_contributions,
            "feature_count_by_timeframe": {
                tf: len(config.expected_features) 
                for tf, config in self.timeframe_configs.items()
                if config.enabled
            }
        }
        
        return prediction

    def get_model_summary(self) -> Dict[str, Any]:
        """Get comprehensive model summary."""
        summary = {
            "model_type": "MultiTimeframeMLP",
            "total_parameters": sum(p.numel() for p in self.model.parameters()) if self.model else 0,
            "trainable_parameters": sum(p.numel() for p in self.model.parameters() if p.requires_grad) if self.model else 0,
            "timeframes": list(self.timeframe_configs.keys()),
            "enabled_timeframes": [tf for tf, config in self.timeframe_configs.items() if config.enabled],
            "total_features": len(self.feature_order),
            "expected_input_size": self.expected_input_size,
            "is_trained": self.is_trained
        }
        
        if self.model:
            summary["architecture"] = str(self.model)
        
        return summary