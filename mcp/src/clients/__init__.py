"""Domain-specific API clients for KTRDR backend"""

# Using relative imports - appropriate for package-internal modules
from .base import BaseAPIClient, KTRDRAPIError
from .data_client import DataAPIClient
from .operations_client import OperationsAPIClient
from .system_client import SystemAPIClient
from .training_client import TrainingAPIClient

__all__ = [
    "BaseAPIClient",
    "KTRDRAPIError",
    "DataAPIClient",
    "TrainingAPIClient",
    "OperationsAPIClient",
    "SystemAPIClient",
]
