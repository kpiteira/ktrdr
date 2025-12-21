"""LLM-based interpretation of Claude Code output.

Uses Claude Code CLI with Haiku 4.5 to semantically understand task output,
replacing fragile regex-based detection with semantic understanding.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

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

    # Try common installation location
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
class InterpretationResult:
    """Result of LLM interpretation of task output.

    Provides structured information about what happened during task execution,
    including whether human input is needed and what questions/options to present.
    """

    needs_human: bool
    question: str | None
    options: list[str] | None
    recommendation: str | None
    task_completed: bool
    task_failed: bool
    error_message: str | None


# Maximum characters of output to include in the prompt
MAX_OUTPUT_LENGTH = 8000

# Prompt template for interpretation
INTERPRETATION_PROMPT = """Analyze this Claude Code output and return ONLY valid JSON.

IMPORTANT:
- Return ONLY the JSON object, nothing else
- All string values must be plain text (NO markdown formatting like ** or __)
- Extract the actual question being asked, not the formatting

{{
  "needs_human": true or false,
  "question": "the exact question being asked, plain text only" or null,
  "options": ["option 1 text", "option 2 text"] or null,
  "recommendation": "the recommendation, plain text only" or null,
  "task_completed": true or false,
  "task_failed": true or false,
  "error_message": "error details" or null
}}

Output to analyze:
{output}
"""


class LLMInterpreter:
    """Interprets task output using Claude Code CLI with Haiku.

    Uses semantic understanding to detect:
    - Whether the task needs human input (questions, options)
    - Whether the task completed successfully
    - Whether the task failed and any error details
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """Initialize the interpreter.

        Args:
            model: The Claude model to use. Defaults to Haiku 4.5.
        """
        self.model = model

    def interpret(self, output: str) -> InterpretationResult:
        """Interpret task output using Claude Code CLI.

        Args:
            output: The text output from Claude Code task execution.

        Returns:
            InterpretationResult with structured information about the output.
        """
        # Find Claude CLI
        claude_path = find_claude_cli()
        if claude_path is None:
            return self._create_fallback_result(
                "Interpreter error: Claude CLI not found"
            )

        # Truncate output if too large
        truncated_output = output[:MAX_OUTPUT_LENGTH]
        prompt = INTERPRETATION_PROMPT.format(output=truncated_output)

        try:
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
                timeout=30,
            )

            if result.returncode != 0:
                # CLI failed - use fallback. Error may be in stdout or stderr.
                error_text = result.stderr or result.stdout or "unknown error"
                return self._create_fallback_result(
                    f"Interpreter error: {error_text[:200]}"
                )

            return self._parse_response(result.stdout)

        except subprocess.TimeoutExpired:
            return self._create_fallback_result("Interpreter error: timeout expired")
        except FileNotFoundError:
            return self._create_fallback_result(
                f"Interpreter error: Claude CLI not found at {claude_path}"
            )

    def _parse_response(self, response: str) -> InterpretationResult:
        """Parse the LLM response into an InterpretationResult.

        Args:
            response: The raw response from the Claude CLI.

        Returns:
            Parsed InterpretationResult.
        """
        try:
            # Try direct JSON parse first
            data = json.loads(response.strip())
            return InterpretationResult(**data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract embedded JSON from response
        try:
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return InterpretationResult(**data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback if we can't parse
        return self._create_fallback_result(
            "Interpreter error: could not parse response"
        )

    def _create_fallback_result(self, error_message: str) -> InterpretationResult:
        """Create a fallback result when interpretation fails.

        When the interpreter fails, we conservatively assume human input is
        needed to avoid missing escalation cases. This is safer than assuming
        task completion, as a false positive escalation is better than silently
        ignoring a question from Claude.

        Args:
            error_message: Description of what went wrong.

        Returns:
            InterpretationResult indicating human review needed.
        """
        return InterpretationResult(
            needs_human=True,  # Conservative: escalate when uncertain
            question=f"LLM interpretation failed: {error_message}. Please review the task output.",
            options=None,
            recommendation=None,
            task_completed=False,
            task_failed=False,
            error_message=error_message,
        )
