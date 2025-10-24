"""
Operations Service for Training Host Service

This module provides access to the OperationsService from ktrdr.api.services.
The same OperationsService code runs in both the backend and host services,
enabling unified operations tracking and pull-based progress updates.

Task 2.1 (M2): Deploy OperationsService singleton in training host service
"""

from typing import Optional

from ktrdr.api.services.operations_service import OperationsService
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Global operations service instance (singleton)
_operations_service: Optional[OperationsService] = None


def get_operations_service() -> OperationsService:
    """
    Get or create the global operations service instance.

    Returns the singleton instance of OperationsService, creating it if needed.
    This follows the same pattern as get_training_service() in this host service.

    Returns:
        OperationsService: Singleton instance for managing operations
    """
    global _operations_service
    if _operations_service is None:
        _operations_service = OperationsService()
        logger.info("Operations service initialized in training host service")
    return _operations_service


# Re-export OperationsService for convenience
__all__ = ["OperationsService", "get_operations_service"]
