"""
Workers API endpoints.

This module implements the API endpoints for worker registration and discovery
in the distributed training and backtesting architecture.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ktrdr import get_logger
from ktrdr.api.models.workers import CompletedOperationReport, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry

# Setup module-level logger
logger = get_logger(__name__)

# Create router for worker endpoints
router = APIRouter()

# Global worker registry instance (singleton)
_worker_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    """
    Get or create the global WorkerRegistry instance.

    Returns:
        WorkerRegistry: The global worker registry singleton
    """
    global _worker_registry
    if _worker_registry is None:
        _worker_registry = WorkerRegistry()
        logger.info("Worker registry initialized")
    return _worker_registry


class WorkerRegistrationRequest(BaseModel):
    """Request model for worker registration.

    Supports resilience fields for re-registration after backend restart:
    - current_operation_id: Operation currently being executed
    - completed_operations: Operations that finished while backend was unavailable
    """

    worker_id: str = Field(..., description="Unique identifier for the worker")
    worker_type: WorkerType = Field(..., description="Type of worker")
    endpoint_url: str = Field(..., description="HTTP URL where worker can be reached")
    capabilities: Optional[dict] = Field(
        default=None, description="Worker capabilities (cores, memory, etc.)"
    )
    # Resilience fields for re-registration (M1 checkpoint)
    current_operation_id: Optional[str] = Field(
        default=None,
        description="ID of operation currently being executed by this worker",
    )
    completed_operations: list[CompletedOperationReport] = Field(
        default_factory=list,
        description="Operations that completed while backend was unavailable",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "worker_id": "backtest-worker-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
                "capabilities": {"cores": 4, "memory_gb": 8},
                "current_operation_id": None,
                "completed_operations": [],
            }
        }
    )


@router.post(
    "/workers/register",
    tags=["Workers"],
    summary="Register a worker",
    description="Register or update a worker node in the distributed system",
)
async def register_worker(
    request: WorkerRegistrationRequest,
    registry: WorkerRegistry = Depends(get_worker_registry),
) -> dict:
    """
    Register or update a worker node.

    Workers self-register on startup by calling this endpoint with their
    ID, type, URL, and capabilities. Re-registering an existing worker
    updates its information (idempotent operation).

    Returns 503 Service Unavailable if the backend is shutting down,
    signaling workers to retry after the backend restarts.

    Args:
        request: Worker registration information
        registry: The worker registry (injected dependency)

    Returns:
        dict: The registered worker information

    Raises:
        HTTPException: 503 if backend is shutting down

    Example:
        ```json
        {
            "worker_id": "backtest-worker-1",
            "worker_type": "backtesting",
            "endpoint_url": "http://192.168.1.201:5003",
            "capabilities": {"cores": 4, "memory_gb": 8}
        }
        ```
    """
    # M7.5 Task 7.5.3: Reject registrations during shutdown
    if registry.is_shutting_down():
        logger.info(
            f"Rejecting registration from {request.worker_id} - backend is shutting down"
        )
        raise HTTPException(
            status_code=503,
            detail="Backend is shutting down - retry after restart",
            headers={"Retry-After": "5"},
        )

    logger.info(
        f"Worker registration request: {request.worker_id} ({request.worker_type})"
    )

    result = await registry.register_worker(
        worker_id=request.worker_id,
        worker_type=request.worker_type,
        endpoint_url=request.endpoint_url,
        capabilities=request.capabilities,
        current_operation_id=request.current_operation_id,
        completed_operations=request.completed_operations,
    )

    logger.info(f"Worker registered successfully: {request.worker_id}")

    return result.worker.to_dict()


@router.get(
    "/workers",
    tags=["Workers"],
    summary="List workers",
    description="List all registered workers with optional filtering",
)
async def list_workers(
    worker_type: Optional[WorkerType] = None,
    status: Optional[str] = None,
    registry: WorkerRegistry = Depends(get_worker_registry),
) -> list[dict]:
    """
    List registered workers with optional filtering.

    Args:
        worker_type: Optional filter by worker type
        status: Optional filter by worker status
        registry: The worker registry (injected dependency)

    Returns:
        list[dict]: List of workers matching the filters

    Example:
        ```
        GET /api/v1/workers
        GET /api/v1/workers?worker_type=backtesting
        GET /api/v1/workers?status=available
        GET /api/v1/workers?worker_type=backtesting&status=available
        ```
    """
    # Import WorkerStatus here to avoid circular dependency
    from ktrdr.api.models.workers import WorkerStatus

    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = WorkerStatus(status)
        except ValueError:
            logger.warning(f"Invalid status filter: {status}")
            # Return empty list for invalid status
            return []

    workers = registry.list_workers(worker_type=worker_type, status=status_enum)

    return [worker.to_dict() for worker in workers]


@router.get(
    "/workers/{worker_id}",
    tags=["Workers"],
    summary="Get worker by ID",
    description="Check if a specific worker is registered",
)
async def get_worker(
    worker_id: str,
    registry: WorkerRegistry = Depends(get_worker_registry),
) -> dict:
    """
    Get a specific worker by ID.

    Used by workers to check if they're still registered after
    backend restart. Returns 404 if not found, triggering re-registration.

    Args:
        worker_id: The worker's unique identifier
        registry: The worker registry (injected dependency)

    Returns:
        dict: Worker information if found

    Raises:
        HTTPException: 404 if worker not found
    """
    worker = registry.get_worker(worker_id)
    if worker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Worker not found: {worker_id}",
        )
    return worker.to_dict()
