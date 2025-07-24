"""
Training Service

Provides neural network training functionality for the API layer.
"""

import asyncio
import uuid
import yaml
import tempfile
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
from ktrdr.training.training_manager import TrainingManager

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
        self.training_manager = TrainingManager()
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
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start neural network training task."""
        # Simple delegation to training manager (no complex fallback logic)
        return await self._start_training_via_manager(
            symbol=symbol,
            timeframes=timeframes,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            task_id=task_id,
            detailed_analytics=detailed_analytics
        )
    
    async def _start_training_via_manager(
        self,
        symbol: str,
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start neural network training task using TrainingManager (host service or local)."""
        # Validate strategy file exists - check both Docker and local paths
        strategy_paths = [
            Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
            Path(f"strategies/{strategy_name}.yaml"),       # Local path
        ]
        
        strategy_path = None
        for path in strategy_paths:
            if path.exists():
                strategy_path = path
                break
        
        if not strategy_path:
            raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
        
        # Load and validate strategy config
        with open(strategy_path, 'r') as f:
            strategy_config = yaml.safe_load(f)
        
        validation_issues = _validate_strategy_config(strategy_config, strategy_name)
        error_issues = [issue for issue in validation_issues if issue.severity == "error"]
        
        if error_issues:
            error_messages = [f"{issue.category}: {issue.message}" for issue in error_issues]
            raise ValidationError("Strategy validation failed:\n" + "\n".join(error_messages))
        
        # Apply analytics settings if requested
        if detailed_analytics:
            strategy_config = self._apply_analytics_settings(strategy_config)
        
        training_config = strategy_config.get("model", {}).get("training", {})
        
        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframes[0] if timeframes else "1h",
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
            parameters={
                "strategy_name": strategy_name,
                "strategy_path": str(strategy_path),
                "training_type": strategy_config.get("model", {}).get("type", "mlp"),
                "epochs": training_config.get("epochs", 100),
                "timeframes": timeframes,
                "use_host_service": self.training_manager.is_using_host_service()
            },
        )

        # Create operation
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Start training using TrainingManager
        task = asyncio.create_task(
            self._run_training_via_manager_async(
                operation_id, strategy_path, [symbol], timeframes, start_date, end_date
            )
        )

        await self.operations_service.start_operation(operation_id, task)

        return {
            "success": True,
            "task_id": operation_id,
            "status": "training_started",
            "message": f"Neural network training started for {symbol} using {strategy_name} strategy",
            "symbol": symbol,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": training_config.get("estimated_duration_minutes", 30),
            "use_host_service": self.training_manager.is_using_host_service()
        }

    def _apply_analytics_settings(self, strategy_config: dict) -> dict:
        """Apply detailed analytics settings to strategy configuration."""
        if "training" not in strategy_config:
            strategy_config["training"] = {}
        
        strategy_config["training"]["detailed_analytics"] = True
        strategy_config["training"]["save_intermediate_models"] = True
        strategy_config["training"]["track_gradients"] = True
        
        return strategy_config

    async def _run_training_via_manager_async(
        self,
        operation_id: str,
        strategy_path: Path,
        symbols: List[str],
        timeframes: List[str], 
        start_date: Optional[str],
        end_date: Optional[str]
    ):
        """Run training via TrainingManager with progress updates."""
        try:
            # Create progress callback
            async def progress_callback(progress: Dict[str, Any]):
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=progress.get("progress_percentage", 0.0),
                        current_step=progress.get("current_step", "Training in progress")
                    )
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
                progress_callback=progress_callback
            )
            
            # Update with completion
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=100.0,
                    current_step="Training completed successfully",
                    completed=True
                )
            )
            
            logger.info(f"Training completed successfully for operation {operation_id}")
            
        except Exception as e:
            # Update with error
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=0.0,
                    current_step=f"Training failed: {str(e)}",
                    error=str(e)
                )
            )
            logger.error(f"Training failed for operation {operation_id}: {str(e)}")

    async def start_multi_symbol_training(
        self,
        symbols: List[str],
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start multi-symbol neural network training task."""
        # Simple delegation to the same manager-based method (no complex fallback logic)
        return await self._start_training_via_manager_multi_symbol(
            symbols=symbols,
            timeframes=timeframes,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            task_id=task_id,
            detailed_analytics=detailed_analytics
        )

    async def _start_training_via_manager_multi_symbol(
        self,
        symbols: List[str],
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start multi-symbol neural network training task using TrainingManager."""
        # Validate strategy file exists
        strategy_paths = [
            Path(f"/app/strategies/{strategy_name}.yaml"),
            Path(f"strategies/{strategy_name}.yaml"),
        ]
        
        strategy_path = None
        for path in strategy_paths:
            if path.exists():
                strategy_path = path
                break
        
        if not strategy_path:
            raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
        
        # Load and validate strategy config
        with open(strategy_path, 'r') as f:
            strategy_config = yaml.safe_load(f)
        
        validation_issues = _validate_strategy_config(strategy_config, strategy_name)
        error_issues = [issue for issue in validation_issues if issue.severity == "error"]
        
        if error_issues:
            error_messages = [f"{issue.category}: {issue.message}" for issue in error_issues]
            raise ValidationError("Strategy validation failed:\n" + "\n".join(error_messages))
        
        if detailed_analytics:
            strategy_config = self._apply_analytics_settings(strategy_config)
        
        training_config = strategy_config.get("model", {}).get("training", {})
        
        # Create operation metadata for multi-symbol
        metadata = OperationMetadata(
            symbol=symbols[0] if symbols else "MULTI",  # Use first symbol for compatibility
            timeframe=timeframes[0] if timeframes else "1h",
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
            parameters={
                "strategy_name": strategy_name,
                "strategy_path": str(strategy_path),
                "training_type": "multi_symbol",
                "symbols": symbols,
                "timeframes": timeframes,
                "epochs": training_config.get("epochs", 100),
                "use_host_service": self.training_manager.is_using_host_service()
            },
        )

        # Create operation
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Start training using TrainingManager
        task = asyncio.create_task(
            self._run_training_via_manager_async(
                operation_id, strategy_path, symbols, timeframes, start_date, end_date
            )
        )

        await self.operations_service.start_operation(operation_id, task)

        return {
            "success": True,
            "task_id": operation_id,
            "status": "training_started",
            "message": f"Multi-symbol neural network training started for {', '.join(symbols)} using {strategy_name} strategy",
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": training_config.get("estimated_duration_minutes", 30),
            "use_host_service": self.training_manager.is_using_host_service()
        }
    
    async def _start_multi_symbol_training_with_host_service(
        self,
        symbols: List[str],
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start multi-symbol neural network training task using the training host service."""
        logger.info(f"Starting multi-symbol training with host service: {symbols} on {timeframes}")
        
        # Load and validate strategy configuration
        strategy_paths = [
            Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
            Path(f"strategies/{strategy_name}.yaml"),       # Local path
        ]
        
        strategy_path = None
        for path in strategy_paths:
            if path.exists():
                strategy_path = path
                break
        
        if not strategy_path:
            raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
        
        # Load strategy config
        with open(strategy_path, 'r') as f:
            strategy_config = yaml.safe_load(f)
        
        # Apply analytics settings if requested
        if detailed_analytics:
            strategy_config = self._apply_analytics_settings(strategy_config)
        
        # Validate the strategy configuration
        _validate_strategy_config(strategy_config, strategy_name)
        
        # Extract training configuration
        training_config = strategy_config.get("training", {})
        
        # Create operation for progress tracking
        operation_id = task_id or str(uuid.uuid4())
        
        symbols_str = "_".join(symbols)  # Combined symbols for metadata
        await self.operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol=symbols_str,
                timeframes=timeframes,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                parameters={
                    "symbols": symbols,
                    "multi_symbol": True,
                }
            ),
        )
        
        # Initialize progress
        await self.operations_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=0.0, current_step="Initializing multi-symbol training host service"
            ),
        )
        
        # Get training host client
        training_host_settings = get_training_host_settings()
        host_client = get_training_host_client(training_host_settings.base_url)
        
        try:
            # Check if host service is available
            if not await host_client.is_available():
                raise TrainingHostServiceError("Training host service is not available")
            
            # Prepare configuration for host service (multi-symbol)
            host_config = {
                "strategy_config": strategy_config,
                "symbols": symbols,  # Multiple symbols instead of single symbol
                "timeframes": timeframes,
                "start_date": start_date,
                "end_date": end_date,
                "epochs": training_config.get("epochs", 100),
                "validation_split": training_config.get("validation_split", 0.2),
                "batch_size": training_config.get("batch_size", 32),
                "learning_rate": training_config.get("learning_rate", 0.001),
                "early_stopping": training_config.get("early_stopping", True),
                "enable_gpu": True,
                "mixed_precision": True,
                "model_type": strategy_config.get("model", {}).get("type", "mlp"),
                "multi_symbol": True,  # Flag for multi-symbol training
            }
            
            # Update progress
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0, current_step=f"Starting multi-symbol training session on host service ({len(symbols)} symbols)"
                ),
            )
            
            # Start training session on host service
            session_id = await host_client.start_training_session(host_config)
            logger.info(f"Started multi-symbol training session {session_id} on host service")
            
            # Start background task to monitor progress
            monitoring_task = asyncio.create_task(
                self._monitor_host_service_training(
                    operation_id, session_id, host_client, training_host_settings
                )
            )
            logger.info(f"Started monitoring task for operation {operation_id}, session {session_id}")
            
            return {
                "success": True,
                "task_id": operation_id,
                "status": "started",
                "message": f"Multi-symbol training started successfully on host service (session: {session_id})",
                "session_id": session_id,
                "symbols": symbols,
                "timeframes": timeframes,
                "strategy_name": strategy_name,
                "use_host_service": True,
                "multi_symbol": True
            }
            
        except Exception as e:
            # Update operation with error
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=0.0, 
                    current_step=f"Host service error: {str(e)}",
                    error=str(e)
                ),
            )
            raise TrainingHostServiceError(f"Training host service failed: {str(e)}")
    
    async def _start_multi_symbol_training_local(
        self,
        symbols: List[str],
        timeframes: List[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> Dict[str, Any]:
        """Start multi-symbol neural network training task using local Docker training."""
        # Validate strategy file exists - check both Docker and local paths
        strategy_paths = [
            Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
            Path(f"strategies/{strategy_name}.yaml"),       # Local path
        ]
        
        strategy_path = None
        for path in strategy_paths:
            if path.exists():
                strategy_path = path
                break
        
        if not strategy_path:
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
        
        # Create operation metadata for multi-symbol training
        symbols_str = "_".join(symbols)  # Combined symbols for metadata
        metadata = OperationMetadata(
            symbol=symbols_str,  # Use combined symbols string
            timeframe=timeframes[0] if timeframes else "1h",  # Use first timeframe for metadata compatibility
            start_date=datetime.fromisoformat(start_date) if start_date else None,
            end_date=datetime.fromisoformat(end_date) if end_date else None,
            parameters={
                "strategy_name": strategy_name,
                "strategy_path": str(strategy_path),
                "training_type": "multi_symbol_" + strategy_config.get("model", {}).get("type", "mlp"),
                "epochs": training_config.get("epochs", 100),
                "symbols": symbols,  # Store all symbols in parameters
                "timeframes": timeframes,  # Store all timeframes in parameters
                "multi_symbol": True,  # Mark as multi-symbol training
            },
        )

        # Create operation using operations service
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.TRAINING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Start multi-symbol training in background
        task = asyncio.create_task(
            self._run_multi_symbol_training_async(
                operation_id,
                symbols,
                timeframes,
                strategy_name,
                start_date,
                end_date,
                detailed_analytics,
            )
        )

        # Register task with operations service for cancellation support
        await self.operations_service.start_operation(operation_id, task)

        return {
            "success": True,
            "task_id": operation_id,
            "status": "training_started",
            "message": f"Multi-symbol neural network training started for {symbols} using {strategy_name} strategy",
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "estimated_duration_minutes": 45,  # Longer for multi-symbol
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
        timeframes: List[str],
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
                    percentage=5.0, current_step="Validating training configuration"
                ),
            )

            # Use the real strategy file that exists - check both Docker and local paths
            strategy_paths = [
                Path(f"/app/strategies/{strategy_name}.yaml"),  # Docker path
                Path(f"strategies/{strategy_name}.yaml"),       # Local path
            ]
            
            strategy_path = None
            for path in strategy_paths:
                if path.exists():
                    strategy_path = str(path)
                    break
            
            if not strategy_path:
                raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
            
            # Load strategy config to get training parameters
            with open(strategy_path, 'r') as f:
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
                strategy_config["model"]["training"]["analytics"]["export_alerts"] = True
                
                logger.info(f"Analytics enabled for training operation {operation_id}")
            
            # Update training_config reference after modification
            training_config = strategy_config.get("model", {}).get("training", {})

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
                
                # If analytics is enabled, create a temporary strategy file with modified config
                actual_strategy_path = strategy_path
                if detailed_analytics:
                    temp_strategy_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                    try:
                        yaml.dump(strategy_config, temp_strategy_file, default_flow_style=False, indent=2)
                        temp_strategy_file.flush()
                        actual_strategy_path = temp_strategy_file.name
                        logger.info(f"Created temporary strategy config with analytics: {actual_strategy_path}")
                    finally:
                        temp_strategy_file.close()

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
                import json
                
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
                        actual_strategy_path,
                        symbol,
                        timeframes,
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
                    
                    # Clean up temporary strategy file if analytics was enabled
                    if detailed_analytics and actual_strategy_path != strategy_path:
                        try:
                            Path(actual_strategy_path).unlink(missing_ok=True)
                            logger.info(f"Cleaned up temporary strategy config: {actual_strategy_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up temporary strategy config: {e}")

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

    async def _run_multi_symbol_training_async(
        self,
        operation_id: str,
        symbols: List[str],
        timeframes: List[str],
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
                Path(f"strategies/{strategy_name}.yaml"),       # Local path
            ]
            
            strategy_path = None
            for path in strategy_paths:
                if path.exists():
                    strategy_path = path
                    break
            
            if not strategy_path:
                raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")
            
            # Load strategy configuration
            with open(strategy_path, 'r') as f:
                strategy_config = yaml.safe_load(f)
            
            training_config = strategy_config.get("model", {}).get("training", {})
            total_epochs = training_config.get("epochs", 100)

            # Phase 1: Configuration and validation (10%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=5.0,
                    current_step="Configuring multi-symbol training environment",
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
                strategy_config["model"]["training"]["analytics"]["export_alerts"] = True
                
                logger.info(f"Analytics enabled for multi-symbol training operation {operation_id}")
            
            # Update training_config reference after modification
            training_config = strategy_config.get("model", {}).get("training", {})

            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0,
                    current_step="Preparing multi-symbol training environment",
                    items_total=total_epochs,
                ),
            )

            try:
                # Phase 2: Setup trainer (15%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=15.0, current_step="Initializing multi-symbol strategy trainer"
                    ),
                )

                trainer = StrategyTrainer(models_dir="models")
                
                # If analytics is enabled, create a temporary strategy file with modified config
                actual_strategy_path = strategy_path
                if detailed_analytics:
                    temp_strategy_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                    try:
                        yaml.dump(strategy_config, temp_strategy_file, default_flow_style=False, indent=2)
                        temp_strategy_file.flush()
                        actual_strategy_path = temp_strategy_file.name
                        logger.info(f"Created temporary strategy config with analytics: {actual_strategy_path}")
                    finally:
                        temp_strategy_file.close()

                # Phase 3: Training loop with epoch-based progress (15% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting multi-symbol training for {total_epochs} epochs",
                        items_processed=0,
                        items_total=total_epochs,
                    ),
                )

                # Phase 4: Run actual multi-symbol training with progress monitoring (20% to 90%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=20.0,
                        current_step=f"Starting multi-symbol neural network training for {len(symbols)} symbols...",
                        items_processed=0,
                        items_total=total_epochs,
                    ),
                )

                # Create a shared progress state file for sync/async communication
                import json
                
                progress_file = Path(tempfile.gettempdir()) / f"training_progress_{operation_id}.json"
                progress_state = {
                    "current_epoch": 0,
                    "total_epochs": total_epochs,
                    "current_step": "Starting multi-symbol training...",
                    "last_metrics": {},
                    "multi_symbol": True,
                }
                
                # Write initial progress state
                with open(progress_file, 'w') as f:
                    json.dump(progress_state, f)
                
                def sync_progress_callback(epoch: int, total_epochs: int, metrics: dict):
                    """Callback that writes progress to shared file."""
                    try:
                        progress_type = metrics.get('progress_type', 'epoch')
                        is_multi_symbol = metrics.get('multi_symbol', False)
                        
                        if progress_type == 'batch':
                            # Batch-level progress: more frequent updates with bars
                            batch_idx = metrics.get('batch', 0)
                            total_batches_per_epoch = metrics.get('total_batches_per_epoch', 1)
                            completed_batches = metrics.get('completed_batches', 0)
                            total_batches = metrics.get('total_batches', 1)
                            
                            # Use bars (market data points) instead of batches
                            total_bars_processed = metrics.get('total_bars_processed', 0)
                            total_bars_all_epochs = metrics.get('total_bars_all_epochs', 1)
                            
                            symbols_info = f" ({len(symbols)} symbols)" if is_multi_symbol else ""
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}{symbols_info}"
                            
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
                                "progress_type": "batch",
                                "multi_symbol": is_multi_symbol,
                            })
                        else:
                            # Epoch-level progress: complete epoch with validation
                            total_bars_processed = metrics.get('total_bars_processed', 0)
                            total_bars_all_epochs = metrics.get('total_bars_all_epochs', 1)
                            
                            symbols_info = f" ({len(symbols)} symbols)" if is_multi_symbol else ""
                            current_step = f"Epoch: {epoch}, Bars: {total_bars_processed:,}/{total_bars_all_epochs:,}{symbols_info} (Val Acc: {metrics.get('val_accuracy', 0):.3f})"
                            
                            progress_state.update({
                                "current_epoch": epoch,
                                "total_epochs": total_epochs,
                                "total_bars_processed": total_bars_processed,
                                "total_bars_all_epochs": total_bars_all_epochs,
                                "current_step": current_step,
                                "last_metrics": metrics,
                                "progress_type": "epoch",
                                "multi_symbol": is_multi_symbol,
                            })
                        
                        with open(progress_file, 'w') as f:
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
                        start_date,
                        end_date,
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
                                with open(progress_file, 'r') as f:
                                    current_progress = json.load(f)
                                
                                current_epoch = current_progress.get("current_epoch", 0)
                                current_step = current_progress.get("current_step", "Multi-symbol training...")
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
                    
                    # Clean up temporary strategy file if analytics was enabled
                    if detailed_analytics and actual_strategy_path != strategy_path:
                        try:
                            Path(actual_strategy_path).unlink(missing_ok=True)
                            logger.info(f"Cleaned up temporary strategy config: {actual_strategy_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up temporary strategy config: {e}")

                # Phase 5: Finalization (95%)
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=95.0, current_step="Processing multi-symbol training results"
                    ),
                )

                # Prepare results summary using real training results
                if results:
                    results_summary = {
                        "model_path": results.get("model_path"),
                        "training_metrics": results.get("training_metrics", {}),
                        "test_metrics": results.get("test_metrics", {}),
                        "per_symbol_metrics": results.get("per_symbol_metrics", {}),  # Multi-symbol specific
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

                logger.info(f"Multi-symbol training operation {operation_id} completed successfully")

            except Exception as e:
                logger.error(
                    f"Multi-symbol training operation {operation_id} failed: {str(e)}", exc_info=True
                )
                await self.operations_service.fail_operation(operation_id, str(e))

        except Exception as e:
            logger.error(
                f"Multi-symbol training operation {operation_id} failed: {str(e)}", exc_info=True
            )
            await self.operations_service.fail_operation(operation_id, str(e))
    
    async def _monitor_host_service_training(
        self,
        operation_id: str,
        session_id: str,
        host_client,
        training_host_settings: Dict[str, Any]
    ):
        """
        Monitor training progress on the host service and update operations framework.
        
        This method polls the training host service status endpoint and converts
        the response to operations framework format for CLI consumption.
        """
        logger.info(f"Starting host service monitoring for operation {operation_id}, session {session_id}")
        
        try:
            last_percentage = 0.0
            
            while True:
                try:
                    # Poll host service status
                    status_data = await host_client.get_training_status(session_id)
                    
                    host_status = status_data.get("status", "unknown")
                    host_progress = status_data.get("progress", {})
                    host_metrics = status_data.get("metrics", {})
                    
                    logger.info(f"[MONITOR] Session {session_id}: status={host_status}, progress={host_progress}, metrics={host_metrics}")
                    
                    # Convert host service progress to operations framework format
                    if host_status == "running":
                        # Extract progress information
                        current_epoch = host_progress.get("epoch", 0)
                        total_epochs = host_progress.get("total_epochs", 100)
                        current_batch = host_progress.get("batch", 0)
                        total_batches = host_progress.get("total_batches", 0)
                        
                        # Calculate percentage (20% to 90% range for training phase)
                        if total_epochs > 0:
                            epoch_progress = (current_epoch / total_epochs)
                            if total_batches > 0 and current_batch > 0:
                                # Add batch-level granularity within the epoch
                                batch_progress = (current_batch / total_batches) / total_epochs
                                epoch_progress += batch_progress
                            
                            percentage = 20.0 + (epoch_progress * 70.0)  # 20% to 90%
                        else:
                            percentage = host_progress.get("progress_percent", 0.0)
                        
                        # Ensure percentage doesn't go backwards or exceed limits
                        percentage = max(percentage, last_percentage)
                        percentage = min(percentage, 90.0)
                        
                        # Format current step with epoch and batch info
                        current_step = f"Epoch: {current_epoch}, Batch: {current_batch}"
                        if total_epochs > 0:
                            current_step += f"/{total_epochs}"
                        if total_batches > 0:
                            current_step += f", Batches: {current_batch}/{total_batches}"
                        
                        # Add metrics if available
                        if host_metrics:
                            accuracy = host_metrics.get("accuracy", 0)
                            loss = host_metrics.get("loss", 0)
                            if accuracy > 0:
                                current_step += f" (Acc: {accuracy:.3f})"
                            if loss > 0:
                                current_step += f" (Loss: {loss:.4f})"
                        
                        # Update operations framework
                        logger.info(f"[MONITOR] Updating operation {operation_id}: {percentage:.1f}% - {current_step}")
                        await self.operations_service.update_progress(
                            operation_id,
                            OperationProgress(
                                percentage=percentage,
                                current_step=current_step,
                                items_processed=current_epoch,
                                items_total=total_epochs,
                            ),
                        )
                        
                        last_percentage = percentage
                        
                    elif host_status == "completed":
                        # Training completed successfully
                        logger.info(f"Host service training completed for session {session_id}")
                        
                        # Final progress update
                        await self.operations_service.update_progress(
                            operation_id,
                            OperationProgress(
                                percentage=95.0,
                                current_step="Processing training results from host service",
                            ),
                        )
                        
                        # Extract results and complete operation
                        results_summary = {
                            "session_id": session_id,
                            "host_metrics": host_metrics,
                            "training_completed": True,
                            "host_service_used": True
                        }
                        
                        await self.operations_service.complete_operation(
                            operation_id, result_summary=results_summary
                        )
                        break
                        
                    elif host_status == "failed":
                        # Training failed on host service
                        error_msg = status_data.get("error", "Training failed on host service")
                        logger.error(f"Host service training failed for session {session_id}: {error_msg}")
                        
                        await self.operations_service.fail_operation(operation_id, error_msg)
                        break
                        
                    elif host_status == "stopped":
                        # Training was stopped
                        logger.info(f"Host service training stopped for session {session_id}")
                        
                        await self.operations_service.fail_operation(
                            operation_id, "Training stopped on host service"
                        )
                        break
                        
                    else:
                        # Unknown status, continue monitoring but log warning
                        logger.warning(f"Unknown host service status: {host_status}")
                    
                    # Wait before next poll
                    await asyncio.sleep(3)
                    
                except asyncio.CancelledError:
                    logger.info(f"[MONITOR] Training monitoring cancelled for operation {operation_id}")
                    # Don't update operations service on cancellation, let the CLI handle it
                    break
                except Exception as e:
                    logger.error(f"[MONITOR] Error polling host service status: {str(e)}")
                    
                    # If we can't communicate with host service, fail the operation
                    if "Connection" in str(e) or "timeout" in str(e).lower():
                        await self.operations_service.fail_operation(
                            operation_id, f"Lost connection to training host service: {str(e)}"
                        )
                        break
                    
                    # For other errors, wait and retry
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"Host service monitoring failed for operation {operation_id}: {str(e)}")
            await self.operations_service.fail_operation(
                operation_id, f"Host service monitoring error: {str(e)}"
            )
