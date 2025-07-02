"""Main training analytics system for KTRDR neural networks."""

import json
import yaml
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import torch
import torch.nn as nn

from ktrdr import get_logger
from .detailed_metrics import DetailedTrainingMetrics
from .metrics_collector import MetricsCollector

logger = get_logger(__name__)


class TrainingAnalyzer:
    """Main analytics collection and export system for training runs."""
    
    def __init__(self, run_id: str, output_dir: Path, config: Dict[str, Any]):
        """Initialize the training analyzer.
        
        Args:
            run_id: Unique identifier for this training run
            output_dir: Directory to store analytics outputs
            config: Training configuration dictionary
        """
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.config = config
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize metrics storage
        self.metrics_history: List[DetailedTrainingMetrics] = []
        self.alerts: List[Dict[str, Any]] = []
        
        # Initialize metrics collector
        self.metrics_collector = MetricsCollector()
        
        # Training metadata
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
        # Analytics configuration
        analytics_config = config.get("model", {}).get("training", {}).get("analytics", {})
        self.export_csv = analytics_config.get("export_csv", True)
        self.export_json = analytics_config.get("export_json", True)
        self.export_alerts = analytics_config.get("export_alerts", True)
        
        logger.info(f"Training analyzer initialized for run: {run_id}")
        
    def collect_epoch_metrics(
        self,
        epoch: int,
        model: nn.Module,
        train_metrics: Dict[str, float],
        val_metrics: Dict[str, float],
        optimizer: torch.optim.Optimizer,
        y_pred: torch.Tensor,
        y_true: torch.Tensor,
        model_outputs: torch.Tensor,
        batch_count: int = 0,
        total_samples: int = 0,
        early_stopping_triggered: bool = False
    ) -> DetailedTrainingMetrics:
        """Collect comprehensive metrics for one epoch.
        
        Args:
            epoch: Current epoch number
            model: PyTorch model
            train_metrics: Training metrics dict (loss, accuracy)
            val_metrics: Validation metrics dict (loss, accuracy)
            optimizer: PyTorch optimizer
            y_pred: Predicted labels tensor
            y_true: True labels tensor
            model_outputs: Raw model outputs (for confidence analysis)
            batch_count: Number of batches processed
            total_samples: Total samples processed
            early_stopping_triggered: Whether early stopping was triggered
            
        Returns:
            DetailedTrainingMetrics object with all collected data
        """
        try:
            epoch_start_time = time.time()
            
            # Collect gradient metrics
            gradient_metrics = self.metrics_collector.collect_gradient_metrics(model)
            
            # Collect parameter metrics
            param_metrics = self.metrics_collector.collect_parameter_metrics(model)
            
            # Collect class-wise metrics
            class_metrics = self.metrics_collector.collect_class_metrics(y_true, y_pred)
            
            # Collect prediction confidence metrics
            prediction_metrics = self.metrics_collector.collect_prediction_metrics(model_outputs)
            
            # Create detailed metrics object
            detailed_metrics = DetailedTrainingMetrics(
                epoch=epoch,
                train_loss=train_metrics.get('loss', 0.0),
                train_accuracy=train_metrics.get('accuracy', 0.0),
                val_loss=val_metrics.get('loss'),
                val_accuracy=val_metrics.get('accuracy'),
                learning_rate=optimizer.param_groups[0]['lr'],
                duration=time.time() - epoch_start_time,
                
                # Gradient metrics
                gradient_norm_avg=gradient_metrics['average_norm'],
                gradient_norm_max=gradient_metrics['maximum_norm'],
                gradient_norms_by_layer=gradient_metrics['layer_norms'],
                
                # Parameter metrics
                param_change_magnitude=param_metrics['total_change_magnitude'],
                param_stats_by_layer=param_metrics['param_stats_by_layer'],
                
                # Class metrics
                class_precisions=class_metrics['class_precisions'],
                class_recalls=class_metrics['class_recalls'],
                class_f1_scores=class_metrics['class_f1_scores'],
                class_supports=class_metrics['class_supports'],
                
                # Prediction metrics
                prediction_confidence_avg=prediction_metrics['mean_confidence'],
                prediction_entropy=prediction_metrics['prediction_entropy'],
                high_confidence_predictions=prediction_metrics['high_confidence_predictions'],
                confidence_distribution=prediction_metrics['confidence_distribution'],
                
                # Training process metrics
                batch_count=batch_count,
                total_samples_processed=total_samples,
                early_stopping_triggered=early_stopping_triggered
            )
            
            # Calculate learning indicators
            previous_metrics = self.metrics_history[-1] if self.metrics_history else None
            learning_indicators = self.metrics_collector.calculate_learning_indicators(
                detailed_metrics, previous_metrics
            )
            
            # Update learning indicators
            detailed_metrics.learning_signal_strength = learning_indicators['learning_signal_strength']
            detailed_metrics.overfitting_score = learning_indicators['overfitting_score']
            detailed_metrics.class_balance_score = learning_indicators['class_balance_score']
            detailed_metrics.convergence_indicator = learning_indicators['convergence_indicator']
            
            # Store metrics
            self.metrics_history.append(detailed_metrics)
            
            # Check for alerts
            alerts = self.check_alerts(detailed_metrics)
            self.alerts.extend(alerts)
            
            logger.debug(f"Collected metrics for epoch {epoch}: {detailed_metrics.learning_signal_strength} signal")
            
            return detailed_metrics
            
        except Exception as e:
            logger.error(f"Failed to collect epoch metrics for epoch {epoch}: {e}")
            # Return minimal metrics to keep training going
            basic_metrics = DetailedTrainingMetrics(
                epoch=epoch,
                train_loss=train_metrics.get('loss', 0.0),
                train_accuracy=train_metrics.get('accuracy', 0.0),
                val_loss=val_metrics.get('loss'),
                val_accuracy=val_metrics.get('accuracy'),
                learning_rate=optimizer.param_groups[0]['lr'] if optimizer.param_groups else 0.001
            )
            self.metrics_history.append(basic_metrics)
            return basic_metrics
    
    def check_alerts(self, metrics: DetailedTrainingMetrics) -> List[Dict[str, Any]]:
        """Check for training issues and generate alerts.
        
        Args:
            metrics: Current epoch metrics
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        try:
            # Vanishing gradients
            if metrics.gradient_norm_avg < 0.01 and metrics.epoch > 5:
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'warning',
                    'category': 'gradient_flow',
                    'message': '⚠️ Vanishing gradients detected - learning may have stopped',
                    'details': {
                        'gradient_norm': metrics.gradient_norm_avg,
                        'threshold': 0.01
                    }
                })
            
            # Exploding gradients
            if metrics.gradient_norm_max > 10.0:
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'critical',
                    'category': 'gradient_flow',
                    'message': '🚨 Exploding gradients - reduce learning rate immediately',
                    'details': {
                        'max_gradient_norm': metrics.gradient_norm_max,
                        'threshold': 10.0
                    }
                })
            
            # Severe overfitting
            if metrics.overfitting_score > 0.7:
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'critical',
                    'category': 'overfitting',
                    'message': '🚨 Severe overfitting detected - validation much worse than training',
                    'details': {
                        'overfitting_score': metrics.overfitting_score,
                        'train_loss': metrics.train_loss,
                        'val_loss': metrics.val_loss
                    }
                })
            
            # Weak learning signal
            if metrics.learning_signal_strength == "weak" and metrics.epoch > 3:
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'warning',
                    'category': 'learning_dynamics',
                    'message': '📉 Weak learning signal - consider reducing learning rate',
                    'details': {
                        'signal_strength': metrics.learning_signal_strength,
                        'gradient_norm': metrics.gradient_norm_avg,
                        'param_change': metrics.param_change_magnitude
                    }
                })
            
            # Class imbalance
            if metrics.class_balance_score < 0.5:
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'warning',
                    'category': 'data_quality',
                    'message': '⚖️ Severe class imbalance affecting learning',
                    'details': {
                        'balance_score': metrics.class_balance_score,
                        'class_supports': metrics.class_supports
                    }
                })
            
            # Poor convergence
            if (metrics.val_accuracy is not None and 
                metrics.val_accuracy < 0.4 and 
                metrics.epoch > 10):
                alerts.append({
                    'epoch': metrics.epoch,
                    'severity': 'warning',
                    'category': 'performance',
                    'message': '📊 Poor accuracy after 10 epochs - check architecture or features',
                    'details': {
                        'val_accuracy': metrics.val_accuracy,
                        'epoch': metrics.epoch,
                        'threshold': 0.4
                    }
                })
            
        except Exception as e:
            logger.warning(f"Failed to check alerts for epoch {metrics.epoch}: {e}")
        
        return alerts
    
    def finalize_training(self, final_epoch: int, stopping_reason: str = "completed"):
        """Finalize training and prepare for export.
        
        Args:
            final_epoch: Final epoch number
            stopping_reason: Reason training stopped
        """
        self.end_time = datetime.now()
        
        # Add final analysis
        self.final_analysis = {
            'total_epochs_completed': final_epoch,
            'stopping_reason': stopping_reason,
            'training_duration_minutes': (self.end_time - self.start_time).total_seconds() / 60,
            'best_val_accuracy': max((m.val_accuracy for m in self.metrics_history if m.val_accuracy), default=0.0),
            'best_epoch': max(enumerate(self.metrics_history), 
                            key=lambda x: x[1].val_accuracy if x[1].val_accuracy else 0.0)[0] + 1 if self.metrics_history else 0,
            'final_gradient_norm': self.metrics_history[-1].gradient_norm_avg if self.metrics_history else 0.0,
            'alert_count': len(self.alerts)
        }
        
        logger.info(f"Training finalized: {final_epoch} epochs, reason: {stopping_reason}")
    
    def export_csv(self) -> Path:
        """Export LLM-friendly CSV file.
        
        Returns:
            Path to exported CSV file
        """
        if not self.export_csv or not self.metrics_history:
            return None
        
        try:
            csv_path = self.output_dir / "metrics.csv"
            
            # Convert metrics to CSV rows
            csv_data = [metrics.to_csv_row() for metrics in self.metrics_history]
            
            # Create DataFrame and export
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_path, index=False)
            
            logger.info(f"CSV metrics exported to: {csv_path}")
            return csv_path
            
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return None
    
    def export_json(self) -> Path:
        """Export detailed JSON file.
        
        Returns:
            Path to exported JSON file
        """
        if not self.export_json:
            return None
        
        try:
            json_path = self.output_dir / "detailed_metrics.json"
            
            # Prepare JSON data
            json_data = {
                'run_metadata': {
                    'run_id': self.run_id,
                    'start_time': self.start_time.isoformat(),
                    'end_time': self.end_time.isoformat() if self.end_time else None,
                    'total_epochs': len(self.metrics_history)
                },
                'training_config': self.config,
                'epoch_metrics': [metrics.to_json_dict() for metrics in self.metrics_history],
                'alerts': self.alerts,
                'final_analysis': getattr(self, 'final_analysis', {})
            }
            
            # Export JSON
            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            logger.info(f"JSON metrics exported to: {json_path}")
            return json_path
            
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return None
    
    def export_alerts(self) -> Path:
        """Export human-readable alerts file.
        
        Returns:
            Path to exported alerts file
        """
        if not self.export_alerts:
            return None
        
        try:
            alerts_path = self.output_dir / "alerts.txt"
            
            with open(alerts_path, 'w') as f:
                f.write(f"Training Alerts for Run: {self.run_id}\n")
                f.write("=" * 50 + "\n\n")
                
                if not self.alerts:
                    f.write("No alerts generated during training.\n")
                else:
                    for alert in self.alerts:
                        f.write(f"Epoch {alert['epoch']} [{alert['severity'].upper()}]: {alert['message']}\n")
                        if alert.get('details'):
                            for key, value in alert['details'].items():
                                f.write(f"  {key}: {value}\n")
                        f.write("\n")
                
                # Summary
                f.write("\nSummary:\n")
                f.write(f"Total alerts: {len(self.alerts)}\n")
                critical_alerts = [a for a in self.alerts if a['severity'] == 'critical']
                warning_alerts = [a for a in self.alerts if a['severity'] == 'warning']
                f.write(f"Critical: {len(critical_alerts)}, Warnings: {len(warning_alerts)}\n")
            
            logger.info(f"Alerts exported to: {alerts_path}")
            return alerts_path
            
        except Exception as e:
            logger.error(f"Failed to export alerts: {e}")
            return None
    
    def export_config(self) -> Path:
        """Export training configuration for reproducibility.
        
        Returns:
            Path to exported config file
        """
        try:
            config_path = self.output_dir / "config.yaml"
            
            with open(config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Config exported to: {config_path}")
            return config_path
            
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return None
    
    def export_all(self) -> Dict[str, Optional[Path]]:
        """Export all analytics files.
        
        Returns:
            Dictionary mapping file type to export path
        """
        export_paths = {}
        
        export_paths['csv'] = self.export_csv()
        export_paths['json'] = self.export_json()
        export_paths['alerts'] = self.export_alerts()
        export_paths['config'] = self.export_config()
        
        # Log summary
        successful_exports = [k for k, v in export_paths.items() if v is not None]
        logger.info(f"Analytics export completed: {successful_exports}")
        
        return export_paths