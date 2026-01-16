"""
Training Service

Provides neural network training functionality for the API layer.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.services.training import (
    TrainingOperationContext,
    build_training_context,
    extract_symbols_timeframes_from_strategy,
)
from ktrdr.api.services.training.training_progress_renderer import (
    TrainingProgressRenderer,
)
from ktrdr.api.uptime import get_uptime_seconds
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError, WorkerUnavailableError
from ktrdr.monitoring.service_telemetry import trace_service_method
from ktrdr.training.model_storage import ModelStorage

if TYPE_CHECKING:
    from ktrdr.api.models.workers import WorkerEndpoint
    from ktrdr.api.services.worker_registry import WorkerRegistry

logger = get_logger(__name__)

# In-memory storage for loaded models (in production, use proper model registry)
_loaded_models: dict[str, Any] = {}


class TrainingService(ServiceOrchestrator[None]):
    """Service for neural network training operations (distributed-only mode).

    TrainingService requires WorkerRegistry and always uses distributed workers.
    GPU workers are preferred for performance, with automatic fallback to CPU workers.
    """

    def __init__(self, worker_registry: "WorkerRegistry") -> None:
        """Initialize training service (distributed mode).

        Args:
            worker_registry: WorkerRegistry for distributed worker selection (REQUIRED).
                           GPU workers are selected first (10x-100x faster),
                           with automatic fallback to CPU workers.
        """
        super().__init__()
        # Override progress renderer with training-specific renderer
        self._progress_renderer = TrainingProgressRenderer()
        self.model_storage = ModelStorage()
        self.model_loader = ModelLoader()
        self.operations_service = get_operations_service()
        self.worker_registry = worker_registry

        # Track which worker is handling which operation for cleanup
        # operation_id → worker_id mapping
        self._operation_workers: dict[str, str] = {}

        logger.info(
            "Training service initialized (distributed mode: GPU-first, CPU-fallback)"
        )

    def _select_training_worker(self, context: dict) -> Optional["WorkerEndpoint"]:
        """
        Select training worker with GPU-first, CPU-fallback strategy.

        Priority:
        1. Try GPU workers first (10x-100x faster)
        2. Fallback to CPU workers if no GPU available
        3. Raise WorkerUnavailableError if no workers available

        Args:
            context: Training operation context (currently unused, for future filtering)

        Returns:
            Selected WorkerEndpoint with optimal capabilities

        Raises:
            WorkerUnavailableError: If no training workers are available (HTTP 503)
        """
        from ktrdr.api.models.workers import WorkerStatus

        # Get all training workers (any status for counting)
        all_registered = self.worker_registry.list_workers(
            worker_type=WorkerType.TRAINING
        )
        registered_count = len(all_registered)

        # Get available workers
        all_workers = self.worker_registry.list_workers(
            worker_type=WorkerType.TRAINING, status=WorkerStatus.AVAILABLE
        )

        if not all_workers:
            raise WorkerUnavailableError(
                worker_type="training",
                registered_count=registered_count,
                backend_uptime_seconds=get_uptime_seconds(),
            )

        # Try GPU workers first (10x-100x faster)
        gpu_workers = [w for w in all_workers if w.capabilities.get("gpu") is True]

        if gpu_workers:
            logger.info("Selected GPU worker for training (10x-100x faster)")
            return gpu_workers[0]

        # Fallback to CPU workers (always available via containers)
        cpu_workers = [
            w
            for w in all_workers
            if w.capabilities.get("gpu") is False or "gpu" not in w.capabilities
        ]

        if cpu_workers:
            logger.info("Selected CPU worker for training (GPU unavailable)")
            return cpu_workers[0]

        # No available workers (all might be busy)
        raise WorkerUnavailableError(
            worker_type="training",
            registered_count=registered_count,
            backend_uptime_seconds=get_uptime_seconds(),
            hint="All training workers are currently busy. Retry in a few seconds.",
        )

    def _get_service_name(self) -> str:
        return "TrainingService"

    def _initialize_adapter(self) -> None:
        """No adapter needed for distributed-only mode."""
        return None

    def _get_default_host_url(self) -> str:
        """Not used in distributed-only mode."""
        return ""

    def _get_env_var_prefix(self) -> str:
        """Not used in distributed-only mode."""
        return "TRAINING"

    @trace_service_method("training.health_check")
    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the training service.

        Returns:
            Dict[str, Any]: Health check information
        """
        active_operations, _, _ = await self.operations_service.list_operations(
            operation_type=OperationType.TRAINING, active_only=True
        )
        return {
            "service": "TrainingService",
            "status": "ok",
            "active_trainings": len(active_operations),
            "model_storage_ready": self.model_storage is not None,
            "model_loader_ready": self.model_loader is not None,
        }

    @trace_service_method("training.start")
    async def start_training(
        self,
        symbols: Optional[list[str]],
        timeframes: Optional[list[str]],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> dict[str, Any]:
        """Start neural network training task.

        When symbols/timeframes are None, they are extracted from the strategy
        configuration file. This allows users to run `ktrdr train <strategy>`
        without specifying symbols/timeframes explicitly.

        Task 3.10 Fix: For distributed operations, bypass start_managed_operation.
        The worker creates the operation in DB (not the backend) to avoid duplicate
        key errors. Backend just dispatches to worker and registers a proxy.
        """
        # Task 1.7: Extract symbols/timeframes from strategy config if not provided
        resolved_symbols = symbols
        resolved_timeframes = timeframes

        if resolved_symbols is None or resolved_timeframes is None:
            logger.info(
                f"Extracting symbols/timeframes from strategy config: {strategy_name}"
            )
            config_symbols, config_timeframes = (
                extract_symbols_timeframes_from_strategy(strategy_name)
            )

            if resolved_symbols is None:
                resolved_symbols = config_symbols
                logger.info(f"Using symbols from strategy config: {resolved_symbols}")

            if resolved_timeframes is None:
                resolved_timeframes = config_timeframes
                logger.info(
                    f"Using timeframes from strategy config: {resolved_timeframes}"
                )

        # Task 3.10: Generate operation_id here if not provided
        # The worker creates the operation in its DB (distributed-only mode)
        operation_id = task_id or self.operations_service.generate_operation_id(
            OperationType.TRAINING
        )

        context = build_training_context(
            operation_id=operation_id,
            strategy_name=strategy_name,
            symbols=resolved_symbols,
            timeframes=resolved_timeframes,
            start_date=start_date,
            end_date=end_date,
            detailed_analytics=detailed_analytics,
            use_host_service=False,  # Distributed-only mode (no local/remote toggle)
        )

        logger.info(
            f"Starting training (distributed mode): {operation_id} "
            f"for {', '.join(resolved_symbols)} using {strategy_name}"
        )

        # Task 3.10: Dispatch directly to worker (no start_managed_operation)
        # Worker will create the operation in DB
        worker_result = await self._run_distributed_worker_training_wrapper(
            context=context
        )

        # Get operation_id from worker result (may differ from our generated ID)
        final_operation_id = worker_result.get("backend_operation_id", operation_id)

        estimated_duration = context.training_config.get(
            "estimated_duration_minutes", 30
        )
        message = (
            f"Neural network training started for {', '.join(context.symbols)} "
            f"using {strategy_name} strategy"
        )

        return {
            "success": True,
            "operation_id": final_operation_id,  # Added for MCP compatibility
            "task_id": final_operation_id,  # Keep for backward compatibility
            "status": "training_started",
            "message": message,
            "symbols": context.symbols,
            "timeframes": context.timeframes,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": estimated_duration,
            "worker_id": worker_result.get("worker_id"),
        }

    async def _legacy_operation_entrypoint(
        self,
        *,
        operation_id: str,
        context: TrainingOperationContext,
    ) -> Optional[dict[str, Any]]:
        """Execute training on distributed workers (distributed-only mode)."""
        context.operation_id = operation_id

        # Log training mode clearly before execution
        logger.info("=" * 80)
        logger.info("🚀 EXECUTING TRAINING: DISTRIBUTED WORKERS MODE")
        logger.info(f"   Operation ID: {operation_id}")
        logger.info(f"   Symbols: {', '.join(context.symbols)}")
        logger.info(f"   Strategy: {context.strategy_name}")
        logger.info("   Worker Selection: GPU-first, CPU-fallback")
        logger.info("=" * 80)

        return await self._run_distributed_worker_training_wrapper(context=context)

    async def _run_distributed_worker_training_wrapper(
        self, *, context: TrainingOperationContext
    ) -> dict[str, Any]:
        """
        Run training on distributed workers using proxy pattern (distributed-only mode).

        Backend acts as pure proxy:
        1. Starts training on remote worker
        2. Registers OperationServiceProxy for client queries
        3. Returns immediately (no waiting, no polling)

        Progress tracking happens via client-driven queries:
        - Client queries backend (GET /api/v1/operations/{backend_op_id})
        - Backend pulls from worker via proxy (cached with TTL)
        - Completion discovered when client queries, not through background polling
        """
        # Get backend operation ID
        backend_operation_id = context.operation_id
        if not backend_operation_id:
            raise RuntimeError("Operation ID required for distributed training")

        from datetime import UTC

        start_date = context.start_date or "2020-01-01"
        end_date = context.end_date or datetime.now(UTC).strftime("%Y-%m-%d")

        # Use WorkerRegistry for worker selection (distributed-only mode)
        return await self._run_distributed_worker_training(
            context=context,
            backend_operation_id=backend_operation_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def _run_distributed_worker_training(
        self,
        *,
        context: TrainingOperationContext,
        backend_operation_id: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        Run training on distributed workers using proxy pattern.

        Follows backtesting's remote pattern:
        1. Select available worker from WorkerRegistry
        2. Start training on remote worker (HTTP POST)
        3. Get remote operation ID
        4. Create OperationServiceProxy
        5. Register proxy with OperationsService
        6. Return immediately (no waiting)

        Args:
            context: Training operation context
            backend_operation_id: Backend operation identifier
            start_date: Training start date
            end_date: Training end date

        Returns:
            Dictionary with status="started" (remote operation continues independently)

        Raises:
            RuntimeError: If no workers are available
        """
        # (1) Select worker from registry with retry on 503 (worker busy)
        worker_id: Optional[str] = None
        remote_url: str
        max_retries = 3
        attempted_workers: list[str] = []

        if self.worker_registry is not None:
            for attempt in range(max_retries):
                # Use GPU-first worker selection (10x-100x faster)
                worker = self._select_training_worker(context={})
                if not worker:
                    if attempt == 0:
                        raise RuntimeError(
                            "No available training workers. All workers are busy or unavailable."
                        )
                    # All workers have been tried, none available
                    raise RuntimeError(
                        f"All training workers are busy. Tried {len(attempted_workers)} workers: {attempted_workers}"
                    )

                # Skip workers we've already tried
                if worker.worker_id in attempted_workers:
                    continue

                worker_id = worker.worker_id
                remote_url = worker.endpoint_url
                attempted_workers.append(worker_id)

                logger.info(
                    f"Selected worker {worker_id} for operation {backend_operation_id} "
                    f"(symbols={context.symbols}, timeframes={context.timeframes}, "
                    f"strategy={context.strategy_name}, attempt={attempt + 1}/{max_retries})"
                )
                break  # Worker selected, exit retry loop to try dispatching
            else:
                raise RuntimeError(
                    f"Could not select unique worker after {max_retries} attempts"
                )
        else:
            raise RuntimeError(
                "WorkerRegistry is required for distributed worker training"
            )

        # (2) Dispatch to worker with retry on 503
        # Read strategy YAML file to send to worker
        with open(context.strategy_path) as f:
            strategy_yaml = f.read()

        # Task 4.8: Convert strategy path to relative format for checkpoint storage
        # Workers mount strategies at /app/strategies, so we store relative path
        strategy_path_str = str(context.strategy_path)
        if "/app/" in strategy_path_str:
            # Docker path: /app/strategies/foo.yaml -> strategies/foo.yaml
            strategy_path_relative = strategy_path_str.split("/app/", 1)[1]
        elif strategy_path_str.startswith("strategies/"):
            # Already relative
            strategy_path_relative = strategy_path_str
        else:
            # Use as-is (may be absolute path in dev)
            strategy_path_relative = strategy_path_str

        request_payload = {
            "task_id": backend_operation_id,  # ← Operation ID sync (training-host pattern)
            "strategy_yaml": strategy_yaml,  # ← Send YAML content (required for training)
            "strategy_path": strategy_path_relative,  # ← Path for checkpoint storage (Task 4.8)
            "symbols": context.symbols,
            "timeframes": context.timeframes,
            "start_date": start_date,
            "end_date": end_date,
        }

        remote_response = None
        remote_operation_id = None

        # Retry loop: Try selected worker, if 503 (busy), select different worker
        for retry_attempt in range(max_retries):
            try:
                logger.info(
                    f"Dispatching training to worker {worker_id} at {remote_url}/training/start "
                    f"(attempt {retry_attempt + 1}/{max_retries})"
                )

                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{remote_url}/training/start",
                        json=request_payload,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    remote_response = response.json()

                # Success! Break retry loop
                remote_operation_id = remote_response.get("operation_id")
                if not remote_operation_id:
                    raise RuntimeError("Remote worker did not return operation_id")

                logger.info(
                    f"✅ Training accepted by worker {worker_id}: remote_op={remote_operation_id}"
                )
                break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    # Worker is busy, try different worker
                    logger.warning(
                        f"Worker {worker_id} is busy (503), selecting different worker "
                        f"(attempt {retry_attempt + 1}/{max_retries})"
                    )

                    if retry_attempt < max_retries - 1:
                        # Select a different worker for next attempt
                        if self.worker_registry is not None:
                            # Use GPU-first selection for retry
                            worker = self._select_training_worker(context={})
                            if worker and worker.worker_id not in attempted_workers:
                                worker_id = worker.worker_id
                                remote_url = worker.endpoint_url
                                attempted_workers.append(worker_id)
                                logger.info(f"Retrying with worker {worker_id}")
                                continue  # Retry with new worker
                            else:
                                # No more unique workers available
                                raise RuntimeError(
                                    f"All workers busy or unavailable after {retry_attempt + 1} attempts. "
                                    f"Tried workers: {attempted_workers}"
                                ) from e
                    else:
                        # Last retry failed
                        raise RuntimeError(
                            f"All workers busy after {max_retries} attempts. "
                            f"Tried workers: {attempted_workers}"
                        ) from e
                else:
                    # Other HTTP error, don't retry
                    raise

        if not remote_operation_id:
            raise RuntimeError("Failed to start training on any worker")

        logger.info(
            f"Remote training started: backend_op={backend_operation_id}, "
            f"remote_op={remote_operation_id}, worker={worker_id}"
        )

        # (3) Mark worker as busy (if using registry)
        if self.worker_registry is not None and worker_id is not None:
            self.worker_registry.mark_busy(worker_id, backend_operation_id)
            self._operation_workers[backend_operation_id] = worker_id
            logger.info(
                f"Marked worker {worker_id} as BUSY for operation {backend_operation_id}"
            )
            logger.info(
                "Worker cleanup will be handled by health check system "
                "(worker reports idle when training completes)"
            )

        # (4) Create OperationServiceProxy for remote worker
        from ktrdr.api.services.adapters.operation_service_proxy import (
            OperationServiceProxy,
        )

        proxy = OperationServiceProxy(base_url=remote_url)

        # (5) Register proxy with OperationsService
        self.operations_service.register_remote_proxy(
            backend_operation_id=backend_operation_id,
            proxy=proxy,
            host_operation_id=remote_operation_id,
        )

        logger.info(
            f"Registered remote proxy: {backend_operation_id} → {remote_operation_id}"
        )

        # (6) Return immediately with status="started"
        # Backend doesn't know completion status - client discovers via queries
        return {
            "remote_operation_id": remote_operation_id,
            "backend_operation_id": backend_operation_id,
            "status": "started",
            "message": f"Training started on worker {worker_id}: {', '.join(context.symbols)} ({context.strategy_name})",
            "worker_id": worker_id,  # Include worker_id in response for visibility
        }

    @trace_service_method("training.get_performance")
    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Get detailed performance metrics for completed training."""
        # Get operation info from operations service
        operation = await self.operations_service.get_operation(task_id)
        if not operation:
            raise ValidationError(f"Training task {task_id} not found")

        if operation.status.value != "completed":
            raise ValidationError(
                f"Training task {task_id} is not completed (status: {operation.status.value})"
            )

        # Extract metrics from aggregated results
        results = operation.result_summary or {}

        # Results are now in standardized aggregated format
        training_metrics = results.get("training_metrics", {})
        test_metrics = results.get("test_metrics", {})
        model_info = results.get("model_info", {})

        return {
            "success": True,
            "task_id": task_id,
            "status": operation.status.value,
            "training_metrics": training_metrics,
            "test_metrics": test_metrics,
            "model_info": model_info,
        }

    @trace_service_method("training.save_model")
    async def save_trained_model(
        self, task_id: str, model_name: str, description: str = ""
    ) -> dict[str, Any]:
        """Save a trained model for later use."""
        # Verify training task exists and is completed
        operation = await self.operations_service.get_operation(task_id)
        if not operation:
            raise ValidationError(f"Training task {task_id} not found")

        if operation.status.value != "completed":
            raise ValidationError(f"Training task {task_id} is not completed")

        # Get model path from aggregated artifacts
        results = operation.result_summary or {}
        artifacts = results.get("artifacts", {})
        model_path = artifacts.get("model_path")
        if not model_path or not Path(model_path).exists():
            raise ValidationError("Trained model file not found")

        # Generate model ID
        model_id = f"model_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Calculate model size
        model_size_mb = None
        if Path(model_path).exists():
            model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)

        logger.info(f"Model {model_name} saved with ID {model_id}")

        return {
            "success": True,
            "model_id": model_id,
            "model_name": model_name,
            "model_path": str(model_path),
            "task_id": task_id,
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "model_size_mb": model_size_mb,
        }

    @trace_service_method("training.load_model")
    async def load_trained_model(self, model_name: str) -> dict[str, Any]:
        """Load a previously saved neural network model."""
        # Check if model exists in storage
        all_models = self.model_storage.list_models()
        model_info = None

        for model in all_models:
            if model.get("name") == model_name:
                model_info = model
                break

        if not model_info:
            raise ValidationError(f"Model '{model_name}' not found")

        # Load model using ModelLoader
        model_path = model_info.get("path", "")

        if model_path and Path(model_path).exists():
            # Simulate loading the model
            _loaded_models[model_name] = {
                "model": "loaded_model_placeholder",
                "info": model_info,
                "loaded_at": datetime.utcnow().isoformat(),
            }
            model_loaded = True
        else:
            model_loaded = False

        logger.info(f"Model {model_name} loaded successfully: {model_loaded}")

        return {
            "success": True,
            "model_name": model_name,
            "model_loaded": model_loaded,
            "model_info": {
                "created_at": model_info.get("created_at", ""),
                "symbol": model_info.get("symbol", ""),
                "timeframe": model_info.get("timeframe", ""),
                "architecture": model_info.get("architecture", ""),
                "training_accuracy": model_info.get("training_accuracy", 0.0),
                "test_accuracy": model_info.get("test_accuracy", 0.0),
            },
        }

    @trace_service_method("training.test_prediction")
    async def test_model_prediction(
        self,
        model_name: str,
        symbol: str,
        timeframe: str = "1h",
        test_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Test a loaded model's prediction capability."""
        # Check if model is loaded
        if model_name not in _loaded_models:
            raise ValidationError(f"Model '{model_name}' is not loaded. Load it first.")

        # Use test_date or default to latest available
        test_date = test_date or datetime.utcnow().strftime("%Y-%m-%d")

        # In a real implementation, this would generate actual predictions
        logger.info(f"Model {model_name} prediction for {symbol} on {test_date}")

        return {
            "success": True,
            "model_name": model_name,
            "symbol": symbol,
            "test_date": test_date,
            "prediction": {
                "signal": "hold",  # Default to hold if no real prediction
                "confidence": 0.0,
                "signal_strength": 0.0,
                "fuzzy_outputs": {"bullish": 0.0, "bearish": 0.0, "neutral": 1.0},
            },
            "input_features": {},  # Would be populated by real model prediction
        }

    @trace_service_method("training.list_models")
    async def list_trained_models(self) -> dict[str, Any]:
        """List all available trained neural network models."""
        # Get all models from storage
        all_models = self.model_storage.list_models()

        # Convert to response format
        model_summaries = []
        for model in all_models:
            summary = {
                "model_id": model.get("id", ""),
                "model_name": model.get("name", ""),
                "symbol": model.get("symbol", ""),
                "timeframe": model.get("timeframe", ""),
                "created_at": model.get("created_at", ""),
                "training_accuracy": model.get("training_accuracy", 0.0),
                "test_accuracy": model.get("test_accuracy", 0.0),
                "description": model.get("description", ""),
            }
            model_summaries.append(summary)

        logger.info(f"Listed {len(model_summaries)} models")

        return {"success": True, "models": model_summaries}


# Note: get_training_service() dependency function is defined in endpoints/training.py
# It properly injects WorkerRegistry which is required for distributed-only mode
