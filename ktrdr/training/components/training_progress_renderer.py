"""
TrainingProgressRenderer - Training-specific progress rendering for ServiceOrchestrator.

This renderer implements the ProgressRenderer interface to provide structured
progress context for training operations, eliminating the need for complex
string parsing in CLI commands.

Key features:
- Training-specific context formatting (model type, symbols, timeframes)
- Smart truncation for multi-symbol/timeframe scenarios
- Both coarse (epoch) and fine (batch) progress information
- Thread-safe message rendering and state enhancement
- Consistent with DataProgressRenderer patterns
"""

import logging
from typing import Any

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer

logger = logging.getLogger(__name__)


class TrainingProgressRenderer(ProgressRenderer):
    """
    Training-specific progress renderer for ServiceOrchestrator integration.

    This renderer provides structured progress context for training operations,
    following the same patterns as DataProgressRenderer from Slice 1. It formats
    training progress with rich context instead of relying on brittle string
    parsing in CLI commands.

    Key features:
    - Model type identification (MLP, CNN, LSTM, etc.)
    - Symbol and timeframe information with smart truncation
    - Epoch and batch progress tracking
    - Thread-safe operations
    - Graceful handling of missing context fields

    Progress format examples:
    - Single symbol: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
    - Multi-symbol: "Training MLP model on AAPL, MSFT (+2 more) [1H, 4H] [epoch 15/50] [3/4]"
    """

    def __init__(self):
        """
        Initialize TrainingProgressRenderer.

        Sets up internal state for context tracking, following the same
        patterns as DataProgressRenderer.
        """
        # Initialize current context tracking (like DataProgressRenderer)
        self._current_context: dict[str, Any] = {}

        logger.debug("TrainingProgressRenderer initialized")

    def render_message(self, state: GenericProgressState) -> str:
        """
        Render training-specific progress message with rich context.

        This method creates structured progress messages for training operations,
        providing clear, consistent information about training status including
        model type, symbols, timeframes, epochs, and batches.

        Args:
            state: Current progress state with training context

        Returns:
            Enhanced message string for training operations

        Examples:
            Single symbol: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
            Multi-symbol: "Training CNN model on AAPL, MSFT (+3 more) [1H, 4H (+1 more)] [epoch 8/20] [1/4]"
        """
        context = state.context or {}

        # Extract training context
        model_type = context.get("model_type", "unknown")
        symbols = context.get("symbols", [])
        timeframes = context.get("timeframes", [])
        current_epoch = context.get("current_epoch", 0)
        total_epochs = context.get("total_epochs", 0)
        current_batch = context.get("current_batch", 0)
        total_batches = context.get("total_batches", 0)

        # Build the training message
        return self._format_training_message(
            model_type,
            symbols,
            timeframes,
            current_epoch,
            total_epochs,
            current_batch,
            total_batches,
            state.current_step,
            state.total_steps,
        )

    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """
        Enhance generic state with training-specific information.

        This method allows the training domain to enhance the progress state
        with training-specific context tracking, following the same patterns
        as DataProgressRenderer.

        Args:
            state: Generic progress state to enhance

        Returns:
            Enhanced progress state with training-specific information
        """
        # Update current context with state context (preserve existing pattern)
        if state.context:
            self._current_context.update(state.context)

        # For training operations, we primarily preserve the state as-is
        # since training is a simpler delegation pattern compared to data
        return state

    def _format_training_message(
        self,
        model_type: str,
        symbols: list[str],
        timeframes: list[str],
        current_epoch: int,
        total_epochs: int,
        current_batch: int,
        total_batches: int,
        current_step: int,
        total_steps: int,
    ) -> str:
        """
        Format training message with all context elements.

        Args:
            model_type: Type of model being trained (MLP, CNN, etc.)
            symbols: List of symbols being trained on
            timeframes: List of timeframes being used
            current_epoch: Current epoch number
            total_epochs: Total number of epochs
            current_batch: Current batch number within epoch
            total_batches: Total batches in epoch
            current_step: Current step from ServiceOrchestrator
            total_steps: Total steps in operation

        Returns:
            Formatted training progress message
        """
        message_parts = []

        # Base message with model type
        base_message = f"Training {model_type} model"
        message_parts.append(base_message)

        # Add symbol information with smart truncation
        if symbols:
            symbols_str = self._format_symbols_with_truncation(symbols)
            message_parts.append(f"on {symbols_str}")

        # Add timeframe information with smart truncation
        if timeframes:
            timeframes_str = self._format_timeframes_with_truncation(timeframes)
            message_parts.append(f"[{timeframes_str}]")

        # Add epoch progress (coarse-grained)
        if total_epochs > 0:
            epoch_str = f"[epoch {current_epoch}/{total_epochs}]"
            message_parts.append(epoch_str)

        # Add batch progress (fine-grained) if available
        if total_batches > 0:
            batch_str = f"(batch {current_batch}/{total_batches})"
            message_parts.append(batch_str)

        # Add step progress from ServiceOrchestrator (overall operation)
        if total_steps > 0:
            step_str = f"[{current_step}/{total_steps}]"
            message_parts.append(step_str)

        return " ".join(message_parts)

    def _format_symbols_with_truncation(self, symbols: list[str]) -> str:
        """
        Format symbols list with smart truncation for readability.

        Args:
            symbols: List of symbol strings

        Returns:
            Formatted symbols string with truncation if needed

        Examples:
            ["AAPL"] -> "AAPL"
            ["AAPL", "MSFT"] -> "AAPL, MSFT"
            ["AAPL", "MSFT", "GOOGL"] -> "AAPL, MSFT, GOOGL"
            ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"] -> "AAPL, MSFT (+3 more)"
        """
        if not symbols:
            return ""

        if len(symbols) <= 3:
            # Show all symbols if 3 or fewer
            return ", ".join(symbols)
        else:
            # Show first 2 symbols and count the rest
            displayed_symbols = symbols[:2]
            remaining_count = len(symbols) - 2
            return f"{', '.join(displayed_symbols)} (+{remaining_count} more)"

    def _format_timeframes_with_truncation(self, timeframes: list[str]) -> str:
        """
        Format timeframes list with smart truncation for readability.

        Args:
            timeframes: List of timeframe strings

        Returns:
            Formatted timeframes string with truncation if needed

        Examples:
            ["1H"] -> "1H"
            ["1H", "4H"] -> "1H, 4H"
            ["1H", "4H", "1D"] -> "1H, 4H (+1 more)"
        """
        if not timeframes:
            return ""

        if len(timeframes) <= 2:
            # Show all timeframes if 2 or fewer
            return ", ".join(timeframes)
        else:
            # Show first 2 timeframes and count the rest
            displayed_timeframes = timeframes[:2]
            remaining_count = len(timeframes) - 2
            return f"{', '.join(displayed_timeframes)} (+{remaining_count} more)"
