"""
Claude Code invoker service for research agents.

This service invokes Claude Code CLI with MCP configuration to run
the agent with access to KTRDR tools. It handles subprocess management,
timeout handling, and output parsing.

Phase 0: Proves the basic invocation works.
Future phases: Direct API calls, cost tracking, etc.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class InvokerConfig:
    """Configuration for the Claude Code invoker.

    Attributes:
        timeout_seconds: Maximum time to wait for Claude to complete (default: 5 minutes)
        claude_path: Path to the Claude CLI executable
        mcp_config_path: Path to MCP configuration JSON file
    """

    timeout_seconds: int = 300  # 5 minutes
    claude_path: str = "claude"
    mcp_config_path: str = field(
        default_factory=lambda: str(
            Path(__file__).parent.parent.parent / "mcp" / "claude_mcp_config.json"
        )
    )

    @classmethod
    def from_env(cls) -> "InvokerConfig":
        """Load configuration from environment variables.

        Environment variables:
            AGENT_INVOKER_TIMEOUT_SECONDS: Maximum time for invocation (default: 300)
            CLAUDE_PATH: Path to Claude CLI (default: "claude")
            AGENT_MCP_CONFIG_PATH: Path to MCP config (default: mcp/claude_mcp_config.json)

        Returns:
            InvokerConfig instance with values from environment.

        Raises:
            FileNotFoundError: If MCP config file does not exist.
        """
        timeout = int(os.getenv("AGENT_INVOKER_TIMEOUT_SECONDS", "300"))
        claude_path = os.getenv("CLAUDE_PATH", "claude")
        default_mcp_path = str(
            Path(__file__).parent.parent.parent / "mcp" / "claude_mcp_config.json"
        )
        mcp_config_path = os.getenv("AGENT_MCP_CONFIG_PATH", default_mcp_path)

        # Validate MCP config file exists
        if not Path(mcp_config_path).exists():
            raise FileNotFoundError(
                f"MCP config file not found: {mcp_config_path}. "
                f"Set AGENT_MCP_CONFIG_PATH to a valid path."
            )

        return cls(
            timeout_seconds=timeout,
            claude_path=claude_path,
            mcp_config_path=mcp_config_path,
        )


@dataclass
class InvocationResult:
    """Result of a Claude Code invocation.

    Attributes:
        success: Whether the invocation completed successfully
        exit_code: The exit code from the Claude CLI process
        output: Parsed JSON output from Claude (if valid JSON)
        raw_output: Raw string output from Claude
        error: Error message if invocation failed
    """

    success: bool
    exit_code: int
    output: dict | None
    raw_output: str
    error: str | None


class InvocationError(Exception):
    """Exception raised when Claude Code invocation fails."""

    pass


class ClaudeCodeInvoker:
    """Invokes Claude Code CLI with MCP configuration.

    This class implements the AgentInvoker protocol defined in trigger.py,
    using subprocess to call the Claude CLI with appropriate arguments.

    Usage:
        config = InvokerConfig.from_env()
        invoker = ClaudeCodeInvoker(config=config)
        result = await invoker.invoke(
            prompt="Design a strategy",
            system_prompt="You are a strategy designer"
        )
    """

    def __init__(self, config: InvokerConfig | None = None):
        """Initialize the invoker.

        Args:
            config: Invoker configuration. If None, uses from_env().
        """
        self.config = config or InvokerConfig.from_env()

    async def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> InvocationResult:
        """Invoke Claude Code with the given prompt.

        Args:
            prompt: The user prompt to send to Claude.
            system_prompt: Optional system prompt to customize behavior.
            session_context: Optional context dict (session_id, phase, etc.)
                            to include in the prompt.

        Returns:
            InvocationResult with success status, output, and any errors.
        """
        # Build the prompt with session context if provided
        full_prompt = prompt
        if session_context:
            context_str = json.dumps(session_context, indent=2)
            full_prompt = f"""Session Context:
{context_str}

{prompt}"""

        # Build CLI arguments
        args = self._build_cli_args(full_prompt, system_prompt)

        logger.info(
            "Invoking Claude Code",
            timeout=self.config.timeout_seconds,
            mcp_config=self.config.mcp_config_path,
            has_system_prompt=system_prompt is not None,
            has_session_context=session_context is not None,
        )

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Claude Code invocation timed out",
                    timeout=self.config.timeout_seconds,
                )
                process.kill()
                await process.wait()  # Clean up the process
                return InvocationResult(
                    success=False,
                    exit_code=-1,
                    output=None,
                    raw_output="",
                    error=f"Timeout after {self.config.timeout_seconds} seconds",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Check exit code
            if process.returncode != 0:
                logger.error(
                    "Claude Code invocation failed",
                    exit_code=process.returncode,
                    stderr=stderr_str,
                )
                return InvocationResult(
                    success=False,
                    exit_code=process.returncode,
                    output=None,
                    raw_output=stdout_str,
                    error=stderr_str or f"Exit code {process.returncode}",
                )

            # Parse output as JSON if possible
            output_dict = None
            try:
                output_dict = json.loads(stdout_str)
            except json.JSONDecodeError:
                logger.debug("Claude output is not JSON, using raw output")

            logger.info(
                "Claude Code invocation completed successfully",
                exit_code=process.returncode,
                output_length=len(stdout_str),
            )

            return InvocationResult(
                success=True,
                exit_code=process.returncode,
                output=output_dict,
                raw_output=stdout_str,
                error=None,
            )

        except OSError as e:
            logger.error("Failed to start Claude Code process", error=str(e))
            return InvocationResult(
                success=False,
                exit_code=-1,
                output=None,
                raw_output="",
                error=str(e),
            )

    def _build_cli_args(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> list[str]:
        """Build the CLI arguments for Claude Code.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.

        Returns:
            List of CLI arguments.
        """
        args = [
            self.config.claude_path,
            "--print",
            "--output-format",
            "json",
            "--mcp-config",
            self.config.mcp_config_path,
        ]

        if system_prompt:
            args.extend(["--system-prompt", system_prompt])

        # Add the prompt as the final argument
        args.append(prompt)

        return args
