"""
Training Service

Core training orchestration service that integrates all existing KTRDR training
components with GPU acceleration and host-level resource management.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from opentelemetry import trace

# Task 2.3: Import operations service and progress bridge for pull-based operations
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.progress_bridge import ProgressBridge
from ktrdr.logging import get_logger
from ktrdr.training.data_optimization import DataConfig, DataLoadingOptimizer
from ktrdr.training.device_manager import DeviceManager

# Import existing ktrdr training components
from ktrdr.training.gpu_memory_manager import GPUMemoryConfig, GPUMemoryManager
from ktrdr.training.memory_manager import MemoryBudget, MemoryManager
from ktrdr.training.performance_optimizer import PerformanceConfig, PerformanceOptimizer

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class TrainingSession:
    """Represents an active training session with all its resources."""

    def __init__(self, session_id: str, config: dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.status = "initializing"
        self.start_time = datetime.now(UTC)
        self.last_updated = datetime.now(UTC)

        # Task 2.3: Pull-based operations tracking
        self.operation_id: Optional[str] = None
        self.progress_bridge: Optional[ProgressBridge] = None

        # Progress tracking - store complete data from ModelTrainer (source of truth)
        self._last_progress_data: Optional[dict[str, Any]] = None

        # Legacy fields for backwards compatibility
        self.current_epoch = 0
        self.current_batch = 0
        self.total_epochs = config.get("training_config", {}).get("epochs", 100)
        self.total_batches = 0
        self.items_processed = 0
        self.message = "Initializing"
        self.current_item = ""

        # Metrics tracking
        self.metrics = {}
        self.best_metrics = {}

        # Resource managers
        self.gpu_manager: Optional[GPUMemoryManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.performance_optimizer: Optional[PerformanceOptimizer] = None
        self.data_optimizer: Optional[DataLoadingOptimizer] = None

        # Training components
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.dataloader = None

        # Background task
        self.training_task: Optional[asyncio.Task] = None
        self.stop_requested = False

        # Error tracking
        self.error = None

        # Training result storage (Task 3.3: Result Harmonization)
        # Store complete training result from TrainingPipeline for harmonization
        # with local training format. This enables status endpoint to return
        # the actual training result instead of requiring transformation.
        self.training_result: Optional[dict[str, Any]] = None

    def update_progress(self, epoch: int, batch: int, metrics: dict[str, float]):
        """
        Update training progress - store complete data from ModelTrainer (source of truth).

        ModelTrainer/TrainingPipeline is execution-agnostic and calculates all progress data.
        This method just stores the data and passes it through in get_progress_dict().
        """
        self.last_updated = datetime.now(UTC)

        # Store complete progress data from ModelTrainer (single source of truth)
        self._last_progress_data = {
            "epoch": metrics.get("epoch", epoch),
            "total_epochs": metrics.get("total_epochs", self.total_epochs),
            "batch": metrics.get("batch", batch),
            "total_batches_per_epoch": metrics.get("total_batches_per_epoch"),
            "completed_batches": metrics.get("completed_batches"),
            "total_batches": metrics.get("total_batches"),
            "progress_percent": metrics.get("progress_percent"),
            "progress_type": metrics.get("progress_type"),
        }

        # Update legacy fields for backwards compatibility
        try:
            self.current_epoch = int(self._last_progress_data["epoch"])
        except (TypeError, ValueError):
            pass

        try:
            self.current_batch = int(self._last_progress_data["batch"])
        except (TypeError, ValueError):
            pass

        try:
            self.total_batches = int(
                self._last_progress_data["total_batches_per_epoch"] or 0
            )
        except (TypeError, ValueError):
            pass

        try:
            self.items_processed = int(self._last_progress_data["completed_batches"] or 0)
        except (TypeError, ValueError):
            pass

        # Build message for display (legacy field)
        # Check if orchestrator provided a custom message (e.g., preprocessing)
        custom_message = metrics.get("message")
        if custom_message:
            self.message = custom_message
            self.current_item = custom_message
        else:
            # Build message from epoch/batch data
            message_parts = []
            epoch_val = self._last_progress_data.get("epoch")
            total_epochs_val = self._last_progress_data.get("total_epochs")
            batch_val = self._last_progress_data.get("batch")
            total_batches_per_epoch_val = self._last_progress_data.get(
                "total_batches_per_epoch"
            )

            if epoch_val and total_epochs_val:
                message_parts.append(f"Epoch {epoch_val}/{total_epochs_val}")
            elif epoch_val:
                message_parts.append(f"Epoch {epoch_val}")

            if batch_val and total_batches_per_epoch_val:
                message_parts.append(f"Batch {batch_val}/{total_batches_per_epoch_val}")

            if message_parts:
                self.message = " · ".join(message_parts)
                self.current_item = message_parts[-1]
            else:
                self.message = "Training in progress"
                self.current_item = self.message

        # Update metrics tracking
        for key, value in metrics.items():
            if key not in self.metrics:
                self.metrics[key] = []
            self.metrics[key].append(value)

            if "loss" in key.lower():
                if key not in self.best_metrics or value < self.best_metrics[key]:
                    self.best_metrics[key] = value
            else:
                if key not in self.best_metrics or value > self.best_metrics[key]:
                    self.best_metrics[key] = value

    def get_progress_dict(self) -> dict[str, Any]:
        """
        Get progress information - pass through from ModelTrainer (execution-agnostic).

        All progress calculations happen in TrainingPipeline/ModelTrainer (single source of truth).
        This method just returns the data for transmission to backend.
        """
        if self._last_progress_data:
            # Pass through complete progress data from ModelTrainer
            return {
                "epoch": self._last_progress_data.get("epoch", 0),
                "total_epochs": self._last_progress_data.get(
                    "total_epochs", self.total_epochs
                ),
                "batch": self._last_progress_data.get("batch", 0),
                "total_batches": self._last_progress_data.get(
                    "total_batches_per_epoch", 0
                ),
                "progress_percent": self._last_progress_data.get("progress_percent", 0.0),
                "items_processed": self._last_progress_data.get("completed_batches", 0),
                "items_total": self._last_progress_data.get("total_batches"),
                "message": self.message,
                "current_item": self.current_item or self.message,
            }

        # Fallback if no data yet (initialization phase)
        return {
            "epoch": 0,
            "total_epochs": self.total_epochs,
            "batch": 0,
            "total_batches": 0,
            "progress_percent": 0.0,
            "items_processed": 0,
            "items_total": None,
            "message": self.message,
            "current_item": self.current_item or self.message,
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """Get current resource usage information."""
        resource_info = {
            "gpu_allocated": self.gpu_manager is not None and self.gpu_manager.enabled,
            "memory_monitoring": self.memory_manager is not None,
            "performance_optimization": self.performance_optimizer is not None,
        }

        # GPU usage
        if self.gpu_manager and self.gpu_manager.enabled:
            try:
                snapshot = self.gpu_manager.capture_snapshot(0)
                resource_info["gpu_memory"] = {
                    "allocated_mb": snapshot.allocated_mb,
                    "total_mb": snapshot.total_mb,
                    "utilization_percent": (
                        (snapshot.allocated_mb / snapshot.total_mb) * 100
                        if snapshot.total_mb > 0
                        else 0
                    ),
                }
            except Exception as e:
                resource_info["gpu_memory"] = {"error": str(e)}

        # System memory
        if self.memory_manager:
            try:
                memory_snapshot = self.memory_manager.capture_snapshot()
                resource_info["system_memory"] = {
                    "process_mb": memory_snapshot.process_memory_mb,
                    "system_percent": memory_snapshot.system_memory_percent,
                    "system_total_mb": memory_snapshot.system_memory_total_mb,
                }
            except Exception as e:
                resource_info["system_memory"] = {"error": str(e)}

        return resource_info

    async def cleanup(self):
        """Clean up session resources."""
        logger.info(f"Cleaning up session {self.session_id}")

        # Stop training task if running
        if self.training_task and not self.training_task.done():
            self.stop_requested = True
            try:
                await asyncio.wait_for(self.training_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Training task for session {self.session_id} did not stop gracefully"
                )
                self.training_task.cancel()

        # Cleanup GPU resources
        if self.gpu_manager:
            try:
                self.gpu_manager.cleanup_memory()
                if hasattr(self.gpu_manager, "stop_monitoring"):
                    self.gpu_manager.stop_monitoring()
            except Exception as e:
                logger.warning(f"Error cleaning up GPU resources: {str(e)}")

        # Cleanup memory manager
        if self.memory_manager:
            try:
                self.memory_manager.cleanup_memory()
                if hasattr(self.memory_manager, "stop_monitoring"):
                    self.memory_manager.stop_monitoring()
            except Exception as e:
                logger.warning(f"Error cleaning up memory resources: {str(e)}")

        logger.info(f"Session {self.session_id} cleanup completed")


class TrainingService:
    """
    Main training service that orchestrates GPU-accelerated training sessions.

    This service integrates all existing KTRDR training components:
    - GPUMemoryManager for GPU resource management
    - MemoryManager for system memory monitoring
    - PerformanceOptimizer for training optimization
    - DataLoadingOptimizer for efficient data loading
    """

    def __init__(
        self, max_concurrent_sessions: int = 1, session_timeout_minutes: int = 60
    ):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_timeout_minutes = session_timeout_minutes
        self.sessions: dict[str, TrainingSession] = {}

        # Model storage - use MODELS_DIR env var (set by local_prod.py from .env.sandbox)
        # Falls back to project root if env var not set
        import os
        from pathlib import Path

        from ktrdr.training.model_storage import ModelStorage

        models_dir = os.getenv("MODELS_DIR")
        if not models_dir:
            project_root = Path(__file__).parent.parent.parent
            models_dir = str(project_root / "models")
        self.model_storage = ModelStorage(base_path=models_dir)

        # Global resource managers
        self.global_gpu_manager: Optional[GPUMemoryManager] = None
        self._initialize_global_resources()

        # Background cleanup task (will be started when needed)
        self.cleanup_task = None

    def _initialize_global_resources(self):
        """Initialize global GPU resources."""
        try:
            # Use DeviceManager to detect device and capabilities
            device_info = DeviceManager.get_device_info()
            device_type = device_info["device"]
            capabilities = device_info["capabilities"]

            if device_type in ("cuda", "mps"):
                # Configure based on device capabilities
                gpu_config = GPUMemoryConfig(
                    memory_fraction=0.8,
                    enable_mixed_precision=capabilities["mixed_precision"],
                    enable_memory_profiling=capabilities["memory_info"],
                    enable_memory_pooling=(
                        device_type == "cuda"
                    ),  # Only CUDA supports pooling
                    profiling_interval_seconds=1.0,
                )
                self.global_gpu_manager = GPUMemoryManager(gpu_config)
                logger.info(
                    f"Global GPU manager initialized with {device_info['device_name']}"
                )
            else:
                logger.info("No GPU available, running in CPU-only mode")
        except Exception as e:
            logger.error(f"Failed to initialize global GPU resources: {str(e)}")
            self.global_gpu_manager = None

    async def create_session(
        self, config: dict[str, Any], session_id: Optional[str] = None
    ) -> str:
        """
        Create a new training session.

        Args:
            config: Training configuration including model, training, and data configs
            session_id: Optional session ID, will be generated if not provided

        Returns:
            Session ID of the created session

        Raises:
            Exception: If session creation fails or resource limits exceeded
        """
        # Check session limits
        active_sessions = [
            s for s in self.sessions.values() if s.status in ["running", "initializing"]
        ]
        all_sessions = [(sid, s.status) for sid, s in self.sessions.items()]
        logger.info(
            f"🔍 CREATE_SESSION: Checking limits - active={len(active_sessions)}/{self.max_concurrent_sessions}, "
            f"all_sessions={all_sessions}"
        )
        if len(active_sessions) >= self.max_concurrent_sessions:
            raise Exception(
                f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached"
            )

        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Check for duplicate session ID
        if session_id in self.sessions:
            raise Exception(f"Session {session_id} already exists")

        # Create session
        session = TrainingSession(session_id, config)

        try:
            # Initialize session resources
            await self._initialize_session_resources(session)

            # Task 2.3: Create operation and register bridge BEFORE training starts
            await self._create_operation_and_bridge(session)

            # Add to sessions
            self.sessions[session_id] = session

            # Start background cleanup task if not already running
            if self.cleanup_task is None:
                self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

            # Start training in background
            session.training_task = asyncio.create_task(
                self._run_training_session(session)
            )

            logger.info(f"✅ CREATE_SESSION: session_id={session_id}, status={session.status} - Training task started")
            return session_id

        except Exception as e:
            # Cleanup on failure
            await session.cleanup()
            raise Exception(f"Failed to create training session: {str(e)}") from e

    async def _initialize_session_resources(self, session: TrainingSession):
        """Initialize resources for a training session."""
        try:
            # Initialize GPU manager for session
            if self.global_gpu_manager and self.global_gpu_manager.enabled:
                # Create session-specific GPU config
                gpu_config = GPUMemoryConfig()
                if "gpu_config" in session.config:
                    # Update with session-specific GPU settings
                    for key, value in session.config["gpu_config"].items():
                        if hasattr(gpu_config, key):
                            setattr(gpu_config, key, value)

                session.gpu_manager = GPUMemoryManager(gpu_config)
                logger.info(f"GPU manager initialized for session {session.session_id}")

            # Initialize memory manager
            memory_budget = MemoryBudget(
                max_process_memory_mb=4096,  # TODO: Make configurable
                warning_threshold_percent=0.8,
                enable_monitoring=True,
                monitoring_interval_seconds=1.0,
            )
            session.memory_manager = MemoryManager(budget=memory_budget)

            # Initialize performance optimizer - disable mixed precision for MPS compatibility
            perf_config = PerformanceConfig(
                enable_mixed_precision=False,  # Disable mixed precision for MPS compatibility
                adaptive_batch_size=True,
                compile_model=False,  # Disable for compatibility
                min_batch_size=16,
                max_batch_size=128,
            )
            session.performance_optimizer = PerformanceOptimizer(perf_config)

            # Initialize data optimizer
            data_config = DataConfig(
                enable_memory_mapping=False,  # Disable for compatibility
                enable_batch_prefetching=True,
                balanced_sampling=True,
                symbol_balanced_sampling=True,
            )
            session.data_optimizer = DataLoadingOptimizer(data_config)

            session.status = "initialized"
            logger.info(f"All resources initialized for session {session.session_id}")

        except Exception as e:
            session.error = str(e)
            session.status = "failed"
            raise

    async def _create_operation_and_bridge(self, session: TrainingSession):
        """
        Create operation and register progress bridge for pull-based operations.

        Task 2.3: This method implements the operation creation and bridge registration
        required for pull-based operations API integration.

        Args:
            session: Training session to create operation for

        Raises:
            Exception: If operation creation or bridge registration fails
        """
        try:
            # Get operations service singleton
            ops_service = get_operations_service()

            # Use session_id directly as operation_id (backend's operation_id passed via task_id)
            # This ensures backend and worker track the same operation with the same ID
            operation_id = session.session_id
            session.operation_id = operation_id

            # Create operation in OperationsService
            await ops_service.create_operation(
                operation_id=operation_id,
                operation_type=OperationType.TRAINING,
                metadata=OperationMetadata(
                    symbol=session.config.get("symbols", ["unknown"])[0]
                    if isinstance(session.config.get("symbols"), list)
                    else session.config.get("symbols", "unknown"),
                    timeframe="multiple"
                    if isinstance(session.config.get("timeframes"), list)
                    and len(session.config.get("timeframes", [])) > 1
                    else (
                        session.config.get("timeframes", ["1d"])[0]
                        if isinstance(session.config.get("timeframes"), list)
                        else session.config.get("timeframes", "1d")
                    ),
                    description=f"Host training session {session.session_id}",
                ),
            )

            logger.info(
                f"✅ Operation created: {operation_id} for session {session.session_id}"
            )

            # Create TrainingProgressBridge
            # Parse training config to get total epochs
            import yaml

            strategy_yaml = session.config.get("strategy_yaml", "")
            training_config = {}
            strategy_dict = {}
            if strategy_yaml:
                try:
                    strategy_dict = yaml.safe_load(strategy_yaml)
                    training_config = strategy_dict.get("training_config", {})
                except Exception as e:
                    logger.warning(
                        f"Failed to parse strategy YAML for epochs: {e}, using default"
                    )

            total_epochs = training_config.get("epochs", session.total_epochs)

            # Extract symbols and timeframes from config
            symbols = session.config.get("symbols", ["unknown"])
            if not isinstance(symbols, list):
                symbols = [symbols]

            timeframes = session.config.get("timeframes", ["1d"])
            if not isinstance(timeframes, list):
                timeframes = [timeframes]

            start_date = session.config.get("start_date")
            end_date = session.config.get("end_date")

            # Create operation metadata
            from pathlib import Path

            metadata = OperationMetadata(
                symbol=symbols[0] if symbols else "unknown",
                timeframe="multiple" if len(timeframes) > 1 else timeframes[0],
                description=f"Host training session {session.session_id}",
            )

            # Create operation context (provide all required fields)
            context = TrainingOperationContext(
                operation_id=operation_id,
                strategy_name="host_training",  # Host service doesn't use named strategies
                strategy_path=Path(""),  # No file path for inline YAML
                strategy_config=strategy_dict if strategy_yaml else {},
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                training_config=training_config,
                analytics_enabled=False,  # Host service uses basic analytics
                use_host_service=True,  # This IS the host service
                training_mode="host",
                total_epochs=total_epochs,
                total_batches=None,  # Will be determined during training
                metadata=metadata,
                session_id=session.session_id,
            )

            # Create progress manager for pull-based state tracking (just like backend)
            from ktrdr.async_infrastructure.progress import GenericProgressManager

            # Create progress manager (no callback needed, just for state tracking)
            progress_manager = GenericProgressManager()

            # Create bridge with progress manager (enables pull-based queries)
            bridge = TrainingProgressBridge(
                context=context,
                progress_manager=progress_manager,
                cancellation_token=None,  # Cancellation handled via session.stop_requested
            )

            session.progress_bridge = bridge

            # Register bridge with operations service
            ops_service.register_local_bridge(operation_id, bridge)

            logger.info(
                f"✅ Progress bridge registered for operation {operation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to create operation and bridge for session {session.session_id}: {e}"
            )
            raise

    async def _run_training_session(self, session: TrainingSession):
        """Run the actual training for a session."""
        # Get operations service for completion/failure updates
        ops_service = get_operations_service()

        try:
            session.status = "running"
            session.last_updated = datetime.now(UTC)

            logger.info(f"Starting training for session {session.session_id}")

            # TASK 3.1: Update operation status to RUNNING
            if session.operation_id:
                operation = await ops_service.get_operation(session.operation_id)
                if operation:
                    from datetime import timezone

                    operation.status = OperationStatus.RUNNING
                    operation.started_at = datetime.now(timezone.utc)
                    logger.info(f"✅ Operation {session.operation_id} status updated to RUNNING")

            # Start resource monitoring
            if session.gpu_manager:
                session.gpu_manager.start_monitoring()
            # PERFORMANCE FIX: Memory monitoring disabled - causes 2x slowdown due to aggressive
            # gc.collect() cycles every 1 second. The monitoring thread iterates through all
            # Python objects, counts tensors, and triggers automatic cleanup at 80% memory usage,
            # which runs gc.collect() 4 times per cleanup. This blocks the GPU training thread.
            # See analysis: memory_manager.py sets monitoring_interval_seconds=1.0 (line 419)
            # and auto_cleanup triggers at 80% threshold (line 299-323).
            # if session.memory_manager:
            #     session.memory_manager.start_monitoring()

            # Real GPU training implementation
            result = await self._run_real_training(session)

            # Training completed successfully
            if not session.stop_requested:
                session.status = "completed"
                logger.info(f"Training completed for session {session.session_id}")

                # Task 2.3: Mark operation as complete
                if session.operation_id:
                    await ops_service.complete_operation(session.operation_id, result)
                    logger.info(
                        f"✅ Operation {session.operation_id} marked as completed"
                    )
            else:
                session.status = "stopped"
                logger.info(f"Training stopped for session {session.session_id}")

        except Exception as e:
            session.error = str(e)
            session.status = "failed"
            logger.error(f"Training failed for session {session.session_id}: {str(e)}")

            # Task 2.3: Mark operation as failed
            if session.operation_id:
                try:
                    await ops_service.fail_operation(
                        session.operation_id, f"Training failed: {str(e)}"
                    )
                    logger.info(
                        f"❌ Operation {session.operation_id} marked as failed"
                    )
                except Exception as fail_error:
                    logger.error(
                        f"Failed to mark operation as failed: {fail_error}"
                    )

        finally:
            # Stop monitoring
            try:
                if session.gpu_manager:
                    session.gpu_manager.stop_monitoring()
                # Memory monitoring disabled (see start_monitoring comment above)
                # if session.memory_manager:
                #     session.memory_manager.stop_monitoring()
            except Exception as e:
                logger.warning(
                    f"Error stopping monitoring for session {session.session_id}: {str(e)}"
                )

            session.last_updated = datetime.now(UTC)

    async def _run_real_training(self, session: TrainingSession):
        """
        Run training using HostTrainingOrchestrator.

        This method is now a thin wrapper that delegates all work to
        HostTrainingOrchestrator, which uses TrainingPipeline for training logic.

        PERFORMANCE FIX: The old implementation had 14 minutes of sleep overhead per
        100 epochs. The orchestrator uses intelligent throttling instead (8ms overhead).
        """
        # Create span for GPU training with detailed attributes
        with tracer.start_as_current_span("training_host.gpu_training") as span:
            # Add GPU device information if available
            if self.global_gpu_manager and self.global_gpu_manager.enabled:
                try:
                    import torch

                    if torch.cuda.is_available():
                        device = torch.cuda.current_device()
                        span.set_attribute("gpu.device", torch.cuda.get_device_name(device))
                        span.set_attribute(
                            "gpu.memory_allocated_mb",
                            round(torch.cuda.memory_allocated(device) / 1024 / 1024, 2),
                        )
                        span.set_attribute(
                            "gpu.memory_reserved_mb",
                            round(torch.cuda.memory_reserved(device) / 1024 / 1024, 2),
                        )
                        # GPU utilization would require nvidia-smi or similar
                        # For now, we track memory which is the key metric
                except Exception as e:
                    logger.debug(f"Could not capture GPU metrics: {e}")

            # Add training configuration to span
            span.set_attribute(
                "training.epochs", session.config.get("training_config", {}).get("epochs", 0)
            )
            span.set_attribute("training.session_id", session.session_id)

            try:
                # Import orchestrator using importlib to avoid module cache conflicts
                # The parent directory contains both orchestrator.py (what we want) and
                # ktrdr-prod/orchestrator/ package (Claude orchestration) - naive sys.path
                # manipulation fails because Python caches the package resolution
                import importlib.util
                from pathlib import Path

                orchestrator_file = Path(__file__).parent.parent / "orchestrator.py"
                spec = importlib.util.spec_from_file_location(
                    "host_orchestrator", orchestrator_file
                )
                orchestrator_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(orchestrator_module)
                HostTrainingOrchestrator = orchestrator_module.HostTrainingOrchestrator

                # Host service has its own ModelStorage instance configured at service level
                # This provides situational awareness - the service knows where models should be saved
                # The orchestrator receives this and passes it through to TrainingPipeline
                orchestrator = HostTrainingOrchestrator(
                    session=session,
                    model_storage=self.model_storage,  # Use service-level ModelStorage
                )

                # Run training via orchestrator (direct async - no thread wrapper)
                result = await orchestrator.run()

                # Add final GPU metrics to span after training
                if self.global_gpu_manager and self.global_gpu_manager.enabled:
                    try:
                        import torch

                        if torch.cuda.is_available():
                            device = torch.cuda.current_device()
                            span.set_attribute(
                                "gpu.memory_allocated_final_mb",
                                round(torch.cuda.memory_allocated(device) / 1024 / 1024, 2),
                            )
                            span.set_attribute(
                                "gpu.memory_peak_mb",
                                round(torch.cuda.max_memory_allocated(device) / 1024 / 1024, 2),
                            )
                    except Exception as e:
                        logger.debug(f"Could not capture final GPU metrics: {e}")

                # Result already includes:
                # - model_path (saved via ModelStorage)
                # - training_metrics
                # - test_metrics
                # - resource_usage (GPU info)
                # - session_id

                # Session status already updated by orchestrator
                logger.info(
                    f"Training orchestration completed for session {session.session_id}"
                )

                return result

            except Exception as e:
                session.status = "failed"
                session.message = f"Training failed: {str(e)}"
                span.record_exception(e)
                span.set_attribute("error", True)
                logger.error(f"Training failed for session {session.session_id}: {str(e)}")
                raise

    # Old simplified feature engineering methods removed - now using TrainingPipeline

    async def stop_session(self, session_id: str, save_checkpoint: bool = True) -> bool:
        """
        Stop a running training session.

        Args:
            session_id: ID of session to stop
            save_checkpoint: Whether to save a checkpoint before stopping

        Returns:
            True if session was stopped successfully
        """
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")

        session = self.sessions[session_id]

        if session.status not in ["running", "initializing"]:
            raise Exception(
                f"Session {session_id} is not running (status: {session.status})"
            )

        logger.info(
            f"Training cancellation received for session {session_id} - requesting training stop"
        )

        # Request stop
        session.stop_requested = True
        logger.info(
            f"🛑 STOP_SESSION: session_id={session_id}, current_status={session.status}, stop_requested=True"
        )

        # TODO: Implement checkpoint saving if requested
        if save_checkpoint:
            logger.info(f"Checkpoint saving requested for session {session_id}")
            # Implementation would save model state, optimizer state, etc.

        # Wait for training task to complete
        logger.info("⏳ STOP_SESSION: Waiting for training task to complete (timeout=30s)")
        if session.training_task:
            try:
                await asyncio.wait_for(session.training_task, timeout=30.0)
                logger.info(f"✅ STOP_SESSION: Training task completed, session_status={session.status}")
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏰ STOP_SESSION: Training task for session {session_id} did not stop gracefully (timeout)"
                )
                session.training_task.cancel()
                session.status = "stopped"
            except asyncio.CancelledError:
                logger.info(
                    f"❌ STOP_SESSION: Training task for session {session_id} was already cancelled"
                )
                session.status = "stopped"
        else:
            logger.info("⚠️ STOP_SESSION: No training task found")

        logger.info(f"🏁 STOP_SESSION: Returning True, final session_status={session.status}")
        return True

    def get_session_status(self, session_id: str) -> dict[str, Any]:
        """
        Get detailed status of a training session.

        TASK 3.3: Always returns progress format (even when completed).
        Use session.training_result directly to get final training results.

        Returns:
            dict: Status with progress, metrics, resource_usage for all states
        """
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")

        session = self.sessions[session_id]

        # Always return progress format (separation of concerns: status vs results)
        return {
            "session_id": session_id,
            "status": session.status,
            "progress": session.get_progress_dict(),
            "metrics": {"current": session.metrics, "best": session.best_metrics},
            "resource_usage": session.get_resource_usage(),
            "start_time": session.start_time.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "error": session.error,
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all training sessions with summary information."""
        sessions = []
        for session_id, session in self.sessions.items():
            sessions.append(
                {
                    "session_id": session_id,
                    "status": session.status,
                    "start_time": session.start_time.isoformat(),
                    "last_updated": session.last_updated.isoformat(),
                    "progress": session.get_progress_dict(),
                    "gpu_allocated": session.gpu_manager is not None
                    and session.gpu_manager.enabled,
                    "error": session.error,
                }
            )
        return sessions

    async def cleanup_session(self, session_id: str) -> bool:
        """Clean up a completed or failed session."""
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")

        session = self.sessions[session_id]

        # Only allow cleanup of non-running sessions
        if session.status == "running":
            raise Exception(f"Cannot cleanup running session {session_id}")

        # Cleanup resources
        await session.cleanup()

        # Remove from sessions
        del self.sessions[session_id]

        logger.info(f"Session {session_id} cleaned up successfully")
        return True

    async def _periodic_cleanup(self):
        """Periodic cleanup of timed-out sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.now(UTC)
                timeout_threshold = timedelta(minutes=self.session_timeout_minutes)

                sessions_to_cleanup = []
                for session_id, session in self.sessions.items():
                    # Check for timed-out sessions
                    if session.status in ["completed", "failed", "stopped"]:
                        time_since_update = current_time - session.last_updated
                        if time_since_update > timeout_threshold:
                            sessions_to_cleanup.append(session_id)

                # Cleanup timed-out sessions
                for session_id in sessions_to_cleanup:
                    try:
                        await self.cleanup_session(session_id)
                        logger.info(f"Auto-cleaned up timed-out session {session_id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to auto-cleanup session {session_id}: {str(e)}"
                        )

            except Exception as e:
                logger.error(f"Error in periodic cleanup: {str(e)}")

    async def shutdown(self):
        """Shutdown the training service and cleanup all resources."""
        logger.info("Shutting down training service...")

        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()

        # Stop and cleanup all active sessions
        for session_id in list(self.sessions.keys()):
            try:
                session = self.sessions[session_id]
                if session.status == "running":
                    await self.stop_session(session_id, save_checkpoint=False)
                await self.cleanup_session(session_id)
            except Exception as e:
                logger.error(
                    f"Error cleaning up session {session_id} during shutdown: {str(e)}"
                )

        # Cleanup global resources
        if self.global_gpu_manager:
            try:
                self.global_gpu_manager.cleanup_memory()
            except Exception as e:
                logger.warning(f"Error cleaning up global GPU resources: {str(e)}")

        logger.info("Training service shutdown completed")


# Global service instance
_training_service: Optional[TrainingService] = None


def get_training_service(
    max_concurrent_sessions: int = 1, session_timeout_minutes: int = 60
) -> TrainingService:
    """Get or create the global training service instance."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService(
            max_concurrent_sessions, session_timeout_minutes
        )
    return _training_service
