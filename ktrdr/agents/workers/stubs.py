"""Stub workers for testing orchestrator without real operations.

These workers simulate each phase of the research cycle with configurable delays
(default ~30s per phase). Sleep in small intervals for responsive cancellation.

Environment Variables:
    STUB_WORKER_DELAY: Seconds per phase (default: 30)
    STUB_WORKER_FAST: Set to "true" for fast mode (500ms per phase)
"""

import asyncio
import os
from typing import Any


def _get_phase_delay() -> float:
    """Get the delay for each phase in seconds.

    Returns:
        30s by default, 0.5s if STUB_WORKER_FAST=true, or STUB_WORKER_DELAY value.
    """
    if os.getenv("STUB_WORKER_FAST", "").lower() in ("true", "1", "yes"):
        return 0.5

    try:
        return float(os.getenv("STUB_WORKER_DELAY", "30"))
    except ValueError:
        return 30.0


async def _cancellable_sleep(total_seconds: float, interval: float = 0.1) -> None:
    """Sleep in small intervals to allow responsive cancellation.

    Args:
        total_seconds: Total time to sleep.
        interval: Sleep interval (default 100ms for responsive cancellation).

    Raises:
        asyncio.CancelledError: If cancelled during sleep.
    """
    elapsed = 0.0
    while elapsed < total_seconds:
        await asyncio.sleep(min(interval, total_seconds - elapsed))
        elapsed += interval


class StubDesignWorker:
    """Stub that simulates strategy design.

    Returns mock strategy configuration as if Claude had designed it.
    """

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Simulate design phase.

        Args:
            operation_id: The operation ID for tracking.

        Returns:
            Mock design result with strategy name, path, and token usage.
        """
        await _cancellable_sleep(_get_phase_delay())
        return {
            "success": True,
            "strategy_name": "stub_momentum_v1",
            "strategy_path": "/app/strategies/stub_momentum_v1.yaml",
            "input_tokens": 2500,
            "output_tokens": 1800,
        }


class StubTrainingWorker:
    """Stub that simulates model training.

    Returns mock training metrics as if a model had been trained.
    """

    async def run(self, operation_id: str, strategy_path: str) -> dict[str, Any]:
        """Simulate training phase.

        Args:
            operation_id: The operation ID for tracking.
            strategy_path: Path to the strategy configuration.

        Returns:
            Mock training result with accuracy, loss, and model path.
        """
        await _cancellable_sleep(_get_phase_delay())
        return {
            "success": True,
            "accuracy": 0.65,
            "final_loss": 0.35,
            "initial_loss": 0.85,
            "model_path": "/app/models/stub_momentum_v1/model.pt",
        }


class StubBacktestWorker:
    """Stub that simulates backtesting.

    Returns mock backtest metrics as if a backtest had been run.
    """

    async def run(self, operation_id: str, model_path: str) -> dict[str, Any]:
        """Simulate backtest phase.

        Args:
            operation_id: The operation ID for tracking.
            model_path: Path to the trained model.

        Returns:
            Mock backtest result with sharpe, win_rate, drawdown, return.
        """
        await _cancellable_sleep(_get_phase_delay())
        return {
            "success": True,
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 0.15,
            "total_return": 0.23,
        }


class StubAssessmentWorker:
    """Stub that simulates Claude assessment.

    Returns mock assessment as if Claude had evaluated the results.
    """

    async def run(self, operation_id: str, results: dict[str, Any]) -> dict[str, Any]:
        """Simulate assessment phase.

        Args:
            operation_id: The operation ID for tracking.
            results: Combined training and backtest results.

        Returns:
            Mock assessment with verdict, strengths, weaknesses, suggestions.
        """
        await _cancellable_sleep(_get_phase_delay())
        return {
            "success": True,
            "verdict": "promising",
            "strengths": ["Good risk management", "Consistent returns"],
            "weaknesses": ["Limited sample size"],
            "suggestions": ["Test with longer timeframe"],
            "assessment_path": "/app/strategies/stub_momentum_v1/assessment.json",
            "input_tokens": 3000,
            "output_tokens": 1500,
        }
