"""
Remote Backtesting API - FastAPI Application for Remote Container.

This module provides a FastAPI application that runs BacktestingService in LOCAL mode
within a remote container. The backend treats this as "remote", but this service
itself runs locally (from its own perspective).

Key Design:
- Runs BacktestingService in LOCAL mode (not remote mode!)
- Exposes same OperationsService endpoints as backend
- Backend proxies to this service via OperationServiceProxy
- Two-level caching: backend cache + this service's cache

Usage:
    # Run directly for development
    uvicorn ktrdr.backtesting.remote_api:app --host 0.0.0.0 --port 5003

    # Or via Docker
    docker run -p 5003:5003 ktrdr-backend uvicorn ktrdr.backtesting.remote_api:app ...
"""

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ktrdr.api.models.backtesting import BacktestStartRequest, BacktestStartResponse
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.backtesting.backtesting_service import BacktestingService

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
_operations_service = None
_backtesting_service = None


def get_backtest_service() -> BacktestingService:
    """Get backtesting service singleton."""
    global _backtesting_service
    if _backtesting_service is None:
        _backtesting_service = BacktestingService()
    return _backtesting_service


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _operations_service

    logger.info("=" * 80)
    logger.info("🚀 Starting Backtesting Remote Service")
    logger.info("=" * 80)

    # Force local mode (this service should never use remote mode)
    os.environ["USE_REMOTE_BACKTEST_SERVICE"] = "false"

    # Initialize OperationsService
    _operations_service = get_operations_service()
    logger.info(
        f"✅ OperationsService initialized (cache_ttl={_operations_service._cache_ttl}s)"
    )

    # Initialize BacktestingService (will run in local mode)
    backtest_service = get_backtest_service()
    logger.info(f"✅ BacktestingService initialized (mode: {'remote' if backtest_service._use_remote else 'local'})")

    logger.info("")
    logger.info("📡 Available Endpoints:")
    logger.info("  POST /backtests/start               - Start backtest (domain-specific)")
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
    backtest_service = get_backtest_service()
    return {
        "service": "Backtesting Remote Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "local",  # This service always runs in local mode
        "note": "Runs BacktestingService in LOCAL mode (backend treats this as remote)",
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "healthy": True,
        "service": "backtest-remote",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational",
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
        HTTPException: 400 for validation errors, 500 for internal errors
    """
    try:
        service = get_backtest_service()

        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Build strategy config path
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

        # Call BacktestingService (will run in LOCAL mode)
        logger.info(f"Starting backtest: {request.symbol} {request.timeframe} ({request.start_date} to {request.end_date})")

        result = await service.run_backtest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            strategy_config_path=strategy_config_path,
            model_path=None,  # Auto-discovery
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
        )

        logger.info(f"Backtest started: operation_id={result['operation_id']}")

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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Internal error starting backtest: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# Operations Endpoints (Generic - Proxy to OperationsService)
# ============================================================================


@app.get("/api/v1/operations")
async def list_operations(
    operation_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """
    List operations (same as backend OperationsService).

    This allows the backend to query all operations running on this remote service.
    """
    try:
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
        raise HTTPException(status_code=500, detail=str(e))


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
        operation = await _operations_service.get_operation(
            operation_id=operation_id,
            force_refresh=force_refresh,
        )

        if operation is None:
            raise HTTPException(status_code=404, detail=f"Operation not found: {operation_id}")

        return operation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        metrics, new_cursor = await _operations_service.get_operation_metrics(
            operation_id=operation_id,
            cursor=cursor,
        )

        return {
            "metrics": metrics,
            "cursor": new_cursor,
        }

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Operation not found: {operation_id}")
    except Exception as e:
        logger.error(f"Error getting metrics for {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        result = await _operations_service.cancel_operation(operation_id=operation_id)
        return result

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Operation not found: {operation_id}")
    except Exception as e:
        logger.error(f"Error cancelling operation {operation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
