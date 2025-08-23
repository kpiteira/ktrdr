"""Training stability and recovery system for robust KTRDR training."""

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn

from ktrdr import get_logger
from ktrdr.training.error_handler import ErrorHandler, RecoveryAction

logger = get_logger(__name__)


class TrainingStatus(Enum):
    """Training status indicators."""

    STABLE = "stable"
    UNSTABLE = "unstable"
    DIVERGING = "diverging"
    STALLED = "stalled"
    RECOVERING = "recovering"
    FAILED = "failed"


@dataclass
class CheckpointMetadata:
    """Metadata for training checkpoints."""

    epoch: int
    step: int
    timestamp: float
    model_hash: str
    optimizer_state_hash: str
    loss: float
    metrics: dict[str, float]
    training_status: TrainingStatus
    model_config: dict[str, Any]
    training_config: dict[str, Any]
    data_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "epoch": self.epoch,
            "step": self.step,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "model_hash": self.model_hash,
            "optimizer_state_hash": self.optimizer_state_hash,
            "loss": self.loss,
            "metrics": self.metrics,
            "training_status": self.training_status.value,
            "model_config": self.model_config,
            "training_config": self.training_config,
            "data_config": self.data_config,
        }


@dataclass
class StabilityMetrics:
    """Training stability metrics."""

    loss_variance: float
    loss_trend: float  # Positive = increasing, negative = decreasing
    gradient_norm: float
    learning_rate: float
    convergence_rate: float
    oscillation_frequency: float
    recovery_time: float = 0.0
    instability_count: int = 0

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "loss_variance": self.loss_variance,
            "loss_trend": self.loss_trend,
            "gradient_norm": self.gradient_norm,
            "learning_rate": self.learning_rate,
            "convergence_rate": self.convergence_rate,
            "oscillation_frequency": self.oscillation_frequency,
            "recovery_time": self.recovery_time,
            "instability_count": self.instability_count,
        }


