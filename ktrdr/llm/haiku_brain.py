"""Haiku Brain - All orchestration intelligence via Claude Haiku.

This module replaces brittle regex-based parsing with Claude Haiku API calls
for semantic understanding of milestone plans and task execution results.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Cache for the Claude CLI path
_claude_cli_path: str | None = None


def find_claude_cli() -> str | None:
    """Find the Claude CLI executable.

    Checks:
    1. shutil.which("claude") - standard PATH lookup
    2. ~/.claude/local/claude - common installation location

    Returns:
        Path to the Claude CLI, or None if not found.
    """
    global _claude_cli_path

    # Return cached path if already found
    if _claude_cli_path is not None:
        return _claude_cli_path

    # Try PATH first
    path_result = shutil.which("claude")
    if path_result:
        _claude_cli_path = path_result
        return _claude_cli_path

    # Try common installation locations
    home = Path.home()
    common_locations = [
        home / ".claude" / "local" / "claude",
        home / ".claude" / "bin" / "claude",
    ]

    for location in common_locations:
        if location.exists() and os.access(location, os.X_OK):
            _claude_cli_path = str(location)
            return _claude_cli_path

    return None


@dataclass
class ExtractedTask:
    """A task extracted from a milestone plan.

    Contains minimal fields needed for orchestration. The /ktask skill
    reads detailed fields (file_path, acceptance_criteria) from the plan directly.
    """

    id: str
    title: str
    description: str


@dataclass
class InterpretationResult:
    """Result of interpreting Claude Code task execution output.

    Provides structured information about what happened during task execution,
    including whether human input is needed and what questions/options to present.
    """

    status: Literal["completed", "failed", "needs_help"]
    summary: str
    error: str | None
    question: str | None
    options: list[str] | None
    recommendation: str | None


@dataclass
class RetryDecision:
    """Decision on whether to retry a failed task or escalate to human.

    When decision is "retry", guidance_for_retry provides suggestions for
    the next attempt. When "escalate", guidance_for_retry is None.
    """

    decision: Literal["retry", "escalate"]
    reason: str
    guidance_for_retry: str | None  # Suggestion for next attempt


@dataclass
class ParsedAssessment:
    """Structured data extracted from agent's assessment output."""

    verdict: str  # "strong_signal" | "weak_signal" | "no_signal" | "overfit"
    observations: list[str]
    hypotheses: list[dict]  # [{"text": "...", "status": "untested"}]
    limitations: list[str]
    capability_requests: list[str]
    tested_hypothesis_ids: list[str]  # H_001, H_002, etc. if mentioned
    raw_text: str  # Original output for reference

    @classmethod
    def empty(cls, raw_text: str) -> "ParsedAssessment":
        """Create empty result when parsing fails."""
        return cls(
            verdict="unknown",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text=raw_text,
        )


# Prompt for extracting tasks from a milestone plan
# From Architecture doc Appendix: Prompt 1
EXTRACT_TASKS_PROMPT = """You are parsing a milestone plan to extract tasks for an orchestrator to execute.

CRITICAL: Only extract REAL tasks that should be executed. Ignore:
- Tasks mentioned inside fenced code blocks (```...```)
- Tasks in "Example" or "E2E Test" sections that are illustrative, not actionable
- Duplicate mentions of the same task

Return a JSON array of tasks. Each task has:
- id: The task number (e.g., "1.1", "2.3")
- title: The task title
- description: Brief description of what to implement

Example output:
[
  {{"id": "1.1", "title": "Create data model", "description": "..."}},
  {{"id": "1.2", "title": "Add API endpoint", "description": "..."}}
]

Return ONLY the JSON array, no other text.

Plan content:
{plan_content}
"""

# Prompt for interpreting task execution results
# From Architecture doc Appendix: Prompt 2
INTERPRET_RESULT_PROMPT = """Analyze this Claude Code output and determine the task status.

Return a JSON object:
{{
  "status": "completed" | "failed" | "needs_help",
  "summary": "Brief description of what happened",
  "error": "Error details if failed, null otherwise",
  "question": "The question Claude is asking, if needs_help",
  "options": ["Option A", "Option B"] or null,
  "recommendation": "Claude's recommended option, if stated"
}}

Determine status as:
- "completed": Task finished successfully. Look for task summaries, passing tests, successful commits.
- "failed": Task encountered an error it couldn't recover from. Look for unresolved errors, failed tests that weren't fixed, explicit failure messages.
- "needs_help": Claude is asking a question or needs human decision. Look for:
  - AskUserQuestion tool usage
  - Questions like "Which approach should I take?"
  - Statements like "I need clarification" or "I'm blocked"
  - Multiple options presented for human to choose

When in doubt between "completed" and "needs_help", prefer "needs_help" — it's safer to ask than to assume.

Return ONLY the JSON, no other text.

Claude Code output:
{output}
"""

