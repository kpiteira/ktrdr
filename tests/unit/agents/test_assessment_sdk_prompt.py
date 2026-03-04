"""Unit tests for assessment agent system prompt.

Validates the prompt defines a clear analysis rubric, references
the save_assessment MCP tool, and includes hypothesis generation guidance.
"""

from ktrdr.agents.assessment_sdk_prompt import ASSESSMENT_SYSTEM_PROMPT


class TestAssessmentSystemPrompt:
    """Tests for the assessment agent system prompt content."""

    def test_prompt_defines_analyst_role(self):
        """Prompt identifies the agent as a strategy analyst."""
        assert "analyst" in ASSESSMENT_SYSTEM_PROMPT.lower()

    def test_prompt_references_save_assessment_tool(self):
        """Prompt references save_assessment as the output tool."""
        assert "save_assessment" in ASSESSMENT_SYSTEM_PROMPT

    def test_prompt_defines_verdict_categories(self):
        """Prompt defines the three verdict categories."""
        assert "promising" in ASSESSMENT_SYSTEM_PROMPT
        assert "neutral" in ASSESSMENT_SYSTEM_PROMPT
        assert "poor" in ASSESSMENT_SYSTEM_PROMPT

    def test_prompt_includes_sharpe_ratio_guidance(self):
        """Prompt references Sharpe ratio as an evaluation metric."""
        assert "sharpe" in ASSESSMENT_SYSTEM_PROMPT.lower()

    def test_prompt_includes_drawdown_guidance(self):
        """Prompt references drawdown as an evaluation metric."""
        assert "drawdown" in ASSESSMENT_SYSTEM_PROMPT.lower()

    def test_prompt_includes_trade_frequency_guidance(self):
        """Prompt references trade count/frequency as an evaluation metric."""
        assert "trade" in ASSESSMENT_SYSTEM_PROMPT.lower()

    def test_prompt_includes_hypothesis_guidance(self):
        """Prompt includes guidance on generating hypotheses."""
        assert "hypothes" in ASSESSMENT_SYSTEM_PROMPT.lower()

    def test_prompt_references_filesystem_access(self):
        """Prompt mentions filesystem paths for memory/experiments."""
        assert (
            "/app/memory" in ASSESSMENT_SYSTEM_PROMPT
            or "memory" in ASSESSMENT_SYSTEM_PROMPT
        )

    def test_prompt_references_mcp_discovery_tools(self):
        """Prompt mentions MCP tools available for data exploration."""
        assert (
            "get_model_performance" in ASSESSMENT_SYSTEM_PROMPT
            or "MCP" in ASSESSMENT_SYSTEM_PROMPT
        )

    def test_prompt_is_concise(self):
        """Prompt is slim (~60-100 lines), not a massive context dump."""
        line_count = len(ASSESSMENT_SYSTEM_PROMPT.strip().split("\n"))
        assert line_count < 120, f"Prompt is {line_count} lines — should be under 120"
        assert line_count > 30, (
            f"Prompt is only {line_count} lines — too short to be useful"
        )

    def test_prompt_does_not_contain_indicator_lists(self):
        """Prompt should NOT pre-load indicator lists (D7: discover via MCP)."""
        # These would indicate a bloated prompt that pre-loads context
        assert "RSI(period" not in ASSESSMENT_SYSTEM_PROMPT
        assert "MACD(fast" not in ASSESSMENT_SYSTEM_PROMPT
