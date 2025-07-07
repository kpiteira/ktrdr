"""
Default configuration values and configuration presets.

Provides pre-configured settings for different environments and use cases.
"""

from typing import Dict, Any
from .research import (
    ResearchAgentConfig,
    ResearchOrchestratorConfig, 
    ResearchCycleConfig,
    ResearchSessionConfig
)
from .components import (
    HypothesisGeneratorConfig,
    ExperimentExecutorConfig,
    ResultsAnalyzerConfig,
    KnowledgeIntegratorConfig,
    StrategyOptimizerConfig
)


# Development environment configurations
DEVELOPMENT_CONFIG = {
    "research_cycle": ResearchCycleConfig(
        heartbeat_interval_seconds=15,  # Faster feedback in dev
        cycle_check_interval_seconds=30,
        error_retry_delay_seconds=30,
        cycle_timeout_hours=1,  # Shorter timeouts for testing
        session_timeout_hours=4,
        fitness_threshold=0.5,  # Lower threshold for testing
        max_concurrent_experiments=1,  # Safer for dev
        hypothesis_batch_size=3,  # Smaller batches
        llm_timeout_seconds=15,  # Shorter timeouts
        ktrdr_timeout_seconds=120,
        database_timeout_seconds=5
    ),
    
    "research_orchestrator": ResearchOrchestratorConfig(
        hypothesis_generation_timeout=30,
        experiment_design_timeout=15,
        experiment_execution_timeout=3600,  # 1 hour for dev
        results_analysis_timeout=120,
        knowledge_integration_timeout=60,
        strategy_optimization_timeout=30,
        max_phase_retries=1,  # Fewer retries in dev
        phase_retry_delay_seconds=15,
        max_sessions_per_agent=2,
        performance_window_cycles=3,  # Smaller window
        max_memory_usage_mb=512  # Lower memory usage
    ),
    
    "hypothesis_generator": HypothesisGeneratorConfig(
        exploration_ratio=0.5,  # More exploration in dev
        exploitation_ratio=0.5,  # Make sure they add up to 1.0
        min_confidence_threshold=0.4,  # Lower threshold
        default_batch_size=3,
        llm_timeout_seconds=15,
        llm_max_retries=2
    ),
    
    "experiment_executor": ExperimentExecutorConfig(
        max_concurrent_experiments=1,
        default_timeout_hours=1,
        ktrdr_connection_timeout_seconds=15,
        ktrdr_request_timeout_seconds=120,
        ktrdr_max_retries=2,
        progress_check_interval_seconds=15
    ),
    
    "results_analyzer": ResultsAnalyzerConfig(
        min_data_points=50,  # Lower requirement for dev
        analyzer_timeout_seconds=60,
        cache_ttl_seconds=1800  # Shorter cache for dev
    ),
    
    "knowledge_integrator": KnowledgeIntegratorConfig(
        min_quality_threshold=0.2,  # Lower threshold for dev
        max_entries_per_session=50,
        batch_size=10,
        database_timeout_seconds=5
    ),
    
    "strategy_optimizer": StrategyOptimizerConfig(
        fitness_threshold=0.5,  # Lower threshold for dev
        min_cycles_for_adaptation=2,  # Faster adaptation
        parameter_adjustment_rate=0.15,  # More aggressive changes
        performance_history_size=20  # Smaller history
    )
}


