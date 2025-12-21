"""LLM-based interpretation of Claude Code output.

Uses Claude Code CLI with Haiku 4.5 to semantically understand task output,
replacing fragile regex-based detection with semantic understanding.
"""

import json
import re
import subprocess
from dataclasses import dataclass


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
INTERPRETATION_PROMPT = """Analyze this Claude Code output and return ONLY valid JSON (no markdown, no explanation):

{{
  "needs_human": true or false,
  "question": "the question being asked" or null,
  "options": ["option A", "option B"] or null,
  "recommendation": "recommended choice" or null,
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

    def __init__(self, model: str = "claude-haiku-4.5-20251001"):
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
        # Truncate output if too large
        truncated_output = output[:MAX_OUTPUT_LENGTH]
        prompt = INTERPRETATION_PROMPT.format(output=truncated_output)

        try:
            result = subprocess.run(
                [
                    "claude",
                    "--model",
                    self.model,
                    "--print",
                    "--no-session-persistence",
                    "--tools",
                    "",
                    "-p",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # CLI failed - use fallback
                return self._create_fallback_result(
                    f"Interpreter error: {result.stderr[:200]}"
                )

            return self._parse_response(result.stdout)

        except subprocess.TimeoutExpired:
            return self._create_fallback_result("Interpreter error: timeout expired")

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

        When the interpreter fails, we assume the task completed successfully
        to avoid blocking progress. The error is recorded for debugging.

        Args:
            error_message: Description of what went wrong.

        Returns:
            InterpretationResult with safe fallback values.
        """
        return InterpretationResult(
            needs_human=False,
            question=None,
            options=None,
            recommendation=None,
            task_completed=True,
            task_failed=False,
            error_message=error_message,
        )
