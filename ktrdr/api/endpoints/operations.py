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
        100, ge=1, le=1000, description="Maximum number of operations to return"
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
        operations, total_count, active_count = (
            await operations_service.list_operations(
                status=status,
                operation_type=operation_type,
                limit=limit,
                offset=offset,
                active_only=active_only,
            )
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
            request = CancelOperationRequest()

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
