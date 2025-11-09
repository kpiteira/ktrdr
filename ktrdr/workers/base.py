"""
Worker API Base Class - Extracted from training-host-service

This module provides the complete worker infrastructure pattern that's proven
to work in training-host-service. It's extracted verbatim to ensure consistency.

Source: training-host-service/
- services/operations.py (41 lines)
- endpoints/operations.py (374 lines)
- endpoints/health.py (~50 lines)
- main.py (FastAPI setup, ~200 lines)
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from ktrdr.api.models.operations import (
    OperationListResponse,
    OperationMetricsResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class WorkerAPIBase:
    """
    Base class for all worker APIs.

    Extracted from training-host-service to provide proven working pattern.

    Provides:
    - OperationsService singleton
    - Operations proxy endpoints (/api/v1/operations/*)
    - Health endpoint (/health)
    - FastAPI app setup with CORS
    - Self-registration on startup
    """

    def __init__(
        self,
        worker_type: WorkerType,
        operation_type: OperationType,
        worker_port: int,
        backend_url: str,
    ):
        """
        Initialize worker API base.

        Args:
            worker_type: Type of worker (backtesting, training, etc.)
            operation_type: Type of operations this worker handles
            worker_port: Port for this worker service
            backend_url: URL of backend service for registration
        """
        self.worker_type = worker_type
        self.operation_type = operation_type
        self.worker_port = worker_port
        self.backend_url = backend_url

        # Worker ID (from environment or generate)
        self.worker_id = os.getenv(
            "WORKER_ID", f"{worker_type.value}-worker-{os.urandom(4).hex()}"
        )

        # Initialize OperationsService singleton (CRITICAL!)
        # Each worker MUST have its own instance for remote queryability
        self._operations_service = OperationsService()
        logger.info(f"Operations service initialized in {worker_type.value} worker")

        # Create FastAPI app
        self.app = FastAPI(
            title=f"{worker_type.value.title()} Worker Service",
            description=f"{worker_type.value.title()} worker execution service",
            version="1.0.0",
        )

        # Add CORS middleware (for Docker communication)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register common endpoints
        self._register_operations_endpoints()
        self._register_health_endpoint()
        self._register_root_endpoint()
        self._register_startup_event()

    def get_operations_service(self) -> OperationsService:
        """Get OperationsService singleton."""
        return self._operations_service

    def _register_operations_endpoints(self) -> None:
        """
        Register operations proxy endpoints.

        Source: training-host-service/endpoints/operations.py (374 lines - verbatim copy)

        These endpoints expose worker's OperationsService for backend queries.
        """

        @self.app.get(
            "/api/v1/operations/{operation_id}",
            response_model=OperationStatusResponse,
            summary="Get operation status",
        )
        async def get_operation_status(
            operation_id: str = Path(..., description="Unique operation identifier"),
            force_refresh: bool = Query(False, description="Force refresh from bridge"),
        ) -> OperationStatusResponse:
            """Get detailed status information for a specific operation."""
            try:
                logger.debug(
                    f"Getting operation status: {operation_id} (force_refresh={force_refresh})"
                )

                # Get operation from service (triggers pull from bridge if stale)
                operation = await self._operations_service.get_operation(
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

            except KeyError:
                # OperationsService raises KeyError for missing operations
                logger.warning(f"Operation not found: {operation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                ) from None
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting operation status: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get operation status: {str(e)}",
                ) from e

        @self.app.get(
            "/api/v1/operations/{operation_id}/metrics",
            response_model=OperationMetricsResponse,
            summary="Get operation metrics",
        )
        async def get_operation_metrics(
            operation_id: str = Path(..., description="Unique operation identifier"),
            cursor: int = Query(0, ge=0, description="Cursor position"),
        ) -> OperationMetricsResponse:
            """Get domain-specific metrics for an operation."""
            try:
                logger.debug(
                    f"Getting metrics for operation: {operation_id} (cursor={cursor})"
                )

                # Verify operation exists
                operation = await self._operations_service.get_operation(operation_id)

                if not operation:
                    logger.warning(f"Operation not found: {operation_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"Operation not found: {operation_id}",
                    )

                # Get incremental metrics from service
                metrics = await self._operations_service.get_operation_metrics(
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
                        "cursor": cursor,
                    },
                )

            except KeyError:
                logger.warning(f"Operation not found: {operation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                ) from None
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting operation metrics: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get operation metrics: {str(e)}",
                ) from e

        @self.app.get(
            "/api/v1/operations",
            response_model=OperationListResponse,
            summary="List operations",
        )
        async def list_operations(
            status: Optional[OperationStatus] = Query(
                None, description="Filter by status"
            ),
            operation_type: Optional[OperationType] = Query(
                None, description="Filter by type"
            ),
            limit: int = Query(10, ge=1, le=1000, description="Maximum number"),
            offset: int = Query(0, ge=0, description="Number to skip"),
            active_only: bool = Query(False, description="Show only active operations"),
        ) -> OperationListResponse:
            """List all operations with optional filtering."""
            try:
                logger.debug(
                    f"Listing operations: status={status}, type={operation_type}, active_only={active_only}"
                )

                (operations, total_count, active_count) = (
                    await self._operations_service.list_operations(
                        status=status,
                        operation_type=operation_type,
                        limit=limit,
                        offset=offset,
                        active_only=active_only,
                    )
                )

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

        @self.app.delete(
            "/api/v1/operations/{operation_id}/cancel",
            summary="Cancel operation",
        )
        async def cancel_operation(
            operation_id: str = Path(..., description="Unique operation identifier"),
            reason: Optional[str] = Query(None, description="Cancellation reason"),
        ) -> dict:
            """Cancel a running operation."""
            try:
                logger.info(
                    f"Cancelling operation: {operation_id}, reason: {reason or 'No reason provided'}"
                )

                result = await self._operations_service.cancel_operation(
                    operation_id, reason
                )

                logger.info(f"Successfully cancelled operation: {operation_id}")

                return {
                    "success": True,
                    "data": result,
                }

            except KeyError:
                logger.warning(f"Operation not found: {operation_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                ) from None
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error cancelling operation: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to cancel operation: {str(e)}",
                ) from e

    def _register_health_endpoint(self) -> None:
        """
        Register health check endpoint.

        Source: training-host-service/endpoints/health.py (adapted for generic workers)
        """

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint - reports worker busy/idle status."""
            try:
                active_ops, _, _ = await self._operations_service.list_operations(
                    operation_type=self.operation_type, active_only=True
                )

                return {
                    "healthy": True,
                    "service": f"{self.worker_type.value}-worker",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "operational",
                    "worker_status": "busy" if active_ops else "idle",
                    "current_operation": (
                        active_ops[0].operation_id if active_ops else None
                    ),
                }

            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                return {
                    "healthy": False,
                    "service": f"{self.worker_type.value}-worker",
                    "error": str(e),
                }

    def _register_root_endpoint(self) -> None:
        """Register root endpoint."""

        @self.app.get("/")
        async def root():
            return {
                "service": f"{self.worker_type.value.title()} Worker Service",
                "version": "1.0.0",
                "status": "running",
                "timestamp": datetime.utcnow().isoformat(),
                "worker_id": self.worker_id,
            }

    def _register_startup_event(self) -> None:
        """Register startup event for self-registration."""

        @self.app.on_event("startup")
        async def startup():
            logger.info(f"Starting {self.worker_type.value} worker...")
            logger.info(f"Worker ID: {self.worker_id}")
            logger.info(f"Worker port: {self.worker_port}")
            logger.info(
                f"✅ OperationsService initialized (cache_ttl={self._operations_service._cache_ttl}s)"
            )

            # Self-register with backend
            await self.self_register()

    async def self_register(self) -> None:
        """
        Register this worker with backend.

        Pattern from training-host-service worker registration.
        """
        # For now, this is a placeholder - worker registration will be implemented
        # in the actual worker classes that inherit from this base
        logger.info(
            f"Worker self-registration placeholder (worker_id: {self.worker_id})"
        )
        # TODO: Implement actual registration in Phase 1, Task 1.5
