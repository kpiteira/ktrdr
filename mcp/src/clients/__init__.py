"""Domain-specific API clients for KTRDR backend"""

# Using relative imports - appropriate for package-internal modules
from .backtesting_client import BacktestingAPIClient
from .base import BaseAPIClient, KTRDRAPIError
from .data_client import DataAPIClient
from .indicators_client import IndicatorsAPIClient
from .operations_client import OperationsAPIClient
from .strategies_client import StrategiesAPIClient
from .system_client import SystemAPIClient
from .training_client import TrainingAPIClient

__all__ = [
    "BaseAPIClient",
    "KTRDRAPIError",
    "BacktestingAPIClient",
    "DataAPIClient",
    "TrainingAPIClient",
    "OperationsAPIClient",
    "SystemAPIClient",
    "IndicatorsAPIClient",
    "StrategiesAPIClient",
]
