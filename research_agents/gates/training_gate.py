"""
Training quality gate.

Deterministic check on training results to prevent wasting compute
on backtesting poorly-trained models.

Thresholds are intentionally loose for MVP - we want to gather data
on what fails before tightening them.
"""

import os
from dataclasses import dataclass


@dataclass
class TrainingGateConfig:
    """Configuration for training quality gate.

    Attributes:
        min_accuracy: Minimum accuracy threshold (default: 0.45 = 45%)
        max_loss: Maximum final loss threshold (default: 0.8)
        min_loss_reduction: Minimum loss reduction ratio (default: 0.2 = 20%)
    """

    min_accuracy: float = 0.45
    max_loss: float = 0.8
    min_loss_reduction: float = 0.2

    @classmethod
    def from_env(cls) -> "TrainingGateConfig":
        """Load configuration from environment variables.

        Environment variables:
            TRAINING_GATE_MIN_ACCURACY: Minimum accuracy (default: 0.45)
            TRAINING_GATE_MAX_LOSS: Maximum final loss (default: 0.8)
            TRAINING_GATE_MIN_LOSS_REDUCTION: Minimum loss reduction (default: 0.2)

        Returns:
            TrainingGateConfig instance with values from environment.
        """
        min_accuracy = float(os.getenv("TRAINING_GATE_MIN_ACCURACY", "0.45"))
        max_loss = float(os.getenv("TRAINING_GATE_MAX_LOSS", "0.8"))
        min_loss_reduction = float(os.getenv("TRAINING_GATE_MIN_LOSS_REDUCTION", "0.2"))
        return cls(
            min_accuracy=min_accuracy,
            max_loss=max_loss,
            min_loss_reduction=min_loss_reduction,
        )


def evaluate_training_gate(
    results: dict, config: TrainingGateConfig | None = None
) -> tuple[bool, str]:
    """Evaluate training results against quality thresholds.

    This is a deterministic check that runs without invoking the LLM,
    ensuring zero token cost for filtering poor strategies.

    Args:
        results: Training results containing:
            - accuracy: Model accuracy (0.0 to 1.0)
            - final_loss: Final training loss
            - initial_loss: Initial training loss
        config: Configuration thresholds (defaults to TrainingGateConfig())

    Returns:
        Tuple of (passed, reason):
            - passed: True if all thresholds met, False otherwise
            - reason: Human-readable explanation of result
    """
    if config is None:
        config = TrainingGateConfig()

    accuracy = results.get("accuracy", 0.0)
    final_loss = results.get("final_loss", float("inf"))
    initial_loss = results.get("initial_loss", 0.0)

    # Check accuracy threshold
    if accuracy < config.min_accuracy:
        return False, f"Accuracy {accuracy:.2%} below threshold ({config.min_accuracy:.0%})"

    # Check final loss threshold
    if final_loss > config.max_loss:
        return False, f"Final loss {final_loss:.3f} above threshold ({config.max_loss})"

    # Check loss reduction
    # Handle edge case of zero initial loss
    if initial_loss <= 0:
        # If initial loss is zero or negative, we can't compute reduction
        # This is an unusual case - fail safely
        return False, "Cannot compute loss reduction: initial_loss <= 0"

    loss_reduction = 1 - (final_loss / initial_loss)
    if loss_reduction < config.min_loss_reduction:
        return (
            False,
            f"Loss reduction {loss_reduction:.1%} below threshold ({config.min_loss_reduction:.0%})",
        )

    return True, "All thresholds passed"
