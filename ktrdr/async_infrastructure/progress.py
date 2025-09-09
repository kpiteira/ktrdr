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

    def update_progress(
        self,
        step: int,
        message: Optional[str] = None,
        items_processed: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Update progress - generic interface.

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
            )
            self.callback(state_copy)
        except Exception as e:
            # Same error handling as existing ProgressManager
            logger.warning(f"Progress callback failed: {e}")
