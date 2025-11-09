"""
Training Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but uses
WorkerAPIBase for common infrastructure.
"""

import os
import uuid
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType

# Note: TrainingProgressBridge requires TrainingOperationContext which is complex
# For now, we'll use direct progress callbacks instead
from ktrdr.logging import get_logger
from ktrdr.training.training_manager import TrainingManager
from ktrdr.workers.base import WorkerAPIBase

logger = get_logger(__name__)


class TrainingStartRequest(BaseModel):
    """Request to start training (following training-host pattern)."""

    task_id: Optional[str] = Field(
        default=None,
        description="Optional task ID from backend (for operation ID synchronization)",
    )
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

        # Force local mode (this service should never use remote mode)
        os.environ["USE_TRAINING_HOST_SERVICE"] = "false"

        # Register domain-specific endpoint
        @self.app.post("/training/start")
        async def start_training(request: TrainingStartRequest):
            """
            Start a training operation.

            Follows training-host-service pattern:
            - Accepts task_id from backend for ID synchronization
            - Returns operation_id back to backend
            """
            # Use backend's task_id if provided, generate if not
            operation_id = request.task_id or f"worker_training_{uuid.uuid4().hex[:12]}"

            # Execute work following training-host pattern
            result = await self._execute_training_work(operation_id, request)

            return {
                "success": True,
                "operation_id": operation_id,  # ← Return same ID to backend!
                "status": "started",
                **result,
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

        # 2. Progress tracking (simplified - no bridge needed for now)
        # TrainingManager handles its own progress tracking
        logger.info(f"Starting training for operation {operation_id}")

        # 3. Execute actual work (TrainingManager)
        try:
            # Create training manager
            manager = TrainingManager()

            # Get cancellation token
            cancellation_token = self._operations_service.get_cancellation_token(
                operation_id
            )

            # Run training (async)
            # TODO: Need to create temporary YAML file from strategy_yaml string
            # For now, use a placeholder path
            result = await manager.train_multi_symbol_strategy(
                strategy_config_path="temp_strategy.yaml",  # TODO: Create from request.strategy_yaml
                symbols=request.symbols or ["AAPL"],
                timeframes=request.timeframes or ["1d"],
                start_date=request.start_date or "2020-01-01",
                end_date=request.end_date or "2024-12-31",
                validation_split=0.2,
                data_mode="local",
                progress_callback=None,  # TrainingManager handles progress internally
                cancellation_token=cancellation_token,
            )

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


# Create worker instance
worker = TrainingWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5002")),
    backend_url=os.getenv("KTRDR_API_URL", "http://backend:8000"),
)

# Export FastAPI app for uvicorn
app: FastAPI = worker.app
