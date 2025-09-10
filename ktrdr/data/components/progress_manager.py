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
