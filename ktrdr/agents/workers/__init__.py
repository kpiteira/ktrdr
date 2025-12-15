"""Agent workers for research cycle phases.

This module contains worker classes for each phase of the agent research cycle:
- AgentResearchWorker - Orchestrator that manages the full research cycle
- StubDesignWorker / AgentDesignWorker - Strategy design (Claude)
- StubAssessmentWorker / AgentAssessmentWorker - Result assessment (Claude)

Training and Backtest phases are handled by the orchestrator calling
TrainingService and BacktestingService directly.
"""

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubDesignWorker,
)

__all__ = [
    "AgentResearchWorker",
    "StubDesignWorker",
    "StubAssessmentWorker",
]
