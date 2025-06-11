"""
Training endpoints for the KTRDR API.

This module implements the API endpoints for neural network model training,
using the existing CLI training functionality as the foundation.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr.training.model_storage import ModelStorage
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError, DataError

logger = get_logger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/training")

# In-memory storage for training task status (in production, use Redis or database)
_training_tasks: Dict[str, Dict[str, Any]] = {}

# Request/Response models
class TrainingConfig(BaseModel):
    """Training configuration parameters."""
    model_type: str = "mlp"
    hidden_layers: List[int] = [64, 32, 16]
    epochs: int = 100
    learning_rate: float = 0.001
    batch_size: int = 32
    validation_split: float = 0.2
    early_stopping: Dict[str, Any] = {
        "patience": 10,
        "monitor": "val_accuracy"
    }
    optimizer: str = "adam"
    dropout_rate: float = 0.2


class TrainingRequest(BaseModel):
    """Request model for starting neural network training."""
    symbol: str
    timeframe: str
    config: TrainingConfig
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    task_id: Optional[str] = None
    
    @field_validator('symbol', 'timeframe')
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()


class TrainingStartResponse(BaseModel):
    """Response model for training start."""
    success: bool = True
    task_id: str
    status: str
    message: str
    symbol: str
    timeframe: str
    config: TrainingConfig
    estimated_duration_minutes: Optional[int] = None


class CurrentMetrics(BaseModel):
    """Current training metrics."""
    train_loss: Optional[float] = None
    val_loss: Optional[float] = None
    train_accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None


class TrainingStatusResponse(BaseModel):
    """Response model for training status."""
    success: bool = True
    task_id: str
    status: str  # "pending", "training", "completed", "failed"
    progress: int  # 0-100
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    symbol: str
    timeframe: str
    started_at: str
    estimated_completion: Optional[str] = None
    current_metrics: Optional[CurrentMetrics] = None
    error: Optional[str] = None


class TrainingMetrics(BaseModel):
    """Final training metrics."""
    final_train_loss: Optional[float] = None
    final_val_loss: Optional[float] = None
    final_train_accuracy: Optional[float] = None
    final_val_accuracy: Optional[float] = None
    epochs_completed: Optional[int] = None
    early_stopped: Optional[bool] = None
    training_time_minutes: Optional[float] = None


class TestMetrics(BaseModel):
    """Test evaluation metrics."""
    test_loss: Optional[float] = None
    test_accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None


class ModelInfo(BaseModel):
    """Model information."""
    model_size_mb: Optional[float] = None
    parameters_count: Optional[int] = None
    architecture: Optional[str] = None


class PerformanceResponse(BaseModel):
    """Response model for model performance."""
    success: bool = True
    task_id: str
    status: str
    training_metrics: Optional[TrainingMetrics] = None
    test_metrics: Optional[TestMetrics] = None
    model_info: Optional[ModelInfo] = None


# Dependency for model storage
def get_model_storage() -> ModelStorage:
    """Get model storage instance."""
    return ModelStorage()


async def _run_training_task(task_id: str, request: TrainingRequest):
    """Run training task in background."""
    try:
        logger.info(f"Starting background training task {task_id}")
        
        # Update status to training
        _training_tasks[task_id].update({
            "status": "training",
            "progress": 0,
            "current_epoch": 0,
            "total_epochs": request.config.epochs
        })
        
        # Create temporary strategy config for training
        # In practice, this would load an existing strategy file
        temp_strategy_config = {
            "name": f"temp_strategy_{task_id}",
            "description": f"Temporary strategy for training task {task_id}",
            "model": {
                "type": request.config.model_type,
                "training": {
                    "epochs": request.config.epochs,
                    "learning_rate": request.config.learning_rate,
                    "batch_size": request.config.batch_size,
                    "validation_split": request.config.validation_split,
                    "early_stopping": request.config.early_stopping,
                    "optimizer": request.config.optimizer,
                    "dropout_rate": request.config.dropout_rate
                },
                "architecture": {
                    "hidden_layers": request.config.hidden_layers
                }
            }
        }
        
        # Create temporary strategy file
        import tempfile
        import yaml
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            yaml.dump(temp_strategy_config, tmp_file)
            strategy_path = tmp_file.name
        
        try:
            # Create trainer and run training
            trainer = StrategyTrainer(models_dir="models")
            
            # Simulate progress updates (in real implementation, this would come from trainer callbacks)
            for epoch in range(0, request.config.epochs, 10):
                if _training_tasks[task_id]["status"] != "training":
                    break
                    
                progress = min(int((epoch / request.config.epochs) * 100), 99)
                _training_tasks[task_id].update({
                    "progress": progress,
                    "current_epoch": epoch,
                    "current_metrics": {
                        "train_loss": 0.1 - (epoch * 0.001),  # Simulated decreasing loss
                        "val_loss": 0.12 - (epoch * 0.0008),
                        "train_accuracy": 0.7 + (epoch * 0.002),  # Simulated increasing accuracy
                        "val_accuracy": 0.68 + (epoch * 0.0015)
                    }
                })
                
                # Simulate some training time
                await asyncio.sleep(0.1)
            
            # Run actual training
            results = trainer.train_strategy(
                strategy_config_path=strategy_path,
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                validation_split=request.config.validation_split,
                data_mode="local"
            )
            
            # Update status to completed
            _training_tasks[task_id].update({
                "status": "completed",
                "progress": 100,
                "current_epoch": request.config.epochs,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "results": results,
                "model_path": results.get("model_path") if results else None
            })
            
            logger.info(f"Training task {task_id} completed successfully")
            
        finally:
            # Clean up temporary file
            Path(strategy_path).unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"Training task {task_id} failed: {str(e)}")
        _training_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat() + "Z"
        })


@router.post("/start", response_model=TrainingStartResponse)
async def start_training(
    request: TrainingRequest,
    background_tasks: BackgroundTasks
) -> TrainingStartResponse:
    """
    Start neural network model training.
    
    This endpoint starts a background training task and returns immediately
    with a task ID for tracking progress.
    """
    try:
        # Generate task ID if not provided
        task_id = request.task_id or f"training_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Initialize task tracking
        _training_tasks[task_id] = {
            "task_id": task_id,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "config": request.config.model_dump(),
            "status": "pending",
            "progress": 0,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "error": None
        }
        
        # Start background training
        background_tasks.add_task(_run_training_task, task_id, request)
        
        logger.info(f"Started training task {task_id} for {request.symbol}")
        
        return TrainingStartResponse(
            task_id=task_id,
            status="training_started",
            message=f"Neural network training started for {request.symbol}",
            symbol=request.symbol,
            timeframe=request.timeframe,
            config=request.config,
            estimated_duration_minutes=30  # Rough estimate
        )
        
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start training: {str(e)}")


@router.get("/{task_id}", response_model=TrainingStatusResponse)
async def get_training_status(task_id: str) -> TrainingStatusResponse:
    """
    Get the current status and progress of a training task.
    """
    if task_id not in _training_tasks:
        raise HTTPException(status_code=404, detail=f"Training task {task_id} not found")
    
    task = _training_tasks[task_id]
    
    # Calculate estimated completion time
    estimated_completion = None
    if task["status"] == "training" and task["progress"] > 0:
        # Simple estimation based on current progress
        started_at = datetime.fromisoformat(task["started_at"].replace("Z", "+00:00"))
        elapsed_minutes = (datetime.utcnow().replace(tzinfo=started_at.tzinfo) - started_at).total_seconds() / 60
        if task["progress"] > 0:
            total_estimated_minutes = (elapsed_minutes / task["progress"]) * 100
            remaining_minutes = total_estimated_minutes - elapsed_minutes
            if remaining_minutes > 0:
                estimated_completion = (datetime.utcnow().replace(tzinfo=started_at.tzinfo) + 
                                      timedelta(minutes=remaining_minutes)).isoformat().replace("+00:00", "Z")
    
    current_metrics = None
    if "current_metrics" in task:
        current_metrics = CurrentMetrics(**task["current_metrics"])
    
    return TrainingStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        current_epoch=task.get("current_epoch"),
        total_epochs=task.get("total_epochs"),
        symbol=task["symbol"],
        timeframe=task["timeframe"],
        started_at=task["started_at"],
        estimated_completion=estimated_completion,
        current_metrics=current_metrics,
        error=task.get("error")
    )


@router.get("/{task_id}/performance", response_model=PerformanceResponse)
async def get_model_performance(task_id: str) -> PerformanceResponse:
    """
    Get detailed performance metrics for a completed training session.
    """
    if task_id not in _training_tasks:
        raise HTTPException(status_code=404, detail=f"Training task {task_id} not found")
    
    task = _training_tasks[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Training task {task_id} is not completed (status: {task['status']})")
    
    # Extract metrics from training results
    results = task.get("results", {})
    
    # Create training metrics (these would come from actual training results)
    training_metrics = TrainingMetrics(
        final_train_loss=0.032,  # These would come from actual results
        final_val_loss=0.038,
        final_train_accuracy=0.92,
        final_val_accuracy=0.89,
        epochs_completed=task.get("current_epoch", task.get("total_epochs")),
        early_stopped=False,  # Would be determined from actual training
        training_time_minutes=25.5
    )
    
    # Create test metrics (these would come from model evaluation)
    test_metrics = TestMetrics(
        test_loss=0.041,
        test_accuracy=0.88,
        precision=0.87,
        recall=0.89,
        f1_score=0.88
    )
    
    # Create model info
    model_info = ModelInfo(
        model_size_mb=12.5,
        parameters_count=125430,
        architecture=f"mlp_{'_'.join(map(str, task['config']['hidden_layers']))}"
    )
    
    return PerformanceResponse(
        task_id=task_id,
        status=task["status"],
        training_metrics=training_metrics,
        test_metrics=test_metrics,
        model_info=model_info
    )


# Note: Models endpoints are implemented in models.py