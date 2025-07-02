"""Core metrics collection utilities for training analytics."""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from sklearn.metrics import precision_recall_fscore_support
import logging

from ktrdr import get_logger
from .detailed_metrics import DetailedTrainingMetrics

logger = get_logger(__name__)


class MetricsCollector:
    """Handles collection of detailed training metrics from PyTorch models."""
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.previous_params: Optional[Dict[str, torch.Tensor]] = None
        self.class_names = ["BUY", "HOLD", "SELL"]
        
    def collect_gradient_metrics(self, model: nn.Module) -> Dict[str, Any]:
        """Calculate gradient norms and related metrics.
        
        Args:
            model: PyTorch model after loss.backward() has been called
            
        Returns:
            Dictionary containing gradient statistics
        """
        try:
            total_norm = 0.0
            layer_norms = {}
            max_norm = 0.0
            
            for name, param in model.named_parameters():
                if param.grad is not None:
                    param_norm = param.grad.data.norm(2).item()
                    total_norm += param_norm ** 2
                    layer_norms[name] = param_norm
                    max_norm = max(max_norm, param_norm)
            
            total_norm = total_norm ** 0.5
            avg_norm = total_norm / len(layer_norms) if layer_norms else 0.0
            
            return {
                'total_norm': total_norm,
                'average_norm': avg_norm,
                'maximum_norm': max_norm,
                'layer_norms': layer_norms
            }
            
        except Exception as e:
            logger.warning(f"Failed to collect gradient metrics: {e}")
            return {
                'total_norm': 0.0,
                'average_norm': 0.0,
                'maximum_norm': 0.0,
                'layer_norms': {}
            }
    
    def collect_parameter_metrics(self, model: nn.Module) -> Dict[str, Any]:
        """Calculate parameter change statistics between epochs.
        
        Args:
            model: PyTorch model with current parameters
            
        Returns:
            Dictionary containing parameter change statistics
        """
        try:
            current_params = {name: param.data.clone() for name, param in model.named_parameters()}
            
            if self.previous_params is None:
                # First epoch - no changes to calculate
                self.previous_params = current_params
                return {
                    'total_change_magnitude': 0.0,
                    'layer_changes': {},
                    'param_stats_by_layer': {}
                }
            
            total_change = 0.0
            layer_changes = {}
            param_stats = {}
            
            for name, current in current_params.items():
                if name in self.previous_params:
                    change = (current - self.previous_params[name])
                    change_magnitude = change.norm().item()
                    total_change += change_magnitude ** 2
                    layer_changes[name] = change_magnitude
                    
                    # Additional parameter statistics
                    param_stats[name] = {
                        'mean_change': change.mean().item(),
                        'std_change': change.std().item(),
                        'max_change': change.abs().max().item(),
                        'mean_value': current.mean().item(),
                        'std_value': current.std().item()
                    }
            
            # Update previous parameters for next epoch
            self.previous_params = current_params
            
            return {
                'total_change_magnitude': total_change ** 0.5,
                'layer_changes': layer_changes,
                'param_stats_by_layer': param_stats
            }
            
        except Exception as e:
            logger.warning(f"Failed to collect parameter metrics: {e}")
            return {
                'total_change_magnitude': 0.0,
                'layer_changes': {},
                'param_stats_by_layer': {}
            }
    
    def collect_class_metrics(self, y_true: torch.Tensor, y_pred: torch.Tensor) -> Dict[str, Any]:
        """Calculate class-wise precision, recall, and F1 scores.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels (class indices)
            
        Returns:
            Dictionary containing class-wise metrics
        """
        try:
            # Convert to numpy for sklearn
            y_true_np = y_true.cpu().numpy()
            y_pred_np = y_pred.cpu().numpy()
            
            # Calculate metrics
            precision, recall, f1, support = precision_recall_fscore_support(
                y_true_np, y_pred_np, average=None, zero_division=0, labels=[0, 1, 2]
            )
            
            # Organize by class name
            class_precisions = {}
            class_recalls = {}
            class_f1_scores = {}
            class_supports = {}
            
            for i, class_name in enumerate(self.class_names):
                if i < len(precision):
                    class_precisions[class_name] = float(precision[i])
                    class_recalls[class_name] = float(recall[i])
                    class_f1_scores[class_name] = float(f1[i])
                    class_supports[class_name] = int(support[i])
                else:
                    class_precisions[class_name] = 0.0
                    class_recalls[class_name] = 0.0
                    class_f1_scores[class_name] = 0.0
                    class_supports[class_name] = 0
            
            return {
                'class_precisions': class_precisions,
                'class_recalls': class_recalls,
                'class_f1_scores': class_f1_scores,
                'class_supports': class_supports
            }
            
        except Exception as e:
            logger.warning(f"Failed to collect class metrics: {e}")
            return {
                'class_precisions': {name: 0.0 for name in self.class_names},
                'class_recalls': {name: 0.0 for name in self.class_names},
                'class_f1_scores': {name: 0.0 for name in self.class_names},
                'class_supports': {name: 0 for name in self.class_names}
            }
    
    def collect_prediction_metrics(self, model_outputs: torch.Tensor) -> Dict[str, Any]:
        """Calculate prediction confidence and entropy metrics.
        
        Args:
            model_outputs: Raw model outputs (logits or probabilities)
            
        Returns:
            Dictionary containing prediction confidence statistics
        """
        try:
            # Apply softmax to get probabilities if not already applied
            if model_outputs.dim() > 1 and model_outputs.size(1) > 1:
                probs = torch.softmax(model_outputs, dim=1)
            else:
                probs = model_outputs
            
            # Calculate confidence metrics
            max_probs = torch.max(probs, dim=1)[0]
            mean_confidence = max_probs.mean().item()
            
            # High confidence predictions (>0.7 confidence)
            high_confidence_mask = max_probs > 0.7
            high_confidence_ratio = high_confidence_mask.float().mean().item()
            
            # Calculate entropy
            log_probs = torch.log(probs + 1e-10)  # Add small value to avoid log(0)
            entropy = -torch.sum(probs * log_probs, dim=1)
            mean_entropy = entropy.mean().item()
            
            # Confidence distribution (binned)
            confidence_bins = [0.0, 0.4, 0.6, 0.8, 1.0]
            confidence_dist = []
            for i in range(len(confidence_bins) - 1):
                lower, upper = confidence_bins[i], confidence_bins[i + 1]
                in_bin = ((max_probs >= lower) & (max_probs < upper)).float().mean().item()
                confidence_dist.append(in_bin)
            
            return {
                'mean_confidence': mean_confidence,
                'high_confidence_predictions': high_confidence_ratio,
                'prediction_entropy': mean_entropy,
                'confidence_distribution': confidence_dist
            }
            
        except Exception as e:
            logger.warning(f"Failed to collect prediction metrics: {e}")
            return {
                'mean_confidence': 0.0,
                'high_confidence_predictions': 0.0,
                'prediction_entropy': 0.0,
                'confidence_distribution': [0.0, 0.0, 0.0, 0.0]
            }
    
    def calculate_learning_indicators(
        self, 
        current_metrics: DetailedTrainingMetrics,
        previous_metrics: Optional[DetailedTrainingMetrics]
    ) -> Dict[str, Any]:
        """Calculate high-level learning quality indicators.
        
        Args:
            current_metrics: Current epoch metrics
            previous_metrics: Previous epoch metrics (if available)
            
        Returns:
            Dictionary containing learning quality indicators
        """
        try:
            # Learning signal strength
            signal_strength = self._calculate_learning_signal_strength(
                current_metrics, previous_metrics
            )
            
            # Overfitting score
            overfitting_score = self._calculate_overfitting_score(current_metrics)
            
            # Class balance score
            class_balance_score = self._calculate_class_balance_score(current_metrics)
            
            # Convergence indicator
            convergence_indicator = self._calculate_convergence_indicator(
                current_metrics, previous_metrics
            )
            
            return {
                'learning_signal_strength': signal_strength,
                'overfitting_score': overfitting_score,
                'class_balance_score': class_balance_score,
                'convergence_indicator': convergence_indicator
            }
            
        except Exception as e:
            logger.warning(f"Failed to calculate learning indicators: {e}")
            return {
                'learning_signal_strength': 'unknown',
                'overfitting_score': 0.0,
                'class_balance_score': 0.0,
                'convergence_indicator': 'unknown'
            }
    
    def _calculate_learning_signal_strength(
        self, 
        current: DetailedTrainingMetrics,
        previous: Optional[DetailedTrainingMetrics]
    ) -> str:
        """Determine learning signal strength based on multiple indicators."""
        if previous is None:
            return "unknown"
        
        score = 0
        
        # Check loss improvement
        if previous.train_loss > 0:
            loss_improvement = (previous.train_loss - current.train_loss) / previous.train_loss
            if loss_improvement > 0.05:  # >5% improvement
                score += 2
            elif loss_improvement > 0.01:  # >1% improvement
                score += 1
        
        # Check gradient magnitude
        if current.gradient_norm_avg > 0.1:
            score += 2
        elif current.gradient_norm_avg > 0.01:
            score += 1
        
        # Check parameter changes
        if current.param_change_magnitude > 0.01:
            score += 1
        
        # Classify strength
        if score >= 4:
            return "strong"
        elif score >= 2:
            return "medium"
        else:
            return "weak"
    
    def _calculate_overfitting_score(self, metrics: DetailedTrainingMetrics) -> float:
        """Calculate overfitting score based on train/val gap."""
        if metrics.val_loss is None or metrics.val_accuracy is None:
            return 0.0
        
        # Loss gap (higher = more overfitting)
        loss_gap = metrics.val_loss - metrics.train_loss
        loss_gap_normalized = max(0.0, min(1.0, loss_gap / 0.5))  # Normalize to 0-1
        
        # Accuracy gap (higher = more overfitting)
        acc_gap = metrics.train_accuracy - metrics.val_accuracy
        acc_gap_normalized = max(0.0, min(1.0, acc_gap / 0.3))  # Normalize to 0-1
        
        # Combined score
        overfitting_score = (loss_gap_normalized + acc_gap_normalized) / 2
        return float(overfitting_score)
    
    def _calculate_class_balance_score(self, metrics: DetailedTrainingMetrics) -> float:
        """Calculate class balance score (1.0 = perfect balance, 0.0 = severe imbalance)."""
        if not metrics.class_supports:
            return 0.0
        
        supports = list(metrics.class_supports.values())
        if not supports or sum(supports) == 0:
            return 0.0
        
        # Calculate coefficient of variation (lower = more balanced)
        mean_support = np.mean(supports)
        std_support = np.std(supports)
        
        if mean_support == 0:
            return 0.0
        
        cv = std_support / mean_support
        # Convert to balance score (1 - normalized CV)
        balance_score = max(0.0, 1.0 - min(1.0, cv))
        return float(balance_score)
    
    def _calculate_convergence_indicator(
        self,
        current: DetailedTrainingMetrics,
        previous: Optional[DetailedTrainingMetrics]
    ) -> str:
        """Determine if training is improving, plateauing, or diverging."""
        if previous is None:
            return "unknown"
        
        # Check loss trend
        loss_change = current.train_loss - previous.train_loss
        
        # Check if we have validation loss
        if current.val_loss is not None and previous.val_loss is not None:
            val_loss_change = current.val_loss - previous.val_loss
            
            if loss_change < -0.01 and val_loss_change < 0.01:
                return "improving"
            elif abs(loss_change) < 0.001 and abs(val_loss_change) < 0.001:
                return "plateauing"
            elif loss_change > 0.01 or val_loss_change > 0.05:
                return "diverging"
            else:
                return "stable"
        else:
            # Only training loss available
            if loss_change < -0.01:
                return "improving"
            elif abs(loss_change) < 0.001:
                return "plateauing"
            elif loss_change > 0.01:
                return "diverging"
            else:
                return "stable"