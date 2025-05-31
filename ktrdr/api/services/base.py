"""
Base service interfaces for the KTRDR API.

This module defines the base service interfaces used to connect the API
with core KTRDR modules.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Generic, TypeVar

# Type variable for generic service responses
T = TypeVar("T")


class BaseService(ABC):
    """
    Base service interface for API services.

    This abstract class provides a template for API service implementations
    with common functionality like logging and performance tracking.
    """

    def __init__(self):
        """Initialize the service with a logger."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def log_operation(self, operation: str, **kwargs) -> None:
        """
        Log a service operation with contextual information.

        Args:
            operation (str): The name of the operation being performed
            **kwargs: Additional context to include in the log
        """
        context = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{operation}: {context}")

    def track_performance(self, operation: str) -> Dict[str, Any]:
        """
        Create a context manager for tracking operation performance.

        Args:
            operation (str): The name of the operation to track

        Returns:
            Dict[str, Any]: A dictionary with performance metrics
        """
        start_time = time.time()

        def end_tracking() -> Dict[str, Any]:
            """End performance tracking and return metrics."""
            duration_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"Performance: {operation} took {duration_ms:.2f}ms")
            return {"operation": operation, "duration_ms": duration_ms}

        return {"start_time": start_time, "end_tracking": end_tracking}

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the service.

        Returns:
            Dict[str, Any]: Health check information
        """
        pass
