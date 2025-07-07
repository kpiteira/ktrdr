"""
Training Service

Core training orchestration service that integrates all existing KTRDR training
components with GPU acceleration and host-level resource management.
"""

import asyncio
import uuid
import torch
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

# Import existing ktrdr training components
from ktrdr.training.gpu_memory_manager import GPUMemoryManager, GPUMemoryConfig
from ktrdr.training.memory_manager import MemoryManager, MemoryBudget
from ktrdr.training.performance_optimizer import PerformanceOptimizer, PerformanceConfig
from ktrdr.training.data_optimization import DataLoadingOptimizer, DataConfig
from ktrdr.logging import get_logger

logger = get_logger(__name__)

class TrainingSession:
    """Represents an active training session with all its resources."""
    
    def __init__(self, session_id: str, config: Dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.status = "initializing"
        self.start_time = datetime.utcnow()
        self.last_updated = datetime.utcnow()
        
        # Progress tracking
        self.current_epoch = 0
        self.current_batch = 0
        self.total_epochs = config.get("training_config", {}).get("epochs", 100)
        self.total_batches = 0
        
        # Metrics tracking
        self.metrics = {}
        self.best_metrics = {}
        
        # Resource managers
        self.gpu_manager: Optional[GPUMemoryManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.performance_optimizer: Optional[PerformanceOptimizer] = None
        self.data_optimizer: Optional[DataLoadingOptimizer] = None
        
        # Training components
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.dataloader = None
        
        # Background task
        self.training_task: Optional[asyncio.Task] = None
        self.stop_requested = False
        
        # Error tracking
        self.error = None
        
    def update_progress(self, epoch: int, batch: int, metrics: Dict[str, float]):
        """Update training progress and metrics."""
        self.current_epoch = epoch
        self.current_batch = batch
        self.last_updated = datetime.utcnow()
        
        # Update metrics
        for key, value in metrics.items():
            if key not in self.metrics:
                self.metrics[key] = []
            self.metrics[key].append(value)
            
            # Track best metrics
            if "loss" in key.lower():
                if key not in self.best_metrics or value < self.best_metrics[key]:
                    self.best_metrics[key] = value
            else:
                if key not in self.best_metrics or value > self.best_metrics[key]:
                    self.best_metrics[key] = value
    
    def get_progress_dict(self) -> Dict[str, Any]:
        """Get progress information as dictionary."""
        return {
            "epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "batch": self.current_batch,
            "total_batches": self.total_batches,
            "progress_percent": (self.current_epoch / self.total_epochs) * 100 if self.total_epochs > 0 else 0
        }
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage information."""
        resource_info = {
            "gpu_allocated": self.gpu_manager is not None and self.gpu_manager.enabled,
            "memory_monitoring": self.memory_manager is not None,
            "performance_optimization": self.performance_optimizer is not None
        }
        
        # GPU usage
        if self.gpu_manager and self.gpu_manager.enabled:
            try:
                snapshot = self.gpu_manager.capture_snapshot(0)
                resource_info["gpu_memory"] = {
                    "allocated_mb": snapshot.allocated_mb,
                    "total_mb": snapshot.total_mb,
                    "utilization_percent": (snapshot.allocated_mb / snapshot.total_mb) * 100 if snapshot.total_mb > 0 else 0
                }
            except Exception as e:
                resource_info["gpu_memory"] = {"error": str(e)}
        
        # System memory
        if self.memory_manager:
            try:
                memory_snapshot = self.memory_manager.capture_snapshot()
                resource_info["system_memory"] = {
                    "process_mb": memory_snapshot.process_memory_mb,
                    "system_percent": memory_snapshot.system_memory_percent,
                    "system_total_mb": memory_snapshot.system_memory_total_mb
                }
            except Exception as e:
                resource_info["system_memory"] = {"error": str(e)}
        
        return resource_info
    
    async def cleanup(self):
        """Clean up session resources."""
        logger.info(f"Cleaning up session {self.session_id}")
        
        # Stop training task if running
        if self.training_task and not self.training_task.done():
            self.stop_requested = True
            try:
                await asyncio.wait_for(self.training_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"Training task for session {self.session_id} did not stop gracefully")
                self.training_task.cancel()
        
        # Cleanup GPU resources
        if self.gpu_manager:
            try:
                self.gpu_manager.cleanup_memory()
                if hasattr(self.gpu_manager, 'stop_monitoring'):
                    self.gpu_manager.stop_monitoring()
            except Exception as e:
                logger.warning(f"Error cleaning up GPU resources: {str(e)}")
        
        # Cleanup memory manager
        if self.memory_manager:
            try:
                self.memory_manager.cleanup_memory()
                if hasattr(self.memory_manager, 'stop_monitoring'):
                    self.memory_manager.stop_monitoring()
            except Exception as e:
                logger.warning(f"Error cleaning up memory resources: {str(e)}")
        
        logger.info(f"Session {self.session_id} cleanup completed")

class TrainingService:
    """
    Main training service that orchestrates GPU-accelerated training sessions.
    
    This service integrates all existing KTRDR training components:
    - GPUMemoryManager for GPU resource management
    - MemoryManager for system memory monitoring
    - PerformanceOptimizer for training optimization
    - DataLoadingOptimizer for efficient data loading
    """
    
    def __init__(self, max_concurrent_sessions: int = 1, session_timeout_minutes: int = 60):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_timeout_minutes = session_timeout_minutes
        self.sessions: Dict[str, TrainingSession] = {}
        
        # Global resource managers
        self.global_gpu_manager: Optional[GPUMemoryManager] = None
        self._initialize_global_resources()
        
        # Background cleanup task (will be started when needed)
        self.cleanup_task = None
    
    def _initialize_global_resources(self):
        """Initialize global GPU resources."""
        try:
            if torch.cuda.is_available():
                gpu_config = GPUMemoryConfig(
                    memory_fraction=0.8,
                    enable_mixed_precision=True,
                    enable_memory_profiling=True,
                    profiling_interval_seconds=1.0
                )
                self.global_gpu_manager = GPUMemoryManager(gpu_config)
                logger.info(f"Global GPU manager initialized with {self.global_gpu_manager.num_devices} devices")
            else:
                logger.info("No GPU available, running in CPU-only mode")
        except Exception as e:
            logger.error(f"Failed to initialize global GPU resources: {str(e)}")
            self.global_gpu_manager = None
    
    async def create_session(self, config: Dict[str, Any], session_id: Optional[str] = None) -> str:
        """
        Create a new training session.
        
        Args:
            config: Training configuration including model, training, and data configs
            session_id: Optional session ID, will be generated if not provided
            
        Returns:
            Session ID of the created session
            
        Raises:
            Exception: If session creation fails or resource limits exceeded
        """
        # Check session limits
        active_sessions = [s for s in self.sessions.values() if s.status in ["running", "initializing"]]
        if len(active_sessions) >= self.max_concurrent_sessions:
            raise Exception(f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached")
        
        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Check for duplicate session ID
        if session_id in self.sessions:
            raise Exception(f"Session {session_id} already exists")
        
        # Create session
        session = TrainingSession(session_id, config)
        
        try:
            # Initialize session resources
            await self._initialize_session_resources(session)
            
            # Add to sessions
            self.sessions[session_id] = session
            
            # Start background cleanup task if not already running
            if self.cleanup_task is None:
                self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            
            # Start training in background
            session.training_task = asyncio.create_task(self._run_training_session(session))
            
            logger.info(f"Training session {session_id} created successfully")
            return session_id
            
        except Exception as e:
            # Cleanup on failure
            await session.cleanup()
            raise Exception(f"Failed to create training session: {str(e)}")
    
    async def _initialize_session_resources(self, session: TrainingSession):
        """Initialize resources for a training session."""
        try:
            # Initialize GPU manager for session
            if self.global_gpu_manager and self.global_gpu_manager.enabled:
                # Create session-specific GPU config
                gpu_config = GPUMemoryConfig()
                if "gpu_config" in session.config:
                    # Update with session-specific GPU settings
                    for key, value in session.config["gpu_config"].items():
                        if hasattr(gpu_config, key):
                            setattr(gpu_config, key, value)
                
                session.gpu_manager = GPUMemoryManager(gpu_config)
                logger.info(f"GPU manager initialized for session {session.session_id}")
            
            # Initialize memory manager
            memory_budget = MemoryBudget(
                max_process_memory_mb=4096,  # TODO: Make configurable
                warning_threshold_percent=0.8,
                enable_monitoring=True,
                monitoring_interval_seconds=1.0
            )
            session.memory_manager = MemoryManager(budget=memory_budget)
            
            # Initialize performance optimizer
            perf_config = PerformanceConfig(
                enable_mixed_precision=session.gpu_manager is not None and session.gpu_manager.enabled,
                adaptive_batch_size=True,
                compile_model=False,  # Disable for compatibility
                min_batch_size=16,
                max_batch_size=128
            )
            session.performance_optimizer = PerformanceOptimizer(perf_config)
            
            # Initialize data optimizer
            data_config = DataConfig(
                enable_memory_mapping=False,  # Disable for compatibility
                enable_batch_prefetching=True,
                balanced_sampling=True,
                symbol_balanced_sampling=True
            )
            session.data_optimizer = DataLoadingOptimizer(data_config)
            
            session.status = "initialized"
            logger.info(f"All resources initialized for session {session.session_id}")
            
        except Exception as e:
            session.error = str(e)
            session.status = "failed"
            raise
    
    async def _run_training_session(self, session: TrainingSession):
        """Run the actual training for a session."""
        try:
            session.status = "running"
            session.last_updated = datetime.utcnow()
            
            logger.info(f"Starting training for session {session.session_id}")
            
            # Start resource monitoring
            if session.gpu_manager:
                session.gpu_manager.start_monitoring()
            if session.memory_manager:
                session.memory_manager.start_monitoring()
            
            # TODO: Implement actual training loop
            # This is where we would:
            # 1. Load and prepare data using data_optimizer
            # 2. Initialize model and move to GPU
            # 3. Setup optimizer and criterion
            # 4. Run training loop with performance_optimizer
            # 5. Handle checkpointing and metrics
            
            # For now, simulate training progress
            total_epochs = session.total_epochs
            for epoch in range(total_epochs):
                if session.stop_requested:
                    logger.info(f"Stop requested for session {session.session_id}")
                    break
                
                # Simulate epoch processing
                await asyncio.sleep(0.1)  # Simulate work
                
                # Update progress
                session.update_progress(
                    epoch=epoch + 1,
                    batch=100,  # Simulate 100 batches per epoch
                    metrics={
                        "train_loss": 1.0 - (epoch / total_epochs) * 0.8,  # Decreasing loss
                        "train_accuracy": 0.5 + (epoch / total_epochs) * 0.4,  # Increasing accuracy
                        "val_loss": 1.1 - (epoch / total_epochs) * 0.7,
                        "val_accuracy": 0.45 + (epoch / total_epochs) * 0.35
                    }
                )
                
                # Periodic cleanup
                if epoch % 10 == 0:
                    if session.memory_manager:
                        session.memory_manager.cleanup_memory()
                    if session.gpu_manager:
                        session.gpu_manager.cleanup_memory()
            
            # Training completed successfully
            if not session.stop_requested:
                session.status = "completed"
                logger.info(f"Training completed for session {session.session_id}")
            else:
                session.status = "stopped"
                logger.info(f"Training stopped for session {session.session_id}")
            
        except Exception as e:
            session.error = str(e)
            session.status = "failed"
            logger.error(f"Training failed for session {session.session_id}: {str(e)}")
        
        finally:
            # Stop monitoring
            try:
                if session.gpu_manager:
                    session.gpu_manager.stop_monitoring()
                if session.memory_manager:
                    session.memory_manager.stop_monitoring()
            except Exception as e:
                logger.warning(f"Error stopping monitoring for session {session.session_id}: {str(e)}")
            
            session.last_updated = datetime.utcnow()
    
    async def stop_session(self, session_id: str, save_checkpoint: bool = True) -> bool:
        """
        Stop a running training session.
        
        Args:
            session_id: ID of session to stop
            save_checkpoint: Whether to save a checkpoint before stopping
            
        Returns:
            True if session was stopped successfully
        """
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        if session.status not in ["running", "initializing"]:
            raise Exception(f"Session {session_id} is not running (status: {session.status})")
        
        logger.info(f"Stopping session {session_id}")
        
        # Request stop
        session.stop_requested = True
        
        # TODO: Implement checkpoint saving if requested
        if save_checkpoint:
            logger.info(f"Checkpoint saving requested for session {session_id}")
            # Implementation would save model state, optimizer state, etc.
        
        # Wait for training task to complete
        if session.training_task:
            try:
                await asyncio.wait_for(session.training_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning(f"Training task for session {session_id} did not stop gracefully")
                session.training_task.cancel()
                session.status = "stopped"
        
        return True
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed status of a training session."""
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        return {
            "session_id": session_id,
            "status": session.status,
            "progress": session.get_progress_dict(),
            "metrics": {
                "current": session.metrics,
                "best": session.best_metrics
            },
            "resource_usage": session.get_resource_usage(),
            "start_time": session.start_time.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "error": session.error
        }
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all training sessions with summary information."""
        sessions = []
        for session_id, session in self.sessions.items():
            sessions.append({
                "session_id": session_id,
                "status": session.status,
                "start_time": session.start_time.isoformat(),
                "last_updated": session.last_updated.isoformat(),
                "progress": session.get_progress_dict(),
                "gpu_allocated": session.gpu_manager is not None and session.gpu_manager.enabled,
                "error": session.error
            })
        return sessions
    
    async def cleanup_session(self, session_id: str) -> bool:
        """Clean up a completed or failed session."""
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        # Only allow cleanup of non-running sessions
        if session.status == "running":
            raise Exception(f"Cannot cleanup running session {session_id}")
        
        # Cleanup resources
        await session.cleanup()
        
        # Remove from sessions
        del self.sessions[session_id]
        
        logger.info(f"Session {session_id} cleaned up successfully")
        return True
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of timed-out sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                timeout_threshold = timedelta(minutes=self.session_timeout_minutes)
                
                sessions_to_cleanup = []
                for session_id, session in self.sessions.items():
                    # Check for timed-out sessions
                    if session.status in ["completed", "failed", "stopped"]:
                        time_since_update = current_time - session.last_updated
                        if time_since_update > timeout_threshold:
                            sessions_to_cleanup.append(session_id)
                
                # Cleanup timed-out sessions
                for session_id in sessions_to_cleanup:
                    try:
                        await self.cleanup_session(session_id)
                        logger.info(f"Auto-cleaned up timed-out session {session_id}")
                    except Exception as e:
                        logger.error(f"Failed to auto-cleanup session {session_id}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {str(e)}")
    
    async def shutdown(self):
        """Shutdown the training service and cleanup all resources."""
        logger.info("Shutting down training service...")
        
        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Stop and cleanup all active sessions
        for session_id in list(self.sessions.keys()):
            try:
                session = self.sessions[session_id]
                if session.status == "running":
                    await self.stop_session(session_id, save_checkpoint=False)
                await self.cleanup_session(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id} during shutdown: {str(e)}")
        
        # Cleanup global resources
        if self.global_gpu_manager:
            try:
                self.global_gpu_manager.cleanup_memory()
            except Exception as e:
                logger.warning(f"Error cleaning up global GPU resources: {str(e)}")
        
        logger.info("Training service shutdown completed")

# Global service instance
_training_service: Optional[TrainingService] = None

def get_training_service(max_concurrent_sessions: int = 1, session_timeout_minutes: int = 60) -> TrainingService:
    """Get or create the global training service instance."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService(max_concurrent_sessions, session_timeout_minutes)
    return _training_service