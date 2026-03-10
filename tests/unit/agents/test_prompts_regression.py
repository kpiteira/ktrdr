"""Tests for regression-specific assessment prompt context."""

from ktrdr.agents.prompts import AssessmentContext, get_assessment_prompt


class TestAssessmentPromptRegression:
    """Assessment prompt includes regression context when output_format is regression."""

    def _make_regression_context(self) -> AssessmentContext:
        return AssessmentContext(
            operation_id="op_test_123",
            strategy_name="regression_test_strategy",
            strategy_path="strategies/test.yaml",
            training_metrics={
                "output_format": "regression",
                "directional_accuracy": 0.55,
                "r_squared": 0.12,
                "mse": 0.0001,
                "mae": 0.008,
                "initial_loss": 0.01,
                "final_loss": 0.005,
            },
            backtest_metrics={
                "sharpe_ratio": 0.5,
                "win_rate": 0.55,
                "max_drawdown": 0.05,
                "total_return": 0.02,
                "total_trades": 15,
                "net_return": 0.02,
            },
            cost_model={
                "round_trip_cost": 0.003,
                "min_edge_multiplier": 1.5,
            },
        )

    def _make_classification_context(self) -> AssessmentContext:
        return AssessmentContext(
            operation_id="op_test_456",
            strategy_name="classification_test_strategy",
            strategy_path="strategies/class.yaml",
            training_metrics={
                "accuracy": 0.65,
                "initial_loss": 1.0,
                "final_loss": 0.5,
            },
            backtest_metrics={
                "sharpe_ratio": 0.3,
                "win_rate": 0.45,
                "max_drawdown": 0.1,
                "total_return": -0.01,
                "total_trades": 30,
            },
        )

    def test_regression_prompt_includes_regression_guidance(self):
        """Assessment prompt includes regression-specific guidance."""
        ctx = self._make_regression_context()
        prompt = get_assessment_prompt(ctx)
        assert "regression" in prompt.lower()
        assert (
            "directional accuracy" in prompt.lower()
            or "directional_accuracy" in prompt.lower()
        )

    def test_regression_prompt_includes_r_squared(self):
        """R-squared metric included in regression assessment."""
        ctx = self._make_regression_context()
        prompt = get_assessment_prompt(ctx)
        assert (
            "r_squared" in prompt.lower()
            or "r-squared" in prompt.lower()
            or "r²" in prompt.lower()
        )

    def test_regression_prompt_includes_cost_model(self):
        """cost_model config included in regression assessment context."""
        ctx = self._make_regression_context()
        prompt = get_assessment_prompt(ctx)
        assert "cost" in prompt.lower()
        assert "0.003" in prompt or "round_trip" in prompt.lower()

    def test_regression_metric_names_match_collector(self):
        """Regression metrics in prompt match what MetricsCollector produces."""
        ctx = self._make_regression_context()
        prompt = get_assessment_prompt(ctx)
        prompt_lower = prompt.lower()
        # These are the key names from MetricsCollector.collect_regression_metrics
        # Check each appears in some readable form
        assert "directional accuracy" in prompt_lower, "Missing: directional_accuracy"
        assert "r-squared" in prompt_lower or "r²" in prompt_lower, "Missing: r_squared"
        assert "mse" in prompt_lower, "Missing: mse"
        assert "mae" in prompt_lower, "Missing: mae"

    def test_classification_prompt_unchanged(self):
        """Classification assessment prompt still works normally."""
        ctx = self._make_classification_context()
        prompt = get_assessment_prompt(ctx)
        assert "accuracy" in prompt.lower()
        assert "65.0%" in prompt or "0.65" in prompt
        # Should NOT contain regression-specific content
        assert "forward return" not in prompt.lower()
