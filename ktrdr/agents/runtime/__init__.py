"""Agent runtime abstraction — provider-agnostic protocol for LLM agent invocation.

Ported from agent-memory's production runtime, adapted for ktrdr's
ephemeral per-operation model (no persistent sessions).
"""

from ktrdr.agents.runtime.protocol import AgentResult, AgentRuntime, AgentRuntimeConfig

__all__ = ["AgentRuntime", "AgentResult", "AgentRuntimeConfig"]
