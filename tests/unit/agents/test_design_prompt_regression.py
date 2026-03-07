"""Tests for regression mode documentation in design SDK prompt."""

from ktrdr.agents.design_sdk_prompt import DESIGN_SYSTEM_PROMPT


class TestDesignPromptRegressionGuidance:
    """Design prompt includes regression mode documentation."""

    def test_includes_regression_mode_documentation(self):
        """Prompt documents the output_format: regression option."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "regression" in prompt_lower
        assert "output_format" in prompt_lower

    def test_includes_forward_return_labels(self):
        """Prompt documents labels.source: forward_return and horizon."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "forward_return" in prompt_lower
        assert "horizon" in prompt_lower

    def test_includes_cost_model_documentation(self):
        """Prompt documents cost_model configuration."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "cost_model" in prompt_lower
        assert "round_trip_cost" in prompt_lower
        assert "min_edge_multiplier" in prompt_lower

    def test_includes_huber_loss_option(self):
        """Prompt documents Huber loss option."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "huber" in prompt_lower

    def test_includes_architecture_guidance(self):
        """Prompt includes guidance about larger architectures for regression."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "64" in prompt_lower  # [64, 32] recommendation

    def test_classification_documentation_preserved(self):
        """Existing classification documentation is still present."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "classification" in prompt_lower or "softmax" in prompt_lower
        # The indicator types should still be there
        assert "rsi" in prompt_lower
        assert "macd" in prompt_lower

    def test_regression_example_contains_key_fields(self):
        """The regression config examples contain all required fields."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        # Regression decisions example must include these
        assert "output_format: regression" in prompt_lower
        assert "source: forward_return" in prompt_lower
        assert "loss: huber" in prompt_lower
