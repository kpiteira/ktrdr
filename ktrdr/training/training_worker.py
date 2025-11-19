"""
Training Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but uses
WorkerAPIBase for common infrastructure.
"""

import asyncio
import os
import uuid
from typing import Any, Optional

from fastapi import FastAPI
from opentelemetry import trace
from pydantic import Field

from ktrdr.api.models.backtesting import ResumeRequest
from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.checkpoint.service import CheckpointService

# Note: TrainingProgressBridge requires TrainingOperationContext which is complex
# For now, we'll use direct progress callbacks instead
from ktrdr.logging import get_logger
from ktrdr.monitoring.setup import instrument_app, setup_monitoring
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

logger = get_logger(__name__)

# Get worker ID for unique service identification
worker_id = os.getenv("WORKER_ID", uuid.uuid4().hex[:8])

# Setup monitoring BEFORE creating worker
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
setup_monitoring(
    service_name=f"ktrdr-training-worker-{worker_id}",
    otlp_endpoint=otlp_endpoint,
    console_output=os.getenv("ENVIRONMENT") == "development",
)


class TrainingStartRequest(WorkerOperationMixin):
    """Request to start training (following training-host pattern)."""

    # task_id inherited from WorkerOperationMixin
    strategy_yaml: str = Field(description="Strategy configuration as YAML string")
    # Runtime overrides (optional)
    symbols: Optional[list[str]] = Field(
        default=None, description="Override symbols from strategy"
    )
    timeframes: Optional[list[str]] = Field(
        default=None, description="Override timeframes from strategy"
    )
    start_date: Optional[str] = Field(
        default=None, description="Override start date (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        default=None, description="Override end date (YYYY-MM-DD)"
    )


