"""
IB (Interactive Brokers) Module

This module contains all Interactive Brokers specific functionality isolated from
the main data layer. It provides:

- Connection management with dedicated threads and persistent event loops
- Error classification based on official IB documentation
- Rate limiting and pacing enforcement
- Data fetching and symbol validation
- Clean interface for use by other modules

Key Components:
- IbConnection: Connection with dedicated thread and 3-minute idle timeout
- IbConnectionPool: Simple pool managing connections, no client ID registry
- IbErrorClassifier: Accurate error handling based on official IB docs
- IbPaceManager: Rate limiting (50 req/sec, 2 sec between historical calls)
- IbDataFetcher: Data fetching using the connection pool
- IbSymbolValidator: Symbol validation using IB API

This module is designed to be:
1. Completely self-contained
2. Thread-safe for concurrent use
3. Easy to move to separate container in future
4. Testable in isolation

For the data layer, use the IbDataAdapter which bridges this module to the
ExternalDataProvider interface.
"""

# Version info
__version__ = "1.0.0"
__author__ = "KTRDR Team"

# Import main classes for easy access
from .connection import IbConnection
from .data_fetcher import IbDataFetcher
from .error_classifier import IbErrorClassifier, IbErrorType
from .pace_manager import IbPaceManager
from .pool import IbConnectionPool
from .symbol_validator import ContractInfo, IbSymbolValidator, ValidationResult

__all__ = [
    "IbConnection",
    "IbConnectionPool",
    "IbErrorClassifier",
    "IbErrorType",
    "IbPaceManager",
    "IbSymbolValidator",
    "ValidationResult",
    "ContractInfo",
    "IbDataFetcher",
]
