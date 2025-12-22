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


def strip_markdown(text: str | None) -> str | None:
    """Strip common markdown formatting from text.

    Removes:
    - Bold: **text** or __text__ → text
    - Orphan bold markers: ** at start of text/line
    - Headers: # Header → Header
    - Leading/trailing whitespace

    Args:
        text: The text to clean.

    Returns:
        Cleaned text with markdown formatting removed, or None if input was None.
    """
    if text is None:
        return None

    # Remove complete bold markers (**text** or __text__)
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    result = re.sub(r"__(.+?)__", r"\1", result)

    # Remove orphan ** at the start of lines (e.g., "**QUESTION:" with no closing **)
    result = re.sub(r"^\*\*\s*", "", result, flags=re.MULTILINE)

    # Remove orphan ** that appears after a newline or space
    result = re.sub(r"(\s)\*\*\s*", r"\1", result)

    # Remove header markers (# Header)
    result = re.sub(r"^#+\s*", "", result, flags=re.MULTILINE)

    # Remove italic markers (*text* or _text_) - be careful not to break underscores in identifiers
    result = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", result)

    return result.strip()

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
INTERPRETATION_PROMPT = """Analyze this Claude Code output and determine if human input is needed.

Return ONLY a valid JSON object with no additional text.

CRITICAL RULES:
1. Return ONLY the JSON, nothing before or after
2. All string values MUST be plain text - NO markdown (**bold**, __italic__, #headers)
3. For "question": Extract the COMPLETE question including all context. If there are multiple related questions or sub-questions, combine them into one coherent question.
4. For "options": Extract each distinct choice as a separate array element
5. For "recommendation": Extract the suggested approach if one is given

Detect "needs_human" as TRUE if:
- Claude explicitly asks a question requiring human decision
- Claude presents options/choices for the user to pick from
- Claude says it needs clarification, is uncertain, or can't proceed without input
- The output contains "ESCALATION", "NEEDS_HUMAN", or asks "which approach should I take?"

JSON format:
{{
  "needs_human": true or false,
  "question": "Complete question text, plain text only, include all context and sub-questions" or null,
  "options": ["Option A description", "Option B description", ...] or null,
  "recommendation": "Recommended approach if stated" or null,
  "task_completed": true or false,
  "task_failed": true or false,
  "error_message": "Error details if task failed" or null
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

                # Check for known CLI issues with clearer messages
                if "Consumer Terms" in error_text or "Privacy Policy" in error_text:
                    return self._create_fallback_result(
                        "Claude CLI needs terms acceptance. Run 'claude' directly first to accept."
                    )

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
        data = None

        # Try direct JSON parse first
        try:
            data = json.loads(response.strip())
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract embedded JSON using balanced brace matching
        if data is None:
            data = self._extract_json_object(response)

        if data is None:
            return self._create_fallback_result(
                "Interpreter error: could not parse response"
            )

        # Clean markdown from string values
        data = self._clean_data(data)

        try:
            return InterpretationResult(**data)
        except TypeError as e:
            return self._create_fallback_result(f"Interpreter error: {e}")

    def _extract_json_object(self, text: str) -> dict | None:
        """Extract a JSON object from text using balanced brace matching.

        Finds the first { and matches it to its closing } by counting braces,
        handling nested objects properly.

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
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
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

    def _clean_data(self, data: dict) -> dict:
        """Clean markdown formatting from string values in the data dict.

        Args:
            data: The parsed JSON data.

        Returns:
            Data with markdown stripped from string values.
        """
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = strip_markdown(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    strip_markdown(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned

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
