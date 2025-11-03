"""
Data Acquisition Module.

This module provides external data acquisition orchestration,
including gap analysis, segmentation, and provider integration.
"""

from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService
from ktrdr.data.acquisition.external_data_interface import (
    DataProviderConnectionError,
    DataProviderError,
    ExternalDataProvider,
)
from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.gap_classifier import (
    GapClassification,
    GapClassifier,
    GapInfo,
)
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
from ktrdr.data.acquisition.segment_manager import SegmentManager

__all__ = [
    "DataAcquisitionService",
    "ExternalDataProvider",
    "DataProviderError",
    "DataProviderConnectionError",
    "GapAnalyzer",
    "GapClassification",
    "GapClassifier",
    "GapInfo",
    "IbDataProvider",
    "SegmentManager",
]
