"""
Multi-timeframe neural network training pipeline.

This module provides enhanced training capabilities for multi-timeframe
neural networks including cross-timeframe validation, early stopping
strategies, and comprehensive training metrics.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from typing import Dict, Any, List, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
import time
from sklearn.model_selection import train_test_split, StratifiedKFold, TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from ktrdr import get_logger
from ktrdr.neural.models.multi_timeframe_mlp import (
    MultiTimeframeMLP,
    MultiTimeframeTrainingResult,
)
from ktrdr.neural.feature_engineering import MultiTimeframeFeatureEngineer
from ktrdr.errors import ConfigurationError, ProcessingError

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class CrossTimeframeValidationConfig:
    """Configuration for cross-timeframe validation strategies."""

    method: str = (
        "temporal_split"  # temporal_split, stratified_kfold, timeframe_holdout
    )
    n_splits: int = 5
    test_size: float = 0.2
    validation_size: float = 0.15
    holdout_timeframe: Optional[str] = None
    temporal_gap: int = 0  # Gap between train/validation for temporal split
    shuffle: bool = False
    random_state: Optional[int] = 42


@dataclass
class EarlyStoppingConfig:
    """Configuration for early stopping strategies."""

    monitor: str = "val_loss"  # val_loss, val_accuracy, cross_timeframe_consistency
    patience: int = 20
    min_delta: float = 0.001
    mode: str = "min"  # min for loss, max for accuracy
    restore_best_weights: bool = True
    baseline: Optional[float] = None


@dataclass
class TrainingMetrics:
    """Comprehensive training metrics for multi-timeframe models."""

    epoch: int
    train_loss: float
    train_accuracy: float
    val_loss: float
    val_accuracy: float
    cross_timeframe_consistency: float
    timeframe_accuracies: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.001
    gradient_norm: float = 0.0
    processing_time: float = 0.0


@dataclass
class MultiTimeframeTrainingConfig:
    """Complete configuration for multi-timeframe training."""

    model_config: Dict[str, Any]
    feature_engineering_config: Dict[str, Any]
    validation_config: CrossTimeframeValidationConfig
    early_stopping_config: EarlyStoppingConfig
    training_params: Dict[str, Any] = field(default_factory=dict)
    save_checkpoints: bool = True
    checkpoint_dir: Optional[str] = None


class MultiTimeframeTrainer:
    """
    Enhanced trainer for multi-timeframe neural networks.

    This trainer provides comprehensive training capabilities including:
    - Cross-timeframe validation strategies
    - Advanced early stopping with multi-metric monitoring
    - Timeframe-specific performance tracking
    - Automated hyperparameter logging
    - Model checkpointing and recovery
    """

    def __init__(self, config: MultiTimeframeTrainingConfig):
        """
        Initialize the multi-timeframe trainer.

        Args:
            config: Complete training configuration
        """
        self.config = config
        self.model = None
        self.feature_engineer = None
        self.training_history = []
        self.best_model_state = None
        self.best_metrics = None
        self.is_trained = False

        # Setup checkpoint directory
        if config.save_checkpoints and config.checkpoint_dir:
            self.checkpoint_dir = Path(config.checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.checkpoint_dir = None

        logger.info("Initialized MultiTimeframeTrainer")

    def train(
        self,
        multi_timeframe_data: Dict[str, Dict[str, np.ndarray]],
        labels: np.ndarray,
        validation_data: Optional[
            Tuple[Dict[str, Dict[str, np.ndarray]], np.ndarray]
        ] = None,
    ) -> MultiTimeframeTrainingResult:
        """
        Train the multi-timeframe model with comprehensive validation.

        Args:
            multi_timeframe_data: Dictionary mapping timeframes to feature dictionaries
            labels: Target labels (0=BUY, 1=HOLD, 2=SELL)
            validation_data: Optional validation data tuple

        Returns:
            MultiTimeframeTrainingResult with comprehensive training metrics
        """
        logger.info("Starting multi-timeframe training")
        training_start_time = time.time()

        try:
            # Initialize feature engineer
            self.feature_engineer = MultiTimeframeFeatureEngineer(
                self.config.feature_engineering_config
            )

            # Prepare features
            features_by_timeframe = self._prepare_timeframe_features(
                multi_timeframe_data
            )

            # Apply feature engineering
            feature_result = self.feature_engineer.fit_transform(
                features_by_timeframe, labels
            )
            X_train = feature_result.transformed_features

            # Prepare validation data if provided
            X_val, y_val = None, None
            if validation_data is not None:
                val_features_by_timeframe = self._prepare_timeframe_features(
                    validation_data[0]
                )
                X_val = self.feature_engineer.transform(val_features_by_timeframe)
                y_val = validation_data[1]
            else:
                # Create validation split
                X_train, X_val, y_train, y_val = self._create_validation_split(
                    X_train, labels
                )
                labels = y_train  # Update labels to training subset

            # Initialize model
            self.model = MultiTimeframeMLP(self.config.model_config)
            self.model.build_model(X_train.shape[1])

            # Convert to tensors
            X_train_tensor = torch.FloatTensor(X_train)
            y_train_tensor = torch.LongTensor(labels)
            X_val_tensor = torch.FloatTensor(X_val)
            y_val_tensor = torch.LongTensor(y_val)

            # Perform cross-timeframe validation if configured
            if self.config.validation_config.method != "simple_split":
                cv_results = self._perform_cross_timeframe_validation(
                    features_by_timeframe, labels
                )
            else:
                cv_results = None

            # Train model with enhanced monitoring
            training_result = self._train_with_enhanced_monitoring(
                X_train_tensor,
                y_train_tensor,
                X_val_tensor,
                y_val_tensor,
                features_by_timeframe,
            )

            # Calculate final metrics
            final_metrics = self._calculate_final_metrics(
                X_train_tensor,
                y_train_tensor,
                X_val_tensor,
                y_val_tensor,
                features_by_timeframe,
            )

            # Update training result with additional information
            training_result.model_performance.update(final_metrics)
            training_result.feature_importance = feature_result.feature_importance

            if cv_results:
                training_result.model_performance["cross_validation"] = cv_results

            # Save final model if checkpointing enabled
            if self.checkpoint_dir:
                self._save_final_model(training_result)

            total_training_time = time.time() - training_start_time
            logger.info(f"Training completed in {total_training_time:.2f} seconds")

            training_result.model_performance["total_training_time"] = (
                total_training_time
            )
            self.is_trained = True

            return training_result

        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise ProcessingError(
                message="Multi-timeframe training failed",
                error_code="TRAINING-Failed",
                details={"original_error": str(e)},
            ) from e

    def _prepare_timeframe_features(
        self, multi_timeframe_data: Dict[str, Dict[str, np.ndarray]]
    ) -> Dict[str, np.ndarray]:
        """Prepare features by timeframe for feature engineering."""
        features_by_timeframe = {}

        for timeframe, timeframe_data in multi_timeframe_data.items():
            # Combine all feature arrays for this timeframe
            if isinstance(timeframe_data, dict):
                # If it's a dictionary of feature arrays, concatenate them
                feature_arrays = []
                for feature_name, feature_array in timeframe_data.items():
                    if feature_array.ndim == 1:
                        feature_array = feature_array.reshape(-1, 1)
                    feature_arrays.append(feature_array)

                if feature_arrays:
                    features_by_timeframe[timeframe] = np.concatenate(
                        feature_arrays, axis=1
                    )
                else:
                    logger.warning(f"No features found for timeframe {timeframe}")
            else:
                # If it's already an array, use it directly
                features_by_timeframe[timeframe] = timeframe_data

        return features_by_timeframe

    def _create_validation_split(
        self, X: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Create validation split based on configuration."""
        val_config = self.config.validation_config

        if val_config.method == "temporal_split":
            # Time-based split preserving temporal order
            split_idx = int(len(X) * (1 - val_config.test_size))
            if val_config.temporal_gap > 0:
                split_idx = max(0, split_idx - val_config.temporal_gap)

            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

        else:
            # Random stratified split
            X_train, X_val, y_train, y_val = train_test_split(
                X,
                y,
                test_size=val_config.test_size,
                stratify=y,
                random_state=val_config.random_state,
                shuffle=val_config.shuffle,
            )

        logger.debug(
            f"Created validation split: {len(X_train)} train, {len(X_val)} val"
        )
        return X_train, X_val, y_train, y_val

    def _perform_cross_timeframe_validation(
        self, features_by_timeframe: Dict[str, np.ndarray], labels: np.ndarray
    ) -> Dict[str, Any]:
        """Perform cross-timeframe validation."""
        val_config = self.config.validation_config
        cv_results = {
            "method": val_config.method,
            "n_splits": val_config.n_splits,
            "scores": [],
            "mean_score": 0.0,
            "std_score": 0.0,
        }

        # Combine features for cross-validation
        combined_features, _ = self.feature_engineer._combine_timeframe_features(
            features_by_timeframe
        )

        try:
            if val_config.method == "stratified_kfold":
                cv = StratifiedKFold(
                    n_splits=val_config.n_splits,
                    shuffle=val_config.shuffle,
                    random_state=val_config.random_state,
                )
            elif val_config.method == "timeseries_split":
                cv = TimeSeriesSplit(n_splits=val_config.n_splits)
            else:
                logger.warning(f"Unknown CV method: {val_config.method}")
                return cv_results

            fold_scores = []

            for fold, (train_idx, val_idx) in enumerate(
                cv.split(combined_features, labels)
            ):
                logger.debug(f"Processing CV fold {fold + 1}/{val_config.n_splits}")

                # Split data
                X_fold_train, X_fold_val = (
                    combined_features[train_idx],
                    combined_features[val_idx],
                )
                y_fold_train, y_fold_val = labels[train_idx], labels[val_idx]

                # Create temporary model for this fold
                fold_model = MultiTimeframeMLP(self.config.model_config)
                fold_model.build_model(X_fold_train.shape[1])

                # Quick training for evaluation
                X_fold_train_tensor = torch.FloatTensor(X_fold_train)
                y_fold_train_tensor = torch.LongTensor(y_fold_train)
                X_fold_val_tensor = torch.FloatTensor(X_fold_val)
                y_fold_val_tensor = torch.LongTensor(y_fold_val)

                # Simplified training for CV
                fold_result = fold_model.train(
                    X_fold_train_tensor,
                    y_fold_train_tensor,
                    validation_data=(X_fold_val_tensor, y_fold_val_tensor),
                )

                # Calculate fold score
                fold_score = fold_result.model_performance.get("val_accuracy", 0.0)
                fold_scores.append(fold_score)

                logger.debug(f"Fold {fold + 1} score: {fold_score:.4f}")

            cv_results["scores"] = fold_scores
            cv_results["mean_score"] = float(np.mean(fold_scores))
            cv_results["std_score"] = float(np.std(fold_scores))

            logger.info(
                f"Cross-validation complete: {cv_results['mean_score']:.4f} ± {cv_results['std_score']:.4f}"
            )

        except Exception as e:
            logger.error(f"Cross-validation failed: {e}")
            cv_results["error"] = str(e)

        return cv_results

    def _train_with_enhanced_monitoring(
        self,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        features_by_timeframe: Dict[str, np.ndarray],
    ) -> MultiTimeframeTrainingResult:
        """Train model with enhanced monitoring and early stopping."""
        # Get training parameters
        training_params = self.config.training_params
        epochs = training_params.get("epochs", 200)

        # Setup early stopping
        early_stopping = EnhancedEarlyStopping(self.config.early_stopping_config)

        # Perform standard training
        training_result = self.model.train(
            X_train, y_train, validation_data=(X_val, y_val)
        )

        # Enhance training result with additional metrics
        enhanced_metrics = self._calculate_enhanced_metrics(
            X_train, y_train, X_val, y_val, features_by_timeframe
        )

        training_result.model_performance.update(enhanced_metrics)

        return training_result

    def _calculate_enhanced_metrics(
        self,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        features_by_timeframe: Dict[str, np.ndarray],
    ) -> Dict[str, Any]:
        """Calculate enhanced metrics for multi-timeframe training."""
        enhanced_metrics = {}

        try:
            # Calculate cross-timeframe consistency
            consistency_score = self._calculate_cross_timeframe_consistency(
                features_by_timeframe
            )
            enhanced_metrics["cross_timeframe_consistency"] = consistency_score

            # Calculate detailed classification metrics
            self.model.model.eval()
            with torch.no_grad():
                # Training predictions
                train_outputs = self.model.model(X_train)
                _, train_preds = torch.max(train_outputs, 1)

                # Validation predictions
                val_outputs = self.model.model(X_val)
                _, val_preds = torch.max(val_outputs, 1)

            # Convert to numpy for sklearn metrics
            y_train_np = y_train.cpu().numpy()
            y_val_np = y_val.cpu().numpy()
            train_preds_np = train_preds.cpu().numpy()
            val_preds_np = val_preds.cpu().numpy()

            # Calculate detailed metrics
            enhanced_metrics.update(
                {
                    "train_precision": float(
                        precision_score(
                            y_train_np,
                            train_preds_np,
                            average="weighted",
                            zero_division=0,
                        )
                    ),
                    "train_recall": float(
                        recall_score(
                            y_train_np,
                            train_preds_np,
                            average="weighted",
                            zero_division=0,
                        )
                    ),
                    "train_f1": float(
                        f1_score(
                            y_train_np,
                            train_preds_np,
                            average="weighted",
                            zero_division=0,
                        )
                    ),
                    "val_precision": float(
                        precision_score(
                            y_val_np, val_preds_np, average="weighted", zero_division=0
                        )
                    ),
                    "val_recall": float(
                        recall_score(
                            y_val_np, val_preds_np, average="weighted", zero_division=0
                        )
                    ),
                    "val_f1": float(
                        f1_score(
                            y_val_np, val_preds_np, average="weighted", zero_division=0
                        )
                    ),
                }
            )

            # Class-specific metrics
            for class_idx, class_name in enumerate(["BUY", "HOLD", "SELL"]):
                # Training class metrics
                train_class_precision = precision_score(
                    y_train_np,
                    train_preds_np,
                    labels=[class_idx],
                    average=None,
                    zero_division=0,
                )
                train_class_recall = recall_score(
                    y_train_np,
                    train_preds_np,
                    labels=[class_idx],
                    average=None,
                    zero_division=0,
                )

                # Validation class metrics
                val_class_precision = precision_score(
                    y_val_np,
                    val_preds_np,
                    labels=[class_idx],
                    average=None,
                    zero_division=0,
                )
                val_class_recall = recall_score(
                    y_val_np,
                    val_preds_np,
                    labels=[class_idx],
                    average=None,
                    zero_division=0,
                )

                enhanced_metrics.update(
                    {
                        f"train_{class_name.lower()}_precision": (
                            float(train_class_precision[0])
                            if len(train_class_precision) > 0
                            else 0.0
                        ),
                        f"train_{class_name.lower()}_recall": (
                            float(train_class_recall[0])
                            if len(train_class_recall) > 0
                            else 0.0
                        ),
                        f"val_{class_name.lower()}_precision": (
                            float(val_class_precision[0])
                            if len(val_class_precision) > 0
                            else 0.0
                        ),
                        f"val_{class_name.lower()}_recall": (
                            float(val_class_recall[0])
                            if len(val_class_recall) > 0
                            else 0.0
                        ),
                    }
                )

            # Confusion matrices
            enhanced_metrics["train_confusion_matrix"] = confusion_matrix(
                y_train_np, train_preds_np
            ).tolist()
            enhanced_metrics["val_confusion_matrix"] = confusion_matrix(
                y_val_np, val_preds_np
            ).tolist()

        except Exception as e:
            logger.warning(f"Could not calculate enhanced metrics: {e}")

        return enhanced_metrics

    def _calculate_cross_timeframe_consistency(
        self, features_by_timeframe: Dict[str, np.ndarray]
    ) -> float:
        """Calculate consistency score across timeframes."""
        if len(features_by_timeframe) < 2:
            return 1.0  # Perfect consistency if only one timeframe

        try:
            # Calculate correlation between timeframe predictions
            correlations = []
            timeframes = list(features_by_timeframe.keys())

            for i, tf1 in enumerate(timeframes):
                for tf2 in timeframes[i + 1 :]:
                    # Get feature means as proxy for timeframe signal
                    signal1 = np.mean(features_by_timeframe[tf1], axis=1)
                    signal2 = np.mean(features_by_timeframe[tf2], axis=1)

                    # Calculate correlation
                    corr = np.corrcoef(signal1, signal2)[0, 1]
                    if not np.isnan(corr):
                        correlations.append(abs(corr))  # Use absolute correlation

            # Return average correlation as consistency score
            return float(np.mean(correlations)) if correlations else 0.0

        except Exception as e:
            logger.warning(f"Could not calculate cross-timeframe consistency: {e}")
            return 0.0

    def _calculate_final_metrics(
        self,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        features_by_timeframe: Dict[str, np.ndarray],
    ) -> Dict[str, Any]:
        """Calculate comprehensive final metrics."""
        final_metrics = {}

        try:
            # Model complexity metrics
            if self.model.model:
                total_params = sum(p.numel() for p in self.model.model.parameters())
                trainable_params = sum(
                    p.numel() for p in self.model.model.parameters() if p.requires_grad
                )

                final_metrics.update(
                    {
                        "total_parameters": int(total_params),
                        "trainable_parameters": int(trainable_params),
                        "model_size_mb": total_params
                        * 4
                        / (1024 * 1024),  # Assume float32
                    }
                )

            # Feature engineering metrics
            if self.feature_engineer:
                final_metrics["original_feature_count"] = sum(
                    arr.shape[1] for arr in features_by_timeframe.values()
                )
                final_metrics["final_feature_count"] = X_train.shape[1]
                final_metrics["feature_reduction_ratio"] = (
                    final_metrics["final_feature_count"]
                    / final_metrics["original_feature_count"]
                )

            # Training efficiency metrics
            final_metrics.update(
                {
                    "training_samples": int(X_train.shape[0]),
                    "validation_samples": int(X_val.shape[0]),
                    "timeframes_used": len(features_by_timeframe),
                    "convergence_achieved": self.model.is_trained,
                }
            )

        except Exception as e:
            logger.warning(f"Could not calculate final metrics: {e}")

        return final_metrics

    def _save_final_model(self, training_result: MultiTimeframeTrainingResult):
        """Save the final trained model and metadata."""
        if not self.checkpoint_dir:
            return

        try:
            # Save model
            model_path = self.checkpoint_dir / "final_model"
            self.model.save_model(str(model_path))

            # Save feature engineer
            if self.feature_engineer:
                import pickle

                with open(self.checkpoint_dir / "feature_engineer.pkl", "wb") as f:
                    pickle.dump(self.feature_engineer, f)

            # Save training results
            results_dict = {
                "training_history": training_result.training_history,
                "model_performance": training_result.model_performance,
                "timeframe_contributions": training_result.timeframe_contributions,
                "convergence_metrics": training_result.convergence_metrics,
            }

            with open(self.checkpoint_dir / "training_results.json", "w") as f:
                json.dump(results_dict, f, indent=2, default=str)

            logger.info(f"Model and results saved to {self.checkpoint_dir}")

        except Exception as e:
            logger.error(f"Failed to save model: {e}")


