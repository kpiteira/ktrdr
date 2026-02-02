"""Decision engine for trading signal generation."""

# Base classes load immediately (no torch dependency)
from .base import Position, Signal, TradingDecision

# Temporarily disabled while updating multi-timeframe for pure fuzzy
# from .multi_timeframe_orchestrator import (
#     MultiTimeframeDecisionOrchestrator,
#     MultiTimeframeDecisionContext,
#     TimeframeDecisionContext,
#     TimeframeDecision,
#     MultiTimeframeConsensus,
#     create_multi_timeframe_decision_orchestrator,
# )

__all__ = [
    "Signal",
    "Position",
    "TradingDecision",
    "DecisionEngine",
    "DecisionOrchestrator",
    "DecisionContext",
    "PositionState",
    # "MultiTimeframeDecisionOrchestrator",  # Temporarily disabled
    # "MultiTimeframeDecisionContext",  # Temporarily disabled
    # "TimeframeDecisionContext",  # Temporarily disabled
    # "TimeframeDecision",  # Temporarily disabled
    # "MultiTimeframeConsensus",  # Temporarily disabled
    # "create_multi_timeframe_decision_orchestrator",  # Temporarily disabled
]


def __getattr__(name: str):
    """Lazy loading for torch-dependent modules."""
    if name == "DecisionEngine":
        from .engine import DecisionEngine

        return DecisionEngine
    if name == "DecisionOrchestrator":
        from .orchestrator import DecisionOrchestrator

        return DecisionOrchestrator
    if name == "DecisionContext":
        from .orchestrator import DecisionContext

        return DecisionContext
    if name == "PositionState":
        from .orchestrator import PositionState

        return PositionState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
