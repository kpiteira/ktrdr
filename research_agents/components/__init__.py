"""
Research Agent Components

This package contains the focused, single-responsibility components that were
extracted from the monolithic ResearchAgentMVP god class to improve
maintainability, testability, and adherence to SOLID principles.

Components:
- interfaces: Abstract base classes defining component contracts
- hypothesis_generator: Handles LLM hypothesis generation
- experiment_executor: Executes and monitors experiments  
- results_analyzer: Analyzes results and calculates fitness
- knowledge_integrator: Handles knowledge base operations
- strategy_optimizer: Optimizes research strategies
"""

from .interfaces import (
    HypothesisGeneratorInterface,
    ExperimentExecutorInterface,
    ResultsAnalyzerInterface,
    KnowledgeIntegratorInterface,
    StrategyOptimizerInterface,
)

from .hypothesis_generator import HypothesisGenerator
from .experiment_executor import ExperimentExecutor
from .results_analyzer import ResultsAnalyzer  
from .knowledge_integrator import KnowledgeIntegrator
from .strategy_optimizer import StrategyOptimizer

__all__ = [
    # Interfaces
    "HypothesisGeneratorInterface",
    "ExperimentExecutorInterface", 
    "ResultsAnalyzerInterface",
    "KnowledgeIntegratorInterface",
    "StrategyOptimizerInterface",
    
    # Implementations
    "HypothesisGenerator",
    "ExperimentExecutor",
    "ResultsAnalyzer",
    "KnowledgeIntegrator", 
    "StrategyOptimizer",
]