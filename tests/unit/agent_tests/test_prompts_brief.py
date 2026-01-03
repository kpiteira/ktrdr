"""Tests for brief injection into designer prompts.

Task 3.4: Verify brief is included in prompt when provided.
"""

from ktrdr.agents.prompts import TriggerReason, get_strategy_designer_prompt


class TestBriefInjection:
    """Tests for brief parameter in prompts."""

    def test_brief_included_in_prompt_when_provided(self):
        """Brief should appear in prompt when provided."""
        prompt_data = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test",
            phase="designing",
            brief="Design a simple RSI strategy for EURUSD 1h only.",
        )

        # Brief should be in the user prompt
        assert "RSI strategy" in prompt_data["user"]
        assert "EURUSD 1h" in prompt_data["user"]

    def test_brief_section_omitted_when_none(self):
        """Brief section should not appear when brief is None."""
        prompt_data = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test",
            phase="designing",
            brief=None,
        )

        # Should not have "Research Brief" section
        assert "Research Brief" not in prompt_data["user"]

    def test_brief_text_appears_verbatim(self):
        """Brief text should appear exactly as provided."""
        brief_text = "Use RSI indicator only. Single symbol. Single timeframe."

        prompt_data = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test",
            phase="designing",
            brief=brief_text,
        )

        # Brief should appear verbatim
        assert brief_text in prompt_data["user"]

    def test_brief_has_section_header(self):
        """Brief should have clear section header."""
        prompt_data = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test",
            phase="designing",
            brief="Test brief content.",
        )

        # Should have Research Brief header
        assert "Research Brief" in prompt_data["user"]

    def test_empty_brief_treated_as_none(self):
        """Empty string brief should be treated like None."""
        prompt_data = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test",
            phase="designing",
            brief="",
        )

        # Empty brief should not create section
        assert "Research Brief" not in prompt_data["user"]
