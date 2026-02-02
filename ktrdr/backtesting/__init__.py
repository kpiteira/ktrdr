"""Backtesting system for strategy evaluation."""

from .engine import BacktestConfig, BacktestingEngine, BacktestResults
from .performance import PerformanceMetrics, PerformanceTracker
from .position_manager import Position, PositionManager, PositionStatus, Trade
from .progress_bridge import BacktestProgressBridge


def __getattr__(name: str):
    """Lazy loading for torch-dependent modules."""
    if name == "ModelLoader":
        from .model_loader import ModelLoader

        return ModelLoader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BacktestConfig",
    "BacktestingEngine",
    "BacktestProgressBridge",
    "BacktestResults",
    "ModelLoader",
    "PerformanceMetrics",
    "PerformanceTracker",
    "Position",
    "PositionManager",
    "PositionStatus",
    "Trade",
]
