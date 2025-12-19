"""Stub workers for testing orchestrator without real operations.

Only Design and Assessment need stubs because they make Claude API calls.
Training and Backtest are handled by the orchestrator calling services directly.

These workers simulate each phase with configurable delays (default ~30s per phase).
Sleep in small intervals for responsive cancellation.

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

    async def run(self, operation_id: str, model: str | None = None) -> dict[str, Any]:
        """Simulate design phase.

        Args:
            operation_id: The operation ID for tracking.
            model: Model to use (ignored in stub, for interface compatibility).

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


class StubAssessmentWorker:
    """Stub that simulates Claude assessment.

    Returns mock assessment as if Claude had evaluated the results.
    """

    async def run(
        self, operation_id: str, results: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]:
        """Simulate assessment phase.

        Args:
            operation_id: The operation ID for tracking.
            results: Combined training and backtest results.
            model: Model to use (ignored in stub, for interface compatibility).

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
