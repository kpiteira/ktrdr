"""Training checkpoint restore functionality.

Provides functions and data structures to restore training from a checkpoint
for resuming cancelled or failed training operations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from ktrdr.checkpoint.checkpoint_service import CheckpointService
from ktrdr.training.checkpoint_builder import (
    ArtifactValidationError,
    validate_artifacts,
)


class CheckpointNotFoundError(Exception):
    """Raised when no checkpoint is found for an operation."""

    pass


class CheckpointCorruptedError(Exception):
    """Raised when checkpoint artifacts are missing or invalid."""

    pass


@dataclass
class TrainingResumeContext:
    """Context for resuming training from a checkpoint.

    Contains all the information needed to restore training state
    and continue from where it left off.

    Attributes:
        start_epoch: The epoch to start from (checkpoint_epoch + 1).
        model_weights: Serialized model state_dict bytes.
        optimizer_state: Serialized optimizer state_dict bytes.
        scheduler_state: Optional serialized scheduler state_dict bytes.
        best_model_weights: Optional serialized best model state_dict bytes.
        training_history: History of training metrics for plotting.
        best_val_loss: Best validation loss seen before checkpoint.
        original_request: Original training request parameters.
    """

    # Required - always present
    start_epoch: int
    model_weights: bytes
    optimizer_state: bytes

    # Optional - may not be in checkpoint
    scheduler_state: Optional[bytes] = None
    best_model_weights: Optional[bytes] = None

    # State from checkpoint
    training_history: dict[str, list[float]] = field(default_factory=dict)
    best_val_loss: float = float("inf")
    original_request: dict[str, Any] = field(default_factory=dict)


async def restore_from_checkpoint(
    checkpoint_service: CheckpointService,
    operation_id: str,
) -> TrainingResumeContext:
    """Restore training context from a checkpoint.

    Loads the checkpoint for the given operation and creates a
    TrainingResumeContext that can be used to resume training.

    Args:
        checkpoint_service: Service for loading checkpoints.
        operation_id: The operation ID to restore.

    Returns:
        TrainingResumeContext with all state needed to resume.

    Raises:
        CheckpointNotFoundError: If no checkpoint exists for the operation.
        CheckpointCorruptedError: If required artifacts are missing or invalid.
    """
    # Load checkpoint with artifacts
    checkpoint = await checkpoint_service.load_checkpoint(
        operation_id, load_artifacts=True
    )

    if checkpoint is None:
        raise CheckpointNotFoundError(
            f"No checkpoint found for operation {operation_id}"
        )

    # Validate artifacts before use
    if checkpoint.artifacts is None:
        raise CheckpointCorruptedError(
            f"Checkpoint for {operation_id} has no artifacts"
        )

    try:
        validate_artifacts(checkpoint.artifacts)
    except ArtifactValidationError as e:
        raise CheckpointCorruptedError(str(e)) from e

    # Extract state from checkpoint
    state = checkpoint.state

    # Resume from NEXT epoch (per design decision D7)
    start_epoch = state.get("epoch", 0) + 1

    # Extract required artifacts
    model_weights = checkpoint.artifacts["model.pt"]
    optimizer_state = checkpoint.artifacts["optimizer.pt"]

    # Extract optional artifacts
    scheduler_state = checkpoint.artifacts.get("scheduler.pt")
    best_model_weights = checkpoint.artifacts.get("best_model.pt")

    # Extract state fields
    training_history = state.get("training_history", {})
    best_val_loss = state.get("best_val_loss", float("inf"))
    original_request = state.get("original_request", {})

    return TrainingResumeContext(
        start_epoch=start_epoch,
        model_weights=model_weights,
        optimizer_state=optimizer_state,
        scheduler_state=scheduler_state,
        best_model_weights=best_model_weights,
        training_history=training_history,
        best_val_loss=best_val_loss,
        original_request=original_request,
    )