# Prompt for deciding retry vs escalate
# From Architecture doc Appendix: Prompt 3
RETRY_ESCALATE_PROMPT = """You are deciding whether to retry a failed task or escalate to a human.

Task: {task_id} - {task_title}

Attempt history:
{attempt_history}

Current attempt count: {attempt_count}

Decide: Should we retry or escalate?

RETRY when:
- The error is different from previous attempts (making progress)
- The error seems transient or fixable (import errors, typos, missing files)
- Only 1-2 attempts so far and the errors aren't identical

ESCALATE when:
- Same or very similar error 3+ times (stuck in a loop)
- The error indicates a design/architecture issue, not a coding bug
- Claude explicitly said it needs human input or is confused
- The error is about something Claude can't fix (permissions, external service, missing context)

Return a JSON object:
{{
  "decision": "retry" | "escalate",
  "reason": "Brief explanation of why",
  "guidance_for_retry": "If retrying, what to tell Claude differently (null if escalating)"
}}

Return ONLY the JSON, no other text.
"""

# Prompt for parsing agent assessment output
PARSE_ASSESSMENT_PROMPT = """Extract structured assessment data from this agent output.

The output may be structured (with headers like "### Verdict") or prose.
Extract what you can, using reasonable defaults for missing fields.

Return a JSON object:
{{
  "verdict": "strong_signal" | "weak_signal" | "no_signal" | "overfit",
  "observations": ["observation 1", "observation 2", ...],
  "hypotheses": [{{"text": "hypothesis text", "status": "untested"}}, ...],
  "limitations": ["limitation 1", ...],
  "capability_requests": ["request 1", ...],
  "tested_hypothesis_ids": ["H_001", ...] // if existing hypotheses are referenced
}}

Guidelines:
- verdict: Classify based on test accuracy and generalization
  - "strong_signal": test accuracy >= 60%, small val-test gap
  - "weak_signal": test accuracy 55-60%
  - "no_signal": test accuracy <= 55% or large val-test gap
  - "overfit": high validation, low test (gap > 10pp)
- observations: Key factual statements about results
- hypotheses: New ideas generated for future testing
- limitations: What wasn't tested, caveats
- capability_requests: Things the agent wishes it could try
- tested_hypothesis_ids: Look for references to existing hypotheses like "H_001",
  "H_002", etc. If the agent mentions testing or validating a specific hypothesis
  ID, include it here. Examples:
  - "Testing hypothesis H_001" → include "H_001"
  - "H_002 was validated by this experiment" → include "H_002"
  - "This refutes H_003" → include "H_003"
  - "H_004 inconclusive" → include "H_004"
  Only include IDs explicitly mentioned, not hypotheses from new ideas.

Return ONLY the JSON, no other text.

Agent output:
{output}
"""


