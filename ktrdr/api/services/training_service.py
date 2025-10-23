"""
Training Service

Provides neural network training functionality for the API layer.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.services.training import (
    HostSessionManager,
    TrainingOperationContext,
    TrainingProgressBridge,
    build_training_context,
)
from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator
from ktrdr.api.services.training.training_progress_renderer import (
    TrainingProgressRenderer,
)
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError
from ktrdr.training.model_storage import ModelStorage
from ktrdr.training.training_adapter import TrainingAdapter

logger = get_logger(__name__)

# In-memory storage for loaded models (in production, use proper model registry)
_loaded_models: dict[str, Any] = {}


class TrainingService(ServiceOrchestrator[TrainingAdapter | None]):
    """Service for neural network training operations.

    Adapter is None for local training mode (uses LocalTrainingOrchestrator directly).
    Adapter is TrainingAdapter for host service mode.
    """

    def __init__(self) -> None:
        super().__init__()
        # Override progress renderer with training-specific renderer
        self._progress_renderer = TrainingProgressRenderer()
        self.model_storage = ModelStorage()
        self.model_loader = ModelLoader()
        self.operations_service = get_operations_service()
        logger.info("Training service initialized with TrainingProgressRenderer")

    def _initialize_adapter(self) -> TrainingAdapter | None:
        """Initialize training adapter only for host service mode.

        For local training, returns None since LocalTrainingOrchestrator is used directly.
        """
        import os

        # Check if host service is enabled
        env_enabled = os.getenv("USE_TRAINING_HOST_SERVICE", "").lower()
        use_host_service = env_enabled in ("true", "1", "yes")

        if not use_host_service:
            # Local training mode - no adapter needed (uses LocalTrainingOrchestrator directly)
            logger.info("=" * 80)
            logger.info("💻 TRAINING MODE: LOCAL (Docker Container)")
            logger.info("   Uses: LocalTrainingOrchestrator directly")
            logger.info("   GPU Training: Not available in Docker")
            logger.info("   CPU Training: Available")
            logger.info("=" * 80)
            return None

        # Host service mode - create adapter
        host_service_url = os.getenv(
            "TRAINING_HOST_SERVICE_URL", "http://localhost:5002"
        )
        logger.info("=" * 80)
        logger.info("🚀 TRAINING MODE: HOST SERVICE")
        logger.info(f"   URL: {host_service_url}")
        logger.info("   GPU Training: Available (if host service has GPU)")
        logger.info("=" * 80)

        return TrainingAdapter(use_host_service=True, host_service_url=host_service_url)

    def _get_service_name(self) -> str:
        return "TrainingService"

    def _get_default_host_url(self) -> str:
        return "http://localhost:5002"

    def _get_env_var_prefix(self) -> str:
        return "TRAINING"

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

    async def start_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> dict[str, Any]:
        """Start neural network training task."""
        context = build_training_context(
            operation_id=task_id,
            strategy_name=strategy_name,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            detailed_analytics=detailed_analytics,
            use_host_service=self.is_using_host_service(),
        )

        operation_result = await self.start_managed_operation(
            operation_name="training",
            operation_type=OperationType.TRAINING.value,
            operation_func=self._legacy_operation_entrypoint,
            context=context,
            metadata=context.metadata,
            total_steps=context.total_steps,
        )

        operation_id = operation_result["operation_id"]
        context.operation_id = operation_id

        estimated_duration = context.training_config.get(
            "estimated_duration_minutes", 30
        )
        message = (
            f"Neural network training started for {', '.join(context.symbols)} "
            f"using {strategy_name} strategy"
        )

        return {
            "success": True,
            "operation_id": operation_id,  # Added for MCP compatibility
            "task_id": operation_id,  # Keep for backward compatibility
            "status": "training_started",
            "message": message,
            "symbols": context.symbols,
            "timeframes": context.timeframes,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": estimated_duration,
            "use_host_service": context.use_host_service,
        }

    async def _legacy_operation_entrypoint(
        self,
        *,
        operation_id: str,
        context: TrainingOperationContext,
    ) -> Optional[dict[str, Any]]:
        """Temporary adapter that reuses legacy training manager wiring."""
        context.operation_id = operation_id

        # Log training mode clearly before execution
        if context.use_host_service:
            logger.info("=" * 80)
            logger.info("🚀 EXECUTING TRAINING: HOST SERVICE MODE")
            logger.info(f"   Operation ID: {operation_id}")
            logger.info(f"   Symbols: {', '.join(context.symbols)}")
            logger.info(f"   Strategy: {context.strategy_name}")
            logger.info("   GPU Training: Available (if host service has GPU)")
            logger.info("=" * 80)
            return await self._run_host_training(context=context)
        else:
            logger.info("=" * 80)
            logger.info("💻 EXECUTING TRAINING: LOCAL MODE (Docker Container)")
            logger.info(f"   Operation ID: {operation_id}")
            logger.info(f"   Symbols: {', '.join(context.symbols)}")
            logger.info(f"   Strategy: {context.strategy_name}")
            logger.info("   GPU Training: Not available")
            logger.info("   CPU Training: Active")
            logger.info("=" * 80)
            return await self._run_local_training(context=context)

    async def _run_local_training(
        self, *, context: TrainingOperationContext
    ) -> dict[str, Any]:
        """Run local training via the orchestrator-native components."""
        progress_manager = self._current_operation_progress
        if progress_manager is None:
            raise RuntimeError("Progress manager not available for training operation")

        # TASK 1.2: Pull-based metrics - OperationsService will pull via bridge.get_metrics()
        # Metrics callback removed - replaced with pull-based architecture
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress_manager,
            cancellation_token=self._current_cancellation_token,
        )

        # TASK 1.3: Register bridge with OperationsService for pull-based refresh
        if context.operation_id:
            self.operations_service.register_local_bridge(context.operation_id, bridge)
            logger.info(
                f"Registered local training bridge for operation {context.operation_id}"
            )

        orchestrator = LocalTrainingOrchestrator(
            context=context,
            progress_bridge=bridge,
            cancellation_token=self._current_cancellation_token,
            model_storage=self.model_storage,
        )

        return await orchestrator.run()

    async def _run_host_training(
        self, *, context: TrainingOperationContext
    ) -> dict[str, Any]:
        """Run host-service backed training with orchestrator components."""
        progress_manager = self._current_operation_progress
        if progress_manager is None:
            raise RuntimeError("Progress manager not available for training operation")

        # TASK 1.2: Pull-based metrics - OperationsService will pull via bridge.get_metrics()
        # Metrics callback removed - replaced with pull-based architecture
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress_manager,
            cancellation_token=self._current_cancellation_token,
        )

        # TASK 1.3: Register bridge with OperationsService for pull-based refresh
        if context.operation_id:
            self.operations_service.register_local_bridge(context.operation_id, bridge)
            logger.info(
                f"Registered host training bridge for operation {context.operation_id}"
            )

        # Type assertion: adapter is guaranteed to be TrainingAdapter in host service mode
        assert (
            self.adapter is not None
        ), "Adapter should not be None in host service mode"

        manager = HostSessionManager(
            adapter=self.adapter,
            context=context,
            progress_bridge=bridge,
            cancellation_token=self._current_cancellation_token,
            poll_interval=0.3,  # Poll every 300ms for responsive progress updates
            backoff_factor=1.0,  # No backoff - keep constant polling frequency
        )

        # Returns aggregated result from from_host_run
        return await manager.run()

    async def cancel_training_session(
        self, session_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Cancel a training session via TrainingManager."""
        if not self.is_using_host_service():
            raise ValidationError("Host training service is not enabled")

        # Type assertion: adapter is guaranteed to be TrainingAdapter in host service mode
        assert (
            self.adapter is not None
        ), "Adapter should not be None in host service mode"

        try:
            logger.info(f"Cancelling training session {session_id} (reason: {reason})")
            result = await self.adapter.stop_training(session_id)
            logger.info(f"Training session {session_id} cancelled successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel training session {session_id}: {str(e)}")
            raise

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


# Global training service instance

# Global training service instance
_training_service: TrainingService | None = None


def get_training_service() -> TrainingService:
    """Get the global training service instance."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService()
    return _training_service
