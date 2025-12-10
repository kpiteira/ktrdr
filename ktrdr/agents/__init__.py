"""
Agent module for KTRDR autonomous research system.

This module contains the Anthropic API integration for the agent:
- AnthropicAgentInvoker: Direct API integration with Anthropic Claude
- AgentResult: Result dataclass for agent invocations
"""

from ktrdr.agents.invoker import AgentResult, AnthropicAgentInvoker

__all__ = ["AnthropicAgentInvoker", "AgentResult"]
