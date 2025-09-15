"""
TrainingProgressRenderer - Training-specific progress rendering following DataProgressRenderer pattern.

This renderer implements the ProgressRenderer interface and provides training-specific
features while following the exact same patterns as DataProgressRenderer:
- TimeEstimationEngine integration
- Hierarchical progress display
- Rich context messaging with strategy/symbols/timeframes
- Thread-safe message rendering
- GenericProgressState rendering
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine

logger = logging.getLogger(__name__)


class TrainingProgressRenderer(ProgressRenderer):
    """
    Training-specific progress renderer following DataProgressRenderer pattern.

    This renderer maintains training-specific functionality while working with the
    generic progress infrastructure:

    Key features:
    - TimeEstimationEngine integration for learning-based time estimation
    - Hierarchical progress display (Training → Epochs → Batches → Symbols)
    - Rich context messaging with strategy, symbols, timeframes, models
    - Thread-safe context enhancement and message rendering
    - GenericProgressState enhancement with training-specific context
    - Learning-based time estimation with persistent cache
    """

    def __init__(
        self,
        time_estimation_engine: Optional[TimeEstimationEngine] = None,
        enable_hierarchical_progress: bool = True,
    ):
        """
        Initialize TrainingProgressRenderer with training-specific capabilities.

        Args:
            time_estimation_engine: Optional TimeEstimationEngine for learning-based
                                  time estimation with persistent cache
            enable_hierarchical_progress: Enable hierarchical progress display
                                        (Training → Epochs → Batches → Symbols)
        """
        self.time_estimator = time_estimation_engine
        self.enable_hierarchical = enable_hierarchical_progress

        # Initialize current context tracking (like DataProgressRenderer)
        self._current_context: dict[str, Any] = {}

        # Track operation context for time estimation (preserve existing pattern)
        self._operation_start_time: Optional[datetime] = None
        self._operation_type: Optional[str] = None

        logger.debug(
            "TrainingProgressRenderer initialized with time_estimation: %s, hierarchical: %s",
            time_estimation_engine is not None,
            enable_hierarchical_progress,
        )

    def render_message(self, state: GenericProgressState) -> str:
        """
        Render training-specific progress message with sophisticated enhancements.

        This method contains training-specific message building logic that produces
        messages like:
        - "Training Epoch: 🧠 Epoch 5/50 - Loss: 0.0234 (AAPL+MSFT MLP) ETA: 2h 15m"
        - "Model Validation: ✅ Validation complete - Accuracy: 94.2% (Strategy XYZ)"
        - "Training Complete: 🎯 Model saved - Final Loss: 0.0123 (multi-symbol)"

        Args:
            state: Current progress state

        Returns:
            Enhanced message string for training operations
        """
        # Handle training step detail processing (🧠, ✅, 🎯 indicators)
        step_detail = state.context.get("step_detail", "")
        current_item_detail = state.context.get("current_item_detail")

        if step_detail:
            # Training-specific step details like epoch progress, validation results
            return self._build_training_step_detail_message(state, step_detail)

        # Handle regular training progress messages
        return self._create_enhanced_training_message(state, current_item_detail)

    def _build_training_step_detail_message(
        self, state: GenericProgressState, detail: str
    ) -> str:
        """
        Build training step detail message with training-specific indicators.

        Creates messages like:
        - "🧠 Epoch 5/50 - Loss: 0.0234"
        - "✅ Validation complete - Accuracy: 94.2%"
        - "🎯 Model saved - Final Loss: 0.0123"

        Args:
            state: Current progress state
            detail: Step detail string

        Returns:
            Formatted training step detail message
        """
        # Training context
        symbols = state.context.get("symbols", [])
        model_type = state.context.get("model_type", "")

        # Format symbols display
        symbols_str = ""
        if symbols:
            if len(symbols) == 1:
                symbols_str = f" ({symbols[0]}"
            elif len(symbols) <= 3:
                symbols_str = f" ({'+'.join(symbols)}"
            else:
                symbols_str = f" ({symbols[0]}+{len(symbols)-1} others"

            if model_type:
                symbols_str += f" {model_type})"
            else:
                symbols_str += ")"

        # Progress context
        progress_info = ""
        if state.total and state.total > 0:
            progress_info = f" [{state.current}/{state.total}]"
        elif state.percentage is not None:
            progress_info = f" ({state.percentage:.1f}%)"

        # Time estimation
        eta_str = ""
        if self.time_estimator and state.percentage is not None and state.percentage > 0:
            eta = self._estimate_remaining_time(state)
            if eta:
                eta_str = f" ETA: {self._format_duration(eta)}"

        return f"{detail}{symbols_str}{progress_info}{eta_str}"

    def _create_enhanced_training_message(
        self, state: GenericProgressState, current_item_detail: Optional[str]
    ) -> str:
        """
        Create enhanced training message with training-specific context.

        Args:
            state: Current progress state
            current_item_detail: Optional current item detail

        Returns:
            Enhanced training progress message
        """
        # Base message
        message = state.message or "Training"

        # Training context enhancement
        context_parts = []

        strategy = state.context.get("strategy")
        if strategy:
            context_parts.append(f"Strategy: {strategy}")

        symbols = state.context.get("symbols", [])
        if symbols:
            if len(symbols) == 1:
                context_parts.append(f"Symbol: {symbols[0]}")
            elif len(symbols) <= 3:
                context_parts.append(f"Symbols: {', '.join(symbols)}")
            else:
                context_parts.append(f"Symbols: {symbols[0]} +{len(symbols)-1} others")

        timeframes = state.context.get("timeframes", [])
        if timeframes:
            if len(timeframes) == 1:
                context_parts.append(f"Timeframe: {timeframes[0]}")
            else:
                context_parts.append(f"Timeframes: {', '.join(timeframes)}")

        model_type = state.context.get("model_type")
        if model_type:
            context_parts.append(f"Model: {model_type}")

        # Add current item detail if available
        if current_item_detail:
            context_parts.append(current_item_detail)

        # Progress information
        progress_parts = []

        if state.total and state.total > 0:
            progress_parts.append(f"{state.current}/{state.total}")
        elif state.percentage is not None:
            progress_parts.append(f"{state.percentage:.1f}%")

        # Time estimation
        if self.time_estimator and state.percentage is not None and state.percentage > 0:
            eta = self._estimate_remaining_time(state)
            if eta:
                progress_parts.append(f"ETA: {self._format_duration(eta)}")

        # Assemble final message
        message_parts = [message]

        if progress_parts:
            message_parts.append(f"({', '.join(progress_parts)})")

        if context_parts:
            message_parts.append(f"[{', '.join(context_parts)}]")

        return " ".join(message_parts)

    def _estimate_remaining_time(self, state: GenericProgressState) -> Optional[timedelta]:
        """
        Estimate remaining time using TimeEstimationEngine.

        Args:
            state: Current progress state

        Returns:
            Estimated remaining time or None
        """
        if not self.time_estimator or state.percentage is None or state.percentage <= 0:
            return None

        try:
            # Create operation key for time estimation
            operation_key = self._get_operation_key(state)

            # Get time estimate
            estimated_total = self.time_estimator.estimate_total_time(
                operation_key, state.percentage / 100.0
            )

            if estimated_total:
                elapsed = datetime.now() - (self._operation_start_time or datetime.now())
                remaining = estimated_total - elapsed
                return remaining if remaining.total_seconds() > 0 else None

        except Exception as e:
            logger.debug("Time estimation failed: %s", e)

        return None

    def _get_operation_key(self, state: GenericProgressState) -> str:
        """
        Generate operation key for time estimation.

        Args:
            state: Current progress state

        Returns:
            Operation key string
        """
        # Include training-specific context in operation key
        key_parts = ["training"]

        if self._operation_type:
            key_parts.append(self._operation_type)

        symbols = state.context.get("symbols", [])
        if symbols:
            key_parts.append(f"symbols_{len(symbols)}")

        timeframes = state.context.get("timeframes", [])
        if timeframes:
            key_parts.append(f"tf_{len(timeframes)}")

        model_type = state.context.get("model_type")
        if model_type:
            key_parts.append(model_type)

        return "_".join(key_parts)

    def _format_duration(self, duration: timedelta) -> str:
        """
        Format duration for display.

        Args:
            duration: Time duration

        Returns:
            Formatted duration string
        """
        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def notify_operation_start(self, operation_type: str, context: dict[str, Any]) -> None:
        """
        Notify renderer of operation start for time estimation.

        Args:
            operation_type: Type of training operation
            context: Operation context
        """
        self._operation_start_time = datetime.now()
        self._operation_type = operation_type
        self._current_context.update(context)

        logger.debug(
            "Training operation started: %s with context: %s",
            operation_type,
            context
        )

    def notify_operation_complete(self, operation_type: str, result: dict[str, Any]) -> None:
        """
        Notify renderer of operation completion for time tracking.

        Args:
            operation_type: Type of training operation
            result: Operation result
        """
        if self.time_estimator and self._operation_start_time:
            try:
                # Record actual completion time for learning
                operation_key = f"training_{operation_type}"
                duration = datetime.now() - self._operation_start_time

                self.time_estimator.record_completion(operation_key, duration)

                logger.debug(
                    "Training operation completed: %s in %s",
                    operation_type,
                    duration
                )

            except Exception as e:
                logger.debug("Failed to record completion time: %s", e)

        # Reset operation tracking
        self._operation_start_time = None
        self._operation_type = None
        self._current_context.clear()

    def get_context(self) -> dict[str, Any]:
        """
        Get current training context.

        Returns:
            Current context dictionary
        """
        return self._current_context.copy()
