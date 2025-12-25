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

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.async_infrastructure.cancellation import CancellationError

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

    # Default checkpoint configuration (can be overridden via environment)
    checkpoint_epoch_interval: int = 10
    checkpoint_time_interval: int = 300  # 5 minutes

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

        # Load checkpoint configuration from environment
        self.checkpoint_epoch_interval = int(
            os.getenv("CHECKPOINT_EPOCH_INTERVAL", "10")
        )
        self.checkpoint_time_interval = int(
            os.getenv("CHECKPOINT_TIME_INTERVAL_SECONDS", "300")
        )
        self._checkpoint_dir = os.getenv("CHECKPOINT_DIR", "/app/data/checkpoints")

        # Register domain-specific endpoint
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

        # Initialize variables for checkpoint handling (accessible in except blocks)
        last_checkpoint_state: dict = {}
        checkpoint_service = self.get_checkpoint_service()
        original_request = {
            "strategy_yaml": request.strategy_yaml[:100],  # Truncate
            "symbols": request.symbols,
            "timeframes": request.timeframes,
            "start_date": request.start_date,
            "end_date": request.end_date,
        }

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

            # Extract strategy name from YAML content using proper YAML parsing
            import yaml

            strategy_name = "neuro_mean_reversion"  # Default
            try:
                yaml_content = yaml.safe_load(request.strategy_yaml)
                if yaml_content and "name" in yaml_content:
                    strategy_name = yaml_content["name"]
            except yaml.YAMLError:
                # Fallback: if YAML parsing fails, use default
                logger.warning("Failed to parse strategy YAML, using default name")

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

                # Create checkpoint policy for this operation
                from ktrdr.checkpoint import CheckpointPolicy

                checkpoint_policy = CheckpointPolicy(
                    unit_interval=self.checkpoint_epoch_interval,
                    time_interval_seconds=self.checkpoint_time_interval,
                )

                # Create checkpoint callback (runs in ModelTrainer's training loop)
                def checkpoint_callback(**kwargs):
                    """Called after each epoch with model, optimizer, scheduler, trainer."""
                    from ktrdr.training.checkpoint_builder import (
                        build_training_checkpoint_artifacts,
                        build_training_checkpoint_state,
                    )

                    epoch = kwargs["epoch"]
                    model = kwargs["model"]
                    optimizer = kwargs["optimizer"]
                    scheduler = kwargs.get("scheduler")
                    trainer = kwargs["trainer"]

                    # Store latest state for potential cancellation/failure checkpoint
                    last_checkpoint_state["epoch"] = epoch
                    last_checkpoint_state["model"] = model
                    last_checkpoint_state["optimizer"] = optimizer
                    last_checkpoint_state["scheduler"] = scheduler
                    last_checkpoint_state["trainer"] = trainer

                    # Check if we should save a periodic checkpoint
                    if checkpoint_policy.should_checkpoint(epoch):
                        try:
                            # Build state and artifacts
                            state = build_training_checkpoint_state(
                                trainer, epoch, original_request
                            )
                            artifacts = build_training_checkpoint_artifacts(
                                model,
                                optimizer,
                                scheduler,
                                trainer.best_model_state,
                            )

                            # Run async checkpoint save from sync context
                            # Since we're in a thread pool, we need to run in the event loop
                            import asyncio

                            loop = asyncio.new_event_loop()
                            try:
                                loop.run_until_complete(
                                    checkpoint_service.save_checkpoint(
                                        operation_id=operation_id,
                                        checkpoint_type="periodic",
                                        state=state.to_dict(),
                                        artifacts=artifacts,
                                    )
                                )
                                checkpoint_policy.record_checkpoint(epoch)
                                logger.info(
                                    f"Periodic checkpoint saved for {operation_id} at epoch {epoch}"
                                )
                            finally:
                                loop.close()

                        except Exception as e:
                            logger.warning(f"Failed to save periodic checkpoint: {e}")

                # Create orchestrator with checkpoint callback
                orchestrator = LocalTrainingOrchestrator(
                    context=context,
                    progress_bridge=bridge,
                    cancellation_token=cancellation_token,
                    model_storage=model_storage,
                    checkpoint_callback=checkpoint_callback,
                )

                # Run training (async)
                result = await orchestrator.run()
            finally:
                # Clean up temp directory
                import shutil

                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

            # 4. Delete checkpoint on successful completion
            try:
                await checkpoint_service.delete_checkpoint(operation_id)
                logger.info(
                    f"Checkpoint deleted after successful completion: {operation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to delete checkpoint on success: {e}")

            # 5. Complete operation
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

        except CancellationError:
            # Save cancellation checkpoint if we have state
            if last_checkpoint_state and "trainer" in last_checkpoint_state:
                try:
                    from ktrdr.training.checkpoint_builder import (
                        build_training_checkpoint_artifacts,
                        build_training_checkpoint_state,
                    )

                    state = build_training_checkpoint_state(
                        last_checkpoint_state["trainer"],
                        last_checkpoint_state["epoch"],
                        original_request,
                    )
                    artifacts = build_training_checkpoint_artifacts(
                        last_checkpoint_state["model"],
                        last_checkpoint_state["optimizer"],
                        last_checkpoint_state.get("scheduler"),
                        last_checkpoint_state["trainer"].best_model_state,
                    )

                    await checkpoint_service.save_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type="cancellation",
                        state=state.to_dict(),
                        artifacts=artifacts,
                    )
                    logger.info(
                        f"Cancellation checkpoint saved for {operation_id} at epoch {last_checkpoint_state['epoch']}"
                    )
                except Exception as cp_err:
                    logger.warning(f"Failed to save cancellation checkpoint: {cp_err}")

            logger.info(f"Training operation {operation_id} cancelled")
            return {
                "status": "cancelled",
                "operation_id": operation_id,
            }

        except Exception as e:
            # Save failure checkpoint if we have state
            if last_checkpoint_state and "trainer" in last_checkpoint_state:
                try:
                    from ktrdr.training.checkpoint_builder import (
                        build_training_checkpoint_artifacts,
                        build_training_checkpoint_state,
                    )

                    state = build_training_checkpoint_state(
                        last_checkpoint_state["trainer"],
                        last_checkpoint_state["epoch"],
                        original_request,
                    )
                    artifacts = build_training_checkpoint_artifacts(
                        last_checkpoint_state["model"],
                        last_checkpoint_state["optimizer"],
                        last_checkpoint_state.get("scheduler"),
                        last_checkpoint_state["trainer"].best_model_state,
                    )

                    await checkpoint_service.save_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type="failure",
                        state=state.to_dict(),
                        artifacts=artifacts,
                    )
                    logger.info(
                        f"Failure checkpoint saved for {operation_id} at epoch {last_checkpoint_state['epoch']}"
                    )
                except Exception as cp_err:
                    logger.warning(f"Failed to save failure checkpoint: {cp_err}")

            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise

    def get_checkpoint_service(self):
        """Get a CheckpointService instance for this worker.

        Uses the worker's database session factory and configured artifacts directory.

        Returns:
            CheckpointService: Service for checkpoint CRUD operations.
        """
        from ktrdr.api.database import get_session_factory
        from ktrdr.checkpoint import CheckpointService

        return CheckpointService(
            session_factory=get_session_factory(),
            artifacts_dir=self._checkpoint_dir,
        )


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
