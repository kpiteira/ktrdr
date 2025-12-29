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
from ktrdr.api.endpoints.workers import get_worker_registry
from ktrdr.api.models.operations import (
    CancelOperationRequest,
    OperationCancelResponse,
    OperationListResponse,
    OperationMetricsResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
    ResumedFromInfo,
    ResumeOperationData,
    ResumeOperationResponse,
    StatusUpdateRequest,
    StatusUpdateResponse,
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


@router.get(
    "/operations/{operation_id}/children",
    response_model=OperationListResponse,
    tags=["Operations"],
    summary="Get child operations (Task 1.15)",
    description="""
    Get all child operations for a parent operation (e.g., agent session).

    **Features:**
    - Returns all child operations in creation order
    - Includes progress and status for each child
    - Useful for displaying session progress tree

    **Perfect for:** Agent session monitoring, progress trees, debugging
    """,
)
async def get_operation_children(
    operation_id: str = Path(..., description="Parent operation identifier"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationListResponse:
    """
    Get all child operations for a parent operation (Task 1.15).

    Returns children in creation order, which corresponds to the execution order
    for agent sessions (design → training → backtest).

    Args:
        operation_id: Unique identifier for the parent operation

    Returns:
        OperationListResponse: List of child operations

    Example:
        GET /api/v1/operations/op_agent_session_20241201_123456/children
    """
    try:
        logger.info(f"Getting children for operation: {operation_id}")

        # Verify parent exists
        parent = await operations_service.get_operation(operation_id)
        if not parent:
            logger.warning(f"Parent operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Get children from service
        children = await operations_service.get_children(operation_id)

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
            for op in children
        ]

        # Count active children
        active_count = sum(
            1
            for op in children
            if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
        )

        logger.info(f"Retrieved {len(children)} children for operation {operation_id}")
        return OperationListResponse(
            success=True,
            data=operation_summaries,
            total_count=len(children),
            active_count=active_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation children: {str(e)}")
        raise DataError(
            message=f"Failed to get children for operation {operation_id}",
            error_code="OPERATIONS-GetChildrenError",
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


def _get_checkpoint_service():
    """
    Get checkpoint service as FastAPI dependency.

    This wrapper allows proper dependency injection in tests.
    """
    from ktrdr.api.endpoints.checkpoints import get_checkpoint_service

    return get_checkpoint_service()


@router.post(
    "/operations/{operation_id}/resume",
    response_model=ResumeOperationResponse,
    tags=["Operations"],
    summary="Resume cancelled or failed operation",
    description="""
    Resume a cancelled or failed operation from its last checkpoint.

    **Features:**
    - Optimistic locking prevents race conditions
    - Loads checkpoint to verify availability
    - Training continues from checkpoint epoch
    - Checkpoint deleted after successful completion

    **Perfect for:** Resuming interrupted training, recovering from failures
    """,
)
async def resume_operation(
    operation_id: str = Path(..., description="Unique operation identifier to resume"),
    operations_service: OperationsService = Depends(get_operations_service),
    checkpoint_service=Depends(_get_checkpoint_service),
    worker_registry=Depends(get_worker_registry),
) -> ResumeOperationResponse:
    """
    Resume a cancelled or failed operation from checkpoint.

    Uses optimistic locking to atomically update status from CANCELLED/FAILED
    to RUNNING. Then verifies checkpoint exists before dispatching to worker.

    Args:
        operation_id: Unique identifier for the operation to resume

    Returns:
        ResumeOperationResponse: Resume result with checkpoint info

    Raises:
        404: Operation not found or no checkpoint available
        409: Operation cannot be resumed (already running/completed)

    Example:
        POST /api/v1/operations/op_training_20241213_143022_abc123/resume
    """

    try:
        logger.info(f"Resuming operation: {operation_id}")

        # 1. Optimistic lock: Update status only if resumable
        updated = await operations_service.try_resume(operation_id)

        if not updated:
            # try_resume failed, check why
            op = await operations_service.get_operation(operation_id)

            if op is None:
                logger.warning(f"Cannot resume - operation not found: {operation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                )
            if op.status == OperationStatus.RUNNING:
                logger.warning(
                    f"Cannot resume - operation already running: {operation_id}"
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Operation {operation_id} is already running",
                )
            if op.status == OperationStatus.RESUMING:
                logger.warning(
                    f"Cannot resume - operation already resuming: {operation_id}"
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Operation {operation_id} is already resuming",
                )
            if op.status == OperationStatus.COMPLETED:
                logger.warning(
                    f"Cannot resume - operation already completed: {operation_id}"
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"Operation {operation_id} is already completed",
                )
            # Generic case for other non-resumable states
            logger.warning(
                f"Cannot resume - operation in non-resumable state: {operation_id} (status: {op.status})"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resume operation {operation_id} from status {op.status.value}",
            )

        # 2. Load checkpoint to verify it exists
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=False
        )

        if checkpoint is None:
            logger.warning(f"No checkpoint available for operation: {operation_id}")
            # Mark as FAILED since we can't resume
            await operations_service.update_status(operation_id, status="FAILED")
            raise HTTPException(
                status_code=404,
                detail=f"No checkpoint available for operation {operation_id}",
            )

        # 3. Dispatch to worker
        # NOTE: We get operation_type from checkpoint metadata to avoid calling
        # get_operation() here. Calling get_operation() would trigger a proxy
        # refresh which could overwrite the RESUMING status with stale data
        # from the worker (which may still show CANCELLED before it starts).
        op_type = checkpoint.state.get(
            "operation_type", "training"
        )  # Default to training

        if op_type == "training":
            # Select a training worker
            from ktrdr.api.models.workers import WorkerType

            worker = worker_registry.select_worker(WorkerType.TRAINING)
            if worker is None:
                logger.error(f"No training worker available for resume: {operation_id}")
                # Revert status back to cancelled since we can't dispatch
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=503,
                    detail="No training worker available to resume operation",
                )

            # Dispatch to worker's /training/resume endpoint
            import httpx

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{worker.endpoint_url}/training/resume",
                        json={"operation_id": operation_id},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    worker_response = response.json()
                    logger.info(
                        f"Dispatched resume to worker {worker.worker_id}: {worker_response}"
                    )
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Worker rejected resume request: {e.response.status_code} - {e.response.text}"
                )
                # Revert status back to cancelled since dispatch failed
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=502,
                    detail=f"Worker failed to resume: {e.response.text}",
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Failed to connect to worker: {str(e)}")
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to connect to worker: {str(e)}",
                ) from e

        elif op_type == "backtesting":
            # Select a backtesting worker
            from ktrdr.api.models.workers import WorkerType

            worker = worker_registry.select_worker(WorkerType.BACKTESTING)
            if worker is None:
                logger.error(f"No backtest worker available for resume: {operation_id}")
                # Revert status back to cancelled since we can't dispatch
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=503,
                    detail="No backtest worker available to resume operation",
                )

            # Dispatch to worker's /backtests/resume endpoint
            import httpx

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{worker.endpoint_url}/backtests/resume",
                        json={"operation_id": operation_id},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    worker_response = response.json()
                    logger.info(
                        f"Dispatched backtest resume to worker {worker.worker_id}: {worker_response}"
                    )
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Backtest worker rejected resume request: {e.response.status_code} - {e.response.text}"
                )
                # Revert status back to cancelled since dispatch failed
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=502,
                    detail=f"Worker failed to resume: {e.response.text}",
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Failed to connect to backtest worker: {str(e)}")
                await operations_service.update_status(operation_id, status="CANCELLED")
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to connect to worker: {str(e)}",
                ) from e

        logger.info(
            f"Successfully resumed operation: {operation_id} from epoch {checkpoint.state.get('epoch')}"
        )

        # Return RESUMING status - we know try_resume succeeded and set this status.
        # Don't query the worker as it may still show stale data (CANCELLED).
        # The worker will update to RUNNING when it starts, and get_operation
        # will sync that status on subsequent queries.
        return ResumeOperationResponse(
            success=True,
            data=ResumeOperationData(
                operation_id=operation_id,
                status="resuming",
                resumed_from=ResumedFromInfo(
                    checkpoint_type=checkpoint.checkpoint_type,
                    created_at=checkpoint.created_at,
                    epoch=checkpoint.state.get("epoch"),
                ),
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming operation: {str(e)}")
        raise DataError(
            message=f"Failed to resume operation {operation_id}",
            error_code="OPERATIONS-ResumeError",
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


@router.patch(
    "/operations/{operation_id}/status",
    response_model=StatusUpdateResponse,
    tags=["Operations"],
    summary="Update operation status (M6: worker graceful shutdown)",
    description="""
    Update the status of an operation.

    **Primary use case:** Workers calling this during graceful shutdown to
    mark operations as CANCELLED before exiting.

    For user-initiated cancellation, prefer DELETE /operations/{id} instead,
    which handles cascade cancellation of children and cleanup.

    **Perfect for:** Worker graceful shutdown, status synchronization
    """,
)
async def update_operation_status(
    request: StatusUpdateRequest,
    operation_id: str = Path(..., description="Unique operation identifier"),
    operations_service: OperationsService = Depends(get_operations_service),
) -> StatusUpdateResponse:
    """
    Update operation status.

    Used primarily by workers to report final status during graceful shutdown.
    This is a simplified status update that doesn't perform cascade operations
    like the cancel endpoint does.

    Args:
        operation_id: Unique identifier for the operation
        request: Status update request with new status and optional message

    Returns:
        StatusUpdateResponse: Update result with previous and new status

    Raises:
        404: Operation not found

    Example:
        PATCH /api/v1/operations/op_training_20250128_120000/status
        {
            "status": "CANCELLED",
            "error_message": "Graceful shutdown - checkpoint saved"
        }
    """
    try:
        logger.info(f"Updating operation status: {operation_id} -> {request.status}")

        # Get current operation
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        previous_status = operation.status.value

        # Update status
        await operations_service.update_status(operation_id, request.status)

        # If there's an error message, update that too (via repository if available)
        if request.error_message and operations_service._repository:
            await operations_service._repository.update(
                operation_id,
                error_message=request.error_message,
            )

        logger.info(
            f"Updated operation {operation_id}: {previous_status} -> {request.status}"
        )

        return StatusUpdateResponse(
            success=True,
            operation_id=operation_id,
            previous_status=previous_status,
            new_status=request.status.lower(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating operation status: {str(e)}")
        raise DataError(
            message=f"Failed to update status for operation {operation_id}",
            error_code="OPERATIONS-StatusUpdateError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e
