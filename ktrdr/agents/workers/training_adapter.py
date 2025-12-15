"""Training worker adapter for agent orchestrator.

Adapts the existing TrainingService for use by the agent orchestrator,
handling the polling loop and result transformation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import yaml

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus
from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class TrainingServiceProtocol(Protocol):
    """Protocol for TrainingService to enable dependency injection."""

    async def start_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]: ...


class WorkerError(Exception):
    """Error during worker execution."""

    pass


class TrainingWorkerAdapter:
    """Adapts TrainingService for orchestrator use.

    This adapter:
    1. Starts training via TrainingService
    2. Polls the training operation until complete
    3. Returns training metrics for gate evaluation
    """

    POLL_INTERVAL = 10.0  # seconds between status checks

    def __init__(
        self,
        operations_service: OperationsService,
        training_service: TrainingServiceProtocol | None = None,
    ):
        """Initialize the training worker adapter.

        Args:
            operations_service: Service for operation tracking and queries.
            training_service: Training service instance (created if not provided).
        """
        self.ops = operations_service
        self._training_service = training_service

    @property
    def training(self) -> TrainingServiceProtocol:
        """Get training service, creating lazily if needed."""
        if self._training_service is None:
            # Lazy import to avoid circular dependency
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.api.services.training_service import TrainingService

            registry = get_worker_registry()
            self._training_service = TrainingService(worker_registry=registry)  # type: ignore[assignment]
        return self._training_service  # type: ignore[return-value]

    async def run(
        self,
        parent_operation_id: str,
        strategy_path: str,
    ) -> dict[str, Any]:
        """Run training phase.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            strategy_path: Path to strategy YAML file.

        Returns:
            Training metrics including accuracy, loss, model_path, training_op_id.

        Raises:
            WorkerError: If training fails.
            asyncio.CancelledError: If cancelled.
        """
        logger.info(
            f"Starting training phase for parent {parent_operation_id} "
            f"with strategy {strategy_path}"
        )

        # Load strategy config
        config = self._load_strategy_config(strategy_path)

        # Extract training parameters from config
        strategy_name = config.get("name", "unknown_strategy")
        symbols = self._get_symbols(config)
        timeframes = self._get_timeframes(config)

        # Start training
        training_result = await self.training.start_training(
            strategy_name=strategy_name,
            symbols=symbols,
            timeframes=timeframes,
        )

        training_op_id = training_result["operation_id"]
        logger.info(f"Training started with operation {training_op_id}")

        # Poll until complete
        try:
            result = await self._poll_until_complete(training_op_id)
            return result
        except asyncio.CancelledError:
            # Cancel the training operation too
            logger.info(f"Cancelling training operation {training_op_id}")
            await self.ops.cancel_operation(training_op_id, "Parent cancelled")
            raise

    async def _poll_until_complete(self, training_op_id: str) -> dict[str, Any]:
        """Poll training operation until it completes.

        Args:
            training_op_id: The training operation ID to poll.

        Returns:
            Training metrics dict.

        Raises:
            WorkerError: If training fails.
            asyncio.CancelledError: If training was cancelled.
        """
        while True:
            op = await self.ops.get_operation(training_op_id)

            if op is None:
                raise WorkerError(f"Training operation {training_op_id} not found")

            if op.status == OperationStatus.COMPLETED:
                result_summary = op.result_summary or {}
                logger.info(
                    f"Training completed for {training_op_id} "
                    f"with accuracy {result_summary.get('accuracy')}"
                )
                return {
                    "success": True,
                    "training_op_id": training_op_id,
                    "accuracy": result_summary.get("accuracy", 0),
                    "final_loss": result_summary.get("final_loss", 1.0),
                    "initial_loss": result_summary.get("initial_loss", 1.0),
                    "model_path": result_summary.get("model_path"),
                }

            if op.status == OperationStatus.FAILED:
                error = op.error_message or "Unknown error"
                logger.error(f"Training failed for {training_op_id}: {error}")
                raise WorkerError(f"Training failed: {error}")

            if op.status == OperationStatus.CANCELLED:
                raise asyncio.CancelledError("Training was cancelled")

            # Log progress
            if op.progress:
                logger.debug(
                    f"Training progress for {training_op_id}: "
                    f"{op.progress.percentage:.1f}% - {op.progress.current_step}"
                )

            await asyncio.sleep(self.POLL_INTERVAL)

    def _load_strategy_config(self, strategy_path: str) -> dict[str, Any]:
        """Load strategy configuration from YAML file.

        Args:
            strategy_path: Path to strategy YAML file.

        Returns:
            Parsed strategy configuration dict.
        """
        with open(strategy_path) as f:
            return yaml.safe_load(f)

    def _get_symbols(self, config: dict[str, Any]) -> list[str]:
        """Extract symbols from strategy config.

        Args:
            config: Strategy configuration dict.

        Returns:
            List of symbols to train on.
        """
        training_data = config.get("training_data", {})
        symbols_config = training_data.get("symbols", {})

        # Check for explicit list
        if "list" in symbols_config:
            return symbols_config["list"]

        # Default fallback
        return ["EURUSD"]

    def _get_timeframes(self, config: dict[str, Any]) -> list[str]:
        """Extract timeframes from strategy config.

        Args:
            config: Strategy configuration dict.

        Returns:
            List of timeframes to train on.
        """
        training_data = config.get("training_data", {})
        timeframes_config = training_data.get("timeframes", {})

        # Check for explicit list
        if "list" in timeframes_config:
            return timeframes_config["list"]

        # Default fallback
        return ["1h"]