class EnhancedEarlyStopping:
    """Enhanced early stopping with multi-metric monitoring."""

    def __init__(self, config: EarlyStoppingConfig):
        """Initialize enhanced early stopping."""
        self.config = config
        self.best_score = None
        self.patience_counter = 0
        self.best_weights = None

    def __call__(
        self,
        score: float,
        model: nn.Module,
        additional_metrics: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Check if training should stop.

        Args:
            score: Current score to monitor
            model: Model to potentially save weights from
            additional_metrics: Additional metrics for complex stopping criteria

        Returns:
            True if training should stop
        """
        # Determine if this is an improvement
        is_improvement = self._is_improvement(score)

        if is_improvement:
            self.best_score = score
            self.patience_counter = 0

            if self.config.restore_best_weights:
                self.best_weights = model.state_dict().copy()

        else:
            self.patience_counter += 1

        # Check if we should stop
        should_stop = self.patience_counter >= self.config.patience

        if should_stop and self.config.restore_best_weights and self.best_weights:
            model.load_state_dict(self.best_weights)

        return should_stop

    def _is_improvement(self, score: float) -> bool:
        """Check if the current score is an improvement."""
        if self.best_score is None:
            return True

        if self.config.mode == "min":
            return score < (self.best_score - self.config.min_delta)
        else:  # mode == "max"
            return score > (self.best_score + self.config.min_delta)


def create_multi_timeframe_trainer(config: Dict[str, Any]) -> MultiTimeframeTrainer:
    """
    Factory function to create a multi-timeframe trainer.

    Args:
        config: Training configuration dictionary

    Returns:
        Configured MultiTimeframeTrainer instance
    """
    # Convert dictionary config to structured config
    training_config = MultiTimeframeTrainingConfig(
        model_config=config.get("model_config", {}),
        feature_engineering_config=config.get("feature_engineering_config", {}),
        validation_config=CrossTimeframeValidationConfig(
            **config.get("validation_config", {})
        ),
        early_stopping_config=EarlyStoppingConfig(
            **config.get("early_stopping_config", {})
        ),
        training_params=config.get("training_params", {}),
        save_checkpoints=config.get("save_checkpoints", True),
        checkpoint_dir=config.get("checkpoint_dir"),
    )

    return MultiTimeframeTrainer(training_config)
