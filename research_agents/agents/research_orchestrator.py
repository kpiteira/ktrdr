"""
Research Orchestrator Agent

This is the replacement for the ResearchAgentMVP god class.
It coordinates between focused, single-responsibility components
to achieve the same functionality with better architecture.

Responsibilities:
- Orchestrate research workflow phases
- Coordinate between components
- Manage research state and transitions
- Handle high-level research session management
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ktrdr import get_logger
from ktrdr.errors import ProcessingError

from .base import BaseResearchAgent
from .research_agent_mvp import (
    ResearchPhase, 
    ResearchStrategy, 
    ResearchCycle, 
    ResearchProgress
)
from ..components.interfaces import ResearchContext
from ..components.hypothesis_generator import HypothesisGenerator
from ..components.experiment_executor import ExperimentExecutor
from ..components.results_analyzer import ResultsAnalyzer
from ..components.knowledge_integrator import KnowledgeIntegrator
from ..components.strategy_optimizer import StrategyOptimizer

logger = get_logger(__name__)


class ResearchOrchestrator(BaseResearchAgent):
    """
    Research Orchestrator - Clean Architecture Implementation
    
    Replaces the ResearchAgentMVP god class with a focused orchestrator
    that coordinates between single-responsibility components.
    
    This follows the SOLID principles and provides better:
    - Testability (each component can be tested independently)
    - Maintainability (changes affect only relevant components)
    - Extensibility (new components can be easily added)
    - Reusability (components can be used in other contexts)
    """
    
    def __init__(
        self, 
        agent_id: str,
        hypothesis_generator: HypothesisGenerator,
        experiment_executor: ExperimentExecutor,
        results_analyzer: ResultsAnalyzer,
        knowledge_integrator: KnowledgeIntegrator,
        strategy_optimizer: StrategyOptimizer,
        **config
    ):
        super().__init__(agent_id, "research_orchestrator", **config)
        
        # Injected components (Dependency Injection)
        self.hypothesis_generator = hypothesis_generator
        self.experiment_executor = experiment_executor
        self.results_analyzer = results_analyzer
        self.knowledge_integrator = knowledge_integrator
        self.strategy_optimizer = strategy_optimizer
        
        # Research state
        self.current_session_id: Optional[UUID] = None
        self.current_cycle: Optional[ResearchCycle] = None
        self.current_strategy: ResearchStrategy = ResearchStrategy.EXPLORATORY
        self.research_progress: Optional[ResearchProgress] = None
        
        # Configuration
        self.hypothesis_batch_size = config.get("hypothesis_batch_size", 5)
        self.max_concurrent_experiments = config.get("max_concurrent_experiments", 2)
        self.fitness_threshold = config.get("fitness_threshold", 0.6)
        self.cycle_timeout_hours = config.get("cycle_timeout_hours", 4)
        
        logger.info(f"Research orchestrator initialized with {len(self._get_component_names())} components")
    
    def _get_component_names(self) -> List[str]:
        """Get names of injected components for logging"""
        return [
            type(self.hypothesis_generator).__name__,
            type(self.experiment_executor).__name__,
            type(self.results_analyzer).__name__,
            type(self.knowledge_integrator).__name__,
            type(self.strategy_optimizer).__name__
        ]
    
    async def start_research_session(
        self,
        research_goal: str,
        strategy: ResearchStrategy = ResearchStrategy.EXPLORATORY,
        max_cycles: int = 10,
        session_config: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Start a new research session"""
        
        try:
            session_id = uuid4()
            self.current_session_id = session_id
            self.current_strategy = strategy
            
            logger.info(f"Starting research session {session_id} with strategy: {strategy}, goal: {research_goal}")
            
            # Initialize research progress tracking
            await self._initialize_research_progress()
            
            # Store session metadata
            session_metadata = {
                "session_id": str(session_id),
                "research_goal": research_goal,
                "strategy": strategy,
                "max_cycles": max_cycles,
                "config": session_config or {},
                "started_at": datetime.now(timezone.utc).isoformat(),
                "agent_id": self.agent_id
            }
            
            # Begin research cycles
            self.is_running = True
            await self._update_status("research_session", f"Research session started: {research_goal}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start research session: {e}")
            raise ProcessingError(
                "Research session startup failed",
                error_code="RESEARCH_SESSION_START_FAILED", 
                details={
                    "research_goal": research_goal,
                    "strategy": strategy,
                    "original_error": str(e)
                }
            ) from e
    
    async def _execute_cycle(self) -> None:
        """Execute main agent cycle - delegates to research cycle execution"""
        await self._execute_research_cycle()
    
    async def _execute_research_cycle(self) -> None:
        """Execute a complete research cycle using components"""
        
        try:
            # Create new research cycle
            cycle_id = uuid4()
            self.current_cycle = ResearchCycle(
                cycle_id=cycle_id,
                session_id=self.current_session_id,
                strategy=self.current_strategy,
                phase=ResearchPhase.IDLE,
                hypotheses=[],
                experiments=[],
                insights=[],
                fitness_scores=[],
                started_at=datetime.now(timezone.utc)
            )
            
            logger.info(f"Starting research cycle {cycle_id} with strategy: {self.current_strategy}")
            
            # Create research context
            context = self._create_research_context()
            
            # Execute research phases in sequence
            await self._phase_hypothesis_generation(context)
            await self._phase_experiment_design(context)  
            await self._phase_experiment_execution(context)
            await self._phase_results_analysis(context)
            await self._phase_knowledge_integration(context)
            await self._phase_strategy_optimization(context)
            
            # Complete the cycle
            await self._complete_research_cycle()
            
            logger.info(f"Research cycle {cycle_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Research cycle failed: {e}")
            
            # Update cycle with failure information
            if self.current_cycle:
                self.current_cycle.phase = ResearchPhase.IDLE
                await self._record_cycle_failure(str(e))
            
            raise
    
    def _create_research_context(self) -> ResearchContext:
        """Create research context for components"""
        
        return ResearchContext(
            session_id=self.current_session_id,
            cycle_id=self.current_cycle.cycle_id,
            agent_id=self.agent_id,
            current_phase=self.current_cycle.phase,
            strategy=self.current_strategy,
            progress=self._get_progress_dict(),
            config=self.config
        )
    
    def _get_progress_dict(self) -> Dict[str, Any]:
        """Convert research progress to dictionary"""
        
        if not self.research_progress:
            return {}
        
        return {
            "total_cycles": self.research_progress.total_cycles,
            "completed_cycles": self.research_progress.completed_cycles,
            "active_experiments": self.research_progress.active_experiments,
            "best_fitness_score": self.research_progress.best_fitness_score,
            "avg_fitness_score": self.research_progress.avg_fitness_score,
            "successful_strategies": self.research_progress.successful_strategies,
            "failed_experiments": self.research_progress.failed_experiments,
            "knowledge_base_size": self.research_progress.knowledge_base_size,
            "research_velocity": self.research_progress.research_velocity
        }
    
    async def _phase_hypothesis_generation(self, context: ResearchContext) -> None:
        """Phase 1: Generate research hypotheses using component"""
        
        self.current_cycle.phase = ResearchPhase.HYPOTHESIS_GENERATION
        context.current_phase = ResearchPhase.HYPOTHESIS_GENERATION
        
        logger.info(f"Phase 1: Hypothesis generation for cycle {self.current_cycle.cycle_id}")
        
        try:
            # Load knowledge context for hypothesis generation
            recent_knowledge = await self.knowledge_integrator.search_knowledge(
                "recent insights research patterns", context
            )
            context.knowledge_cache["recent_insights"] = recent_knowledge
            
            # Generate hypotheses using component
            hypotheses = await self.hypothesis_generator.generate_hypotheses(
                context, count=self.hypothesis_batch_size
            )
            
            # Store hypotheses in cycle (convert to dict format for compatibility)
            self.current_cycle.hypotheses = [
                {
                    "hypothesis_id": str(h.hypothesis_id),
                    "content": h.content,
                    "confidence": h.confidence,
                    "experiment_type": h.experiment_type,
                    "expected_outcome": h.expected_outcome,
                    "rationale": h.rationale,
                    "parameters": h.parameters,
                    "metadata": h.metadata
                }
                for h in hypotheses
            ]
            
            context.hypotheses = hypotheses
            
            logger.info(f"Generated {len(hypotheses)} hypotheses for cycle {self.current_cycle.cycle_id}")
            
        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            raise
    
    async def _phase_experiment_design(self, context: ResearchContext) -> None:
        """Phase 2: Design experiments from hypotheses"""
        
        self.current_cycle.phase = ResearchPhase.EXPERIMENT_DESIGN
        context.current_phase = ResearchPhase.EXPERIMENT_DESIGN
        
        logger.info(f"Phase 2: Experiment design for cycle {self.current_cycle.cycle_id}")
        
        try:
            # Convert hypotheses to experiment configs
            from ..components.interfaces import ExperimentConfig
            
            experiment_configs = []
            experiment_ids = []
            
            for hypothesis_dict in self.current_cycle.hypotheses:
                experiment_id = uuid4()
                experiment_ids.append(experiment_id)
                
                # Create experiment configuration
                config = ExperimentConfig(
                    experiment_id=experiment_id,
                    hypothesis_id=UUID(hypothesis_dict["hypothesis_id"]),
                    experiment_type=hypothesis_dict["experiment_type"],
                    parameters=hypothesis_dict["parameters"],
                    timeout_hours=self.cycle_timeout_hours,
                    priority="normal",
                    metadata={
                        "cycle_id": str(self.current_cycle.cycle_id),
                        "session_id": str(self.current_session_id),
                        "strategy": self.current_strategy
                    }
                )
                experiment_configs.append(config)
            
            self.current_cycle.experiments = experiment_ids
            context.experiments = experiment_ids
            
            # Store configs for execution phase
            context.knowledge_cache["experiment_configs"] = experiment_configs
            
            logger.info(f"Designed {len(experiment_configs)} experiments for cycle {self.current_cycle.cycle_id}")
            
        except Exception as e:
            logger.error(f"Experiment design failed: {e}")
            raise
    
    async def _phase_experiment_execution(self, context: ResearchContext) -> None:
        """Phase 3: Execute experiments using component"""
        
        self.current_cycle.phase = ResearchPhase.EXPERIMENT_EXECUTION
        context.current_phase = ResearchPhase.EXPERIMENT_EXECUTION
        
        logger.info(f"Phase 3: Experiment execution for cycle {self.current_cycle.cycle_id}")
        
        try:
            experiment_configs = context.knowledge_cache["experiment_configs"]
            
            # Execute experiments concurrently using component
            tasks = []
            for config in experiment_configs:
                task = asyncio.create_task(
                    self.experiment_executor.execute_experiment(config, context)
                )
                tasks.append(task)
            
            # Wait for all experiments to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            experiment_results = []
            successful_experiments = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Experiment {i} failed with exception: {result}")
                else:
                    experiment_results.append(result)
                    if result.status == "completed" and result.fitness_score > 0:
                        successful_experiments += 1
                        self.current_cycle.fitness_scores.append(result.fitness_score)
            
            # Store results for analysis phase
            context.results = experiment_results
            
            logger.info(f"Experiment execution completed: {successful_experiments}/{len(experiment_configs)} successful")
            
        except Exception as e:
            logger.error(f"Experiment execution failed: {e}")
            raise
    
    async def _phase_results_analysis(self, context: ResearchContext) -> None:
        """Phase 4: Analyze results using component"""
        
        self.current_cycle.phase = ResearchPhase.RESULTS_ANALYSIS
        context.current_phase = ResearchPhase.RESULTS_ANALYSIS
        
        logger.info(f"Phase 4: Results analysis for cycle {self.current_cycle.cycle_id}")
        
        try:
            experiment_results = context.results
            analysis_reports = []
            
            # Analyze each experiment result
            for result in experiment_results:
                analysis = await self.results_analyzer.analyze_results(result, context)
                analysis_reports.append(analysis)
                
                # Extract insights
                self.current_cycle.insights.extend(analysis.insights)
                
                # Update fitness scores if not already included
                if result.fitness_score > 0 and result.fitness_score not in self.current_cycle.fitness_scores:
                    self.current_cycle.fitness_scores.append(result.fitness_score)
            
            # Store analysis reports
            context.knowledge_cache["analysis_reports"] = analysis_reports
            
            logger.info(f"Results analysis completed: {len(analysis_reports)} reports generated, {len(self.current_cycle.insights)} insights extracted")
            
        except Exception as e:
            logger.error(f"Results analysis failed: {e}")
            raise
    
    async def _phase_knowledge_integration(self, context: ResearchContext) -> None:
        """Phase 5: Integrate knowledge using component"""
        
        self.current_cycle.phase = ResearchPhase.KNOWLEDGE_INTEGRATION
        context.current_phase = ResearchPhase.KNOWLEDGE_INTEGRATION
        
        logger.info(f"Phase 5: Knowledge integration for cycle {self.current_cycle.cycle_id}")
        
        try:
            # Integrate insights into knowledge base
            integration_results = await self.knowledge_integrator.integrate_insights(
                self.current_cycle.insights, context
            )
            
            logger.info(f"Knowledge integration completed: {integration_results['integrated_count']} insights integrated")
            
        except Exception as e:
            logger.error(f"Knowledge integration failed: {e}")
            raise
    
    async def _phase_strategy_optimization(self, context: ResearchContext) -> None:
        """Phase 6: Optimize strategy using component"""
        
        self.current_cycle.phase = ResearchPhase.STRATEGY_OPTIMIZATION
        context.current_phase = ResearchPhase.STRATEGY_OPTIMIZATION
        
        logger.info(f"Phase 6: Strategy optimization for cycle {self.current_cycle.cycle_id}")
        
        try:
            # Calculate cycle performance
            cycle_performance = 0.0
            if self.current_cycle.fitness_scores:
                cycle_performance = sum(self.current_cycle.fitness_scores) / len(self.current_cycle.fitness_scores)
            
            performance = {
                "cycle_fitness": cycle_performance,
                "success_rate": len(self.current_cycle.fitness_scores) / max(len(self.current_cycle.experiments), 1),
                "experiment_count": len(self.current_cycle.experiments)
            }
            
            # Optimize parameters
            optimization_results = await self.strategy_optimizer.optimize_parameters(
                performance, context
            )
            
            # Adapt strategy if needed
            new_strategy = await self.strategy_optimizer.adapt_strategy(
                {"performance": performance}, context
            )
            
            if new_strategy != self.current_strategy:
                logger.info(f"Strategy adapted from {self.current_strategy} to {new_strategy}")
                self.current_strategy = new_strategy
            
            logger.info(f"Strategy optimization completed: {len(optimization_results['parameter_adjustments'])} parameter adjustments")
            
        except Exception as e:
            logger.error(f"Strategy optimization failed: {e}")
            raise
    
    async def _complete_research_cycle(self) -> None:
        """Complete the current research cycle"""
        
        if not self.current_cycle:
            return
        
        self.current_cycle.phase = ResearchPhase.SESSION_COMPLETION
        self.current_cycle.completed_at = datetime.now(timezone.utc)
        
        # Calculate success rate
        if self.current_cycle.experiments:
            successful_experiments = len([score for score in self.current_cycle.fitness_scores if score > self.fitness_threshold])
            self.current_cycle.success_rate = successful_experiments / len(self.current_cycle.experiments)
        else:
            self.current_cycle.success_rate = 0.0
        
        # Update research progress
        if self.research_progress:
            self.research_progress.completed_cycles += 1
            
            if self.current_cycle.fitness_scores:
                max_fitness = max(self.current_cycle.fitness_scores)
                if max_fitness > self.research_progress.best_fitness_score:
                    self.research_progress.best_fitness_score = max_fitness
        
        logger.info(f"Research cycle {self.current_cycle.cycle_id} completed with success rate: {self.current_cycle.success_rate:.2f}")
    
    async def _initialize_research_progress(self) -> None:
        """Initialize research progress tracking"""
        
        self.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=0,
            research_velocity=0.0
        )
        
        logger.debug("Research progress tracking initialized")
    
    async def _record_cycle_failure(self, error_message: str) -> None:
        """Record a cycle failure for tracking"""
        
        if self.research_progress:
            self.research_progress.failed_experiments += 1
        
        logger.warning(f"Recorded cycle failure: {error_message}")
    
    async def get_research_status(self) -> Dict[str, Any]:
        """Get comprehensive research status"""
        
        status = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "session_id": str(self.current_session_id) if self.current_session_id else None,
            "current_strategy": self.current_strategy,
            "is_running": self.is_running,
            "components": self._get_component_names()
        }
        
        if self.current_cycle:
            status["current_cycle"] = {
                "cycle_id": str(self.current_cycle.cycle_id),
                "phase": self.current_cycle.phase,
                "started_at": self.current_cycle.started_at.isoformat(),
                "hypotheses_count": len(self.current_cycle.hypotheses),
                "experiments_count": len(self.current_cycle.experiments),
                "insights_count": len(self.current_cycle.insights),
                "fitness_scores": self.current_cycle.fitness_scores,
                "success_rate": self.current_cycle.success_rate
            }
        
        if self.research_progress:
            status["progress"] = self._get_progress_dict()
        
        return status


