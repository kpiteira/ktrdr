"""
Quality gates for agent research cycles.

These gates are deterministic checks applied by the trigger service
to filter out poor-performing strategies before wasting compute
on subsequent phases.
"""

from research_agents.gates.backtest_gate import (
    BacktestGateConfig,
    evaluate_backtest_gate,
)
from research_agents.gates.training_gate import (
    TrainingGateConfig,
    evaluate_training_gate,
)

__all__ = [
    "BacktestGateConfig",
    "evaluate_backtest_gate",
    "TrainingGateConfig",
    "evaluate_training_gate",
]
