"""
Experiment Executor Component

Handles all aspects of experiment execution for the research agent system.
Extracted from ResearchAgentMVP to follow Single Responsibility Principle.

Responsibilities:
- Execute experiments using KTRDR training/backtesting services
- Monitor experiment progress and status
- Handle experiment cancellation and timeouts
- Manage concurrent experiment execution with semaphores
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

from ktrdr import get_logger
from ktrdr.errors import ProcessingError, ConnectionError as KtrdrConnectionError

from .interfaces import (
    ExperimentExecutorInterface,
    ResearchContext,
    ExperimentConfig,
    ExperimentResult,
)
from ..services.interfaces import KTRDRService
from ..config import ExperimentExecutorConfig

logger = get_logger(__name__)


class ExperimentExecutor(ExperimentExecutorInterface):
    """
    Concrete implementation of experiment execution.
    
    Manages concurrent experiment execution using KTRDR services
    with proper resource management and error handling.
    """
    
    def __init__(
        self,
        ktrdr_service: KTRDRService,
        config: Optional[ExperimentExecutorConfig] = None
    ):
        self.ktrdr_service = ktrdr_service
        self.config = config or ExperimentExecutorConfig()
        
        # Semaphore for controlling concurrency
        self.execution_semaphore = asyncio.Semaphore(self.config.max_concurrent_experiments)
        
        # Track running experiments
        self.running_experiments: Dict[UUID, Dict[str, Any]] = {}
        
        logger.info(f"Experiment executor initialized with max_concurrent={self.config.max_concurrent_experiments}, timeout={self.config.default_timeout_hours}h")
    
    async def execute_experiment(
        self,
        config: ExperimentConfig,
        context: ResearchContext
    ) -> ExperimentResult:
        """Execute a single experiment"""
        
        async with self.execution_semaphore:
            try:
                logger.info(f"Starting experiment {config.experiment_id} for hypothesis {config.hypothesis_id}")
                
                # Register as running
                self.running_experiments[config.experiment_id] = {
                    "status": "starting",
                    "started_at": datetime.now(timezone.utc),
                    "config": config,
                    "context": context
                }
                
                # Start experiment using KTRDR service
                training_result = await self.ktrdr_service.start_training(config.parameters)
                
                # Update status
                self.running_experiments[config.experiment_id]["status"] = "running"
                self.running_experiments[config.experiment_id]["training_job_id"] = training_result.get("job_id")
                
                # Monitor experiment to completion
                result = await self._monitor_experiment_to_completion(
                    config.experiment_id,
                    training_result.get("job_id"),
                    config.timeout_hours
                )
                
                # Clean up
                if config.experiment_id in self.running_experiments:
                    del self.running_experiments[config.experiment_id]
                
                logger.info(f"Experiment {config.experiment_id} completed with fitness score: {result.fitness_score}")
                return result
                
            except Exception as e:
                logger.error(f"Experiment {config.experiment_id} failed: {e}")
                
                # Clean up on error
                if config.experiment_id in self.running_experiments:
                    del self.running_experiments[config.experiment_id]
                
                # Return failed result
                return ExperimentResult(
                    experiment_id=config.experiment_id,
                    status="failed",
                    fitness_score=0.0,
                    metrics={},
                    artifacts={},
                    error_message=str(e),
                    metadata={
                        "failure_reason": "execution_error",
                        "error_type": type(e).__name__
                    }
                )
    
    async def monitor_experiments(
        self,
        experiment_ids: List[UUID],
        context: ResearchContext
    ) -> Dict[UUID, Dict[str, Any]]:
        """Monitor multiple running experiments"""
        
        try:
            logger.info(f"Monitoring {len(experiment_ids)} experiments")
            
            status_map = {}
            
            for exp_id in experiment_ids:
                if exp_id in self.running_experiments:
                    exp_info = self.running_experiments[exp_id]
                    training_job_id = exp_info.get("training_job_id")
                    
                    if training_job_id:
                        # Get status from KTRDR service
                        try:
                            status = await self.ktrdr_service.get_training_status(training_job_id)
                            status_map[exp_id] = {
                                "status": status.get("status", "unknown"),
                                "progress": status.get("progress", 0),
                                "metrics": status.get("metrics", {}),
                                "started_at": exp_info["started_at"].isoformat(),
                                "training_job_id": training_job_id
                            }
                        except Exception as e:
                            logger.error(f"Failed to get status for experiment {exp_id}: {e}")
                            status_map[exp_id] = {
                                "status": "error",
                                "error": str(e)
                            }
                    else:
                        status_map[exp_id] = {
                            "status": exp_info["status"],
                            "started_at": exp_info["started_at"].isoformat()
                        }
                else:
                    status_map[exp_id] = {
                        "status": "not_tracked",
                        "message": "Experiment not found in running experiments"
                    }
            
            return status_map
            
        except Exception as e:
            logger.error(f"Failed to monitor experiments: {e}")
            raise ProcessingError(
                "Experiment monitoring failed",
                error_code="EXPERIMENT_MONITORING_FAILED",
                details={
                    "experiment_ids": [str(id) for id in experiment_ids],
                    "original_error": str(e)
                }
            ) from e
    
    async def cancel_experiment(
        self,
        experiment_id: UUID
    ) -> bool:
        """Cancel a running experiment"""
        
        try:
            logger.info(f"Cancelling experiment {experiment_id}")
            
            if experiment_id not in self.running_experiments:
                logger.warning(f"Experiment {experiment_id} not found in running experiments")
                return False
            
            exp_info = self.running_experiments[experiment_id]
            training_job_id = exp_info.get("training_job_id")
            
            if training_job_id:
                # Try to cancel the training job
                # Note: This would require a cancel method in KTRDRService interface
                # For now, we just mark it as cancelled locally
                logger.warning(f"KTRDR service doesn't support cancellation, marking experiment {experiment_id} as cancelled locally")
            
            # Remove from tracking
            del self.running_experiments[experiment_id]
            
            logger.info(f"Experiment {experiment_id} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel experiment {experiment_id}: {e}")
            return False
    
    async def _monitor_experiment_to_completion(
        self,
        experiment_id: UUID,
        training_job_id: str,
        timeout_hours: int
    ) -> ExperimentResult:
        """Monitor a single experiment until completion or timeout"""
        
        start_time = datetime.now(timezone.utc)
        timeout_seconds = timeout_hours * 3600
        check_interval = self.config.progress_check_interval_seconds  # Use configurable check interval
        
        logger.info(f"Monitoring experiment {experiment_id} (job: {training_job_id}) with {timeout_hours}h timeout")
        
        while True:
            try:
                # Check timeout
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    logger.error(f"Experiment {experiment_id} timed out after {timeout_hours} hours")
                    return ExperimentResult(
                        experiment_id=experiment_id,
                        status="timeout",
                        fitness_score=0.0,
                        metrics={},
                        artifacts={},
                        error_message=f"Experiment timed out after {timeout_hours} hours",
                        metadata={"timeout_hours": timeout_hours, "elapsed_seconds": elapsed}
                    )
                
                # Get current status
                status = await self.ktrdr_service.get_training_status(training_job_id)
                current_status = status.get("status", "unknown")
                
                logger.debug(f"Experiment {experiment_id} status: {current_status}")
                
                if current_status in ["completed", "finished", "success"]:
                    # Get final results
                    results = await self.ktrdr_service.get_training_results(training_job_id)
                    
                    # Calculate fitness score from results
                    fitness_score = self._calculate_fitness_score(results)
                    
                    return ExperimentResult(
                        experiment_id=experiment_id,
                        status="completed",
                        fitness_score=fitness_score,
                        metrics=results.get("metrics", {}),
                        artifacts=results.get("artifacts", {}),
                        metadata={
                            "training_job_id": training_job_id,
                            "completion_time": datetime.now(timezone.utc).isoformat(),
                            "elapsed_seconds": elapsed
                        }
                    )
                
                elif current_status in ["failed", "error", "cancelled"]:
                    error_message = status.get("error_message", f"Training failed with status: {current_status}")
                    
                    return ExperimentResult(
                        experiment_id=experiment_id,
                        status="failed",
                        fitness_score=0.0,
                        metrics=status.get("metrics", {}),
                        artifacts={},
                        error_message=error_message,
                        metadata={
                            "training_job_id": training_job_id,
                            "failure_status": current_status,
                            "elapsed_seconds": elapsed
                        }
                    )
                
                # Still running, wait and check again
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring experiment {experiment_id}: {e}")
                
                # Return error result
                return ExperimentResult(
                    experiment_id=experiment_id,
                    status="error",
                    fitness_score=0.0,
                    metrics={},
                    artifacts={},
                    error_message=f"Monitoring error: {e}",
                    metadata={
                        "training_job_id": training_job_id,
                        "error_type": type(e).__name__,
                        "elapsed_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
                    }
                )
    
    def _calculate_fitness_score(self, results: Dict[str, Any]) -> float:
        """Calculate fitness score from experiment results"""
        
        try:
            # Extract key metrics
            metrics = results.get("metrics", {})
            
            # Simple fitness calculation - can be made more sophisticated
            profit_factor = metrics.get("profit_factor", 0.0)
            sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
            max_drawdown = metrics.get("max_drawdown", 1.0)
            win_rate = metrics.get("win_rate", 0.0)
            
            # Normalize and combine metrics
            fitness_score = 0.0
            
            if profit_factor > 0:
                fitness_score += min(profit_factor / 2.0, 0.3)  # Cap at 0.3
            
            if sharpe_ratio > 0:
                fitness_score += min(sharpe_ratio / 3.0, 0.3)  # Cap at 0.3
            
            if max_drawdown < 1.0:
                fitness_score += (1.0 - max_drawdown) * 0.2  # Up to 0.2
            
            if win_rate > 0:
                fitness_score += win_rate * 0.2  # Up to 0.2
            
            # Ensure score is between 0 and 1
            fitness_score = max(0.0, min(1.0, fitness_score))
            
            logger.debug(f"Calculated fitness score: {fitness_score} from metrics: {metrics}")
            return fitness_score
            
        except Exception as e:
            logger.error(f"Error calculating fitness score: {e}")
            return 0.0