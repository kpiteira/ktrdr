"""Tests for fitness evaluator — scoring researchers from backtest results."""

from __future__ import annotations

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.fitness import FitnessEvaluator

MINIMUM_FITNESS = -999.0


class TestFitnessEvaluator:
    """Tests for FitnessEvaluator.evaluate()."""

    def test_positive_sharpe_low_drawdown(self) -> None:
        """Positive Sharpe + low drawdown → positive fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": 1.5, "max_drawdown": 0.10}
        fitness = evaluator.evaluate(result)
        # fitness = 1.5 - 1.0 * 0.10 = 1.4
        assert fitness > 0
        assert abs(fitness - 1.4) < 1e-9

    def test_negative_sharpe(self) -> None:
        """Negative Sharpe → negative fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": -0.5, "max_drawdown": 0.10}
        fitness = evaluator.evaluate(result)
        # fitness = -0.5 - 1.0 * 0.10 = -0.6
        assert fitness < 0
        assert abs(fitness - (-0.6)) < 1e-9

    def test_high_drawdown_penalty(self) -> None:
        """High drawdown should be penalized via lambda_dd."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": 1.0, "max_drawdown": 0.30}
        fitness = evaluator.evaluate(result)
        # fitness = 1.0 - 1.0 * 0.30 = 0.70
        assert abs(fitness - 0.70) < 1e-9

    def test_lambda_dd_affects_scoring(self) -> None:
        """Custom lambda_dd should change the penalty weight."""
        config = EvolutionConfig(lambda_dd=2.0)
        evaluator = FitnessEvaluator(config)
        result = {"sharpe": 1.0, "max_drawdown": 0.20}
        fitness = evaluator.evaluate(result)
        # fitness = 1.0 - 2.0 * 0.20 = 0.60
        assert abs(fitness - 0.60) < 1e-9

    def test_missing_backtest_result_none(self) -> None:
        """None backtest result → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        fitness = evaluator.evaluate(None)
        assert fitness == MINIMUM_FITNESS

    def test_empty_backtest_result(self) -> None:
        """Empty dict → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        fitness = evaluator.evaluate({})
        assert fitness == MINIMUM_FITNESS

    def test_missing_sharpe_key(self) -> None:
        """Dict without 'sharpe' key → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"max_drawdown": 0.10}
        fitness = evaluator.evaluate(result)
        assert fitness == MINIMUM_FITNESS

    def test_missing_drawdown_key(self) -> None:
        """Dict without 'max_drawdown' key → minimum fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": 1.0}
        fitness = evaluator.evaluate(result)
        assert fitness == MINIMUM_FITNESS

    def test_non_numeric_values(self) -> None:
        """Non-numeric values → minimum fitness (no exception)."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": "bad", "max_drawdown": 0.10}
        fitness = evaluator.evaluate(result)
        assert fitness == MINIMUM_FITNESS

    def test_zero_sharpe_zero_drawdown(self) -> None:
        """Zero values → zero fitness."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe": 0.0, "max_drawdown": 0.0}
        fitness = evaluator.evaluate(result)
        assert abs(fitness) < 1e-9

    def test_sharpe_ratio_key_from_worker(self) -> None:
        """Worker uses 'sharpe_ratio' key — evaluator should accept it."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe_ratio": 1.5, "max_drawdown": 0.10}
        fitness = evaluator.evaluate(result)
        assert abs(fitness - 1.4) < 1e-9

    def test_sharpe_ratio_preferred_over_sharpe(self) -> None:
        """When both keys present, sharpe_ratio takes precedence."""
        evaluator = FitnessEvaluator(EvolutionConfig())
        result = {"sharpe_ratio": 2.0, "sharpe": 1.0, "max_drawdown": 0.0}
        fitness = evaluator.evaluate(result)
        assert abs(fitness - 2.0) < 1e-9
