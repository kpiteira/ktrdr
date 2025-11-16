"""
Operations management endpoints for the KTRDR API.

This module provides endpoints for managing long-running operations:
- List operations
- Get operation status
- Cancel operations
- Monitor progress
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ktrdr import get_logger
from ktrdr.api.dependencies import get_operations_service
from ktrdr.api.models.operations import (
    CancelOperationRequest,
    OperationCancelResponse,
    OperationListResponse,
    OperationMetricsResponse,
    OperationResumeResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.errors import DataError
from ktrdr.logging.config import should_rate_limit_log

# Setup module-level logger
logger = get_logger(__name__)

# Create router for operations endpoints
router = APIRouter()


@router.get(
    "/operations",
    response_model=OperationListResponse,
    tags=["Operations"],
    summary="List operations",
    description="""
    Get a list of all operations with optional filtering.

    **Features:**
    - Filter by status (running, completed, failed, etc.)
    - Filter by operation type (data_load, training, etc.)
    - Pagination support
    - Sort by creation date or status

    **Perfect for:** CLI status commands, dashboards, monitoring
    """,
)
async def list_operations(
    status: Optional[OperationStatus] = Query(
        None, description="Filter by operation status"
    ),
    operation_type: Optional[OperationType] = Query(
        None, description="Filter by operation type"
    ),
    limit: int = Query(
        10, ge=1, le=1000, description="Maximum number of operations to return"
    ),
    offset: int = Query(0, ge=0, description="Number of operations to skip"),
    active_only: bool = Query(
        False, description="Show only active (running/pending) operations"
    ),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationListResponse:
    """
    List all operations with optional filtering.

    Returns a paginated list of operations, with support for filtering by
    status, type, and other criteria. Useful for monitoring and management.

    Args:
        status: Filter operations by status
        operation_type: Filter operations by type
        limit: Maximum number of operations to return
        offset: Number of operations to skip (for pagination)
        active_only: If True, only return running/pending operations

    Returns:
        OperationListResponse: Paginated list of operations

    Example:
        GET /api/v1/operations?status=running&limit=10
        GET /api/v1/operations?active_only=true
    """
    try:
        logger.info(
            f"Listing operations: status={status}, type={operation_type}, active_only={active_only}"
        )

        # Get operations from service
        (
            operations,
            total_count,
            active_count,
        ) = await operations_service.list_operations(
            status=status,
            operation_type=operation_type,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )

        # Convert to summary format
        operation_summaries = [
            OperationSummary(
                operation_id=op.operation_id,
                operation_type=op.operation_type,
                status=op.status,
                created_at=op.created_at,
                progress_percentage=op.progress.percentage,
                current_step=op.progress.current_step,
                symbol=op.metadata.symbol,
                duration_seconds=op.duration_seconds,
            )
            for op in operations
        ]

        logger.info(
            f"Retrieved {len(operations)} operations (total: {total_count}, active: {active_count})"
        )
        return OperationListResponse(
            success=True,
            data=operation_summaries,
            total_count=total_count,
            active_count=active_count,
        )

    except Exception as e:
        logger.error(f"Error listing operations: {str(e)}")
        raise DataError(
            message="Failed to list operations",
            error_code="OPERATIONS-ListError",
            details={"error": str(e)},
        ) from e


@router.get(
    "/operations/{operation_id}",
    response_model=OperationStatusResponse,
    tags=["Operations"],
    summary="Get operation status",
    description="""
    Get detailed status and progress information for a specific operation.

    **Features:**
    - Complete operation information including progress
    - Real-time status updates
    - Error details if operation failed
    - Result summary if operation completed

    **Perfect for:** Progress monitoring, debugging, result retrieval
    """,
)
async def get_operation_status(
    operation_id: str = Path(..., description="Unique operation identifier"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Get detailed status information for a specific operation.

    Returns complete information about an operation including current status,
    progress, metadata, and results (if completed).

    Args:
        operation_id: Unique identifier for the operation

    Returns:
        OperationStatusResponse: Detailed operation information

    Raises:
        404: Operation not found

    Example:
        GET /api/v1/operations/op_data_load_20241201_123456
    """
    try:
        # Use rate limiting for frequent status polling
        if should_rate_limit_log(f"operation_status_{operation_id}", 10):
            logger.info(f"Getting status for operation: {operation_id}")

        # Get operation from service
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Log operation completion at higher visibility
        if operation.status.value in ["completed", "failed", "cancelled"]:
            if should_rate_limit_log(f"operation_complete_{operation_id}", 1):
                logger.info(
                    f"🏁 OPERATION {operation.status.value.upper()}: {operation_id} ({operation.operation_type.value})"
                )
        else:
            # Rate limit routine status checks
            if should_rate_limit_log(f"operation_status_detail_{operation_id}", 10):
                logger.info(
                    f"Retrieved operation {operation_id}: status={operation.status}"
                )

        return OperationStatusResponse(
            success=True,
            data=operation,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation status: {str(e)}")
        raise DataError(
            message=f"Failed to get operation status for {operation_id}",
            error_code="OPERATIONS-GetStatusError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.delete(
    "/operations/{operation_id}",
    response_model=OperationCancelResponse,
    tags=["Operations"],
    summary="Cancel operation",
    description="""
    Cancel a running or pending operation.

    **Features:**
    - Graceful cancellation with cleanup
    - Force cancellation option for stuck operations
    - Cancellation reason tracking
    - Status verification before cancellation

    **Perfect for:** CLI Ctrl+C handling, stuck operation recovery, resource cleanup
    """,
)
async def cancel_operation(
    operation_id: str = Path(..., description="Unique operation identifier"),
    request: Optional[CancelOperationRequest] = None,
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationCancelResponse:
    """
    Cancel a running or pending operation.

    Attempts to gracefully cancel an operation. If the operation is in a
    critical section, cancellation may be delayed until safe. Use force=True
    to attempt immediate cancellation.

    Args:
        operation_id: Unique identifier for the operation to cancel
        request: Optional cancellation request with reason and force flag

    Returns:
        OperationCancelResponse: Cancellation result

    Raises:
        404: Operation not found
        400: Operation cannot be cancelled (already completed/failed)

    Example:
        DELETE /api/v1/operations/op_data_load_20241201_123456

    Example with body:
        DELETE /api/v1/operations/op_data_load_20241201_123456
        {
          "reason": "User requested cancellation via CLI",
          "force": false
        }
    """
    try:
        # Default request if none provided
        if request is None:
            request = CancelOperationRequest(reason=None, force=False)

        logger.info(
            f"Cancelling operation {operation_id}: reason='{request.reason}', force={request.force}"
        )

        # Get operation first to verify it exists
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Cannot cancel - operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Check if operation can be cancelled
        if operation.status in [
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ]:
            logger.warning(
                f"Cannot cancel - operation already finished: {operation_id} (status: {operation.status})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Operation {operation_id} cannot be cancelled (status: {operation.status})",
            )

        # Attempt cancellation
        cancellation_result = await operations_service.cancel_operation(
            operation_id=operation_id,
            reason=request.reason,
            force=request.force,
        )

        if cancellation_result["success"]:
            logger.info(f"Successfully cancelled operation: {operation_id}")
            return OperationCancelResponse(
                success=True,
                data=cancellation_result,
            )
        else:
            logger.warning(f"Failed to cancel operation: {operation_id}")
            raise DataError(
                message=f"Failed to cancel operation {operation_id}",
                error_code="OPERATIONS-CancelFailed",
                details=cancellation_result,
            )

    except HTTPException:
        raise
    except DataError:
        raise
    except Exception as e:
        logger.error(f"Error cancelling operation: {str(e)}")
        raise DataError(
            message=f"Failed to cancel operation {operation_id}",
            error_code="OPERATIONS-CancelError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.post(
    "/operations/{operation_id}/retry",
    response_model=OperationStatusResponse,
    tags=["Operations"],
    summary="Retry failed operation",
    description="""
    Retry a failed operation with the same parameters.

    **Features:**
    - Restart failed operations
    - Preserve original parameters
    - Create new operation ID for tracking

    **Perfect for:** Automatic retry logic, error recovery
    """,
)
async def retry_operation(
    operation_id: str = Path(..., description="Unique operation identifier to retry"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Retry a failed operation.

    Creates a new operation with the same parameters as the failed operation.
    The new operation gets a new operation ID for tracking.

    Args:
        operation_id: Unique identifier for the failed operation to retry

    Returns:
        OperationStatusResponse: New operation information

    Raises:
        404: Operation not found
        400: Operation is not in a failed state

    Example:
        POST /api/v1/operations/op_data_load_20241201_123456/retry
    """
    try:
        logger.info(f"Retrying operation: {operation_id}")

        # Get original operation
        original_operation = await operations_service.get_operation(operation_id)

        if not original_operation:
            logger.warning(f"Cannot retry - operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Check if operation can be retried
        if original_operation.status != OperationStatus.FAILED:
            logger.warning(
                f"Cannot retry - operation not failed: {operation_id} (status: {original_operation.status})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Operation {operation_id} cannot be retried (status: {original_operation.status})",
            )

        # Create new operation with same parameters
        new_operation = await operations_service.retry_operation(operation_id)

        logger.info(
            f"Created retry operation: {new_operation.operation_id} (original: {operation_id})"
        )
        return OperationStatusResponse(
            success=True,
            data=new_operation,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying operation: {str(e)}")
        raise DataError(
            message=f"Failed to retry operation {operation_id}",
            error_code="OPERATIONS-RetryError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.get(
    "/operations/{operation_id}/results",
    tags=["Operations"],
    summary="Get operation results",
    description="""
    Get operation results (summary metrics + analytics paths).

    Returns lightweight summary metrics and paths/links to detailed data.
    Works for any operation type (data loading, training, backtesting).

    Only returns results for completed or failed operations.
    For running operations, use GET /operations/{operation_id} for status.
    """,
)
async def get_operation_results(
    operation_id: str = Path(..., description="Unique operation identifier"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> dict:
    """
    Get operation results from result_summary.

    Args:
        operation_id: Unique identifier for the operation

    Returns:
        dict: Operation results with summary metrics

    Raises:
        404: Operation not found
        400: Operation not finished (status not completed or failed)

    Example:
        GET /api/v1/operations/op_training_20241201_123456/results
    """
    try:
        logger.info(f"Getting results for operation: {operation_id}")

        # Get operation from service
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Check if operation is finished
        if operation.status not in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
            logger.warning(
                f"Operation not finished: {operation_id} (status: {operation.status})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Operation not finished (status: {operation.status.value})",
            )

        logger.info(f"Returning results for operation: {operation_id}")
        return {
            "success": True,
            "operation_id": operation_id,
            "operation_type": operation.operation_type.value,
            "status": operation.status.value,
            "results": operation.result_summary or {},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation results: {str(e)}")
        raise DataError(
            message=f"Failed to get results for operation {operation_id}",
            error_code="OPERATIONS-ResultsError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.get(
    "/operations/{operation_id}/metrics",
    response_model=OperationMetricsResponse,
    tags=["Operations"],
    summary="Get operation metrics (M1: API Contract)",
    description="""
    Get domain-specific metrics for an operation.

    **M1: API Contract** - Returns empty metrics structure. Will be populated in M2.

    **Features:**
    - Training operations: epoch history, best epoch, overfitting indicators
    - Data operations: segment stats, cache info
    - Backtesting: trade stats, performance metrics

    **Perfect for:** Agent monitoring, trend analysis, decision making
    """,
)
async def get_operation_metrics(
    operation_id: str = Path(..., description="Unique operation identifier"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationMetricsResponse:
    """
    Get domain-specific metrics for an operation.

    In M1, returns empty structure. In M2, will return populated metrics.

    Args:
        operation_id: Unique identifier for the operation

    Returns:
        OperationMetricsResponse: Operation metrics data

    Raises:
        404: Operation not found

    Example:
        GET /api/v1/operations/op_training_20250117_120000/metrics
    """
    try:
        logger.info(f"Getting metrics for operation: {operation_id}")

        # Get operation from service
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Get metrics (empty in M1)
        metrics = await operations_service.get_operation_metrics(operation_id)

        logger.info(f"Retrieved metrics for operation: {operation_id}")
        return OperationMetricsResponse(
            success=True,
            data={
                "operation_id": operation_id,
                "operation_type": operation.operation_type.value,
                "metrics": metrics or {},
            },
        )

    except HTTPException:
        raise
    except KeyError as e:
        # Operation not found
        logger.warning(f"Operation not found: {operation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Operation not found: {operation_id}",
        ) from e
    except Exception as e:
        logger.error(f"Error getting operation metrics: {str(e)}")
        raise DataError(
            message=f"Failed to get metrics for operation {operation_id}",
            error_code="OPERATIONS-MetricsError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.post(
    "/operations/{operation_id}/metrics",
    tags=["Operations"],
    summary="Add metrics to operation (M1: validates only)",
    description="""
    Add domain-specific metrics to an operation.

    **M1: API Contract** - Validates payload but doesn't store. Will store in M2.

    Called by:
    - Local training orchestrator (direct call)
    - Training host service (via HTTP from host machine)

    **Perfect for:** Metrics collection pipeline testing
    """,
)
async def add_operation_metrics(
    operation_id: str,
    metrics: dict,
    operations_service: OperationsService = Depends(get_operations_service),
) -> dict:
    """
    Add metrics to an operation.

    In M1, validates payload but doesn't store. In M2, will persist metrics.

    Args:
        operation_id: Unique identifier for the operation
        metrics: Metrics payload (structure varies by operation type)

    Returns:
        dict: Success response

    Raises:
        404: Operation not found
        400: Invalid metrics payload

    Example:
        POST /api/v1/operations/op_training_20250117_120000/metrics
        {
            "epoch": 0,
            "train_loss": 0.8234,
            "val_loss": 0.8912
        }
    """
    try:
        logger.info(
            f"Adding metrics to operation: {operation_id} ({len(metrics)} fields)"
        )

        # Validate operation exists
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Add metrics (validates in M1, will store in M2)
        await operations_service.add_operation_metrics(operation_id, metrics)

        logger.info(f"[M1] Metrics validated for operation: {operation_id}")
        return {
            "success": True,
            "message": "[M1] Metrics validated successfully (not stored yet)",
            "operation_id": operation_id,
        }

    except HTTPException:
        raise
    except KeyError as e:
        logger.warning(f"Operation not found: {operation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Operation not found: {operation_id}",
        ) from e
    except ValueError as e:
        logger.warning(f"Invalid metrics payload: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid metrics payload: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Error adding operation metrics: {str(e)}")
        raise DataError(
            message=f"Failed to add metrics for operation {operation_id}",
            error_code="OPERATIONS-AddMetricsError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.post(
    "/operations/{operation_id}/resume",
    response_model=OperationResumeResponse,
    tags=["Operations"],
    summary="Resume operation from checkpoint",
    description="""
    Resume a FAILED or CANCELLED operation from its last checkpoint.

    **Features:**
    - Validates operation is resumable (FAILED/CANCELLED only)
    - Loads latest checkpoint from database
    - Creates new operation linked to original
    - Dispatches to appropriate service (Training/Backtesting)
    - Deletes original checkpoint after resume starts

    **Perfect for:** Recovery from failures, continuing cancelled work
    """,
)
async def resume_operation(
    operation_id: str = Path(..., description="ID of operation to resume"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationResumeResponse:
    """
    Resume operation from checkpoint (Task 3.2).

    Algorithm:
    1. Validate operation exists and is resumable (FAILED/CANCELLED)
    2. Load checkpoint from CheckpointService
    3. Create new operation with resumed_from link
    4. Dispatch to TrainingService or BacktestingService
    5. Delete original checkpoint
    6. Return new operation info

    Args:
        operation_id: ID of the original (failed/cancelled) operation

    Returns:
        OperationResumeResponse: Information about resumed operation

    Raises:
        404: Operation not found
        400: Operation not resumable or no checkpoint found
        500: Resume failed

    Example:
        POST /api/v1/operations/op_training_20250117_100000/resume
        Response:
        {
            "success": true,
            "original_operation_id": "op_training_20250117_100000",
            "new_operation_id": "op_training_20250117_140000",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 45"
        }
    """
    try:
        logger.info(f"Resuming operation from checkpoint: {operation_id}")

        # Resume operation via service
        result = await operations_service.resume_operation(operation_id)

        logger.info(
            f"Successfully resumed operation {operation_id} as {result['new_operation_id']}"
        )

        return OperationResumeResponse(**result)

    except ValueError as e:
        # ValueError raised for validation errors (not found, wrong status, no checkpoint)
        error_msg = str(e)
        logger.warning(f"Cannot resume operation {operation_id}: {error_msg}")

        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg) from e
        else:
            raise HTTPException(status_code=400, detail=error_msg) from e

    except Exception as e:
        logger.error(f"Error resuming operation {operation_id}: {str(e)}")
        raise DataError(
            message=f"Failed to resume operation {operation_id}",
            error_code="OPERATIONS-ResumeError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.delete(
    "/operations/{operation_id}/checkpoint",
    tags=["Operations"],
    summary="Delete checkpoint for operation",
    description="""
    Delete the checkpoint for a specific operation.

    **Use Cases:**
    - Free up disk space by deleting unused checkpoints
    - Clean up after successful operation completion
    - Remove checkpoints for operations that won't be resumed

    **Perfect for:** Disk space management, cleanup scripts
    """,
)
async def delete_checkpoint(
    operation_id: str = Path(
        ..., description="ID of operation whose checkpoint to delete"
    ),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Delete checkpoint for a specific operation.

    Args:
        operation_id: ID of the operation
        operations_service: Operations service dependency
        checkpoint_service: Checkpoint service dependency

    Returns:
        OperationStatusResponse: Confirmation of deletion

    Raises:
        HTTPException:
            404: Operation not found
            500: Deletion failed

    Example:
        DELETE /api/v1/operations/op_training_001/checkpoint

        Response:
        {
            "success": true,
            "data": {
                "operation_id": "op_training_001",
                "message": "Checkpoint deleted successfully"
            }
        }
    """
    try:
        # Import here to avoid circular imports
        from ktrdr.api.dependencies import get_checkpoint_service

        checkpoint_service = get_checkpoint_service()

        logger.info(f"Deleting checkpoint for operation: {operation_id}")

        # Verify operation exists
        operation = await operations_service.get_operation(operation_id)
        if not operation:
            raise HTTPException(
                status_code=404, detail=f"Operation not found: {operation_id}"
            )

        # Delete checkpoint
        checkpoint_service.delete_checkpoint(operation_id)

        logger.info(f"Successfully deleted checkpoint for operation {operation_id}")

        return OperationStatusResponse(
            success=True,
            data={  # type: ignore[arg-type]
                "operation_id": operation_id,
                "message": "Checkpoint deleted successfully",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting checkpoint for {operation_id}: {str(e)}")
        raise DataError(
            message=f"Failed to delete checkpoint for operation {operation_id}",
            error_code="OPERATIONS-DeleteCheckpointError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@router.post(
    "/operations/checkpoints/cleanup-cancelled",
    response_model=OperationStatusResponse,
    tags=["Operations"],
    summary="Cleanup cancelled operation checkpoints",
    description="""
    Delete checkpoints for all cancelled operations.

    **Use Cases:**
    - Automated cleanup of cancelled operations
    - Free disk space from abandoned operations
    - Scheduled maintenance

    **Perfect for:** Cleanup scripts, scheduled jobs
    """,
)
async def cleanup_cancelled_checkpoints(
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Clean up checkpoints for all cancelled operations.

    Args:
        operations_service: Operations service dependency

    Returns:
        OperationStatusResponse: Cleanup statistics

    Example:
        POST /api/v1/operations/checkpoints/cleanup-cancelled

        Response:
        {
            "success": true,
            "data": {
                "deleted_count": 3,
                "operation_ids": ["op_001", "op_002", "op_003"],
                "total_freed_bytes": 156000000
            }
        }
    """
    try:
        from ktrdr.api.dependencies import get_checkpoint_service

        checkpoint_service = get_checkpoint_service()

        logger.info("Cleaning up cancelled operation checkpoints")

        # Load operations with checkpoints (only cancelled)
        ops_with_checkpoints = (
            await operations_service.load_operations_with_checkpoints()
        )

        # Filter for cancelled operations
        cancelled_ops = [op for op in ops_with_checkpoints if op.status == "CANCELLED"]

        deleted_ids = []
        total_freed_bytes = 0

        # Delete each checkpoint
        for operation in cancelled_ops:
            try:
                checkpoint_service.delete_checkpoint(operation.operation_id)
                deleted_ids.append(operation.operation_id)
                # Note: We don't track freed bytes in current implementation
            except Exception as e:
                logger.warning(
                    f"Failed to delete checkpoint for {operation.operation_id}: {str(e)}"
                )

        logger.info(f"Cleaned up {len(deleted_ids)} cancelled operation checkpoints")

        return OperationStatusResponse(
            success=True,
            data={  # type: ignore[arg-type]
                "deleted_count": len(deleted_ids),
                "operation_ids": deleted_ids,
                "total_freed_bytes": total_freed_bytes,
            },
        )

    except Exception as e:
        logger.error(f"Error cleaning up cancelled checkpoints: {str(e)}")
        raise DataError(
            message="Failed to cleanup cancelled operation checkpoints",
            error_code="OPERATIONS-CleanupCancelledError",
            details={"error": str(e)},
        ) from e


@router.post(
    "/operations/checkpoints/cleanup-old",
    response_model=OperationStatusResponse,
    tags=["Operations"],
    summary="Cleanup old operation checkpoints",
    description="""
    Delete checkpoints older than specified days.

    **Use Cases:**
    - Scheduled cleanup of old checkpoints
    - Disk space management
    - Retention policy enforcement

    **Perfect for:** Cron jobs, maintenance scripts
    """,
)
async def cleanup_old_checkpoints(
    days: int = Query(
        30, ge=1, description="Delete checkpoints older than this many days"
    ),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Clean up checkpoints older than specified days.

    Args:
        days: Delete checkpoints older than this many days
        operations_service: Operations service dependency

    Returns:
        OperationStatusResponse: Cleanup statistics

    Example:
        POST /api/v1/operations/checkpoints/cleanup-old?days=7

        Response:
        {
            "success": true,
            "data": {
                "deleted_count": 5,
                "operation_ids": ["op_001", "op_002", "op_003", "op_004", "op_005"],
                "total_freed_bytes": 260000000
            }
        }
    """
    try:
        from datetime import datetime, timedelta

        from ktrdr.api.dependencies import get_checkpoint_service

        checkpoint_service = get_checkpoint_service()

        logger.info(f"Cleaning up checkpoints older than {days} days")

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)

        # Load operations with checkpoints
        ops_with_checkpoints = (
            await operations_service.load_operations_with_checkpoints()
        )

        # Filter for old operations (FAILED or CANCELLED only for safety)
        cutoff_str = cutoff_date.isoformat()
        old_ops = [
            op
            for op in ops_with_checkpoints
            if op.status in ["FAILED", "CANCELLED"] and op.created_at < cutoff_str  # type: ignore[operator]
        ]

        deleted_ids = []
        total_freed_bytes = 0

        # Delete each checkpoint
        for operation in old_ops:
            try:
                checkpoint_service.delete_checkpoint(operation.operation_id)
                deleted_ids.append(operation.operation_id)
            except Exception as e:
                logger.warning(
                    f"Failed to delete checkpoint for {operation.operation_id}: {str(e)}"
                )

        logger.info(
            f"Cleaned up {len(deleted_ids)} old operation checkpoints (>{days} days)"
        )

        return OperationStatusResponse(
            success=True,
            data={  # type: ignore[arg-type]
                "deleted_count": len(deleted_ids),
                "operation_ids": deleted_ids,
                "total_freed_bytes": total_freed_bytes,
            },
        )

    except Exception as e:
        logger.error(f"Error cleaning up old checkpoints: {str(e)}")
        raise DataError(
            message=f"Failed to cleanup old operation checkpoints (>{days} days)",
            error_code="OPERATIONS-CleanupOldError",
            details={"days": days, "error": str(e)},
        ) from e
