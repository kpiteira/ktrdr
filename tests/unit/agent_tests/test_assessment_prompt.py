"""Unit tests for assessment prompt builder.

Tests for Task 5.1: Assessment prompt construction.
"""

import pytest

from ktrdr.agents.prompts import (
    ASSESSMENT_SYSTEM_PROMPT,
    AssessmentContext,
    get_assessment_prompt,
)


class TestAssessmentContext:
    """Tests for AssessmentContext dataclass."""

    def test_assessment_context_creation(self):
        """AssessmentContext can be created with all required fields."""
        ctx = AssessmentContext(
            operation_id="op_agent_assessment_123",
            strategy_name="momentum_rsi_v1",
            strategy_path="/app/strategies/momentum_rsi_v1.yaml",
            training_metrics={"accuracy": 0.65, "final_loss": 0.35},
            backtest_metrics={"sharpe_ratio": 1.2, "win_rate": 0.55},
        )

        assert ctx.operation_id == "op_agent_assessment_123"
        assert ctx.strategy_name == "momentum_rsi_v1"
        assert ctx.strategy_path == "/app/strategies/momentum_rsi_v1.yaml"
        assert ctx.training_metrics["accuracy"] == 0.65
        assert ctx.backtest_metrics["sharpe_ratio"] == 1.2


class TestAssessmentSystemPrompt:
    """Tests for the assessment system prompt."""

    def test_system_prompt_exists(self):
        """ASSESSMENT_SYSTEM_PROMPT is defined."""
        assert ASSESSMENT_SYSTEM_PROMPT is not None
        assert len(ASSESSMENT_SYSTEM_PROMPT) > 100

    def test_system_prompt_contains_key_instructions(self):
        """System prompt contains key instructions for Claude."""
        assert "save_assessment" in ASSESSMENT_SYSTEM_PROMPT
        assert "strengths" in ASSESSMENT_SYSTEM_PROMPT.lower()
        assert "weaknesses" in ASSESSMENT_SYSTEM_PROMPT.lower()
        assert "verdict" in ASSESSMENT_SYSTEM_PROMPT.lower()


class TestGetAssessmentPrompt:
    """Tests for get_assessment_prompt function."""

    @pytest.fixture
    def sample_context(self) -> AssessmentContext:
        """Create a sample assessment context."""
        return AssessmentContext(
            operation_id="op_agent_assessment_456",
            strategy_name="mean_reversion_v2",
            strategy_path="/app/strategies/mean_reversion_v2.yaml",
            training_metrics={
                "accuracy": 0.62,
                "final_loss": 0.38,
                "initial_loss": 0.75,
            },
            backtest_metrics={
                "sharpe_ratio": 1.5,
                "win_rate": 0.58,
                "max_drawdown": 0.12,
                "total_return": 0.25,
                "total_trades": 42,
            },
        )

    def test_prompt_includes_strategy_info(self, sample_context):
        """Prompt includes strategy name and path."""
        prompt = get_assessment_prompt(sample_context)

        assert "mean_reversion_v2" in prompt
        assert sample_context.operation_id in prompt

    def test_prompt_includes_training_metrics(self, sample_context):
        """Prompt includes all relevant training metrics."""
        prompt = get_assessment_prompt(sample_context)

        # Should include accuracy
        assert "62" in prompt or "0.62" in prompt
        # Should include final loss
        assert "0.38" in prompt or "38" in prompt

    def test_prompt_includes_backtest_metrics(self, sample_context):
        """Prompt includes all relevant backtest metrics."""
        prompt = get_assessment_prompt(sample_context)

        # Should include sharpe ratio
        assert "1.5" in prompt or "1.50" in prompt
        # Should include win rate
        assert "58" in prompt or "0.58" in prompt
        # Should include total trades
        assert "42" in prompt

    def test_prompt_includes_verdict_instructions(self, sample_context):
        """Prompt includes clear instructions for verdict."""
        prompt = get_assessment_prompt(sample_context)

        assert "promising" in prompt.lower()
        assert "mediocre" in prompt.lower()
        assert "poor" in prompt.lower()

    def test_prompt_mentions_save_assessment_tool(self, sample_context):
        """Prompt instructs Claude to use save_assessment tool."""
        prompt = get_assessment_prompt(sample_context)

        assert "save_assessment" in prompt

    def test_loss_improvement_calculated(self, sample_context):
        """Loss improvement is calculated and included in prompt."""
        prompt = get_assessment_prompt(sample_context)

        # Loss improvement = (0.75 - 0.38) / 0.75 = 0.493 = 49.3%
        # Should appear somewhere in the prompt
        assert "49" in prompt or "improvement" in prompt.lower()

    def test_handles_missing_initial_loss(self):
        """Handles missing initial_loss gracefully."""
        ctx = AssessmentContext(
            operation_id="op_test",
            strategy_name="test_strategy",
            strategy_path="/app/strategies/test.yaml",
            training_metrics={"accuracy": 0.6, "final_loss": 0.4},
            backtest_metrics={"sharpe_ratio": 1.0, "win_rate": 0.5},
        )

        # Should not raise
        prompt = get_assessment_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
