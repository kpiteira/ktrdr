"""
Strategy Optimizer Component

Handles all aspects of strategy optimization for the research agent system.
Extracted from ResearchAgentMVP to follow Single Responsibility Principle.

Responsibilities:
- Optimize research parameters based on performance feedback
- Adapt research strategies based on success patterns
- Recommend next research actions and directions
- Manage exploration vs exploitation balance
"""

from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import statistics
from datetime import datetime, timezone

from ktrdr import get_logger
from ktrdr.errors import ProcessingError

from .interfaces import (
    StrategyOptimizerInterface,
    ResearchContext,
)
from ..types import ResearchStrategy

logger = get_logger(__name__)


class OptimizationTarget(str, Enum):
    """Optimization targets for strategy adaptation"""
    FITNESS_SCORE = "fitness_score"
    SUCCESS_RATE = "success_rate"
    EFFICIENCY = "efficiency"
    EXPLORATION_BALANCE = "exploration_balance"


class StrategyOptimizer(StrategyOptimizerInterface):
    """
    Concrete implementation of strategy optimization.
    
    Adapts research strategies and parameters based on performance
    feedback to improve overall research effectiveness.
    """
    
    def __init__(
        self,
        fitness_threshold: float = 0.6,
        min_cycles_for_adaptation: int = 3,
        performance_history_limit: int = 10,
        exploration_decay_rate: float = 0.95
    ):
        self.fitness_threshold = fitness_threshold
        self.min_cycles_for_adaptation = min_cycles_for_adaptation
        self.performance_history_limit = performance_history_limit
        self.exploration_decay_rate = exploration_decay_rate
        
        # Strategy performance tracking
        self.strategy_performance: Dict[str, List[float]] = {}
        self.parameter_performance: Dict[str, Dict[str, float]] = {}
        
        # Adaptation history for learning
        self.adaptation_history: List[Dict[str, Any]] = []
        
        logger.info(f"Strategy optimizer initialized with fitness_threshold={fitness_threshold}, min_cycles={min_cycles_for_adaptation}")
    
    async def optimize_parameters(
        self,
        performance: Dict[str, Any],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Optimize research parameters based on performance"""
        
        try:
            logger.info(f"Optimizing parameters for session {context.session_id}, current strategy: {context.strategy}")
            
            # Extract performance metrics
            cycle_fitness = performance.get("cycle_fitness", 0.0)
            success_rate = performance.get("success_rate", 0.0)
            experiment_count = performance.get("experiment_count", 0)
            
            # Track performance for current strategy
            strategy_key = str(context.strategy)
            if strategy_key not in self.strategy_performance:
                self.strategy_performance[strategy_key] = []
            
            # Add current performance and maintain history limit
            perf_history = self.strategy_performance[strategy_key]
            perf_history.append(cycle_fitness)
            if len(perf_history) > self.performance_history_limit:
                perf_history.pop(0)
            
            # Calculate optimization recommendations
            optimizations: Dict[str, Any] = {
                "parameter_adjustments": {},
                "confidence": 0.0,
                "reasoning": [],
                "target_metrics": {}
            }
            
            # Only optimize if we have enough data
            if len(perf_history) >= self.min_cycles_for_adaptation:
                optimizations = await self._calculate_parameter_optimizations(
                    performance, context, perf_history
                )
            else:
                optimizations["reasoning"].append(
                    f"Insufficient data for optimization (need {self.min_cycles_for_adaptation}, have {len(perf_history)})"
                )
            
            # Add general recommendations
            optimizations.update(
                await self._generate_general_recommendations(performance, context)
            )
            
            logger.info(f"Parameter optimization completed with {len(optimizations['parameter_adjustments'])} adjustments")
            return optimizations
            
        except Exception as e:
            logger.error(f"Failed to optimize parameters: {e}")
            raise ProcessingError(
                "Parameter optimization failed",
                error_code="PARAMETER_OPTIMIZATION_FAILED",
                details={
                    "session_id": str(context.session_id),
                    "strategy": context.strategy,
                    "original_error": str(e)
                }
            ) from e
    
    async def adapt_strategy(
        self,
        feedback: Dict[str, Any],
        context: ResearchContext
    ) -> ResearchStrategy:
        """Adapt research strategy based on feedback"""
        
        try:
            logger.info(f"Adapting strategy based on feedback for session {context.session_id}")
            
            current_strategy = context.strategy
            
            # Analyze strategy performance
            strategy_analysis = self._analyze_strategy_performance(current_strategy)
            
            # Determine if strategy change is needed
            should_change_strategy = self._should_change_strategy(
                strategy_analysis, feedback, context
            )
            
            if should_change_strategy:
                new_strategy = self._select_optimal_strategy(strategy_analysis, context)
                
                # Record adaptation
                adaptation_record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": str(context.session_id),
                    "cycle_id": str(context.cycle_id),
                    "old_strategy": current_strategy,
                    "new_strategy": new_strategy,
                    "reason": strategy_analysis.get("change_reason", "performance_optimization"),
                    "feedback": feedback
                }
                self.adaptation_history.append(adaptation_record)
                
                logger.info(f"Strategy adapted from {current_strategy} to {new_strategy}")
                return new_strategy
            else:
                logger.info(f"Keeping current strategy: {current_strategy}")
                return current_strategy
            
        except Exception as e:
            logger.error(f"Failed to adapt strategy: {e}")
            # Return current strategy on error
            return context.strategy
    
    async def recommend_next_action(
        self,
        context: ResearchContext
    ) -> Tuple[str, Dict[str, Any]]:
        """Recommend next research action"""
        
        try:
            logger.info(f"Generating next action recommendation for session {context.session_id}")
            
            # Analyze current context
            progress = context.progress
            completed_cycles = progress.get("completed_cycles", 0)
            avg_fitness = progress.get("avg_fitness_score", 0.0)
            recent_failures = progress.get("failed_experiments", 0)
            
            # Determine recommendation based on context
            if completed_cycles == 0:
                # First cycle - start with exploration
                action = "start_exploration"
                params = {
                    "strategy": ResearchStrategy.EXPLORATORY,
                    "hypothesis_count": 3,
                    "exploration_ratio": 0.8,
                    "reasoning": "First research cycle - starting with broad exploration"
                }
            
            elif avg_fitness < 0.3:
                # Poor performance - increase exploration
                action = "increase_exploration"
                params = {
                    "strategy": ResearchStrategy.EXPLORATORY,
                    "hypothesis_count": 5,
                    "exploration_ratio": 0.9,
                    "reasoning": "Low performance detected - increasing exploration to find better approaches"
                }
            
            elif avg_fitness > 0.7:
                # Good performance - focus on optimization
                action = "optimize_successful_patterns"
                params = {
                    "strategy": ResearchStrategy.OPTIMIZATION,
                    "hypothesis_count": 3,
                    "exploration_ratio": 0.2,
                    "reasoning": "High performance detected - focusing on optimization of successful patterns"
                }
            
            elif recent_failures > 5:
                # Too many failures - validation mode
                action = "validate_approach"
                params = {
                    "strategy": ResearchStrategy.VALIDATION,
                    "hypothesis_count": 2,
                    "exploration_ratio": 0.3,
                    "reasoning": "High failure rate - switching to validation mode to verify approach"
                }
            
            else:
                # Balanced approach
                action = "balanced_research"
                params = {
                    "strategy": ResearchStrategy.FOCUSED,
                    "hypothesis_count": 4,
                    "exploration_ratio": 0.5,
                    "reasoning": "Balanced performance - maintaining focused research approach"
                }
            
            # Add contextual adjustments
            params.update(self._adjust_for_context(params, context))
            
            logger.info(f"Recommended action: {action} with strategy {params.get('strategy')}")
            return action, params
            
        except Exception as e:
            logger.error(f"Failed to recommend next action: {e}")
            # Return safe default
            return "balanced_research", {
                "strategy": ResearchStrategy.FOCUSED,
                "hypothesis_count": 3,
                "exploration_ratio": 0.5,
                "reasoning": "Error in recommendation system - using safe default"
            }
    
    async def _calculate_parameter_optimizations(
        self,
        performance: Dict[str, Any],
        context: ResearchContext,
        perf_history: List[float]
    ) -> Dict[str, Any]:
        """Calculate specific parameter optimizations"""
        
        optimizations: Dict[str, Any] = {
            "parameter_adjustments": {},
            "confidence": 0.0,
            "reasoning": [],
            "target_metrics": {}
        }
        
        # Analyze performance trend
        if len(perf_history) >= 3:
            recent_avg = statistics.mean(perf_history[-3:])
            overall_avg = statistics.mean(perf_history)
            
            trend = "improving" if recent_avg > overall_avg else "declining"
            
            if trend == "declining":
                # Performance is declining - suggest parameter adjustments
                optimizations["parameter_adjustments"]["exploration_ratio"] = min(
                    context.config.get("exploration_ratio", 0.3) + 0.1, 0.8
                )
                optimizations["reasoning"].append(
                    "Performance declining - increasing exploration ratio"
                )
            
            elif trend == "improving" and recent_avg > self.fitness_threshold:
                # Performance improving and good - focus more on exploitation
                optimizations["parameter_adjustments"]["exploration_ratio"] = max(
                    context.config.get("exploration_ratio", 0.3) - 0.1, 0.1
                )
                optimizations["reasoning"].append(
                    "Performance improving - reducing exploration to exploit successful patterns"
                )
        
        # Adjust hypothesis count based on success rate
        success_rate = performance.get("success_rate", 0.0)
        current_hypothesis_count = context.config.get("hypothesis_batch_size", 5)
        
        if success_rate < 0.3:
            # Low success rate - try more hypotheses
            new_count = min(current_hypothesis_count + 1, 8)
            optimizations["parameter_adjustments"]["hypothesis_batch_size"] = new_count
            optimizations["reasoning"].append(
                f"Low success rate ({success_rate:.2f}) - increasing hypothesis count"
            )
        
        elif success_rate > 0.8:
            # High success rate - can reduce hypothesis count for efficiency
            new_count = max(current_hypothesis_count - 1, 2)
            optimizations["parameter_adjustments"]["hypothesis_batch_size"] = new_count
            optimizations["reasoning"].append(
                f"High success rate ({success_rate:.2f}) - reducing hypothesis count for efficiency"
            )
        
        # Calculate confidence based on data quality
        data_quality = min(len(perf_history) / self.performance_history_limit, 1.0)
        performance_stability = 1.0 - (statistics.stdev(perf_history) if len(perf_history) > 1 else 0.5)
        optimizations["confidence"] = (data_quality + performance_stability) / 2.0
        
        return optimizations
    
    def _analyze_strategy_performance(self, strategy: str) -> Dict[str, Any]:
        """Analyze performance of a specific strategy"""
        
        analysis = {
            "strategy": strategy,
            "sample_size": 0,
            "average_performance": 0.0,
            "performance_stability": 0.0,
            "trend": "unknown",
            "change_reason": None
        }
        
        if strategy in self.strategy_performance:
            performance_data = self.strategy_performance[strategy]
            analysis["sample_size"] = len(performance_data)
            
            if performance_data:
                analysis["average_performance"] = statistics.mean(performance_data)
                
                if len(performance_data) > 1:
                    analysis["performance_stability"] = 1.0 - statistics.stdev(performance_data)
                    
                    # Determine trend
                    if len(performance_data) >= 3:
                        recent = statistics.mean(performance_data[-2:])
                        earlier = statistics.mean(performance_data[:-2])
                        
                        if recent > earlier * 1.1:
                            analysis["trend"] = "improving"
                        elif recent < earlier * 0.9:
                            analysis["trend"] = "declining"
                            analysis["change_reason"] = "performance_decline"
                        else:
                            analysis["trend"] = "stable"
        
        return analysis
    
    def _should_change_strategy(
        self,
        strategy_analysis: Dict[str, Any],
        feedback: Dict[str, Any],
        context: ResearchContext
    ) -> bool:
        """Determine if strategy should be changed"""
        
        # Don't change if insufficient data
        if strategy_analysis["sample_size"] < self.min_cycles_for_adaptation:
            return False
        
        # Change if performance is consistently poor
        if (strategy_analysis["average_performance"] < 0.3 and 
            strategy_analysis["sample_size"] >= 5):
            return True
        
        # Change if performance is declining
        if strategy_analysis["trend"] == "declining":
            return True
        
        # Change if explicitly requested in feedback
        if feedback.get("force_strategy_change", False):
            return True
        
        # Change if stuck in same strategy for too long without improvement
        if (strategy_analysis["sample_size"] > 8 and 
            strategy_analysis["average_performance"] < 0.5):
            return True
        
        return False
    
    def _select_optimal_strategy(
        self,
        current_analysis: Dict[str, Any],
        context: ResearchContext
    ) -> ResearchStrategy:
        """Select the optimal strategy based on performance analysis"""
        
        # Analyze all strategies
        strategy_scores = {}
        
        for strategy_name in [s.value for s in ResearchStrategy]:
            if strategy_name in self.strategy_performance:
                data = self.strategy_performance[strategy_name]
                if data:
                    avg_performance = statistics.mean(data)
                    recency_bonus = 0.1 if len(data) >= 3 else 0.0
                    strategy_scores[strategy_name] = avg_performance + recency_bonus
                else:
                    strategy_scores[strategy_name] = 0.0
            else:
                # Untracked strategies get neutral score
                strategy_scores[strategy_name] = 0.5
        
        # Don't select the same strategy that's performing poorly
        current_strategy = current_analysis["strategy"]
        if current_analysis["average_performance"] < 0.3:
            strategy_scores[current_strategy] = 0.0
        
        # Select best performing strategy
        best_strategy = max(strategy_scores.items(), key=lambda x: x[1])[0]
        
        # Convert string back to enum
        return ResearchStrategy(best_strategy)
    
    async def _generate_general_recommendations(
        self,
        performance: Dict[str, Any],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Generate general optimization recommendations"""
        
        recommendations: Dict[str, Any] = {
            "general_recommendations": [],
            "risk_adjustments": {},
            "efficiency_improvements": {}
        }
        
        # Analyze efficiency
        experiment_count = performance.get("experiment_count", 0)
        if experiment_count > 0:
            efficiency = performance.get("cycle_fitness", 0.0) / experiment_count
            
            if efficiency < 0.1:
                recommendations["general_recommendations"].append(
                    "Consider reducing experiment count or improving hypothesis quality"
                )
                recommendations["efficiency_improvements"]["max_experiments"] = min(
                    experiment_count - 1, 2
                )
        
        # Risk management recommendations
        success_rate = performance.get("success_rate", 0.0)
        if success_rate < 0.2:
            recommendations["general_recommendations"].append(
                "High failure rate detected - consider more conservative parameters"
            )
            recommendations["risk_adjustments"]["timeout_buffer"] = 1.5
        
        return recommendations
    
    def _adjust_for_context(
        self,
        params: Dict[str, Any],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Adjust parameters based on research context"""
        
        adjustments = {}
        
        # Adjust based on progress
        completed_cycles = context.progress.get("completed_cycles", 0)
        
        # Early in research session - be more exploratory
        if completed_cycles < 3:
            adjustments["exploration_ratio"] = min(params.get("exploration_ratio", 0.5) + 0.2, 0.8)
        
        # Late in session - be more focused
        elif completed_cycles > 10:
            adjustments["exploration_ratio"] = max(params.get("exploration_ratio", 0.5) - 0.1, 0.2)
        
        # Adjust for available knowledge
        knowledge_size = context.progress.get("knowledge_base_size", 0)
        if knowledge_size < 10:
            # Limited knowledge - explore more
            adjustments["exploration_ratio"] = min(params.get("exploration_ratio", 0.5) + 0.1, 0.7)
        
        return adjustments