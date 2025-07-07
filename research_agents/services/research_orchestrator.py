"""
Core Research Service Architecture - Experiment Lifecycle Management

This module provides the central orchestration service for AI research experiments,
managing the complete lifecycle from hypothesis to results analysis.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field
from ktrdr import get_logger
from .database import ResearchDatabaseService

logger = get_logger(__name__)


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status states"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentType(str, Enum):
    """Types of research experiments"""
    NEURO_FUZZY_STRATEGY = "neuro_fuzzy_strategy"
    PATTERN_DISCOVERY = "pattern_discovery"
    INDICATOR_OPTIMIZATION = "indicator_optimization"
    REGIME_DETECTION = "regime_detection"
    CROSS_VALIDATION = "cross_validation"


@dataclass
class ExperimentConfig:
    """Configuration for a research experiment"""
    experiment_name: str
    hypothesis: str
    experiment_type: ExperimentType
    parameters: Dict[str, Any]
    data_requirements: Dict[str, Any]
    training_config: Dict[str, Any]
    validation_config: Dict[str, Any]
    timeout_minutes: int = 240  # 4 hours default
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class ExperimentResults:
    """Results from a completed experiment"""
    experiment_id: UUID
    status: ExperimentStatus
    fitness_score: Optional[float]
    performance_metrics: Dict[str, Any]
    training_results: Optional[Dict[str, Any]]
    backtesting_results: Optional[Dict[str, Any]]
    insights: List[str]
    error_info: Optional[Dict[str, Any]]
    execution_time_minutes: float
    completed_at: Optional[datetime]


class ResearchOrchestratorError(Exception):
    """Base exception for research orchestrator operations"""
    pass


class ExperimentExecutionError(ResearchOrchestratorError):
    """Exception raised during experiment execution"""
    pass


class ResourceLimitError(ResearchOrchestratorError):
    """Exception raised when resource limits are exceeded"""
    pass


class ResearchOrchestrator:
    """
    Central orchestration service for AI research experiments.
    
    Manages the complete experiment lifecycle from creation to completion,
    with robust error handling, resource management, and progress tracking.
    """
    
    def __init__(
        self,
        db_service: ResearchDatabaseService,
        max_concurrent_experiments: int = 3,
        default_timeout_minutes: int = 240
    ):
        self.db_service = db_service
        self.max_concurrent_experiments = max_concurrent_experiments
        self.default_timeout_minutes = default_timeout_minutes
        
        # Track running experiments
        self._running_experiments: Dict[UUID, asyncio.Task] = {}
        self._experiment_locks: Dict[UUID, asyncio.Lock] = {}
        
        # Service state
        self._is_initialized = False
        self._shutdown_event = asyncio.Event()
        
        # Metrics
        self._total_experiments = 0
        self._completed_experiments = 0
        self._failed_experiments = 0
        
        logger.info(f"Research orchestrator initialized with max_concurrent={max_concurrent_experiments}")
    
    async def initialize(self) -> None:
        """Initialize the research orchestrator"""
        if self._is_initialized:
            return
            
        try:
            # Ensure database connection
            await self.db_service.initialize()
            
            # Recovery: Check for interrupted experiments
            await self._recover_interrupted_experiments()
            
            self._is_initialized = True
            logger.info("Research orchestrator ready")
            
        except Exception as e:
            logger.error(f"Failed to initialize research orchestrator: {e}")
            raise ResearchOrchestratorError(f"Initialization failed: {e}") from e
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator"""
        logger.info("Shutting down research orchestrator")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel running experiments
        if self._running_experiments:
            logger.info(f"Cancelling {len(self._running_experiments)} running experiments")
            
            for experiment_id, task in self._running_experiments.items():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    # Update experiment status to cancelled
                    await self._update_experiment_status(
                        experiment_id, ExperimentStatus.CANCELLED
                    )
        
        # Close database connection
        await self.db_service.close()
        
        logger.info("Research orchestrator shutdown complete")
    
    async def create_experiment(
        self,
        session_id: UUID,
        config: ExperimentConfig
    ) -> UUID:
        """Create a new research experiment"""
        if not self._is_initialized:
            raise ResearchOrchestratorError("Orchestrator not initialized")
        
        experiment_id = uuid4()
        
        try:
            # Store experiment in database
            await self.db_service.execute_query("""
                INSERT INTO research.experiments (
                    id, session_id, experiment_name, hypothesis, 
                    experiment_type, configuration, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
                experiment_id,
                session_id,
                config.experiment_name,
                config.hypothesis,
                config.experiment_type.value,
                {
                    "parameters": config.parameters,
                    "data_requirements": config.data_requirements,
                    "training_config": config.training_config,
                    "validation_config": config.validation_config,
                    "timeout_minutes": config.timeout_minutes,
                    "priority": config.priority
                },
                ExperimentStatus.PENDING.value,
                datetime.now(timezone.utc)
            )
            
            self._total_experiments += 1
            
            logger.info(f"Experiment created: {experiment_id} '{config.experiment_name}' type={config.experiment_type.value}")
            
            return experiment_id
            
        except Exception as e:
            logger.error(f"Failed to create experiment {experiment_id}: {e}")
            raise ExperimentExecutionError(f"Failed to create experiment: {e}") from e
    
    async def start_experiment(self, experiment_id: UUID) -> None:
        """Start execution of a pending experiment"""
        if not self._is_initialized:
            raise ResearchOrchestratorError("Orchestrator not initialized")
        
        # Check resource limits
        if len(self._running_experiments) >= self.max_concurrent_experiments:
            raise ResourceLimitError(
                f"Maximum concurrent experiments ({self.max_concurrent_experiments}) exceeded"
            )
        
        # Get experiment configuration
        experiment = await self._get_experiment_config(experiment_id)
        if not experiment:
            raise ExperimentExecutionError(f"Experiment {experiment_id} not found")
        
        if experiment["status"] != ExperimentStatus.PENDING.value:
            raise ExperimentExecutionError(
                f"Experiment {experiment_id} is not in pending status"
            )
        
        # Create experiment lock
        self._experiment_locks[experiment_id] = asyncio.Lock()
        
        # Start experiment task
        task = asyncio.create_task(self._execute_experiment(experiment_id, experiment))
        self._running_experiments[experiment_id] = task
        
        logger.info(f"Experiment started: {experiment_id} '{experiment['experiment_name']}'")
    
    async def get_experiment_status(self, experiment_id: UUID) -> Dict[str, Any]:
        """Get current status of an experiment"""
        experiment = await self.db_service.execute_query("""
            SELECT id, experiment_name, status, hypothesis, experiment_type,
                   configuration, created_at, started_at, completed_at,
                   results, error_info
            FROM research.experiments 
            WHERE id = $1
        """, experiment_id, fetch="one")
        
        if not experiment:
            raise ExperimentExecutionError(f"Experiment {experiment_id} not found")
        
        # Add runtime information
        is_running = experiment_id in self._running_experiments
        
        return {
            **dict(experiment),
            "is_running": is_running,
            "runtime_info": {
                "total_experiments": self._total_experiments,
                "running_experiments": len(self._running_experiments),
                "completed_experiments": self._completed_experiments,
                "failed_experiments": self._failed_experiments
            }
        }
    
    async def list_experiments(
        self,
        session_id: Optional[UUID] = None,
        status: Optional[ExperimentStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List experiments with optional filtering"""
        query = """
            SELECT id, session_id, experiment_name, status, hypothesis,
                   experiment_type, created_at, started_at, completed_at,
                   fitness_score
            FROM research.experiments
        """
        
        conditions = []
        params = []
        param_count = 0
        
        if session_id:
            param_count += 1
            conditions.append(f"session_id = ${param_count}")
            params.append(session_id)
        
        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status.value)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY created_at DESC LIMIT ${param_count + 1}"
        params.append(limit)
        
        experiments = await self.db_service.execute_query(query, *params, fetch="all")
        
        # Add runtime status
        for exp in experiments:
            exp["is_running"] = exp["id"] in self._running_experiments
        
        return experiments
    
    async def cancel_experiment(self, experiment_id: UUID) -> None:
        """Cancel a running experiment"""
        if experiment_id not in self._running_experiments:
            raise ExperimentExecutionError(f"Experiment {experiment_id} is not running")
        
        # Cancel the task
        task = self._running_experiments[experiment_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Update status
        await self._update_experiment_status(experiment_id, ExperimentStatus.CANCELLED)
        
        logger.info(f"Experiment cancelled: {experiment_id}")
    
    async def get_orchestrator_metrics(self) -> Dict[str, Any]:
        """Get orchestrator performance metrics"""
        return {
            "total_experiments": self._total_experiments,
            "running_experiments": len(self._running_experiments),
            "completed_experiments": self._completed_experiments,
            "failed_experiments": self._failed_experiments,
            "max_concurrent": self.max_concurrent_experiments,
            "is_initialized": self._is_initialized,
            "database_health": await self.db_service.health_check()
        }
    
    # Private methods
    
    async def _execute_experiment(
        self,
        experiment_id: UUID,
        experiment_config: Dict[str, Any]
    ) -> ExperimentResults:
        """Execute a single experiment with comprehensive error handling"""
        start_time = datetime.now(timezone.utc)
        
        try:
            async with self._experiment_locks[experiment_id]:
                # Update status to initializing
                await self._update_experiment_status(
                    experiment_id, ExperimentStatus.INITIALIZING
                )
                
                logger.info(f"Experiment execution started: {experiment_id} '{experiment_config['experiment_name']}'")
                
                # Phase 1: Initialize experiment
                await self._initialize_experiment(experiment_id, experiment_config)
                
                # Phase 2: Execute training
                await self._update_experiment_status(
                    experiment_id, ExperimentStatus.RUNNING
                )
                
                training_results = await self._execute_training(
                    experiment_id, experiment_config
                )
                
                # Phase 3: Execute backtesting
                backtesting_results = await self._execute_backtesting(
                    experiment_id, experiment_config, training_results
                )
                
                # Phase 4: Analyze results
                await self._update_experiment_status(
                    experiment_id, ExperimentStatus.ANALYZING
                )
                
                analysis_results = await self._analyze_results(
                    experiment_id, training_results, backtesting_results
                )
                
                # Phase 5: Complete experiment
                end_time = datetime.now(timezone.utc)
                execution_time = (end_time - start_time).total_seconds() / 60.0
                
                results = ExperimentResults(
                    experiment_id=experiment_id,
                    status=ExperimentStatus.COMPLETED,
                    fitness_score=analysis_results.get("fitness_score"),
                    performance_metrics=analysis_results.get("metrics", {}),
                    training_results=training_results,
                    backtesting_results=backtesting_results,
                    insights=analysis_results.get("insights", []),
                    error_info=None,
                    execution_time_minutes=execution_time,
                    completed_at=end_time
                )
                
                await self._complete_experiment(experiment_id, results)
                
                self._completed_experiments += 1
                
                logger.info(f"Experiment completed successfully: {experiment_id} (time={execution_time:.1f}min, fitness={results.fitness_score})")
                
                return results
                
        except asyncio.CancelledError:
            logger.info(f"Experiment cancelled: {experiment_id}")
            raise
            
        except Exception as e:
            # Handle experiment failure
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds() / 60.0
            
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "execution_time_minutes": execution_time,
                "failed_at": end_time.isoformat()
            }
            
            await self._fail_experiment(experiment_id, error_info)
            
            self._failed_experiments += 1
            
            logger.error(f"Experiment failed: {experiment_id} - {e} (time={execution_time:.1f}min)")
            
            raise
            
        finally:
            # Cleanup
            self._running_experiments.pop(experiment_id, None)
            self._experiment_locks.pop(experiment_id, None)
    
    async def _get_experiment_config(self, experiment_id: UUID) -> Optional[Dict[str, Any]]:
        """Get experiment configuration from database"""
        return await self.db_service.execute_query("""
            SELECT id, session_id, experiment_name, hypothesis, experiment_type,
                   configuration, status, created_at
            FROM research.experiments 
            WHERE id = $1
        """, experiment_id, fetch="one")
    
    async def _update_experiment_status(
        self,
        experiment_id: UUID,
        status: ExperimentStatus,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update experiment status in database"""
        update_data = {"status": status.value, "updated_at": datetime.now(timezone.utc)}
        
        if status == ExperimentStatus.RUNNING:
            update_data["started_at"] = datetime.now(timezone.utc)
        elif status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED]:
            update_data["completed_at"] = datetime.now(timezone.utc)
        
        if additional_data:
            update_data.update(additional_data)
        
        await self.db_service.execute_query("""
            UPDATE research.experiments 
            SET status = $2, updated_at = $3
            WHERE id = $1
        """, experiment_id, status.value, datetime.now(timezone.utc))
    
    async def _initialize_experiment(
        self,
        experiment_id: UUID,
        experiment_config: Dict[str, Any]
    ) -> None:
        """Initialize experiment environment"""
        # This will be implemented to prepare data, validate configuration, etc.
        logger.info(f"Initializing experiment: {experiment_id}")
        
        # Placeholder for initialization logic
        await asyncio.sleep(0.1)  # Simulate initialization work
    
    async def _execute_training(
        self,
        experiment_id: UUID,
        experiment_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute neural network training via KTRDR API"""
        logger.info(f"Starting training phase: {experiment_id}")
        
        # This will be implemented with real KTRDR integration
        # For now, return realistic placeholder data
        await asyncio.sleep(0.5)  # Simulate training work
        
        return {
            "training_id": str(uuid4()),
            "epochs_completed": 100,
            "final_loss": 0.0234,
            "validation_loss": 0.0198,
            "training_time_minutes": 45.2,
            "accuracy": 0.7234,
            "model_path": f"/models/experiment_{experiment_id}",
            "status": "completed"
        }
    
    async def _execute_backtesting(
        self,
        experiment_id: UUID,
        experiment_config: Dict[str, Any],
        training_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute strategy backtesting"""
        logger.info(f"Starting backtesting phase: {experiment_id}")
        
        # Placeholder for KTRDR backtesting API integration
        await asyncio.sleep(0.3)  # Simulate backtesting work
        
        return {
            "backtest_id": str(uuid4()),
            "total_trades": 1234,
            "profitable_trades": 756,
            "profit_factor": 1.34,
            "sharpe_ratio": 1.67,
            "max_drawdown": 0.08,
            "total_return": 0.234
        }
    
    async def _analyze_results(
        self,
        experiment_id: UUID,
        training_results: Dict[str, Any],
        backtesting_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze experiment results and calculate fitness score"""
        logger.info(f"Analyzing results: {experiment_id}")
        
        # Calculate fitness score (placeholder implementation)
        profit_factor = backtesting_results.get("profit_factor", 1.0)
        sharpe_ratio = backtesting_results.get("sharpe_ratio", 0.0)
        max_drawdown = backtesting_results.get("max_drawdown", 1.0)
        
        # Simple fitness calculation
        fitness_score = (profit_factor * sharpe_ratio) / (1 + max_drawdown)
        
        insights = []
        if fitness_score > 1.5:
            insights.append("High-quality strategy discovered")
        if sharpe_ratio > 1.5:
            insights.append("Excellent risk-adjusted returns")
        if max_drawdown < 0.1:
            insights.append("Low drawdown strategy")
        
        return {
            "fitness_score": fitness_score,
            "metrics": {
                "profit_factor": profit_factor,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "total_trades": backtesting_results.get("total_trades", 0)
            },
            "insights": insights
        }
    
    async def _complete_experiment(
        self,
        experiment_id: UUID,
        results: ExperimentResults
    ) -> None:
        """Mark experiment as completed and store results"""
        await self.db_service.execute_query("""
            UPDATE research.experiments 
            SET status = $2, fitness_score = $3, results = $4, 
                completed_at = $5, updated_at = $5
            WHERE id = $1
        """, 
            experiment_id,
            results.status.value,
            results.fitness_score,
            {
                "performance_metrics": results.performance_metrics,
                "training_results": results.training_results,
                "backtesting_results": results.backtesting_results,
                "insights": results.insights,
                "execution_time_minutes": results.execution_time_minutes
            },
            results.completed_at
        )
    
    async def _fail_experiment(
        self,
        experiment_id: UUID,
        error_info: Dict[str, Any]
    ) -> None:
        """Mark experiment as failed and store error information"""
        await self.db_service.execute_query("""
            UPDATE research.experiments 
            SET status = $2, error_info = $3, completed_at = $4, updated_at = $4
            WHERE id = $1
        """, 
            experiment_id,
            ExperimentStatus.FAILED.value,
            error_info,
            datetime.now(timezone.utc)
        )
    
    async def _recover_interrupted_experiments(self) -> None:
        """Recover experiments that were interrupted during shutdown"""
        interrupted = await self.db_service.execute_query("""
            SELECT id, experiment_name 
            FROM research.experiments 
            WHERE status IN ('initializing', 'running', 'analyzing')
        """, fetch="all")
        
        if interrupted:
            logger.info(f"Recovering {len(interrupted)} interrupted experiments")
            
            for exp in interrupted:
                await self.db_service.execute_query("""
                    UPDATE research.experiments 
                    SET status = 'failed', 
                        error_info = $2,
                        completed_at = $3,
                        updated_at = $3
                    WHERE id = $1
                """, 
                    exp["id"],
                    {
                        "error_type": "SystemInterruption",
                        "error_message": "Experiment interrupted during system shutdown",
                        "recovered_at": datetime.now(timezone.utc).isoformat()
                    },
                    datetime.now(timezone.utc)
                )
                
                logger.info(f"Marked interrupted experiment as failed: {exp['id']} '{exp['experiment_name']}'")


# Factory function for creating research orchestrator
async def create_research_orchestrator(
    db_service: ResearchDatabaseService,
    max_concurrent_experiments: int = 3
) -> ResearchOrchestrator:
    """Create and initialize a research orchestrator instance"""
    orchestrator = ResearchOrchestrator(
        db_service=db_service,
        max_concurrent_experiments=max_concurrent_experiments
    )
    
    await orchestrator.initialize()
    return orchestrator