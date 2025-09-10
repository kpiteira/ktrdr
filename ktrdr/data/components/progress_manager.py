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
    """DEPRECATED: Temporary stub to prevent import errors. Use GenericProgressManager instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ProgressManager is deprecated and will be removed. "
            "Use GenericProgressManager with DataProgressRenderer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Minimal stub - methods will raise NotImplementedError if called
    
    def __getattr__(self, name):
        raise NotImplementedError(
            f"ProgressManager.{name}() is deprecated and removed. "
            "Use GenericProgressManager with DataProgressRenderer instead. "
            "See migration guide in this module."
        )


class ProgressState:
    """DEPRECATED: Temporary stub to prevent import errors. Use GenericProgressState instead."""
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ProgressState is deprecated and will be removed. "
            "Use GenericProgressState instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Minimal stub - prevent crashes during imports
        self.operation_id = kwargs.get("operation_id", "deprecated")
        self.current_step = kwargs.get("current_step", 0)
        self.total_steps = kwargs.get("total_steps", 1)
        self.message = kwargs.get("message", "Deprecated")
        self.percentage = kwargs.get("percentage", 0.0)

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
