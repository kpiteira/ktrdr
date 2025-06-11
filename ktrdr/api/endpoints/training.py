"""
Training endpoints for the KTRDR API.

This module implements the API endpoints for neural network model training,
using the existing CLI training functionality as the foundation.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.api.services.training_service import TrainingService
from ktrdr.errors import ValidationError, DataError

logger = get_logger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/training")


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
    success: bool
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
    success: bool
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
    success: bool
    task_id: str
    status: str
    training_metrics: Optional[TrainingMetrics] = None
    test_metrics: Optional[TestMetrics] = None
    model_info: Optional[ModelInfo] = None


# Singleton training service instance
_training_service: Optional[TrainingService] = None

# Dependency for training service
async def get_training_service() -> TrainingService:
    """Get training service instance (singleton)."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService()
    return _training_service


@router.post("/start", response_model=TrainingStartResponse)
async def start_training(
    request: TrainingRequest,
    service: TrainingService = Depends(get_training_service)
) -> TrainingStartResponse:
    """
    Start neural network model training.
    
    This endpoint starts a background training task and returns immediately
    with a task ID for tracking progress.
    """
    try:
        result = await service.start_training(
            symbol=request.symbol,
            timeframe=request.timeframe,
            config=request.config.model_dump(),
            start_date=request.start_date,
            end_date=request.end_date,
            task_id=request.task_id
        )
        
        return TrainingStartResponse(
            success=result["success"],
            task_id=result["task_id"],
            status=result["status"],
            message=result["message"],
            symbol=result["symbol"],
            timeframe=result["timeframe"],
            config=TrainingConfig(**result["config"]),
            estimated_duration_minutes=result.get("estimated_duration_minutes")
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start training")


@router.get("/{task_id}", response_model=TrainingStatusResponse)
async def get_training_status(
    task_id: str,
    service: TrainingService = Depends(get_training_service)
) -> TrainingStatusResponse:
    """
    Get the current status and progress of a training task.
    """
    try:
        status = await service.get_training_status(task_id)
        
        current_metrics = None
        if status.get("current_metrics"):
            current_metrics = CurrentMetrics(**status["current_metrics"])
        
        return TrainingStatusResponse(
            success=status["success"],
            task_id=status["task_id"],
            status=status["status"],
            progress=status["progress"],
            current_epoch=status.get("current_epoch"),
            total_epochs=status.get("total_epochs"),
            symbol=status["symbol"],
            timeframe=status["timeframe"],
            started_at=status["started_at"],
            estimated_completion=status.get("estimated_completion"),
            current_metrics=current_metrics,
            error=status.get("error")
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get training status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get training status")


@router.get("/{task_id}/performance", response_model=PerformanceResponse)
async def get_model_performance(
    task_id: str,
    service: TrainingService = Depends(get_training_service)
) -> PerformanceResponse:
    """
    Get detailed performance metrics for a completed training session.
    """
    try:
        performance = await service.get_model_performance(task_id)
        
        training_metrics = None
        if performance.get("training_metrics"):
            training_metrics = TrainingMetrics(**performance["training_metrics"])
        
        test_metrics = None
        if performance.get("test_metrics"):
            test_metrics = TestMetrics(**performance["test_metrics"])
            
        model_info = None
        if performance.get("model_info"):
            model_info = ModelInfo(**performance["model_info"])
        
        return PerformanceResponse(
            success=performance["success"],
            task_id=performance["task_id"],
            status=performance["status"],
            training_metrics=training_metrics,
            test_metrics=test_metrics,
            model_info=model_info
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get model performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get model performance")