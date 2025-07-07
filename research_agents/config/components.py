"""
Component-specific configurations.

Defines configuration classes for each research agent component
with their specific parameters and validation rules.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .base import BaseConfig


@dataclass
class HypothesisGeneratorConfig(BaseConfig):
    """Configuration for hypothesis generation component"""
    
    # Generation parameters
    exploration_ratio: float = 0.3
    exploitation_ratio: float = 0.7
    min_confidence_threshold: float = 0.6
    max_confidence_threshold: float = 0.95
    
    # Batch processing
    default_batch_size: int = 5
    max_batch_size: int = 20
    batch_timeout_seconds: int = 60
    
    # LLM interaction
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 3
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000
    
    # Hypothesis quality
    min_hypothesis_length: int = 50
    max_hypothesis_length: int = 500
    required_sections: Optional[List[str]] = None
    
    # Diversity and exploration
    novelty_threshold: float = 0.4
    diversity_weight: float = 0.3
    
    def __post_init__(self) -> None:
        if self.required_sections is None:
            self.required_sections = ["rationale", "expected_outcome", "parameters"]
        super().__post_init__()
    
    def _validate(self) -> None:
        """Validate hypothesis generator configuration"""
        if self.exploration_ratio < 0.0 or self.exploration_ratio > 1.0:
            raise ValueError("exploration_ratio must be between 0.0 and 1.0")
        
        if self.exploitation_ratio < 0.0 or self.exploitation_ratio > 1.0:
            raise ValueError("exploitation_ratio must be between 0.0 and 1.0")
        
        if abs((self.exploration_ratio + self.exploitation_ratio) - 1.0) > 0.01:
            raise ValueError("exploration_ratio + exploitation_ratio must equal 1.0")
        
        if self.min_confidence_threshold >= self.max_confidence_threshold:
            raise ValueError("min_confidence_threshold must be less than max_confidence_threshold")
        
        if self.default_batch_size > self.max_batch_size:
            raise ValueError("default_batch_size cannot exceed max_batch_size")


@dataclass
class ExperimentExecutorConfig(BaseConfig):
    """Configuration for experiment execution component"""
    
    # Concurrency control
    max_concurrent_experiments: int = 2
    semaphore_timeout_seconds: int = 300
    experiment_queue_size: int = 50
    
    # Timeout configuration
    default_timeout_hours: int = 4
    min_timeout_minutes: int = 10
    max_timeout_hours: int = 24
    
    # KTRDR service interaction
    ktrdr_connection_timeout_seconds: int = 30
    ktrdr_request_timeout_seconds: int = 300
    ktrdr_max_retries: int = 3
    ktrdr_retry_delay_seconds: int = 60
    
    # Progress monitoring
    progress_check_interval_seconds: int = 30
    heartbeat_interval_seconds: int = 60
    status_update_interval_seconds: int = 120
    
    # Resource management
    max_memory_usage_mb: int = 1024
    cleanup_interval_seconds: int = 300
    
    # Error handling
    max_consecutive_failures: int = 3
    failure_cooldown_seconds: int = 300
    
    def _validate(self) -> None:
        """Validate experiment executor configuration"""
        if self.max_concurrent_experiments < 1:
            raise ValueError("max_concurrent_experiments must be at least 1")
        
        if self.default_timeout_hours < (self.min_timeout_minutes / 60):
            raise ValueError(f"default_timeout_hours must be at least {self.min_timeout_minutes / 60} hours")
        
        if self.default_timeout_hours > self.max_timeout_hours:
            raise ValueError("default_timeout_hours cannot exceed max_timeout_hours")
        
        if self.ktrdr_max_retries < 0:
            raise ValueError("ktrdr_max_retries must be non-negative")


@dataclass
class ResultsAnalyzerConfig(BaseConfig):
    """Configuration for results analysis component"""
    
    # Analysis parameters
    fitness_calculation_method: str = "composite"
    risk_tolerance: float = 0.5
    performance_window_days: int = 30
    
    # Scoring thresholds
    min_fitness_score: float = 0.0
    max_fitness_score: float = 1.0
    fitness_precision: int = 4
    
    # Quality indicators
    min_data_points: int = 100
    confidence_interval: float = 0.95
    outlier_threshold_std: float = 3.0
    
    # Comparison settings
    statistical_significance_level: float = 0.05
    min_samples_for_comparison: int = 10
    comparison_metrics: Optional[List[str]] = None
    
    # Analysis service integration
    analyzer_timeout_seconds: int = 120
    cache_results: bool = True
    cache_ttl_seconds: int = 3600
    
    def __post_init__(self) -> None:
        if self.comparison_metrics is None:
            self.comparison_metrics = [
                "sharpe_ratio", 
                "total_return", 
                "max_drawdown", 
                "win_rate"
            ]
        super().__post_init__()
    
    def _validate(self) -> None:
        """Validate results analyzer configuration"""
        if self.fitness_calculation_method not in ["composite", "weighted", "percentile"]:
            raise ValueError("fitness_calculation_method must be one of: composite, weighted, percentile")
        
        if self.risk_tolerance < 0.0 or self.risk_tolerance > 1.0:
            raise ValueError("risk_tolerance must be between 0.0 and 1.0")
        
        if self.min_fitness_score >= self.max_fitness_score:
            raise ValueError("min_fitness_score must be less than max_fitness_score")
        
        if self.statistical_significance_level <= 0.0 or self.statistical_significance_level >= 1.0:
            raise ValueError("statistical_significance_level must be between 0.0 and 1.0")


@dataclass  
class KnowledgeIntegratorConfig(BaseConfig):
    """Configuration for knowledge integration component"""
    
    # Quality thresholds
    min_quality_threshold: float = 0.3
    max_quality_threshold: float = 1.0
    quality_decay_rate: float = 0.95
    
    # Knowledge base management
    max_entries_per_session: int = 100
    max_total_entries: int = 10000
    cleanup_threshold_entries: int = 8000
    retention_days: int = 30
    
    # Integration processing
    batch_size: int = 20
    processing_timeout_seconds: int = 60
    similarity_threshold: float = 0.8
    
    # Database interaction
    database_timeout_seconds: int = 10
    max_database_retries: int = 3
    connection_pool_size: int = 5
    
    # Pattern recognition
    pattern_detection_enabled: bool = True
    min_pattern_frequency: int = 3
    pattern_confidence_threshold: float = 0.7
    
    # Knowledge categorization
    auto_categorization: bool = True
    category_confidence_threshold: float = 0.6
    max_categories_per_entry: int = 5
    
    def _validate(self) -> None:
        """Validate knowledge integrator configuration"""
        if self.min_quality_threshold >= self.max_quality_threshold:
            raise ValueError("min_quality_threshold must be less than max_quality_threshold")
        
        if self.quality_decay_rate <= 0.0 or self.quality_decay_rate > 1.0:
            raise ValueError("quality_decay_rate must be between 0.0 and 1.0")
        
        if self.cleanup_threshold_entries >= self.max_total_entries:
            raise ValueError("cleanup_threshold_entries must be less than max_total_entries")
        
        if self.similarity_threshold < 0.0 or self.similarity_threshold > 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")


@dataclass
class StrategyOptimizerConfig(BaseConfig):
    """Configuration for strategy optimization component"""
    
    # Performance thresholds
    fitness_threshold: float = 0.6
    improvement_threshold: float = 0.05
    degradation_threshold: float = 0.1
    
    # Adaptation parameters
    min_cycles_for_adaptation: int = 3
    max_cycles_before_forced_adaptation: int = 10
    adaptation_sensitivity: float = 0.5
    
    # Parameter optimization
    parameter_adjustment_rate: float = 0.1
    max_parameter_change: float = 0.3
    convergence_tolerance: float = 0.01
    
    # Strategy switching
    strategy_evaluation_window: int = 5
    min_confidence_for_switch: float = 0.7
    switch_cooldown_cycles: int = 2
    
    # Optimization algorithms
    optimization_method: str = "adaptive_gradient"
    learning_rate: float = 0.01
    momentum: float = 0.9
    
    # Performance tracking
    performance_history_size: int = 50
    trend_analysis_window: int = 10
    volatility_penalty: float = 0.1
    
    def _validate(self) -> None:
        """Validate strategy optimizer configuration"""
        if self.fitness_threshold < 0.0 or self.fitness_threshold > 1.0:
            raise ValueError("fitness_threshold must be between 0.0 and 1.0")
        
        if self.min_cycles_for_adaptation < 1:
            raise ValueError("min_cycles_for_adaptation must be at least 1")
        
        if self.max_cycles_before_forced_adaptation <= self.min_cycles_for_adaptation:
            raise ValueError("max_cycles_before_forced_adaptation must be greater than min_cycles_for_adaptation")
        
        if self.optimization_method not in ["adaptive_gradient", "genetic", "simulated_annealing", "bayesian"]:
            raise ValueError("optimization_method must be one of: adaptive_gradient, genetic, simulated_annealing, bayesian")
        
        if self.learning_rate <= 0.0 or self.learning_rate > 1.0:
            raise ValueError("learning_rate must be between 0.0 and 1.0")