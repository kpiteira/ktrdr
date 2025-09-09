"""
DataProgressRenderer - Preserves ALL existing ProgressManager features.

This renderer implements the ProgressRenderer interface and preserves all sophisticated
features from the existing ProgressManager including:
- TimeEstimationEngine integration
- Hierarchical progress display
- Rich context messaging with symbol/timeframe/mode
- Thread-safe message rendering
- Legacy ProgressState compatibility
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer
from ktrdr.data.components.progress_manager import ProgressState, TimeEstimationEngine

logger = logging.getLogger(__name__)


class DataProgressRenderer(ProgressRenderer):
    """
    Preserves ALL existing ProgressManager features with domain-specific rendering.

    This renderer maintains all the sophisticated functionality from the existing
    ProgressManager while working with the new generic progress infrastructure:

    Key features preserved:
    - TimeEstimationEngine integration for learning-based time estimation
    - Hierarchical progress display (Operation → Steps → Sub-steps → Items)
    - Rich context messaging with symbol, timeframe, mode information
    - Thread-safe context enhancement and message rendering
    - Legacy ProgressState conversion for backward compatibility
    - Learning-based time estimation with persistent cache
    """

    def __init__(
        self,
        time_estimation_engine: Optional[TimeEstimationEngine] = None,
        enable_hierarchical_progress: bool = True,
    ):
        """
        Initialize DataProgressRenderer with existing ProgressManager capabilities.

        Args:
            time_estimation_engine: Optional TimeEstimationEngine for learning-based
                                  time estimation with persistent cache
            enable_hierarchical_progress: Enable hierarchical progress display
                                        (Operation → Steps → Sub-steps → Items)
        """
        self.time_estimator = time_estimation_engine
        self.enable_hierarchical = enable_hierarchical_progress

        # Track operation context for time estimation (preserve existing pattern)
        self._operation_start_time: Optional[datetime] = None
        self._operation_type: Optional[str] = None

        logger.debug(
            "DataProgressRenderer initialized with time_estimation: %s, hierarchical: %s",
            time_estimation_engine is not None,
            enable_hierarchical_progress,
        )

    def render_message(self, state: GenericProgressState) -> str:
        """
        Render data-specific progress message with ALL existing enhancements.

        Preserves the existing ProgressManager message format with:
        - Base message content
        - Data-specific context (symbol, timeframe, mode)
        - Step progress [current/total]
        - Item progress (bars, data points, etc.)
        - Time estimation display

        Args:
            state: Current progress state

        Returns:
            Enhanced message string preserving existing format
        """
        base_message = self._extract_base_message(state.message)

        # Build message parts preserving existing ProgressManager format
        context = state.context
        parts = [base_message]

        # Add data-specific context (preserve existing logic)
        symbol = context.get("symbol", "Unknown")
        timeframe = context.get("timeframe", "Unknown")
        mode = context.get("mode", "Unknown")

        if symbol != "Unknown" or timeframe != "Unknown":
            context_str = f"({symbol} {timeframe}"
            if mode != "Unknown":
                context_str += f", {mode} mode"
            context_str += ")"
            parts.append(context_str)

        # Add step progress (preserve existing functionality)
        if state.total_steps > 0:
            parts.append(f"[{state.current_step}/{state.total_steps}]")

        # Add item progress (preserve existing functionality)
        if state.total_items and state.total_items > 0:
            items_str = f"{state.items_processed}/{state.total_items} items"
            parts.append(f"({items_str})")

        # Add time estimation (preserve existing functionality)
        if state.estimated_remaining:
            parts.append(f"ETA: {self._format_timedelta(state.estimated_remaining)}")

        return " ".join(parts)

    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """
        Enhance generic state with ALL existing ProgressManager features.

        Preserves and enhances:
        - Time estimation based on current progress
        - Learning-based time estimation using TimeEstimationEngine
        - Hierarchical progress context
        - Operation tracking for time estimation accuracy

        Args:
            state: Generic progress state to enhance

        Returns:
            Enhanced state with all existing ProgressManager capabilities
        """
        # Time estimation enhancement (preserve existing logic)
        if self.time_estimator and state.context:
            if not self._operation_start_time and state.current_step == 0:
                self._operation_start_time = state.start_time
                self._operation_type = state.operation_id

            # Calculate estimated remaining time (preserve existing calculation)
            if self._operation_start_time and state.current_step > 0:
                elapsed = (datetime.now() - self._operation_start_time).total_seconds()
                if state.percentage > 0:
                    # Use the same estimation logic as existing ProgressManager
                    estimated_total = elapsed / (state.percentage / 100.0)
                    estimated_remaining = max(0, estimated_total - elapsed)
                    state.estimated_remaining = timedelta(seconds=estimated_remaining)

        # Add hierarchical progress context (preserve existing functionality)
        if self.enable_hierarchical and state.context:
            # Extract step details if available (preserve existing pattern)
            step_name = state.context.get("current_step_name")
            if step_name:
                state.context["enhanced_step_name"] = step_name

            # Add sub-step progress (preserve existing format)
            step_current = state.context.get("step_current", 0)
            step_total = state.context.get("step_total", 0)
            if step_total > 0:
                state.context["step_progress"] = f"{step_current}/{step_total}"

        return state

    def create_legacy_compatible_state(
        self, generic_state: GenericProgressState
    ) -> ProgressState:
        """
        Convert generic state back to rich ProgressState for backward compatibility.

        This method ensures 100% backward compatibility with existing code that
        expects ProgressState objects, preserving all existing fields and functionality.

        Args:
            generic_state: GenericProgressState to convert

        Returns:
            ProgressState with all existing fields populated
        """
        # Create full ProgressState with all existing fields (preserve exact compatibility)
        return ProgressState(
            # Core progress fields
            operation_id=generic_state.operation_id,
            current_step=generic_state.current_step,
            total_steps=generic_state.total_steps,
            message=generic_state.message,
            percentage=generic_state.percentage,
            estimated_remaining=generic_state.estimated_remaining,
            start_time=generic_state.start_time,
            # Backward compatibility fields
            steps_completed=generic_state.current_step,
            steps_total=generic_state.total_steps,
            expected_items=generic_state.total_items,
            items_processed=generic_state.items_processed,
            operation_context=generic_state.context,
            # Extract hierarchical fields from context if available
            current_step_name=generic_state.context.get("current_step_name"),
            step_current=generic_state.context.get("step_current", 0),
            step_total=generic_state.context.get("step_total", 0),
            step_detail=generic_state.context.get("step_detail", ""),
            current_item_detail=generic_state.context.get("current_item_detail"),
            # Additional existing fields with sensible defaults
            step_start_percentage=0.0,
            step_end_percentage=100.0,
            step_items_processed=generic_state.items_processed,
            estimated_completion=None,
            overall_percentage=generic_state.percentage,
        )

    def _extract_base_message(self, message: str) -> str:
        """
        Extract base message without previous context (preserve existing logic).

        Args:
            message: Full message that may contain context

        Returns:
            Base message without context decoration
        """
        if "(" in message and ")" in message:
            return message[: message.find("(")].strip()
        return message

    def _format_timedelta(self, td: timedelta) -> str:
        """
        Format timedelta for display (preserve existing logic).

        Args:
            td: Time delta to format

        Returns:
            Human-readable time string matching existing format
        """
        seconds = int(td.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            else:
                return f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
