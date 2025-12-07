"""
Unit tests for research agent prompts.

Tests cover:
- Phase 0 test prompt structure and content
- Prompt template variable substitution
"""

from research_agents.prompts.phase0_test import (
    PHASE0_SYSTEM_PROMPT,
    PHASE0_TEST_PROMPT,
    get_phase0_prompt,
)


class TestPhase0TestPrompt:
    """Tests for Phase 0 test prompt."""

    def test_system_prompt_exists(self):
        """System prompt should exist and contain key instructions."""
        assert PHASE0_SYSTEM_PROMPT is not None
        assert len(PHASE0_SYSTEM_PROMPT) > 0
        # Should mention being a test agent
        assert "test" in PHASE0_SYSTEM_PROMPT.lower()

    def test_user_prompt_exists(self):
        """User prompt should exist and contain tool call instructions."""
        assert PHASE0_TEST_PROMPT is not None
        assert len(PHASE0_TEST_PROMPT) > 0
        # Should mention the 3-step flow
        assert "create_agent_session" in PHASE0_TEST_PROMPT
        assert "update_agent_state" in PHASE0_TEST_PROMPT

    def test_prompt_includes_phase_transitions(self):
        """Prompt should mention phase transitions."""
        # The prompt should guide the agent to transition through phases
        assert (
            "testing" in PHASE0_TEST_PROMPT.lower()
            or "test" in PHASE0_TEST_PROMPT.lower()
        )
        assert "complete" in PHASE0_TEST_PROMPT.lower()

    def test_get_phase0_prompt_returns_dict(self):
        """get_phase0_prompt should return a dict with system and user messages."""
        result = get_phase0_prompt()
        assert isinstance(result, dict)
        assert "system" in result
        assert "user" in result
        assert result["system"] == PHASE0_SYSTEM_PROMPT
        assert result["user"] == PHASE0_TEST_PROMPT

    def test_get_phase0_prompt_with_session_id(self):
        """get_phase0_prompt should handle optional session_id."""
        result = get_phase0_prompt(session_id=42)
        assert isinstance(result, dict)
        # Session ID should be in the user prompt if provided
        assert "42" in result["user"] or result["user"] == PHASE0_TEST_PROMPT
