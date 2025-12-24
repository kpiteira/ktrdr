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
