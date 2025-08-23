"""
Research Agent MVP - Unified Autonomous Research System

This module implements a comprehensive research agent that combines the
researcher and assistant agents into a unified system capable of autonomous
research workflows from hypothesis generation to results analysis.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass

import logging

from .base import BaseResearchAgent
from .researcher import ResearcherAgent
from .assistant import AssistantAgent
from ..services.database import ResearchDatabaseService
from ..services.research_orchestrator import (
    ResearchOrchestrator,
    ExperimentConfig,
    ExperimentType,
    ExperimentStatus,
)

logger = logging.getLogger(__name__)


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
    FOCUSED = "focused"  # Deep dive on specific area
    OPTIMIZATION = "optimization"  # Improve existing strategies
    VALIDATION = "validation"  # Validate previous findings


@dataclass
class ResearchCycle:
    """Represents a complete research cycle"""

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
    success_rate: Optional[float] = None


@dataclass
class ResearchProgress:
    """Tracks research progress and metrics"""

    total_cycles: int
    completed_cycles: int
    active_experiments: int
    best_fitness_score: float
    avg_fitness_score: float
    successful_strategies: List[str]
    failed_experiments: int
    knowledge_base_size: int
    research_velocity: float  # cycles per hour


class ResearchAgentMVP(BaseResearchAgent):
    """
    Research Agent MVP - Autonomous Research Orchestrator

    Combines researcher and assistant capabilities into a unified system
    that can autonomously conduct research from hypothesis to results.

    Key Capabilities:
    - Autonomous research cycle execution
    - Hypothesis generation and experiment design
    - Experiment execution and monitoring
    - Results analysis and knowledge integration
    - Strategy adaptation and optimization
    - Long-term research session management
    """

    def __init__(self, agent_id: str, **config):
        super().__init__(agent_id, "research_mvp", **config)

        # Core research configuration
        self.max_concurrent_experiments = config.get("max_concurrent_experiments", 2)
        self.hypothesis_batch_size = config.get("hypothesis_batch_size", 5)
        self.cycle_timeout_hours = config.get("cycle_timeout_hours", 4)
        self.fitness_threshold = config.get("fitness_threshold", 1.5)
        self.exploration_ratio = config.get("exploration_ratio", 0.3)

        # Research state
        self.current_session_id: Optional[UUID] = None
        self.current_cycle: Optional[ResearchCycle] = None
        self.research_progress: Optional[ResearchProgress] = None
        self.active_experiments: Dict[UUID, Dict[str, Any]] = {}

        # Sub-agents (will be initialized during startup)
        self.researcher: Optional[ResearcherAgent] = None
        self.assistant: Optional[AssistantAgent] = None

        # Services
        self.db_service: Optional[ResearchDatabaseService] = None
        self.orchestrator: Optional[ResearchOrchestrator] = None

        # Research strategy state
        self.current_strategy = ResearchStrategy.EXPLORATORY
        self.strategy_performance: Dict[ResearchStrategy, float] = {}
        self.knowledge_cache: Dict[str, Any] = {}

        logger.info("Info message")

    async def initialize(self) -> None:
        """Initialize the research agent and all sub-components"""
        try:
            await super().initialize()

            # Initialize research progress tracking
            await self._initialize_research_progress()

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def run(self) -> None:
        """Main research agent execution loop"""
        try:
            logger.info("Info message")

            # Initialize is_running flag
            self.is_running = True

            while self.is_running:
                try:
                    # Update agent status
                    await self._update_status("active", "Running research cycle")

                    # Execute one complete research cycle
                    await self._execute_research_cycle()

                    # Brief pause between cycles
                    await asyncio.sleep(10)

                except asyncio.CancelledError:
                    logger.info("Info message")
                    break

                except Exception as e:
                    logger.error("Error occurred")

                    # Update status to error and wait before retry
                    await self._update_status(
                        "error", f"Research cycle error: {str(e)}"
                    )
                    await asyncio.sleep(60)  # Wait 1 minute before retry

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            await self._update_status("error", f"Critical error: {str(e)}")
            raise
        finally:
            await self._cleanup()

    async def start_research_session(
        self,
        session_name: str,
        strategic_goals: List[str],
        strategy: ResearchStrategy = ResearchStrategy.EXPLORATORY,
    ) -> UUID:
        """Start a new research session"""
        try:
            # Create research session in database
            session_id = await self.db_service.create_session(
                session_name=session_name,
                description=f"Autonomous research session - {strategy.value}",
                strategic_goals=strategic_goals,
                resource_allocation={
                    "max_experiments_per_cycle": self.hypothesis_batch_size,
                    "max_concurrent_experiments": self.max_concurrent_experiments,
                    "fitness_threshold": self.fitness_threshold,
                },
            )

            self.current_session_id = session_id
            self.current_strategy = strategy

            # Initialize research progress
            self.research_progress = ResearchProgress(
                total_cycles=0,
                completed_cycles=0,
                active_experiments=0,
                best_fitness_score=0.0,
                avg_fitness_score=0.0,
                successful_strategies=[],
                failed_experiments=0,
                knowledge_base_size=await self._get_knowledge_base_size(),
                research_velocity=0.0,
            )

            logger.info("Info message")

            return session_id

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _execute_research_cycle(self) -> None:
        """Execute one complete research cycle"""
        if not self.current_session_id:
            # Start default exploratory session
            await self.start_research_session(
                session_name=f"Auto-Session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                strategic_goals=[
                    "Discover novel trading strategies",
                    "Optimize performance metrics",
                ],
                strategy=ResearchStrategy.EXPLORATORY,
            )

        cycle_id = uuid4()
        cycle_start = datetime.now(timezone.utc)

        try:
            # Create new research cycle
            self.current_cycle = ResearchCycle(
                cycle_id=cycle_id,
                session_id=self.current_session_id,
                strategy=self.current_strategy,
                phase=ResearchPhase.HYPOTHESIS_GENERATION,
                hypotheses=[],
                experiments=[],
                insights=[],
                fitness_scores=[],
                started_at=cycle_start,
            )

            logger.info("Info message")

            # Phase 1: Generate hypotheses
            await self._phase_hypothesis_generation()

            # Phase 2: Design experiments
            await self._phase_experiment_design()

            # Phase 3: Execute experiments
            await self._phase_experiment_execution()

            # Phase 4: Analyze results
            await self._phase_results_analysis()

            # Phase 5: Integrate knowledge
            await self._phase_knowledge_integration()

            # Phase 6: Optimize strategy
            await self._phase_strategy_optimization()

            # Complete cycle
            await self._complete_research_cycle()

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")

            # Update cycle with failure information
            if self.current_cycle:
                self.current_cycle.phase = ResearchPhase.IDLE
                await self._record_cycle_failure(str(e))

            raise

    async def _phase_hypothesis_generation(self) -> None:
        """Phase 1: Generate research hypotheses"""
        self.current_cycle.phase = ResearchPhase.HYPOTHESIS_GENERATION

        logger.info("Info message")

        try:
            # Get recent knowledge for context
            recent_knowledge = await self._get_recent_insights(limit=10)

            # Determine exploration vs exploitation
            if self._should_explore():
                # Exploratory hypothesis generation
                hypotheses = await self.researcher.generate_novel_hypotheses(
                    session_id=self.current_session_id,
                    count=self.hypothesis_batch_size,
                    context={"recent_insights": recent_knowledge},
                )
            else:
                # Focused hypothesis generation based on successful patterns
                successful_patterns = await self._get_successful_patterns()
                hypotheses = await self.researcher.generate_focused_hypotheses(
                    session_id=self.current_session_id,
                    patterns=successful_patterns,
                    count=self.hypothesis_batch_size,
                )

            self.current_cycle.hypotheses = hypotheses

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _phase_experiment_design(self) -> None:
        """Phase 2: Design experiments from hypotheses"""
        self.current_cycle.phase = ResearchPhase.EXPERIMENT_DESIGN

        logger.info("Info message")

        try:
            experiment_configs = []

            for i, hypothesis in enumerate(self.current_cycle.hypotheses):
                # Design experiment for this hypothesis
                config = await self.researcher.design_experiment(
                    hypothesis=hypothesis,
                    session_id=self.current_session_id,
                    experiment_name=f"Cycle-{self.current_cycle.cycle_id.hex[:8]}-Exp-{i+1}",
                )

                experiment_configs.append(config)

            # Create experiments in database
            experiment_ids = []
            for config in experiment_configs:
                exp_id = await self.orchestrator.create_experiment(
                    session_id=self.current_session_id, config=config
                )
                experiment_ids.append(exp_id)

            self.current_cycle.experiments = experiment_ids

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _phase_experiment_execution(self) -> None:
        """Phase 3: Execute experiments concurrently"""
        self.current_cycle.phase = ResearchPhase.EXPERIMENT_EXECUTION

        logger.info("Info message")

        try:
            # Start experiments with concurrency limit
            experiment_tasks = []
            semaphore = asyncio.Semaphore(self.max_concurrent_experiments)

            async def run_experiment(exp_id: UUID):
                async with semaphore:
                    try:
                        # Start experiment
                        await self.orchestrator.start_experiment(exp_id)

                        # Monitor experiment using assistant
                        result = await self.assistant.monitor_experiment(exp_id)

                        return exp_id, result

                    except Exception as e:
                        logger.error("Error occurred")
                        return exp_id, None

            # Create tasks for all experiments
            for exp_id in self.current_cycle.experiments:
                task = asyncio.create_task(run_experiment(exp_id))
                experiment_tasks.append(task)

            # Wait for all experiments to complete
            results = await asyncio.gather(*experiment_tasks, return_exceptions=True)

            # Process results
            successful_experiments = 0
            for exp_id, result in results:
                if isinstance(result, Exception):
                    logger.error("Error occurred")
                elif result is not None:
                    successful_experiments += 1
                    if hasattr(result, "fitness_score") and result.fitness_score:
                        self.current_cycle.fitness_scores.append(result.fitness_score)

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _phase_results_analysis(self) -> None:
        """Phase 4: Analyze experiment results"""
        self.current_cycle.phase = ResearchPhase.RESULTS_ANALYSIS

        logger.info("Info message")

        try:
            # Get experiment results
            experiment_results = []
            for exp_id in self.current_cycle.experiments:
                try:
                    status = await self.orchestrator.get_experiment_status(exp_id)
                    if status.get("status") == ExperimentStatus.COMPLETED.value:
                        experiment_results.append(status)
                except Exception as e:
                    logger.error("Error occurred")

            # Analyze results using assistant
            if experiment_results:
                analysis = await self.assistant.analyze_experiment_results(
                    experiment_results=experiment_results,
                    session_id=self.current_session_id,
                )

                self.current_cycle.insights = analysis.get("insights", [])

                # Extract fitness scores from both experiment results and analysis
                for result in experiment_results:
                    if result.get("fitness_score"):
                        self.current_cycle.fitness_scores.append(
                            result["fitness_score"]
                        )

                # Also extract fitness score from analysis if available
                if analysis.get("fitness_score"):
                    self.current_cycle.fitness_scores.append(analysis["fitness_score"])

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _phase_knowledge_integration(self) -> None:
        """Phase 5: Integrate new knowledge into knowledge base"""
        self.current_cycle.phase = ResearchPhase.KNOWLEDGE_INTEGRATION

        logger.info("Info message")

        try:
            # Store insights in knowledge base
            for insight in self.current_cycle.insights:
                # Calculate quality score based on associated fitness scores
                quality_score = 0.5  # Default
                if self.current_cycle.fitness_scores:
                    quality_score = (
                        max(self.current_cycle.fitness_scores) / 3.0
                    )  # Normalize

                await self.db_service.create_knowledge_entry(
                    content=insight,
                    knowledge_type="research_insight",
                    source_experiment_id=(
                        self.current_cycle.experiments[0]
                        if self.current_cycle.experiments
                        else None
                    ),
                    tags=["autonomous_research", self.current_strategy.value],
                    quality_score=min(quality_score, 1.0),  # Cap at 1.0
                )

            # Update knowledge cache
            await self._refresh_knowledge_cache()

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _phase_strategy_optimization(self) -> None:
        """Phase 6: Optimize research strategy based on results"""
        self.current_cycle.phase = ResearchPhase.STRATEGY_OPTIMIZATION

        logger.info("Info message")

        try:
            # Calculate cycle performance
            cycle_performance = 0.0
            if self.current_cycle.fitness_scores:
                cycle_performance = sum(self.current_cycle.fitness_scores) / len(
                    self.current_cycle.fitness_scores
                )

            # Update strategy performance tracking
            if self.current_strategy not in self.strategy_performance:
                self.strategy_performance[self.current_strategy] = []

            # Store recent performance (keep last 10 cycles)
            if len(self.strategy_performance[self.current_strategy]) >= 10:
                self.strategy_performance[self.current_strategy].pop(0)
            self.strategy_performance[self.current_strategy].append(cycle_performance)

            # Adapt strategy based on performance
            await self._adapt_research_strategy()

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")
            raise

    async def _complete_research_cycle(self) -> None:
        """Complete the current research cycle"""
        if not self.current_cycle:
            return

        self.current_cycle.phase = ResearchPhase.SESSION_COMPLETION
        self.current_cycle.completed_at = datetime.now(timezone.utc)

        # Calculate success rate
        if self.current_cycle.experiments:
            successful_experiments = len(
                [
                    score
                    for score in self.current_cycle.fitness_scores
                    if score > self.fitness_threshold
                ]
            )
            self.current_cycle.success_rate = successful_experiments / len(
                self.current_cycle.experiments
            )
        else:
            self.current_cycle.success_rate = 0.0

        # Update research progress
        if self.research_progress:
            self.research_progress.completed_cycles += 1
            self.research_progress.total_cycles += 1

            if self.current_cycle.fitness_scores:
                max_score = max(self.current_cycle.fitness_scores)
                if max_score > self.research_progress.best_fitness_score:
                    self.research_progress.best_fitness_score = max_score

                # Update average (simple moving average)
                current_avg = self.research_progress.avg_fitness_score
                cycle_avg = sum(self.current_cycle.fitness_scores) / len(
                    self.current_cycle.fitness_scores
                )
                self.research_progress.avg_fitness_score = (current_avg + cycle_avg) / 2

            # Calculate research velocity (cycles per hour)
            duration_hours = (
                self.current_cycle.completed_at - self.current_cycle.started_at
            ).total_seconds() / 3600
            if duration_hours > 0:
                self.research_progress.research_velocity = 1.0 / duration_hours

        # Log cycle completion
        logger.info("Info message")

        # Reset for next cycle
        self.current_cycle = None

    # Helper methods

    async def _initialize_research_progress(self) -> None:
        """Initialize research progress tracking"""
        knowledge_size = await self._get_knowledge_base_size()

        self.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=knowledge_size,
            research_velocity=0.0,
        )

    async def _get_knowledge_base_size(self) -> int:
        """Get current knowledge base size"""
        try:
            stats = await self.db_service.get_knowledge_base_statistics()
            return stats.get("total_entries", 0)
        except Exception:
            return 0

    async def _get_recent_insights(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent insights from knowledge base"""
        try:
            return await self.db_service.search_knowledge_base(
                query="", limit=limit, knowledge_type="research_insight"
            )
        except Exception:
            return []

    async def _get_successful_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns from successful experiments"""
        try:
            # Get high-quality knowledge entries
            return await self.db_service.search_knowledge_base(
                query="",
                limit=5,
                knowledge_type="research_insight",
                min_quality_score=0.7,
            )
        except Exception:
            return []

    def _should_explore(self) -> bool:
        """Determine if agent should explore (vs exploit)"""
        # Use epsilon-greedy strategy
        import random

        return random.random() < self.exploration_ratio

    async def _adapt_research_strategy(self) -> None:
        """Adapt research strategy based on performance"""
        if not self.strategy_performance:
            return

        # Calculate average performance for each strategy
        strategy_averages = {}
        for strategy, performances in self.strategy_performance.items():
            if performances:
                strategy_averages[strategy] = sum(performances) / len(performances)

        if not strategy_averages:
            return

        # Find best performing strategy
        best_strategy = max(strategy_averages.items(), key=lambda x: x[1])[0]

        # Switch to best strategy if significantly better
        current_avg = strategy_averages.get(self.current_strategy, 0.0)
        best_avg = strategy_averages[best_strategy]

        if best_avg > current_avg * 1.2:  # 20% improvement threshold
            logger.info("Info message")
            self.current_strategy = best_strategy

    async def _refresh_knowledge_cache(self) -> None:
        """Refresh local knowledge cache"""
        try:
            recent_knowledge = await self._get_recent_insights(limit=20)
            self.knowledge_cache = {
                "recent_insights": recent_knowledge,
                "updated_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.error("Error occurred")

    async def _record_cycle_failure(self, error_message: str) -> None:
        """Record research cycle failure"""
        if self.research_progress:
            self.research_progress.failed_experiments += 1

        # Store failure insight
        await self.db_service.create_knowledge_entry(
            content=f"Research cycle failure: {error_message}",
            knowledge_type="research_failure",
            tags=["failure_analysis", "autonomous_research"],
            quality_score=0.1,
        )

    async def get_research_status(self) -> Dict[str, Any]:
        """Get comprehensive research status"""
        status = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "current_session_id": (
                str(self.current_session_id) if self.current_session_id else None
            ),
            "current_strategy": (
                self.current_strategy.value if self.current_strategy else None
            ),
            "research_progress": None,
            "current_cycle": None,
            "active_experiments": len(self.active_experiments),
            "strategy_performance": {},
        }

        if self.research_progress:
            status["research_progress"] = {
                "total_cycles": self.research_progress.total_cycles,
                "completed_cycles": self.research_progress.completed_cycles,
                "best_fitness_score": self.research_progress.best_fitness_score,
                "avg_fitness_score": self.research_progress.avg_fitness_score,
                "research_velocity": self.research_progress.research_velocity,
                "knowledge_base_size": self.research_progress.knowledge_base_size,
            }

        if self.current_cycle:
            status["current_cycle"] = {
                "cycle_id": str(self.current_cycle.cycle_id),
                "phase": self.current_cycle.phase.value,
                "hypotheses_count": len(self.current_cycle.hypotheses),
                "experiments_count": len(self.current_cycle.experiments),
                "insights_count": len(self.current_cycle.insights),
                "started_at": self.current_cycle.started_at.isoformat(),
            }

        # Strategy performance summary
        for strategy, performances in self.strategy_performance.items():
            if performances:
                status["strategy_performance"][strategy.value] = {
                    "average_score": sum(performances) / len(performances),
                    "recent_scores": performances[-3:],  # Last 3 scores
                    "total_cycles": len(performances),
                }

        return status

    # ========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS (from BaseResearchAgent)
    # ========================================================================

    async def _initialize_agent(self) -> None:
        """Agent-specific initialization logic"""
        # Initialize database service
        from ..services.database import create_database_service

        self.db_service = create_database_service(self.database_url)
        await self.db_service.initialize()

        # Initialize research orchestrator
        from ..services.research_orchestrator import create_research_orchestrator

        self.orchestrator = await create_research_orchestrator(
            db_service=self.db_service,
            max_concurrent_experiments=self.max_concurrent_experiments,
        )

        # Initialize sub-agents
        researcher_config = {
            **self.config,
            "database_service": self.db_service,
            "creativity_level": 0.8,
            "hypothesis_batch_size": self.hypothesis_batch_size,
        }

        assistant_config = {
            **self.config,
            "database_service": self.db_service,
            "orchestrator": self.orchestrator,
            "enable_early_stopping": True,
        }

        self.researcher = ResearcherAgent(
            f"{self.agent_id}_researcher", **researcher_config
        )

        self.assistant = AssistantAgent(
            f"{self.agent_id}_assistant", **assistant_config
        )

        # Initialize sub-agents
        await self.researcher.initialize()
        await self.assistant.initialize()

        logger.info("Info message")

    async def _execute_cycle(self) -> None:
        """Main agent execution cycle - called repeatedly"""
        try:
            # If no active session, start one
            if not self.current_session_id:
                self.current_session_id = await self.start_research_session(
                    session_name=f"Auto-Session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    strategic_goals=[
                        "Discover novel trading strategies",
                        "Optimize performance metrics",
                    ],
                    strategy=ResearchStrategy.EXPLORATORY,
                )

            # Execute one research cycle
            await self._execute_research_cycle()

            # Brief pause between cycles
            await asyncio.sleep(10)

        except Exception as e:
            logger.error("Error occurred")
            await self._record_cycle_failure(str(e))
            # Continue running despite errors
            await asyncio.sleep(30)

    async def _cleanup_agent(self) -> None:
        """Agent-specific cleanup logic"""
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Cleanup resources"""
        try:
            # Shutdown sub-agents (handle errors individually)
            if self.researcher:
                try:
                    await self.researcher.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down researcher: {e}")

            if self.assistant:
                try:
                    await self.assistant.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down assistant: {e}")

            # Shutdown services (handle errors individually)
            if self.orchestrator:
                try:
                    await self.orchestrator.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down orchestrator: {e}")

            if self.db_service:
                try:
                    await self.db_service.close()
                except Exception as e:
                    logger.error(f"Error closing database: {e}")

            logger.info("Info message")

        except Exception as e:
            logger.error("Error occurred")


# Factory function for creating Research Agent MVP
async def create_research_agent_mvp(agent_id: str, **config) -> ResearchAgentMVP:
    """Create and initialize a Research Agent MVP instance"""
    agent = ResearchAgentMVP(agent_id, **config)
    await agent.initialize()
    return agent