# Production environment configurations  
PRODUCTION_CONFIG = {
    "research_cycle": ResearchCycleConfig(
        heartbeat_interval_seconds=30,
        cycle_check_interval_seconds=60,
        error_retry_delay_seconds=60,
        cycle_timeout_hours=4,
        session_timeout_hours=24,
        fitness_threshold=0.6,
        max_concurrent_experiments=2,
        hypothesis_batch_size=5,
        llm_timeout_seconds=30,
        ktrdr_timeout_seconds=300,
        database_timeout_seconds=10
    ),
    
    "research_orchestrator": ResearchOrchestratorConfig(
        hypothesis_generation_timeout=60,
        experiment_design_timeout=30,
        experiment_execution_timeout=14400,  # 4 hours
        results_analysis_timeout=300,
        knowledge_integration_timeout=120,
        strategy_optimization_timeout=60,
        max_phase_retries=2,
        phase_retry_delay_seconds=30,
        max_sessions_per_agent=5,
        performance_window_cycles=10,
        max_memory_usage_mb=2048
    ),
    
    "hypothesis_generator": HypothesisGeneratorConfig(
        exploration_ratio=0.3,
        min_confidence_threshold=0.6,
        default_batch_size=5,
        llm_timeout_seconds=30,
        llm_max_retries=3
    ),
    
    "experiment_executor": ExperimentExecutorConfig(
        max_concurrent_experiments=2,
        default_timeout_hours=4,
        ktrdr_connection_timeout_seconds=30,
        ktrdr_request_timeout_seconds=300,
        ktrdr_max_retries=3,
        progress_check_interval_seconds=30
    ),
    
    "results_analyzer": ResultsAnalyzerConfig(
        min_data_points=100,
        analyzer_timeout_seconds=120,
        cache_ttl_seconds=3600
    ),
    
    "knowledge_integrator": KnowledgeIntegratorConfig(
        min_quality_threshold=0.3,
        max_entries_per_session=100,
        batch_size=20,
        database_timeout_seconds=10
    ),
    
    "strategy_optimizer": StrategyOptimizerConfig(
        fitness_threshold=0.6,
        min_cycles_for_adaptation=3,
        parameter_adjustment_rate=0.1,
        performance_history_size=50
    )
}


# High-performance environment configurations (for intensive research)
HIGH_PERFORMANCE_CONFIG = {
    "research_cycle": ResearchCycleConfig(
        heartbeat_interval_seconds=30,
        cycle_check_interval_seconds=60,
        error_retry_delay_seconds=60,
        cycle_timeout_hours=8,  # Longer timeouts for complex experiments
        session_timeout_hours=48,
        fitness_threshold=0.7,  # Higher threshold
        max_concurrent_experiments=4,  # More parallelism
        hypothesis_batch_size=10,  # Larger batches
        llm_timeout_seconds=60,  # Longer LLM timeouts
        ktrdr_timeout_seconds=600,  # Longer KTRDR timeouts
        database_timeout_seconds=20
    ),
    
    "research_orchestrator": ResearchOrchestratorConfig(
        hypothesis_generation_timeout=120,
        experiment_design_timeout=60,
        experiment_execution_timeout=28800,  # 8 hours
        results_analysis_timeout=600,  # 10 minutes
        knowledge_integration_timeout=300,  # 5 minutes
        strategy_optimization_timeout=120,
        max_phase_retries=3,
        phase_retry_delay_seconds=60,
        max_sessions_per_agent=10,
        performance_window_cycles=20,
        max_memory_usage_mb=4096  # Higher memory limit
    ),
    
    "hypothesis_generator": HypothesisGeneratorConfig(
        exploration_ratio=0.2,  # Less exploration, more exploitation
        exploitation_ratio=0.8,  # Make sure they add up to 1.0
        min_confidence_threshold=0.7,  # Higher confidence required
        default_batch_size=10,
        max_batch_size=50,
        llm_timeout_seconds=60,
        llm_max_retries=5
    ),
    
    "experiment_executor": ExperimentExecutorConfig(
        max_concurrent_experiments=4,
        default_timeout_hours=8,
        ktrdr_connection_timeout_seconds=60,
        ktrdr_request_timeout_seconds=600,
        ktrdr_max_retries=5,
        progress_check_interval_seconds=60,
        max_memory_usage_mb=2048
    ),
    
    "results_analyzer": ResultsAnalyzerConfig(
        min_data_points=200,  # Higher data requirements
        analyzer_timeout_seconds=300,  # Longer analysis time
        cache_ttl_seconds=7200,  # Longer cache
        performance_window_days=60  # Longer performance window
    ),
    
    "knowledge_integrator": KnowledgeIntegratorConfig(
        min_quality_threshold=0.4,  # Higher quality threshold
        max_entries_per_session=200,
        max_total_entries=50000,  # Much larger knowledge base
        batch_size=50,
        database_timeout_seconds=20,
        connection_pool_size=10
    ),
    
    "strategy_optimizer": StrategyOptimizerConfig(
        fitness_threshold=0.7,  # Higher threshold
        min_cycles_for_adaptation=5,  # More cycles before adaptation
        parameter_adjustment_rate=0.05,  # More conservative changes
        performance_history_size=100,  # Larger history
        strategy_evaluation_window=10
    )
}


