"""Tests for v3 strategy format in prompts.

Validates that the strategy generation prompt:
1. Contains v3 keywords (indicators dict, nn_inputs)
2. Does NOT contain v2 keywords (feature_id)
3. Example in prompt is valid v3 YAML
"""

import re

import yaml


class TestPromptV3Keywords:
    """Test that prompt contains v3 markers and not v2 markers."""

    def test_prompt_contains_nn_inputs(self):
        """Prompt must mention nn_inputs section."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        assert "nn_inputs" in SYSTEM_PROMPT_TEMPLATE, "Prompt must contain 'nn_inputs'"

    def test_prompt_contains_indicators_dict_explanation(self):
        """Prompt must explain that indicators is a dict."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        # Should explain indicators as a dict, not a list
        assert "indicators:" in SYSTEM_PROMPT_TEMPLATE
        # Should explain it's keyed by indicator_id
        assert (
            "indicator_id" in SYSTEM_PROMPT_TEMPLATE.lower()
            or "keyed by" in SYSTEM_PROMPT_TEMPLATE.lower()
        )

    def test_prompt_contains_fuzzy_sets_explanation(self):
        """Prompt must explain fuzzy_sets with indicator reference."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        assert "fuzzy_sets:" in SYSTEM_PROMPT_TEMPLATE
        # Should explain the indicator reference
        assert (
            "indicator:" in SYSTEM_PROMPT_TEMPLATE
            or "references" in SYSTEM_PROMPT_TEMPLATE.lower()
        )

    def test_prompt_does_not_contain_feature_id(self):
        """Prompt must NOT contain v2 feature_id terminology."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        # feature_id is v2 terminology that should not appear
        assert (
            "feature_id" not in SYSTEM_PROMPT_TEMPLATE
        ), "Prompt must not contain v2 'feature_id'"


class TestPromptYAMLExample:
    """Test that the YAML example in the prompt is valid v3."""

    def _extract_yaml_from_prompt(self, prompt: str) -> str | None:
        """Extract first YAML code block from prompt."""
        # Match ```yaml ... ``` blocks
        yaml_match = re.search(r"```yaml\n(.+?)```", prompt, re.DOTALL)
        if yaml_match:
            return yaml_match.group(1)
        return None

    def test_example_parses_as_valid_yaml(self):
        """Example in prompt must be valid YAML."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        yaml_str = self._extract_yaml_from_prompt(SYSTEM_PROMPT_TEMPLATE)
        assert yaml_str is not None, "Prompt must contain a YAML example"

        # Should parse without error
        config = yaml.safe_load(yaml_str)
        assert config is not None

    def test_example_has_indicators_as_dict(self):
        """Example indicators must be a dict, not a list."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        yaml_str = self._extract_yaml_from_prompt(SYSTEM_PROMPT_TEMPLATE)
        config = yaml.safe_load(yaml_str)

        assert "indicators" in config, "Example must have indicators section"
        assert isinstance(
            config["indicators"], dict
        ), "indicators must be a dict (v3 format), not a list"

    def test_example_has_nn_inputs(self):
        """Example must have nn_inputs section."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        yaml_str = self._extract_yaml_from_prompt(SYSTEM_PROMPT_TEMPLATE)
        config = yaml.safe_load(yaml_str)

        assert "nn_inputs" in config, "Example must have nn_inputs section (v3 format)"
        assert isinstance(config["nn_inputs"], list), "nn_inputs must be a list"

    def test_example_fuzzy_sets_have_indicator_reference(self):
        """Example fuzzy_sets must reference indicators."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        yaml_str = self._extract_yaml_from_prompt(SYSTEM_PROMPT_TEMPLATE)
        config = yaml.safe_load(yaml_str)

        assert "fuzzy_sets" in config, "Example must have fuzzy_sets section"
        assert isinstance(config["fuzzy_sets"], dict)

        # At least one fuzzy set should have 'indicator' reference
        has_indicator_ref = any(
            "indicator" in fs for fs in config["fuzzy_sets"].values()
        )
        assert has_indicator_ref, "fuzzy_sets must have 'indicator' field (v3 format)"

    def test_example_validates_as_v3_config(self):
        """Example must be parseable as StrategyConfigurationV3."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE
        from ktrdr.config.models import StrategyConfigurationV3

        yaml_str = self._extract_yaml_from_prompt(SYSTEM_PROMPT_TEMPLATE)
        config = yaml.safe_load(yaml_str)

        # Should parse without error as v3 config
        parsed = StrategyConfigurationV3(**config)
        assert parsed.name is not None
        assert parsed.nn_inputs is not None
        assert len(parsed.nn_inputs) > 0


class TestCriticalV3Rules:
    """Test that prompt contains critical v3 rules summary (issue #253).

    These rules prevent Claude from wasting tokens on trial-and-error validation:
    - indicators is a DICT, not a list
    - fuzzy_sets MUST have indicator field
    - nn_inputs section is REQUIRED
    - Indicator type is case-sensitive
    """

    def test_prompt_has_critical_v3_rules_summary(self):
        """Prompt must have an explicit Critical v3 rules summary (issue #253)."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        # Issue #253 specifically asks for a "Critical v3 rules" section
        # that lists the rules in a numbered format for quick reference
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()

        # Should have a section about critical v3 rules
        assert (
            "critical v3 rules" in prompt_lower or "critical rules" in prompt_lower
        ), "Prompt must have a 'Critical v3 rules' summary section"

    def test_emphasizes_indicators_dict_not_list(self):
        """Prompt must explicitly state indicators is DICT, NOT list."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Should explicitly say NOT a list
        assert (
            "not a list" in prompt_lower or "not list" in prompt_lower
        ), "Prompt must explicitly say 'indicators' is NOT a list"

    def test_emphasizes_fuzzy_sets_indicator_field_required(self):
        """Prompt must state fuzzy_sets MUST have indicator field."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Should mention that indicator field is required in fuzzy_sets
        assert (
            "fuzzy" in prompt_lower
            and "indicator" in prompt_lower
            and ("must" in prompt_lower or "required" in prompt_lower)
        ), "Prompt must state fuzzy_sets MUST have indicator field"

    def test_emphasizes_nn_inputs_required(self):
        """Prompt must explicitly state nn_inputs is REQUIRED."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Should say nn_inputs is required
        assert (
            "nn_inputs" in prompt_lower and "required" in prompt_lower
        ), "Prompt must state nn_inputs is REQUIRED"

    def test_emphasizes_indicator_type_case_sensitive(self):
        """Prompt must warn about case sensitivity for indicator type."""
        from ktrdr.agents.prompts import SYSTEM_PROMPT_TEMPLATE

        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Should mention case sensitivity
        assert (
            "case" in prompt_lower and "sensitive" in prompt_lower
        ), "Prompt must warn about case sensitivity for indicator type"
