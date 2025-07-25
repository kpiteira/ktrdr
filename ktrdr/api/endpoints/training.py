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
from ktrdr.api.services.operations_service import get_operations_service, OperationsService
from ktrdr.errors import ValidationError, DataError

logger = get_logger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/trainings")


# Request/Response models
class TrainingConfig(BaseModel):
    """Training configuration parameters."""

    model_type: str = "mlp"
    hidden_layers: List[int] = [64, 32, 16]
    epochs: int = 100
    learning_rate: float = 0.001
    batch_size: int = 32
    validation_split: float = 0.2
    early_stopping: Dict[str, Any] = {"patience": 10, "monitor": "val_accuracy"}
    optimizer: str = "adam"
    dropout_rate: float = 0.2


class TrainingRequest(BaseModel):
    """Request model for starting neural network training."""

    symbols: List[str]
    timeframes: List[str]
    strategy_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    task_id: Optional[str] = None
    detailed_analytics: bool = False

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        """Validate that symbols list is not empty and contains valid symbols."""
        if not v or len(v) == 0:
            raise ValueError("At least one symbol must be specified")
        
        valid_symbols = []
        for symbol in v:
            if not symbol or not symbol.strip():
                raise ValueError("Symbol cannot be empty")
            valid_symbols.append(symbol.strip())
        
        return valid_symbols
    
    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, v: List[str]) -> List[str]:
        """Validate that timeframes list is not empty and contains valid timeframes."""
        if not v or len(v) == 0:
            raise ValueError("At least one timeframe must be specified")
        
        valid_timeframes = []
        for timeframe in v:
            if not timeframe or not timeframe.strip():
                raise ValueError("Timeframe cannot be empty")
            valid_timeframes.append(timeframe.strip())
        
        return valid_timeframes




class TrainingStartResponse(BaseModel):
    """Response model for training start."""

    success: bool
    task_id: str
    status: str
    message: str
    symbols: List[str]
    timeframes: List[str]
    strategy_name: str
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
    symbols: List[str]
    timeframes: List[str]
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

    model_size_bytes: Optional[int] = None
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
        # Pass the global OperationsService singleton to avoid creating separate instances
        operations_service = get_operations_service()
        _training_service = TrainingService(operations_service=operations_service)
    return _training_service


@router.post("/start", response_model=TrainingStartResponse)
async def start_training(
    request: TrainingRequest, service: TrainingService = Depends(get_training_service)
) -> TrainingStartResponse:
    """
    Start neural network model training.

    This endpoint starts a background training task and returns immediately
    with a task ID for tracking progress.
    """
    try:
        result = await service.start_training(
            symbols=request.symbols,
            timeframes=request.timeframes,
            strategy_name=request.strategy_name,
            start_date=request.start_date,
            end_date=request.end_date,
            task_id=request.task_id,
            detailed_analytics=request.detailed_analytics,
        )

        return TrainingStartResponse(
            success=result["success"],
            task_id=result["task_id"],
            status=result["status"],
            message=result["message"],
            symbols=result["symbols"],
            timeframes=result["timeframes"],
            strategy_name=result["strategy_name"],
            estimated_duration_minutes=result.get("estimated_duration_minutes"),
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start training")




@router.get("/{task_id}/performance", response_model=PerformanceResponse)
async def get_model_performance(
    task_id: str, service: TrainingService = Depends(get_training_service)
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
            model_info=model_info,
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get model performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get model performance")