class HaikuBrain:
    """All orchestration intelligence via Claude Haiku.

    Uses Claude Code CLI with Haiku model for:
    - Extracting tasks from milestone plans (ignoring code blocks)
    - Interpreting task execution results (planned for M2)
    - Deciding retry vs escalate (planned for M3)
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """Initialize the Haiku Brain.

        Args:
            model: The Claude model to use. Defaults to Haiku 4.5.
        """
        self.model = model

    def extract_tasks(self, plan_content: str) -> list[ExtractedTask]:
        """Extract executable tasks from a milestone plan.

        Uses Haiku to semantically understand the plan and identify real tasks,
        ignoring tasks inside code blocks, example sections, etc.

        Args:
            plan_content: The full text content of the milestone plan.

        Returns:
            List of ExtractedTask with id, title, and description.

        Raises:
            ValueError: If the response cannot be parsed as valid task JSON.
            RuntimeError: If Claude CLI invocation fails.
        """
        prompt = EXTRACT_TASKS_PROMPT.format(plan_content=plan_content)
        response = self._invoke_haiku(prompt)
        return self._parse_tasks(response)

    def _invoke_haiku(self, prompt: str) -> str:
        """Invoke Claude CLI with Haiku model.

        Args:
            prompt: The prompt to send to Haiku.

        Returns:
            The response text from Haiku.

        Raises:
            RuntimeError: If Claude CLI is not found or returns non-zero.
        """
        claude_path = find_claude_cli()
        if claude_path is None:
            raise RuntimeError(
                "Claude CLI not found. Ensure Claude Code is installed and in PATH."
            )

        result = subprocess.run(
            [
                claude_path,
                "--model",
                self.model,
                "--print",
                "--no-session-persistence",
                "--allowedTools",
                "",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error_text = result.stderr or result.stdout or "unknown error"
            raise RuntimeError(f"Claude CLI failed: {error_text[:200]}")

        return result.stdout

    def _parse_tasks(self, response: str) -> list[ExtractedTask]:
        """Parse Haiku response into a list of ExtractedTask.

        Handles JSON that may be wrapped in markdown code blocks.

        Args:
            response: The raw response from Haiku.

        Returns:
            List of ExtractedTask parsed from the response.

        Raises:
            ValueError: If the response cannot be parsed as valid task JSON.
        """
        # Try direct JSON parse first
        try:
            data = json.loads(response.strip())
            return [ExtractedTask(**t) for t in data]
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract JSON from markdown code block
        json_str = self._extract_json_array(response)
        if json_str is not None:
            try:
                data = json.loads(json_str)
                return [ExtractedTask(**t) for t in data]
            except (json.JSONDecodeError, TypeError):
                pass

        raise ValueError(
            f"Failed to parse tasks from Haiku response. Response was: {response[:200]}"
        )

    def _extract_json_array(self, text: str) -> str | None:
        """Extract a JSON array from text that may contain markdown.

        Handles cases where JSON is wrapped in ```json ... ``` blocks.

        Args:
            text: The text potentially containing a JSON array.

        Returns:
            The JSON array string if found, None otherwise.
        """
        # Try to find JSON array in markdown code block
        code_block_pattern = r"```(?:json)?\s*(\[[\s\S]*?\])\s*```"
        match = re.search(code_block_pattern, text)
        if match:
            return match.group(1)

        # Try to find bare JSON array using balanced bracket matching
        start = text.find("[")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if in_string:
                # When inside a string, handle escapes and closing quote
                if escape_next:
                    # Current character is escaped; consume it as literal
                    escape_next = False
                    continue

                if char == "\\":
                    # Next character is escaped
                    escape_next = True
                    continue

                if char == '"':
                    # End of string
                    in_string = False
                # Ignore all other characters while in a string
                continue

            # Not currently inside a string
            if char == '"':
                in_string = True
                continue

            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None

    def interpret_result(self, output: str) -> InterpretationResult:
        """Interpret Claude Code output to determine task status.

        Uses Haiku to semantically understand the task execution output and
        determine whether the task completed, failed, or needs human help.

        No truncation - full output is sent to Haiku (per Decision 8).

        Args:
            output: The full text output from Claude Code task execution.

        Returns:
            InterpretationResult with status, summary, and any question/options.
        """
        prompt = INTERPRET_RESULT_PROMPT.format(output=output)
        try:
            response = self._invoke_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            # Conservative fallback: if Haiku invocation fails, do not crash task execution.
            return InterpretationResult(
                status="needs_help",
                summary="Failed to interpret task output",
                error=f"Haiku invocation failed: {e}",
                question="Please review the task output and advise on next steps.",
                options=None,
                recommendation=None,
            )
        return self._parse_interpretation(response)

    def _parse_interpretation(self, response: str) -> InterpretationResult:
        """Parse Haiku response into an InterpretationResult.

        Handles JSON that may be wrapped in markdown code blocks.
        Falls back to needs_help status when parsing fails (conservative).

        Args:
            response: The raw response from Haiku.

        Returns:
            InterpretationResult parsed from the response.
        """
        data = None

        # Try direct JSON parse first
        try:
            data = json.loads(response.strip())
        except (json.JSONDecodeError, TypeError):
            # If direct parsing fails, fall back to extracting an embedded JSON object below.
            pass

        # Try to extract embedded JSON using balanced brace matching
        if data is None:
            data = self._extract_json_object(response)

        # If parsing failed, return conservative needs_help result
        if data is None:
            return InterpretationResult(
                status="needs_help",
                summary="Failed to interpret task output",
                error="Could not parse Haiku response as JSON",
                question="Please review the task output and advise on next steps.",
                options=None,
                recommendation=None,
            )

        # Handle both string and None values for status
        status = data.get("status", "needs_help")
        if status not in ("completed", "failed", "needs_help"):
            status = "needs_help"

        return InterpretationResult(
            status=status,
            summary=data.get("summary", ""),
            error=data.get("error"),
            question=data.get("question"),
            options=data.get("options"),
            recommendation=data.get("recommendation"),
        )

    def _extract_json_object(self, text: str) -> dict | None:
        """Extract a JSON object from text using balanced brace matching.

        Finds the first { and matches it to its closing } by counting braces,
        handling nested objects and strings properly.

        Args:
            text: The text potentially containing a JSON object.

        Returns:
            Parsed dict if found, None otherwise.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if in_string:
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None

        return None

    def should_retry_or_escalate(
        self,
        task_id: str,
        task_title: str,
        attempt_history: list[str],
        attempt_count: int,
    ) -> RetryDecision:
        """Decide whether to retry a failed task or escalate to human.

        Uses Haiku to semantically analyze the attempt history and determine
        if the errors show progress (retry) or indicate being stuck (escalate).

        Args:
            task_id: The task identifier (e.g., "1.1").
            task_title: The task title for context.
            attempt_history: List of error summaries from previous attempts.
            attempt_count: Number of attempts so far.

        Returns:
            RetryDecision with decision, reason, and guidance_for_retry if retrying.
        """
        prompt = RETRY_ESCALATE_PROMPT.format(
            task_id=task_id,
            task_title=task_title,
            attempt_history="\n".join(
                f"Attempt {i + 1}: {h}" for i, h in enumerate(attempt_history)
            ),
            attempt_count=attempt_count,
        )

        try:
            response = self._invoke_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            # Conservative fallback: if Haiku invocation fails, escalate for safety
            return RetryDecision(
                decision="escalate",
                reason=f"Haiku invocation failed: {e}",
                guidance_for_retry=None,
            )

        return self._parse_retry_decision(response)

    def _parse_retry_decision(self, response: str) -> RetryDecision:
        """Parse Haiku response into a RetryDecision.

        Handles JSON that may be wrapped in markdown code blocks.
        Falls back to escalate decision when parsing fails (conservative).

        Args:
            response: The raw response from Haiku.

        Returns:
            RetryDecision parsed from the response.
        """
        data = None

        # Try direct JSON parse first
        try:
            data = json.loads(response.strip())
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract embedded JSON using balanced brace matching
        if data is None:
            data = self._extract_json_object(response)

        # If parsing failed, return conservative escalate decision
        if data is None:
            return RetryDecision(
                decision="escalate",
                reason="Failed to parse Haiku response as JSON",
                guidance_for_retry=None,
            )

        # Validate decision field
        decision = data.get("decision", "escalate")
        if decision not in ("retry", "escalate"):
            decision = "escalate"

        return RetryDecision(
            decision=decision,
            reason=data.get("reason", ""),
            guidance_for_retry=data.get("guidance_for_retry"),
        )

    def parse_assessment(
        self,
        output: str,
        context: dict,
    ) -> ParsedAssessment:
        """Extract structured assessment from any format using Haiku.

        Uses Haiku to semantically understand the assessment output and
        extract structured data regardless of whether the input is
        structured markdown, prose, or mixed format.

        Args:
            output: The agent's assessment output text.
            context: Optional context dict (e.g., strategy_config) for reference.

        Returns:
            ParsedAssessment with extracted fields, or empty result on failure.
        """
        prompt = PARSE_ASSESSMENT_PROMPT.format(output=output)

        try:
            response = self._invoke_haiku(prompt)
        except (RuntimeError, subprocess.TimeoutExpired):
            return ParsedAssessment.empty(output)

        return self._parse_assessment_response(response, output)

    def _parse_assessment_response(
        self, response: str, raw_text: str
    ) -> ParsedAssessment:
        """Parse Haiku response into ParsedAssessment.

        Handles JSON that may be wrapped in markdown code blocks.
        Falls back to empty result when parsing fails.

        Args:
            response: The raw response from Haiku.
            raw_text: The original output text for preservation.

        Returns:
            ParsedAssessment parsed from the response.
        """
        data = self._extract_json_object(response)

        if data is None:
            return ParsedAssessment.empty(raw_text)

        return ParsedAssessment(
            verdict=data.get("verdict", "unknown"),
            observations=data.get("observations", []),
            hypotheses=data.get("hypotheses", []),
            limitations=data.get("limitations", []),
            capability_requests=data.get("capability_requests", []),
            tested_hypothesis_ids=data.get("tested_hypothesis_ids", []),
            raw_text=raw_text,
        )
