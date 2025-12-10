"""
Anthropic Agent Invoker for KTRDR research agents.

This module provides direct integration with the Anthropic API for running
the autonomous research agent. It implements an agentic loop that:
1. Sends prompts to Claude
2. Handles tool calls by executing them locally
3. Returns tool results to Claude
4. Continues until Claude finishes (no more tool calls)

This replaces the Phase 0 ClaudeCodeInvoker that used subprocess.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import structlog

if TYPE_CHECKING:
    import anthropic

logger = structlog.get_logger(__name__)


@dataclass
class AgentResult:
    """Result of an Anthropic agent invocation.

    Attributes:
        success: Whether the invocation completed successfully
        output: Text output from the agent
        input_tokens: Total input tokens used across all API calls
        output_tokens: Total output tokens used across all API calls
        error: Error message if invocation failed
    """

    success: bool
    output: str | None
    input_tokens: int
    output_tokens: int
    error: str | None


@dataclass
class AnthropicInvokerConfig:
    """Configuration for the Anthropic agent invoker.

    Attributes:
        model: The Claude model to use (e.g., claude-sonnet-4-20250514)
        max_tokens: Maximum tokens for response generation
        timeout_seconds: Timeout for API calls in seconds (default: 300 = 5 minutes)
    """

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout_seconds: int = 300  # 5 minutes default (Task 1.13b)

    @classmethod
    def from_env(cls) -> AnthropicInvokerConfig:
        """Load configuration from environment variables.

        Environment variables:
            AGENT_MODEL: Claude model to use (default: claude-sonnet-4-20250514)
            AGENT_MAX_TOKENS: Maximum tokens for response (default: 4096)
            AGENT_TIMEOUT_SECONDS: Timeout for API calls (default: 300)

        Returns:
            AnthropicInvokerConfig instance with values from environment.
        """
        model = os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514")
        max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
        timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))
        return cls(model=model, max_tokens=max_tokens, timeout_seconds=timeout_seconds)


# Type alias for tool executor function
# Tool results can be dict or list (for tools returning collections)
ToolExecutorResult = dict[str, Any] | list[dict[str, Any]]
ToolExecutor = Callable[[str, dict[str, Any]], Coroutine[Any, Any, ToolExecutorResult]]


class AnthropicAgentInvoker:
    """Invokes Claude via the Anthropic API with tool support.

    This class implements an agentic loop pattern:
    1. Send initial prompt with tools to Claude
    2. If Claude requests tool calls, execute them
    3. Send tool results back to Claude
    4. Repeat until Claude finishes (no tool calls)

    Usage:
        config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=config)
        result = await invoker.run(
            prompt="Design a trading strategy",
            tools=AGENT_TOOLS,
            system_prompt="You are a strategy designer.",
            tool_executor=my_executor
        )
    """

    def __init__(self, config: AnthropicInvokerConfig | None = None):
        """Initialize the invoker.

        Args:
            config: Invoker configuration. If None, uses from_env().
        """
        self.config = config or AnthropicInvokerConfig.from_env()
        self.client: anthropic.Anthropic | None = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the Anthropic client.

        Lazy import to avoid requiring anthropic package at module load time.
        Task 1.13b: Configure client with timeout to prevent hung operations.
        """
        try:
            import anthropic

            # Task 1.13b: Set explicit timeout for API calls
            self.client = anthropic.Anthropic(
                timeout=float(self.config.timeout_seconds)
            )
            logger.info(
                "Initialized Anthropic client",
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                timeout_seconds=self.config.timeout_seconds,
            )
        except ImportError:
            logger.warning("anthropic package not installed - client not initialized")
            self.client = None

    async def run(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        tool_executor: ToolExecutor | None = None,
    ) -> AgentResult:
        """Run the agent with the given prompt.

        Args:
            prompt: The user prompt to send to Claude.
            tools: List of tool definitions in Anthropic format.
            system_prompt: System prompt for the agent.
            tool_executor: Async function to execute tool calls.

        Returns:
            AgentResult with success status, output, token counts, and errors.
        """
        if self.client is None:
            return AgentResult(
                success=False,
                output=None,
                input_tokens=0,
                output_tokens=0,
                error="Anthropic client not initialized. Is ANTHROPIC_API_KEY set?",
            )

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        total_input_tokens = 0
        total_output_tokens = 0

        logger.info(
            "Starting agent invocation",
            model=self.config.model,
            has_tools=len(tools) > 0,
            has_tool_executor=tool_executor is not None,
        )

        try:
            while True:
                # Make API call in a thread to avoid blocking
                response = await asyncio.to_thread(
                    self._create_message,
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                )

                # Track token usage
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens

                logger.debug(
                    "Received API response",
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    stop_reason=response.stop_reason,
                )

                # Check for tool calls
                tool_calls = [
                    block for block in response.content if block.type == "tool_use"
                ]

                if not tool_calls:
                    # No more tools - extract final text and return
                    output_text = self._extract_text(response.content)
                    logger.info(
                        "Agent completed",
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=total_output_tokens,
                    )
                    return AgentResult(
                        success=True,
                        output=output_text,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        error=None,
                    )

                # Execute tools and continue the loop
                messages.append({"role": "assistant", "content": response.content})
                tool_results = await self._execute_tools(tool_calls, tool_executor)
                messages.append({"role": "user", "content": tool_results})

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Agent invocation failed",
                error=error_msg,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
            )
            return AgentResult(
                success=False,
                output=None,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                error=error_msg,
            )

    def _create_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        """Create a message using the Anthropic API.

        This is called in a thread via asyncio.to_thread.

        Args:
            system_prompt: System prompt for the conversation.
            messages: Message history.
            tools: Tool definitions.

        Returns:
            Anthropic API response.

        Raises:
            RuntimeError: If client is not initialized.
        """
        # This should never happen as run() checks client before calling
        if self.client is None:
            raise RuntimeError("Anthropic client not initialized")

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        # Only include tools if we have any
        if tools:
            kwargs["tools"] = tools

        return self.client.messages.create(**kwargs)

    async def _execute_tools(
        self,
        tool_calls: list[Any],
        tool_executor: ToolExecutor | None,
    ) -> list[dict[str, Any]]:
        """Execute tool calls and return results.

        Args:
            tool_calls: List of tool_use blocks from Claude's response.
            tool_executor: Async function to execute tools.

        Returns:
            List of tool_result blocks for the next API call.
        """
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_input = tool_call.input
            tool_use_id = tool_call.id

            logger.info(
                "Executing tool",
                tool_name=tool_name,
                tool_use_id=tool_use_id,
            )

            # Type hint for result_content - can be dict or list from tool executor
            result_content: ToolExecutorResult

            if tool_executor is None:
                # No executor provided - return error
                result_content = {
                    "error": f"No tool executor provided for tool: {tool_name}"
                }
            else:
                try:
                    result_content = await tool_executor(tool_name, tool_input)
                except Exception as e:
                    logger.error(
                        "Tool execution failed",
                        tool_name=tool_name,
                        error=str(e),
                    )
                    result_content = {"error": f"Tool execution failed: {str(e)}"}

            # Format as tool_result block
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": str(result_content),
                }
            )

        return results

    def _extract_text(self, content: list[Any]) -> str:
        """Extract text content from response content blocks.

        Args:
            content: List of content blocks from the response.

        Returns:
            Combined text from all text blocks.
        """
        text_parts = []
        for block in content:
            if block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)
