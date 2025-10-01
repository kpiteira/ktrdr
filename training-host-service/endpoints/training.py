"""
Training endpoints for Training Host Service

Provides GPU-accelerated training functionality.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import existing ktrdr modules
from ktrdr.logging import get_logger

# Import training service and health utilities
from services.training_service import get_training_service

from .health import get_gpu_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/training", tags=["training"])


def get_service():
    """Get the training service instance."""
    return get_training_service()


# Request/Response Models


class TrainingStartRequest(BaseModel):
    """Request to start a training session."""

    session_id: Optional[str] = Field(default=None, description="Optional session ID")
    model_configuration: dict[str, Any] = Field(description="Model configuration")
    training_configuration: dict[str, Any] = Field(description="Training configuration")
    data_configuration: dict[str, Any] = Field(description="Data configuration")
    gpu_configuration: Optional[dict[str, Any]] = Field(
        default=None, description="GPU-specific configuration"
    )


class TrainingStopRequest(BaseModel):
    """Request to stop a training session."""

    session_id: str = Field(description="Session ID to stop")
    save_checkpoint: bool = Field(
        default=True, description="Whether to save final checkpoint"
    )


class TrainingStatusResponse(BaseModel):
    """Training session status response."""

    session_id: str
    status: str  # "running", "completed", "failed", "stopped"
    progress: dict[str, Any]
    metrics: dict[str, Any]
    gpu_usage: dict[str, Any]
    start_time: str
    last_updated: str
    error: Optional[str] = None


class TrainingStartResponse(BaseModel):
    """Response to training start request."""

    session_id: str
    status: str
    message: str
    gpu_allocated: bool
    estimated_duration_minutes: Optional[float] = None


class EvaluationRequest(BaseModel):
    """Request to evaluate a model."""

    model_path: str = Field(description="Path to model file")
    data_config: dict[str, Any] = Field(description="Evaluation data configuration")
    metrics: list[str] = Field(
        default=["accuracy", "loss"], description="Metrics to compute"
    )


class EvaluationResponse(BaseModel):
    """Model evaluation response."""

    evaluation_id: str
    results: dict[str, float]
    gpu_used: bool
    evaluation_time_seconds: float
    timestamp: str


# Endpoints


@router.post("/start", response_model=TrainingStartResponse)
async def start_training(request: TrainingStartRequest):
    """
    Start a new training session with GPU acceleration.

    Creates a new training session, allocates GPU resources if available,
    and begins training with the provided configuration.
    """
    try:
        service = get_service()

        # Debug: Log what we receive
        logger.info(f"Received training_configuration: {request.training_configuration}")

        # Prepare configuration for training service
        config = {
            "model_config": request.model_configuration,
            "training_config": request.training_configuration,
            "data_config": request.data_configuration,
            "gpu_config": request.gpu_configuration or {},
        }

        # Create training session
        session_id = await service.create_session(config, request.session_id)

        # Get session status to determine GPU allocation
        status = service.get_session_status(session_id)
        gpu_allocated = status["resource_usage"].get("gpu_allocated", False)

        logger.info(f"Training session {session_id} started successfully")

        return TrainingStartResponse(
            session_id=session_id,
            status="started",
            message=f"Training session {session_id} started successfully",
            gpu_allocated=gpu_allocated,
            estimated_duration_minutes=request.training_configuration.get(
                "estimated_duration_minutes"
            ),
        )

    except Exception as e:
        logger.error(f"Failed to start training session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start training: {str(e)}"
        ) from e


@router.post("/stop")
async def stop_training(request: TrainingStopRequest):
    """
    Stop a running training session.

    Gracefully stops the training session, optionally saves a checkpoint,
    and releases GPU resources.
    """
    try:
        service = get_service()

        # Stop the training session
        await service.stop_session(request.session_id, request.save_checkpoint)

        logger.info(f"Training session {request.session_id} stopped successfully")

        return {
            "session_id": request.session_id,
            "status": "stopped",
            "message": f"Training session {request.session_id} stopped successfully",
            "checkpoint_saved": request.save_checkpoint,
        }

    except Exception as e:
        logger.error(f"Failed to stop training session {request.session_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to stop training: {str(e)}"
        ) from e


@router.get("/status/{session_id}", response_model=TrainingStatusResponse)
async def get_training_status(session_id: str):
    """
    Get the status of a training session.

    Returns detailed information about the training progress,
    metrics, and resource usage.
    """
    try:
        service = get_service()

        # Get session status from service
        status_info = service.get_session_status(session_id)

        return TrainingStatusResponse(
            session_id=session_id,
            status=status_info["status"],
            progress=status_info["progress"],
            metrics=status_info["metrics"]["current"],
            gpu_usage=status_info["resource_usage"],
            start_time=status_info["start_time"],
            last_updated=status_info["last_updated"],
            error=status_info.get("error"),
        )

    except Exception as e:
        logger.error(f"Failed to get status for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get training status: {str(e)}"
        ) from e


@router.get("/sessions")
async def list_training_sessions():
    """
    List all training sessions.

    Returns a summary of all active and completed training sessions.
    """
    try:
        service = get_service()
        sessions = service.list_sessions()

        return {
            "total_sessions": len(sessions),
            "sessions": sessions,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to list training sessions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {str(e)}"
        ) from e


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_model(request: EvaluationRequest):
    """
    Evaluate a trained model with GPU acceleration.

    Loads a model and evaluates it on the provided dataset,
    returning performance metrics.
    """
    try:
        evaluation_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        # Check GPU availability
        gpu_manager = await get_gpu_manager()
        gpu_used = gpu_manager is not None and gpu_manager.enabled

        # TODO: Implement actual model evaluation logic
        # For now, return mock results
        results = {"accuracy": 0.85, "loss": 0.23, "f1_score": 0.82}

        end_time = datetime.utcnow()
        evaluation_time = (end_time - start_time).total_seconds()

        logger.info(f"Model evaluation {evaluation_id} completed successfully")

        return EvaluationResponse(
            evaluation_id=evaluation_id,
            results=results,
            gpu_used=gpu_used,
            evaluation_time_seconds=evaluation_time,
            timestamp=end_time.isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to evaluate model: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Model evaluation failed: {str(e)}"
        ) from e


@router.delete("/sessions/{session_id}")
async def cleanup_session(session_id: str):
    """
    Clean up a completed or failed training session.

    Removes session data and releases any remaining resources.
    """
    try:
        service = get_service()

        # Cleanup the session
        await service.cleanup_session(session_id)

        logger.info(f"Training session {session_id} cleaned up successfully")

        return {
            "session_id": session_id,
            "status": "cleaned_up",
            "message": f"Session {session_id} cleaned up successfully",
        }

    except Exception as e:
        logger.error(f"Failed to cleanup session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup session: {str(e)}"
        ) from e
