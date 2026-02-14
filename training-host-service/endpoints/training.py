"""
Training endpoints for Training Host Service

Provides GPU-accelerated training functionality.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import existing ktrdr modules
from ktrdr.logging import get_logger
from ktrdr.workers.base import WorkerOperationMixin

# Import training service
from services.training_service import get_training_service

logger = get_logger(__name__)
router = APIRouter(prefix="/training", tags=["training"])


def get_service():
    """Get the training service instance."""
    return get_training_service()


# Request/Response Models


class TrainingStartRequest(WorkerOperationMixin):
    """Request to start a training session."""

    # task_id inherited from WorkerOperationMixin
    session_id: Optional[str] = Field(default=None, description="Optional session ID (legacy)")
    strategy_yaml: str = Field(description="Strategy configuration as YAML string")
    # Runtime overrides (optional)
    symbols: Optional[list[str]] = Field(
        default=None, description="Override symbols from strategy"
    )
    timeframes: Optional[list[str]] = Field(
        default=None, description="Override timeframes from strategy"
    )
    start_date: Optional[str] = Field(
        default=None, description="Override start date (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        default=None, description="Override end date (YYYY-MM-DD)"
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
    operation_id: str  # Backend expects this field (same as session_id)
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

        # Prepare configuration for training service
        config = {
            "strategy_yaml": request.strategy_yaml,
            # Runtime overrides (optional)
            "symbols": request.symbols,
            "timeframes": request.timeframes,
            "start_date": request.start_date,
            "end_date": request.end_date,
        }

        # Use backend's task_id if provided, otherwise session_id
        # This aligns with WorkerAPIBase pattern (accept backend's operation_id)
        operation_id = request.task_id or request.session_id

        # Create training session
        session_id = await service.create_session(config, operation_id)

        # Get session status to determine GPU allocation
        status = service.get_session_status(session_id)
        gpu_allocated = status["resource_usage"].get("gpu_allocated", False)

        logger.info(f"Training session {session_id} started successfully")

        return TrainingStartResponse(
            session_id=session_id,
            operation_id=session_id,  # Backend expects operation_id field
            status="started",
            message=f"Training session {session_id} started successfully",
            gpu_allocated=gpu_allocated,
            estimated_duration_minutes=None,  # Can be computed from strategy YAML if needed
        )

    except Exception as e:
        logger.error(f"Failed to start training session: {str(e)}", exc_info=True)
        # Log current session state to help diagnose issues
        service = get_service()
        active_sessions = [
            (sid, s.status) for sid, s in service.sessions.items()
            if s.status in ["running", "initializing"]
        ]
        logger.error(f"Active sessions at failure: {active_sessions}")

        # Return appropriate HTTP status code based on error type
        if "Maximum concurrent sessions" in str(e):
            # 503 Service Unavailable - temporary condition, client should retry later
            raise HTTPException(
                status_code=503,
                detail=f"Service temporarily unavailable: {str(e)}. Please try again in a moment."
            ) from e
        elif "already exists" in str(e):
            # 409 Conflict - session ID conflict
            raise HTTPException(
                status_code=409,
                detail=f"Session conflict: {str(e)}"
            ) from e
        elif "password authentication failed for user" in str(e).lower():
            # Clear operational hint for common host-service startup misconfiguration.
            raise HTTPException(
                status_code=500,
                detail=(
                    "Training host service database authentication failed. "
                    "This usually means the service was started without the correct "
                    "DB secret. Start it with "
                    "`uv run kinfra local-prod start-training-host` so "
                    "`KTRDR_DB_PASSWORD` is loaded from 1Password."
                ),
            ) from e
        else:
            # 500 Internal Server Error - unexpected errors
            raise HTTPException(
                status_code=500, detail=f"Failed to start training: {str(e)}"
            ) from e


@router.get("/result/{session_id}")
async def get_training_result(session_id: str):
    """
    Get the final training result.

    Returns the complete training result in TrainingPipeline format.
    Only valid when training status is "completed".

    TASK 3.3: This endpoint returns the harmonized TrainingPipeline result format,
    eliminating the need for result_aggregator transformation.

    Returns:
        dict: Training result with keys: model_path, training_metrics, test_metrics,
              artifacts, model_info, data_summary, resource_usage, session_id, etc.

    Raises:
        404: Session not found
        400: Training not completed yet
    """
    try:
        service = get_service()

        session = service.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if session.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Training not completed yet (status: {session.status})"
            )

        if not session.training_result:
            raise HTTPException(
                status_code=500,
                detail="Training completed but result not available"
            )

        # Return the harmonized TrainingPipeline result format
        result = {
            **session.training_result,
            "session_id": session_id,
            "status": session.status,
            "start_time": session.start_time.isoformat(),
            "last_updated": session.last_updated.isoformat(),
        }

        # TASK 3.3: Verification logging
        logger.info("=" * 80)
        logger.info(f"RESULT ENDPOINT RETURNING COMPLETED RESULT (session {session_id})")
        logger.info(f"  Keys: {list(result.keys())}")
        logger.info(f"  model_path: {result.get('model_path')}")
        logger.info(f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}")
        logger.info(f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}")
        logger.info("=" * 80)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get result for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get training result: {str(e)}"
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
            "timestamp": datetime.now(UTC).isoformat(),
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
        start_time = datetime.now(UTC)

        # Note: GPU availability is managed by the worker via WorkerAPIBase
        # Worker self-registers with GPU capabilities to backend
        gpu_used = True  # Assume GPU if worker has it

        # TODO: Implement actual model evaluation logic
        # For now, return mock results
        results = {"accuracy": 0.85, "loss": 0.23, "f1_score": 0.82}

        end_time = datetime.now(UTC)
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
