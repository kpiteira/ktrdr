"""Sandbox manager for Docker container interaction.

Provides methods to execute commands and invoke Claude Code in the
sandboxed environment via docker exec.
"""

import json
import subprocess
from dataclasses import dataclass

from orchestrator.models import ClaudeResult


class SandboxError(Exception):
    """Exception raised for sandbox-related errors."""

    pass


@dataclass
class SandboxManager:
    """Manages interaction with the sandbox Docker container.

    Provides methods to execute commands and invoke Claude Code
    in the isolated sandbox environment.
    """

    container_name: str = "ktrdr-sandbox"
    workspace_path: str = "/workspace"

    async def exec(self, command: str, timeout: int = 300) -> str:
        """Execute a command in the sandbox container.

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds

        Returns:
            Command stdout output

        Raises:
            SandboxError: If command exits with non-zero status
            subprocess.TimeoutExpired: If command exceeds timeout
        """
        result = subprocess.run(
            ["docker", "exec", self.container_name, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise SandboxError(f"Command failed: {result.stderr}")

        return result.stdout

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
    ) -> ClaudeResult:
        """Invoke Claude Code in the sandbox with JSON output.

        Args:
            prompt: The prompt to send to Claude Code
            max_turns: Maximum conversation turns
            allowed_tools: List of tools Claude can use
            timeout: Maximum execution time in seconds

        Returns:
            ClaudeResult with parsed response

        Raises:
            SandboxError: If JSON parsing fails
            subprocess.TimeoutExpired: If invocation exceeds timeout
        """
        tools = allowed_tools or ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

        cmd = [
            "docker",
            "exec",
            "-w",
            self.workspace_path,
            self.container_name,
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
            "--max-turns",
            str(max_turns),
            "--allowedTools",
            ",".join(tools),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Parse JSON output
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise SandboxError(f"Failed to parse Claude JSON output: {e}") from e

        return ClaudeResult(
            is_error=output.get("is_error", False),
            result=output.get("result", ""),
            total_cost_usd=output.get("total_cost_usd", 0.0),
            duration_ms=output.get("duration_ms", 0),
            num_turns=output.get("num_turns", 0),
            session_id=output.get("session_id", ""),
        )
