"""
Remote Backtesting API - FastAPI Application for Remote Container.

DEPRECATED: This file is being replaced by BacktestWorker (using WorkerAPIBase pattern).
See ktrdr/backtesting/backtest_worker.py for the new implementation.

This module provides a FastAPI application that runs BacktestingService within
a remote container using the legacy pattern.

Legacy Design:
- Exposes OperationsService endpoints
- Backend proxies to this service via OperationServiceProxy
- Being replaced by WorkerAPIBase pattern

Usage (DEPRECATED):
    # Use backtest_worker.py instead
    # Legacy: uvicorn ktrdr.backtesting.remote_api:app --host 0.0.0.0 --port 5003
"""

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ktrdr.api.models.backtesting import BacktestStartRequest, BacktestStartResponse
from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.services.training import extract_symbols_timeframes_from_strategy
from ktrdr.api.services.worker_registry import WorkerRegistry
from ktrdr.backtesting.backtesting_service import BacktestingService
from ktrdr.backtesting.worker_registration import WorkerRegistration
from ktrdr.errors import ValidationError

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
    title="Backtesting Remote Service",
    description="Remote backtest execution service for KTRDR (runs BacktestingService in local mode)",
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
_backtesting_service: Optional[BacktestingService] = None


def get_backtest_service() -> BacktestingService:
    """
    Get backtesting service singleton.

    Note: This creates an empty WorkerRegistry as this legacy API
    is being replaced by BacktestWorker.
    """
    global _backtesting_service
    if _backtesting_service is None:
        # Create minimal registry for backward compatibility
        # (This file is deprecated - use backtest_worker.py instead)
        worker_registry = WorkerRegistry()
        _backtesting_service = BacktestingService(worker_registry=worker_registry)
    return _backtesting_service


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _operations_service

    logger.info("=" * 80)
    logger.info("🚀 Starting Backtesting Remote Service")
    logger.info("=" * 80)

    # Initialize OperationsService
    _operations_service = get_operations_service()
    logger.info(
        f"✅ OperationsService initialized (cache_ttl={_operations_service._cache_ttl}s)"
    )

    # Initialize BacktestingService (distributed-only mode)
    get_backtest_service()
    logger.info("✅ BacktestingService initialized (mode: distributed, workers-only)")

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
        "  POST /backtests/start               - Start backtest (domain-specific)"
    )
    logger.info("  GET  /api/v1/operations             - List operations")
    logger.info("  GET  /api/v1/operations/{id}        - Get operation status")
    logger.info("  GET  /api/v1/operations/{id}/metrics - Get operation metrics")
    logger.info("  DELETE /api/v1/operations/{id}/cancel - Cancel operation")
    logger.info("  GET  /health                        - Health check")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Backtesting Remote Service...")


# ============================================================================
# Health & Info Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint with service info."""
    # Trigger service initialization
    get_backtest_service()
    return {
        "service": "Backtesting Remote Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": "local",  # This service always runs in local mode
        "note": "Runs BacktestingService in LOCAL mode (backend treats this as remote)",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint that reports worker status.

    Returns worker_status as 'busy' if there are active operations,
    'idle' otherwise. This is used by the backend's health check system
    to determine worker availability.
    """
    # Check if there are active backtest operations
    ops_service = get_operations_service()
    active_ops, _, _ = await ops_service.list_operations(
        operation_type=OperationType.BACKTESTING, active_only=True
    )

    worker_status = "busy" if active_ops else "idle"
    current_operation = active_ops[0].operation_id if active_ops else None

    return {
        "healthy": True,
        "service": "backtest-remote",
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "operational",
        "worker_status": worker_status,  # 'busy' or 'idle' - used by backend health checks
        "current_operation": current_operation,
        "active_operations_count": len(active_ops),
    }


# ============================================================================
# Backtesting Endpoints (Domain-Specific)
# ============================================================================


@app.post("/backtests/start", response_model=BacktestStartResponse)
async def start_backtest(request: BacktestStartRequest) -> BacktestStartResponse:
    """
    Start a backtest on this remote container.

    This endpoint runs BacktestingService in LOCAL mode (from this container's
    perspective). The backend service treats this as "remote", but this service
    itself doesn't know or care - it just runs backtests locally.

    Args:
        request: Backtest configuration

    Returns:
        BacktestStartResponse with operation_id for tracking

    Raises:
        HTTPException: 400 for validation errors, 500 for internal errors, 503 if worker busy
    """
    # EXCLUSIVITY CHECK: Reject if worker is already busy
    ops_service = get_operations_service()
    active_ops, _, _ = await ops_service.list_operations(
        operation_type=OperationType.BACKTESTING, active_only=True
    )

    if active_ops:
        current_operation = active_ops[0].operation_id
        logger.warning(
            f"⛔ Worker BUSY - Rejecting new backtest request (current operation: {current_operation})"
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

    try:
        service = get_backtest_service()

        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Build strategy config path
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

        # Resolve symbol/timeframe - use request values or extract from strategy config
        resolved_symbol = request.symbol
        resolved_timeframe = request.timeframe

        if resolved_symbol is None or resolved_timeframe is None:
            logger.info(
                f"Extracting symbol/timeframe from strategy config: {request.strategy_name}"
            )
            config_symbols, config_timeframes = (
                extract_symbols_timeframes_from_strategy(request.strategy_name)
            )

            if resolved_symbol is None:
                resolved_symbol = config_symbols[0] if config_symbols else None
                logger.info(f"Using symbol from strategy config: {resolved_symbol}")

            if resolved_timeframe is None:
                resolved_timeframe = config_timeframes[0] if config_timeframes else None
                logger.info(
                    f"Using timeframe from strategy config: {resolved_timeframe}"
                )

        # Validate we have both symbol and timeframe (either from request or strategy)
        if not resolved_symbol or not resolved_timeframe:
            raise ValidationError(
                "Symbol and timeframe must be provided or defined in strategy config"
            )

        # Get worker ID for logging
        import socket

        worker_id = os.getenv("WORKER_ID") or f"backtest-{socket.gethostname()}"

        # Call BacktestingService (will run in LOCAL mode)
        logger.info(
            f"🔵 WORKER {worker_id}: Starting backtest {resolved_symbol} {resolved_timeframe} ({request.start_date} to {request.end_date})"
        )

        result = await service.run_backtest(
            symbol=resolved_symbol,
            timeframe=resolved_timeframe,
            strategy_config_path=strategy_config_path,
            model_path=None,  # Auto-discovery
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
        )

        logger.info(
            f"🔵 WORKER {worker_id}: Operation started - operation_id={result['operation_id']}"
        )

        return BacktestStartResponse(
            success=result["success"],
            operation_id=result["operation_id"],
            status=result["status"],
            message=result["message"],
            symbol=result["symbol"],
            timeframe=result["timeframe"],
            mode="local",  # This service always runs locally
        )

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Internal error starting backtest: {str(e)}", exc_info=True)
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
