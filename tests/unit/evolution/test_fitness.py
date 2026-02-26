"""Tests for fitness evaluator — M3 full multi-layer evaluation.

Layer A: Gate checks (instant death for failures)
Layer B: Performance scoring across slices with variance + complexity penalties
"""

from __future__ import annotations

import math

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS, FitnessEvaluator


def _make_slice(
    sharpe: float = 1.0,
    max_dd: float = 0.10,
    total_trades: int = 50,
    long_trades: int | None = None,
    short_trades: int | None = None,
) -> dict:
    """Helper to build a backtest result slice."""
    result: dict = {
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "total_trades": total_trades,
    }
    if long_trades is not None:
        result["long_trades"] = long_trades
    if short_trades is not None:
        result["short_trades"] = short_trades
    return result


class TestFitnessNoMinTradesGate:
    """Min trades gate was removed — low-trade strategies should be scored."""

    def test_1_trade_gets_scored(self) -> None:
        """A strategy with 1 trade should be scored, not gate-killed."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(total_trades=1)]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS

    def test_0_trades_still_scored(self) -> None:
        """Even 0 trades gets scored (no min trades gate)."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(total_trades=0)]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS

    def test_low_trade_slices_not_killed(self) -> None:
        """Mixed trade counts should all pass (no min trades gate)."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [
            _make_slice(total_trades=50),
            _make_slice(total_trades=1),
            _make_slice(total_trades=50),
        ]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS


class TestFitnessGateMaxDrawdown:
    """Gate: maximum drawdown per slice (default 35%)."""

    def test_036_drawdown_fails_gate(self) -> None:
        """0.36 > 0.35 threshold → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(max_dd=0.36)]
        assert evaluator.evaluate_slices(slices) == MINIMUM_FITNESS

    def test_034_drawdown_passes_gate(self) -> None:
        """0.34 < 0.35 threshold → passes gate."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(max_dd=0.34)]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS

    def test_035_drawdown_passes_gate(self) -> None:
        """0.35 = threshold → passes (boundary)."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(max_dd=0.35)]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS

    def test_max_drawdown_pct_preferred_over_dollar_amount(self) -> None:
        """Standalone backtests have max_drawdown in dollars, max_drawdown_pct as ratio.

        The evaluator should use max_drawdown_pct when available to avoid
        treating dollar amounts (e.g. 2205.49) as percentages.
        """
        evaluator = FitnessEvaluator(EvolutionConfig())
        # max_drawdown is a dollar amount (would fail gate), but
        # max_drawdown_pct is the actual ratio (should pass gate)
        slices = [
            {
                "sharpe_ratio": 0.09,
                "max_drawdown": 2205.49,  # Dollar amount — NOT a ratio
                "max_drawdown_pct": 0.0216,  # Actual ratio — 2.16%
                "total_trades": 1,
            }
        ]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS


class TestFitnessGateActionDiversity:
    """Gate: action diversity (not >90% same direction)."""

    def test_95pct_long_fails_gate(self) -> None:
        """95% long → fails diversity gate."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(long_trades=95, short_trades=5, total_trades=100)]
        assert evaluator.evaluate_slices(slices) == MINIMUM_FITNESS

    def test_80pct_long_passes_gate(self) -> None:
        """80% long → passes diversity gate."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(long_trades=80, short_trades=20, total_trades=100)]
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS

    def test_95pct_short_fails_gate(self) -> None:
        """95% short (>90% in one direction) → fails."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice(long_trades=5, short_trades=95, total_trades=100)]
        assert evaluator.evaluate_slices(slices) == MINIMUM_FITNESS

    def test_missing_direction_data_skips_gate(self) -> None:
        """If long_trades/short_trades not available, skip diversity gate."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        slices = [_make_slice()]  # No long_trades/short_trades
        assert evaluator.evaluate_slices(slices) != MINIMUM_FITNESS


