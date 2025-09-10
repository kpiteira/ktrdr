"""
Generic progress infrastructure for KTRDR async operations.

This module provides domain-agnostic progress tracking that integrates with
the existing ServiceOrchestrator architecture while preserving all the rich
features from the existing ProgressManager implementation.

Key components:
- GenericProgressState: Domain-agnostic progress state data structure
- ProgressRenderer: Abstract base for domain-specific progress rendering
- GenericProgressManager: Thread-safe progress manager with TimeEstimationEngine integration
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class GenericProgressState:
    """
    Generic progress state - domain-agnostic core.

    This data structure contains all the essential progress information
    that any domain might need, while allowing domain-specific context
    through the context dictionary.
    """

    # Core progress fields - required for all operations
    operation_id: str
    current_step: int
    total_steps: int
    percentage: float
    message: str

    # Timing information
    start_time: datetime = field(default_factory=datetime.now)

    # Generic context - domain defines content
    context: dict[str, Any] = field(default_factory=dict)

    # Time estimation fields
    estimated_remaining: Optional[timedelta] = None

    # Generic item tracking - can be bars, data points, files, etc.
    items_processed: int = 0
    total_items: Optional[int] = None

    # Step percentage ranges for hierarchical progress (preserve ProgressManager functionality)
    step_start_percentage: float = 0.0
    step_end_percentage: float = 0.0

    # Current step progress tracking
    step_current: int = 0
    step_total: int = 0


class ProgressRenderer(ABC):
    """
    Abstract progress renderer for domain-specific display.

    This abstract base class defines the contract for domain-specific
    progress rendering while allowing each domain to customize the
    presentation and enhancement of progress information.
    """

    @abstractmethod
    def render_message(self, state: GenericProgressState) -> str:
        """
        Render progress message for this domain.

        Args:
            state: The current progress state

        Returns:
            Formatted message string appropriate for this domain
        """
        pass

    @abstractmethod
    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """
        Enhance state with domain-specific information.

        This method allows domains to add their own calculations,
        time estimates, or contextual information to the progress state.

        Args:
            state: The generic progress state to enhance

        Returns:
            Enhanced progress state with domain-specific information
        """
        pass


class GenericProgressManager:
    """
    Domain-agnostic progress manager extracted from existing ProgressManager.

    This class provides thread-safe progress tracking with all the sophisticated
    features from the existing ProgressManager, but in a domain-agnostic way.
    Domain-specific behavior is handled through the ProgressRenderer pattern.

    Key features preserved from existing ProgressManager:
    - Thread-safe operations with RLock
    - Rich progress state tracking
    - Callback-based progress reporting
    - Integration with TimeEstimationEngine
    - Hierarchical progress support
    - Context-aware messaging
    """

    def __init__(
        self,
        callback: Optional[Callable[[GenericProgressState], None]] = None,
        renderer: Optional[ProgressRenderer] = None,
    ):
        """
        Initialize GenericProgressManager with optional callback and renderer.

        Args:
            callback: Optional callback function to receive progress updates.
                     Receives GenericProgressState instances.
            renderer: Optional ProgressRenderer for domain-specific enhancements.
        """
        self.callback = callback
        self.renderer = renderer
        self._state: Optional[GenericProgressState] = None
        self._lock = (
            threading.RLock()
        )  # Same as existing ProgressManager for thread safety

        logger.debug(
            "GenericProgressManager initialized with callback: %s, renderer: %s",
            callback is not None,
            renderer is not None,
        )

    def start_operation(
        self,
        operation_id: str,
        total_steps: int,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Start tracking operation - generic interface.

        Args:
            operation_id: Unique identifier for the operation
            total_steps: Total number of steps in the operation
            context: Optional context dictionary for domain-specific information
        """
        with self._lock:
            self._state = GenericProgressState(
                operation_id=operation_id,
                current_step=0,
                total_steps=total_steps,
                percentage=0.0,
                message=f"Starting {operation_id}",
                context=context or {},
            )

            # Use renderer if available to enhance state and message
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)

            logger.debug(
                "Started operation '%s' with %d steps and context: %s",
                operation_id,
                total_steps,
                context,
            )

            self._trigger_callback()

    def start_step(
        self,
        step_name: str,
        step_number: int,
        step_percentage: Optional[float] = None,
        step_end_percentage: Optional[float] = None,
        expected_items: Optional[int] = None,
    ) -> None:
        """
        Start a new step with percentage range support (preserve ProgressManager functionality).

        This method supports the hierarchical progress that data loading orchestrator uses,
        where steps have custom percentage ranges like Step 6: 10% → 96%.

        Args:
            step_name: Name of the step being started
            step_number: Step number (1-based)
            step_percentage: Custom start percentage for this step (e.g., 10.0 for segment fetching)
            step_end_percentage: Custom end percentage for this step (e.g., 96.0 for segment fetching)
            expected_items: Expected number of items to process in this step
        """
        with self._lock:
            if not self._state:
                logger.warning("start_step called without active operation")
                return

            self._state.current_step = step_number
            self._state.step_current = 0
            self._state.step_total = 0

            # Update expected items for this step
            if expected_items is not None:
                self._state.total_items = expected_items

            # Set step percentage ranges (CRITICAL for proper progress calculation)
            if step_percentage is not None:
                # Use custom percentage ranges (like data loading orchestrator does)
                self._state.percentage = step_percentage
                self._state.step_start_percentage = step_percentage

                if step_end_percentage is not None:
                    self._state.step_end_percentage = step_end_percentage
                else:
                    # Default: assume equal step increments if no end specified
                    default_increment = (
                        100.0 / self._state.total_steps
                        if self._state.total_steps > 0
                        else 10.0
                    )
                    self._state.step_end_percentage = (
                        step_percentage + default_increment
                    )
            else:
                # Use default equal increment calculation
                if self._state.total_steps > 0:
                    start_pct = (step_number - 1) / self._state.total_steps * 100.0
                    end_pct = step_number / self._state.total_steps * 100.0

                    self._state.percentage = start_pct
                    self._state.step_start_percentage = start_pct
                    self._state.step_end_percentage = end_pct

            # Update context with step info
            self._state.context.update(
                {
                    "current_step_name": step_name,
                    "step_start_percentage": self._state.step_start_percentage,
                    "step_end_percentage": self._state.step_end_percentage,
                }
            )

            # Use renderer for enhanced message
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)
            else:
                self._state.message = f"Starting {step_name}"

            logger.debug(
                "Started step %d (%s): %.1f%% → %.1f%%",
                step_number,
                step_name,
                self._state.step_start_percentage,
                self._state.step_end_percentage,
            )

            self._trigger_callback()

    def update_step_progress(
        self, current: int, total: int, items_processed: int = 0, detail: str = ""
    ) -> None:
        """
        Update progress within the current step using percentage ranges.

        This is the key method that calculates progress within step percentage ranges,
        enabling smooth progress from 10% → 96% during segment fetching.

        Args:
            current: Current progress within the step (e.g., segment 15 of 50)
            total: Total items in the step (e.g., 50 segments)
            items_processed: Number of items processed (bars, data points, etc.)
            detail: Additional detail message (e.g., "✅ Loaded 1500 bars")
        """
        with self._lock:
            if not self._state:
                logger.warning("update_step_progress called without active operation")
                return

            self._state.step_current = current
            self._state.step_total = total
            self._state.items_processed = items_processed

            # Calculate percentage within the step's range (CRITICAL for smooth progress)
            step_start = self._state.step_start_percentage
            step_end = self._state.step_end_percentage
            step_range = step_end - step_start

            if total > 0:
                # Calculate progress within the step's percentage range
                sub_progress_ratio = current / total
                sub_progress_percentage = sub_progress_ratio * step_range
                self._state.percentage = step_start + sub_progress_percentage
            else:
                # No sub-progress, stay at step start
                self._state.percentage = step_start

            # Update context with step progress details
            self._state.context.update(
                {
                    "step_current": current,
                    "step_total": total,
                    "step_detail": detail,
                    "step_progress_ratio": current / total if total > 0 else 0.0,
                }
            )

            # Use renderer for enhanced message
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)

            self._trigger_callback()

    def update_progress(
        self,
        step: int,
        message: Optional[str] = None,
        items_processed: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Update progress - generic interface (now preserves step ranges).

        Args:
            step: Current step number
            message: Optional progress message (overridden by renderer if present)
            items_processed: Number of items processed (bars, files, etc.)
            context: Optional additional context for this update
        """
        with self._lock:
            if not self._state:
                logger.warning("update_progress called without active operation")
                return

            # Update core progress fields
            self._state.current_step = step

            # Only update percentage if no step ranges are defined
            # (preserve hierarchical progress when step ranges are active)
            if (
                self._state.step_start_percentage == 0.0
                and self._state.step_end_percentage == 0.0
            ):
                self._state.percentage = (
                    min(100.0, (step / self._state.total_steps) * 100.0)
                    if self._state.total_steps > 0
                    else 100.0
                )

            self._state.items_processed = items_processed

            # Update context
            if context:
                self._state.context.update(context)

            # Use renderer for message if available, otherwise use provided message
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)
            elif message:
                self._state.message = message

            self._trigger_callback()

    def complete_operation(self) -> None:
        """Mark operation complete."""
        with self._lock:
            if not self._state:
                logger.warning("complete_operation called without active operation")
                return

            self._state.current_step = self._state.total_steps
            self._state.percentage = 100.0

            if self.renderer:
                # Let renderer create completion message
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)
            else:
                self._state.message = f"Operation {self._state.operation_id} completed"

            logger.info(
                "Operation '%s' completed successfully", self._state.operation_id
            )
            self._trigger_callback()

    def _trigger_callback(self) -> None:
        """
        Trigger progress callback - preserve existing pattern.

        Handles callback failures gracefully with logging, same as existing ProgressManager.
        """
        if self.callback is None or self._state is None:
            return

        try:
            # Pass a copy of the state to avoid external mutation
            state_copy = GenericProgressState(
                operation_id=self._state.operation_id,
                current_step=self._state.current_step,
                total_steps=self._state.total_steps,
                percentage=self._state.percentage,
                message=self._state.message,
                start_time=self._state.start_time,
                context=self._state.context.copy(),
                estimated_remaining=self._state.estimated_remaining,
                items_processed=self._state.items_processed,
                total_items=self._state.total_items,
                # Include new hierarchical progress fields
                step_start_percentage=self._state.step_start_percentage,
                step_end_percentage=self._state.step_end_percentage,
                step_current=self._state.step_current,
                step_total=self._state.step_total,
            )
            self.callback(state_copy)
        except Exception as e:
            # Same error handling as existing ProgressManager
            logger.warning(f"Progress callback failed: {e}")
