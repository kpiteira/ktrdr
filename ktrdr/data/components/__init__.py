"""Data components module."""

from ktrdr.data.repository.data_quality_validator import DataQualityValidator

from .data_health_checker import DataHealthChecker
from .gap_analyzer import GapAnalyzer
from .gap_classifier import GapClassifier

# ProgressManager and ProgressState have been migrated to:
# - ktrdr.async_infrastructure.progress.GenericProgressManager
# - ktrdr.async_infrastructure.progress.GenericProgressState
from .segment_manager import SegmentManager
from .timeframe_synchronizer import TimeframeSynchronizer

__all__ = [
    "DataHealthChecker",
    "DataQualityValidator",
    "GapAnalyzer",
    "GapClassifier",
    # "ProgressManager",  # MIGRATED to GenericProgressManager
    # "ProgressState",    # MIGRATED to GenericProgressState
    "SegmentManager",
    "TimeframeSynchronizer",
]