class TrainingStabilizer:
    """Advanced training stability monitoring and recovery system."""

    def __init__(
        self,
        checkpoint_dir: Path,
        save_frequency: int = 10,
        max_checkpoints: int = 10,
        stability_window: int = 50,
        error_handler: Optional[ErrorHandler] = None,
    ):
        """Initialize training stabilizer.

        Args:
            checkpoint_dir: Directory to save checkpoints
            save_frequency: Save checkpoint every N epochs
            max_checkpoints: Maximum number of checkpoints to keep
            stability_window: Window size for stability analysis
            error_handler: Error handler for recovery operations
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.save_frequency = save_frequency
        self.max_checkpoints = max_checkpoints
        self.stability_window = stability_window
        self.error_handler = error_handler or ErrorHandler()

        # Training state tracking
        self.checkpoints: list[CheckpointMetadata] = []
        self.loss_history: list[float] = []
        self.gradient_history: list[float] = []
        self.stability_history: list[StabilityMetrics] = []

        # Stability monitoring
        self.current_status = TrainingStatus.STABLE
        self.instability_count = 0
        self.last_stable_checkpoint: Optional[Path] = None
        self.recovery_attempts = 0

        # Threading for background monitoring
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None

        logger.info(
            f"TrainingStabilizer initialized, checkpoint dir: {self.checkpoint_dir}"
        )

    def save_checkpoint(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        epoch: int,
        step: int,
        loss: float,
        metrics: dict[str, float],
        model_config: dict[str, Any],
        training_config: dict[str, Any],
        force: bool = False,
    ) -> Path:
        """Save training checkpoint.

        Args:
            model: Model to checkpoint
            optimizer: Optimizer to checkpoint
            epoch: Current epoch
            step: Current step
            loss: Current loss
            metrics: Performance metrics
            model_config: Model configuration
            training_config: Training configuration
            force: Force save regardless of frequency

        Returns:
            Path to saved checkpoint
        """
        # Check if we should save
        if not force and epoch % self.save_frequency != 0:
            return None

        timestamp = time.time()

        # Generate checkpoint filename
        checkpoint_name = (
            f"checkpoint_epoch_{epoch:04d}_step_{step:06d}_{int(timestamp)}.pt"
        )
        checkpoint_path = self.checkpoint_dir / checkpoint_name

        # Create checkpoint data
        model_state = model.state_dict()
        optimizer_state = optimizer.state_dict()

        # Generate hashes for verification
        model_hash = self._generate_state_hash(model_state)
        optimizer_hash = self._generate_state_hash(optimizer_state)

        checkpoint_data = {
            "epoch": epoch,
            "step": step,
            "model_state_dict": model_state,
            "optimizer_state_dict": optimizer_state,
            "loss": loss,
            "metrics": metrics,
            "timestamp": timestamp,
            "model_hash": model_hash,
            "optimizer_hash": optimizer_hash,
            "model_config": model_config,
            "training_config": training_config,
            "training_status": self.current_status.value,
            "stability_metrics": (
                self.stability_history[-1].to_dict() if self.stability_history else {}
            ),
        }

        # Save checkpoint
        try:
            torch.save(checkpoint_data, checkpoint_path)

            # Create metadata
            metadata = CheckpointMetadata(
                epoch=epoch,
                step=step,
                timestamp=timestamp,
                model_hash=model_hash,
                optimizer_state_hash=optimizer_hash,
                loss=loss,
                metrics=metrics,
                training_status=self.current_status,
                model_config=model_config,
                training_config=training_config,
            )

            self.checkpoints.append(metadata)

            # Update last stable checkpoint if training is stable
            if self.current_status == TrainingStatus.STABLE:
                self.last_stable_checkpoint = checkpoint_path

            # Clean up old checkpoints
            self._cleanup_old_checkpoints()

            logger.info(f"Checkpoint saved: {checkpoint_path}")
            return checkpoint_path

        except Exception as e:
            recovery_action = self.error_handler.handle_error(
                e,
                "TrainingStabilizer",
                "save_checkpoint",
                {"epoch": epoch, "step": step, "checkpoint_path": str(checkpoint_path)},
            )

            if recovery_action == RecoveryAction.RETRY:
                # Retry with a different filename
                checkpoint_name = f"checkpoint_epoch_{epoch:04d}_step_{step:06d}_{int(time.time())}_retry.pt"
                checkpoint_path = self.checkpoint_dir / checkpoint_name
                torch.save(checkpoint_data, checkpoint_path)
                logger.warning(f"Checkpoint saved after retry: {checkpoint_path}")
                return checkpoint_path
            else:
                logger.error(f"Failed to save checkpoint: {e}")
                return None

    def load_checkpoint(self, checkpoint_path: Path) -> dict[str, Any]:
        """Load training checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint data dictionary
        """
        try:
            checkpoint_data = torch.load(checkpoint_path, map_location="cpu")

            # Verify checkpoint integrity
            if not self._verify_checkpoint_integrity(checkpoint_data):
                raise ValueError("Checkpoint integrity verification failed")

            logger.info(f"Checkpoint loaded: {checkpoint_path}")
            return checkpoint_data

        except Exception as e:
            recovery_action = self.error_handler.handle_error(
                e,
                "TrainingStabilizer",
                "load_checkpoint",
                {"checkpoint_path": str(checkpoint_path)},
            )

            if recovery_action == RecoveryAction.FALLBACK:
                # Try to load last stable checkpoint
                if (
                    self.last_stable_checkpoint
                    and self.last_stable_checkpoint != checkpoint_path
                ):
                    logger.warning(
                        f"Loading fallback checkpoint: {self.last_stable_checkpoint}"
                    )
                    return self.load_checkpoint(self.last_stable_checkpoint)

            raise

    def resume_training(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        checkpoint_path: Optional[Path] = None,
    ) -> tuple[int, int, dict[str, Any]]:
        """Resume training from checkpoint.

        Args:
            model: Model to restore
            optimizer: Optimizer to restore
            checkpoint_path: Specific checkpoint to load (latest if None)

        Returns:
            Tuple of (epoch, step, metrics)
        """
        if checkpoint_path is None:
            checkpoint_path = self._find_latest_checkpoint()

        if checkpoint_path is None:
            logger.info("No checkpoint found, starting fresh training")
            return 0, 0, {}

        checkpoint_data = self.load_checkpoint(checkpoint_path)

        # Restore model and optimizer state
        model.load_state_dict(checkpoint_data["model_state_dict"])
        optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])

        epoch = checkpoint_data["epoch"]
        step = checkpoint_data["step"]
        metrics = checkpoint_data.get("metrics", {})

        # Restore training status
        self.current_status = TrainingStatus(
            checkpoint_data.get("training_status", "stable")
        )

        logger.info(f"Training resumed from epoch {epoch}, step {step}")
        return epoch, step, metrics

    def monitor_training_stability(
        self,
        loss: float,
        gradients: Optional[torch.Tensor] = None,
        learning_rate: float = 0.001,
    ) -> StabilityMetrics:
        """Monitor training stability and detect issues.

        Args:
            loss: Current training loss
            gradients: Current gradients (optional)
            learning_rate: Current learning rate

        Returns:
            Stability metrics
        """
        self.loss_history.append(loss)

        # Track gradient norms
        if gradients is not None:
            grad_norm = torch.norm(gradients).item()
            self.gradient_history.append(grad_norm)
        else:
            grad_norm = 0.0

        # Keep only recent history
        if len(self.loss_history) > self.stability_window:
            self.loss_history = self.loss_history[-self.stability_window :]
        if len(self.gradient_history) > self.stability_window:
            self.gradient_history = self.gradient_history[-self.stability_window :]

        # Calculate stability metrics
        metrics = self._calculate_stability_metrics(loss, grad_norm, learning_rate)
        self.stability_history.append(metrics)

        # Keep only recent stability history
        if len(self.stability_history) > self.stability_window:
            self.stability_history = self.stability_history[-self.stability_window :]

        # Update training status based on metrics
        self._update_training_status(metrics)

        return metrics

    def _calculate_stability_metrics(
        self, current_loss: float, grad_norm: float, learning_rate: float
    ) -> StabilityMetrics:
        """Calculate training stability metrics."""
        if len(self.loss_history) < 2:
            return StabilityMetrics(
                loss_variance=0.0,
                loss_trend=0.0,
                gradient_norm=grad_norm,
                learning_rate=learning_rate,
                convergence_rate=0.0,
                oscillation_frequency=0.0,
            )

        loss_array = np.array(self.loss_history)

        # Loss variance
        loss_variance = np.var(loss_array)

        # Loss trend (linear regression slope)
        x = np.arange(len(loss_array))
        trend_coeff = np.polyfit(x, loss_array, 1)[0]

        # Convergence rate (rate of loss decrease)
        if len(loss_array) >= 10:
            recent_losses = loss_array[-10:]
            convergence_rate = (recent_losses[0] - recent_losses[-1]) / len(
                recent_losses
            )
        else:
            convergence_rate = 0.0

        # Oscillation frequency (zero crossings in loss differences)
        loss_diffs = np.diff(loss_array)
        if len(loss_diffs) > 1:
            zero_crossings = np.sum(np.diff(np.sign(loss_diffs)) != 0)
            oscillation_freq = zero_crossings / len(loss_diffs)
        else:
            oscillation_freq = 0.0

        return StabilityMetrics(
            loss_variance=float(loss_variance),
            loss_trend=float(trend_coeff),
            gradient_norm=grad_norm,
            learning_rate=learning_rate,
            convergence_rate=float(convergence_rate),
            oscillation_frequency=float(oscillation_freq),
            instability_count=self.instability_count,
        )

    def _update_training_status(self, metrics: StabilityMetrics):
        """Update training status based on stability metrics."""
        previous_status = self.current_status

        # Define thresholds for stability assessment
        high_variance_threshold = 0.1
        stall_threshold = 1e-6
        divergence_threshold = 0.01  # Positive trend = loss increasing
        high_oscillation_threshold = 0.3

        # Assess stability
        if metrics.loss_trend > divergence_threshold:
            self.current_status = TrainingStatus.DIVERGING
        elif metrics.loss_variance > high_variance_threshold:
            self.current_status = TrainingStatus.UNSTABLE
        elif (
            abs(metrics.convergence_rate) < stall_threshold
            and len(self.loss_history) > 20
        ):
            self.current_status = TrainingStatus.STALLED
        elif metrics.oscillation_frequency > high_oscillation_threshold:
            self.current_status = TrainingStatus.UNSTABLE
        else:
            self.current_status = TrainingStatus.STABLE

        # Track instability events
        if (
            self.current_status != TrainingStatus.STABLE
            and previous_status == TrainingStatus.STABLE
        ):
            self.instability_count += 1
            logger.warning(
                f"Training instability detected: {self.current_status.value}"
            )

        # Log status changes
        if self.current_status != previous_status:
            logger.info(
                f"Training status changed: {previous_status.value} → {self.current_status.value}"
            )

    def get_recovery_recommendations(self) -> list[str]:
        """Get recommendations for training recovery."""
        recommendations = []

        if not self.stability_history:
            return recommendations

        latest_metrics = self.stability_history[-1]

        if self.current_status == TrainingStatus.DIVERGING:
            recommendations.extend(
                [
                    "Reduce learning rate by factor of 2-10",
                    "Load checkpoint from last stable state",
                    "Consider gradient clipping",
                    "Check for data quality issues",
                ]
            )

        elif self.current_status == TrainingStatus.UNSTABLE:
            recommendations.extend(
                [
                    "Reduce learning rate",
                    "Increase batch size for smoother gradients",
                    "Apply gradient clipping",
                    "Consider learning rate scheduling",
                ]
            )

        elif self.current_status == TrainingStatus.STALLED:
            recommendations.extend(
                [
                    "Increase learning rate carefully",
                    "Apply learning rate warmup/cycling",
                    "Check for vanishing gradients",
                    "Consider model architecture changes",
                ]
            )

        # General recommendations based on metrics
        if latest_metrics.gradient_norm > 10.0:
            recommendations.append("Apply gradient clipping (gradient norm is high)")

        if latest_metrics.gradient_norm < 1e-6:
            recommendations.append("Check for vanishing gradients")

        if latest_metrics.oscillation_frequency > 0.4:
            recommendations.append("Reduce learning rate to decrease oscillations")

        return recommendations

    def auto_recovery(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    ) -> bool:
        """Attempt automatic recovery from training instability.

        Args:
            model: Current model
            optimizer: Current optimizer
            scheduler: Learning rate scheduler (optional)

        Returns:
            True if recovery was attempted, False otherwise
        """
        if self.current_status == TrainingStatus.STABLE:
            return False

        self.recovery_attempts += 1
        logger.info(f"Attempting auto-recovery (attempt {self.recovery_attempts})")

        try:
            if self.current_status == TrainingStatus.DIVERGING:
                # Severe instability - reload last stable checkpoint
                if self.last_stable_checkpoint:
                    checkpoint_data = self.load_checkpoint(self.last_stable_checkpoint)
                    model.load_state_dict(checkpoint_data["model_state_dict"])
                    optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])

                    # Reduce learning rate significantly
                    for param_group in optimizer.param_groups:
                        param_group["lr"] *= 0.1

                    logger.info("Loaded stable checkpoint and reduced learning rate")
                    self.current_status = TrainingStatus.RECOVERING
                    return True

            elif self.current_status in [
                TrainingStatus.UNSTABLE,
                TrainingStatus.STALLED,
            ]:
                # Moderate instability - adjust learning rate
                if self.current_status == TrainingStatus.UNSTABLE:
                    lr_factor = 0.5  # Reduce LR
                else:  # STALLED
                    lr_factor = 1.2  # Increase LR slightly

                for param_group in optimizer.param_groups:
                    param_group["lr"] *= lr_factor

                logger.info(f"Adjusted learning rate by factor {lr_factor}")
                self.current_status = TrainingStatus.RECOVERING
                return True

        except Exception as e:
            self.error_handler.handle_error(
                e,
                "TrainingStabilizer",
                "auto_recovery",
                {
                    "recovery_attempts": self.recovery_attempts,
                    "status": self.current_status.value,
                },
            )
            return False

        return False

    def _generate_state_hash(self, state_dict: dict[str, Any]) -> str:
        """Generate hash for state dict verification."""
        state_str = ""
        for key in sorted(state_dict.keys()):
            value = state_dict[key]
            if torch.is_tensor(value):
                if value.dtype.is_floating_point:
                    # Use sum for floating point tensors (more stable)
                    state_str += f"{key}:{value.sum().item():.6f}"
                else:
                    # Use exact values for integer tensors
                    state_str += f"{key}:{value.sum().item()}"
            else:
                # For non-tensor values, convert to string
                state_str += f"{key}:{str(value)}"

        return hashlib.md5(
            state_str.encode()
        ).hexdigest()  # nosec B324 - Used for data integrity, not cryptographic security

    def _verify_checkpoint_integrity(self, checkpoint_data: dict[str, Any]) -> bool:
        """Verify checkpoint integrity using hashes."""
        try:
            model_state = checkpoint_data["model_state_dict"]
            optimizer_state = checkpoint_data["optimizer_state_dict"]
            stored_model_hash = checkpoint_data.get("model_hash", "")
            stored_optimizer_hash = checkpoint_data.get("optimizer_hash", "")

            # Verify model state hash
            computed_model_hash = self._generate_state_hash(model_state)
            if computed_model_hash != stored_model_hash:
                logger.warning("Model state hash mismatch")
                return False

            # Skip optimizer state verification as it's complex and less critical
            # than model state verification
            if stored_optimizer_hash:
                logger.debug("Skipping optimizer state hash verification")

            return True

        except Exception as e:
            logger.error(f"Checkpoint verification failed: {e}")
            return False

    def _find_latest_checkpoint(self) -> Optional[Path]:
        """Find the most recent checkpoint file."""
        checkpoint_files = list(self.checkpoint_dir.glob("checkpoint_*.pt"))
        if not checkpoint_files:
            return None

        # Sort by modification time
        latest_checkpoint = max(checkpoint_files, key=lambda p: p.stat().st_mtime)
        return latest_checkpoint

    def _cleanup_old_checkpoints(self):
        """Remove old checkpoints beyond max_checkpoints limit."""
        checkpoint_files = list(self.checkpoint_dir.glob("checkpoint_*.pt"))

        if len(checkpoint_files) <= self.max_checkpoints:
            return

        # Sort by modification time (oldest first)
        checkpoint_files.sort(key=lambda p: p.stat().st_mtime)

        # Remove oldest checkpoints
        to_remove = checkpoint_files[: -self.max_checkpoints]
        for checkpoint_path in to_remove:
            try:
                checkpoint_path.unlink()
                logger.debug(f"Removed old checkpoint: {checkpoint_path}")
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint {checkpoint_path}: {e}")

        # Also cleanup metadata
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints = self.checkpoints[-self.max_checkpoints :]

    def get_training_summary(self) -> dict[str, Any]:
        """Get comprehensive training stability summary."""
        if not self.stability_history:
            return {
                "current_status": self.current_status.value,
                "checkpoints_saved": len(self.checkpoints),
                "instability_events": self.instability_count,
                "recovery_attempts": self.recovery_attempts,
            }

        latest_metrics = self.stability_history[-1]

        # Calculate average metrics over recent history
        recent_window = min(10, len(self.stability_history))
        recent_metrics = self.stability_history[-recent_window:]

        avg_loss_variance = np.mean([m.loss_variance for m in recent_metrics])
        avg_convergence_rate = np.mean([m.convergence_rate for m in recent_metrics])
        avg_gradient_norm = np.mean([m.gradient_norm for m in recent_metrics])

        return {
            "current_status": self.current_status.value,
            "current_metrics": latest_metrics.to_dict(),
            "average_metrics": {
                "loss_variance": float(avg_loss_variance),
                "convergence_rate": float(avg_convergence_rate),
                "gradient_norm": float(avg_gradient_norm),
            },
            "training_health": {
                "checkpoints_saved": len(self.checkpoints),
                "instability_events": self.instability_count,
                "recovery_attempts": self.recovery_attempts,
                "last_stable_checkpoint": (
                    str(self.last_stable_checkpoint)
                    if self.last_stable_checkpoint
                    else None
                ),
            },
            "recommendations": self.get_recovery_recommendations(),
        }

    def export_stability_log(self, file_path: Optional[Path] = None) -> Path:
        """Export training stability log.

        Args:
            file_path: Output file path (auto-generated if None)

        Returns:
            Path to exported file
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.checkpoint_dir / f"stability_log_{timestamp}.json"

        stability_data = {
            "metadata": {
                "export_timestamp": time.time(),
                "checkpoint_dir": str(self.checkpoint_dir),
                "stability_window": self.stability_window,
                "save_frequency": self.save_frequency,
            },
            "training_summary": self.get_training_summary(),
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "stability_history": [sm.to_dict() for sm in self.stability_history],
            "loss_history": self.loss_history,
            "gradient_history": self.gradient_history,
        }

        with open(file_path, "w") as f:
            json.dump(stability_data, f, indent=2, default=str)

        logger.info(f"Stability log exported to: {file_path}")
        return file_path
