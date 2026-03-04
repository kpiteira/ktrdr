"""AgentRuntime protocol and supporting types.

Ported from agent-memory's runtime/protocol.py, adapted for ktrdr:
- No PersistentAgentRuntime (ktrdr agents are ephemeral per-operation)
- No resume() (operations don't resume sessions)
- No transcript_path (transcripts stored in operation results, not filesystem)
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class AgentResult:
    """Result from an AgentRuntime invocation."""

    output: str
    cost_usd: float
    turns: int
    transcript: list[dict]
    session_id: str | None = None


@dataclass
class AgentRuntimeConfig:
    """Configuration for the agent runtime."""

    provider: str = "claude"
    model: str = "claude-sonnet-4-6"
    max_budget_usd: float = 5.0
    max_turns: int = 20


@runtime_checkable
class AgentRuntime(Protocol):
    """Protocol for autonomous agent runtimes with tool use.

    Design and assessment workers program against this protocol,
    not a specific SDK. Adding a new provider (e.g., Copilot) means
    implementing this protocol in a new file — worker code stays identical.
    """

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
    ) -> AgentResult: ...
