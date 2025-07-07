"""
Results Analyzer Component

Handles all aspects of results analysis for the research agent system.
Extracted from ResearchAgentMVP to follow Single Responsibility Principle.

This is a component wrapper around the existing ResultsAnalyzer service
to adapt it to the component interface and provide focused responsibilities.

Responsibilities:
- Analyze experiment results and generate insights
- Calculate fitness scores from performance metrics
- Compare and rank multiple experiment results
- Generate recommendations based on analysis
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from ktrdr import get_logger
from ktrdr.errors import ProcessingError

from .interfaces import (
    ResultsAnalyzerInterface,
    ResearchContext,
    ExperimentResult,
    AnalysisReport,
)
from ..services.results_analyzer import (
    ResultsAnalyzer as ResultsAnalyzerService,
    RiskProfile,
    PerformanceMetrics
)

logger = get_logger(__name__)


class ResultsAnalyzer(ResultsAnalyzerInterface):
    """
    Component wrapper for the results analysis service.
    
    Adapts the existing ResultsAnalyzerService to the component interface
    while providing focused responsibilities for the research agent system.
    """
    
    def __init__(
        self,
        results_analyzer_service: Optional[ResultsAnalyzerService] = None,
        **analyzer_config
    ):
        # Use provided service or create a new one with config
        if results_analyzer_service:
            self.analyzer = results_analyzer_service
        else:
            self.analyzer = ResultsAnalyzerService(**analyzer_config)
        
        logger.info("Results analyzer component initialized")
    
    async def analyze_results(
        self,
        result: ExperimentResult,
        context: ResearchContext
    ) -> AnalysisReport:
        """Analyze experiment results and generate insights"""
        
        try:
            logger.info(f"Analyzing results for experiment {result.experiment_id}")
            
            # If experiment failed, create minimal analysis
            if result.status != "completed":
                return self._create_failure_analysis(result, context)
            
            # Convert ExperimentResult to format expected by analyzer service
            training_results = {
                "job_id": str(result.experiment_id),
                "status": "completed",
                "metrics": result.metrics,
                "artifacts": result.artifacts
            }
            
            backtesting_results = result.artifacts.get("backtesting_results", {})
            
            # Use the analyzer service for comprehensive analysis
            analysis_result = await self.analyzer.analyze_experiment_results(
                experiment_id=result.experiment_id,
                training_results=training_results,
                backtesting_results=backtesting_results,
                additional_data={
                    "session_id": str(context.session_id),
                    "cycle_id": str(context.cycle_id),
                    "strategy": context.strategy,
                    "phase": context.current_phase
                }
            )
            
            # Convert to component AnalysisReport format
            return AnalysisReport(
                experiment_id=result.experiment_id,
                fitness_score=analysis_result["fitness_score"],
                risk_profile=analysis_result["risk_profile"],
                performance_metrics=analysis_result["performance_metrics"],
                insights=analysis_result.get("insights", []),
                recommendations=analysis_result.get("recommendations", []),
                quality_indicators=analysis_result.get("quality_indicators", {}),
                metadata={
                    "analysis_timestamp": analysis_result.get("analysis_timestamp"),
                    "analyzer_version": "component_v1.0",
                    "context": {
                        "session_id": str(context.session_id),
                        "cycle_id": str(context.cycle_id),
                        "strategy": context.strategy
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze results for experiment {result.experiment_id}: {e}")
            raise ProcessingError(
                "Results analysis failed",
                error_code="RESULTS_ANALYSIS_FAILED",
                details={
                    "experiment_id": str(result.experiment_id),
                    "result_status": result.status,
                    "original_error": str(e)
                }
            ) from e
    
    async def calculate_fitness_score(
        self,
        metrics: Dict[str, Any]
    ) -> float:
        """Calculate fitness score from performance metrics"""
        
        try:
            # Convert metrics to PerformanceMetrics if needed
            if not isinstance(metrics, dict):
                logger.warning("Metrics is not a dictionary, returning 0.0")
                return 0.0
            
            # Use the analyzer service to calculate fitness
            # This may require calling a method that calculates fitness from metrics
            fitness_components = await self.analyzer._calculate_fitness_components(
                metrics, {}
            )
            
            return fitness_components.get("composite_score", 0.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate fitness score: {e}")
            return 0.0
    
    async def compare_results(
        self,
        results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """Compare multiple experiment results"""
        
        try:
            logger.info(f"Comparing {len(results)} experiment results")
            
            if not results:
                return {"comparison": "no_results", "rankings": []}
            
            # Calculate fitness scores for all results
            scored_results = []
            for result in results:
                if result.status == "completed":
                    fitness_score = await self.calculate_fitness_score(result.metrics)
                    scored_results.append({
                        "experiment_id": result.experiment_id,
                        "fitness_score": fitness_score,
                        "metrics": result.metrics,
                        "status": result.status
                    })
                else:
                    scored_results.append({
                        "experiment_id": result.experiment_id,
                        "fitness_score": 0.0,
                        "metrics": {},
                        "status": result.status,
                        "error": result.error_message
                    })
            
            # Sort by fitness score (descending)
            sorted_results = sorted(scored_results, key=lambda x: x["fitness_score"], reverse=True)
            
            # Generate comparison insights
            completed_results = [r for r in scored_results if r["status"] == "completed"]
            
            if completed_results:
                fitness_scores = [r["fitness_score"] for r in completed_results]
                
                comparison = {
                    "total_experiments": len(results),
                    "completed_experiments": len(completed_results),
                    "failed_experiments": len(results) - len(completed_results),
                    "best_fitness_score": max(fitness_scores),
                    "worst_fitness_score": min(fitness_scores),
                    "average_fitness_score": sum(fitness_scores) / len(fitness_scores),
                    "fitness_std_dev": float(__import__('statistics').stdev(fitness_scores)) if len(fitness_scores) > 1 else 0.0,
                    "rankings": sorted_results
                }
            else:
                comparison = {
                    "total_experiments": len(results),
                    "completed_experiments": 0,
                    "failed_experiments": len(results),
                    "message": "No completed experiments to compare",
                    "rankings": sorted_results
                }
            
            logger.info(f"Comparison completed: {comparison.get('completed_experiments', 0)}/{len(results)} successful")
            return comparison
            
        except Exception as e:
            logger.error(f"Failed to compare results: {e}")
            
            # Import numpy locally to avoid issues
            try:
                import numpy as np
            except ImportError:
                # Fallback if numpy not available
                np = None
            
            raise ProcessingError(
                "Results comparison failed", 
                error_code="RESULTS_COMPARISON_FAILED",
                details={
                    "result_count": len(results),
                    "original_error": str(e)
                }
            ) from e
    
    def _create_failure_analysis(
        self,
        result: ExperimentResult,
        context: ResearchContext
    ) -> AnalysisReport:
        """Create analysis report for failed experiments"""
        
        insights = [
            f"Experiment failed with status: {result.status}",
        ]
        
        if result.error_message:
            insights.append(f"Error: {result.error_message}")
        
        recommendations = [
            "Review experiment configuration for errors",
            "Check KTRDR service availability",
            "Consider adjusting timeout settings if applicable"
        ]
        
        # Classify failure type for better recommendations
        if result.error_message:
            error_lower = result.error_message.lower()
            
            if "timeout" in error_lower:
                recommendations.extend([
                    "Increase experiment timeout duration",
                    "Consider using simpler strategy configurations",
                    "Check if training data size is too large"
                ])
            elif "network" in error_lower or "connection" in error_lower:
                recommendations.extend([
                    "Verify KTRDR service connectivity",
                    "Check network configuration",
                    "Consider implementing retry mechanisms"
                ])
            elif "parameter" in error_lower or "config" in error_lower:
                recommendations.extend([
                    "Validate experiment parameters",
                    "Review hypothesis parameter generation",
                    "Check parameter ranges and constraints"
                ])
        
        return AnalysisReport(
            experiment_id=result.experiment_id,
            fitness_score=0.0,
            risk_profile="unknown",
            performance_metrics={},
            insights=insights,
            recommendations=recommendations,
            quality_indicators={
                "experiment_status": result.status,
                "has_error": bool(result.error_message),
                "analysis_type": "failure_analysis"
            },
            metadata={
                "failure_analysis": True,
                "original_status": result.status,
                "error_message": result.error_message,
                "context": {
                    "session_id": str(context.session_id),
                    "cycle_id": str(context.cycle_id),
                    "strategy": context.strategy
                }
            }
        )