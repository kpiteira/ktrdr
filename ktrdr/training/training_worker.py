"""
Training Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but uses
WorkerAPIBase for common infrastructure.
"""

import asyncio
import os
import uuid
from typing import TYPE_CHECKING, Any, Optional

from fastapi import FastAPI

if TYPE_CHECKING:
    from ktrdr.training.checkpoint_restore import TrainingResumeContext
from opentelemetry import trace
from pydantic import Field

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.config.settings import get_checkpoint_settings

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
    strategy_path: Optional[str] = Field(
        default=None,
        description="Path to strategy file (relative like 'strategies/test.yaml'). "
        "Used for checkpoint storage instead of full YAML to avoid DB truncation.",
    )
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


class TrainingResumeRequest(WorkerOperationMixin):
    """Request to resume training from checkpoint.

    Unlike TrainingStartRequest, operation_id is required since we're
    resuming an existing operation (not creating a new one).
    """

    operation_id: str = Field(description="Operation ID to resume")


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

        # Load checkpoint configuration from centralized settings
        checkpoint_settings = get_checkpoint_settings()
        self.checkpoint_epoch_interval = checkpoint_settings.epoch_interval
        self.checkpoint_time_interval = checkpoint_settings.time_interval_seconds
        self._checkpoint_dir = checkpoint_settings.dir

        # M6: Initialize last checkpoint state for graceful shutdown
        # This is populated by epoch callbacks and used by _save_checkpoint on SIGTERM
        self._last_checkpoint_state: dict | None = None

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

            # Start work in background with graceful shutdown support (M6)
            asyncio.create_task(
                self._run_training_with_graceful_shutdown(operation_id, request)
            )

            return {
                "success": True,
                "operation_id": operation_id,  # Standard field (WorkerAPIBase pattern)
                "status": "started",
            }

        @self.app.post("/training/resume")
        async def resume_training(request: TrainingResumeRequest):
            """
            Resume a training operation from checkpoint.

            Follows same pattern as start_training:
            - Loads checkpoint to get resume context
            - Returns immediately with operation info
            - Starts resumed training in background
            """
            from fastapi import HTTPException

            from ktrdr.training.checkpoint_restore import (
                CheckpointCorruptedError,
                CheckpointNotFoundError,
            )

            operation_id = request.operation_id

            try:
                # Load checkpoint and create resume context
                resume_context = await self.restore_from_checkpoint(operation_id)

                # Start resumed training in background with graceful shutdown support (M6)
                asyncio.create_task(
                    self._run_resumed_training_with_graceful_shutdown(
                        operation_id, resume_context
                    )
                )

                return {
                    "success": True,
                    "operation_id": operation_id,
                    "status": "started",
                    "resumed_from_epoch": resume_context.start_epoch
                    - 1,  # Report checkpoint epoch
                }
            except CheckpointNotFoundError as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"No checkpoint found for operation {operation_id}",
                ) from e
            except CheckpointCorruptedError as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Checkpoint corrupted: {str(e)}",
                ) from e

    async def _run_training_with_graceful_shutdown(
        self,
        operation_id: str,
        request: TrainingStartRequest,
    ) -> None:
        """
        Wrapper that runs training with graceful shutdown support (M6).

        Uses WorkerAPIBase.run_with_graceful_shutdown to race training
        against SIGTERM. On shutdown, saves checkpoint and updates status.
        """
        from ktrdr.workers.base import GracefulShutdownError

        try:
            await self.run_with_graceful_shutdown(
                operation_id,
                self._execute_training_work(operation_id, request),
            )
        except GracefulShutdownError:
            logger.info(f"Training {operation_id} interrupted by graceful shutdown")
            # Checkpoint already saved by run_with_graceful_shutdown via _save_checkpoint
            # Status already updated to CANCELLED
        except Exception as e:
            logger.error(f"Training {operation_id} failed: {e}")
            raise  # Re-raise to ensure caller knows training failed

    async def _run_resumed_training_with_graceful_shutdown(
        self,
        operation_id: str,
        resume_context: "TrainingResumeContext",
    ) -> None:
        """
        Wrapper that runs resumed training with graceful shutdown support (M6).
        """
        from ktrdr.workers.base import GracefulShutdownError

        try:
            await self.run_with_graceful_shutdown(
                operation_id,
                self._execute_resumed_training(operation_id, resume_context),
            )
        except GracefulShutdownError:
            logger.info(
                f"Resumed training {operation_id} interrupted by graceful shutdown"
            )
        except Exception as e:
            logger.error(f"Resumed training {operation_id} failed: {e}")
            raise  # Re-raise to ensure caller knows training failed

    async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
        """
        Save checkpoint for graceful shutdown (M6 override).

        Called by WorkerAPIBase.run_with_graceful_shutdown when SIGTERM received.
        Uses the last checkpoint state captured during training.
        """
        # _last_checkpoint_state is initialized to None in __init__ and populated
        # by epoch callbacks during training
        if not self._last_checkpoint_state:
            logger.warning(f"No checkpoint state available to save for {operation_id}")
            return

        state = self._last_checkpoint_state
        if state.get("trainer") is None:
            logger.warning(
                f"Incomplete checkpoint state for {operation_id}, skipping save"
            )
            return

        try:
            from ktrdr.training.checkpoint_builder import (
                build_training_checkpoint_artifacts,
                build_training_checkpoint_state,
            )

            checkpoint_state = build_training_checkpoint_state(
                state["trainer"],
                state["epoch"],
                state.get("original_request", {}),
            )
            artifacts = build_training_checkpoint_artifacts(
                state["model"],
                state["optimizer"],
                state.get("scheduler"),
                state["trainer"].best_model_state,
            )

            checkpoint_service = self.get_checkpoint_service()
            await checkpoint_service.save_checkpoint(
                operation_id=operation_id,
                checkpoint_type=checkpoint_type,
                state=checkpoint_state.to_dict(),
                artifacts=artifacts,
            )
            logger.info(
                f"Shutdown checkpoint saved for {operation_id} at epoch {state['epoch']}"
            )
        except Exception as e:
            logger.error(f"Failed to save shutdown checkpoint: {e}")

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
        # Store strategy_path (not content) to avoid DB truncation issues (Task 4.8)
        # On resume, we read the strategy from disk using this path
        original_request = {
            "strategy_path": request.strategy_path,  # Path to read from on resume
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

                # Capture main event loop for checkpoint callback
                main_loop = asyncio.get_running_loop()

                # Import checkpoint builders
                from ktrdr.training.checkpoint_builder import (
                    build_training_checkpoint_artifacts,
                    build_training_checkpoint_state,
                )

                # Create state builder closure that captures original_request
                def training_state_builder(**kwargs):
                    return build_training_checkpoint_state(
                        kwargs["trainer"], kwargs["epoch"], original_request
                    )

                # Create artifacts builder closure
                def training_artifacts_builder(**kwargs):
                    return build_training_checkpoint_artifacts(
                        kwargs["model"],
                        kwargs["optimizer"],
                        kwargs.get("scheduler"),
                        kwargs["trainer"].best_model_state,
                    )

                # Use shared checkpoint callback infrastructure
                # This fixes the "Future attached to different loop" bug by using
                # run_coroutine_threadsafe instead of asyncio.new_event_loop()
                base_callback = self.create_checkpoint_callback(
                    operation_id=operation_id,
                    checkpoint_service=checkpoint_service,
                    checkpoint_policy=checkpoint_policy,
                    state_builder=training_state_builder,
                    main_loop=main_loop,
                    last_checkpoint_state=last_checkpoint_state,
                    artifacts_builder=training_artifacts_builder,
                )

                # Wrap callback to also store to instance for graceful shutdown (M6)
                def checkpoint_callback(**kwargs):
                    # Store to instance for _save_checkpoint hook (M6 graceful shutdown)
                    self._last_checkpoint_state = {
                        **kwargs,
                        "original_request": original_request,
                    }
                    # Call base callback for periodic checkpoint logic
                    base_callback(**kwargs)

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

    async def restore_from_checkpoint(
        self, operation_id: str
    ) -> "TrainingResumeContext":
        """Restore training context from a checkpoint.

        Loads the checkpoint for the given operation and creates a
        TrainingResumeContext that can be used to resume training.

        Args:
            operation_id: The operation ID to restore.

        Returns:
            TrainingResumeContext with all state needed to resume.

        Raises:
            CheckpointNotFoundError: If no checkpoint exists for the operation.
            CheckpointCorruptedError: If required artifacts are missing or invalid.
        """
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        checkpoint_service = self.get_checkpoint_service()
        return await restore_from_checkpoint(
            checkpoint_service=checkpoint_service,
            operation_id=operation_id,
        )

    async def _execute_resumed_training(
        self,
        operation_id: str,
        resume_context: "TrainingResumeContext",
    ) -> dict[str, Any]:
        """
        Execute resumed training from checkpoint.

        Similar to _execute_training_work but:
        - Uses resume_context instead of creating new operation
        - Starts from checkpoint epoch (not epoch 0)
        - Restores model/optimizer state before training

        Uses shared infrastructure from WorkerAPIBase:
        - adopt_and_start_operation() for resume-to-different-worker support
        - create_checkpoint_callback() for proper event loop handling

        Note: The actual model/optimizer restoration is handled in Task 4.5
        (ModelTrainer integration). This method provides the worker-level
        orchestration for resumed training.
        """
        import tempfile
        from pathlib import Path

        from ktrdr.api.services.training.context import build_training_context
        from ktrdr.api.services.training.local_orchestrator import (
            LocalTrainingOrchestrator,
        )
        from ktrdr.api.services.training.progress_bridge import (
            TrainingProgressBridge,
        )
        from ktrdr.checkpoint import CheckpointPolicy
        from ktrdr.training.model_storage import ModelStorage

        # 1. Adopt operation and transition to RUNNING
        # This handles resume-to-different-worker: loads from DB if not in cache
        await self.adopt_and_start_operation(operation_id)
        logger.info(
            f"Adopted and started operation {operation_id} for resume "
            f"(starting from epoch {resume_context.start_epoch})"
        )

        # Initialize checkpoint service for periodic saves during resumed training
        checkpoint_service = self.get_checkpoint_service()

        # Get cancellation token
        cancellation_token = self._operations_service.get_cancellation_token(
            operation_id
        )

        # Extract original request parameters from checkpoint
        original_request = resume_context.original_request

        # Task 4.8: Load strategy from disk using strategy_path (not from checkpoint)
        # New checkpoints store strategy_path; old checkpoints have strategy_yaml
        import yaml

        strategy_path = original_request.get("strategy_path")
        strategy_yaml_from_checkpoint = original_request.get("strategy_yaml")

        strategy_yaml: str
        strategy_name = "resumed_training"

        if strategy_path:
            # New format: Read strategy from disk using path
            # Convert relative path to absolute (workers mount strategies at /app/strategies)
            if not strategy_path.startswith("/"):
                strategy_file = Path("/app") / strategy_path
            else:
                strategy_file = Path(strategy_path)

            if not strategy_file.exists():
                # Check alternate location (for local dev without /app prefix)
                alt_path = Path(strategy_path)
                if alt_path.exists():
                    strategy_file = alt_path
                else:
                    raise FileNotFoundError(
                        f"Strategy file not found: {strategy_path} "
                        f"(checked {strategy_file} and {alt_path}). "
                        "The strategy file may have been deleted since the checkpoint was created."
                    )

            logger.info(f"Reading strategy from disk: {strategy_file}")
            with open(strategy_file) as f:
                strategy_yaml = f.read()

        elif strategy_yaml_from_checkpoint:
            # Old format (backward compatibility): Use strategy_yaml from checkpoint
            logger.warning(
                "Using strategy_yaml from checkpoint (old format). "
                "New checkpoints store strategy_path instead."
            )
            strategy_yaml = strategy_yaml_from_checkpoint

        else:
            raise ValueError(
                "Checkpoint missing both strategy_path and strategy_yaml. "
                "Cannot resume training without strategy configuration."
            )

        # Extract strategy name from YAML
        try:
            yaml_content = yaml.safe_load(strategy_yaml)
            if yaml_content and "name" in yaml_content:
                strategy_name = yaml_content["name"]
        except yaml.YAMLError:
            logger.warning("Failed to parse strategy YAML")

        # 2. Execute resumed training
        temp_dir = tempfile.mkdtemp()
        temp_yaml_path = Path(temp_dir) / f"{strategy_name}.yaml"

        # Track last checkpoint state for cancellation/failure
        last_checkpoint_state: dict = {}

        try:
            # Write YAML to temp file (needed for build_training_context)
            with open(temp_yaml_path, "w") as f:
                f.write(strategy_yaml)

            # Create training context from checkpoint's original request
            symbols = original_request.get("symbols", ["BTCUSD"])
            timeframes = original_request.get("timeframes", ["1h"])
            start_date = original_request.get("start_date", "2020-01-01")
            end_date = original_request.get("end_date")

            context = build_training_context(
                operation_id=operation_id,
                strategy_name=strategy_name,
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                detailed_analytics=False,
                use_host_service=False,  # Local execution on worker
                strategy_search_paths=[Path(temp_dir)],
            )

            # Create progress bridge
            def noop_callback(**kwargs):
                pass

            bridge = TrainingProgressBridge(
                context=context,
                update_progress_callback=noop_callback,
                cancellation_token=cancellation_token,
            )
            self._operations_service.register_local_bridge(operation_id, bridge)
            logger.info(
                f"Registered training bridge for resumed operation {operation_id}"
            )

            # Create model storage
            model_storage = ModelStorage()

            # Create checkpoint policy for resumed training
            checkpoint_policy = CheckpointPolicy(
                unit_interval=self.checkpoint_epoch_interval,
                time_interval_seconds=self.checkpoint_time_interval,
            )

            # Capture main event loop for checkpoint callback
            main_loop = asyncio.get_running_loop()

            # Import checkpoint builders
            from ktrdr.training.checkpoint_builder import (
                build_training_checkpoint_artifacts,
                build_training_checkpoint_state,
            )

            # Create state builder closure that captures original_request
            def training_state_builder(**kwargs):
                return build_training_checkpoint_state(
                    kwargs["trainer"], kwargs["epoch"], original_request
                )

            # Create artifacts builder closure
            def training_artifacts_builder(**kwargs):
                return build_training_checkpoint_artifacts(
                    kwargs["model"],
                    kwargs["optimizer"],
                    kwargs.get("scheduler"),
                    kwargs["trainer"].best_model_state,  # Pass state dict, not trainer
                )

            # Use shared checkpoint callback infrastructure
            # This fixes the "Future attached to different loop" bug by using
            # run_coroutine_threadsafe instead of asyncio.new_event_loop()
            base_callback = self.create_checkpoint_callback(
                operation_id=operation_id,
                checkpoint_service=checkpoint_service,
                checkpoint_policy=checkpoint_policy,
                state_builder=training_state_builder,
                main_loop=main_loop,
                last_checkpoint_state=last_checkpoint_state,
                artifacts_builder=training_artifacts_builder,
            )

            # Wrap callback to also store to instance for graceful shutdown (M6)
            def checkpoint_callback(**kwargs):
                # Store to instance for _save_checkpoint hook (M6 graceful shutdown)
                self._last_checkpoint_state = {
                    **kwargs,
                    "original_request": original_request,
                }
                # Call base callback for periodic checkpoint logic
                base_callback(**kwargs)

            # Create orchestrator with resume_context for model/optimizer restoration
            orchestrator = LocalTrainingOrchestrator(
                context=context,
                progress_bridge=bridge,
                cancellation_token=cancellation_token,
                model_storage=model_storage,
                checkpoint_callback=checkpoint_callback,
                resume_context=resume_context,
            )

            # Run training (async)
            result = await orchestrator.run()

        finally:
            # Clean up temp directory
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        # 3. Delete checkpoint on successful completion
        try:
            await checkpoint_service.delete_checkpoint(operation_id)
            logger.info(
                f"Checkpoint deleted after successful resumed completion: {operation_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint on success: {e}")

        # 4. Complete operation
        await self._operations_service.complete_operation(
            operation_id,
            result,
        )

        logger.info(
            f"Resumed training completed for operation {operation_id}: "
            f"model_path={result.get('model_path', 'unknown')}"
        )

        return {
            "model_path": result.get("model_path"),
            "training_metrics": result.get("training_metrics", {}),
            "test_metrics": result.get("test_metrics", {}),
        }


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