class TestFitnessMultiSliceScoring:
    """Layer B: Performance scoring across slices."""

    def test_3_slices_known_values(self) -> None:
        """3 slices with known Sharpe/DD → verify exact fitness value."""
        config = EvolutionConfig(lambda_dd=1.0, lambda_var=1.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [
            _make_slice(sharpe=1.0, max_dd=0.10),
            _make_slice(sharpe=1.5, max_dd=0.15),
            _make_slice(sharpe=2.0, max_dd=0.20),
        ]
        fitness = evaluator.evaluate_slices(slices)

        # mean(Sharpe) = (1.0 + 1.5 + 2.0) / 3 = 1.5
        # mean(MaxDD) = (0.10 + 0.15 + 0.20) / 3 = 0.15
        # std(Sharpe) = sqrt(((1-1.5)^2 + (1.5-1.5)^2 + (2-1.5)^2) / 3) ≈ 0.4082
        # fitness = 1.5 - 1.0*0.15 - 1.0*0.4082 - 0 ≈ 0.9418
        mean_sharpe = (1.0 + 1.5 + 2.0) / 3
        mean_dd = (0.10 + 0.15 + 0.20) / 3
        variance = sum((s - mean_sharpe) ** 2 for s in [1.0, 1.5, 2.0]) / 3
        std_sharpe = math.sqrt(variance)
        expected = mean_sharpe - 1.0 * mean_dd - 1.0 * std_sharpe
        assert abs(fitness - expected) < 1e-9

    def test_identical_sharpes_zero_variance_penalty(self) -> None:
        """Identical Sharpes across slices → 0 variance penalty."""
        config = EvolutionConfig(lambda_dd=0.0, lambda_var=1.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [
            _make_slice(sharpe=1.5, max_dd=0.0),
            _make_slice(sharpe=1.5, max_dd=0.0),
            _make_slice(sharpe=1.5, max_dd=0.0),
        ]
        fitness = evaluator.evaluate_slices(slices)
        # mean(Sharpe) = 1.5, std(Sharpe) = 0, no DD or complexity penalties
        assert abs(fitness - 1.5) < 1e-9

    def test_divergent_sharpes_large_variance_penalty(self) -> None:
        """Divergent Sharpes → large variance penalty."""
        config = EvolutionConfig(lambda_dd=0.0, lambda_var=1.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [
            _make_slice(sharpe=0.0, max_dd=0.0),
            _make_slice(sharpe=3.0, max_dd=0.0),
        ]
        fitness = evaluator.evaluate_slices(slices)
        # mean = 1.5, std = sqrt(((0-1.5)^2 + (3-1.5)^2)/2) = 1.5
        # fitness = 1.5 - 1.5 = 0.0
        assert abs(fitness) < 1e-9


class TestFitnessComplexity:
    """Complexity penalty from strategy info."""

    def test_small_strategy_low_penalty(self) -> None:
        """2 indicators + small network → low complexity."""
        config = EvolutionConfig(lambda_complexity=0.1, lambda_dd=0.0, lambda_var=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [_make_slice(sharpe=2.0, max_dd=0.0)]
        info = {"indicator_count": 2, "nn_param_count": 50}  # <100 → bucket 0.1
        fitness = evaluator.evaluate_slices(slices, strategy_info=info)
        # complexity = 2/10 + 0.1 = 0.3
        # fitness = 2.0 - 0.1*0.3 = 1.97
        assert abs(fitness - (2.0 - 0.1 * 0.3)) < 1e-9

    def test_large_strategy_high_penalty(self) -> None:
        """8 indicators + large network → high complexity."""
        config = EvolutionConfig(lambda_complexity=0.1, lambda_dd=0.0, lambda_var=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [_make_slice(sharpe=2.0, max_dd=0.0)]
        info = {"indicator_count": 8, "nn_param_count": 15000}  # ≥10000 → bucket 1.0
        fitness = evaluator.evaluate_slices(slices, strategy_info=info)
        # complexity = 8/10 + 1.0 = 1.8
        # fitness = 2.0 - 0.1*1.8 = 1.82
        assert abs(fitness - (2.0 - 0.1 * 1.8)) < 1e-9

    def test_default_complexity_when_no_strategy_info(self) -> None:
        """Without strategy_info, use default complexity 0.5."""
        config = EvolutionConfig(lambda_complexity=0.1, lambda_dd=0.0, lambda_var=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [_make_slice(sharpe=2.0, max_dd=0.0)]
        fitness = evaluator.evaluate_slices(slices)
        # complexity = 0.5 (default)
        # fitness = 2.0 - 0.1*0.5 = 1.95
        assert abs(fitness - (2.0 - 0.1 * 0.5)) < 1e-9

    def test_nn_param_bucket_boundaries(self) -> None:
        """Test nn_param_bucket mapping at boundaries."""
        config = EvolutionConfig(lambda_complexity=1.0, lambda_dd=0.0, lambda_var=0.0)
        evaluator = FitnessEvaluator(config)
        base_slice = [_make_slice(sharpe=5.0, max_dd=0.0)]

        # <100 → 0.1
        f1 = evaluator.evaluate_slices(
            base_slice, {"indicator_count": 0, "nn_param_count": 99}
        )
        # <500 → 0.3
        f2 = evaluator.evaluate_slices(
            base_slice, {"indicator_count": 0, "nn_param_count": 499}
        )
        # <2000 → 0.5
        f3 = evaluator.evaluate_slices(
            base_slice, {"indicator_count": 0, "nn_param_count": 1999}
        )
        # <10000 → 0.7
        f4 = evaluator.evaluate_slices(
            base_slice, {"indicator_count": 0, "nn_param_count": 9999}
        )
        # ≥10000 → 1.0
        f5 = evaluator.evaluate_slices(
            base_slice, {"indicator_count": 0, "nn_param_count": 10000}
        )

        # complexity = 0/10 + bucket
        assert abs(f1 - (5.0 - 1.0 * 0.1)) < 1e-9  # 4.9
        assert abs(f2 - (5.0 - 1.0 * 0.3)) < 1e-9  # 4.7
        assert abs(f3 - (5.0 - 1.0 * 0.5)) < 1e-9  # 4.5
        assert abs(f4 - (5.0 - 1.0 * 0.7)) < 1e-9  # 4.3
        assert abs(f5 - (5.0 - 1.0 * 1.0)) < 1e-9  # 4.0


class TestFitnessGracefulSliceHandling:
    """Handle 1 or 2 slices gracefully."""

    def test_single_slice_variance_zero(self) -> None:
        """1 slice → variance penalty = 0, mean = single value."""
        config = EvolutionConfig(lambda_dd=1.0, lambda_var=1.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [_make_slice(sharpe=2.0, max_dd=0.10)]
        fitness = evaluator.evaluate_slices(slices)
        # mean(Sharpe) = 2.0, mean(DD) = 0.10, std = 0
        # fitness = 2.0 - 1.0*0.10 - 0 = 1.9
        assert abs(fitness - 1.9) < 1e-9

    def test_two_slices_variance_computed(self) -> None:
        """2 slices → variance computed from 2 values."""
        config = EvolutionConfig(lambda_dd=0.0, lambda_var=1.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [
            _make_slice(sharpe=1.0, max_dd=0.0),
            _make_slice(sharpe=3.0, max_dd=0.0),
        ]
        fitness = evaluator.evaluate_slices(slices)
        # mean = 2.0, std = sqrt(((1-2)^2 + (3-2)^2)/2) = 1.0
        # fitness = 2.0 - 1.0 = 1.0
        assert abs(fitness - 1.0) < 1e-9

    def test_empty_slices_minimum_fitness(self) -> None:
        """Empty slice_results → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        assert evaluator.evaluate_slices([]) == MINIMUM_FITNESS


class TestFitnessLambdaConfigurable:
    """All lambdas should be configurable via EvolutionConfig."""

    def test_all_lambdas_at_zero(self) -> None:
        """All lambdas = 0 → fitness = mean(Sharpe)."""
        config = EvolutionConfig(lambda_dd=0.0, lambda_var=0.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [
            _make_slice(sharpe=1.0, max_dd=0.20),
            _make_slice(sharpe=3.0, max_dd=0.20),
        ]
        fitness = evaluator.evaluate_slices(slices)
        assert abs(fitness - 2.0) < 1e-9  # Just mean Sharpe

    def test_custom_lambda_dd(self) -> None:
        """Custom lambda_dd changes drawdown penalty."""
        config = EvolutionConfig(lambda_dd=2.0, lambda_var=0.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        slices = [_make_slice(sharpe=1.0, max_dd=0.20)]
        fitness = evaluator.evaluate_slices(slices)
        # 1.0 - 2.0*0.20 = 0.6
        assert abs(fitness - 0.6) < 1e-9


class TestFitnessBackwardCompat:
    """Old evaluate() method should still work as a wrapper."""

    def test_evaluate_none_returns_minimum(self) -> None:
        """None → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        assert evaluator.evaluate(None) == MINIMUM_FITNESS

    def test_evaluate_empty_dict_returns_minimum(self) -> None:
        """Empty dict → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        assert evaluator.evaluate({}) == MINIMUM_FITNESS

    def test_evaluate_single_result_scores(self) -> None:
        """Single dict delegates to evaluate_slices with 1 slice."""
        config = EvolutionConfig(lambda_dd=1.0, lambda_var=0.0, lambda_complexity=0.0)
        evaluator = FitnessEvaluator(config)
        result = {"sharpe_ratio": 1.5, "max_drawdown": 0.10, "total_trades": 50}
        fitness = evaluator.evaluate(result)
        # mean(Sharpe) = 1.5, mean(DD) = 0.10, std = 0, no complexity penalty
        # 1.5 - 1.0*0.10 = 1.40
        expected = 1.5 - 1.0 * 0.10
        assert abs(fitness - expected) < 1e-9

    def test_evaluate_accepts_sharpe_key(self) -> None:
        """Accept both 'sharpe_ratio' and 'sharpe' keys."""
        evaluator = FitnessEvaluator(
            EvolutionConfig(lambda_dd=0.0, lambda_var=0.0, lambda_complexity=0.0)
        )
        result = {"sharpe": 1.5, "max_drawdown": 0.0, "total_trades": 50}
        fitness = evaluator.evaluate(result)
        assert abs(fitness - 1.5) < 1e-9
