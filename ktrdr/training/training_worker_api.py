"""
Training Worker API - FastAPI Application for Training Worker Container.

This module provides a FastAPI application that runs TrainingManager in LOCAL mode
within a remote container. The backend treats this as "remote", but this service
itself runs training locally (from its own perspective).

Key Design:
- Runs TrainingManager in LOCAL mode (not remote mode!)
- Exposes same OperationsService endpoints as backend
- Backend proxies to this service via OperationServiceProxy
- One training operation at a time (worker exclusivity)

Usage:
    # Run directly for development
    uvicorn ktrdr.training.training_worker_api:app --host 0.0.0.0 --port 5004

    # Or via Docker
    docker run -p 5004:5004 ktrdr-backend uvicorn ktrdr.training.training_worker_api:app ...
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.training.training_manager import TrainingManager
from ktrdr.training.worker_registration import WorkerRegistration

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Training Worker Service",
    description="Training worker execution service for KTRDR (runs TrainingManager in local mode)",
    version="1.0.0",
)

# Add CORS middleware for container communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for container/localhost communication
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service singletons (initialized on startup)
_operations_service: Optional["OperationsService"] = None
_training_manager: Optional[TrainingManager] = None


def get_training_manager() -> TrainingManager:
    """Get training manager singleton."""
    global _training_manager
    if _training_manager is None:
        _training_manager = TrainingManager()
    return _training_manager


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _operations_service

    logger.info("=" * 80)
    logger.info("🚀 Starting Training Worker Service")
    logger.info("=" * 80)

    # Force local mode (this service should never use remote mode)
    os.environ["USE_TRAINING_HOST_SERVICE"] = "false"

    # Initialize OperationsService
    _operations_service = get_operations_service()
    logger.info(
        f"✅ OperationsService initialized (cache_ttl={_operations_service._cache_ttl}s)"
    )

    # Initialize TrainingManager (will run in local mode)
    get_training_manager()
    logger.info("✅ TrainingManager initialized (mode: local)")

    # Register with backend (self-registration)
    logger.info("")
    logger.info("📝 Registering worker with backend...")
    worker_registration = WorkerRegistration()
    registration_success = await worker_registration.register()

    if registration_success:
        logger.info(
            f"✅ Worker registered successfully: {worker_registration.worker_id}"
        )
    else:
        logger.warning(
            f"⚠️  Worker registration failed: {worker_registration.worker_id}"
        )
        logger.warning(
            "   Worker will continue running but may not receive tasks from backend"
        )

    logger.info("")
    logger.info("📡 Available Endpoints:")
    logger.info(
        "  POST /training/start              - Start training (domain-specific)"
    )
    logger.info("  GET  /api/v1/operations           - List operations")
    logger.info("  GET  /api/v1/operations/{id}      - Get operation status")
    logger.info("  GET  /api/v1/operations/{id}/metrics - Get operation metrics")
    logger.info("  DELETE /api/v1/operations/{id}/cancel - Cancel operation")
    logger.info("  GET  /health                      - Health check")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Training Worker Service...")


# ============================================================================
# Health & Info Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint with service info."""
    # Trigger service initialization
    get_training_manager()
    return {
        "service": "Training Worker Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "local",  # This service always runs in local mode
        "note": "Runs TrainingManager in LOCAL mode (backend treats this as remote)",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint that reports worker status.

    Returns worker_status as 'busy' if there are active operations,
    'idle' otherwise. This is used by the backend's health check system
    to determine worker availability.
    """
    # Check if there are active training operations
    ops_service = get_operations_service()
    active_ops, _, _ = await ops_service.list_operations(
        operation_type=OperationType.TRAINING, active_only=True
    )

    worker_status = "busy" if active_ops else "idle"
    current_operation = active_ops[0].operation_id if active_ops else None

    return {
        "healthy": True,
        "service": "training-worker",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational",
        "worker_status": worker_status,  # 'busy' or 'idle' - used by backend health checks
        "current_operation": current_operation,
        "active_operations_count": len(active_ops),
    }


# ============================================================================
# Training Endpoints (Domain-Specific) - Will be implemented in Task 3.2
# ============================================================================

# Placeholder for /training/start endpoint - will be implemented in next task


# ============================================================================
# Operations Endpoints (Generic - Proxy to OperationsService)
# ============================================================================


@app.get("/api/v1/operations")
async def list_operations(
    operation_type: Optional[OperationType] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """
    List operations (same as backend OperationsService).

    This allows the backend to query all operations running on this remote service.
    """
    try:
        assert _operations_service is not None, "OperationsService not initialized"
        operations, total, filtered = await _operations_service.list_operations(
            operation_type=operation_type,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

        return {
            "operations": operations,
            "total": total,
            "filtered": filtered,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error listing operations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/operations/{operation_id}")
async def get_operation(
    operation_id: str,
    force_refresh: bool = Query(False),
):
    """
    Get operation status (same as backend OperationsService).

    This is the endpoint that backend's OperationServiceProxy calls to get
    operation status from this remote service. Uses same pull-based architecture
    with cache + TTL.

    Args:
        operation_id: Operation identifier
        force_refresh: Force refresh from bridge (bypass cache)

    Returns:
        Operation status dictionary
    """
    try:
        assert _operations_service is not None, "OperationsService not initialized"
        operation = await _operations_service.get_operation(
            operation_id=operation_id,
            force_refresh=force_refresh,
        )

        if operation is None:
            raise HTTPException(
                status_code=404, detail=f"Operation not found: {operation_id}"
            )

        return operation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/operations/{operation_id}/metrics")
async def get_operation_metrics(
    operation_id: str,
    cursor: int = Query(0, description="Cursor for incremental metric retrieval"),
):
    """
    Get operation metrics (same as backend OperationsService).

    Supports incremental retrieval via cursor (returns only new metrics since cursor).

    Args:
        operation_id: Operation identifier
        cursor: Cursor position for incremental retrieval

    Returns:
        Dictionary with metrics and new cursor
    """
    try:
        assert _operations_service is not None, "OperationsService not initialized"
        metrics, new_cursor = await _operations_service.get_operation_metrics(
            operation_id=operation_id,
            cursor=cursor,
        )

        return {
            "metrics": metrics,
            "cursor": new_cursor,
        }

    except KeyError as e:
        raise HTTPException(
            status_code=404, detail=f"Operation not found: {operation_id}"
        ) from e
    except Exception as e:
        logger.error(f"Error getting metrics for {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/v1/operations/{operation_id}/cancel")
async def cancel_operation(operation_id: str):
    """
    Cancel operation (same as backend OperationsService).

    Args:
        operation_id: Operation identifier to cancel

    Returns:
        Cancellation confirmation
    """
    try:
        assert _operations_service is not None, "OperationsService not initialized"
        result = await _operations_service.cancel_operation(operation_id=operation_id)
        return result

    except KeyError as e:
        raise HTTPException(
            status_code=404, detail=f"Operation not found: {operation_id}"
        ) from e
    except Exception as e:
        logger.error(f"Error cancelling operation {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
