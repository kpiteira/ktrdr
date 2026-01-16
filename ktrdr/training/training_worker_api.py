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
from datetime import UTC, datetime
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
        "timestamp": datetime.now(UTC).isoformat(),
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
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "operational",
        "worker_status": worker_status,  # 'busy' or 'idle' - used by backend health checks
        "current_operation": current_operation,
        "active_operations_count": len(active_ops),
    }


# ============================================================================
# Training Endpoints (Domain-Specific)
# ============================================================================


@app.post("/training/start")
async def start_training(
    symbols: list[str],
    timeframes: list[str],
    strategy_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_id: Optional[str] = None,
    detailed_analytics: bool = False,
):
    """
    Start a training operation on this worker.

    This endpoint runs TrainingManager in LOCAL mode (from this container's
    perspective). The backend service treats this as "remote", but this service
    itself doesn't know or care - it just runs training locally.

    Args:
        symbols: List of symbols to train on
        timeframes: List of timeframes to train on
        strategy_name: Name of strategy configuration file
        start_date: Optional start date for training data
        end_date: Optional end date for training data
        task_id: Optional task ID for tracking
        detailed_analytics: Whether to include detailed analytics

    Returns:
        Training start response with operation_id for tracking

    Raises:
        HTTPException: 400 for validation errors, 500 for internal errors, 503 if worker busy
    """
    # EXCLUSIVITY CHECK: Reject if worker is already busy
    ops_service = get_operations_service()
    active_ops, _, _ = await ops_service.list_operations(
        operation_type=OperationType.TRAINING, active_only=True
    )

    if active_ops:
        current_operation = active_ops[0].operation_id
        logger.warning(
            f"⛔ Worker BUSY - Rejecting new training request (current operation: {current_operation})"
        )
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail={
                "error": "Worker busy",
                "message": f"Worker is currently executing operation {current_operation}",
                "current_operation": current_operation,
                "active_operations_count": len(active_ops),
            },
        )

    # IMMEDIATELY register operation to prevent race condition
    # This ensures the next request will see this operation and reject with 503
    import socket
    import uuid
    from datetime import datetime

    from ktrdr.api.models.operations import OperationMetadata

    worker_id = os.getenv("WORKER_ID") or f"training-{socket.gethostname()}"

    # Generate or use provided operation_id
    operation_id = task_id or f"worker_training_{uuid.uuid4().hex[:12]}"

    # Parse date strings to datetime objects
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            start_dt = None
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            end_dt = None

    # Create operation immediately as "in_progress" to claim this worker
    metadata = OperationMetadata(
        symbol=symbols[0] if symbols else "MULTI",
        timeframe=timeframes[0] if timeframes else None,
        mode="training",
        start_date=start_dt,
        end_date=end_dt,
        parameters={
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "worker_id": worker_id,
        },
    )

    await ops_service.create_operation(
        operation_type=OperationType.TRAINING,
        metadata=metadata,
        operation_id=operation_id,
    )

    # Mark operation as started (in-progress) immediately
    # Create a dummy task just for marking it as started
    import asyncio

    dummy_task = asyncio.create_task(asyncio.sleep(0))
    await ops_service.start_operation(operation_id, dummy_task)

    logger.info(
        f"🔵 WORKER {worker_id}: Registered and started operation {operation_id} "
        f"(training {symbols} {timeframes} {strategy_name})"
    )

    try:
        training_manager = get_training_manager()

        # Call TrainingManager (will run in LOCAL mode)
        logger.info(f"🔵 WORKER {worker_id}: Executing training for {operation_id}")

        # Build strategy config path
        strategy_config_path = f"strategies/{strategy_name}.yaml"

        # Execute training (will create its own operation, but we ignore it)
        # We use our pre-registered operation_id for worker exclusivity
        await training_manager.train_multi_symbol_strategy(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date or "2024-01-01",
            end_date=end_date or "2024-12-31",
            validation_split=0.2,
            data_mode="local",
        )

        logger.info(
            f"🔵 WORKER {worker_id}: Operation started - operation_id={operation_id}"
        )

        return {
            "success": True,
            "task_id": operation_id,
            "status": "started",
            "message": "Training started successfully",
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        # Mark operation as failed
        await ops_service.fail_operation(operation_id, str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Internal error starting training: {str(e)}", exc_info=True)
        # Mark operation as failed
        await ops_service.fail_operation(operation_id, str(e))
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


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
