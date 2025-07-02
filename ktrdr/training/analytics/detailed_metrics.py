"""Enhanced training metrics for comprehensive analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DetailedTrainingMetrics:
    """Extended training metrics for comprehensive analysis and debugging.
    
    This class extends the basic TrainingMetrics with detailed diagnostic
    information to help understand training behavior and identify issues.
    """
    
    # Basic metrics (existing compatibility)
    epoch: int
    train_loss: float
    train_accuracy: float
    val_loss: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    duration: float = 0.0
    
    # Gradient metrics for detecting vanishing/exploding gradients
    gradient_norm_avg: float = 0.0
    gradient_norm_max: float = 0.0
    gradient_norms_by_layer: Dict[str, float] = field(default_factory=dict)
    
    # Parameter metrics for tracking learning dynamics
    param_change_magnitude: float = 0.0
    param_stats_by_layer: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Class-wise metrics for multi-class classification analysis
    class_precisions: Dict[str, float] = field(default_factory=dict)
    class_recalls: Dict[str, float] = field(default_factory=dict)
    class_f1_scores: Dict[str, float] = field(default_factory=dict)
    class_supports: Dict[str, int] = field(default_factory=dict)
    
    # Prediction confidence metrics
    prediction_confidence_avg: float = 0.0
    prediction_entropy: float = 0.0
    high_confidence_predictions: float = 0.0
    confidence_distribution: List[float] = field(default_factory=list)
    
    # Learning quality indicators
    learning_signal_strength: str = "unknown"  # strong, medium, weak
    overfitting_score: float = 0.0
    class_balance_score: float = 0.0
    convergence_indicator: str = "unknown"  # improving, plateauing, diverging
    
    # Training process metrics
    batch_count: int = 0
    total_samples_processed: int = 0
    early_stopping_triggered: bool = False
    
    def to_csv_row(self) -> Dict[str, Any]:
        """Convert to flat dictionary for CSV export (LLM-friendly)."""
        return {
            'epoch': self.epoch,
            'train_loss': self.train_loss,
            'val_loss': self.val_loss,
            'train_acc': self.train_accuracy,
            'val_acc': self.val_accuracy,
            'learning_rate': self.learning_rate,
            'gradient_norm_avg': self.gradient_norm_avg,
            'gradient_norm_max': self.gradient_norm_max,
            'param_change_magnitude': self.param_change_magnitude,
            'buy_precision': self.class_precisions.get('BUY', 0.0),
            'hold_precision': self.class_precisions.get('HOLD', 0.0),
            'sell_precision': self.class_precisions.get('SELL', 0.0),
            'buy_recall': self.class_recalls.get('BUY', 0.0),
            'hold_recall': self.class_recalls.get('HOLD', 0.0),
            'sell_recall': self.class_recalls.get('SELL', 0.0),
            'prediction_confidence_avg': self.prediction_confidence_avg,
            'prediction_entropy': self.prediction_entropy,
            'learning_signal_strength': self.learning_signal_strength,
            'early_stopping_triggered': self.early_stopping_triggered,
            'overfitting_score': self.overfitting_score,
            'class_balance_score': self.class_balance_score,
            'batch_count': self.batch_count,
            'total_samples_processed': self.total_samples_processed,
            'epoch_duration_seconds': self.duration
        }
    
    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to comprehensive dictionary for JSON export."""
        return {
            'epoch': self.epoch,
            'train_loss': self.train_loss,
            'val_loss': self.val_loss,
            'train_accuracy': self.train_accuracy,
            'val_accuracy': self.val_accuracy,
            'learning_rate': self.learning_rate,
            'duration': self.duration,
            'gradient_norms': {
                'average': self.gradient_norm_avg,
                'maximum': self.gradient_norm_max,
                'by_layer': self.gradient_norms_by_layer
            },
            'parameter_stats': {
                'total_change_magnitude': self.param_change_magnitude,
                'by_layer': self.param_stats_by_layer
            },
            'class_metrics': {
                'BUY': {
                    'precision': self.class_precisions.get('BUY', 0.0),
                    'recall': self.class_recalls.get('BUY', 0.0),
                    'f1': self.class_f1_scores.get('BUY', 0.0),
                    'support': self.class_supports.get('BUY', 0)
                },
                'HOLD': {
                    'precision': self.class_precisions.get('HOLD', 0.0),
                    'recall': self.class_recalls.get('HOLD', 0.0),
                    'f1': self.class_f1_scores.get('HOLD', 0.0),
                    'support': self.class_supports.get('HOLD', 0)
                },
                'SELL': {
                    'precision': self.class_precisions.get('SELL', 0.0),
                    'recall': self.class_recalls.get('SELL', 0.0),
                    'f1': self.class_f1_scores.get('SELL', 0.0),
                    'support': self.class_supports.get('SELL', 0)
                }
            },
            'prediction_stats': {
                'mean_confidence': self.prediction_confidence_avg,
                'confidence_distribution': self.confidence_distribution,
                'prediction_entropy': self.prediction_entropy,
                'high_confidence_predictions': self.high_confidence_predictions
            },
            'learning_indicators': {
                'signal_strength': self.learning_signal_strength,
                'overfitting_score': self.overfitting_score,
                'class_balance_score': self.class_balance_score,
                'convergence_indicator': self.convergence_indicator
            },
            'timing': {
                'epoch_duration': self.duration,
                'batch_count': self.batch_count,
                'samples_processed': self.total_samples_processed
            },
            'early_stopping_triggered': self.early_stopping_triggered
        }
    
    @classmethod
    def from_basic_metrics(cls, basic_metrics, **additional_kwargs):
        """Create DetailedTrainingMetrics from basic TrainingMetrics."""
        return cls(
            epoch=basic_metrics.epoch,
            train_loss=basic_metrics.train_loss,
            train_accuracy=basic_metrics.train_accuracy,
            val_loss=basic_metrics.val_loss,
            val_accuracy=basic_metrics.val_accuracy,
            learning_rate=basic_metrics.learning_rate,
            duration=basic_metrics.duration,
            **additional_kwargs
        )