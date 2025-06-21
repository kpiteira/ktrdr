"""
Training Service

Provides neural network training functionality for the API layer.
"""

import asyncio
import uuid
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from ktrdr import get_logger
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import (
    OperationType,
    OperationMetadata,
    OperationProgress,
)
from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr.training.model_storage import ModelStorage
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.errors import ValidationError, DataError
from ktrdr.api.endpoints.strategies import _validate_strategy_config

logger = get_logger(__name__)

# In-memory storage for loaded models (in production, use proper model registry)
_loaded_models: Dict[str, Any] = {}


class TrainingService(BaseService):
    """Service for neural network training operations."""

    def __init__(self, operations_service: Optional[OperationsService] = None):
        """Initialize the training service."""
        super().__init__()
        self.model_storage = ModelStorage()
        self.model_loader = ModelLoader()
        if operations_service is None:
            raise ValueError("OperationsService must be provided to TrainingService")
        self.operations_service = operations_service
        logger.info("Training service initialized")

    async def health_check(self) -> Dict[str, Any]:
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
        symbol: str,
        timeframe: str,
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start neural network training task."""
        # Validate strategy file exists
        strategy_path = Path(f"/app/strategies/{strategy_name}.yaml")
        if not strategy_path.exists():
            raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
        
        # Load strategy config to get training parameters
        with open(strategy_path, 'r') as f:
            strategy_config = yaml.safe_load(f)
        
        # Validate strategy configuration before training
        validation_issues = _validate_strategy_config(strategy_config, strategy_name)
        error_issues = [issue for issue in validation_issues if issue.severity == "error"]
        
        if error_issues:
            # Format validation errors into clear message
            error_messages = []
            for issue in error_issues:
                error_messages.append(f"{issue.category}: {issue.message}")
            
            validation_error = "Strategy validation failed:\n" + "\n".join(error_messages)
            raise ValidationError(validation_error)
        
        training_config = strategy_config.get("model", {}).get("training", {})
        
        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
            parameters={
                "strategy_name": strategy_name,
                "strategy_path": str(strategy_path),
                "training_type": strategy_config.get("model", {}).get("type", "mlp"),
                "epochs": training_config.get("epochs", 100),
            },
        )

        # Create operation using operations service
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Start training in background
        task = asyncio.create_task(
            self._run_training_async(
                operation_id,
                symbol,
                timeframe,
                strategy_name,
                start_date,
                end_date,
            )
        )

        # Register task with operations service for cancellation support
        await self.operations_service.start_operation(operation_id, task)

        return {
            "success": True,
            "task_id": operation_id,
            "status": "training_started",
            "message": f"Neural network training started for {symbol} using {strategy_name} strategy",
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": 30,
        }


    async def get_model_performance(self, task_id: str) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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

    async def load_trained_model(self, model_name: str) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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

    async def list_trained_models(self) -> Dict[str, Any]:
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
        timeframe: str,
        strategy_name: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ):
        """Run training task asynchronously with data-driven progress tracking."""
        try:
            logger.info(f"Starting background training operation {operation_id}")

            # Phase 1: Validation (5%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=5.0, current_step="Validating training configuration"
                ),
            )

            # Use the real strategy file that exists in the Docker volume
            strategy_path = f"/app/strategies/{strategy_name}.yaml"
            
            # Load strategy config to get training parameters
            with open(strategy_path, 'r') as f:
                strategy_config = yaml.safe_load(f)
            
            training_config = strategy_config.get("model", {}).get("training", {})
            total_epochs = training_config.get("epochs", 100)

            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0,
                    current_step="Preparing training environment",
                    items_total=total_epochs,
                ),
            )

            try:
                # Phase 2: Setup trainer (15%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=15.0, current_step="Initializing strategy trainer"
                    ),
                )

                trainer = StrategyTrainer(models_dir="models")

                # Phase 3: Training loop with epoch-based progress (15% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting training for {total_epochs} epochs",
                        items_processed=0,
                        items_total=total_epochs,
                    ),
                )

                # Phase 4: Run actual training with progress monitoring (20% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step="Starting neural network training...",
                        items_processed=0,
                        items_total=total_epochs,
                    ),
                )

                # Create a shared progress state file for sync/async communication
                import tempfile
                import json
                from pathlib import Path
                
                progress_file = Path(tempfile.gettempdir()) / f"training_progress_{operation_id}.json"
                progress_state = {
                    "current_epoch": 0,
                    "total_epochs": total_epochs,
                    "current_step": "Starting training...",
                    "last_metrics": {}
                }
                
                # Write initial progress state
                with open(progress_file, 'w') as f:
                    json.dump(progress_state, f)
                
                def sync_progress_callback(epoch: int, total_epochs: int, metrics: dict):
                    """Callback that writes progress to shared file."""
                    try:
                        progress_type = metrics.get('progress_type', 'epoch')
                        
                        if progress_type == 'batch':
                            # Batch-level progress: more frequent updates with bars
                            batch_idx = metrics.get('batch', 0)
                            total_batches_per_epoch = metrics.get('total_batches_per_epoch', 1)
                            completed_batches = metrics.get('completed_batches', 0)
                            total_batches = metrics.get('total_batches', 1)
                            
                            # Use bars (market data points) instead of batches
                            total_bars_processed = metrics.get('total_bars_processed', 0)
                            total_bars_all_epochs = metrics.get('total_bars_all_epochs', 1)
                            
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}"
                            
                            progress_state.update({
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
                                "progress_type": "batch"
                            })
                        else:
                            # Epoch-level progress: complete epoch with validation
                            total_bars_processed = metrics.get('total_bars_processed', 0)
                            total_bars_all_epochs = metrics.get('total_bars_all_epochs', 1)
                            
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,} (Val Acc: {metrics.get('val_accuracy', 0):.3f})"
                            
                            progress_state.update({
                                "current_epoch": epoch,
                                "total_epochs": total_epochs,
                                "total_bars_processed": total_bars_processed,
                                "total_bars_all_epochs": total_bars_all_epochs,
                                "current_step": current_step,
                                "last_metrics": metrics,
                                "progress_type": "epoch"
                            })
                        
                        with open(progress_file, 'w') as f:
                            json.dump(progress_state, f)
                    except Exception as e:
                        logger.warning(f"Failed to update progress file: {e}")

                # Start training in background with progress monitoring
                import concurrent.futures
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Submit training task
                    training_future = executor.submit(
                        trainer.train_strategy,
                        strategy_path,
                        symbol,
                        timeframe,
                        start_date,
                        end_date,
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
                                with open(progress_file, 'r') as f:
                                    current_progress = json.load(f)
                                
                                current_epoch = current_progress.get("current_epoch", 0)
                                current_step = current_progress.get("current_step", "Training...")
                                progress_type = current_progress.get("progress_type", "epoch")
                                
                                # Calculate fine-grained progress based on bars (market data points)
                                if progress_type == "batch":
                                    completed_batches = current_progress.get("completed_batches", 0)
                                    total_batches = current_progress.get("total_batches", 1)
                                    total_bars_processed = current_progress.get("total_bars_processed", 0)
                                    total_bars_all_epochs = current_progress.get("total_bars_all_epochs", 1)
                                    
                                    # Only update if batch changed (avoid spam)
                                    if completed_batches != last_reported_batch and total_bars_all_epochs > 0:
                                        # Map bars progress to 20% -> 90% range  
                                        bars_progress = (total_bars_processed / total_bars_all_epochs) * 70  # 70% of range
                                        percentage = 20.0 + bars_progress
                                        
                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                            ),
                                        )
                                        last_reported_batch = completed_batches
                                else:
                                    # Epoch-level progress (fallback or validation updates)
                                    total_bars_processed = current_progress.get("total_bars_processed", 0)
                                    total_bars_all_epochs = current_progress.get("total_bars_all_epochs", 0)
                                    
                                    if total_bars_all_epochs > 0:
                                        # Use bars progress if available
                                        bars_progress = (total_bars_processed / total_bars_all_epochs) * 70
                                        percentage = 20.0 + bars_progress
                                        
                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                items_processed=total_bars_processed,
                                                items_total=total_bars_all_epochs,
                                            ),
                                        )
                                    elif total_epochs > 0:
                                        # Fallback to epoch progress
                                        epoch_progress = (current_epoch / total_epochs) * 70
                                        percentage = 20.0 + epoch_progress
                                        
                                        await self.operations_service.update_progress(
                                            operation_id,
                                            OperationProgress(
                                                percentage=min(percentage, 90.0),
                                                current_step=current_step,
                                                items_processed=current_epoch,
                                                items_total=total_epochs,
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
                    except:
                        pass

                # Phase 5: Finalization (95%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=95.0, current_step="Processing training results"
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
