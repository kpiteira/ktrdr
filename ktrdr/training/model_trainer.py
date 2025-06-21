"""Model training with PyTorch for neuro-fuzzy strategies."""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
import time
from pathlib import Path
import json


@dataclass
class TrainingMetrics:
    """Container for training metrics."""

    epoch: int
    train_loss: float
    train_accuracy: float
    val_loss: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    duration: float = 0.0


class EarlyStopping:
    """Early stopping callback to prevent overfitting."""

    def __init__(
        self,
        patience: int = 10,
        min_delta: float = 0.0001,
        monitor: str = "val_loss",
        mode: str = "min",
    ):
        """Initialize early stopping.

        Args:
            patience: Number of epochs with no improvement to wait
            min_delta: Minimum change to consider as improvement
            monitor: Metric to monitor
            mode: 'min' or 'max'
        """
        self.patience = patience
        self.min_delta = min_delta
        self.monitor = monitor
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.early_stop = False

    def __call__(self, metrics: TrainingMetrics) -> bool:
        """Check if training should stop.

        Args:
            metrics: Current training metrics

        Returns:
            True if should stop, False otherwise
        """
        if self.monitor == "val_loss":
            score = -metrics.val_loss if metrics.val_loss else None
        elif self.monitor == "val_accuracy":
            score = metrics.val_accuracy
        else:
            score = None

        if score is None:
            return False

        if self.best_score is None:
            self.best_score = score
        elif score < self.best_score + self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = score
            self.counter = 0

        return self.early_stop


