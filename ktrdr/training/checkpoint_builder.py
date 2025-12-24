"""Training checkpoint builder functions.

Provides functions to extract checkpoint state and artifacts from a ModelTrainer
and related PyTorch objects during training.
"""

import io
from typing import Any, Optional

import torch
import torch.nn as nn
import torch.optim as optim

from ktrdr.checkpoint.schemas import TRAINING_ARTIFACTS, TrainingCheckpointState
from ktrdr.training.model_trainer import ModelTrainer


class ArtifactValidationError(Exception):
    """Raised when artifact validation fails."""

    pass


def build_training_checkpoint_state(
    trainer: ModelTrainer,
    current_epoch: int,
    original_request: Optional[dict[str, Any]] = None,
) -> TrainingCheckpointState:
    """Extract checkpoint state from a ModelTrainer.

    Args:
        trainer: The ModelTrainer instance with training history.
        current_epoch: The current epoch number (0-indexed).
        original_request: Original training request for resume context.

    Returns:
        TrainingCheckpointState populated from the trainer's history.
    """
    # Get the latest metrics from history
    if trainer.history and len(trainer.history) > current_epoch:
        latest = trainer.history[current_epoch]
    elif trainer.history:
        latest = trainer.history[-1]
    else:
        # No history yet - use defaults
        return TrainingCheckpointState(
            epoch=current_epoch,
            train_loss=float("inf"),
            val_loss=float("inf"),
            original_request=original_request or {},
        )

    # Extract training history for plotting
    training_history: dict[str, list[float]] = {
        "train_loss": [m.train_loss for m in trainer.history],
        "train_accuracy": [m.train_accuracy for m in trainer.history],
    }

    # Add validation metrics if available
    val_losses = [m.val_loss for m in trainer.history if m.val_loss is not None]
    val_accuracies = [
        m.val_accuracy for m in trainer.history if m.val_accuracy is not None
    ]

    if val_losses:
        training_history["val_loss"] = val_losses
    if val_accuracies:
        training_history["val_accuracy"] = val_accuracies

    # Calculate best validation loss
    best_val_loss = min(val_losses) if val_losses else float("inf")

    return TrainingCheckpointState(
        epoch=current_epoch,
        train_loss=latest.train_loss,
        val_loss=latest.val_loss if latest.val_loss is not None else float("inf"),
        train_accuracy=latest.train_accuracy,
        val_accuracy=latest.val_accuracy,
        learning_rate=latest.learning_rate,
        best_val_loss=best_val_loss,
        training_history=training_history,
        original_request=original_request or {},
    )


def build_training_checkpoint_artifacts(
    model: nn.Module,
    optimizer: optim.Optimizer,
    scheduler: Optional[Any] = None,
    best_model_state: Optional[dict[str, Any]] = None,
) -> dict[str, bytes]:
    """Extract checkpoint artifacts from PyTorch objects.

    Serializes model, optimizer, and optionally scheduler state to bytes
    for storage on the filesystem.

    Args:
        model: The PyTorch model to checkpoint.
        optimizer: The optimizer with current state.
        scheduler: Optional learning rate scheduler.
        best_model_state: Optional best model state dict to save.

    Returns:
        Dictionary mapping artifact names to their serialized bytes.
    """
    artifacts: dict[str, bytes] = {}

    # Required: model.pt
    model_buffer = io.BytesIO()
    torch.save(model.state_dict(), model_buffer)
    artifacts["model.pt"] = model_buffer.getvalue()

    # Required: optimizer.pt
    optimizer_buffer = io.BytesIO()
    torch.save(optimizer.state_dict(), optimizer_buffer)
    artifacts["optimizer.pt"] = optimizer_buffer.getvalue()

    # Optional: scheduler.pt
    if scheduler is not None:
        scheduler_buffer = io.BytesIO()
        torch.save(scheduler.state_dict(), scheduler_buffer)
        artifacts["scheduler.pt"] = scheduler_buffer.getvalue()

    # Optional: best_model.pt
    if best_model_state is not None:
        best_model_buffer = io.BytesIO()
        torch.save(best_model_state, best_model_buffer)
        artifacts["best_model.pt"] = best_model_buffer.getvalue()

    return artifacts


def validate_artifacts(artifacts: dict[str, bytes]) -> None:
    """Validate that artifacts contain all required items.

    Args:
        artifacts: Dictionary of artifact name to bytes.

    Raises:
        ArtifactValidationError: If required artifacts are missing or empty.
    """
    for name, requirement in TRAINING_ARTIFACTS.items():
        if requirement != "required":
            continue

        if name not in artifacts:
            raise ArtifactValidationError(
                f"Missing required artifact: {name}. "
                f"Required artifacts: {[k for k, v in TRAINING_ARTIFACTS.items() if v == 'required']}"
            )

        if not artifacts[name]:
            raise ArtifactValidationError(
                f"Required artifact is empty: {name}. "
                "Artifact bytes cannot be empty."
            )
