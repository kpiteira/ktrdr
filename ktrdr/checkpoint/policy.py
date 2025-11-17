"""
Checkpoint policy configuration and decision logic.

This module implements:
- CheckpointPolicy: Dataclass for checkpoint configuration
- CheckpointDecisionEngine: Time-based checkpoint decision algorithm
- load_checkpoint_policies(): Load policies from config/persistence.yaml
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CheckpointPolicy:
    """
    Configuration for checkpoint behavior.

    Attributes:
        checkpoint_interval_seconds: Target time between checkpoints (seconds)
            Adapts to operation speed: fast epochs (10s) → checkpoint every ~30 epochs
            slow epochs (30m) → checkpoint every epoch
        force_checkpoint_every_n: Force checkpoint every N natural boundaries (epochs/bars)
            Safety net ensures checkpoint even if time threshold not reached
        delete_on_completion: Delete checkpoint when operation completes successfully
            Checkpoints are ephemeral - only needed for resume
        checkpoint_on_failure: Save checkpoint when operation fails
            Allows resume from failure point
        checkpoint_on_cancellation: Save checkpoint when user cancels operation
            Preserves work when operation is manually cancelled (Task 3.5)
    """

    checkpoint_interval_seconds: float
    force_checkpoint_every_n: int
    delete_on_completion: bool
    checkpoint_on_failure: bool
    checkpoint_on_cancellation: bool

    def __post_init__(self):
        """Validate policy parameters."""
        if self.checkpoint_interval_seconds <= 0:
            raise ValueError("checkpoint_interval_seconds must be positive")
        if self.force_checkpoint_every_n <= 0:
            raise ValueError("force_checkpoint_every_n must be positive")


class CheckpointDecisionEngine:
    """
    Decision engine for time-based checkpoint logic.

    Implements checkpoint decision algorithm from architecture document:
    1. First boundary? → NO (no checkpoint on first epoch/bar)
    2. At forced boundary? (every N epochs/bars) → YES
    3. Enough time elapsed? → YES if time_since_last >= checkpoint_interval_seconds
    4. Default: NO
    """

    def should_checkpoint(
        self,
        policy: CheckpointPolicy,
        last_checkpoint_time: float,
        current_time: float,
        natural_boundary: int,
        total_boundaries: int,
    ) -> tuple[bool, str]:
        """
        Determine if checkpoint should be created based on policy and current state.

        Args:
            policy: Checkpoint policy configuration
            last_checkpoint_time: Unix timestamp of last checkpoint (or operation start)
            current_time: Current unix timestamp
            natural_boundary: Current natural boundary (epoch number or bar number)
            total_boundaries: Total boundaries processed so far

        Returns:
            Tuple of (should_checkpoint: bool, reason: str)
                should_checkpoint: True if checkpoint should be created
                reason: Human-readable explanation of decision

        Decision algorithm:
            1. First boundary → NO CHECKPOINT (nothing to save yet)
            2. Force boundary (every N) → YES (safety net)
            3. Time threshold met → YES (time_since_last >= interval)
            4. Default → NO
        """
        # 1. First boundary? → NO
        if natural_boundary == 1:
            return False, "First boundary - nothing to checkpoint yet"

        # 2. At forced boundary? → YES
        if natural_boundary % policy.force_checkpoint_every_n == 0:
            return (
                True,
                f"Force checkpoint at boundary {natural_boundary} (every {policy.force_checkpoint_every_n})",
            )

        # 3. Enough time elapsed? → YES
        time_since_last = current_time - last_checkpoint_time
        if time_since_last >= policy.checkpoint_interval_seconds:
            return (
                True,
                f"Time threshold met ({time_since_last:.1f}s >= {policy.checkpoint_interval_seconds}s)",
            )

        # 4. Default → NO
        return (
            False,
            f"Not enough time elapsed ({time_since_last:.1f}s < {policy.checkpoint_interval_seconds}s)",
        )


def load_checkpoint_policies(
    config_path: Path | None = None,
) -> dict[str, CheckpointPolicy]:
    """
    Load checkpoint policies from config/persistence.yaml.

    Args:
        config_path: Optional custom config path. If None, uses config/persistence.yaml

    Returns:
        Dictionary mapping operation type to CheckpointPolicy:
            {"training": CheckpointPolicy(...), "backtesting": CheckpointPolicy(...)}

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config structure is invalid or missing required fields
        yaml.YAMLError: If YAML syntax is invalid
    """
    if config_path is None:
        # Default to config/persistence.yaml in project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "persistence.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Checkpoint persistence config not found at {config_path}. "
            f"Ensure config/persistence.yaml exists."
        )

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

    if not isinstance(config, dict):
        raise ValueError(f"Config file {config_path} should contain a YAML dictionary")

    if "checkpointing" not in config:
        raise ValueError(
            f"Config file {config_path} missing 'checkpointing' section. "
            f"See docs/architecture/checkpoint/checkpoint-persistence-architecture.md"
        )

    checkpointing = config["checkpointing"]

    if "training" not in checkpointing:
        raise ValueError("'checkpointing' section missing 'training' policy")

    if "backtesting" not in checkpointing:
        raise ValueError("'checkpointing' section missing 'backtesting' policy")

    # Load training policy
    training_config = checkpointing["training"]
    training_policy = CheckpointPolicy(
        checkpoint_interval_seconds=float(
            training_config["checkpoint_interval_seconds"]
        ),
        force_checkpoint_every_n=int(training_config["force_checkpoint_every_n"]),
        delete_on_completion=bool(training_config["delete_on_completion"]),
        checkpoint_on_failure=bool(training_config["checkpoint_on_failure"]),
        checkpoint_on_cancellation=bool(
            training_config.get("checkpoint_on_cancellation", False)
        ),
    )

    # Load backtesting policy
    backtesting_config = checkpointing["backtesting"]
    backtesting_policy = CheckpointPolicy(
        checkpoint_interval_seconds=float(
            backtesting_config["checkpoint_interval_seconds"]
        ),
        force_checkpoint_every_n=int(backtesting_config["force_checkpoint_every_n"]),
        delete_on_completion=bool(backtesting_config["delete_on_completion"]),
        checkpoint_on_failure=bool(backtesting_config["checkpoint_on_failure"]),
        checkpoint_on_cancellation=bool(
            backtesting_config.get("checkpoint_on_cancellation", False)
        ),
    )

    return {
        "training": training_policy,
        "backtesting": backtesting_policy,
    }