class ModelTrainer:
    """Handle PyTorch training loop with advanced features."""

    def __init__(self, config: Dict[str, Any], progress_callback=None):
        """Initialize trainer.

        Args:
            config: Training configuration
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.history: List[TrainingMetrics] = []
        self.best_model_state = None
        self.best_val_accuracy = 0.0
        self.progress_callback = progress_callback

    def train(
        self,
        model: nn.Module,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: Optional[torch.Tensor] = None,
        y_val: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Train the neural network model.

        Args:
            model: PyTorch model to train
            X_train: Training features
            y_train: Training labels
            X_val: Optional validation features
            y_val: Optional validation labels

        Returns:
            Training history and metrics
        """
        # Move model to device
        model = model.to(self.device)

        # Prepare data
        X_train = X_train.to(self.device)
        y_train = y_train.to(self.device)

        if X_val is not None:
            X_val = X_val.to(self.device)
            y_val = y_val.to(self.device)

        # Get training parameters
        learning_rate = self.config.get("learning_rate", 0.001)
        batch_size = self.config.get("batch_size", 32)
        epochs = self.config.get("epochs", 100)

        # Create data loaders
        train_dataset = TensorDataset(X_train, y_train)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        # Setup optimizer
        optimizer = self._create_optimizer(model, learning_rate)

        # Setup loss function
        criterion = nn.CrossEntropyLoss()

        # Setup learning rate scheduler
        scheduler = self._create_scheduler(optimizer)

        # Setup early stopping
        early_stopping_config = self.config.get("early_stopping", {})
        early_stopping = (
            EarlyStopping(
                patience=early_stopping_config.get("patience", 10),
                monitor=early_stopping_config.get("monitor", "val_loss"),
            )
            if early_stopping_config
            else None
        )

        # Calculate total batches and bars for progress tracking
        total_batches_per_epoch = len(train_loader)
        total_batches = epochs * total_batches_per_epoch
        total_bars = len(X_train)  # Total number of market data bars
        total_bars_all_epochs = total_bars * epochs  # Total bars across all epochs

        # Training loop
        for epoch in range(epochs):
            start_time = time.time()

            # Training phase
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for batch_idx, (batch_X, batch_y) in enumerate(train_loader):
                # DEBUG: Check for NaN in first batch of first epoch
                if epoch == 0 and batch_idx == 0:
                    print(f"🔍 DEBUG: First batch - X contains NaN: {torch.isnan(batch_X).any()}")
                    print(f"🔍 DEBUG: First batch - y contains NaN: {torch.isnan(batch_y).any()}")
                    print(f"🔍 DEBUG: First batch - X shape: {batch_X.shape}, y shape: {batch_y.shape}")
                    print(f"🔍 DEBUG: First batch - X min/max: {batch_X.min():.6f}/{batch_X.max():.6f}")
                    print(f"🔍 DEBUG: First batch - X contains inf: {torch.isinf(batch_X).any()}")
                    print(f"🔍 DEBUG: First batch - y unique values: {torch.unique(batch_y)}")
                
                # Forward pass
                outputs = model(batch_X)
                
                # DEBUG: Check outputs and loss
                if epoch == 0 and batch_idx == 0:
                    print(f"🔍 DEBUG: Model outputs contains NaN: {torch.isnan(outputs).any()}")
                    print(f"🔍 DEBUG: Model outputs min/max: {outputs.min():.6f}/{outputs.max():.6f}")
                
                loss = criterion(outputs, batch_y)
                
                # DEBUG: Check loss immediately after calculation
                if epoch == 0 and batch_idx == 0:
                    print(f"🔍 DEBUG: Loss value: {loss.item():.6f}")
                    print(f"🔍 DEBUG: Loss is NaN: {torch.isnan(loss)}")
                    if torch.isnan(loss):
                        print("🚨 ERROR: NaN loss detected on first batch!")
                        # Check model parameters
                        nan_params = 0
                        total_params = 0
                        for name, param in model.named_parameters():
                            if torch.isnan(param).any():
                                nan_params += torch.isnan(param).sum().item()
                                print(f"  Parameter '{name}' has NaN values")
                            total_params += param.numel()
                        print(f"  Model has {nan_params}/{total_params} NaN parameters")
                        return {"error": "NaN loss detected on first batch"}

                # Backward pass
                optimizer.zero_grad()
                loss.backward()

                # Gradient clipping
                if self.config.get("gradient_clip", 0) > 0:
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), self.config["gradient_clip"]
                    )

                optimizer.step()

                # Track metrics
                train_loss += loss.item() * batch_X.size(0)
                _, predicted = torch.max(outputs.data, 1)
                train_total += batch_y.size(0)
                train_correct += (predicted == batch_y).sum().item()
                
                # Batch-level progress callback (every 10 batches to avoid spam)
                if self.progress_callback and batch_idx % 10 == 0:
                    try:
                        completed_batches = epoch * total_batches_per_epoch + batch_idx
                        current_train_loss = train_loss / max(train_total, 1)
                        current_train_acc = train_correct / max(train_total, 1)
                        
                        # Calculate bars processed (market data points)
                        bars_processed_this_epoch = batch_idx * batch_size
                        total_bars_processed = epoch * total_bars + bars_processed_this_epoch
                        
                        # Create batch-level metrics
                        batch_metrics = {
                            'epoch': epoch,
                            'total_epochs': epochs,
                            'batch': batch_idx,
                            'total_batches_per_epoch': total_batches_per_epoch,
                            'completed_batches': completed_batches,
                            'total_batches': total_batches,
                            'bars_processed_this_epoch': bars_processed_this_epoch,
                            'total_bars_processed': total_bars_processed,
                            'total_bars': total_bars,
                            'total_bars_all_epochs': total_bars_all_epochs,
                            'train_loss': current_train_loss,
                            'train_accuracy': current_train_acc,
                            'progress_type': 'batch'
                        }
                        
                        self.progress_callback(epoch, epochs, batch_metrics)
                    except Exception as e:
                        print(f"Warning: Batch progress callback failed: {e}")

            # Calculate training metrics
            avg_train_loss = train_loss / train_total
            train_accuracy = train_correct / train_total

            # Validation phase
            val_loss = None
            val_accuracy = None

            if X_val is not None:
                model.eval()
                with torch.no_grad():
                    val_outputs = model(X_val)
                    val_loss = criterion(val_outputs, y_val)
                    _, val_predicted = torch.max(val_outputs.data, 1)
                    val_accuracy = (val_predicted == y_val).float().mean().item()
                    val_loss = val_loss.item()

                # Save best model
                if val_accuracy > self.best_val_accuracy:
                    self.best_val_accuracy = val_accuracy
                    self.best_model_state = model.state_dict().copy()

            # Record metrics
            duration = time.time() - start_time
            metrics = TrainingMetrics(
                epoch=epoch,
                train_loss=avg_train_loss,
                train_accuracy=train_accuracy,
                val_loss=val_loss,
                val_accuracy=val_accuracy,
                learning_rate=optimizer.param_groups[0]["lr"],
                duration=duration,
            )
            self.history.append(metrics)

            # Learning rate scheduling
            if scheduler is not None:
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss if val_loss else avg_train_loss)
                else:
                    scheduler.step()

            # Early stopping check
            if early_stopping and early_stopping(metrics):
                print(f"Early stopping triggered at epoch {epoch}")
                break

            # Progress logging
            if epoch % 10 == 0 or epoch == epochs - 1:
                self._log_progress(metrics)
            
            # Progress callback for external monitoring (e.g., API progress updates)
            if self.progress_callback:
                try:
                    # Epoch-level metrics (complete epoch with validation)
                    epoch_metrics = {
                        'epoch': epoch,
                        'total_epochs': epochs,
                        'total_batches_per_epoch': total_batches_per_epoch,
                        'completed_batches': (epoch + 1) * total_batches_per_epoch,
                        'total_batches': total_batches,
                        'total_bars_processed': (epoch + 1) * total_bars,  # All bars in completed epochs
                        'total_bars': total_bars,
                        'total_bars_all_epochs': total_bars_all_epochs,
                        'train_loss': avg_train_loss,
                        'train_accuracy': train_accuracy,
                        'val_loss': val_loss,
                        'val_accuracy': val_accuracy,
                        'progress_type': 'epoch'
                    }
                    self.progress_callback(epoch, epochs, epoch_metrics)
                except Exception as e:
                    print(f"Warning: Progress callback failed: {e}")

        # Restore best model if available
        if self.best_model_state is not None:
            model.load_state_dict(self.best_model_state)

        return self._create_training_summary()

    def _create_optimizer(
        self, model: nn.Module, learning_rate: float
    ) -> optim.Optimizer:
        """Create optimizer based on configuration.

        Args:
            model: PyTorch model
            learning_rate: Learning rate

        Returns:
            Optimizer instance
        """
        optimizer_name = self.config.get("optimizer", "adam").lower()

        if optimizer_name == "adam":
            return optim.Adam(
                model.parameters(),
                lr=learning_rate,
                weight_decay=self.config.get("weight_decay", 0.0001),
            )
        elif optimizer_name == "sgd":
            return optim.SGD(
                model.parameters(),
                lr=learning_rate,
                momentum=self.config.get("momentum", 0.9),
                weight_decay=self.config.get("weight_decay", 0.0001),
            )
        elif optimizer_name == "rmsprop":
            return optim.RMSprop(
                model.parameters(),
                lr=learning_rate,
                weight_decay=self.config.get("weight_decay", 0.0001),
            )
        else:
            return optim.Adam(model.parameters(), lr=learning_rate)

    def _create_scheduler(self, optimizer: optim.Optimizer) -> Optional[object]:
        """Create learning rate scheduler.

        Args:
            optimizer: PyTorch optimizer

        Returns:
            Scheduler instance or None
        """
        scheduler_config = self.config.get("lr_scheduler", None)
        if not scheduler_config:
            return None

        scheduler_type = scheduler_config.get("type", "step").lower()

        if scheduler_type == "step":
            return optim.lr_scheduler.StepLR(
                optimizer,
                step_size=scheduler_config.get("step_size", 30),
                gamma=scheduler_config.get("gamma", 0.1),
            )
        elif scheduler_type == "exponential":
            return optim.lr_scheduler.ExponentialLR(
                optimizer, gamma=scheduler_config.get("gamma", 0.95)
            )
        elif scheduler_type == "reduce_on_plateau":
            return optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode="min",
                factor=scheduler_config.get("factor", 0.5),
                patience=scheduler_config.get("patience", 5),
            )

        return None

    def _log_progress(self, metrics: TrainingMetrics):
        """Log training progress.

        Args:
            metrics: Current training metrics
        """
        msg = f"Epoch {metrics.epoch}: "
        msg += f"Train Loss: {metrics.train_loss:.4f}, "
        msg += f"Train Acc: {metrics.train_accuracy:.4f}"

        if metrics.val_loss is not None:
            msg += f", Val Loss: {metrics.val_loss:.4f}"
        if metrics.val_accuracy is not None:
            msg += f", Val Acc: {metrics.val_accuracy:.4f}"

        msg += f" (LR: {metrics.learning_rate:.6f}, Time: {metrics.duration:.2f}s)"
        print(msg)

    def _create_training_summary(self) -> Dict[str, Any]:
        """Create summary of training results.

        Returns:
            Dictionary with training summary
        """
        if not self.history:
            return {"error": "No training history available"}

        # Extract metrics arrays
        train_losses = [m.train_loss for m in self.history]
        train_accuracies = [m.train_accuracy for m in self.history]
        val_losses = [m.val_loss for m in self.history if m.val_loss is not None]
        val_accuracies = [
            m.val_accuracy for m in self.history if m.val_accuracy is not None
        ]

        summary = {
            "epochs_trained": len(self.history),
            "final_train_loss": train_losses[-1],
            "final_train_accuracy": train_accuracies[-1],
            "best_train_accuracy": max(train_accuracies),
            "training_time": sum(m.duration for m in self.history),
            "history": {"train_loss": train_losses, "train_accuracy": train_accuracies},
        }

        if val_losses:
            summary.update(
                {
                    "final_val_loss": val_losses[-1],
                    "final_val_accuracy": val_accuracies[-1],
                    "best_val_accuracy": self.best_val_accuracy,
                    "history": {
                        **summary["history"],
                        "val_loss": val_losses,
                        "val_accuracy": val_accuracies,
                    },
                }
            )

        return summary

    def save_training_history(self, path: Path):
        """Save training history to file.

        Args:
            path: Path to save history
        """
        history_data = {
            "config": self.config,
            "metrics": [
                {
                    "epoch": m.epoch,
                    "train_loss": m.train_loss,
                    "train_accuracy": m.train_accuracy,
                    "val_loss": m.val_loss,
                    "val_accuracy": m.val_accuracy,
                    "learning_rate": m.learning_rate,
                    "duration": m.duration,
                }
                for m in self.history
            ],
            "best_val_accuracy": self.best_val_accuracy,
        }

        with open(path, "w") as f:
            json.dump(history_data, f, indent=2)
