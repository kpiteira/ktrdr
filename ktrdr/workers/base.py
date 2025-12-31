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

import asyncio
import os
import signal
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from ktrdr.api.models.operations import (
    OperationListResponse,
    OperationMetricsResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)
from ktrdr.api.models.workers import CompletedOperationReport, WorkerType
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)
from ktrdr.logging import get_logger

logger = get_logger(__name__)


# ==============================================================================
# Graceful Shutdown Exception (M6 Task 6.2)
# ==============================================================================


class GracefulShutdownError(Exception):
    """Raised when a worker receives SIGTERM and needs to shutdown gracefully.

    This exception is raised by run_with_graceful_shutdown when the shutdown
    event is detected. It signals that the operation was interrupted due to
    worker shutdown (not a failure) and a checkpoint was saved.
    """

    pass


# ==============================================================================
# Worker Request Models - Operation ID Synchronization Pattern
# ==============================================================================


class WorkerOperationMixin(BaseModel):
    """
    Mixin for worker operation requests to handle backend operation ID synchronization.

    All worker start requests should inherit from this to support the operation ID
    synchronization pattern where backend passes its operation_id as task_id.

    Pattern:
        Backend sends: {"task_id": "op_xyz_123", ...}
        Worker uses:   operation_id = request.task_id or generate_new_id()
        Worker returns: {"operation_id": "op_xyz_123", ...}

    This ensures backend and worker track the same operation with the same ID.

    Example:
        class BacktestStartRequest(WorkerOperationMixin):
            symbol: str
            timeframe: str
            # Automatically gets task_id field from mixin

        # In endpoint:
        operation_id = request.task_id or f"worker_backtest_{uuid.uuid4().hex[:12]}"
    """

    task_id: Optional[str] = Field(
        default=None,
        description="Backend's operation ID for synchronization (backend → worker)",
    )


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

        # Get OperationsService singleton (CRITICAL!)
        # All code in this worker (including domain services) shares the same instance
        # This ensures operations registered by domain services are visible to worker endpoints
        self._operations_service = get_operations_service()
        logger.info(f"Using shared OperationsService in {worker_type.value} worker")

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

        # Health check tracking for re-registration detection (Task 1.6)
        # When backend health-checks us, we record the timestamp.
        # If too much time passes without a health check, we assume backend restarted.
        self._last_health_check_received: Optional[datetime] = None

        # Re-registration monitor configuration (Task 1.7)
        self._health_check_timeout: int = (
            30  # seconds - if no health check, assume backend restarted
        )
        self._reregistration_check_interval: int = 10  # seconds - how often to check

        # Operations that completed while backend was unavailable
        # These are included in the next registration to sync state
        self._completed_operations: list[CompletedOperationReport] = []

        # Background task for monitoring health checks
        self._monitor_task: Optional[asyncio.Task] = None

        # Graceful shutdown support (M6 Task 6.1)
        # Used to detect SIGTERM and allow operations to save checkpoints
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout = 25  # seconds (Docker gives 30s grace period)

        # Current operation tracking for graceful shutdown (M6 Task 6.2)
        # Set by run_with_graceful_shutdown, cleared in finally block
        self._current_operation_id: Optional[str] = None

        # M7.5 Task 7.5.4: Reconnection polling task
        # Started when backend notifies us it's shutting down
        self._reconnection_task: Optional[asyncio.Task] = None

        # Register common endpoints
        self._register_operations_endpoints()
        self._register_health_endpoint()
        self._register_metrics_endpoint()
        self._register_root_endpoint()
        self._register_startup_event()
        self._register_shutdown_notification_endpoint()

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

                (
                    operations,
                    total_count,
                    active_count,
                ) = await self._operations_service.list_operations(
                    status=status,
                    operation_type=operation_type,
                    limit=limit,
                    offset=offset,
                    active_only=active_only,
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
            # Track when backend health-checked us (Task 1.6)
            # This enables detection of backend restart in re-registration monitor
            self._last_health_check_received = datetime.utcnow()

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
                    "error": "Health check failed - see server logs for details",
                }

    def _register_metrics_endpoint(self) -> None:
        """
        Register Prometheus metrics endpoint.

        Exposes OpenTelemetry metrics for Prometheus scraping.
        """

        @self.app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

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

            # Setup signal handlers for graceful shutdown (M6 Task 6.1)
            self._setup_signal_handlers()

            # Self-register with backend
            await self.self_register()

            # Start re-registration monitor (Task 1.7)
            await self._start_reregistration_monitor()

    def _register_shutdown_notification_endpoint(self) -> None:
        """
        Register endpoint for backend shutdown notifications.

        M7.5 Task 7.5.4: When backend is gracefully shutting down, it notifies
        workers before stopping. Workers then poll for backend availability
        and re-register immediately when it comes back up.
        """

        @self.app.post("/backend-shutdown")
        async def backend_shutdown_notification():
            """
            Receive notification that backend is shutting down.

            Triggers reconnection polling to quickly re-register
            when backend comes back up.
            """
            logger.info(
                "Received backend shutdown notification - starting reconnection polling"
            )

            # Start reconnection task, cancelling any existing one to avoid leaks
            if (
                self._reconnection_task is not None
                and not self._reconnection_task.done()
            ):
                logger.info(
                    "Cancelling existing reconnection polling task before starting new one"
                )
                self._reconnection_task.cancel()

            self._reconnection_task = asyncio.create_task(
                self._poll_for_backend_restart()
            )

            return {"acknowledged": True}

    async def _poll_for_backend_restart(
        self,
        poll_interval: float = 2.0,
        max_duration: float = 120.0,
    ) -> None:
        """
        Poll for backend restart and re-register when available.

        Called after receiving backend shutdown notification. Polls the
        registration endpoint until backend is back up and accepts our
        registration.

        Args:
            poll_interval: Seconds between poll attempts
            max_duration: Maximum seconds to poll before giving up
        """

        start_time = datetime.utcnow()
        attempt = 0

        logger.info(f"Polling for backend restart (max {max_duration}s)")

        while (datetime.utcnow() - start_time).total_seconds() < max_duration:
            attempt += 1

            try:
                # Try to register - will get 503 if still shutting down
                success = await self.self_register(max_retries=1, initial_delay=0)
                if success:
                    logger.info(
                        f"✅ Re-registered after backend restart (attempt {attempt})"
                    )
                    self._last_health_check_received = datetime.utcnow()
                    return

            except Exception as e:
                logger.debug(f"Reconnection attempt {attempt} failed: {e}")

            # Sleep at end of loop so first attempt is immediate
            await asyncio.sleep(poll_interval)

        logger.warning(
            f"Failed to reconnect after {max_duration}s - "
            "falling back to health check detection"
        )

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown (M6 Task 6.1).

        Registers SIGTERM handler that sets the shutdown event, allowing
        running operations to save checkpoints before the worker exits.
        """
        # Capture the running event loop at setup time (called from async on_startup)
        # This avoids issues with asyncio.get_event_loop() in signal handler context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def handle_sigterm(signum, frame):
            logger.info("SIGTERM received - initiating graceful shutdown")
            # Set event from signal handler context using thread-safe method
            if loop is not None:
                loop.call_soon_threadsafe(self._shutdown_event.set)
            else:
                # Fallback if no loop was captured: set event directly
                # (may not work correctly but better than silently failing)
                self._shutdown_event.set()

        signal.signal(signal.SIGTERM, handle_sigterm)
        logger.info("SIGTERM handler registered")

    async def wait_for_shutdown(self) -> bool:
        """Wait for shutdown signal with timeout.

        Returns:
            True if shutdown was signaled, False if timeout expired.
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=self._shutdown_timeout,
            )
            return True
        except asyncio.TimeoutError:
            return False

    async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
        """Save a checkpoint for the current operation (M6 Task 6.2).

        This is a hook method that subclasses should override to implement
        actual checkpoint saving. The base implementation is a no-op.

        Args:
            operation_id: The operation ID to save checkpoint for.
            checkpoint_type: Type of checkpoint ("shutdown", "failure", "periodic").
        """
        # No-op in base class - subclasses override to save actual checkpoints
        logger.debug(
            f"Base _save_checkpoint called for {operation_id} (type={checkpoint_type})"
        )

    async def _update_operation_status(
        self,
        operation_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update operation status in backend via HTTP call (M6 Task 6.3).

        Calls the backend's PATCH /operations/{operation_id}/status endpoint
        to update the operation status. Used during graceful shutdown to mark
        operations as CANCELLED before the worker exits.

        Args:
            operation_id: The operation ID to update.
            status: New status (e.g., "CANCELLED", "FAILED").
            error_message: Optional error message.

        Note:
            - Uses 5-second timeout to avoid blocking shutdown
            - Failure is logged but doesn't raise (OrphanDetector handles missed updates)
        """
        import httpx

        status_url = f"{self.backend_url}/api/v1/operations/{operation_id}/status"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.patch(
                    status_url,
                    json={
                        "status": status,
                        "error_message": error_message,
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Updated operation {operation_id} to {status}")
                else:
                    logger.warning(
                        f"Failed to update operation status: {response.status_code}"
                    )
        except Exception as e:
            logger.warning(f"Could not update operation status: {e}")
            # Continue shutdown even if status update fails
            # OrphanDetector will eventually mark it FAILED

    async def run_with_graceful_shutdown(
        self,
        operation_id: str,
        operation_coro: Any,
    ) -> Any:
        """Run operation with graceful shutdown support (M6 Task 6.2).

        Protected helper for subclasses to wrap long-running operations with
        graceful shutdown support. This is NOT exposed as an HTTP endpoint;
        subclasses should call this from their operation execution methods.

        Races the operation against the shutdown event. If SIGTERM is received
        while the operation is running, this method:
        1. Cancels the operation coroutine
        2. Calls _save_checkpoint() hook (subclasses should override)
        3. Calls _update_operation_status() to mark as CANCELLED
        4. Raises GracefulShutdownError

        Args:
            operation_id: The operation ID being executed.
            operation_coro: The operation coroutine to run.

        Returns:
            The result of the operation coroutine (if completed normally).

        Raises:
            GracefulShutdownError: If shutdown was detected during operation.
            Exception: Any exception raised by the operation.

        Example:
            class MyWorker(WorkerAPIBase):
                async def execute_work(self, op_id, params):
                    await self.run_with_graceful_shutdown(
                        op_id,
                        self._do_actual_work(params),
                    )
        """
        self._current_operation_id = operation_id

        operation_task = asyncio.create_task(operation_coro)
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())

        try:
            done, pending = await asyncio.wait(
                [operation_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if shutdown_task in done:
                # Graceful shutdown requested
                logger.info(f"Graceful shutdown - saving checkpoint for {operation_id}")

                # Cancel and await the operation task first to ensure proper cleanup
                # This MUST complete before checkpoint/status operations to avoid leaks
                operation_task.cancel()
                try:
                    await operation_task
                except asyncio.CancelledError:
                    # Expected: operation_task was cancelled by us above.
                    # The await ensures task cleanup completes before we proceed.
                    pass

                # Now save checkpoint and update status (task is fully cleaned up)
                # If these fail, the outer except block will handle it
                await self._save_checkpoint(operation_id, "shutdown")
                await self._update_operation_status(
                    operation_id,
                    "CANCELLED",
                    error_message="Graceful shutdown - checkpoint saved",
                )

                raise GracefulShutdownError("Worker shutdown requested")

            # Operation completed normally - cancel the unused shutdown task
            shutdown_task.cancel()
            try:
                await shutdown_task
            except asyncio.CancelledError:
                # Expected: shutdown_task was cancelled because operation completed first.
                # No further action needed.
                pass

            return operation_task.result()

        except Exception as e:
            if not isinstance(e, GracefulShutdownError):
                # Save failure checkpoint for non-shutdown exceptions
                await self._save_checkpoint(operation_id, "failure")
            raise
        finally:
            self._current_operation_id = None

    async def self_register(
        self,
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> bool:
        """
        Register this worker with backend's WorkerRegistry.

        Retries with exponential backoff if registration fails.

        Args:
            max_retries: Maximum number of registration attempts
            initial_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)

        Returns:
            True if registration succeeded, False otherwise
        """
        import httpx

        registration_url = f"{self.backend_url}/api/v1/workers/register"
        payload = await self._build_registration_payload()

        delay = initial_delay
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(registration_url, json=payload)

                    # 503 means backend is shutting down - retry without counting as failure
                    if response.status_code == 503:
                        logger.info(
                            f"Backend is shutting down (attempt {attempt + 1}/{max_retries}) "
                            f"- will retry in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_delay)
                        continue

                    response.raise_for_status()
                    logger.info(
                        f"✅ Worker registered successfully: {self.worker_id} "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    # Clear completed operations after successful registration
                    self._completed_operations.clear()
                    return True

            except httpx.ConnectError:
                logger.warning(
                    f"Registration attempt {attempt + 1}/{max_retries} failed: "
                    f"backend not reachable (retrying in {delay:.1f}s)"
                )
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Registration attempt {attempt + 1}/{max_retries} failed: "
                    f"HTTP {e.response.status_code} (retrying in {delay:.1f}s)"
                )
            except Exception as e:
                logger.warning(
                    f"Registration attempt {attempt + 1}/{max_retries} failed: {e} "
                    f"(retrying in {delay:.1f}s)"
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

        logger.error(
            f"❌ Worker registration failed after {max_retries} attempts - "
            f"will retry via health check monitor"
        )
        return False

    async def _build_registration_payload(self) -> dict[str, Any]:
        """
        Build the registration payload with current worker state.

        Returns:
            Dictionary containing worker registration data
        """
        # Determine worker capabilities (GPU detection for training workers)
        capabilities: dict[str, Any] = {}
        if self.worker_type.value == "training":
            # Detect GPU for training workers
            try:
                import torch

                capabilities["gpu"] = (
                    torch.cuda.is_available() or torch.backends.mps.is_available()
                )
                if capabilities["gpu"]:
                    if torch.cuda.is_available():
                        capabilities["gpu_type"] = "CUDA"
                        capabilities["gpu_count"] = torch.cuda.device_count()
                    elif torch.backends.mps.is_available():
                        capabilities["gpu_type"] = "MPS"
                        capabilities["gpu_count"] = 1
            except ImportError:
                logger.debug("PyTorch not available - no GPU detection")

        # Use WORKER_PUBLIC_BASE_URL if set (for distributed deployments),
        # otherwise fall back to container hostname (for local Docker Compose)
        public_url = os.getenv("WORKER_PUBLIC_BASE_URL")
        if public_url:
            endpoint_url = public_url
            logger.debug(f"Using WORKER_PUBLIC_BASE_URL: {endpoint_url}")
        else:
            import socket

            hostname = socket.gethostname()
            endpoint_url = f"http://{hostname}:{self.worker_port}"
            logger.debug(
                f"No WORKER_PUBLIC_BASE_URL set, using hostname: {endpoint_url}"
            )

        # Get current operation ID from OperationsService (Task 1.7)
        current_operation_id: Optional[str] = None
        try:
            active_ops, _, _ = await self._operations_service.list_operations(
                operation_type=self.operation_type, active_only=True
            )
            if active_ops:
                current_operation_id = active_ops[0].operation_id
        except Exception as e:
            logger.debug(f"Could not get current operation: {e}")

        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "endpoint_url": endpoint_url,
            "capabilities": capabilities,
            # Resilience fields for re-registration (Task 1.7)
            "current_operation_id": current_operation_id,
            "completed_operations": [
                op.model_dump() for op in self._completed_operations
            ],
        }

    def record_operation_completed(
        self,
        operation_id: str,
        status: str,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Record an operation that completed for next registration.

        When the backend is unavailable, completed operations are stored
        and reported on the next successful registration.

        Args:
            operation_id: The operation's unique identifier
            status: Final status (COMPLETED, FAILED, CANCELLED)
            result: Optional result data
            error_message: Optional error message for failed operations
        """
        report = CompletedOperationReport(
            operation_id=operation_id,
            status=status,  # type: ignore[arg-type]
            result=result,
            error_message=error_message,
            completed_at=datetime.utcnow(),
        )
        self._completed_operations.append(report)
        logger.debug(f"Recorded completed operation: {operation_id} ({status})")

    async def _start_reregistration_monitor(self) -> None:
        """Start the background task that monitors health checks."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_health_checks())
            logger.info("Re-registration monitor started")

    async def _monitor_health_checks(self) -> None:
        """
        Background task that monitors health check timing.

        If the backend hasn't health-checked this worker within the timeout
        period, we assume the backend restarted and check our registration.

        Also checks registration if no health check has ever been received,
        which handles the case where backend crashed before first health check.
        """
        while True:
            try:
                await asyncio.sleep(self._reregistration_check_interval)

                # If never received health check, still verify we're registered
                # This handles the case where backend crashed before first health check
                if self._last_health_check_received is None:
                    logger.debug(
                        "No health check received yet - verifying registration"
                    )
                    await self._ensure_registered()
                    continue

                elapsed = (
                    datetime.utcnow() - self._last_health_check_received
                ).total_seconds()

                if elapsed > self._health_check_timeout:
                    logger.warning(
                        f"No health check in {elapsed:.0f}s - checking registration"
                    )
                    await self._ensure_registered()
                    # Reset the timer after checking
                    self._last_health_check_received = datetime.utcnow()

            except asyncio.CancelledError:
                logger.info("Re-registration monitor stopped")
                break
            except Exception as e:
                logger.error(f"Error in re-registration monitor: {e}")
                await asyncio.sleep(5)  # Back off on error

    async def _ensure_registered(self) -> None:
        """
        Check if this worker is registered with the backend.

        If not registered (404), trigger re-registration with current state.
        """
        import httpx

        check_url = f"{self.backend_url}/api/v1/workers/{self.worker_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(check_url)

                if response.status_code == 200:
                    logger.debug("Worker is still registered")
                    return

                if response.status_code == 404:
                    logger.warning("Worker not found in registry - re-registering")
                    await self.self_register()
                else:
                    logger.warning(
                        f"Unexpected response checking registration: {response.status_code}"
                    )
        except Exception as e:
            logger.error(f"Error checking registration: {e}")

    # ==========================================================================
    # Checkpoint Infrastructure - Common patterns for all workers
    # ==========================================================================

    async def adopt_and_start_operation(self, operation_id: str) -> None:
        """
        Adopt an operation from database and transition to RUNNING.

        This is the correct pattern for resume scenarios where a worker may be
        resuming an operation it didn't originally create. The operation exists
        in the database but may not be in this worker's local cache.

        Pattern:
        1. adopt_operation() - Load from DB into cache if not present
        2. start_operation() - Transition to RUNNING and register task

        Args:
            operation_id: The operation to adopt and start

        Raises:
            DataError: If operation not found in database
        """
        # Adopt operation (loads from DB if not in cache)
        await self._operations_service.adopt_operation(operation_id)

        # Create dummy task and start operation
        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await self._operations_service.start_operation(operation_id, dummy_task)
        logger.info(f"Adopted and started operation {operation_id} for resume")

    def create_checkpoint_callback(
        self,
        operation_id: str,
        checkpoint_service: Any,
        checkpoint_policy: Any,
        state_builder: Any,
        main_loop: asyncio.AbstractEventLoop,
        last_checkpoint_state: dict[str, Any],
        artifacts_builder: Any = None,
    ) -> Any:
        """
        Create a checkpoint callback with proper event loop handling.

        This factory creates checkpoint callbacks that correctly handle the
        threading complexity of saving checkpoints from within worker loops
        that may run in thread pools (via asyncio.to_thread).

        The callback uses run_coroutine_threadsafe() to schedule checkpoint
        saves on the main event loop, avoiding "Future attached to different
        loop" errors that occur when creating new event loops in threads.

        Args:
            operation_id: Operation identifier for checkpoint
            checkpoint_service: Service for saving checkpoints
            checkpoint_policy: Policy determining when to checkpoint
            state_builder: Callable that builds checkpoint state from kwargs
            main_loop: The main asyncio event loop (capture before entering thread)
            last_checkpoint_state: Dict to store latest state for cancellation checkpoints
            artifacts_builder: Optional callable to build artifacts (for training)

        Returns:
            A callback function suitable for use in worker loops

        Example:
            main_loop = asyncio.get_running_loop()
            last_state = {}

            def my_state_builder(**kwargs):
                return build_my_checkpoint_state(kwargs["engine"], kwargs["bar_index"])

            callback = self.create_checkpoint_callback(
                operation_id=operation_id,
                checkpoint_service=checkpoint_service,
                checkpoint_policy=checkpoint_policy,
                state_builder=my_state_builder,
                main_loop=main_loop,
                last_checkpoint_state=last_state,
            )

            # Use in loop
            engine.run(checkpoint_callback=callback)
        """

        def checkpoint_callback(**kwargs):
            """Checkpoint callback with proper event loop handling."""
            # Always update last state for potential cancellation checkpoint
            last_checkpoint_state.update(kwargs)

            # Get the unit value for checkpoint policy (epoch for training, bar_index for backtest)
            unit_value = kwargs.get("epoch") or kwargs.get("bar_index")
            if unit_value is None:
                logger.warning("Checkpoint callback missing epoch or bar_index")
                return

            # Check if we should save a periodic checkpoint
            if checkpoint_policy.should_checkpoint(unit_value):
                try:
                    # Build checkpoint state
                    state = state_builder(**kwargs)

                    # Build artifacts if builder provided (for training)
                    artifacts = None
                    if artifacts_builder:
                        artifacts = artifacts_builder(**kwargs)

                    # Schedule checkpoint save on main event loop
                    # This avoids "Future attached to different loop" errors
                    future = asyncio.run_coroutine_threadsafe(
                        checkpoint_service.save_checkpoint(
                            operation_id=operation_id,
                            checkpoint_type="periodic",
                            state=state.to_dict(),
                            artifacts=artifacts,
                        ),
                        main_loop,
                    )
                    # Wait for completion with timeout
                    future.result(timeout=30.0)
                    checkpoint_policy.record_checkpoint(unit_value)
                    logger.info(
                        f"Periodic checkpoint saved for {operation_id} at unit {unit_value}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to save periodic checkpoint: {e}")

        return checkpoint_callback

    async def save_cancellation_checkpoint(
        self,
        operation_id: str,
        checkpoint_service: Any,
        last_checkpoint_state: dict[str, Any],
        state_builder: Any,
        artifacts_builder: Any = None,
    ) -> bool:
        """
        Save a checkpoint when an operation is cancelled.

        This is a common pattern for all workers: when cancellation occurs,
        save the latest state so the operation can be resumed later.

        Args:
            operation_id: Operation identifier
            checkpoint_service: Service for saving checkpoints
            last_checkpoint_state: Dict containing the latest state from checkpoint callback
            state_builder: Callable that builds checkpoint state from the stored state
            artifacts_builder: Optional callable to build artifacts

        Returns:
            True if checkpoint was saved, False otherwise
        """
        if not last_checkpoint_state:
            logger.warning(
                f"No checkpoint state available for cancellation: {operation_id}"
            )
            return False

        try:
            state = state_builder(**last_checkpoint_state)
            artifacts = None
            if artifacts_builder:
                artifacts = artifacts_builder(**last_checkpoint_state)

            await checkpoint_service.save_checkpoint(
                operation_id=operation_id,
                checkpoint_type="cancellation",
                state=state.to_dict(),
                artifacts=artifacts,
            )

            unit_value = last_checkpoint_state.get(
                "epoch"
            ) or last_checkpoint_state.get("bar_index")
            logger.info(
                f"Cancellation checkpoint saved for {operation_id} at unit {unit_value}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to save cancellation checkpoint: {e}")
            return False
