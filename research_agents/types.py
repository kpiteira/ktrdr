"""
Shared types and enums for the research agents system.

This module contains common type definitions used across the research agents
architecture, extracted from the legacy ResearchAgentMVP for reusability.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


class ResearchPhase(str, Enum):
    """Research workflow phases"""
    IDLE = "idle"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EXPERIMENT_DESIGN = "experiment_design"
    EXPERIMENT_EXECUTION = "experiment_execution"
    RESULTS_ANALYSIS = "results_analysis"
    KNOWLEDGE_INTEGRATION = "knowledge_integration"
    STRATEGY_OPTIMIZATION = "strategy_optimization"
    SESSION_COMPLETION = "session_completion"


class ResearchStrategy(str, Enum):
    """Research strategy types"""
    EXPLORATORY = "exploratory"  # Broad exploration of new ideas
    FOCUSED = "focused"          # Deep dive on specific area
    OPTIMIZATION = "optimization" # Improve existing strategies
    VALIDATION = "validation"    # Validate previous findings


@dataclass
class ResearchCycle:
    """Represents a single research cycle"""
    cycle_id: UUID
    session_id: UUID
    strategy: ResearchStrategy
    phase: ResearchPhase
    hypotheses: List[Dict[str, Any]]
    experiments: List[UUID]
    insights: List[str]
    fitness_scores: List[float]
    started_at: datetime
    completed_at: Optional[datetime] = None
    success_rate: float = 0.0


@dataclass
class ResearchProgress:
    """Tracks overall research progress"""
    total_cycles: int
    completed_cycles: int
    active_experiments: int
    best_fitness_score: float
    avg_fitness_score: float
    successful_strategies: List[str]
    failed_experiments: int
    knowledge_base_size: int
    research_velocity: float  # cycles per hour