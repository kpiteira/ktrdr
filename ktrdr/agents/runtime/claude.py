"""ClaudeAgentRuntime — AgentRuntime using the claude-agent-sdk.

Ported from agent-memory's runtime/claude.py, adapted for ktrdr:
- No resume() (ephemeral per-operation)
- No transcript_path (stored in operation results)
- Single retry on CLIConnectionError

SDK imports are lazy because claude_agent_sdk depends on the `mcp` pip package,
which is shadowed by ktrdr's local `mcp/` directory in development. Inside the
agent Docker container this isn't an issue, but lazy imports keep unit tests
working in the dev environment.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

from ktrdr import get_logger
from ktrdr.agents.runtime.protocol import AgentResult, AgentRuntimeConfig

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

logger = get_logger(__name__)


def _get_sdk():
    """Lazy-import claude_agent_sdk to avoid mcp package shadowing in dev."""
    import claude_agent_sdk

    return claude_agent_sdk


class ClaudeAgentRuntime:
    """AgentRuntime implementation backed by claude-agent-sdk.

    Handles Claude Code SDK invocation with:
    - CLAUDECODE env var management (prevents nested SDK blocking)
    - Transcript conversion from SDK types to dicts
    - Single retry on CLIConnectionError
    - Cost and turn tracking
    """

    def __init__(
        self,
        *,
        config: AgentRuntimeConfig,
        api_key: str | None = None,
    ) -> None:
        self._config = config
        self._api_key = api_key

    async def invoke(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_turns: int = 10,
        max_budget_usd: float = 1.0,
        allowed_tools: list[str] | None = None,
        cwd: str | None = None,
        system_prompt: str | None = None,
        mcp_servers: dict[str, object] | None = None,
    ) -> AgentResult:
        """Invoke Claude Code SDK with the given prompt.

        Builds ClaudeAgentOptions from parameters, manages CLAUDECODE env var,
        and collects results into AgentResult.
        """
        sdk = _get_sdk()
        options = sdk.ClaudeAgentOptions(
            model=model or self._config.model,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            allowed_tools=allowed_tools or [],
            cwd=cwd,
            permission_mode="bypassPermissions",
        )
        if system_prompt:
            options.system_prompt = system_prompt
        if mcp_servers:
            options.mcp_servers = mcp_servers
        if self._api_key:
            options.env["ANTHROPIC_API_KEY"] = self._api_key

        try:
            return await self._run(prompt, options, sdk)
        except sdk.CLIConnectionError:
            logger.warning("CLIConnectionError — retrying once")
            try:
                return await self._run(prompt, options, sdk)
            except Exception:
                logger.exception("Retry also failed")
                return AgentResult(
                    output=f"Agent SDK error after retry: {_exc_summary()}",
                    cost_usd=0.0,
                    turns=0,
                    transcript=[],
                )

    async def _run(
        self, prompt: str, options: ClaudeAgentOptions, sdk: Any
    ) -> AgentResult:
        """Execute SDK query and collect results.

        Removes CLAUDECODE env var before spawn (blocks nested SDK calls)
        and restores it in finally block.
        """
        saved_claudecode = os.environ.pop("CLAUDECODE", None)

        transcript: list[dict] = []
        output = ""
        session_id = None
        cost_usd = 0.0
        turns = 0

        try:
            async for message in sdk.query(prompt=prompt, options=options):
                if isinstance(message, sdk.ResultMessage):
                    session_id = message.session_id
                    cost_usd = message.total_cost_usd or 0.0
                    turns = message.num_turns
                    output = message.result or ""
                elif isinstance(message, sdk.AssistantMessage):
                    for block in message.content:
                        entry = _block_to_transcript(block, sdk)
                        if entry:
                            transcript.append(entry)
        except sdk.CLIConnectionError:
            raise  # Let invoke() handle retry
        except Exception:
            logger.exception("Agent SDK error")
            return AgentResult(
                output=f"Agent SDK error: {_exc_summary()}",
                cost_usd=0.0,
                turns=0,
                transcript=[],
            )
        finally:
            if saved_claudecode is not None:
                os.environ["CLAUDECODE"] = saved_claudecode

        return AgentResult(
            output=output,
            session_id=session_id,
            cost_usd=cost_usd,
            turns=turns,
            transcript=transcript,
        )


def _block_to_transcript(block: object, sdk: Any) -> dict | None:
    """Convert a content block to a transcript entry."""
    if isinstance(block, sdk.TextBlock):
        return {
            "role": "assistant",
            "type": "text",
            "content": block.text,
        }
    if isinstance(block, sdk.ToolUseBlock):
        return {
            "role": "assistant",
            "type": "tool_use",
            "tool": block.name,
            "input": block.input,
            "id": block.id,
        }
    if isinstance(block, sdk.ToolResultBlock):
        return {
            "role": "tool",
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
        }
    return None


def _exc_summary() -> str:
    """Get a one-line summary of the current exception."""
    exc = sys.exc_info()[1]
    return str(exc) if exc else "unknown error"
