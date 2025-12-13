"""
Quality gates for research cycle phases.

Deterministic checks on training and backtest results to filter strategies
that don't meet minimum performance criteria. These run without invoking
the LLM, ensuring zero token cost for filtering poor strategies.

Thresholds are intentionally loose for MVP - we want to gather data
on what fails before tightening them.
"""

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class TrainingGateConfig:
    """Configuration for training quality gate.

    Attributes:
        min_accuracy: Minimum accuracy threshold (default: 0.45 = 45%)
        max_loss: Maximum final loss threshold (default: 0.8)
        min_loss_decrease: Minimum loss decrease ratio (default: 0.2 = 20%)
    """

    min_accuracy: float = 0.45
    max_loss: float = 0.8
    min_loss_decrease: float = 0.2

    @classmethod
    def from_env(cls) -> "TrainingGateConfig":
        """Load configuration from environment variables.

        Environment variables:
            TRAINING_GATE_MIN_ACCURACY: Minimum accuracy (default: 0.45)
            TRAINING_GATE_MAX_LOSS: Maximum final loss (default: 0.8)
            TRAINING_GATE_MIN_LOSS_DECREASE: Minimum loss decrease (default: 0.2)

        Returns:
            TrainingGateConfig instance with values from environment.
        """
        return cls(
            min_accuracy=float(os.getenv("TRAINING_GATE_MIN_ACCURACY", "0.45")),
            max_loss=float(os.getenv("TRAINING_GATE_MAX_LOSS", "0.8")),
            min_loss_decrease=float(
                os.getenv("TRAINING_GATE_MIN_LOSS_DECREASE", "0.2")
            ),
        )


def check_training_gate(
    metrics: dict[str, Any],
    config: TrainingGateConfig | None = None,
) -> tuple[bool, str]:
    """Check if training results pass quality gate.

    This is a deterministic check that runs without invoking the LLM,
    ensuring zero token cost for filtering poor strategies.

    Args:
        metrics: Training results containing:
            - accuracy: Model accuracy (0.0 to 1.0)
            - final_loss: Final training loss
            - initial_loss: Initial training loss
        config: Configuration thresholds (defaults from environment)

    Returns:
        Tuple of (passed, reason):
            - passed: True if all thresholds met, False otherwise
            - reason: Human-readable explanation of result
    """
    if config is None:
        config = TrainingGateConfig.from_env()

    accuracy = metrics.get("accuracy", 0)
    if accuracy < config.min_accuracy:
        return (
            False,
            f"accuracy_below_threshold ({accuracy:.1%} < {config.min_accuracy:.0%})",
        )

    final_loss = metrics.get("final_loss", 1.0)
    if final_loss > config.max_loss:
        return False, f"loss_too_high ({final_loss:.3f} > {config.max_loss})"

    initial = metrics.get("initial_loss", 0)
    final = final_loss
    if initial > 0:
        decrease = (initial - final) / initial
        if decrease < config.min_loss_decrease:
            return (
                False,
                f"insufficient_loss_decrease ({decrease:.1%} < {config.min_loss_decrease:.0%})",
            )

    return True, "passed"


@dataclass
class BacktestGateConfig:
    """Configuration for backtest quality gate.

    Attributes:
        min_win_rate: Minimum win rate threshold (default: 0.45 = 45%)
        max_drawdown: Maximum drawdown threshold (default: 0.4 = 40%)
        min_sharpe: Minimum Sharpe ratio threshold (default: -0.5)
    """

    min_win_rate: float = 0.45
    max_drawdown: float = 0.4
    min_sharpe: float = -0.5

    @classmethod
    def from_env(cls) -> "BacktestGateConfig":
        """Load configuration from environment variables.

        Environment variables:
            BACKTEST_GATE_MIN_WIN_RATE: Minimum win rate (default: 0.45)
            BACKTEST_GATE_MAX_DRAWDOWN: Maximum drawdown (default: 0.4)
            BACKTEST_GATE_MIN_SHARPE: Minimum Sharpe ratio (default: -0.5)

        Returns:
            BacktestGateConfig instance with values from environment.
        """
        return cls(
            min_win_rate=float(os.getenv("BACKTEST_GATE_MIN_WIN_RATE", "0.45")),
            max_drawdown=float(os.getenv("BACKTEST_GATE_MAX_DRAWDOWN", "0.4")),
            min_sharpe=float(os.getenv("BACKTEST_GATE_MIN_SHARPE", "-0.5")),
        )


def check_backtest_gate(
    metrics: dict[str, Any],
    config: BacktestGateConfig | None = None,
) -> tuple[bool, str]:
    """Check if backtest results pass quality gate.

    This is a deterministic check that runs without invoking the LLM,
    ensuring zero token cost for filtering poor strategies.

    Args:
        metrics: Backtest results containing:
            - win_rate: Fraction of winning trades (0.0 to 1.0)
            - max_drawdown: Maximum drawdown ratio (0.0 to 1.0)
            - sharpe_ratio: Sharpe ratio (can be negative)
        config: Configuration thresholds (defaults from environment)

    Returns:
        Tuple of (passed, reason):
            - passed: True if all thresholds met, False otherwise
            - reason: Human-readable explanation of result
    """
    if config is None:
        config = BacktestGateConfig.from_env()

    win_rate = metrics.get("win_rate", 0)
    if win_rate < config.min_win_rate:
        return False, f"win_rate_too_low ({win_rate:.1%} < {config.min_win_rate:.0%})"

    max_drawdown = metrics.get("max_drawdown", 1.0)
    if max_drawdown > config.max_drawdown:
        return (
            False,
            f"drawdown_too_high ({max_drawdown:.1%} > {config.max_drawdown:.0%})",
        )

    sharpe_ratio = metrics.get("sharpe_ratio", -999)
    if sharpe_ratio < config.min_sharpe:
        return False, f"sharpe_too_low ({sharpe_ratio:.2f} < {config.min_sharpe})"

    return True, "passed"
