"""
Hypothesis Generator Component

Handles all aspects of hypothesis generation for the research agent system.
Extracted from ResearchAgentMVP to follow Single Responsibility Principle.

Responsibilities:
- Generate novel and focused hypotheses using LLM services
- Validate hypothesis feasibility and quality
- Refine hypotheses based on feedback
- Manage exploration vs exploitation strategies
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime

from ktrdr import get_logger
from ktrdr.errors import ProcessingError

from .interfaces import (
    HypothesisGeneratorInterface,
    ResearchContext,
    Hypothesis,
)
from ..services.interfaces import LLMService

logger = get_logger(__name__)


class HypothesisGenerator(HypothesisGeneratorInterface):
    """
    Concrete implementation of hypothesis generation.
    
    Uses LLM services to generate creative, testable hypotheses for
    trading strategy research with exploration/exploitation balance.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        exploration_ratio: float = 0.3,
        min_confidence_threshold: float = 0.6,
        max_batch_size: int = 10
    ):
        self.llm_service = llm_service
        self.exploration_ratio = exploration_ratio
        self.min_confidence_threshold = min_confidence_threshold
        self.max_batch_size = max_batch_size
        
        logger.info(f"Hypothesis generator initialized with exploration_ratio={exploration_ratio}, min_confidence={min_confidence_threshold}")
    
    async def generate_hypotheses(
        self, 
        context: ResearchContext,
        count: int = 5
    ) -> List[Hypothesis]:
        """Generate multiple hypotheses based on research context"""
        
        if count > self.max_batch_size:
            count = self.max_batch_size
            logger.warning(f"Requested count {count} exceeds max_batch_size {self.max_batch_size}, using max")
        
        try:
            logger.info(f"Generating {count} hypotheses for session {context.session_id}, strategy: {context.strategy}")
            
            # Determine if we should explore or exploit
            should_explore = self._should_explore(context)
            
            if should_explore:
                hypotheses = await self._generate_exploratory_hypotheses(context, count)
                logger.info(f"Generated {len(hypotheses)} exploratory hypotheses")
            else:
                hypotheses = await self._generate_focused_hypotheses(context, count)
                logger.info(f"Generated {len(hypotheses)} focused hypotheses")
            
            # Validate and filter hypotheses
            validated_hypotheses = []
            for hypothesis in hypotheses:
                is_valid, reason = await self.validate_hypothesis(hypothesis)
                if is_valid:
                    validated_hypotheses.append(hypothesis)
                else:
                    logger.warning(f"Rejected hypothesis {hypothesis.hypothesis_id}: {reason}")
            
            logger.info(f"Generated {len(validated_hypotheses)} valid hypotheses out of {len(hypotheses)} total")
            return validated_hypotheses
            
        except Exception as e:
            logger.error(f"Failed to generate hypotheses: {e}")
            raise ProcessingError(
                "Hypothesis generation failed",
                error_code="HYPOTHESIS_GENERATION_FAILED",
                details={
                    "session_id": str(context.session_id),
                    "cycle_id": str(context.cycle_id),
                    "count": count,
                    "original_error": str(e)
                }
            ) from e
    
    async def _generate_exploratory_hypotheses(
        self,
        context: ResearchContext,
        count: int
    ) -> List[Hypothesis]:
        """Generate exploratory hypotheses for novel discovery"""
        
        # Build exploratory context
        llm_context = {
            "session_id": str(context.session_id),
            "strategy": context.strategy,
            "recent_insights": context.knowledge_cache.get("recent_insights", []),
            "exploration_focus": "novel_approaches",
            "count": count
        }
        
        # Generate using LLM service
        llm_hypotheses = await self.llm_service.generate_hypotheses(llm_context)
        
        # Convert to structured hypothesis objects
        hypotheses = []
        for i, llm_hyp in enumerate(llm_hypotheses):
            hypothesis = Hypothesis(
                hypothesis_id=uuid4(),
                content=llm_hyp.get("content", ""),
                confidence=llm_hyp.get("confidence", 0.5),
                experiment_type=llm_hyp.get("experiment_type", "backtesting"),
                expected_outcome=llm_hyp.get("expected_outcome", ""),
                rationale=llm_hyp.get("rationale", ""),
                parameters=llm_hyp.get("parameters", {}),
                metadata={
                    "generation_type": "exploratory",
                    "generation_index": i,
                    "session_id": str(context.session_id)
                }
            )
            hypotheses.append(hypothesis)
        
        return hypotheses
    
    async def _generate_focused_hypotheses(
        self,
        context: ResearchContext,
        count: int
    ) -> List[Hypothesis]:
        """Generate focused hypotheses based on successful patterns"""
        
        # Get successful patterns from context
        successful_patterns = context.knowledge_cache.get("successful_patterns", [])
        
        # Build focused context
        llm_context = {
            "session_id": str(context.session_id),
            "strategy": context.strategy,
            "successful_patterns": successful_patterns,
            "focus_area": "optimization",
            "count": count
        }
        
        # Generate using LLM service
        llm_hypotheses = await self.llm_service.generate_hypotheses(llm_context)
        
        # Convert to structured hypothesis objects
        hypotheses = []
        for i, llm_hyp in enumerate(llm_hypotheses):
            hypothesis = Hypothesis(
                hypothesis_id=uuid4(),
                content=llm_hyp.get("content", ""),
                confidence=llm_hyp.get("confidence", 0.7),  # Higher confidence for focused
                experiment_type=llm_hyp.get("experiment_type", "backtesting"),
                expected_outcome=llm_hyp.get("expected_outcome", ""),
                rationale=llm_hyp.get("rationale", ""),
                parameters=llm_hyp.get("parameters", {}),
                metadata={
                    "generation_type": "focused",
                    "generation_index": i,
                    "session_id": str(context.session_id),
                    "based_on_patterns": len(successful_patterns)
                }
            )
            hypotheses.append(hypothesis)
        
        return hypotheses
    
    async def refine_hypothesis(
        self,
        hypothesis: Hypothesis,
        feedback: Dict[str, Any]
    ) -> Hypothesis:
        """Refine a hypothesis based on feedback"""
        
        try:
            logger.info(f"Refining hypothesis {hypothesis.hypothesis_id}")
            
            # Build refinement context
            refinement_context = {
                "original_hypothesis": {
                    "content": hypothesis.content,
                    "confidence": hypothesis.confidence,
                    "rationale": hypothesis.rationale,
                    "parameters": hypothesis.parameters
                },
                "feedback": feedback,
                "refinement_goal": feedback.get("goal", "improve_feasibility")
            }
            
            # Use LLM to refine
            refined_data = await self.llm_service.generate_hypothesis(refinement_context)
            
            # Create refined hypothesis
            refined_hypothesis = Hypothesis(
                hypothesis_id=uuid4(),  # New ID for refined version
                content=refined_data.get("content", hypothesis.content),
                confidence=refined_data.get("confidence", hypothesis.confidence),
                experiment_type=refined_data.get("experiment_type", hypothesis.experiment_type),
                expected_outcome=refined_data.get("expected_outcome", hypothesis.expected_outcome),
                rationale=refined_data.get("rationale", hypothesis.rationale),
                parameters=refined_data.get("parameters", hypothesis.parameters),
                metadata={
                    "refinement_of": str(hypothesis.hypothesis_id),
                    "refinement_feedback": feedback,
                    "refinement_timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Successfully refined hypothesis {hypothesis.hypothesis_id} -> {refined_hypothesis.hypothesis_id}")
            return refined_hypothesis
            
        except Exception as e:
            logger.error(f"Failed to refine hypothesis {hypothesis.hypothesis_id}: {e}")
            raise ProcessingError(
                "Hypothesis refinement failed",
                error_code="HYPOTHESIS_REFINEMENT_FAILED",
                details={
                    "hypothesis_id": str(hypothesis.hypothesis_id),
                    "feedback": feedback,
                    "original_error": str(e)
                }
            ) from e
    
    async def validate_hypothesis(
        self,
        hypothesis: Hypothesis
    ) -> Tuple[bool, str]:
        """Validate hypothesis feasibility and quality"""
        
        # Basic validation checks
        if not hypothesis.content or len(hypothesis.content.strip()) < 10:
            return False, "Hypothesis content too short or empty"
        
        if hypothesis.confidence < self.min_confidence_threshold:
            return False, f"Confidence {hypothesis.confidence} below threshold {self.min_confidence_threshold}"
        
        if not hypothesis.experiment_type:
            return False, "Missing experiment type"
        
        if not hypothesis.expected_outcome:
            return False, "Missing expected outcome"
        
        # Validate parameters structure
        if not isinstance(hypothesis.parameters, dict):
            return False, "Parameters must be a dictionary"
        
        # Check for required parameter fields based on experiment type
        if hypothesis.experiment_type == "backtesting":
            required_params = ["symbol", "timeframe", "strategy_config"]
            missing_params = [p for p in required_params if p not in hypothesis.parameters]
            if missing_params:
                return False, f"Missing required backtesting parameters: {missing_params}"
        
        # Additional domain-specific validations can be added here
        
        return True, "Hypothesis validation passed"
    
    def _should_explore(self, context: ResearchContext) -> bool:
        """Determine if we should explore or exploit based on context"""
        
        # Base exploration decision on ratio
        import random
        base_explore = random.random() < self.exploration_ratio
        
        # Modify based on context
        progress = context.progress
        
        # Explore more if we have few cycles
        if progress.get("completed_cycles", 0) < 5:
            return True
        
        # Explore more if performance is poor
        avg_fitness = progress.get("avg_fitness_score", 0.5)
        if avg_fitness < 0.4:
            return True
        
        # Exploit more if we have good patterns
        if len(context.knowledge_cache.get("successful_patterns", [])) > 3:
            return not base_explore  # Invert to favor exploitation
        
        return base_explore