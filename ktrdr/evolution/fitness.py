"""Fitness evaluator — scores researchers based on backtest results.

M1 uses single-slice scoring: fitness = sharpe - lambda_dd * max_drawdown.
Full multi-slice scoring with gates comes in M3.
"""

from __future__ import annotations

from typing import Any

from ktrdr.evolution.config import EvolutionConfig

MINIMUM_FITNESS = -999.0


class FitnessEvaluator:
    """Scores researchers from backtest results.

    M1 formula: fitness = sharpe - lambda_dd * max_drawdown.
    Missing or malformed results receive MINIMUM_FITNESS.
    """

    def __init__(self, config: EvolutionConfig) -> None:
        self._lambda_dd = config.lambda_dd

    def evaluate(self, backtest_result: dict[str, Any] | None) -> float:
        """Score a single backtest result.

        Returns MINIMUM_FITNESS for missing/malformed results instead
        of raising exceptions — failed researchers simply die at selection.
        """
        if not backtest_result:
            return MINIMUM_FITNESS

        try:
            sharpe = float(backtest_result["sharpe"])
            max_dd = float(backtest_result["max_drawdown"])
        except (KeyError, TypeError, ValueError):
            return MINIMUM_FITNESS

        return sharpe - self._lambda_dd * max_dd
