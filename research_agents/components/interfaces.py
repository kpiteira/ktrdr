"""
Component interfaces for research agent system.

Defines abstract base classes for each responsibility extracted from the 
ResearchAgentMVP god class. These interfaces enable dependency injection,
testing with mocks, and future implementation swapping.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime

# Forward declarations to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.research_agent_mvp import ResearchStrategy, ResearchPhase
else:
    # Runtime fallbacks
    from enum import Enum
    
    class ResearchStrategy(str, Enum):
        EXPLORATORY = "exploratory"
        FOCUSED = "focused"
        OPTIMIZATION = "optimization"
        VALIDATION = "validation"
    
    class ResearchPhase(str, Enum):
        IDLE = "idle"
        HYPOTHESIS_GENERATION = "hypothesis_generation"
        EXPERIMENT_DESIGN = "experiment_design"
        EXPERIMENT_EXECUTION = "experiment_execution"
        RESULTS_ANALYSIS = "results_analysis"
        KNOWLEDGE_INTEGRATION = "knowledge_integration"
        STRATEGY_OPTIMIZATION = "strategy_optimization"
        SESSION_COMPLETION = "session_completion"


class ResearchContext:
    """Shared context object passed between components"""
    
    def __init__(
        self,
        session_id: UUID,
        cycle_id: UUID,
        agent_id: str,
        current_phase: ResearchPhase,
        strategy: ResearchStrategy,
        progress: Dict[str, Any],
        config: Dict[str, Any]
    ):
        self.session_id = session_id
        self.cycle_id = cycle_id 
        self.agent_id = agent_id
        self.current_phase = current_phase
        self.strategy = strategy
        self.progress = progress
        self.config = config
        
        # Component-specific context
        self.hypotheses: List[Dict[str, Any]] = []
        self.experiments: List[UUID] = []
        self.results: List[Dict[str, Any]] = []
        self.insights: List[str] = []
        self.knowledge_cache: Dict[str, Any] = {}


class Hypothesis:
    """Structured hypothesis object"""
    
    def __init__(
        self,
        hypothesis_id: UUID,
        content: str,
        confidence: float,
        experiment_type: str,
        expected_outcome: str,
        rationale: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.hypothesis_id = hypothesis_id
        self.content = content
        self.confidence = confidence
        self.experiment_type = experiment_type
        self.expected_outcome = expected_outcome
        self.rationale = rationale
        self.parameters = parameters
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()


class ExperimentConfig:
    """Structured experiment configuration"""
    
    def __init__(
        self,
        experiment_id: UUID,
        hypothesis_id: UUID,
        experiment_type: str,
        parameters: Dict[str, Any],
        timeout_hours: int = 4,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.experiment_id = experiment_id
        self.hypothesis_id = hypothesis_id
        self.experiment_type = experiment_type
        self.parameters = parameters
        self.timeout_hours = timeout_hours
        self.priority = priority
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()


class ExperimentResult:
    """Structured experiment result"""
    
    def __init__(
        self,
        experiment_id: UUID,
        status: str,
        fitness_score: float,
        metrics: Dict[str, Any],
        artifacts: Dict[str, Any],
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.experiment_id = experiment_id
        self.status = status
        self.fitness_score = fitness_score
        self.metrics = metrics
        self.artifacts = artifacts
        self.error_message = error_message
        self.metadata = metadata or {}
        self.completed_at = datetime.utcnow()


class AnalysisReport:
    """Structured analysis report"""
    
    def __init__(
        self,
        experiment_id: UUID,
        fitness_score: float,
        risk_profile: str,
        performance_metrics: Dict[str, Any],
        insights: List[str],
        recommendations: List[str],
        quality_indicators: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.experiment_id = experiment_id
        self.fitness_score = fitness_score
        self.risk_profile = risk_profile
        self.performance_metrics = performance_metrics
        self.insights = insights
        self.recommendations = recommendations
        self.quality_indicators = quality_indicators
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()


class HypothesisGeneratorInterface(ABC):
    """Interface for hypothesis generation component"""
    
    @abstractmethod
    async def generate_hypotheses(
        self, 
        context: ResearchContext,
        count: int = 5
    ) -> List[Hypothesis]:
        """Generate multiple hypotheses based on research context"""
        pass
    
    @abstractmethod 
    async def refine_hypothesis(
        self,
        hypothesis: Hypothesis,
        feedback: Dict[str, Any]
    ) -> Hypothesis:
        """Refine a hypothesis based on feedback"""
        pass
    
    @abstractmethod
    async def validate_hypothesis(
        self,
        hypothesis: Hypothesis
    ) -> Tuple[bool, str]:
        """Validate hypothesis feasibility and quality"""
        pass


class ExperimentExecutorInterface(ABC):
    """Interface for experiment execution component"""
    
    @abstractmethod
    async def execute_experiment(
        self,
        config: ExperimentConfig,
        context: ResearchContext
    ) -> ExperimentResult:
        """Execute a single experiment"""
        pass
    
    @abstractmethod
    async def monitor_experiments(
        self,
        experiment_ids: List[UUID],
        context: ResearchContext
    ) -> Dict[UUID, Dict[str, Any]]:
        """Monitor multiple running experiments"""
        pass
    
    @abstractmethod
    async def cancel_experiment(
        self,
        experiment_id: UUID
    ) -> bool:
        """Cancel a running experiment"""
        pass


class ResultsAnalyzerInterface(ABC):
    """Interface for results analysis component"""
    
    @abstractmethod
    async def analyze_results(
        self,
        result: ExperimentResult,
        context: ResearchContext
    ) -> AnalysisReport:
        """Analyze experiment results and generate insights"""
        pass
    
    @abstractmethod
    async def calculate_fitness_score(
        self,
        metrics: Dict[str, Any]
    ) -> float:
        """Calculate fitness score from performance metrics"""
        pass
    
    @abstractmethod
    async def compare_results(
        self,
        results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """Compare multiple experiment results"""
        pass


class KnowledgeIntegratorInterface(ABC):
    """Interface for knowledge integration component"""
    
    @abstractmethod
    async def integrate_insights(
        self,
        insights: List[str],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Integrate new insights into knowledge base"""
        pass
    
    @abstractmethod
    async def search_knowledge(
        self,
        query: str,
        context: ResearchContext
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information"""
        pass
    
    @abstractmethod
    async def get_patterns(
        self,
        context: ResearchContext
    ) -> List[Dict[str, Any]]:
        """Get successful patterns from knowledge base"""
        pass


class StrategyOptimizerInterface(ABC):
    """Interface for strategy optimization component"""
    
    @abstractmethod
    async def optimize_parameters(
        self,
        performance: Dict[str, Any],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Optimize research parameters based on performance"""
        pass
    
    @abstractmethod
    async def adapt_strategy(
        self,
        feedback: Dict[str, Any],
        context: ResearchContext  
    ) -> ResearchStrategy:
        """Adapt research strategy based on feedback"""
        pass
    
    @abstractmethod
    async def recommend_next_action(
        self,
        context: ResearchContext
    ) -> Tuple[str, Dict[str, Any]]:
        """Recommend next research action"""
        pass