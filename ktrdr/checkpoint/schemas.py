"""Checkpoint state schemas and artifact manifests.

Defines the data structures for checkpoint state that gets stored in the database
(JSONB) and the manifest of artifacts that get stored on the filesystem.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class TrainingCheckpointState:
    """State captured during training for checkpoint/resume functionality.

    This state is stored as JSONB in the database and must be JSON-serializable.
    It captures everything needed to resume training from this point.

    Attributes:
        epoch: Current training epoch (0-indexed).
        train_loss: Training loss at this epoch.
        val_loss: Validation loss at this epoch (inf if no validation).
        train_accuracy: Training accuracy at this epoch.
        val_accuracy: Validation accuracy at this epoch.
        learning_rate: Current learning rate.
        best_val_loss: Best validation loss seen so far.
        training_history: History of metrics for plotting (train_loss, val_loss, etc.).
        original_request: Original training request for resume context.
    """

    # Resume point
    epoch: int
    train_loss: float
    val_loss: float

    # Progress metrics (optional)
    train_accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    best_val_loss: float = float("inf")

    # History for plotting
    training_history: dict[str, list[float]] = field(default_factory=dict)

    # Original request for resume
    original_request: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingCheckpointState":
        """Create from dictionary (deserialization).

        Handles missing optional fields gracefully by using defaults.
        """
        return cls(
            epoch=data["epoch"],
            train_loss=data["train_loss"],
            val_loss=data.get("val_loss", float("inf")),
            train_accuracy=data.get("train_accuracy"),
            val_accuracy=data.get("val_accuracy"),
            learning_rate=data.get("learning_rate", 0.001),
            best_val_loss=data.get("best_val_loss", float("inf")),
            training_history=data.get("training_history", {}),
            original_request=data.get("original_request", {}),
        )


# Artifact manifest for training checkpoints
# Maps artifact filename to requirement level
TRAINING_ARTIFACTS: dict[str, str] = {
    "model.pt": "required",
    "optimizer.pt": "required",
    "scheduler.pt": "optional",
    "best_model.pt": "optional",
}
