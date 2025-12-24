"""Haiku Brain - All orchestration intelligence via Claude Haiku.

This module replaces brittle regex-based parsing with Claude Haiku API calls
for semantic understanding of milestone plans and task execution results.
"""

import json
import re
import subprocess
from dataclasses import dataclass

from orchestrator.llm_interpreter import find_claude_cli


@dataclass
class ExtractedTask:
    """A task extracted from a milestone plan.

    Contains minimal fields needed for orchestration. The /ktask skill
    reads detailed fields (file_path, acceptance_criteria) from the plan directly.
    """

    id: str
    title: str
    description: str


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

            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None
