"""Tests for agent API endpoints.

Task 3.2: Verify brief parameter is accepted and propagated.
"""

from ktrdr.api.models.agent import AgentTriggerRequest


class TestAgentTriggerRequest:
    """Tests for AgentTriggerRequest model."""

    def test_accepts_brief_parameter(self):
        """Request should accept brief parameter."""
        request = AgentTriggerRequest(
            brief="Design a simple RSI strategy for EURUSD 1h."
        )
        assert request.brief == "Design a simple RSI strategy for EURUSD 1h."

    def test_brief_is_optional(self):
        """Brief parameter should be optional (default None)."""
        request = AgentTriggerRequest()
        assert request.brief is None

    def test_brief_with_model(self):
        """Brief should work alongside other parameters."""
        request = AgentTriggerRequest(
            brief="Test strategy with single indicator.",
            model="haiku",
            bypass_gates=True,
        )
        assert request.brief == "Test strategy with single indicator."
        assert request.model == "haiku"
        assert request.bypass_gates is True

    def test_empty_brief_allowed(self):
        """Empty string brief should be allowed."""
        request = AgentTriggerRequest(brief="")
        assert request.brief == ""
