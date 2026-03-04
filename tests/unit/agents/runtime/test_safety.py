"""Tests for SafetyGuard — pre-invocation safety checks."""

from unittest.mock import MagicMock

from ktrdr.agents.runtime.safety import SafetyGuard, SafetyResult


class TestSafetyResult:
    """Tests for SafetyResult dataclass."""

    def test_allowed_result(self) -> None:
        result = SafetyResult(allowed=True)
        assert result.allowed is True
        assert result.reason is None

    def test_denied_result_with_reason(self) -> None:
        result = SafetyResult(allowed=False, reason="budget exceeded")
        assert result.allowed is False
        assert result.reason == "budget exceeded"


class TestSafetyGuardBudget:
    """Tests for budget checking."""

    def test_budget_ok_allows_invocation(self) -> None:
        """When budget has headroom, check passes."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
        )
        result = guard.check(estimated_cost=0.10, tools=["Read"], max_turns=5)
        assert result.allowed is True

    def test_budget_exceeded_blocks_invocation(self) -> None:
        """When budget is exhausted, check fails."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (
            False,
            "budget_exhausted ($0.05 remaining, need $0.50)",
        )

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
        )
        result = guard.check(estimated_cost=0.50, tools=["Read"], max_turns=5)
        assert result.allowed is False
        assert "budget" in result.reason.lower()

    def test_budget_check_passes_estimated_cost(self) -> None:
        """Estimated cost is forwarded to BudgetTracker.can_spend()."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
        )
        guard.check(estimated_cost=0.42, tools=["Read"], max_turns=5)
        budget_tracker.can_spend.assert_called_once_with(0.42)


class TestSafetyGuardTools:
    """Tests for tool allowlist checking."""

    def test_allowed_tools_pass(self) -> None:
        """Tools in the allowlist pass check."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read", "Glob", "Grep", "mcp__ktrdr__*"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["Read", "Glob"],
            max_turns=5,
        )
        assert result.allowed is True

    def test_disallowed_tool_blocks(self) -> None:
        """Tools not in the allowlist fail check."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read", "Glob"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["Read", "Write"],
            max_turns=5,
        )
        assert result.allowed is False
        assert "Write" in result.reason

    def test_wildcard_tool_matching(self) -> None:
        """Wildcard patterns like mcp__ktrdr__* match MCP tools."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["mcp__ktrdr__*", "Read"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["mcp__ktrdr__get_available_indicators", "mcp__ktrdr__save_strategy_config"],
            max_turns=5,
        )
        assert result.allowed is True

    def test_wildcard_does_not_match_other_prefix(self) -> None:
        """mcp__ktrdr__* does not match mcp__other__tool."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["mcp__ktrdr__*"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["mcp__other__dangerous_tool"],
            max_turns=5,
        )
        assert result.allowed is False

    def test_empty_tools_list_passes(self) -> None:
        """Empty tools list is allowed (no tools to check)."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
        )
        result = guard.check(estimated_cost=0.10, tools=[], max_turns=5)
        assert result.allowed is True


class TestSafetyGuardTurnLimit:
    """Tests for turn limit checking."""

    def test_turns_within_limit_pass(self) -> None:
        """Turns within configured limit pass."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
            max_turns_limit=25,
        )
        result = guard.check(estimated_cost=0.10, tools=["Read"], max_turns=20)
        assert result.allowed is True

    def test_turns_exceeding_limit_blocked(self) -> None:
        """Turns exceeding configured limit are blocked."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
            max_turns_limit=10,
        )
        result = guard.check(estimated_cost=0.10, tools=["Read"], max_turns=25)
        assert result.allowed is False
        assert "turn" in result.reason.lower()

    def test_default_turn_limit(self) -> None:
        """Default turn limit allows reasonable values."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["Read"],
        )
        # Default should allow 25 turns (design agent default)
        result = guard.check(estimated_cost=0.10, tools=["Read"], max_turns=25)
        assert result.allowed is True


class TestSafetyGuardWorkerTypes:
    """Tests for worker-type-specific configurations."""

    def test_design_agent_tool_set(self) -> None:
        """Design agents get MCP + read tools."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["mcp__ktrdr__*", "Read", "Glob", "Grep"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["mcp__ktrdr__get_available_indicators", "Read", "Grep"],
            max_turns=5,
        )
        assert result.allowed is True

    def test_assessment_agent_no_write(self) -> None:
        """Assessment agents don't get Write tool."""
        budget_tracker = MagicMock()
        budget_tracker.can_spend.return_value = (True, "ok")

        guard = SafetyGuard(
            budget_tracker=budget_tracker,
            allowed_tools=["mcp__ktrdr__*", "Read", "Glob", "Grep"],
        )
        result = guard.check(
            estimated_cost=0.10,
            tools=["Write"],
            max_turns=5,
        )
        assert result.allowed is False
