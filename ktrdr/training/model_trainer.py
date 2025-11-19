"""Model training with PyTorch for neuro-fuzzy strategies."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from ktrdr.async_infrastructure.cancellation import (
    CancellationError,
    CancellationToken,
)

from .analytics import TrainingAnalyzer
from .device_manager import DeviceManager
from .multi_symbol_data_loader import MultiSymbolDataLoader


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
        self.best_score: Optional[float] = None
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
            self.best_score = float(score)
        elif score < self.best_score + self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = float(score)
            self.counter = 0

        return self.early_stop


class ModelTrainer:
    """Handle PyTorch training loop with advanced features."""

    def __init__(
        self,
        config: dict[str, Any],
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
        checkpoint_service=None,
        checkpoint_policy=None,
        operation_id: Optional[str] = None,
    ):
        """Initialize trainer.

        Args:
            config: Training configuration
            progress_callback: Optional callback for progress updates
            cancellation_token: Optional cancellation token for training interruption
            checkpoint_service: Optional CheckpointService for checkpointing
            checkpoint_policy: Optional CheckpointPolicy for checkpoint decisions
            operation_id: Optional operation ID for checkpoint tracking
        """
        self.config = config
        self.cancellation_token = cancellation_token
        # GPU device selection with Apple Silicon support via DeviceManager
        self.device = DeviceManager.get_torch_device()
        device_info = DeviceManager.get_device_info()
        print(f"🚀 Using {device_info['device_name']} for training")
        self.history: list[TrainingMetrics] = []
        self.best_model_state: Optional[dict[str, Any]] = None
        self.best_val_accuracy = 0.0
        self.progress_callback = progress_callback

        # Progress update frequency: update every N batches
        # Default to 1 (every batch) for responsive UI, can be increased for performance
        self.progress_update_frequency = config.get("progress_update_frequency", 1)

        # Checkpoint support (optional)
        self.checkpoint_service = checkpoint_service
        self.checkpoint_policy = checkpoint_policy
        self.operation_id = operation_id
        self.last_checkpoint_time: Optional[float] = None

        # Analytics setup - check both direct config and full_config
        full_config = config.get("full_config", config)
        self.analytics_enabled = (
            full_config.get("model", {})
            .get("training", {})
            .get("analytics", {})
            .get("enabled", False)
        )
        self.analyzer: Optional[TrainingAnalyzer] = None
        if self.analytics_enabled:
            self._setup_analytics(full_config)

    def _check_cancelled(self) -> None:
        if self.cancellation_token and self.cancellation_token.is_cancelled():
            raise CancellationError("Training cancelled by user request")

    def _setup_analytics(self, full_config):
        """Setup analytics system for detailed training monitoring."""
        try:
            # Generate unique run ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            symbol = full_config.get("symbol", "unknown")
            strategy = full_config.get("name", "unknown")
            run_id = f"{symbol}_{strategy}_{timestamp}"

            # Create analytics directory
            analytics_dir = Path("training_analytics/runs") / run_id

            # Initialize analyzer
            self.analyzer = TrainingAnalyzer(run_id, analytics_dir, full_config)
            print(f"🔍 Analytics enabled - Run ID: {run_id}")

        except Exception as e:
            print(f"⚠️ Failed to setup analytics: {e}")
            self.analytics_enabled = False
            self.analyzer = None

    def train(
        self,
        model: nn.Module,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: Optional[torch.Tensor] = None,
        y_val: Optional[torch.Tensor] = None,
        start_epoch: int = 0,
    ) -> dict[str, Any]:
        """Train the neural network model.

        Args:
            model: PyTorch model to train
            X_train: Training features
            y_train: Training labels
            X_val: Optional validation features
            y_val: Optional validation labels
            start_epoch: Starting epoch for training (default: 0, for resuming: checkpoint_epoch + 1)

        Returns:
            Training history and metrics
        """
        # Move model to device
        model = model.to(self.device)

        # Get training parameters
        learning_rate = self.config.get("learning_rate", 0.001)
        batch_size = self.config.get("batch_size", 32)
        epochs = self.config.get("epochs", 100)

        # PERFORMANCE FIX: For GPU training with large datasets, keep data on CPU and use
        # pin_memory + prefetching for efficient async transfer. Moving entire dataset to GPU
        # upfront causes DataLoader shuffle overhead and wastes GPU memory.
        # With 885k samples, batch_size=32 = 27k batches/epoch. Optimized data loading saves ~15s/epoch.

        # Detect if using GPU (CUDA or MPS)
        is_gpu = self.device.type in ("cuda", "mps")

        # Keep training data on CPU for efficient DataLoader operation
        # It will be transferred to GPU batch-by-batch during training
        if is_gpu:
            # Ensure data is on CPU for DataLoader
            X_train_cpu = (
                X_train.cpu()
                if X_train.is_cuda or X_train.device.type == "mps"
                else X_train
            )
            y_train_cpu = (
                y_train.cpu()
                if y_train.is_cuda or y_train.device.type == "mps"
                else y_train
            )
        else:
            X_train_cpu = X_train
            y_train_cpu = y_train

        # Create optimized data loader with pinned memory for GPU transfer
        train_dataset = TensorDataset(X_train_cpu, y_train_cpu)
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            pin_memory=is_gpu,  # Enable pinned memory for async GPU transfer
            num_workers=0,  # Keep 0 for now (tensors already in memory, workers add overhead)
        )

        # Move validation data to GPU (smaller, benefits from staying on GPU)
        if X_val is not None:
            X_val = X_val.to(self.device)
            if y_val is not None:
                y_val = y_val.to(self.device)

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

        # Training loop (support resuming from start_epoch)
        for epoch in range(start_epoch, epochs):
            self._check_cancelled()
            start_time = time.time()

            # Training phase
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for batch_idx, (batch_X, batch_y) in enumerate(train_loader):
                self._check_cancelled()

                # Move batch to device (DataLoader with pin_memory provides efficient transfer)
                # Using non_blocking=True for async transfer to overlap with computation
                if is_gpu:
                    batch_X = batch_X.to(self.device, non_blocking=True)
                    batch_y = batch_y.to(self.device, non_blocking=True)
                # else: already on CPU, no transfer needed

                # DEBUG: Check for NaN in first batch of first epoch
                if epoch == 0 and batch_idx == 0:
                    print(
                        f"🔍 DEBUG: First batch - X contains NaN: {torch.isnan(batch_X).any()}"
                    )
                    print(
                        f"🔍 DEBUG: First batch - y contains NaN: {torch.isnan(batch_y).any()}"
                    )
                    print(
                        f"🔍 DEBUG: First batch - X shape: {batch_X.shape}, y shape: {batch_y.shape}"
                    )
                    print(
                        f"🔍 DEBUG: First batch - X min/max: {batch_X.min():.6f}/{batch_X.max():.6f}"
                    )
                    print(
                        f"🔍 DEBUG: First batch - X contains inf: {torch.isinf(batch_X).any()}"
                    )
                    print(
                        f"🔍 DEBUG: First batch - y unique values: {torch.unique(batch_y)}"
                    )

                # Forward pass
                outputs = model(batch_X)

                # DEBUG: Check outputs and loss
                if epoch == 0 and batch_idx == 0:
                    print(
                        f"🔍 DEBUG: Model outputs contains NaN: {torch.isnan(outputs).any()}"
                    )
                    print(
                        f"🔍 DEBUG: Model outputs min/max: {outputs.min():.6f}/{outputs.max():.6f}"
                    )

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
                                nan_params += int(torch.isnan(param).sum().item())
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

                # Batch-level progress callback (configurable frequency)
                if (
                    self.progress_callback
                    and batch_idx % self.progress_update_frequency == 0
                ):
                    try:
                        self._check_cancelled()
                        completed_batches = epoch * total_batches_per_epoch + batch_idx
                        current_train_loss = train_loss / max(train_total, 1)
                        current_train_acc = train_correct / max(train_total, 1)

                        # Calculate bars processed (market data points)
                        bars_processed_this_epoch = batch_idx * batch_size
                        total_bars_processed = (
                            epoch * total_bars + bars_processed_this_epoch
                        )

                        # Calculate progress percentage (source of truth)
                        progress_percent = (
                            (completed_batches / total_batches) * 100.0
                            if total_batches > 0
                            else 0.0
                        )
                        progress_percent = max(0.0, min(progress_percent, 100.0))

                        # Create batch-level metrics
                        batch_metrics = {
                            "epoch": epoch,
                            "total_epochs": epochs,
                            "batch": batch_idx,
                            "total_batches_per_epoch": total_batches_per_epoch,
                            "completed_batches": completed_batches,
                            "total_batches": total_batches,
                            "progress_percent": progress_percent,
                            "bars_processed_this_epoch": bars_processed_this_epoch,
                            "total_bars_processed": total_bars_processed,
                            "total_bars": total_bars,
                            "total_bars_all_epochs": total_bars_all_epochs,
                            "train_loss": current_train_loss,
                            "train_accuracy": current_train_acc,
                            "progress_type": "batch",
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
                    if y_val is not None:
                        val_accuracy = (val_predicted == y_val).float().mean().item()
                    else:
                        val_accuracy = 0.0
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

            # Analytics collection (if enabled)
            if self.analyzer:
                try:
                    # Determine which outputs and labels to use for analytics
                    if X_val is not None:
                        # Use validation data for more reliable metrics
                        analytics_outputs = val_outputs
                        analytics_predicted = val_predicted
                        analytics_true = y_val
                    else:
                        # Fallback to training data if no validation
                        with torch.no_grad():
                            model.eval()
                            analytics_outputs = model(
                                X_train[:1000]
                            )  # Sample for efficiency
                            _, analytics_predicted = torch.max(
                                analytics_outputs.data, 1
                            )
                            analytics_true = y_train[:1000]
                            model.train()

                    # Collect detailed analytics (only if we have valid data)
                    if analytics_true is not None:
                        self.analyzer.collect_epoch_metrics(
                            epoch=epoch,
                            model=model,
                            train_metrics={
                                "loss": (
                                    float(avg_train_loss)
                                    if avg_train_loss is not None
                                    else 0.0
                                ),
                                "accuracy": (
                                    float(train_accuracy)
                                    if train_accuracy is not None
                                    else 0.0
                                ),
                            },
                            val_metrics={
                                "loss": (
                                    float(val_loss) if val_loss is not None else 0.0
                                ),
                                "accuracy": (
                                    float(val_accuracy)
                                    if val_accuracy is not None
                                    else 0.0
                                ),
                            },
                            optimizer=optimizer,
                            y_pred=analytics_predicted,
                            y_true=analytics_true,
                            model_outputs=analytics_outputs,
                            batch_count=len(train_loader),
                            total_samples=len(X_train),
                            early_stopping_triggered=False,  # Will be updated if early stopping triggers
                        )

                    # Log any alerts
                    if hasattr(self.analyzer, "alerts") and self.analyzer.alerts:
                        recent_alerts = [
                            a for a in self.analyzer.alerts if a.get("epoch") == epoch
                        ]
                        for alert in recent_alerts:
                            print(f"🚨 Training Alert: {alert['message']}")

                except Exception as e:
                    print(f"⚠️ Analytics collection failed for epoch {epoch}: {e}")
                    # Continue training even if analytics fail

            # Learning rate scheduling
            if scheduler is not None and hasattr(scheduler, "step"):
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss if val_loss else avg_train_loss)
                else:
                    scheduler.step()  # type: ignore[attr-defined]

            # Early stopping check
            if early_stopping and early_stopping(metrics):
                print(f"Early stopping triggered at epoch {epoch}")
                # Update analytics with early stopping info
                if self.analyzer and self.analyzer.metrics_history:
                    self.analyzer.metrics_history[-1].early_stopping_triggered = True
                break

            # Progress logging
            if epoch % 10 == 0 or epoch == epochs - 1:
                self._log_progress(metrics)

            # Progress callback for external monitoring (e.g., API progress updates)
            if self.progress_callback:
                try:
                    self._check_cancelled()

                    # Calculate progress percentage (source of truth)
                    completed_batches_at_epoch_end = (
                        epoch + 1
                    ) * total_batches_per_epoch
                    progress_percent = (
                        (completed_batches_at_epoch_end / total_batches) * 100.0
                        if total_batches > 0
                        else 0.0
                    )
                    progress_percent = max(0.0, min(progress_percent, 100.0))

                    # Epoch-level metrics (complete epoch with validation)
                    # M2: Added learning_rate, duration, timestamp for metrics storage
                    epoch_metrics = {
                        "epoch": epoch,
                        "total_epochs": epochs,
                        "total_batches_per_epoch": total_batches_per_epoch,
                        "completed_batches": completed_batches_at_epoch_end,
                        "total_batches": total_batches,
                        "progress_percent": progress_percent,
                        "total_bars_processed": (epoch + 1)
                        * total_bars,  # All bars in completed epochs
                        "total_bars": total_bars,
                        "total_bars_all_epochs": total_bars_all_epochs,
                        "train_loss": avg_train_loss,
                        "train_accuracy": train_accuracy,
                        "val_loss": val_loss,
                        "val_accuracy": val_accuracy,
                        "learning_rate": optimizer.param_groups[0]["lr"],
                        "duration": duration,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "progress_type": "epoch",
                    }
                    self.progress_callback(epoch, epochs, epoch_metrics)
                except Exception as e:
                    print(f"Warning: Progress callback failed: {e}")

            # Checkpoint logic (if checkpointing enabled)
            if (
                self.checkpoint_service is not None
                and self.checkpoint_policy is not None
                and self.operation_id is not None
            ):
                try:
                    from ktrdr.checkpoint.policy import CheckpointDecisionEngine

                    # Initialize checkpoint time if first checkpoint check
                    if self.last_checkpoint_time is None:
                        self.last_checkpoint_time = time.time()

                    # Check if we should checkpoint
                    engine = CheckpointDecisionEngine()
                    should_checkpoint, reason = engine.should_checkpoint(
                        policy=self.checkpoint_policy,
                        last_checkpoint_time=self.last_checkpoint_time,
                        current_time=time.time(),
                        natural_boundary=epoch + 1,  # Epoch numbers are 0-indexed
                        total_boundaries=epoch + 1,
                    )

                    if should_checkpoint:
                        # Capture checkpoint state
                        checkpoint_state = self.get_checkpoint_state(
                            current_epoch=epoch,
                            model=model,
                            optimizer=optimizer,
                            scheduler=scheduler,
                            early_stopping=early_stopping,
                        )

                        # Prepare checkpoint data for CheckpointService
                        # Extract binary artifacts
                        artifacts: dict[str, bytes] = {
                            "model.pt": checkpoint_state["model_state_dict"],
                            "optimizer.pt": checkpoint_state["optimizer_state_dict"],
                        }

                        # Add scheduler artifact if exists
                        if checkpoint_state.get("scheduler_state_dict"):
                            artifacts["scheduler.pt"] = checkpoint_state[
                                "scheduler_state_dict"
                            ]

                        # Add best model artifact if exists
                        if checkpoint_state.get("best_model_state"):
                            artifacts["best_model.pt"] = checkpoint_state[
                                "best_model_state"
                            ]

                        # Create JSON-serializable state (without binary artifacts)
                        json_state = {
                            k: v
                            for k, v in checkpoint_state.items()
                            if k
                            not in [
                                "model_state_dict",
                                "optimizer_state_dict",
                                "scheduler_state_dict",
                                "best_model_state",
                            ]
                        }

                        checkpoint_data: dict[str, Any] = {
                            "checkpoint_id": f"{self.operation_id}_epoch_{epoch}",
                            "checkpoint_type": "epoch_snapshot",
                            "metadata": {
                                "epoch": epoch,
                                "train_loss": avg_train_loss,
                                "train_accuracy": train_accuracy,
                                "val_loss": val_loss,
                                "val_accuracy": val_accuracy,
                            },
                            "state": json_state,
                            "artifacts": artifacts,
                        }

                        # Save checkpoint via CheckpointService
                        self.checkpoint_service.save_checkpoint(
                            operation_id=self.operation_id,
                            checkpoint_data=checkpoint_data,
                        )

                        # Task 3.8: Write artifacts to shared filesystem for distributed access
                        # Backend and workers share data/checkpoints/ volume (Docker or NFS)
                        # Write artifacts to disk so backend can access during resume
                        artifact_paths = {}
                        try:
                            from pathlib import Path

                            artifacts_dir = (
                                Path("data/checkpoints/artifacts") / self.operation_id
                            )
                            artifacts_dir.mkdir(parents=True, exist_ok=True)

                            # Write each artifact to disk
                            for artifact_name, artifact_bytes in artifacts.items():
                                if artifact_bytes is not None:
                                    artifact_file = artifacts_dir / artifact_name
                                    artifact_file.write_bytes(artifact_bytes)
                                    # Store relative path (not absolute) for portability
                                    artifact_paths[artifact_name] = str(
                                        Path("data/checkpoints/artifacts")
                                        / self.operation_id
                                        / artifact_name
                                    )

                            print(
                                f"💾 Wrote {len(artifact_paths)} artifacts to {artifacts_dir}"
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to write artifacts to disk: {e}")
                            # Continue without artifact paths (graceful degradation)

                        # Task 3.7/3.8: Cache checkpoint state in progress bridge for cancellation checkpoints
                        # This enables OperationsService._get_operation_state() to retrieve full state
                        # (including artifacts) when creating cancellation checkpoints
                        # Task 3.8: Pass artifact PATHS (not bytes) for shared filesystem access
                        if hasattr(
                            self.progress_callback, "set_latest_checkpoint_state"
                        ):
                            self.progress_callback.set_latest_checkpoint_state(
                                checkpoint_data=json_state,
                                artifacts=artifact_paths,  # Task 3.8: Paths not bytes!
                            )

                        # Update last checkpoint time
                        self.last_checkpoint_time = time.time()

                        # Log checkpoint event
                        print(
                            f"💾 Checkpoint saved at epoch {epoch} (reason: {reason})"
                        )

                except Exception as e:
                    # Checkpoint failure should not stop training
                    print(f"⚠️ Checkpoint save failed (training continues): {e}")

        # Restore best model if available
        if self.best_model_state is not None:
            model.load_state_dict(self.best_model_state)

        # Finalize analytics and export results
        analytics_results = {}
        if self.analyzer:
            try:
                # Determine stopping reason
                final_epoch = len(self.history)
                stopping_reason = (
                    "early_stopping" if final_epoch < epochs else "completed"
                )

                # Finalize analytics
                self.analyzer.finalize_training(final_epoch, stopping_reason)

                # Export all analytics
                export_paths = self.analyzer.export_all()
                analytics_results = {
                    "analytics_enabled": True,
                    "run_id": self.analyzer.run_id,
                    "export_paths": {
                        k: str(v) if v else None for k, v in export_paths.items()
                    },
                    "total_alerts": len(self.analyzer.alerts),
                    "final_analysis": getattr(self.analyzer, "final_analysis", {}),
                }

                print(f"📊 Analytics exported to: {self.analyzer.output_dir}")
                if export_paths.get("csv"):
                    print(f"📈 CSV for LLM analysis: {export_paths['csv']}")

            except Exception as e:
                print(f"⚠️ Analytics finalization failed: {e}")
                analytics_results = {"analytics_enabled": True, "error": str(e)}

        return {**self._create_training_summary(), **analytics_results}

    def train_multi_symbol(
        self,
        model: nn.Module,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        symbol_indices_train: torch.Tensor,
        symbols: list[str],
        X_val: Optional[torch.Tensor] = None,
        y_val: Optional[torch.Tensor] = None,
        symbol_indices_val: Optional[torch.Tensor] = None,
    ) -> dict[str, Any]:
        """Train the multi-symbol neural network model with balanced sampling.

        DEPRECATED: This method is deprecated in favor of the symbol-agnostic design.
        Use train() instead, which handles both single and multi-symbol data uniformly.
        The symbol-agnostic approach concatenates all symbol data and trains on patterns
        in technical indicators, not symbol identities.

        Args:
            model: PyTorch model to train (must support symbol indices)
            X_train: Training features
            y_train: Training labels
            symbol_indices_train: Symbol indices for training data
            symbols: List of symbol names
            X_val: Optional validation features
            y_val: Optional validation labels
            symbol_indices_val: Optional symbol indices for validation data

        Returns:
            Training history and metrics
        """
        import warnings

        warnings.warn(
            "train_multi_symbol() is deprecated. Use train() instead for symbol-agnostic training.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Move model to device
        model = model.to(self.device)

        # Get training parameters
        learning_rate = self.config.get("learning_rate", 0.001)
        batch_size = self.config.get("batch_size", 32)
        epochs = self.config.get("epochs", 100)

        # PERFORMANCE FIX: Keep data on CPU for efficient DataLoader (same as train())
        is_gpu = self.device.type in ("cuda", "mps")

        if is_gpu:
            X_train_cpu = (
                X_train.cpu()
                if X_train.is_cuda or X_train.device.type == "mps"
                else X_train
            )
            y_train_cpu = (
                y_train.cpu()
                if y_train.is_cuda or y_train.device.type == "mps"
                else y_train
            )
            symbol_indices_cpu = (
                symbol_indices_train.cpu()
                if symbol_indices_train.is_cuda
                or symbol_indices_train.device.type == "mps"
                else symbol_indices_train
            )
        else:
            X_train_cpu = X_train
            y_train_cpu = y_train
            symbol_indices_cpu = symbol_indices_train

        # Create balanced multi-symbol data loader
        train_loader = MultiSymbolDataLoader.create_balanced_loader(
            features=X_train_cpu,
            labels=y_train_cpu,
            symbol_indices=symbol_indices_cpu,
            symbols=symbols,
            batch_size=batch_size,
            shuffle=True,
        )

        # Move validation data to GPU (smaller dataset)
        if X_val is not None:
            X_val = X_val.to(self.device)
            if y_val is not None:
                y_val = y_val.to(self.device)
            if symbol_indices_val is not None:
                symbol_indices_val = symbol_indices_val.to(self.device)

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

        # Calculate total batches for progress tracking
        total_batches_per_epoch = len(train_loader)
        total_batches = epochs * total_batches_per_epoch
        total_bars = len(X_train)
        total_bars * epochs

        # Training loop
        for epoch in range(epochs):
            self._check_cancelled()
            start_time = time.time()

            # Training phase
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for batch_idx, (batch_X, batch_y, batch_symbol_indices) in enumerate(
                train_loader
            ):
                self._check_cancelled()
                # Move batch to device with async transfer (same optimization as train())
                if is_gpu:
                    batch_X = batch_X.to(self.device, non_blocking=True)
                    batch_y = batch_y.to(self.device, non_blocking=True)
                    batch_symbol_indices = batch_symbol_indices.to(
                        self.device, non_blocking=True
                    )

                # DEBUG: Check for NaN in first batch of first epoch
                if epoch == 0 and batch_idx == 0:
                    print(
                        f"🔍 Multi-symbol DEBUG: First batch - X contains NaN: {torch.isnan(batch_X).any()}"
                    )
                    print(
                        f"🔍 Multi-symbol DEBUG: First batch - y contains NaN: {torch.isnan(batch_y).any()}"
                    )
                    print(
                        f"🔍 Multi-symbol DEBUG: First batch - symbol_indices: {batch_symbol_indices}"
                    )
                    print(
                        f"🔍 Multi-symbol DEBUG: First batch - X shape: {batch_X.shape}, y shape: {batch_y.shape}"
                    )

                # Forward pass with symbol indices
                if (
                    hasattr(model, "forward")
                    and "symbol_indices" in model.forward.__code__.co_varnames
                ):
                    outputs = model(batch_X, batch_symbol_indices)
                else:
                    # Fallback for models without symbol embedding support
                    outputs = model(batch_X)

                loss = criterion(outputs, batch_y)

                # DEBUG: Check loss
                if epoch == 0 and batch_idx == 0:
                    print(f"🔍 Multi-symbol DEBUG: Loss value: {loss.item():.6f}")
                    if torch.isnan(loss):
                        print("🚨 ERROR: NaN loss detected in multi-symbol training!")
                        return {"error": "NaN loss detected in multi-symbol training"}

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

                # Batch-level progress callback (configurable frequency)
                if (
                    self.progress_callback
                    and batch_idx % self.progress_update_frequency == 0
                ):
                    try:
                        self._check_cancelled()
                        completed_batches = epoch * total_batches_per_epoch + batch_idx
                        current_train_loss = train_loss / max(train_total, 1)
                        current_train_acc = train_correct / max(train_total, 1)

                        batch_metrics = {
                            "epoch": epoch,
                            "total_epochs": epochs,
                            "batch": batch_idx,
                            "total_batches_per_epoch": total_batches_per_epoch,
                            "completed_batches": completed_batches,
                            "total_batches": total_batches,
                            "train_loss": current_train_loss,
                            "train_accuracy": current_train_acc,
                            "progress_type": "batch",
                            "multi_symbol": True,
                        }

                        self.progress_callback(epoch, epochs, batch_metrics)
                    except Exception as e:
                        print(
                            f"Warning: Multi-symbol batch progress callback failed: {e}"
                        )

            # Calculate training metrics
            avg_train_loss = train_loss / train_total
            train_accuracy = train_correct / train_total

            # Validation phase
            val_loss = None
            val_accuracy = None

            if X_val is not None:
                model.eval()
                with torch.no_grad():
                    if (
                        hasattr(model, "forward")
                        and "symbol_indices" in model.forward.__code__.co_varnames
                    ):
                        val_outputs = model(X_val, symbol_indices_val)
                    else:
                        val_outputs = model(X_val)

                    val_loss = criterion(val_outputs, y_val)
                    _, val_predicted = torch.max(val_outputs.data, 1)
                    if y_val is not None:
                        val_accuracy = (val_predicted == y_val).float().mean().item()
                    else:
                        val_accuracy = 0.0
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

            # Update learning rate scheduler
            if scheduler is not None and hasattr(scheduler, "step"):
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss if val_loss is not None else avg_train_loss)
                else:
                    scheduler.step()  # type: ignore[attr-defined]

            # Check early stopping
            if early_stopping and early_stopping(metrics):
                print(f"Early stopping triggered at epoch {epoch}")
                break

            # Progress logging
            if epoch % 10 == 0 or epoch == epochs - 1:
                self._log_progress(metrics)

            # Progress callback for external monitoring
            if self.progress_callback:
                try:
                    self._check_cancelled()
                    epoch_metrics = {
                        "epoch": epoch,
                        "total_epochs": epochs,
                        "train_loss": avg_train_loss,
                        "train_accuracy": train_accuracy,
                        "val_loss": val_loss,
                        "val_accuracy": val_accuracy,
                        "progress_type": "epoch",
                        "multi_symbol": True,
                    }
                    self.progress_callback(epoch, epochs, epoch_metrics)
                except Exception as e:
                    print(f"Warning: Multi-symbol progress callback failed: {e}")

        # Restore best model if available
        if self.best_model_state is not None:
            model.load_state_dict(self.best_model_state)

        # Finalize analytics (reuse existing analytics system)
        analytics_results = {}
        if self.analyzer:
            try:
                final_epoch = len(self.history)
                stopping_reason = (
                    "early_stopping" if final_epoch < epochs else "completed"
                )
                self.analyzer.finalize_training(final_epoch, stopping_reason)
                export_paths = self.analyzer.export_all()
                analytics_results = {
                    "analytics_enabled": True,
                    "run_id": self.analyzer.run_id,
                    "export_paths": {
                        k: str(v) if v else None for k, v in export_paths.items()
                    },
                    "total_alerts": len(self.analyzer.alerts),
                }
                print(
                    f"📊 Multi-symbol analytics exported to: {self.analyzer.output_dir}"
                )
            except Exception as e:
                print(f"⚠️ Multi-symbol analytics finalization failed: {e}")
                analytics_results = {"analytics_enabled": True, "error": str(e)}

        return {**self._create_training_summary(), **analytics_results}

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

    def _create_scheduler(self, optimizer: optim.Optimizer) -> Any:
        """Create learning rate scheduler.

        Args:
            optimizer: PyTorch optimizer

        Returns:
            Scheduler instance or None (Any type due to incomplete PyTorch type stubs)
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

    def _create_training_summary(self) -> dict[str, Any]:
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
            # Update validation metrics
            summary["final_val_loss"] = val_losses[-1]
            summary["final_val_accuracy"] = val_accuracies[-1]
            summary["best_val_accuracy"] = self.best_val_accuracy

            # Update history with validation data
            if isinstance(summary["history"], dict):
                summary["history"]["val_loss"] = val_losses
                summary["history"]["val_accuracy"] = val_accuracies

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

    def get_checkpoint_state(
        self,
        current_epoch: int,
        model: nn.Module,
        optimizer: optim.Optimizer,
        scheduler: Any = None,
        early_stopping: EarlyStopping | None = None,
    ) -> dict[str, Any]:
        """
        Capture complete training state for checkpointing.

        Args:
            current_epoch: Current epoch number
            model: PyTorch model being trained
            optimizer: PyTorch optimizer
            scheduler: Optional learning rate scheduler
            early_stopping: Optional early stopping callback

        Returns:
            Dictionary containing all training state:
                - epoch: Current epoch number
                - model_state_dict: Model state as bytes
                - optimizer_state_dict: Optimizer state as bytes
                - scheduler_state_dict: Scheduler state as bytes (or None)
                - history: Training history (list of TrainingMetrics)
                - best_model_state: Best model state as bytes (or None)
                - best_val_accuracy: Best validation accuracy
                - early_stopping_state: Early stopping state (or None)
                - config: Training configuration
                - operation_id: Operation ID (if set)
                - checkpoint_type: Type of checkpoint ('epoch_snapshot')
                - created_at: ISO timestamp
                - pytorch_version: PyTorch version
                - checkpoint_version: Checkpoint format version
        """
        import io
        from datetime import datetime, timezone

        # Serialize model state_dict to bytes
        model_buffer = io.BytesIO()
        torch.save(model.state_dict(), model_buffer)
        model_state_bytes = model_buffer.getvalue()

        # Serialize optimizer state_dict to bytes
        optimizer_buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)
        optimizer_state_bytes = optimizer_buffer.getvalue()

        # Serialize scheduler state_dict to bytes (if exists)
        scheduler_state_bytes = None
        if scheduler is not None:
            scheduler_buffer = io.BytesIO()
            torch.save(scheduler.state_dict(), scheduler_buffer)
            scheduler_state_bytes = scheduler_buffer.getvalue()

        # Serialize best model state to bytes (if exists)
        best_model_state_bytes = None
        if self.best_model_state is not None:
            best_model_buffer = io.BytesIO()
            torch.save(self.best_model_state, best_model_buffer)
            best_model_state_bytes = best_model_buffer.getvalue()

        # Serialize training history (convert TrainingMetrics to dict)
        history_dicts = [
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
        ]

        # Serialize early stopping state (if exists)
        early_stopping_state = None
        if early_stopping is not None:
            early_stopping_state = {
                "counter": early_stopping.counter,
                "best_score": early_stopping.best_score,
                "early_stop": early_stopping.early_stop,
                "patience": early_stopping.patience,
                "min_delta": early_stopping.min_delta,
                "monitor": early_stopping.monitor,
                "mode": early_stopping.mode,
            }

        # Build checkpoint state
        checkpoint_state = {
            "epoch": current_epoch,
            "model_state_dict": model_state_bytes,
            "optimizer_state_dict": optimizer_state_bytes,
            "scheduler_state_dict": scheduler_state_bytes,
            "history": history_dicts,
            "best_model_state": best_model_state_bytes,
            "best_val_accuracy": self.best_val_accuracy,
            "early_stopping_state": early_stopping_state,
            "config": self.config.copy(),
            "operation_id": getattr(self, "operation_id", None),
            "checkpoint_type": "epoch_snapshot",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "pytorch_version": torch.__version__,
            "checkpoint_version": "1.0",
        }

        return checkpoint_state

    def restore_checkpoint_state(
        self,
        model: nn.Module,
        checkpoint_state: dict[str, Any],
        artifacts: dict[str, bytes],
        optimizer: optim.Optimizer | None = None,
        scheduler: Any = None,
        early_stopping: EarlyStopping | None = None,
    ) -> int:
        """
        Restore training state from checkpoint.

        Args:
            model: PyTorch model to restore state into
            checkpoint_state: Checkpoint state dictionary (JSON-serializable part)
            artifacts: Dictionary of binary artifacts (model, optimizer, etc.)
            optimizer: PyTorch optimizer to restore state into (optional, for flexibility)
            scheduler: Optional learning rate scheduler to restore state into
            early_stopping: Optional early stopping callback to restore state into

        Returns:
            Starting epoch for resumed training (checkpoint epoch + 1)
        """
        import io

        # Restore model state from artifacts
        if "model.pt" in artifacts:
            model_bytes = artifacts["model.pt"]
            model_state_dict = torch.load(io.BytesIO(model_bytes))
            model.load_state_dict(model_state_dict)

        # Restore optimizer state from artifacts (if provided)
        if optimizer is not None and "optimizer.pt" in artifacts:
            optimizer_bytes = artifacts["optimizer.pt"]
            optimizer_state_dict = torch.load(io.BytesIO(optimizer_bytes))
            optimizer.load_state_dict(optimizer_state_dict)

        # Restore scheduler state (if exists)
        if scheduler is not None and "scheduler.pt" in artifacts:
            scheduler_bytes = artifacts["scheduler.pt"]
            scheduler_state_dict = torch.load(io.BytesIO(scheduler_bytes))
            scheduler.load_state_dict(scheduler_state_dict)

        # Restore training history
        history_dicts = checkpoint_state["history"]
        self.history = [
            TrainingMetrics(
                epoch=h["epoch"],
                train_loss=h["train_loss"],
                train_accuracy=h["train_accuracy"],
                val_loss=h.get("val_loss"),
                val_accuracy=h.get("val_accuracy"),
                learning_rate=h.get("learning_rate", 0.001),
                duration=h.get("duration", 0.0),
            )
            for h in history_dicts
        ]

        # Restore best model state (if exists in artifacts)
        if "best_model.pt" in artifacts:
            best_model_bytes = artifacts["best_model.pt"]
            self.best_model_state = torch.load(io.BytesIO(best_model_bytes))
        else:
            self.best_model_state = None

        # Restore best validation accuracy
        self.best_val_accuracy = checkpoint_state.get("best_val_accuracy", 0.0)

        # Restore early stopping state (if exists)
        if early_stopping is not None and checkpoint_state.get("early_stopping_state"):
            es_state = checkpoint_state["early_stopping_state"]
            early_stopping.counter = es_state["counter"]
            early_stopping.best_score = es_state["best_score"]
            early_stopping.early_stop = es_state["early_stop"]
            # Restore config (already set in __init__, but verify compatibility)
            # Note: patience, min_delta, monitor, mode are set in __init__

        # Return starting epoch (checkpoint epoch + 1)
        checkpoint_epoch = checkpoint_state["epoch"]
        starting_epoch = checkpoint_epoch + 1

        return starting_epoch
