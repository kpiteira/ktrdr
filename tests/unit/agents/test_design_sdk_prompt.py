"""Tests for the design agent SDK system prompt.

Validates the prompt follows D7 constraints:
- Slim (~60 lines, under 100 max)
- References MCP tools by name
- Does NOT contain indicator lists or YAML templates
- Defines clear workflow and output contract
"""

from ktrdr.agents.design_sdk_prompt import DESIGN_SYSTEM_PROMPT


class TestDesignSystemPrompt:
    """Tests for DESIGN_SYSTEM_PROMPT content and constraints."""

    def test_prompt_is_under_100_lines(self):
        """System prompt stays slim — under 100 lines per D7."""
        line_count = len(DESIGN_SYSTEM_PROMPT.strip().splitlines())
        assert line_count <= 100, f"Prompt is {line_count} lines, should be ≤100"

    def test_prompt_references_save_strategy_config(self):
        """Prompt mentions save_strategy_config MCP tool."""
        assert "save_strategy_config" in DESIGN_SYSTEM_PROMPT

    def test_prompt_references_validate_strategy(self):
        """Prompt mentions validate_strategy MCP tool."""
        assert "validate_strategy" in DESIGN_SYSTEM_PROMPT

    def test_prompt_references_get_available_indicators(self):
        """Prompt mentions get_available_indicators MCP tool."""
        assert "get_available_indicators" in DESIGN_SYSTEM_PROMPT

    def test_prompt_does_not_contain_yaml_template(self):
        """Prompt must NOT contain pre-loaded YAML templates (D7)."""
        # YAML template markers from the old prompt
        assert "training_data:" not in DESIGN_SYSTEM_PROMPT
        assert "fuzzy_sets:" not in DESIGN_SYSTEM_PROMPT
        assert "nn_inputs:" not in DESIGN_SYSTEM_PROMPT
        assert "hidden_layers:" not in DESIGN_SYSTEM_PROMPT

    def test_prompt_does_not_contain_indicator_lists(self):
        """Prompt must NOT contain pre-loaded indicator lists (D7)."""
        # Specific indicator names that would indicate pre-loading
        assert "RSI(period" not in DESIGN_SYSTEM_PROMPT
        assert "MACD(fast" not in DESIGN_SYSTEM_PROMPT
        assert "bbands" not in DESIGN_SYSTEM_PROMPT.lower()

    def test_prompt_does_not_contain_enum_values(self):
        """Prompt must NOT contain pre-loaded enum value lists (D7)."""
        assert "multi_symbol" not in DESIGN_SYSTEM_PROMPT
        assert "group_restricted" not in DESIGN_SYSTEM_PROMPT
        assert "training_only" not in DESIGN_SYSTEM_PROMPT

    def test_prompt_defines_workflow(self):
        """Prompt defines the Discover → Design → Validate → Save workflow."""
        assert "Discover" in DESIGN_SYSTEM_PROMPT
        assert "Design" in DESIGN_SYSTEM_PROMPT
        assert "Validate" in DESIGN_SYSTEM_PROMPT
        assert "Save" in DESIGN_SYSTEM_PROMPT

    def test_prompt_defines_output_contract(self):
        """Prompt defines when the agent is 'done'."""
        # The output contract: calling save_strategy_config means done
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "done" in prompt_lower or "complete" in prompt_lower

    def test_prompt_references_filesystem_discovery(self):
        """Prompt tells agent to read example strategies from filesystem."""
        assert "/app/strategies" in DESIGN_SYSTEM_PROMPT

    def test_prompt_prohibits_write_tool_for_strategies(self):
        """Prompt tells agent NOT to use Write tool for strategy files."""
        prompt_lower = DESIGN_SYSTEM_PROMPT.lower()
        assert "write" in prompt_lower  # Must mention Write tool prohibition
