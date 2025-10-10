"""Local training runner - thin wrapper around LocalTrainingOrchestrator."""

from __future__ import annotations

from typing import Any

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.training.model_storage import ModelStorage

logger = get_logger(__name__)


class LocalTrainingRunner:
    """
    Execute training locally while forwarding progress to the orchestrator.

    REFACTORED: This is now a thin wrapper around LocalTrainingOrchestrator.
    All training logic has been delegated to LocalTrainingOrchestrator which
    uses TrainingPipeline for the actual work.
    """

    def __init__(
        self,
        *,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        model_storage: ModelStorage | None = None,
    ) -> None:
        """
        Initialize the local training runner.

        Args:
            context: Training operation context
            progress_bridge: Progress bridge for reporting
            cancellation_token: Optional cancellation token
            model_storage: Optional model storage (creates default if not provided)
        """
        self._context = context
        self._bridge = progress_bridge
        self._cancellation_token = cancellation_token
        self._model_storage = model_storage or ModelStorage()

        # Create orchestrator instance
        self._orchestrator = LocalTrainingOrchestrator(
            context=context,
            progress_bridge=progress_bridge,
            cancellation_token=cancellation_token,
            model_storage=self._model_storage,
        )

    async def run(self) -> dict[str, Any]:
        """
        Run the training workflow via orchestrator.

        Delegates all work to LocalTrainingOrchestrator, maintaining
        backward-compatible API.

        Returns:
            Training result with standardized format

        Raises:
            CancellationError: If training is cancelled
        """
        # Delegate to orchestrator
        return await self._orchestrator.run()
