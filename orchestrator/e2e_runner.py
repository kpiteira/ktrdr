"""E2E test runner for executing E2E scenarios via Claude Code.

Handles E2E test execution by constructing prompts, invoking Claude Code
in the sandbox, and parsing structured results including diagnosis and
fix suggestions for failures.
"""

import re
import time
from dataclasses import dataclass
from typing import Literal

from opentelemetry import trace

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.sandbox import SandboxManager


@dataclass
class E2EResult:
    """Result from an E2E test execution.

    Captures the outcome of running E2E tests via Claude Code, including
    status, metrics, and failure analysis.

    Status values:
        passed: All E2E tests passed
        failed: One or more E2E tests failed
        unclear: Could not determine test outcome
    """

    status: Literal["passed", "failed", "unclear"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    diagnosis: str | None = None
    fix_suggestion: str | None = None
    is_fixable: bool = False
    raw_output: str = ""


async def run_e2e_tests(
    milestone_id: str,
    e2e_scenario: str,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
) -> E2EResult:
    """Execute E2E tests via Claude Code.

    Invokes Claude Code with the E2E test scenario, then parses the
    structured output to determine pass/fail status and extract any
    failure diagnosis.

    Args:
        milestone_id: Identifier for the milestone being tested
        e2e_scenario: The E2E test scenario text (from plan markdown)
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        tracer: OpenTelemetry tracer for creating spans

    Returns:
        E2EResult with test outcome and analysis
    """
    prompt = _build_e2e_prompt(milestone_id, e2e_scenario)

    with tracer.start_as_current_span("orchestrator.e2e_test") as span:
        span.set_attribute("milestone.id", milestone_id)

        start_time = time.time()
        claude_result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=30,  # E2E tests need fewer turns than full tasks
            timeout=config.task_timeout_seconds,
        )
        duration = time.time() - start_time

        # Parse result
        output = claude_result.result
        status = _parse_e2e_status(output)
        diagnosis = _extract_diagnosis(output) if status == "failed" else None
        is_fixable = _detect_fixable(output)
        fix_suggestion = _extract_fix_plan(output) if is_fixable else None

        # Set span attributes
        span.set_attribute("e2e.status", status)
        span.set_attribute("e2e.is_fixable", is_fixable)

        # Record metrics (safe if counter not yet defined - see Task 5.5)
        if hasattr(telemetry, "e2e_tests_counter"):
            telemetry.e2e_tests_counter.add(
                1, {"milestone": milestone_id, "status": status}
            )

        return E2EResult(
            status=status,
            duration_seconds=duration,
            tokens_used=_estimate_tokens(claude_result.total_cost_usd),
            cost_usd=claude_result.total_cost_usd,
            diagnosis=diagnosis,
            fix_suggestion=fix_suggestion,
            is_fixable=is_fixable,
            raw_output=output,
        )


def _build_e2e_prompt(milestone_id: str, e2e_scenario: str) -> str:
    """Build the prompt for E2E test execution.

    Instructs Claude to execute the E2E scenario and report results
    in a structured format that can be parsed.

    Args:
        milestone_id: Identifier for the milestone
        e2e_scenario: The test scenario text

    Returns:
        Formatted prompt string
    """
    return f"""Execute the following E2E test scenario for milestone {milestone_id}.
Run each command, observe results, and determine if the test passes.

{e2e_scenario}

After executing, report:
- E2E_STATUS: passed | failed
- If failed: DIAGNOSIS: <root cause analysis>
- If failed: FIXABLE: yes | no
- If fixable: FIX_PLAN: <specific changes to make>
- If not fixable: OPTIONS: <options> RECOMMENDATION: <recommendation>
"""


def _parse_e2e_status(output: str) -> Literal["passed", "failed", "unclear"]:
    """Parse E2E test status from Claude output.

    First checks for explicit E2E_STATUS marker, then falls back to
    heuristic detection based on common success/failure patterns.

    Args:
        output: Raw output text from Claude Code

    Returns:
        Status string: 'passed', 'failed', or 'unclear'
    """
    # Check for explicit marker (highest priority)
    if "E2E_STATUS: passed" in output:
        return "passed"
    if "E2E_STATUS: failed" in output:
        return "failed"

    # Heuristic detection (lower priority)
    output_lower = output.lower()

    # Success heuristics
    if "all tests pass" in output_lower or "✓" in output:
        return "passed"

    # Failure heuristics
    if "test failed" in output_lower or "error" in output_lower:
        return "failed"

    return "unclear"


def _extract_diagnosis(output: str) -> str | None:
    """Extract failure diagnosis from Claude output.

    Looks for DIAGNOSIS: marker and extracts the text that follows.

    Args:
        output: Raw output text from Claude Code

    Returns:
        Diagnosis text if found, None otherwise
    """
    match = re.search(r"DIAGNOSIS:\s*(.+?)(?:\n(?=[A-Z_]+:)|\Z)", output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_fix_plan(output: str) -> str | None:
    """Extract fix plan from Claude output.

    Looks for FIX_PLAN: marker and extracts the text that follows.

    Args:
        output: Raw output text from Claude Code

    Returns:
        Fix plan text if found, None otherwise
    """
    match = re.search(r"FIX_PLAN:\s*(.+?)(?:\n(?=[A-Z_]+:)|\Z)", output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _detect_fixable(output: str) -> bool:
    """Detect if the E2E failure is fixable.

    Looks for FIXABLE: yes marker in the output.

    Args:
        output: Raw output text from Claude Code

    Returns:
        True if fixable, False otherwise
    """
    return "FIXABLE: yes" in output


def _estimate_tokens(cost_usd: float) -> int:
    """Estimate token count from cost.

    Rough estimate based on Claude pricing (~$0.01 per 1000 tokens average).

    Args:
        cost_usd: Total cost in USD from Claude

    Returns:
        Estimated token count
    """
    if cost_usd <= 0:
        return 0
    return int(cost_usd * 100000)  # $0.01 = 1000 tokens
