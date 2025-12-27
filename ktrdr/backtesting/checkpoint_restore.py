"""Backtest checkpoint restore functionality.

Provides functions and data structures to restore backtesting from a checkpoint
for resuming cancelled or failed backtest operations.
"""

from dataclasses import dataclass, field
from typing import Any

from ktrdr.checkpoint.checkpoint_service import CheckpointService


class CheckpointNotFoundError(Exception):
    """Raised when no checkpoint is found for an operation."""

    pass


@dataclass
class BacktestResumeContext:
    """Context for resuming backtesting from a checkpoint.

    Contains all the information needed to restore backtest state
    and continue from where it left off.

    Attributes:
        start_bar: The bar to start from (checkpoint_bar + 1).
        cash: Current cash balance in portfolio.
        original_request: Original backtest request parameters for data reload.
        positions: List of open positions (optional).
        trades: List of completed trades (optional).
        equity_samples: Sampled equity curve (optional).
    """

    # Required - always present
    start_bar: int
    cash: float
    original_request: dict[str, Any]

    # Optional - may not be in checkpoint
    positions: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_samples: list[dict[str, Any]] = field(default_factory=list)


async def restore_from_checkpoint(
    checkpoint_service: CheckpointService,
    operation_id: str,
) -> BacktestResumeContext:
    """Restore backtest context from a checkpoint.

    Loads the checkpoint for the given operation and creates a
    BacktestResumeContext that can be used to resume backtesting.

    Args:
        checkpoint_service: Service for loading checkpoints.
        operation_id: The operation ID to restore.

    Returns:
        BacktestResumeContext with all state needed to resume.

    Raises:
        CheckpointNotFoundError: If no checkpoint exists for the operation.
    """
    # Load checkpoint without artifacts (backtesting has no artifacts)
    checkpoint = await checkpoint_service.load_checkpoint(
        operation_id, load_artifacts=False
    )

    if checkpoint is None:
        raise CheckpointNotFoundError(
            f"No checkpoint found for operation {operation_id}"
        )

    # Extract state from checkpoint
    state = checkpoint.state

    # Resume from NEXT bar (per design decision D7)
    start_bar = state.get("bar_index", 0) + 1

    # Extract required fields
    cash = state.get("cash", 0.0)

    # Extract optional fields with defaults
    positions = state.get("positions", [])
    trades = state.get("trades", [])
    equity_samples = state.get("equity_samples", [])
    original_request = state.get("original_request", {})

    return BacktestResumeContext(
        start_bar=start_bar,
        cash=cash,
        original_request=original_request,
        positions=positions,
        trades=trades,
        equity_samples=equity_samples,
    )
