"""Agent workers for research cycle phases.

This module contains worker classes for each phase of the agent research cycle:
- AgentResearchWorker - Orchestrator that manages the full research cycle
- StubDesignWorker / DesignWorker - Strategy design (Claude)
- StubTrainingWorker - Training simulation (stubs) / integration with TrainingService
- StubBacktestWorker - Backtest simulation (stubs) / integration with BacktestService
- StubAssessmentWorker / AssessmentWorker - Result assessment (Claude)
"""

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubBacktestWorker,
    StubDesignWorker,
    StubTrainingWorker,
)

__all__ = [
    "AgentResearchWorker",
    "StubDesignWorker",
    "StubTrainingWorker",
    "StubBacktestWorker",
    "StubAssessmentWorker",
]
