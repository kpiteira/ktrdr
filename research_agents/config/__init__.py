"""
Research Agents Configuration System

Centralized configuration management for the research agents system.
Eliminates magic numbers and provides a single source of truth for
all configurable parameters.

Components:
- base: Base configuration classes and utilities
- research: Research agent specific configurations
- components: Component-specific configurations
- defaults: Default configuration values
"""

from .base import ConfigurationManager, BaseConfig
from .research import (
    ResearchAgentConfig,
    ResearchOrchestratorConfig,
    ResearchCycleConfig,
    ResearchSessionConfig,
)
from .components import (
    HypothesisGeneratorConfig,
    ExperimentExecutorConfig,
    ResultsAnalyzerConfig,
    KnowledgeIntegratorConfig,
    StrategyOptimizerConfig,
)
from .defaults import DEFAULT_CONFIGS

__all__ = [
    # Base configuration
    "ConfigurationManager",
    "BaseConfig",
    
    # Research configurations
    "ResearchAgentConfig",
    "ResearchOrchestratorConfig", 
    "ResearchCycleConfig",
    "ResearchSessionConfig",
    
    # Component configurations
    "HypothesisGeneratorConfig",
    "ExperimentExecutorConfig",
    "ResultsAnalyzerConfig",
    "KnowledgeIntegratorConfig",
    "StrategyOptimizerConfig",
    
    # Defaults
    "DEFAULT_CONFIGS",
]