"""
Agent module for KTRDR autonomous research system.

This module contains the Anthropic API integration for the agent:
- AnthropicAgentInvoker: Direct API integration with Anthropic Claude
- AgentResult: Result dataclass for agent invocations
- ToolExecutor: Executes tool calls from the agent
- AGENT_TOOLS: Tool schema definitions for Anthropic API
"""

from ktrdr.agents.executor import ToolExecutor, create_tool_executor
from ktrdr.agents.invoker import AgentResult, AnthropicAgentInvoker
from ktrdr.agents.tools import AGENT_TOOLS, get_tool_by_name, get_tool_names

__all__ = [
    "AnthropicAgentInvoker",
    "AgentResult",
    "ToolExecutor",
    "create_tool_executor",
    "AGENT_TOOLS",
    "get_tool_by_name",
    "get_tool_names",
]
