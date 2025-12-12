"""
Backtest quality gate.

Deterministic check on backtest results to filter strategies
that don't meet minimum performance criteria.

Thresholds are intentionally loose for MVP - we want to gather data
on what fails before tightening them.
"""

import os
from dataclasses import dataclass


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
        min_win_rate = float(os.getenv("BACKTEST_GATE_MIN_WIN_RATE", "0.45"))
        max_drawdown = float(os.getenv("BACKTEST_GATE_MAX_DRAWDOWN", "0.4"))
        min_sharpe = float(os.getenv("BACKTEST_GATE_MIN_SHARPE", "-0.5"))
        return cls(
            min_win_rate=min_win_rate,
            max_drawdown=max_drawdown,
            min_sharpe=min_sharpe,
        )


def evaluate_backtest_gate(
    results: dict, config: BacktestGateConfig | None = None
) -> tuple[bool, str]:
    """Evaluate backtest results against quality thresholds.

    This is a deterministic check that runs without invoking the LLM,
    ensuring zero token cost for filtering poor strategies.

    Args:
        results: Backtest results containing:
            - win_rate: Fraction of winning trades (0.0 to 1.0)
            - max_drawdown: Maximum drawdown ratio (0.0 to 1.0)
            - sharpe_ratio: Sharpe ratio (can be negative)
        config: Configuration thresholds (defaults to BacktestGateConfig())

    Returns:
        Tuple of (passed, reason):
            - passed: True if all thresholds met, False otherwise
            - reason: Human-readable explanation of result
    """
    if config is None:
        config = BacktestGateConfig()

    win_rate = results.get("win_rate", 0.0)
    max_drawdown = results.get("max_drawdown", float("inf"))
    sharpe_ratio = results.get("sharpe_ratio", float("-inf"))

    # Check win rate threshold
    if win_rate < config.min_win_rate:
        return (
            False,
            f"Win rate {win_rate:.1%} below threshold ({config.min_win_rate:.0%})",
        )

    # Check max drawdown threshold
    if max_drawdown > config.max_drawdown:
        return (
            False,
            f"Max drawdown {max_drawdown:.1%} above threshold ({config.max_drawdown:.0%})",
        )

    # Check Sharpe ratio threshold
    if sharpe_ratio < config.min_sharpe:
        return (
            False,
            f"Sharpe {sharpe_ratio:.2f} below threshold ({config.min_sharpe})",
        )

    return True, "All thresholds passed"
