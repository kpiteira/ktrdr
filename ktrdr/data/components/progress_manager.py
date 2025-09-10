"""
Legacy progress components - DEPRECATED.

This file now contains only deprecated imports for transition period.
The ProgressManager functionality has been moved to:
- ktrdr.async_infrastructure.progress.GenericProgressManager (generic infrastructure)
- ktrdr.data.async_infrastructure.data_progress_renderer (data-specific rendering)

THIS MODULE WILL BE REMOVED IN A FUTURE VERSION.
Update your imports to use the new async infrastructure.
"""

import warnings
from typing import Any, Callable, Optional

# Deprecated imports for backward compatibility - will be removed in future version
from ktrdr.async_infrastructure.time_estimation import (
    TimeEstimationEngine,  # noqa: F401
)

warnings.warn(
    "ktrdr.data.components.progress_manager is deprecated. "
    "Use ktrdr.async_infrastructure.progress.GenericProgressManager with "
    "ktrdr.data.async_infrastructure.data_progress_renderer.DataProgressRenderer instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)


# TEMPORARY COMPATIBILITY STUBS - REMOVE AFTER OTHER MODULES ARE MIGRATED
class ProgressManager:
    """DEPRECATED: Minimal functional stub to maintain basic progress reporting while modules are migrated."""
    
    def __init__(self, callback_func: Optional[Callable[[Any], None]] = None, **kwargs):
        warnings.warn(
            "ProgressManager is deprecated and will be removed. "
            "Use GenericProgressManager with DataProgressRenderer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.callback = callback_func
        self._current_state = None
    
    def start_operation(self, total_steps: int, operation_name: str, **kwargs):
        """Minimal functional implementation for compatibility."""
        if self.callback:
            from datetime import datetime
            self._current_state = ProgressState(
                operation_id=operation_name,
                current_step=0,
                total_steps=total_steps,
                message=f"Starting {operation_name}",
                percentage=0.0,
                start_time=datetime.now()
            )
            self.callback(self._current_state)
    
    def update_progress(self, step: int, message: str):
        """Minimal functional implementation for compatibility."""
        if self.callback and self._current_state:
            self._current_state.current_step = step
            self._current_state.message = message
            if self._current_state.total_steps > 0:
                self._current_state.percentage = min(100.0, (step / self._current_state.total_steps) * 100.0)
            self.callback(self._current_state)
    
    def complete_operation(self):
        """Minimal functional implementation for compatibility."""
        if self.callback and self._current_state:
            self._current_state.current_step = self._current_state.total_steps
            self._current_state.percentage = 100.0
            self._current_state.message = f"Operation '{self._current_state.operation_id}' completed"
            self.callback(self._current_state)
    
    def check_cancelled(self) -> bool:
        """Minimal stub - no cancellation support."""
        return False
    
    def set_cancellation_token(self, token):
        """Minimal stub - no cancellation support."""
        pass
    
    def get_progress_state(self):
        """Return current state or default."""
        if self._current_state:
            return self._current_state
        return ProgressState(
            operation_id="unknown",
            current_step=0,
            total_steps=1,
            message="No active operation",
            percentage=0.0
        )


class ProgressState:
    """DEPRECATED: Minimal functional stub for compatibility. Use GenericProgressState instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ProgressState is deprecated and will be removed. "
            "Use GenericProgressState instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Functional compatibility - preserve essential fields
        from datetime import datetime, timedelta
        
        self.operation_id = kwargs.get("operation_id", "deprecated")
        self.current_step = kwargs.get("current_step", 0)
        self.total_steps = kwargs.get("total_steps", 1)
        self.message = kwargs.get("message", "Deprecated")
        self.percentage = kwargs.get("percentage", 0.0)
        self.start_time = kwargs.get("start_time", datetime.now())
        self.estimated_remaining = kwargs.get("estimated_remaining", timedelta(0))
        
        # Legacy compatibility fields
        self.steps_completed = self.current_step
        self.steps_total = self.total_steps
        self.items_processed = kwargs.get("items_processed", 0)
        self.expected_items = kwargs.get("expected_items", None)
        self.operation_context = kwargs.get("operation_context", {})
        self.current_item_detail = kwargs.get("current_item_detail", None)
        self.overall_percentage = self.percentage

# Note: ProgressManager and ProgressState classes have been REMOVED.
# Use GenericProgressManager and GenericProgressState instead:
#
# OLD:
# from ktrdr.data.components.progress_manager import ProgressManager, ProgressState
#
# NEW:
# from ktrdr.async_infrastructure.progress import GenericProgressManager, GenericProgressState
# from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
# from ktrdr.async_infrastructure.time_estimation import create_time_estimation_engine
#
# time_engine = create_time_estimation_engine()
# renderer = DataProgressRenderer(time_estimation_engine=time_engine)
# progress_manager = GenericProgressManager(callback=callback, renderer=renderer)
