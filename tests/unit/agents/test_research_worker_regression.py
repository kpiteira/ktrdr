"""Tests for regression metadata flow through research worker."""

import pytest

from ktrdr.agents.gates import check_backtest_gate, check_training_gate


class TestResearchWorkerRegressionMetadata:
    """Verify that output_format flows through research cycle gate checks."""

    def test_training_gate_with_regression_result(self):
        """Training result with output_format=regression uses regression gate."""
        result = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.55,
                "test_loss": 0.005,
            },
        }
        passed, reason = check_training_gate(result)
        assert passed is True

    def test_training_gate_regression_fails_correctly(self):
        """Regression training gate rejects low directional accuracy."""
        result = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.48,
                "test_loss": 0.005,
            },
        }
        passed, reason = check_training_gate(result)
        assert passed is False
        assert "directional" in reason.lower()

    def test_backtest_gate_with_regression_result(self):
        """Backtest result with output_format=regression uses regression gate."""
        result = {
            "output_format": "regression",
            "net_return": 0.01,
            "trade_count": 10,
            "win_rate": 0.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5,
        }
        passed, reason = check_backtest_gate(result)
        assert passed is True

    def test_classification_results_unchanged(self):
        """Without output_format, gates use classification checks."""
        training_result = {
            "test_metrics": {"test_accuracy": 0.15, "test_loss": 0.5},
        }
        passed, _ = check_training_gate(training_result)
        assert passed is True

        backtest_result = {
            "win_rate": 0.15,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.0,
        }
        passed, _ = check_backtest_gate(backtest_result)
        assert passed is True


class TestAssessmentWorkerRegressionContext:
    """Verify assessment worker includes regression context."""

    def test_user_prompt_includes_output_format_in_training_metrics(self):
        """Assessment worker should pass output_format through training_metrics."""
        from ktrdr.agents.workers.assessment_agent_worker import AssessmentAgentWorker
        from unittest.mock import MagicMock

        runtime = MagicMock()
        worker = AssessmentAgentWorker(runtime=runtime)

        training_metrics = {
            "output_format": "regression",
            "directional_accuracy": 0.55,
            "r_squared": 0.12,
        }
        backtest_results = {
            "sharpe_ratio": 0.5,
            "win_rate": 0.55,
            "total_trades": 15,
        }

        prompt = worker._build_user_prompt(
            strategy_name="test_regression",
            strategy_config=None,
            training_metrics=training_metrics,
            backtest_results=backtest_results,
            experiment_history=None,
        )

        # The training_metrics JSON should include output_format
        assert "regression" in prompt.lower()
        assert "directional_accuracy" in prompt

    def test_user_prompt_includes_regression_guidance(self):
        """Assessment prompt includes regression evaluation guidance section."""
        from ktrdr.agents.workers.assessment_agent_worker import AssessmentAgentWorker
        from unittest.mock import MagicMock

        runtime = MagicMock()
        worker = AssessmentAgentWorker(runtime=runtime)

        training_metrics = {
            "output_format": "regression",
            "directional_accuracy": 0.55,
        }
        backtest_results = {"sharpe_ratio": 0.5}

        prompt = worker._build_user_prompt(
            strategy_name="test_regression",
            strategy_config=None,
            training_metrics=training_metrics,
            backtest_results=backtest_results,
            experiment_history=None,
        )

        # Should include explicit regression guidance section (not just JSON data)
        assert "forward return" in prompt.lower()
        assert "directional accuracy" in prompt.lower()
        assert "cost threshold" in prompt.lower() or "cost" in prompt.lower()

    def test_classification_prompt_unchanged(self):
        """Classification assessment prompt has no regression content."""
        from ktrdr.agents.workers.assessment_agent_worker import AssessmentAgentWorker
        from unittest.mock import MagicMock

        runtime = MagicMock()
        worker = AssessmentAgentWorker(runtime=runtime)

        training_metrics = {"accuracy": 0.65, "final_loss": 0.5}
        backtest_results = {"sharpe_ratio": 0.3}

        prompt = worker._build_user_prompt(
            strategy_name="test_classification",
            strategy_config=None,
            training_metrics=training_metrics,
            backtest_results=backtest_results,
            experiment_history=None,
        )

        assert "forward return" not in prompt.lower()
