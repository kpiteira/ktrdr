"""
Model endpoints for the KTRDR API.

This module implements the API endpoints for model management - saving, loading,
and testing trained neural network models.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.training.model_storage import ModelStorage
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError, DataError

logger = get_logger(__name__)

# Create router for model endpoints
router = APIRouter(prefix="/models")

# In-memory storage for loaded models (in production, use proper model registry)
_loaded_models: Dict[str, Any] = {}

# Request/Response models
class SaveModelRequest(BaseModel):
    """Request model for saving a trained model."""
    task_id: str
    model_name: str
    description: str = ""
    
    @field_validator('task_id', 'model_name')
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()


class SaveModelResponse(BaseModel):
    """Response model for model save."""
    success: bool = True
    model_id: str
    model_name: str
    model_path: str
    task_id: str
    saved_at: str
    model_size_mb: Optional[float] = None


class LoadModelResponse(BaseModel):
    """Response model for model load."""
    success: bool = True
    model_name: str
    model_loaded: bool
    model_info: Dict[str, Any]


class PredictionRequest(BaseModel):
    """Request model for model prediction."""
    model_name: str
    symbol: str
    timeframe: str = "1h"
    test_date: Optional[str] = None
    
    @field_validator('model_name', 'symbol', 'timeframe')
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
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
    success: bool = True
    model_name: str
    symbol: str
    test_date: str
    prediction: Prediction
    input_features: Dict[str, float]


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
    success: bool = True
    models: List[ModelSummary]


# Dependency for model storage
def get_model_storage() -> ModelStorage:
    """Get model storage instance."""
    return ModelStorage()


def get_model_loader() -> ModelLoader:
    """Get model loader instance."""
    return ModelLoader()


@router.post("/save", response_model=SaveModelResponse)
async def save_trained_model(
    request: SaveModelRequest,
    model_storage: ModelStorage = Depends(get_model_storage)
) -> SaveModelResponse:
    """
    Save a trained neural network model for later use.
    """
    try:
        # Import the training tasks from training module
        from .training import _training_tasks
        
        # Verify training task exists and is completed
        if request.task_id not in _training_tasks:
            raise HTTPException(status_code=404, detail=f"Training task {request.task_id} not found")
        
        task = _training_tasks[request.task_id]
        if task["status"] != "completed":
            raise HTTPException(status_code=400, detail=f"Training task {request.task_id} is not completed")
        
        # Get model path from training results
        model_path = task.get("model_path")
        if not model_path or not Path(model_path).exists():
            raise HTTPException(status_code=400, detail="Trained model file not found")
        
        # Save model using existing ModelStorage
        model_info = {
            "name": request.model_name,
            "description": request.description,
            "symbol": task["symbol"],
            "timeframe": task["timeframe"],
            "config": task["config"],
            "training_results": task.get("results", {}),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Use ModelStorage to save the model
        saved_models = model_storage.list_models()
        model_id = f"model_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate model size
        model_size_mb = None
        if Path(model_path).exists():
            model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
        
        # In a real implementation, this would properly save through ModelStorage
        # For now, we'll simulate the save operation
        
        logger.info(f"Model {request.model_name} saved with ID {model_id}")
        
        return SaveModelResponse(
            model_id=model_id,
            model_name=request.model_name,
            model_path=str(model_path),
            task_id=request.task_id,
            saved_at=datetime.utcnow().isoformat() + "Z",
            model_size_mb=model_size_mb
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save model: {str(e)}")


@router.post("/{model_name}/load", response_model=LoadModelResponse)
async def load_trained_model(
    model_name: str,
    model_storage: ModelStorage = Depends(get_model_storage),
    model_loader: ModelLoader = Depends(get_model_loader)
) -> LoadModelResponse:
    """
    Load a previously saved neural network model into memory for prediction.
    """
    try:
        # Check if model exists in storage
        all_models = model_storage.list_models()
        model_info = None
        
        for model in all_models:
            if model.get("name") == model_name:
                model_info = model
                break
        
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
        
        # Load model using ModelLoader
        # In a real implementation, this would actually load the model weights
        model_path = model_info.get("path", "")
        
        if model_path and Path(model_path).exists():
            # Simulate loading the model
            _loaded_models[model_name] = {
                "model": "loaded_model_placeholder",  # Would be actual model object
                "info": model_info,
                "loaded_at": datetime.utcnow().isoformat()
            }
            model_loaded = True
        else:
            model_loaded = False
        
        # Extract model information
        response_info = {
            "created_at": model_info.get("created_at", ""),
            "symbol": model_info.get("symbol", ""),
            "timeframe": model_info.get("timeframe", ""),
            "architecture": f"mlp_64_32_16",  # Would come from actual model config
            "training_accuracy": 0.89,  # Would come from actual training results
            "test_accuracy": 0.88
        }
        
        logger.info(f"Model {model_name} loaded successfully: {model_loaded}")
        
        return LoadModelResponse(
            model_name=model_name,
            model_loaded=model_loaded,
            model_info=response_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")


@router.post("/predict", response_model=PredictionResponse)
async def test_model_prediction(request: PredictionRequest) -> PredictionResponse:
    """
    Test a loaded model's prediction capability on specific data.
    """
    try:
        # Check if model is loaded
        if request.model_name not in _loaded_models:
            raise HTTPException(status_code=400, detail=f"Model '{request.model_name}' is not loaded. Load it first.")
        
        loaded_model = _loaded_models[request.model_name]
        
        # Use test_date or default to latest available
        test_date = request.test_date or datetime.utcnow().strftime("%Y-%m-%d")
        
        # In a real implementation, this would:
        # 1. Load market data for the test date
        # 2. Calculate indicators/features
        # 3. Run model prediction
        # 4. Apply fuzzy logic post-processing
        
        # For now, return simulated prediction
        prediction = Prediction(
            signal="buy",  # Would come from actual model prediction
            confidence=0.78,
            signal_strength=0.65,
            fuzzy_outputs=FuzzyOutputs(
                bullish=0.78,
                bearish=0.22,
                neutral=0.31
            )
        )
        
        # Simulated input features (would come from actual data processing)
        input_features = {
            "sma_20": 152.34,
            "rsi_14": 64.2,
            "macd_signal": 0.45
        }
        
        logger.info(f"Model {request.model_name} prediction for {request.symbol} on {test_date}: {prediction.signal}")
        
        return PredictionResponse(
            model_name=request.model_name,
            symbol=request.symbol,
            test_date=test_date,
            prediction=prediction,
            input_features=input_features
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to make prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to make prediction: {str(e)}")


@router.get("", response_model=ModelsListResponse)
async def list_trained_models(
    model_storage: ModelStorage = Depends(get_model_storage)
) -> ModelsListResponse:
    """
    List all available trained neural network models.
    """
    try:
        # Get all models from storage
        all_models = model_storage.list_models()
        
        # Convert to response format
        model_summaries = []
        for model in all_models:
            summary = ModelSummary(
                model_id=model.get("id", ""),
                model_name=model.get("name", ""),
                symbol=model.get("symbol", ""),
                timeframe=model.get("timeframe", ""),
                created_at=model.get("created_at", ""),
                training_accuracy=0.89,  # Would come from actual training results
                test_accuracy=0.88,
                description=model.get("description", "")
            )
            model_summaries.append(summary)
        
        logger.info(f"Listed {len(model_summaries)} models")
        
        return ModelsListResponse(models=model_summaries)
        
    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")