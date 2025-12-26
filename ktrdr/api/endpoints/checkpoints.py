"""
Checkpoint management endpoints for the KTRDR API.

This module provides endpoints for managing training checkpoints:
- List checkpoints
- Get checkpoint details
- Delete checkpoints
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ktrdr import get_logger
from ktrdr.api.database import get_session_factory
from ktrdr.checkpoint.checkpoint_service import CheckpointService
from ktrdr.config.settings import get_checkpoint_settings
from ktrdr.errors import DataError

# Setup module-level logger
logger = get_logger(__name__)

# Create router for checkpoint endpoints
router = APIRouter()


# ============================================================================
# Pydantic Response Models
# ============================================================================


class CheckpointSummaryResponse(BaseModel):
    """Response model for checkpoint summary in list."""

    operation_id: str = Field(..., description="Operation ID for this checkpoint")
    checkpoint_type: str = Field(
        ...,
        description="Type of checkpoint (periodic, cancellation, failure, shutdown)",
    )
    created_at: datetime = Field(..., description="When the checkpoint was created")
    state_summary: dict[str, Any] = Field(
        default_factory=dict, description="Key fields from checkpoint state"
    )
    artifacts_size_bytes: Optional[int] = Field(
        None, description="Total size of artifacts in bytes"
    )


class CheckpointListResponse(BaseModel):
    """Response model for listing checkpoints."""

    success: bool = Field(True, description="Whether the request was successful")
    data: list[CheckpointSummaryResponse] = Field(
        default_factory=list, description="List of checkpoint summaries"
    )
    total_count: int = Field(0, description="Total number of checkpoints")


class CheckpointDetailResponse(BaseModel):
    """Response model for checkpoint details (without artifact bytes)."""

    operation_id: str = Field(..., description="Operation ID for this checkpoint")
    checkpoint_type: str = Field(
        ...,
        description="Type of checkpoint (periodic, cancellation, failure, shutdown)",
    )
    created_at: datetime = Field(..., description="When the checkpoint was created")
    state: dict[str, Any] = Field(
        default_factory=dict, description="Full checkpoint state"
    )
    artifacts_path: Optional[str] = Field(
        None, description="Path to artifacts on filesystem"
    )


class CheckpointResponse(BaseModel):
    """Response model for single checkpoint."""

    success: bool = Field(True, description="Whether the request was successful")
    data: CheckpointDetailResponse = Field(..., description="Checkpoint details")


class DeleteCheckpointResponse(BaseModel):
    """Response model for checkpoint deletion."""

    success: bool = Field(True, description="Whether the request was successful")
    message: str = Field(..., description="Result message")


# ============================================================================
# Dependencies
# ============================================================================

# Singleton instance of CheckpointService
_checkpoint_service: Optional[CheckpointService] = None


def get_checkpoint_service() -> CheckpointService:
    """
    Dependency for providing the checkpoint service.

    Returns:
        CheckpointService: Initialized checkpoint service instance.
    """
    global _checkpoint_service
    if _checkpoint_service is None:
        session_factory = get_session_factory()
        checkpoint_settings = get_checkpoint_settings()
        _checkpoint_service = CheckpointService(
            session_factory=session_factory,
            artifacts_dir=checkpoint_settings.dir,
        )
    return _checkpoint_service


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/checkpoints",
    response_model=CheckpointListResponse,
    tags=["Checkpoints"],
    summary="List checkpoints",
    description="""
    Get a list of all checkpoints with optional filtering.

    **Features:**
    - Filter by age (older_than_days)
    - Returns checkpoint summaries (not full state)
    - Ordered by creation date (newest first)

    **Perfect for:** Admin dashboards, cleanup scripts, monitoring
    """,
)
async def list_checkpoints(
    older_than_days: Optional[int] = Query(
        None, description="Filter to checkpoints older than this many days"
    ),
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> CheckpointListResponse:
    """
    List all checkpoints with optional filtering.

    Returns a list of checkpoint summaries, ordered by creation date.

    Args:
        older_than_days: If set, only return checkpoints older than this

    Returns:
        CheckpointListResponse: List of checkpoint summaries

    Example:
        GET /api/v1/checkpoints
        GET /api/v1/checkpoints?older_than_days=7
    """
    try:
        logger.info(f"Listing checkpoints: older_than_days={older_than_days}")

        # Get checkpoints from service
        checkpoints = await checkpoint_service.list_checkpoints(
            older_than_days=older_than_days
        )

        # Convert to response format
        checkpoint_summaries = [
            CheckpointSummaryResponse(
                operation_id=cp.operation_id,
                checkpoint_type=cp.checkpoint_type,
                created_at=cp.created_at,
                state_summary=cp.state_summary,
                artifacts_size_bytes=cp.artifacts_size_bytes,
            )
            for cp in checkpoints
        ]

        logger.info(f"Retrieved {len(checkpoints)} checkpoints")
        return CheckpointListResponse(
            success=True,
            data=checkpoint_summaries,
            total_count=len(checkpoints),
        )

    except Exception as e:
        logger.error(f"Error listing checkpoints: {str(e)}")
        raise DataError(
            message="Failed to list checkpoints",
            error_code="CHECKPOINTS-ListError",
            details={"error": str(e)},
        ) from e


@router.get(
    "/checkpoints/{operation_id}",
    response_model=CheckpointResponse,
    tags=["Checkpoints"],
    summary="Get checkpoint details",
    description="""
    Get detailed information about a specific checkpoint.

    **Features:**
    - Full checkpoint state (epoch, losses, history, etc.)
    - Artifacts path (bytes not loaded for performance)
    - Useful for debugging and resume decisions

    **Perfect for:** Resume logic, debugging, analytics
    """,
)
async def get_checkpoint(
    operation_id: str = Path(..., description="Operation ID of the checkpoint"),
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> CheckpointResponse:
    """
    Get detailed information about a specific checkpoint.

    Returns the full checkpoint state (but not artifact bytes for performance).

    Args:
        operation_id: Unique identifier for the operation

    Returns:
        CheckpointResponse: Checkpoint details

    Raises:
        404: Checkpoint not found

    Example:
        GET /api/v1/checkpoints/op_training_123
    """
    try:
        logger.info(f"Getting checkpoint for operation: {operation_id}")

        # Load checkpoint (without artifacts bytes for performance)
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=False
        )

        if checkpoint is None:
            logger.warning(f"Checkpoint not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint not found: {operation_id}",
            )

        logger.info(f"Retrieved checkpoint for operation: {operation_id}")
        return CheckpointResponse(
            success=True,
            data=CheckpointDetailResponse(
                operation_id=checkpoint.operation_id,
                checkpoint_type=checkpoint.checkpoint_type,
                created_at=checkpoint.created_at,
                state=checkpoint.state,
                artifacts_path=checkpoint.artifacts_path,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting checkpoint: {str(e)}")
        raise DataError(
            message=f"Failed to get checkpoint for {operation_id}",
            error_code="CHECKPOINTS-GetError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.delete(
    "/checkpoints/{operation_id}",
    response_model=DeleteCheckpointResponse,
    tags=["Checkpoints"],
    summary="Delete checkpoint",
    description="""
    Delete a checkpoint (both DB record and filesystem artifacts).

    **Features:**
    - Removes checkpoint from database
    - Removes artifacts from filesystem
    - Idempotent (safe to call multiple times)

    **Perfect for:** Cleanup, space management, manual intervention
    """,
)
async def delete_checkpoint(
    operation_id: str = Path(
        ..., description="Operation ID of the checkpoint to delete"
    ),
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> DeleteCheckpointResponse:
    """
    Delete a checkpoint.

    Removes both the database record and any filesystem artifacts.

    Args:
        operation_id: Unique identifier for the operation

    Returns:
        DeleteCheckpointResponse: Deletion result

    Raises:
        404: Checkpoint not found

    Example:
        DELETE /api/v1/checkpoints/op_training_123
    """
    try:
        logger.info(f"Deleting checkpoint for operation: {operation_id}")

        # Delete checkpoint
        deleted = await checkpoint_service.delete_checkpoint(operation_id)

        if not deleted:
            logger.warning(f"Checkpoint not found for deletion: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint not found: {operation_id}",
            )

        logger.info(f"Deleted checkpoint for operation: {operation_id}")
        return DeleteCheckpointResponse(
            success=True,
            message="Checkpoint deleted",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting checkpoint: {str(e)}")
        raise DataError(
            message=f"Failed to delete checkpoint for {operation_id}",
            error_code="CHECKPOINTS-DeleteError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e
