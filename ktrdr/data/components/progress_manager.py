"""
Legacy progress components - DEPRECATED AND REMOVED.

The ProgressManager and ProgressState functionality has been moved to:
- ktrdr.async_infrastructure.progress.GenericProgressManager (generic infrastructure)
- ktrdr.data.async_infrastructure.data_progress_renderer (data-specific rendering)

THIS MODULE IS NOW EMPTY - ALL COMPONENTS HAVE BEEN MIGRATED.
"""

import warnings

# All imports removed - see migration guide below for updated imports

warnings.warn(
    "ktrdr.data.components.progress_manager is deprecated and empty. "
    "All functionality moved to ktrdr.async_infrastructure.progress.GenericProgressManager with "
    "ktrdr.data.async_infrastructure.data_progress_renderer.DataProgressRenderer. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

# Migration Guide:
#
# OLD:
# from ktrdr.data.components.progress_manager import ProgressManager, ProgressState
#
# NEW:
# from ktrdr.async_infrastructure.progress import GenericProgressManager, GenericProgressState
# from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
# from ktrdr.async_infrastructure.time_estimation import create_time_estimation_engine
#
# # Usage:
# time_engine = create_time_estimation_engine()
# renderer = DataProgressRenderer(time_estimation_engine=time_engine)
# progress_manager = GenericProgressManager(callback=callback, renderer=renderer)
