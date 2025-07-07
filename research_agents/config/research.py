"""
Research agent specific configurations.

Defines configuration classes for research agents, orchestrators,
and research cycle management with proper validation.
"""

from dataclasses import dataclass
from typing import List, Dict, Any

from .base import BaseConfig


@dataclass
class ResearchCycleConfig(BaseConfig):
    """Configuration for research cycle execution"""
    
    # Timing configuration (seconds unless specified)
    heartbeat_interval_seconds: int = 30
    cycle_check_interval_seconds: int = 60
    error_retry_delay_seconds: int = 60
    cycle_timeout_hours: int = 4
    session_timeout_hours: int = 24
    
    # Performance thresholds
    fitness_threshold: float = 0.6
    exploration_ratio: float = 0.3
    quality_score_threshold: float = 0.8
    confidence_threshold: float = 0.6
    
    # Operational limits
    max_errors: int = 3
    max_concurrent_experiments: int = 2
    hypothesis_batch_size: int = 5
    max_cycles_per_session: int = 10
    
    # External service timeouts (seconds)
    llm_timeout_seconds: int = 30
    ktrdr_timeout_seconds: int = 300
    database_timeout_seconds: int = 10
    
    def _validate(self) -> None:
        """Validate research cycle configuration"""
        if self.fitness_threshold < 0.0 or self.fitness_threshold > 1.0:
            raise ValueError("fitness_threshold must be between 0.0 and 1.0")
        
        if self.exploration_ratio < 0.0 or self.exploration_ratio > 1.0:
            raise ValueError("exploration_ratio must be between 0.0 and 1.0")
        
        if self.max_concurrent_experiments < 1:
            raise ValueError("max_concurrent_experiments must be at least 1")
        
        if self.hypothesis_batch_size < 1:
            raise ValueError("hypothesis_batch_size must be at least 1")
        
        if self.cycle_timeout_hours < 1:
            raise ValueError("cycle_timeout_hours must be at least 1")


@dataclass
class ResearchAgentConfig(BaseConfig):
    """Configuration for base research agents"""
    
    # Agent identification
    agent_type: str = "research_agent"
    
    # Database configuration
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "research_agents"
    database_timeout_seconds: int = 10
    
    # Memory management
    memory_limit_entries: int = 50
    memory_cleanup_interval_seconds: int = 300
    
    # State persistence
    state_save_interval_seconds: int = 120
    state_backup_enabled: bool = True
    
    # Error handling
    max_consecutive_errors: int = 3
    error_backoff_multiplier: float = 2.0
    max_error_backoff_seconds: int = 300
    
    def _validate(self) -> None:
        """Validate research agent configuration"""
        if self.database_port < 1 or self.database_port > 65535:
            raise ValueError("database_port must be between 1 and 65535")
        
        if self.memory_limit_entries < 10:
            raise ValueError("memory_limit_entries must be at least 10")
        
        if self.error_backoff_multiplier < 1.0:
            raise ValueError("error_backoff_multiplier must be at least 1.0")


@dataclass
class ResearchOrchestratorConfig(BaseConfig):
    """Configuration for the research orchestrator"""
    
    # Component timeouts (seconds)
    hypothesis_generation_timeout: int = 60
    experiment_design_timeout: int = 30
    experiment_execution_timeout: int = 14400  # 4 hours
    results_analysis_timeout: int = 300  # 5 minutes
    knowledge_integration_timeout: int = 120  # 2 minutes
    strategy_optimization_timeout: int = 60
    
    # Phase retry configuration
    max_phase_retries: int = 2
    phase_retry_delay_seconds: int = 30
    
    # Session management
    max_sessions_per_agent: int = 5
    session_cleanup_interval_hours: int = 24
    
    # Performance monitoring
    performance_window_cycles: int = 10
    performance_degradation_threshold: float = 0.2
    strategy_adaptation_threshold: int = 5  # cycles
    
    # Resource management
    max_memory_usage_mb: int = 2048
    cleanup_threshold_mb: int = 1536
    
    def _validate(self) -> None:
        """Validate orchestrator configuration"""
        if self.experiment_execution_timeout < 600:  # Minimum 10 minutes
            raise ValueError("experiment_execution_timeout must be at least 600 seconds")
        
        if self.max_phase_retries < 0:
            raise ValueError("max_phase_retries must be non-negative")
        
        if self.performance_window_cycles < 3:
            raise ValueError("performance_window_cycles must be at least 3")


@dataclass 
class ResearchSessionConfig(BaseConfig):
    """Configuration for research sessions"""
    
    # Session lifecycle
    session_timeout_hours: int = 24
    idle_timeout_hours: int = 2
    max_cycles_per_session: int = 50
    
    # Research strategy adaptation
    strategy_evaluation_window: int = 5  # cycles
    min_cycles_before_adaptation: int = 3
    strategy_performance_threshold: float = 0.4
    
    # Knowledge management
    knowledge_retention_days: int = 30
    knowledge_quality_threshold: float = 0.5
    max_knowledge_entries_per_cycle: int = 20
    
    # Experiment batching
    max_concurrent_experiments: int = 3
    experiment_batch_delay_seconds: int = 5
    
    def _validate(self) -> None:
        """Validate session configuration"""
        if self.session_timeout_hours < 1:
            raise ValueError("session_timeout_hours must be at least 1")
        
        if self.max_cycles_per_session < 5:
            raise ValueError("max_cycles_per_session must be at least 5")
        
        if self.strategy_evaluation_window < 3:
            raise ValueError("strategy_evaluation_window must be at least 3")