# Conservative configuration (for stable, low-risk research)
CONSERVATIVE_CONFIG = {
    "research_cycle": ResearchCycleConfig(
        heartbeat_interval_seconds=60,  # Less frequent checks
        cycle_check_interval_seconds=120,
        error_retry_delay_seconds=120,
        cycle_timeout_hours=2,  # Shorter timeouts
        session_timeout_hours=12,
        fitness_threshold=0.8,  # High threshold
        max_concurrent_experiments=1,  # Conservative parallelism
        hypothesis_batch_size=3,  # Small batches
        max_errors=2,  # Lower error tolerance
        llm_timeout_seconds=20,
        ktrdr_timeout_seconds=180,
        database_timeout_seconds=8
    ),
    
    "research_orchestrator": ResearchOrchestratorConfig(
        hypothesis_generation_timeout=45,
        experiment_design_timeout=20,
        experiment_execution_timeout=7200,  # 2 hours
        results_analysis_timeout=180,
        knowledge_integration_timeout=90,
        strategy_optimization_timeout=45,
        max_phase_retries=1,  # Conservative retries
        phase_retry_delay_seconds=60,
        max_sessions_per_agent=3,
        performance_window_cycles=5,
        max_memory_usage_mb=1024
    ),
    
    "hypothesis_generator": HypothesisGeneratorConfig(
        exploration_ratio=0.1,  # Minimal exploration
        exploitation_ratio=0.9,  # These already add up to 1.0
        min_confidence_threshold=0.8,  # High confidence required
        default_batch_size=3,
        max_batch_size=10,
        llm_timeout_seconds=20,
        llm_max_retries=2
    ),
    
    "experiment_executor": ExperimentExecutorConfig(
        max_concurrent_experiments=1,
        default_timeout_hours=2,
        ktrdr_connection_timeout_seconds=20,
        ktrdr_request_timeout_seconds=180,
        ktrdr_max_retries=2,
        max_consecutive_failures=2  # Low failure tolerance
    ),
    
    "results_analyzer": ResultsAnalyzerConfig(
        min_data_points=150,  # Higher data requirements
        statistical_significance_level=0.01,  # Higher significance required
        analyzer_timeout_seconds=90,
        risk_tolerance=0.3  # Low risk tolerance
    ),
    
    "knowledge_integrator": KnowledgeIntegratorConfig(
        min_quality_threshold=0.5,  # Higher quality threshold
        max_entries_per_session=30,
        batch_size=10,
        similarity_threshold=0.9,  # High similarity threshold
        database_timeout_seconds=8
    ),
    
    "strategy_optimizer": StrategyOptimizerConfig(
        fitness_threshold=0.8,  # High threshold
        min_cycles_for_adaptation=5,  # Conservative adaptation
        max_cycles_before_forced_adaptation=20,
        parameter_adjustment_rate=0.05,  # Small adjustments
        min_confidence_for_switch=0.9  # High confidence for strategy changes
    )
}


# Default configurations mapping
DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "development": DEVELOPMENT_CONFIG,
    "production": PRODUCTION_CONFIG, 
    "high_performance": HIGH_PERFORMANCE_CONFIG,
    "conservative": CONSERVATIVE_CONFIG
}


def get_config_for_environment(environment: str = "production") -> Dict[str, Any]:
    """Get configuration for specified environment"""
    if environment not in DEFAULT_CONFIGS:
        raise ValueError(f"Unknown environment: {environment}. Available: {list(DEFAULT_CONFIGS.keys())}")
    
    return DEFAULT_CONFIGS[environment]


def create_custom_config(**overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Create custom configuration by overriding production defaults"""
    config = PRODUCTION_CONFIG.copy()
    
    for component, component_overrides in overrides.items():
        if component in config:
            # Update the dataclass with new values
            current_config = config[component]
            updated_config = current_config.update(**component_overrides)
            config[component] = updated_config
    
    return config