async def create_research_orchestrator(
    agent_id: str,
    llm_service,
    ktrdr_service,
    database_service,
    **config
) -> ResearchOrchestrator:
    """Factory function to create a fully configured ResearchOrchestrator"""
    
    # Create components with dependency injection
    hypothesis_generator = HypothesisGenerator(
        llm_service=llm_service,
        exploration_ratio=config.get("exploration_ratio", 0.3),
        min_confidence_threshold=config.get("min_confidence_threshold", 0.6)
    )
    
    experiment_executor = ExperimentExecutor(
        ktrdr_service=ktrdr_service,
        max_concurrent_experiments=config.get("max_concurrent_experiments", 2),
        default_timeout_hours=config.get("cycle_timeout_hours", 4)
    )
    
    # Create results analyzer (using existing service)
    from ..services.results_analyzer import ResultsAnalyzer as ResultsAnalyzerService
    analyzer_service = ResultsAnalyzerService(**config)
    results_analyzer = ResultsAnalyzer(analyzer_service)
    
    knowledge_integrator = KnowledgeIntegrator(
        database_service=database_service,
        min_quality_threshold=config.get("min_quality_threshold", 0.3)
    )
    
    strategy_optimizer = StrategyOptimizer(
        fitness_threshold=config.get("fitness_threshold", 0.6),
        min_cycles_for_adaptation=config.get("min_cycles_for_adaptation", 3)
    )
    
    # Create orchestrator with injected components
    orchestrator = ResearchOrchestrator(
        agent_id=agent_id,
        hypothesis_generator=hypothesis_generator,
        experiment_executor=experiment_executor,
        results_analyzer=results_analyzer,
        knowledge_integrator=knowledge_integrator,
        strategy_optimizer=strategy_optimizer,
        **config
    )
    
    return orchestrator