"""SafetyGuard — pre-invocation safety checks for agent runtime calls.

Ported from agent-memory's runtime/safety.py, adapted for ktrdr:
- Uses ktrdr's BudgetTracker instead of agent-memory's CostTracker
- No circuit breaker (BudgetTracker handles daily limits)
- Wildcard support for MCP tool patterns (e.g., mcp__ktrdr__*)
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Protocol

from ktrdr import get_logger


class BudgetChecker(Protocol):
    """Protocol for budget checking — matches BudgetTracker.can_spend()."""

    def can_spend(self, estimated_amount: float) -> tuple[bool, str]: ...


logger = get_logger(__name__)

# Default max turns if not specified
DEFAULT_MAX_TURNS_LIMIT = 30


@dataclass
class SafetyResult:
    """Result of a safety check."""

    allowed: bool
    reason: str | None = None


class SafetyGuard:
    """Pre-invocation safety checks for agent runtime calls.

    Checks before each invoke():
    1. Budget cap: cumulative cost hasn't exceeded limit
    2. Tool allowlist: only permitted tools are passed to the SDK
    3. Turn limit: max_turns is within configured bounds
    """

    def __init__(
        self,
        *,
        budget_tracker: BudgetChecker,
        allowed_tools: list[str],
        max_turns_limit: int = DEFAULT_MAX_TURNS_LIMIT,
    ) -> None:
        """Initialize the safety guard.

        Args:
            budget_tracker: ktrdr BudgetTracker instance (has can_spend method).
            allowed_tools: List of allowed tool names. Supports fnmatch wildcards
                (e.g., "mcp__ktrdr__*" matches all ktrdr MCP tools).
            max_turns_limit: Maximum allowed turns per invocation.
        """
        self._budget_tracker = budget_tracker
        self._allowed_tools = allowed_tools
        self._max_turns_limit = max_turns_limit

    def check(
        self,
        *,
        estimated_cost: float,
        tools: list[str],
        max_turns: int,
    ) -> SafetyResult:
        """Run all pre-invocation safety checks.

        Args:
            estimated_cost: Estimated cost in dollars for this invocation.
            tools: List of tool names the agent will use.
            max_turns: Requested max turns for this invocation.

        Returns:
            SafetyResult indicating whether the invocation is allowed.
        """
        # 1. Budget check
        can_spend, reason = self._budget_tracker.can_spend(estimated_cost)
        if not can_spend:
            logger.warning("Safety: budget check failed — %s", reason)
            return SafetyResult(allowed=False, reason=f"Budget check failed: {reason}")

        # 2. Tool allowlist check
        disallowed = [t for t in tools if not self._is_tool_allowed(t)]
        if disallowed:
            msg = (
                f"Disallowed tools: {', '.join(disallowed)}. "
                f"Permitted: {', '.join(sorted(self._allowed_tools))}"
            )
            logger.warning("Safety: tool check failed — %s", msg)
            return SafetyResult(allowed=False, reason=msg)

        # 3. Turn limit check
        if max_turns > self._max_turns_limit:
            msg = (
                f"Requested {max_turns} turns exceeds limit of {self._max_turns_limit}"
            )
            logger.warning("Safety: turn limit check failed — %s", msg)
            return SafetyResult(allowed=False, reason=msg)

        return SafetyResult(allowed=True)

    def _is_tool_allowed(self, tool: str) -> bool:
        """Check if a tool name matches any allowed pattern.

        Supports fnmatch wildcards (e.g., mcp__ktrdr__* matches
        mcp__ktrdr__get_available_indicators).
        """
        return any(fnmatch.fnmatch(tool, pattern) for pattern in self._allowed_tools)
