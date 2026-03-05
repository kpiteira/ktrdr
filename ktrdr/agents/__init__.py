"""Agent components for autonomous research."""

from ktrdr.agents.gates import (
    BacktestGateConfig,
    TrainingGateConfig,
    check_backtest_gate,
    check_training_gate,
)
from ktrdr.agents.models import (
    DEFAULT_MODEL,
    MODEL_ALIASES,
    VALID_MODELS,
    resolve_model,
)
from ktrdr.agents.prompts import PromptContext, get_strategy_designer_prompt
from ktrdr.agents.strategy_utils import (
    get_recent_strategies,
    save_strategy_config,
    validate_strategy_config,
)

__all__ = [
    "DEFAULT_MODEL",
    "MODEL_ALIASES",
    "VALID_MODELS",
    "resolve_model",
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
