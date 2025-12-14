"""Agent workers for research cycle phases.

This module contains worker classes for each phase of the agent research cycle:
- StubDesignWorker / DesignWorker - Strategy design (Claude)
- StubTrainingWorker - Training simulation (stubs) / integration with TrainingService
- StubBacktestWorker - Backtest simulation (stubs) / integration with BacktestService
- StubAssessmentWorker / AssessmentWorker - Result assessment (Claude)
"""

from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubBacktestWorker,
    StubDesignWorker,
    StubTrainingWorker,
)

__all__ = [
    "StubDesignWorker",
    "StubTrainingWorker",
    "StubBacktestWorker",
    "StubAssessmentWorker",
]
