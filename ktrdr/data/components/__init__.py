"""Data components module."""

from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.gap_classifier import GapClassifier
from ktrdr.data.acquisition.segment_manager import SegmentManager
from ktrdr.data.repository.data_quality_validator import DataQualityValidator

from .data_health_checker import DataHealthChecker
from .timeframe_synchronizer import TimeframeSynchronizer

# ProgressManager and ProgressState have been migrated to:
# - ktrdr.async_infrastructure.progress.GenericProgressManager
# - ktrdr.async_infrastructure.progress.GenericProgressState

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
