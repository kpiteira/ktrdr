"""
Operations API Endpoints for Training Host Service

Task 2.2 (M2): Expose /operations/* API in training host service matching backend API contract.

This module provides the same operations API as the backend, enabling:
- Unified operations tracking across backend and host services
- Client-driven pull-based progress updates
- Two-level caching (backend + host service)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ktrdr.api.models.operations import (
    OperationListResponse,
    OperationMetricsResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.logging import get_logger
from services.operations import get_operations_service

logger = get_logger(__name__)

# Create router with /api/v1 prefix to match backend
router = APIRouter(prefix="/api/v1", tags=["Operations"])


@router.get(
    "/operations/{operation_id}",
    response_model=OperationStatusResponse,
    summary="Get operation status",
    description="""
    Get detailed status and progress information for a specific operation.

    This endpoint provides the same API contract as the backend, enabling
    transparent operation queries whether the operation runs locally or on host service.
    """,
)
async def get_operation_status(
    operation_id: str = Path(..., description="Unique operation identifier"),
    force_refresh: bool = Query(
        False, description="Force refresh from bridge (bypass cache)"
    ),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationStatusResponse:
    """
    Get detailed status information for a specific operation.

    Args:
        operation_id: Unique identifier for the operation
        force_refresh: If True, bypass cache and refresh from bridge

    Returns:
        OperationStatusResponse: Detailed operation information

    Raises:
        404: Operation not found
    """
    try:
        logger.debug(
            f"Getting operation status: {operation_id} (force_refresh={force_refresh})"
        )

        # Get operation from service (triggers pull from bridge if stale)
        operation = await operations_service.get_operation(
            operation_id, force_refresh=force_refresh
        )

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        logger.debug(
            f"Retrieved operation {operation_id}: status={operation.status.value}"
        )

        return OperationStatusResponse(
            success=True,
            data=operation,
        )

    except KeyError as e:
        # OperationsService raises KeyError for missing operations
        logger.warning(f"Operation not found: {operation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Operation not found: {operation_id}",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get operation status: {str(e)}",
        ) from e


@router.get(
    "/operations/{operation_id}/metrics",
    response_model=OperationMetricsResponse,
    summary="Get operation metrics",
    description="""
    Get incremental metrics for an operation.

    Supports cursor-based retrieval to efficiently fetch only new metrics
    since the last query.
    """,
)
async def get_operation_metrics(
    operation_id: str = Path(..., description="Unique operation identifier"),
    cursor: int = Query(
        0, ge=0, description="Cursor position for incremental metrics retrieval"
    ),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationMetricsResponse:
    """
    Get domain-specific metrics for an operation.

    Supports incremental retrieval using cursor-based pagination.
    Returns only metrics added since the provided cursor position.

    Args:
        operation_id: Unique identifier for the operation
        cursor: Position in metrics history (0 = from beginning)

    Returns:
        OperationMetricsResponse: Metrics data with new cursor

    Raises:
        404: Operation not found
    """
    try:
        logger.debug(f"Getting metrics for operation: {operation_id} (cursor={cursor})")

        # Verify operation exists
        operation = await operations_service.get_operation(operation_id)

        if not operation:
            logger.warning(f"Operation not found: {operation_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Operation not found: {operation_id}",
            )

        # Get incremental metrics from service
        metrics = await operations_service.get_operation_metrics(
            operation_id, cursor=cursor
        )

        logger.debug(
            f"Retrieved {len(metrics) if isinstance(metrics, list) else 0} metrics for operation: {operation_id}"
        )

        return OperationMetricsResponse(
            success=True,
            data={
                "operation_id": operation_id,
                "operation_type": operation.operation_type.value,
                "metrics": metrics or [],
                "cursor": cursor,  # Will be updated by consumer based on metrics length
            },
        )

    except KeyError as e:
        logger.warning(f"Operation not found: {operation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Operation not found: {operation_id}",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get operation metrics: {str(e)}",
        ) from e


@router.get(
    "/operations",
    response_model=OperationListResponse,
    summary="List operations",
    description="""
    Get a list of all operations with optional filtering.

    Supports filtering by status, operation type, and pagination.
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

    Returns a paginated list of operations. Useful for monitoring
    and management of operations running on the host service.

    Args:
        status: Filter operations by status
        operation_type: Filter operations by type
        limit: Maximum number of operations to return
        offset: Number of operations to skip (for pagination)
        active_only: If True, only return running/pending operations

    Returns:
        OperationListResponse: Paginated list of operations
    """
    try:
        logger.debug(
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

        # Convert to summary format (same as backend)
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

        logger.debug(
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list operations: {str(e)}",
        ) from e
