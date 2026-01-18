"""Coding agent container manager for Docker container interaction.

Provides methods to execute commands and invoke Claude Code in the
coding agent container environment via docker exec.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orchestrator.models import ClaudeResult


def format_tool_call(tool_name: str, tool_input: dict) -> str:
    """Format a tool call for human-readable display.

    Args:
        tool_name: Name of the tool (Read, Write, Bash, etc.)
        tool_input: Dictionary of tool input parameters

    Returns:
        Formatted string like "→ Reading config.py..."
    """
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        filename = Path(file_path).name if file_path else "file"
        return f"→ Reading {filename}..."

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        filename = Path(file_path).name if file_path else "file"
        return f"→ Writing {filename}..."

    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        filename = Path(file_path).name if file_path else "file"
        return f"→ Editing {filename}..."

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if len(command) > 50:
            command = command[:50] + "..."
        return f"→ Running: {command}"

    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        return f"→ Searching for {pattern}..."

    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        return f"→ Finding {pattern}..."

    else:
        return f"→ {tool_name}..."


class CodingAgentError(Exception):
    """Exception raised for coding agent container errors."""

    pass


@dataclass
class CodingAgentContainer:
    """Manages interaction with the coding agent Docker container.

    Provides methods to execute commands and invoke Claude Code
    in the isolated coding agent container environment.
    """

    container_name: str = "ktrdr-coding-agent"
    workspace_path: str = "/workspace"
    image_name: str = "ktrdr-coding-agent:latest"

    async def start(self, code_folder: Path) -> None:
        """Start the coding agent container with the code folder mounted.

        Removes any existing container first, then starts a fresh container
        with the specified code folder mounted at /workspace.

        Args:
            code_folder: Path to the code folder to mount as /workspace

        Raises:
            CodingAgentError: If docker commands fail
        """
        # Remove any existing container (ignore errors if it doesn't exist)
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
            text=True,
        )

        # Start fresh container with volume mount
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                self.container_name,
                "-v",
                f"{code_folder}:/workspace",
                "--add-host=host.docker.internal:host-gateway",
                self.image_name,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise CodingAgentError(f"Failed to start container: {result.stderr}")

    async def stop(self) -> None:
        """Stop and remove the coding agent container.

        Raises:
            CodingAgentError: If docker rm fails
        """
        result = subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise CodingAgentError(f"Failed to stop container: {result.stderr}")

    async def exec(self, command: str, timeout: int = 300) -> str:
        """Execute a command in the coding agent container.

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds

        Returns:
            Command stdout output

        Raises:
            CodingAgentError: If command exits with non-zero status
            subprocess.TimeoutExpired: If command exceeds timeout
        """
        result = subprocess.run(
            ["docker", "exec", self.container_name, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise CodingAgentError(f"Command failed: {result.stderr}")

        return result.stdout

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
        model: str | None = None,
        session_id: str | None = None,
    ) -> ClaudeResult:
        """Invoke Claude Code in the coding agent container with JSON output.

        Args:
            prompt: The prompt to send to Claude Code
            max_turns: Maximum conversation turns
            allowed_tools: List of tools Claude can use
            timeout: Maximum execution time in seconds
            model: Claude model to use (e.g., 'sonnet', 'opus'). If None, uses default.
            session_id: Session ID to resume. If provided, continues previous session.

        Returns:
            ClaudeResult with parsed response

        Raises:
            CodingAgentError: If JSON parsing fails
            subprocess.TimeoutExpired: If invocation exceeds timeout
        """
        tools = allowed_tools or ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

        cmd = [
            "docker",
            "exec",
            "-u",
            "ubuntu",  # Run as non-root to allow --dangerously-skip-permissions
            "-w",
            self.workspace_path,
            self.container_name,
            "claude",
        ]

        # Add --resume if continuing a session
        if session_id:
            cmd.extend(["--resume", session_id])

        cmd.extend(
            [
                "-p",
                prompt,
                "--output-format",
                "json",
                "--dangerously-skip-permissions",
                "--max-turns",
                str(max_turns),
                "--allowedTools",
                ",".join(tools),
            ]
        )

        # Add model if specified
        if model:
            cmd.extend(["--model", model])

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
            raise CodingAgentError(f"Failed to parse Claude JSON output: {e}") from e

        return ClaudeResult(
            is_error=output.get("is_error", False),
            result=output.get("result", ""),
            total_cost_usd=output.get("total_cost_usd", 0.0),
            duration_ms=output.get("duration_ms", 0),
            num_turns=output.get("num_turns", 0),
            session_id=output.get("session_id", ""),
        )

    async def invoke_claude_streaming(
        self,
        prompt: str,
        on_tool_use: Callable[[str, dict], None],
        max_turns: int = 50,
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
        model: str | None = None,
        session_id: str | None = None,
    ) -> ClaudeResult:
        """Invoke Claude Code with streaming output for real-time progress.

        Streams tool_use events to the callback as they occur, providing
        visibility into Claude's actions during execution.

        Args:
            prompt: The prompt to send to Claude Code
            on_tool_use: Callback invoked for each tool_use event with (name, input)
            max_turns: Maximum conversation turns
            allowed_tools: List of tools Claude can use
            timeout: Maximum execution time in seconds
            model: Claude model to use (e.g., 'sonnet', 'opus'). If None, uses default.
            session_id: Session ID to resume. If provided, continues previous session.

        Returns:
            ClaudeResult with parsed response

        Note:
            If streaming fails, returns a default error result rather than
            raising an exception.
        """
        tools = allowed_tools or ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

        cmd = [
            "docker",
            "exec",
            "-u",
            "ubuntu",
            "-w",
            self.workspace_path,
            self.container_name,
            "claude",
        ]

        # Add --resume if continuing a session
        if session_id:
            cmd.extend(["--resume", session_id])

        cmd.extend(
            [
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",  # Required for stream-json with -p
                "--dangerously-skip-permissions",
                "--max-turns",
                str(max_turns),
                "--allowedTools",
                ",".join(tools),
            ]
        )

        # Add model if specified
        if model:
            cmd.extend(["--model", model])

        # Use Popen for streaming output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        result_data: dict | None = None

        try:
            # Read lines as they come (stdout is guaranteed to be set when PIPE is used)
            if process.stdout is None:
                return ClaudeResult(
                    is_error=True,
                    result="No stdout stream available",
                    total_cost_usd=0.0,
                    duration_ms=0,
                    num_turns=0,
                    session_id="",
                )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

                event_type = event.get("type")

                if event_type == "assistant":
                    # Tool uses are nested in assistant message content
                    message = event.get("message", {})
                    content = message.get("content", [])
                    for item in content:
                        if item.get("type") == "tool_use":
                            tool_name = item.get("name", "")
                            tool_input = item.get("input", {})
                            on_tool_use(tool_name, tool_input)

                elif event_type == "result":
                    result_data = event

            # Wait for process to complete
            process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            process.kill()
            return ClaudeResult(
                is_error=True,
                result="Timeout exceeded",
                total_cost_usd=0.0,
                duration_ms=timeout * 1000,
                num_turns=0,
                session_id="",
            )

        # Return result from result event, or default error
        if result_data is not None:
            return ClaudeResult(
                is_error=result_data.get("is_error", False),
                result=result_data.get("result", ""),
                total_cost_usd=result_data.get("total_cost_usd", 0.0),
                duration_ms=result_data.get("duration_ms", 0),
                num_turns=result_data.get("num_turns", 0),
                session_id=result_data.get("session_id", ""),
            )
        else:
            return ClaudeResult(
                is_error=True,
                result="No result event received",
                total_cost_usd=0.0,
                duration_ms=0,
                num_turns=0,
                session_id="",
            )
