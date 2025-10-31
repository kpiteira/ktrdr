"""
DataHealthChecker - Health check functionality for DataManager components.

This module provides comprehensive health check capabilities for DataManager
components, extracted to keep DataManager lean and maintain separation of concerns.
"""

import os
from typing import TYPE_CHECKING, Any, Optional

from ktrdr.data.acquisition.gap_classifier import GapClassifier
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.repository.data_quality_validator import DataQualityValidator

if TYPE_CHECKING:
    from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class DataHealthChecker:
    """
    Health check component for DataManager and its dependencies.

    This class provides comprehensive health checking capabilities for all
    data-related components, keeping the DataManager lean by extracting
    this functionality into a dedicated component.
    """

    def __init__(
        self,
        data_loader: LocalDataLoader,
        data_validator: DataQualityValidator,
        gap_classifier: GapClassifier,
        ib_adapter: Optional["IbDataAdapter"] = None,
        enable_ib: bool = True,
        max_gap_percentage: float = 5.0,
        default_repair_method: str = "ffill",
        repair_methods: Optional[dict] = None,
    ):
        """
        Initialize health checker with component references.

        Args:
            data_loader: LocalDataLoader instance
            data_validator: DataQualityValidator instance
            gap_classifier: GapClassifier instance
            ib_adapter: Optional IbDataAdapter instance
            enable_ib: Whether IB integration is enabled
            max_gap_percentage: Max gap percentage configuration
            default_repair_method: Default repair method configuration
            repair_methods: Available repair methods mapping
        """
        self.data_loader = data_loader
        self.data_validator = data_validator
        self.gap_classifier = gap_classifier
        self.ib_adapter = ib_adapter
        self.enable_ib = enable_ib
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method
        self.repair_methods = repair_methods or {}

    async def check_data_loader_health(self) -> dict[str, Any]:
        """Check health of the local data loader."""
        try:
            # Check if data directory exists and is accessible
            data_dir = getattr(self.data_loader, "data_dir", None)
            if data_dir and os.path.exists(data_dir):
                # Check read permissions
                if os.access(data_dir, os.R_OK):
                    return {
                        "status": "healthy",
                        "type": type(self.data_loader).__name__,
                        "data_directory": data_dir,
                        "directory_accessible": True,
                    }
                else:
                    return {
                        "status": "warning",
                        "type": type(self.data_loader).__name__,
                        "data_directory": data_dir,
                        "directory_accessible": False,
                        "issue": "Directory exists but not readable",
                    }
            else:
                return {
                    "status": "warning",
                    "type": type(self.data_loader).__name__,
                    "data_directory": data_dir,
                    "directory_accessible": False,
                    "issue": "Data directory does not exist",
                }
        except Exception as e:
            return {
                "status": "error",
                "type": type(self.data_loader).__name__,
                "error": str(e),
            }

    async def check_data_validator_health(self) -> dict[str, Any]:
        """Check health of the data validator."""
        try:
            # Basic validation that the validator can be instantiated and configured
            if self.data_validator:
                return {
                    "status": "healthy",
                    "type": type(self.data_validator).__name__,
                    "auto_correct": getattr(
                        self.data_validator, "auto_correct", "unknown"
                    ),
                    "max_gap_percentage": getattr(
                        self.data_validator, "max_gap_percentage", "unknown"
                    ),
                }
            else:
                return {
                    "status": "error",
                    "issue": "Data validator not initialized",
                }
        except Exception as e:
            return {
                "status": "error",
                "type": (
                    type(self.data_validator).__name__
                    if self.data_validator
                    else "Unknown"
                ),
                "error": str(e),
            }

    async def check_gap_classifier_health(self) -> dict[str, Any]:
        """Check health of the gap classifier."""
        try:
            if self.gap_classifier:
                return {
                    "status": "healthy",
                    "type": type(self.gap_classifier).__name__,
                }
            else:
                return {
                    "status": "error",
                    "issue": "Gap classifier not initialized",
                }
        except Exception as e:
            return {
                "status": "error",
                "type": (
                    type(self.gap_classifier).__name__
                    if self.gap_classifier
                    else "Unknown"
                ),
                "error": str(e),
            }

    async def check_data_directory_access(self) -> dict[str, Any]:
        """Custom health check for data directory access."""
        try:
            data_dir = getattr(self.data_loader, "data_dir", None)
            if not data_dir:
                return {"status": "warning", "message": "No data directory configured"}

            if not os.path.exists(data_dir):
                return {
                    "status": "error",
                    "message": f"Data directory does not exist: {data_dir}",
                }

            if not os.access(data_dir, os.R_OK):
                return {
                    "status": "error",
                    "message": f"Data directory not readable: {data_dir}",
                }

            # Check for some sample data files
            sample_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")][:5]

            return {
                "status": "healthy",
                "message": f"Data directory accessible: {data_dir}",
                "sample_files_count": len(sample_files),
                "sample_files": sample_files,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def check_local_data_availability(self) -> dict[str, Any]:
        """Custom health check for local data availability."""
        try:
            data_dir = getattr(self.data_loader, "data_dir", None)
            if not data_dir or not os.path.exists(data_dir):
                return {"status": "warning", "message": "No data directory available"}

            # Count available data files
            csv_files = []
            for _root, _dirs, files in os.walk(data_dir):
                csv_files.extend([f for f in files if f.endswith(".csv")])

            if len(csv_files) == 0:
                return {"status": "warning", "message": "No CSV data files found"}

            return {
                "status": "healthy",
                "message": f"Local data available: {len(csv_files)} files",
                "total_files": len(csv_files),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def check_ib_connection(self) -> dict[str, Any]:
        """Custom health check for IB connection."""
        try:
            if not self.enable_ib:
                return {"status": "info", "message": "IB integration disabled"}

            if not self.ib_adapter:
                return {"status": "warning", "message": "IB adapter not initialized"}

            # Don't call adapter health check again - it's already called by ServiceOrchestrator
            # Instead, just report the adapter status
            return {
                "status": "healthy",
                "message": "IB adapter initialized and ready",
                "adapter_type": type(self.ib_adapter).__name__,
                "use_host_service": getattr(self.ib_adapter, "use_host_service", False),
                "host_service_url": getattr(self.ib_adapter, "host_service_url", None),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def perform_comprehensive_health_check(self) -> dict[str, Any]:
        """
        Perform all health checks and return comprehensive results.

        Returns:
            Dictionary with all health check results
        """
        results = {}

        # Component health checks
        results["data_loader"] = await self.check_data_loader_health()
        results["data_validator"] = await self.check_data_validator_health()
        results["gap_classifier"] = await self.check_gap_classifier_health()

        # Custom checks
        custom_checks = {
            "data_directory_access": await self.check_data_directory_access(),
            "local_data_availability": await self.check_local_data_availability(),
            "ib_connection": await self.check_ib_connection(),
        }
        results["custom_checks"] = custom_checks

        # Configuration information
        data_config = {
            "max_gap_percentage": self.max_gap_percentage,
            "default_repair_method": self.default_repair_method,
            "enable_ib": self.enable_ib,
            "valid_repair_methods": list(self.repair_methods.keys()),
        }
        results["data_configuration"] = data_config
        # Backward compatibility
        results["configuration"] = data_config

        return results
