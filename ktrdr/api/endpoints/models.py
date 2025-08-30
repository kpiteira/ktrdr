"""
Model endpoints for the KTRDR API.

This module implements the API endpoints for model management - saving, loading,
and testing trained neural network models.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.api.services.training_service import TrainingService
from ktrdr.errors import ValidationError

logger = get_logger(__name__)

# Create router for model endpoints
router = APIRouter(prefix="/models")


# Request/Response models
class SaveModelRequest(BaseModel):
    """Request model for saving a trained model."""

    task_id: str
    model_name: str
    description: str = ""

    @field_validator("task_id", "model_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class SaveModelResponse(BaseModel):
    """Response model for model save."""

    success: bool
    model_id: str
    model_name: str
    model_path: str
    task_id: str
    saved_at: str
    model_size_mb: Optional[float] = None


class LoadModelResponse(BaseModel):
    """Response model for model load."""

    success: bool
    model_name: str
    model_loaded: bool
    model_info: dict[str, Any]


class PredictionRequest(BaseModel):
    """Request model for model prediction."""

    model_name: str
    symbol: str
    timeframe: str = "1h"
    test_date: Optional[str] = None

    @field_validator("model_name", "symbol", "timeframe")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class FuzzyOutputs(BaseModel):
    """Fuzzy logic outputs."""

    bullish: float
    bearish: float
    neutral: float


class Prediction(BaseModel):
    """Model prediction."""

    signal: str  # "buy", "sell", "hold"
    confidence: float
    signal_strength: float
    fuzzy_outputs: FuzzyOutputs


class PredictionResponse(BaseModel):
    """Response model for model prediction."""

    success: bool
    model_name: str
    symbol: str
    test_date: str
    prediction: Prediction
    input_features: dict[str, float]


class ModelSummary(BaseModel):
    """Model summary information."""

    model_id: str
    model_name: str
    symbol: str
    timeframe: str
    created_at: str
    training_accuracy: Optional[float] = None
    test_accuracy: Optional[float] = None
    description: str = ""


class ModelsListResponse(BaseModel):
    """Response model for models list."""

    success: bool
    models: list[ModelSummary]


# Dependency for training service (contains model management)
async def get_training_service() -> TrainingService:
    """Get training service instance."""
    # Import here to avoid circular imports
    from ktrdr.api.endpoints.training import get_training_service as _get_service

    return await _get_service()


@router.post("/save", response_model=SaveModelResponse)
async def save_trained_model(
    request: SaveModelRequest, service: TrainingService = Depends(get_training_service)
) -> SaveModelResponse:
    """
    Save a trained neural network model for later use.
    """
    try:
        result = await service.save_trained_model(
            task_id=request.task_id,
            model_name=request.model_name,
            description=request.description,
        )

        return SaveModelResponse(
            success=result["success"],
            model_id=result["model_id"],
            model_name=result["model_name"],
            model_path=result["model_path"],
            task_id=result["task_id"],
            saved_at=result["saved_at"],
            model_size_mb=result.get("model_size_mb"),
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to save model: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save model: {str(e)}"
        ) from e


@router.post("/{model_name}/load", response_model=LoadModelResponse)
async def load_trained_model(
    model_name: str, service: TrainingService = Depends(get_training_service)
) -> LoadModelResponse:
    """
    Load a previously saved neural network model into memory for prediction.
    """
    try:
        result = await service.load_trained_model(model_name)

        return LoadModelResponse(
            success=result["success"],
            model_name=result["model_name"],
            model_loaded=result["model_loaded"],
            model_info=result["model_info"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load model: {str(e)}"
        ) from e


@router.post("/predict", response_model=PredictionResponse)
async def test_model_prediction(
    request: PredictionRequest, service: TrainingService = Depends(get_training_service)
) -> PredictionResponse:
    """
    Test a loaded model's prediction capability on specific data.
    """
    try:
        result = await service.test_model_prediction(
            model_name=request.model_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            test_date=request.test_date,
        )

        return PredictionResponse(
            success=result["success"],
            model_name=result["model_name"],
            symbol=result["symbol"],
            test_date=result["test_date"],
            prediction=Prediction(
                signal=result["prediction"]["signal"],
                confidence=result["prediction"]["confidence"],
                signal_strength=result["prediction"]["signal_strength"],
                fuzzy_outputs=FuzzyOutputs(**result["prediction"]["fuzzy_outputs"]),
            ),
            input_features=result["input_features"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to make prediction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to make prediction: {str(e)}"
        ) from e


@router.get("", response_model=ModelsListResponse)
async def list_trained_models(
    service: TrainingService = Depends(get_training_service),
) -> ModelsListResponse:
    """
    List all available trained neural network models.
    """
    try:
        result = await service.list_trained_models()

        model_summaries = []
        for model in result["models"]:
            summary = ModelSummary(
                model_id=model["model_id"],
                model_name=model["model_name"],
                symbol=model["symbol"],
                timeframe=model["timeframe"],
                created_at=model["created_at"],
                training_accuracy=model.get("training_accuracy"),
                test_accuracy=model.get("test_accuracy"),
                description=model["description"],
            )
            model_summaries.append(summary)

        return ModelsListResponse(success=result["success"], models=model_summaries)

    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list models: {str(e)}"
        ) from e
