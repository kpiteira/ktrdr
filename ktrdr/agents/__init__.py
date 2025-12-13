"""Agent components for autonomous research."""

from ktrdr.agents.executor import ToolExecutor, create_tool_executor
from ktrdr.agents.gates import (
    BacktestGateConfig,
    TrainingGateConfig,
    check_backtest_gate,
    check_training_gate,
)
from ktrdr.agents.invoker import AgentResult, AnthropicAgentInvoker
from ktrdr.agents.prompts import PromptContext, get_strategy_designer_prompt
from ktrdr.agents.strategy_utils import (
    get_recent_strategies,
    save_strategy_config,
    validate_strategy_config,
)
from ktrdr.agents.tools import AGENT_TOOLS, get_tool_by_name, get_tool_names

__all__ = [
    "AnthropicAgentInvoker",
    "AgentResult",
    "ToolExecutor",
    "create_tool_executor",
    "AGENT_TOOLS",
    "get_tool_by_name",
    "get_tool_names",
    "check_training_gate",
    "check_backtest_gate",
    "TrainingGateConfig",
    "BacktestGateConfig",
    "get_strategy_designer_prompt",
    "PromptContext",
    "validate_strategy_config",
    "save_strategy_config",
    "get_recent_strategies",
]