class TrainingWorker(WorkerAPIBase):
    """Training worker using WorkerAPIBase."""

    def __init__(
        self,
        worker_port: int = 5002,
        backend_url: str = "http://backend:8000",
    ):
        """Initialize training worker."""
        # Use TRAINING worker type (capabilities determine GPU support)
        worker_type = WorkerType.TRAINING

        super().__init__(
            worker_type=worker_type,
            operation_type=OperationType.TRAINING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Initialize CheckpointService for autonomous checkpoint loading
        self._checkpoint_service = CheckpointService()
        logger.info("CheckpointService initialized in training worker")

        # Register domain-specific endpoint: /training/start
        @self.app.post("/training/start")
        async def start_training(request: TrainingStartRequest):
            """
            Start a training operation.

            Follows training-host-service pattern:
            - Accepts task_id from backend for ID synchronization
            - Returns operation_id back to backend
            - Starts work in background, returns immediately
            """
            # Use backend's task_id if provided, generate if not
            operation_id = request.task_id or f"worker_training_{uuid.uuid4().hex[:12]}"

            # Start work in background (non-blocking!) - training-host pattern
            asyncio.create_task(self._execute_training_work(operation_id, request))

            return {
                "success": True,
                "operation_id": operation_id,  # Standard field (WorkerAPIBase pattern)
                "status": "started",
            }

        # Register domain-specific endpoint: /training/resume
        @self.app.post("/training/resume")
        async def resume_training(request: ResumeRequest):
            """
            Resume a training operation from checkpoint.

            Worker autonomy pattern:
            - Receives only operation IDs from backend (minimal payload)
            - Loads checkpoint autonomously from database
            - Returns operation_id back to backend
            - Starts work in background, returns immediately
            """
            # Use backend's task_id
            operation_id = request.task_id

            # Start resume work in background (non-blocking!)
            asyncio.create_task(
                self._execute_resume_training_work(operation_id, request)
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "started",
            }

    async def _execute_training_work(
        self,
        operation_id: str,
        request: TrainingStartRequest,
    ) -> dict[str, Any]:
        """
        Execute training work.

        Follows training-host-service pattern:
        1. Create operation in worker's OperationsService
        2. Create and register progress bridge
        3. Execute actual work (TrainingManager)
        4. Complete operation
        """

        # 1. Create operation in worker's OperationsService
        from datetime import datetime

        await self._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol=",".join(request.symbols) if request.symbols else "multi",
                timeframe=(
                    ",".join(request.timeframes) if request.timeframes else "multi"
                ),
                mode="training",
                start_date=(
                    datetime.fromisoformat(request.start_date)
                    if request.start_date
                    else datetime(2020, 1, 1)
                ),
                end_date=(
                    datetime.fromisoformat(request.end_date)
                    if request.end_date
                    else datetime.now()
                ),
                parameters={
                    "strategy_yaml": request.strategy_yaml[
                        :100
                    ],  # Truncated for metadata
                    "symbols": request.symbols,
                    "timeframes": request.timeframes,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "worker_id": self.worker_id,
                },
            ),
        )

        # 2. Mark operation as RUNNING (CRITICAL for progress reporting!)
        # Create a dummy task - actual work happens below
        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await self._operations_service.start_operation(operation_id, dummy_task)
        logger.info(f"Marked operation {operation_id} as RUNNING")

        # 3. Execute actual work (LocalTrainingOrchestrator - direct execution)
        try:
            # Use LocalTrainingOrchestrator directly - worker IS the execution environment
            import tempfile
            from pathlib import Path

            from ktrdr.api.services.training.context import build_training_context
            from ktrdr.api.services.training.local_orchestrator import (
                LocalTrainingOrchestrator,
            )
            from ktrdr.api.services.training.progress_bridge import (
                TrainingProgressBridge,
            )
            from ktrdr.training.model_storage import ModelStorage

            # Get cancellation token
            cancellation_token = self._operations_service.get_cancellation_token(
                operation_id
            )

            # Extract strategy name from YAML content FIRST
            strategy_name = "neuro_mean_reversion"  # Default
            for line in request.strategy_yaml.split("\n"):
                if line.strip().startswith("name:"):
                    strategy_name = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break

            # Create temp directory and file with CORRECT strategy name
            # This is critical: build_training_context() looks for {strategy_name}.yaml
            temp_dir = tempfile.mkdtemp()
            temp_yaml_path = Path(temp_dir) / f"{strategy_name}.yaml"

            try:
                # Write YAML to temp file with correct name
                with open(temp_yaml_path, "w") as f:
                    f.write(request.strategy_yaml)

                # Build training context (will find the file now!)
                context = build_training_context(
                    operation_id=operation_id,
                    strategy_name=strategy_name,
                    symbols=request.symbols or ["AAPL"],
                    timeframes=request.timeframes or ["1d"],
                    start_date=request.start_date,
                    end_date=request.end_date,
                    detailed_analytics=False,
                    use_host_service=False,  # Local execution on worker
                    strategy_search_paths=[Path(temp_dir)],
                )

                # Create progress bridge and register it (CRITICAL for progress reporting!)
                # TrainingProgressBridge requires either progress_manager or update_progress_callback
                # We use pull-based progress via OperationsService, so provide a no-op callback
                def noop_callback(**kwargs):
                    pass

                bridge = TrainingProgressBridge(
                    context=context,
                    update_progress_callback=noop_callback,
                    cancellation_token=cancellation_token,
                )
                self._operations_service.register_local_bridge(operation_id, bridge)
                logger.info(f"Registered training bridge for operation {operation_id}")

                # Create model storage
                model_storage = ModelStorage()

                # Create orchestrator
                orchestrator = LocalTrainingOrchestrator(
                    context=context,
                    progress_bridge=bridge,
                    cancellation_token=cancellation_token,
                    model_storage=model_storage,
                )

                # Run training (async)
                result = await orchestrator.run()
            finally:
                # Clean up temp directory
                import shutil

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

            # 4. Complete operation
            await self._operations_service.complete_operation(
                operation_id,
                result,
            )

            logger.info(
                f"Training completed for operation {operation_id}: "
                f"model_path={result.get('model_path', 'unknown')}"
            )

            return {
                "model_path": result.get("model_path"),
                "training_metrics": result.get("training_metrics", {}),
                "test_metrics": result.get("test_metrics", {}),
            }

        except Exception as e:
            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise

    async def _execute_resume_training_work(
        self,
        operation_id: str,
        request: ResumeRequest,
    ) -> dict[str, Any]:
        """
        Execute resumed training work from checkpoint.

        Worker autonomy pattern:
        1. Load checkpoint from database (autonomous)
        2. Load original operation metadata
        3. Extract parameters and rebuild request
        4. Call shared training execution logic

        Args:
            operation_id: New operation ID for resumed training
            request: Resume request with original_operation_id

        Returns:
            Result dictionary
        """
        try:
            # 1. Load checkpoint autonomously from database
            checkpoint = self._checkpoint_service.load_checkpoint(
                request.original_operation_id
            )

            if checkpoint is None:
                error_msg = f"No checkpoint found for {request.original_operation_id}"
                logger.error(error_msg)
                await self._operations_service.fail_operation(operation_id, error_msg)
                raise ValueError(error_msg)

            logger.info(
                f"Loaded checkpoint for {request.original_operation_id}: "
                f"type={checkpoint.get('checkpoint_type')}, "
                f"epoch={checkpoint.get('epoch')}"
            )

            # 2. Load original operation metadata to get parameters
            original_operation = await self._operations_service.get_operation(
                request.original_operation_id
            )

            if original_operation is None:
                error_msg = (
                    f"Original operation not found: {request.original_operation_id}"
                )
                logger.error(error_msg)
                await self._operations_service.fail_operation(operation_id, error_msg)
                raise ValueError(error_msg)

            # 3. Extract parameters and rebuild TrainingStartRequest
            metadata = original_operation.metadata
            params = metadata.parameters

            # Rebuild request from original operation metadata + checkpoint state
            resume_request = TrainingStartRequest(
                task_id=operation_id,
                strategy_yaml=params.get("strategy_yaml", ""),
                symbols=params.get("symbols"),
                timeframes=params.get("timeframes"),
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
            )

            # 4. Execute training work with checkpoint state
            # NOTE: In a full implementation, we'd pass checkpoint_state to the orchestrator
            # For now, execute as fresh start (orchestrator resume logic is separate task)
            logger.warning(
                f"Resume executing as fresh start for {operation_id}. "
                "Orchestrator-level checkpoint resume not yet implemented."
            )

            result = await self._execute_training_work(operation_id, resume_request)

            return result

        except Exception as e:
            logger.error(f"Resume training failed for {operation_id}: {e}")
            await self._operations_service.fail_operation(operation_id, str(e))
            raise


# Create worker instance
worker = TrainingWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5002")),
    backend_url=os.getenv("KTRDR_API_URL", "http://backend:8000"),
)

# Auto-instrument with OpenTelemetry
instrument_app(worker.app)

# Add worker-specific span attributes (for tracing)
tracer = trace.get_tracer(__name__)
# Note: Worker attributes will be added during actual request handling
# The worker_id, worker_type, and capabilities are already tracked in WorkerAPIBase

# Export FastAPI app for uvicorn
app: FastAPI = worker.app
