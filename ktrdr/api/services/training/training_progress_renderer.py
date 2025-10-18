"""TrainingProgressRenderer - Renders rich training progress with epoch/batch/GPU info.

This renderer implements the ProgressRenderer interface following the proven pattern
established by DataProgressRenderer. It extracts training-specific context (epochs,
batches, resource usage) and formats rich progress messages for CLI display.
"""

import logging
from typing import Any

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer

logger = logging.getLogger(__name__)


class TrainingProgressRenderer(ProgressRenderer):
    """
    Renders training-specific progress messages with rich context.

    This renderer extracts training-specific information from GenericProgressState.context
    and formats it into rich, informative messages for CLI display. It follows the same
    pattern as DataProgressRenderer.

    Key features:
    - Extracts epoch/batch information from context
    - Displays GPU resource usage when available
    - Handles both local and remote (host service) training progress
    - Thread-safe context tracking
    """

    def __init__(self) -> None:
        """Initialize TrainingProgressRenderer with internal context tracking."""
        # Track current context for state enhancement (like DataProgressRenderer)
        self._current_context: dict[str, Any] = {}

        logger.debug("TrainingProgressRenderer initialized")

    def render_message(self, state: GenericProgressState) -> str:
        """
        Render training-specific progress message with epoch, batch, and GPU info.

        This method extracts structured data from state.context and formats it into
        a rich progress message like:
        - "📊 Processing AAPL (1/5) - Loading Data" (preprocessing)
        - "⚙️ Combining data from 5 symbols" (preparation)
        - "Epoch 5/10" (training)
        - "Epoch 5/10 · Batch 120/500" (training with batch)
        - "Epoch 5/10 · Batch 120/500 🖥️ GPU: 85%" (training with GPU)

        Args:
            state: Current progress state with training context

        Returns:
            Formatted message string with training details
        """
        phase = state.context.get("phase", "")
        preprocessing_step = state.context.get("preprocessing_step")

        # Preprocessing phase - add visual indicators for different steps
        if phase == "preprocessing":
            message = state.message

            # Add phase-specific emoji/icon for visual clarity
            if preprocessing_step == "loading_data":
                return f"📊 {message}"
            elif preprocessing_step == "computing_indicators":
                return f"📈 {message}"
            elif preprocessing_step == "computing_indicator":
                return f"📈 {message}"
            elif preprocessing_step == "generating_fuzzy":
                return f"🔀 {message}"
            elif preprocessing_step == "creating_features":
                return f"🔧 {message}"
            elif preprocessing_step == "generating_labels":
                return f"🏷️ {message}"
            else:
                return message

        # Preparation phase - add visual indicator
        elif phase == "preparation":
            return f"⚙️ {state.message}"

        # Training phase - existing epoch/batch rendering
        epoch_index = state.context.get("epoch_index", 0)
        total_epochs = state.context.get("total_epochs", 0)
        batch_number = state.context.get("batch_number")
        batch_total = state.context.get("batch_total_per_epoch")

        # Build message starting with epoch info
        if epoch_index > 0 and total_epochs > 0:
            message = f"Epoch {epoch_index}/{total_epochs}"

            # Add batch info if available
            if batch_number is not None and batch_total is not None and batch_total > 0:
                message += f" · Batch {batch_number}/{batch_total}"

            # Add GPU info if available
            resource_usage = state.context.get("resource_usage", {})
            if isinstance(resource_usage, dict) and resource_usage.get("gpu_used"):
                gpu_name = resource_usage.get("gpu_name")
                gpu_util = resource_usage.get("gpu_utilization_percent")

                if gpu_util is not None:
                    # Format GPU info
                    gpu_info = f"GPU: {gpu_util:.0f}%"
                    if gpu_name:
                        gpu_info = f"{gpu_name}: {gpu_util:.0f}%"
                    message += f" 🖥️ {gpu_info}"

            return message
        else:
            # Fallback to base message if no epoch context
            return state.message

    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """
        Enhance generic state with training-specific context tracking.

        This method preserves the original state while maintaining internal context
        tracking for consistency across progress updates.

        Args:
            state: Generic progress state to enhance

        Returns:
            Enhanced state (unchanged, as enhancement is tracked internally)
        """
        # Update internal context tracking (preserve DataProgressRenderer pattern)
        if state.context:
            self._current_context.update(state.context)

        # Return state unchanged (context already contains training-specific data)
        return state
