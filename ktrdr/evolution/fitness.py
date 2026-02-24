"""Fitness evaluator — multi-layer scoring for evolution.

Layer A: Gate checks (instant death for failures)
  - Minimum trades per slice (default 30)
  - Maximum drawdown per slice (default 35%)
  - Action diversity (not >90% same direction)

Layer B: Performance scoring across slices
  fitness = mean(Sharpe_i) - λ_dd * mean(MaxDD_i) - λ_var * std(Sharpe_i) - λ_cmp * complexity
"""

from __future__ import annotations

import math
from typing import Any

from ktrdr.evolution.config import EvolutionConfig

MINIMUM_FITNESS = -999.0

# Gate thresholds
_MIN_TRADES_PER_SLICE = 30
_MAX_DRAWDOWN_PER_SLICE = 0.35
_MAX_DIRECTION_RATIO = 0.90

# Default complexity when strategy info is unavailable
_DEFAULT_COMPLEXITY = 0.5


def _nn_param_bucket(param_count: int) -> float:
    """Map neural network parameter count to a 0-1 complexity bucket."""
    if param_count < 100:
        return 0.1
    if param_count < 500:
        return 0.3
    if param_count < 2000:
        return 0.5
    if param_count < 10000:
        return 0.7
    return 1.0


class FitnessEvaluator:
    """Multi-layer fitness scoring for evolution researchers.

    Uses gate checks (instant death) followed by performance scoring
    across multiple backtest slices, with variance and complexity penalties.
    """

    def __init__(self, config: EvolutionConfig) -> None:
        self._lambda_dd = config.lambda_dd
        self._lambda_var = config.lambda_var
        self._lambda_cmp = config.lambda_complexity

    def evaluate(self, backtest_result: dict[str, Any] | None) -> float:
        """Score a single backtest result (backward-compat wrapper).

        Delegates to evaluate_slices with a single slice.
        Missing or malformed results receive MINIMUM_FITNESS.
        """
        if not backtest_result:
            return MINIMUM_FITNESS
        return self.evaluate_slices([backtest_result])

    def evaluate_slices(
        self,
        slice_results: list[dict[str, Any]],
        strategy_info: dict[str, Any] | None = None,
    ) -> float:
        """Score a researcher from multiple backtest slice results.

        Layer A: Gate checks — any failure on any slice → MINIMUM_FITNESS.
        Layer B: Performance scoring with variance and complexity penalties.

        Args:
            slice_results: List of backtest result dicts (1 to 3 slices).
            strategy_info: Optional dict with 'indicator_count' and 'nn_param_count'
                for complexity calculation. Uses default if not provided.

        Returns:
            Fitness score, or MINIMUM_FITNESS for gate failures / empty input.
        """
        if not slice_results:
            return MINIMUM_FITNESS

        # Extract metrics from all slices
        sharpes: list[float] = []
        drawdowns: list[float] = []

        for s in slice_results:
            # Extract Sharpe — accept both key variants
            raw_sharpe = s.get("sharpe_ratio", s.get("sharpe"))
            raw_dd = s.get("max_drawdown")
            if raw_sharpe is None or raw_dd is None:
                return MINIMUM_FITNESS
            try:
                sharpe_val = float(raw_sharpe)
                dd_val = float(raw_dd)
            except (TypeError, ValueError):
                return MINIMUM_FITNESS

            # --- Layer A: Gate checks ---

            # Gate 1: Minimum trades
            total_trades = s.get("total_trades", 0)
            try:
                total_trades = int(total_trades)
            except (TypeError, ValueError):
                total_trades = 0
            if total_trades < _MIN_TRADES_PER_SLICE:
                return MINIMUM_FITNESS

            # Gate 2: Maximum drawdown
            if dd_val > _MAX_DRAWDOWN_PER_SLICE:
                return MINIMUM_FITNESS

            # Gate 3: Action diversity (skip if direction data unavailable)
            long_trades = s.get("long_trades")
            short_trades = s.get("short_trades")
            if long_trades is not None and short_trades is not None:
                try:
                    lt = int(long_trades)
                    st = int(short_trades)
                    total_dir = lt + st
                    if total_dir > 0:
                        max_ratio = max(lt, st) / total_dir
                        if max_ratio > _MAX_DIRECTION_RATIO:
                            return MINIMUM_FITNESS
                except (TypeError, ValueError):
                    pass  # Skip gate on bad data

            sharpes.append(sharpe_val)
            drawdowns.append(dd_val)

        # --- Layer B: Performance scoring ---

        n = len(sharpes)
        mean_sharpe = sum(sharpes) / n
        mean_dd = sum(drawdowns) / n

        # Cross-slice Sharpe variance (population std, not sample)
        if n > 1:
            variance = sum((s - mean_sharpe) ** 2 for s in sharpes) / n
            std_sharpe = math.sqrt(variance)
        else:
            std_sharpe = 0.0

        # Complexity
        complexity = self._compute_complexity(strategy_info)

        return (
            mean_sharpe
            - self._lambda_dd * mean_dd
            - self._lambda_var * std_sharpe
            - self._lambda_cmp * complexity
        )

    @staticmethod
    def _compute_complexity(strategy_info: dict[str, Any] | None) -> float:
        """Compute complexity score from strategy info.

        complexity = indicator_count/10 + nn_param_bucket
        Returns _DEFAULT_COMPLEXITY if strategy_info not available.
        """
        if strategy_info is None:
            return _DEFAULT_COMPLEXITY

        indicator_count = strategy_info.get("indicator_count")
        nn_param_count = strategy_info.get("nn_param_count")

        if indicator_count is None and nn_param_count is None:
            return _DEFAULT_COMPLEXITY

        ic = int(indicator_count) if indicator_count is not None else 0
        npc = int(nn_param_count) if nn_param_count is not None else 0

        return ic / 10.0 + _nn_param_bucket(npc)
