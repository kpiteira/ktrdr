"""
Training endpoints for the KTRDR API.

This module implements the API endpoints for neural network model training,
using the existing CLI training functionality as the foundation.

HTTP Status Code Mapping
------------------------
The endpoints in this module follow these status code conventions:

200 OK:
    - Training job successfully started
    - Training status successfully retrieved
    - Training results successfully retrieved

400 Bad Request (ConfigurationError):
    - Strategy configuration is invalid (validation errors)
    - Strategy file has incorrect format
    - Feature IDs missing or invalid
    - Fuzzy sets configuration errors
    Fix: Correct the strategy YAML configuration file

422 Unprocessable Entity (ValidationError):
    - Invalid request parameters (invalid strategy name, bad date format)
    - Training configuration parameters out of valid range
    - Request body doesn't match expected schema
    Fix: Correct the API request body/parameters

404 Not Found:
    - Strategy file doesn't exist
    - Training job ID not found
    Fix: Check strategy name or training job ID

503 Service Unavailable (DataError):
    - Data source unavailable (IB Gateway not connected)
    - Insufficient historical data available
    - Data loading/validation failures
    Fix: Check data source connection, verify symbol/timeframe availability

500 Internal Server Error:
    - Model training crashes or fails
    - GPU/memory errors during training
    - Unexpected Python exceptions
    Fix: Check server logs for stack trace, verify GPU availability

Error Response Format
--------------------
All errors return JSON with this structure:
    {
        "message": "Human-readable error description",
        "error_code": "CATEGORY-ErrorName",
        "context": {"strategy_name": "...", "symbol": "...", ...},
        "details": {...},
        "suggestion": "How to fix this error"
    }

Training Flow
-------------
1. POST /trainings/start → Returns operation_id
2. GET /operations/{operation_id} → Check status
3. Results available in response when status = "completed"
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.api.endpoints.workers import get_worker_registry
from ktrdr.api.services.training_service import TrainingService
from ktrdr.errors import (
    ConfigurationError,
    DataError,
    ValidationError,
    WorkerUnavailableError,
)

logger = get_logger(__name__)

# Create router for training endpoints
router = APIRouter(prefix="/trainings")


# Request/Response models
class TrainingConfig(BaseModel):
    """Training configuration parameters."""

    model_type: str = "mlp"
    hidden_layers: list[int] = [64, 32, 16]
    epochs: int = 100
    learning_rate: float = 0.001
    batch_size: int = 32
    validation_split: float = 0.2
    early_stopping: dict[str, Any] = {"patience": 10, "monitor": "val_accuracy"}
    optimizer: str = "adam"
    dropout_rate: float = 0.2


class TrainingRequest(BaseModel):
    """Request model for starting neural network training."""

    symbols: Optional[list[str]] = None
    timeframes: Optional[list[str]] = None
    strategy_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    task_id: Optional[str] = None
    detailed_analytics: bool = False

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate symbols list if provided (non-empty, valid symbols)."""
        if v is None:
            return None

        if len(v) == 0:
            raise ValueError(
                "At least one symbol must be specified when symbols are provided"
            )

        valid_symbols = []
        for symbol in v:
            if not symbol or not symbol.strip():
                raise ValueError("Symbol cannot be empty")
            valid_symbols.append(symbol.strip())

        return valid_symbols

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate timeframes list if provided (non-empty, valid timeframes)."""
        if v is None:
            return None

        if len(v) == 0:
            raise ValueError(
                "At least one timeframe must be specified when timeframes are provided"
            )

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
    symbols: list[str]
    timeframes: list[str]
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
    symbols: list[str]
    timeframes: list[str]
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
        # Inject WorkerRegistry for distributed worker selection
        worker_registry = get_worker_registry()
        _training_service = TrainingService(worker_registry=worker_registry)
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

    except WorkerUnavailableError as e:
        # Return 503 with diagnostic context for worker unavailability
        logger.warning(f"No training workers available: {e.details}")
        raise HTTPException(status_code=503, detail=e.to_response_dict()) from e
    except ConfigurationError as e:
        # Log error with full context before responding
        logger.error(f"Configuration error: {e.format_user_message()}")
        # Return structured error response with all details
        raise HTTPException(status_code=400, detail=e.to_dict()) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DataError as e:
        # DataError indicates data unavailability - return 503
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        # Validation errors should return 422
        logger.error(f"Invalid parameter in training request: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start training") from e


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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except DataError as e:
        # DataError indicates data unavailability - return 503
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        # Validation errors should return 422
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get model performance: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to get model performance"
        ) from e
