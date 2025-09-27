"""
Training Service

Provides neural network training functionality for the API layer.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationProgress, OperationType
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.services.training import TrainingOperationContext, build_training_context
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError
from ktrdr.training.model_storage import ModelStorage
from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr.training.training_adapter import TrainingAdapter
from ktrdr.training.training_manager import TrainingManager

logger = get_logger(__name__)

# In-memory storage for loaded models (in production, use proper model registry)
_loaded_models: dict[str, Any] = {}


class TrainingService(ServiceOrchestrator[TrainingAdapter]):
    """Service for neural network training operations."""

    def __init__(self) -> None:
        super().__init__()
        self.model_storage = ModelStorage()
        self.model_loader = ModelLoader()
        self.operations_service = get_operations_service()
        logger.info("Training service initialized")

    def _initialize_adapter(self) -> TrainingAdapter:
        """Initialize training adapter via the legacy training manager."""
        self.training_manager = TrainingManager()
        return self.training_manager.training_adapter

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
            "task_id": operation_id,
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
        await self._run_training_via_manager_async(
            operation_id=operation_id,
            strategy_path=context.strategy_path,
            symbols=context.symbols,
            timeframes=context.timeframes,
            start_date=context.start_date,
            end_date=context.end_date,
        )
        return None

    async def _run_training_via_manager_async(
        self,
        operation_id: str,
        strategy_path: Path,
        symbols: list[str],
        timeframes: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ):
        """Run training via TrainingManager with progress updates."""
        try:
            # Create progress callback
            async def progress_callback(progress: dict[str, Any]):
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=progress.get("progress_percentage", 0.0),
                        current_step=progress.get(
                            "current_step", "Training in progress"
                        ),
                        steps_completed=progress.get("steps_completed", 0),
                        steps_total=progress.get("steps_total", 100),
                        items_processed=progress.get("items_processed", 0),
                        items_total=progress.get("items_total", None),
                        current_item=progress.get("current_item", None),
                    ),
                )

            # Use TrainingManager to run training (automatically routes to host service or local)
            result = await self.training_manager.train_multi_symbol_strategy(
                strategy_config_path=str(strategy_path),
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date or "2020-01-01",
                end_date=end_date or datetime.utcnow().strftime("%Y-%m-%d"),
                validation_split=0.2,
                data_mode="local",
                progress_callback=progress_callback,
            )

            # Check if this is host service mode (returns session_id) or local mode (completes training)
            if result and result.get("session_id"):
                # Host service mode - store session_id for status polling
                session_id = result["session_id"]
                logger.info(
                    f"Training started on host service with session {session_id}"
                )

                # Store session_id in operation metadata for status polling
                operation = await self.operations_service.get_operation(operation_id)
                if operation and hasattr(operation.metadata, "parameters"):
                    operation.metadata.parameters["session_id"] = session_id

                # Update progress to indicate training started on host service
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=15.0,
                        current_step=f"Training started on host service (session: {session_id})",
                        steps_completed=1,
                        steps_total=10,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )
            else:
                # Local mode - training completed
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=100.0,
                        current_step="Training completed successfully",
                        steps_completed=10,
                        steps_total=10,
                        items_processed=100,
                        items_total=100,
                        current_item="Complete",
                    ),
                )
                logger.info(
                    f"Local training completed successfully for operation {operation_id}"
                )

        except Exception as e:
            # Update with error
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=0.0,
                    current_step=f"Training failed: {str(e)}",
                    steps_completed=0,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None,
                ),
            )
            logger.error(f"Training failed for operation {operation_id}: {str(e)}")

    async def cancel_training_session(
        self, session_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Cancel a training session via TrainingManager."""
        try:
            logger.info(f"Cancelling training session {session_id} (reason: {reason})")
            result = await self.training_manager.stop_training(session_id)
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

        # Extract metrics from training results
        results = operation.result_summary or {}
        config = operation.metadata.parameters.get("config", {})

        # Get training metrics from results
        training_metrics = results.get("training_metrics", {})
        test_metrics = results.get("test_metrics", {})
        model_info = results.get("model_info", {})

        return {
            "success": True,
            "task_id": task_id,
            "status": operation.status.value,
            "training_metrics": {
                "final_train_loss": training_metrics.get("final_train_loss", 0.0),
                "final_val_loss": training_metrics.get("final_val_loss", 0.0),
                "final_train_accuracy": training_metrics.get(
                    "final_train_accuracy", 0.0
                ),
                "final_val_accuracy": training_metrics.get("final_val_accuracy", 0.0),
                "epochs_completed": operation.progress.items_processed
                or config.get("epochs", 100),
                "early_stopped": training_metrics.get("early_stopped", False),
                "training_time_minutes": training_metrics.get(
                    "training_time_minutes", 0.0
                ),
            },
            "test_metrics": {
                "test_loss": test_metrics.get("test_loss", 0.0),
                "test_accuracy": test_metrics.get("test_accuracy", 0.0),
                "precision": test_metrics.get("precision", 0.0),
                "recall": test_metrics.get("recall", 0.0),
                "f1_score": test_metrics.get("f1_score", 0.0),
            },
            "model_info": {
                "model_size_bytes": model_info.get("model_size_bytes", 0),
                "parameters_count": model_info.get("parameters_count", 0),
                "architecture": model_info.get(
                    "architecture",
                    f"mlp_{'_'.join(map(str, config.get('hidden_layers', [64, 32, 16])))}",
                ),
            },
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

        # Get model path from training results
        results = operation.result_summary or {}
        model_path = results.get("model_path")
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

    async def _run_training_async(
        self,
        operation_id: str,
        symbol: str,
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str],
        end_date: Optional[str],
        detailed_analytics: bool = False,
    ):
        """Run training task asynchronously with data-driven progress tracking."""
        try:
            logger.info(f"Starting background training operation {operation_id}")

            # Phase 1: Validation (5%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=5.0,
                    current_step="Validating training configuration",
                    steps_completed=0,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None,
                ),
            )

            # Use the real strategy file that exists - check both Docker and local paths
            strategy_paths = [
                Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
                Path(f"strategies/{strategy_name}.yaml"),  # Local path
            ]

            strategy_path = None
            for path in strategy_paths:
                if path.exists():
                    strategy_path = str(path)
                    break

            if not strategy_path:
                raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")

            # Load strategy config to get training parameters
            with open(strategy_path) as f:
                strategy_config = yaml.safe_load(f)

            training_config = strategy_config.get("model", {}).get("training", {})
            total_epochs = training_config.get("epochs", 100)

            # Inject analytics configuration if detailed_analytics is enabled
            if detailed_analytics:
                # Ensure model.training.analytics exists in strategy config
                if "model" not in strategy_config:
                    strategy_config["model"] = {}
                if "training" not in strategy_config["model"]:
                    strategy_config["model"]["training"] = {}
                if "analytics" not in strategy_config["model"]["training"]:
                    strategy_config["model"]["training"]["analytics"] = {}

                # Enable analytics
                strategy_config["model"]["training"]["analytics"]["enabled"] = True
                strategy_config["model"]["training"]["analytics"]["export_csv"] = True
                strategy_config["model"]["training"]["analytics"]["export_json"] = True
                strategy_config["model"]["training"]["analytics"][
                    "export_alerts"
                ] = True

                logger.info(f"Analytics enabled for training operation {operation_id}")

            # Update training_config reference after modification
            training_config = strategy_config.get("model", {}).get("training", {})

            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0,
                    current_step="Preparing training environment",
                    steps_completed=1,
                    steps_total=10,
                    items_processed=0,
                    items_total=total_epochs,
                    current_item=None,
                ),
            )

            try:
                # Phase 2: Setup trainer (15%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=15.0,
                        current_step="Initializing strategy trainer",
                        steps_completed=2,
                        steps_total=10,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                trainer = StrategyTrainer(models_dir="models")

                # If analytics is enabled, create a temporary strategy file with modified config
                actual_strategy_path = str(strategy_path)
                if detailed_analytics:
                    temp_strategy_file = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".yaml", delete=False
                    )
                    try:
                        yaml.dump(
                            strategy_config,
                            temp_strategy_file,
                            default_flow_style=False,
                            indent=2,
                        )
                        temp_strategy_file.flush()
                        actual_strategy_path = temp_strategy_file.name
                        logger.info(
                            f"Created temporary strategy config with analytics: {actual_strategy_path}"
                        )
                    finally:
                        temp_strategy_file.close()

                # Phase 3: Training loop with epoch-based progress (15% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting training for {total_epochs} epochs",
                        steps_completed=3,
                        steps_total=10,
                        items_processed=0,
                        items_total=total_epochs,
                        current_item=None,
                    ),
                )

                # Phase 4: Run actual training with progress monitoring (20% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step="Starting neural network training...",
                        steps_completed=3,
                        steps_total=10,
                        items_processed=0,
                        items_total=total_epochs,
                        current_item=None,
                    ),
                )

                # Create a shared progress state file for sync/async communication
                import json

                progress_file = (
                    Path(tempfile.gettempdir())
                    / f"training_progress_{operation_id}.json"
                )
                progress_state = {
                    "current_epoch": 0,
                    "total_epochs": total_epochs,
                    "current_step": "Starting training...",
                    "last_metrics": {},
                }

                # Write initial progress state
                with open(progress_file, "w") as f:
                    json.dump(progress_state, f)

                def sync_progress_callback(
                    epoch: int, total_epochs: int, metrics: dict
                ):
                    """Callback that writes progress to shared file."""
                    try:
                        progress_type = metrics.get("progress_type", "epoch")

                        if progress_type == "batch":
                            # Batch-level progress: more frequent updates with bars
                            batch_idx = metrics.get("batch", 0)
                            total_batches_per_epoch = metrics.get(
                                "total_batches_per_epoch", 1
                            )
                            completed_batches = metrics.get("completed_batches", 0)
                            total_batches = metrics.get("total_batches", 1)

                            # Use bars (market data points) instead of batches
                            total_bars_processed = metrics.get(
                                "total_bars_processed", 0
                            )
                            total_bars_all_epochs = metrics.get(
                                "total_bars_all_epochs", 1
                            )

                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}"

                            progress_state.update(
                                {
                                    "current_epoch": epoch,
                                    "total_epochs": total_epochs,
                                    "current_batch": batch_idx,
                                    "total_batches_per_epoch": total_batches_per_epoch,
                                    "completed_batches": completed_batches,
                                    "total_batches": total_batches,
                                    "total_bars_processed": total_bars_processed,
                                    "total_bars_all_epochs": total_bars_all_epochs,
                                    "current_step": current_step,
                                    "last_metrics": metrics,
                                    "progress_type": "batch",
                                }
                            )
                        else:
                            # Epoch-level progress: complete epoch with validation
                            total_bars_processed = metrics.get(
                                "total_bars_processed", 0
                            )
                            total_bars_all_epochs = metrics.get(
                                "total_bars_all_epochs", 1
                            )

                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,} (Val Acc: {metrics.get('val_accuracy', 0):.3f})"

                            progress_state.update(
                                {
                                    "current_epoch": epoch,
                                    "total_epochs": total_epochs,
                                    "total_bars_processed": total_bars_processed,
                                    "total_bars_all_epochs": total_bars_all_epochs,
                                    "current_step": current_step,
                                    "last_metrics": metrics,
                                    "progress_type": "epoch",
                                }
                            )

                        with open(progress_file, "w") as f:
                            json.dump(progress_state, f)
                    except Exception as e:
                        logger.warning(f"Failed to update progress file: {e}")

                # Start training in background with progress monitoring
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Submit training task
                    training_future = executor.submit(
                        trainer.train_strategy,
                        actual_strategy_path,
                        symbol,
                        timeframes,
                        start_date or "",
                        end_date or "",
                        training_config.get("validation_split", 0.2),
                        "local",
                        sync_progress_callback,
                    )

                    # Monitor progress and update operations service
                    last_reported_batch = -1
                    while not training_future.done():
                        try:
                            # Read progress from shared file
                            if progress_file.exists():
                                with open(progress_file) as f:
                                    current_progress = json.load(f)

                                current_epoch = current_progress.get("current_epoch", 0)
                                current_step = current_progress.get(
                                    "current_step", "Training..."
                                )
                                progress_type = current_progress.get(
                                    "progress_type", "epoch"
                                )

                                # Calculate fine-grained progress based on bars (market data points)
                                if progress_type == "batch":
                                    completed_batches = current_progress.get(
                                        "completed_batches", 0
                                    )
                                    current_progress.get("total_batches", 1)
                                    total_bars_processed = current_progress.get(
                                        "total_bars_processed", 0
                                    )
                                    total_bars_all_epochs = current_progress.get(
                                        "total_bars_all_epochs", 1
                                    )

                                    # Only update if batch changed (avoid spam)
                                    if (
                                        completed_batches != last_reported_batch
                                        and total_bars_all_epochs > 0
                                    ):
                                        # Map bars progress to 20% -> 90% range
                                        bars_progress = (
                                            total_bars_processed / total_bars_all_epochs
                                        ) * 70  # 70% of range
                                        percentage = 20.0 + bars_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_progress.get(
                                                    "current_epoch", 0
                                                )
                                                + 1,
                                                steps_total=total_epochs,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                                current_item=None,
                                            ),
                                        )
                                        last_reported_batch = completed_batches
                                else:
                                    # Epoch-level progress (fallback or validation updates)
                                    total_bars_processed = current_progress.get(
                                        "total_bars_processed", 0
                                    )
                                    total_bars_all_epochs = current_progress.get(
                                        "total_bars_all_epochs", 0
                                    )

                                    if total_bars_all_epochs > 0:
                                        # Use bars progress if available
                                        bars_progress = (
                                            total_bars_processed / total_bars_all_epochs
                                        ) * 70
                                        percentage = 20.0 + bars_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_progress.get(
                                                    "current_epoch", 0
                                                )
                                                + 1,
                                                steps_total=total_epochs,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                                current_item=None,
                                            ),
                                        )
                                    elif total_epochs > 0:
                                        # Fallback to epoch progress
                                        epoch_progress = (
                                            current_epoch / total_epochs
                                        ) * 70
                                        percentage = 20.0 + epoch_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_epoch,
                                                steps_total=total_epochs,
                                                items_processed=current_epoch,
                                                items_total=total_epochs,
                                                current_item=None,
                                            ),
                                        )
                        except Exception as e:
                            logger.warning(f"Progress monitoring error: {e}")

                        # Wait before next check
                        await asyncio.sleep(2)

                    # Get training results
                    results = training_future.result()

                    # Clean up progress file
                    try:
                        progress_file.unlink(missing_ok=True)
                    except Exception:
                        pass

                    # Clean up temporary strategy file if analytics was enabled
                    if detailed_analytics and actual_strategy_path != strategy_path:
                        try:
                            Path(actual_strategy_path).unlink(missing_ok=True)
                            logger.info(
                                f"Cleaned up temporary strategy config: {actual_strategy_path}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to clean up temporary strategy config: {e}"
                            )

                # Phase 5: Finalization (95%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=95.0,
                        current_step="Processing training results",
                        steps_completed=9,
                        steps_total=10,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                # Prepare results summary using real training results
                if results:
                    results_summary = {
                        "model_path": results.get("model_path"),
                        "training_metrics": results.get("training_metrics", {}),
                        "test_metrics": results.get("test_metrics", {}),
                        "model_info": results.get("model_info", {}),
                    }
                else:
                    # Fallback if no results returned
                    results_summary = {
                        "model_path": None,
                        "training_metrics": {},
                        "test_metrics": {},
                        "model_info": {},
                    }

                # Complete the operation
                await self.operations_service.complete_operation(
                    operation_id, result_summary=results_summary
                )

                logger.info(f"Training operation {operation_id} completed successfully")

            except Exception as e:
                logger.error(
                    f"Training operation {operation_id} failed: {str(e)}", exc_info=True
                )
                await self.operations_service.fail_operation(operation_id, str(e))

        except Exception as e:
            logger.error(
                f"Training operation {operation_id} failed: {str(e)}", exc_info=True
            )
            await self.operations_service.fail_operation(operation_id, str(e))

    async def _run_multi_symbol_training_async(
        self,
        operation_id: str,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str],
        end_date: Optional[str],
        detailed_analytics: bool,
    ):
        """Run multi-symbol training asynchronously with progress updates."""
        try:
            # Get strategy configuration
            strategy_paths = [
                Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
                Path(f"strategies/{strategy_name}.yaml"),  # Local path
            ]

            strategy_path = None
            for path in strategy_paths:
                if path.exists():
                    strategy_path = path
                    break

            if not strategy_path:
                raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")

            # Load strategy configuration
            with open(strategy_path) as f:
                strategy_config = yaml.safe_load(f)

            training_config = strategy_config.get("model", {}).get("training", {})
            total_epochs = training_config.get("epochs", 100)

            # Phase 1: Configuration and validation (10%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=5.0,
                    current_step="Configuring multi-symbol training environment",
                    steps_completed=0,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None,
                ),
            )

            # Enable analytics if requested
            if detailed_analytics:
                # Ensure model.training.analytics exists in strategy config
                if "model" not in strategy_config:
                    strategy_config["model"] = {}
                if "training" not in strategy_config["model"]:
                    strategy_config["model"]["training"] = {}
                if "analytics" not in strategy_config["model"]["training"]:
                    strategy_config["model"]["training"]["analytics"] = {}

                # Enable analytics
                strategy_config["model"]["training"]["analytics"]["enabled"] = True
                strategy_config["model"]["training"]["analytics"]["export_csv"] = True
                strategy_config["model"]["training"]["analytics"]["export_json"] = True
                strategy_config["model"]["training"]["analytics"][
                    "export_alerts"
                ] = True

                logger.info(
                    f"Analytics enabled for multi-symbol training operation {operation_id}"
                )

            # Update training_config reference after modification
            training_config = strategy_config.get("model", {}).get("training", {})

            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0,
                    current_step="Preparing multi-symbol training environment",
                    steps_completed=1,
                    steps_total=10,
                    items_processed=0,
                    items_total=total_epochs,
                    current_item=None,
                ),
            )

            try:
                # Phase 2: Setup trainer (15%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=15.0,
                        current_step="Initializing multi-symbol strategy trainer",
                        steps_completed=2,
                        steps_total=10,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                trainer = StrategyTrainer(models_dir="models")

                # If analytics is enabled, create a temporary strategy file with modified config
                actual_strategy_path = str(strategy_path)
                if detailed_analytics:
                    temp_strategy_file = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".yaml", delete=False
                    )
                    try:
                        yaml.dump(
                            strategy_config,
                            temp_strategy_file,
                            default_flow_style=False,
                            indent=2,
                        )
                        temp_strategy_file.flush()
                        actual_strategy_path = temp_strategy_file.name
                        logger.info(
                            f"Created temporary strategy config with analytics: {actual_strategy_path}"
                        )
                    finally:
                        temp_strategy_file.close()

                # Phase 3: Training loop with epoch-based progress (15% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting multi-symbol training for {total_epochs} epochs",
                        steps_completed=3,
                        steps_total=10,
                        items_processed=0,
                        items_total=total_epochs,
                        current_item=None,
                    ),
                )

                # Phase 4: Run actual multi-symbol training with progress monitoring (20% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting multi-symbol neural network training for {len(symbols)} symbols...",
                        steps_completed=3,
                        steps_total=10,
                        items_processed=0,
                        items_total=total_epochs,
                        current_item=None,
                    ),
                )

                # Create a shared progress state file for sync/async communication
                import json

                progress_file = (
                    Path(tempfile.gettempdir())
                    / f"training_progress_{operation_id}.json"
                )
                progress_state = {
                    "current_epoch": 0,
                    "total_epochs": total_epochs,
                    "current_step": "Starting multi-symbol training...",
                    "last_metrics": {},
                    "multi_symbol": True,
                }

                # Write initial progress state
                with open(progress_file, "w") as f:
                    json.dump(progress_state, f)

                def sync_progress_callback(
                    epoch: int, total_epochs: int, metrics: dict
                ):
                    """Callback that writes progress to shared file."""
                    try:
                        progress_type = metrics.get("progress_type", "epoch")
                        is_multi_symbol = metrics.get("multi_symbol", False)

                        if progress_type == "batch":
                            # Batch-level progress: more frequent updates with bars
                            batch_idx = metrics.get("batch", 0)
                            total_batches_per_epoch = metrics.get(
                                "total_batches_per_epoch", 1
                            )
                            completed_batches = metrics.get("completed_batches", 0)
                            total_batches = metrics.get("total_batches", 1)

                            # Use bars (market data points) instead of batches
                            total_bars_processed = metrics.get(
                                "total_bars_processed", 0
                            )
                            total_bars_all_epochs = metrics.get(
                                "total_bars_all_epochs", 1
                            )

                            symbols_info = (
                                f" ({len(symbols)} symbols)" if is_multi_symbol else ""
                            )
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}{symbols_info}"

                            progress_state.update(
                                {
                                    "current_epoch": epoch,
                                    "total_epochs": total_epochs,
                                    "current_batch": batch_idx,
                                    "total_batches_per_epoch": total_batches_per_epoch,
                                    "completed_batches": completed_batches,
                                    "total_batches": total_batches,
                                    "total_bars_processed": total_bars_processed,
                                    "total_bars_all_epochs": total_bars_all_epochs,
                                    "current_step": current_step,
                                    "last_metrics": metrics,
                                    "progress_type": "batch",
                                    "multi_symbol": is_multi_symbol,
                                }
                            )
                        else:
                            # Epoch-level progress: complete epoch with validation
                            total_bars_processed = metrics.get(
                                "total_bars_processed", 0
                            )
                            total_bars_all_epochs = metrics.get(
                                "total_bars_all_epochs", 1
                            )

                            symbols_info = (
                                f" ({len(symbols)} symbols)" if is_multi_symbol else ""
                            )
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}{symbols_info} (Val Acc: {metrics.get('val_accuracy', 0):.3f})"

                            progress_state.update(
                                {
                                    "current_epoch": epoch,
                                    "total_epochs": total_epochs,
                                    "total_bars_processed": total_bars_processed,
                                    "total_bars_all_epochs": total_bars_all_epochs,
                                    "current_step": current_step,
                                    "last_metrics": metrics,
                                    "progress_type": "epoch",
                                    "multi_symbol": is_multi_symbol,
                                }
                            )

                        with open(progress_file, "w") as f:
                            json.dump(progress_state, f)
                    except Exception as e:
                        logger.warning(f"Failed to update progress file: {e}")

                # Start multi-symbol training in background with progress monitoring
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Submit multi-symbol training task
                    training_future = executor.submit(
                        trainer.train_multi_symbol_strategy,
                        actual_strategy_path,
                        symbols,
                        timeframes,
                        start_date or "",
                        end_date or "",
                        training_config.get("validation_split", 0.2),
                        "local",
                        sync_progress_callback,
                    )

                    # Monitor progress and update operations service (same logic as single-symbol)
                    last_reported_batch = -1
                    while not training_future.done():
                        try:
                            # Read progress from shared file
                            if progress_file.exists():
                                with open(progress_file) as f:
                                    current_progress = json.load(f)

                                current_epoch = current_progress.get("current_epoch", 0)
                                current_step = current_progress.get(
                                    "current_step", "Multi-symbol training..."
                                )
                                progress_type = current_progress.get(
                                    "progress_type", "epoch"
                                )

                                # Calculate fine-grained progress based on bars (market data points)
                                if progress_type == "batch":
                                    completed_batches = current_progress.get(
                                        "completed_batches", 0
                                    )
                                    current_progress.get("total_batches", 1)
                                    total_bars_processed = current_progress.get(
                                        "total_bars_processed", 0
                                    )
                                    total_bars_all_epochs = current_progress.get(
                                        "total_bars_all_epochs", 1
                                    )

                                    # Only update if batch changed (avoid spam)
                                    if (
                                        completed_batches != last_reported_batch
                                        and total_bars_all_epochs > 0
                                    ):
                                        # Map bars progress to 20% -> 90% range
                                        bars_progress = (
                                            total_bars_processed / total_bars_all_epochs
                                        ) * 70  # 70% of range
                                        percentage = 20.0 + bars_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_progress.get(
                                                    "current_epoch", 0
                                                )
                                                + 1,
                                                steps_total=total_epochs,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                                current_item=None,
                                            ),
                                        )
                                        last_reported_batch = completed_batches
                                else:
                                    # Epoch-level progress (fallback or validation updates)
                                    total_bars_processed = current_progress.get(
                                        "total_bars_processed", 0
                                    )
                                    total_bars_all_epochs = current_progress.get(
                                        "total_bars_all_epochs", 0
                                    )

                                    if total_bars_all_epochs > 0:
                                        # Use bars progress if available
                                        bars_progress = (
                                            total_bars_processed / total_bars_all_epochs
                                        ) * 70
                                        percentage = 20.0 + bars_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_progress.get(
                                                    "current_epoch", 0
                                                )
                                                + 1,
                                                steps_total=total_epochs,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                                current_item=None,
                                            ),
                                        )
                                    elif total_epochs > 0:
                                        # Fallback to epoch progress
                                        epoch_progress = (
                                            current_epoch / total_epochs
                                        ) * 70
                                        percentage = 20.0 + epoch_progress

                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                steps_completed=current_epoch,
                                                steps_total=total_epochs,
                                                items_processed=current_epoch,
                                                items_total=total_epochs,
                                                current_item=None,
                                            ),
                                        )
                        except Exception as e:
                            logger.warning(f"Progress monitoring error: {e}")

                        # Wait before next check
                        await asyncio.sleep(2)

                    # Get training results
                    results = training_future.result()

                    # Clean up progress file
                    try:
                        progress_file.unlink(missing_ok=True)
                    except Exception:
                        pass

                    # Clean up temporary strategy file if analytics was enabled
                    if detailed_analytics and actual_strategy_path != strategy_path:
                        try:
                            Path(actual_strategy_path).unlink(missing_ok=True)
                            logger.info(
                                f"Cleaned up temporary strategy config: {actual_strategy_path}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to clean up temporary strategy config: {e}"
                            )

                # Phase 5: Finalization (95%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=95.0,
                        current_step="Processing multi-symbol training results",
                        steps_completed=9,
                        steps_total=10,
                        items_processed=0,
                        items_total=None,
                        current_item=None,
                    ),
                )

                # Prepare results summary using real training results
                if results:
                    results_summary = {
                        "model_path": results.get("model_path"),
                        "training_metrics": results.get("training_metrics", {}),
                        "test_metrics": results.get("test_metrics", {}),
                        "per_symbol_metrics": results.get(
                            "per_symbol_metrics", {}
                        ),  # Multi-symbol specific
                        "model_info": results.get("model_info", {}),
                    }
                else:
                    # Fallback if no results returned
                    results_summary = {
                        "model_path": None,
                        "training_metrics": {},
                        "test_metrics": {},
                        "per_symbol_metrics": {},
                        "model_info": {},
                    }

                # Complete the operation
                await self.operations_service.complete_operation(
                    operation_id, result_summary=results_summary
                )

                logger.info(
                    f"Multi-symbol training operation {operation_id} completed successfully"
                )

            except Exception as e:
                logger.error(
                    f"Multi-symbol training operation {operation_id} failed: {str(e)}",
                    exc_info=True,
                )
                await self.operations_service.fail_operation(operation_id, str(e))

        except Exception as e:
            logger.error(
                f"Multi-symbol training operation {operation_id} failed: {str(e)}",
                exc_info=True,
            )
            await self.operations_service.fail_operation(operation_id, str(e))


# Global training service instance
_training_service: TrainingService | None = None


def get_training_service() -> TrainingService:
    """Get the global training service instance."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService()
    return _training_service
