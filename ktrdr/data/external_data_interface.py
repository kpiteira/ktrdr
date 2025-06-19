"""
External Data Provider Interface

This module defines the abstract interface for external data providers.
It allows the data layer to work with different data sources (IB, Alpha Vantage, etc.)
without knowing the specific implementation details.

The interface provides a clean separation between the data management layer
and the specific external data source implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class ExternalDataProvider(ABC):
    """
    Abstract interface for external data providers.
    
    This interface defines the contract that all external data providers
    must implement. It includes methods for:
    - Historical data fetching
    - Symbol validation
    - Data availability checking
    - Connection health monitoring
    
    Implementations should handle their own connection management,
    error handling, and rate limiting.
    """
    
    @abstractmethod
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EUR.USD')
            timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            instrument_type: Optional instrument type ('STK', 'FOREX', etc.)
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
            Index should be timezone-aware datetime
            
        Raises:
            DataError: If data cannot be fetched
            ConnectionError: If connection to provider fails
            ValueError: If parameters are invalid
        """
        pass
    
    @abstractmethod
    async def validate_symbol(self, symbol: str, instrument_type: Optional[str] = None) -> bool:
        """
        Check if a symbol is valid and available from the provider.
        
        Args:
            symbol: Trading symbol to validate
            instrument_type: Optional instrument type for validation
            
        Returns:
            True if symbol is valid and available, False otherwise
            
        Raises:
            ConnectionError: If connection to provider fails
        """
        pass
    
    @abstractmethod
    async def get_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        instrument_type: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Get the earliest available data timestamp for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            instrument_type: Optional instrument type
            
        Returns:
            Earliest available datetime (timezone-aware), or None if not available
            
        Raises:
            ConnectionError: If connection to provider fails
            ValueError: If parameters are invalid
        """
        pass
    
    @abstractmethod
    async def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str,
        instrument_type: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Get the latest available data timestamp for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            instrument_type: Optional instrument type
            
        Returns:
            Latest available datetime (timezone-aware), or None if not available
            
        Raises:
            ConnectionError: If connection to provider fails
            ValueError: If parameters are invalid
        """
        pass
    
    @abstractmethod
    async def get_supported_timeframes(self) -> List[str]:
        """
        Get list of supported timeframes.
        
        Returns:
            List of supported timeframe strings (e.g., ['1m', '5m', '1h', '1d'])
        """
        pass
    
    @abstractmethod
    async def get_supported_instruments(self) -> List[str]:
        """
        Get list of supported instrument types.
        
        Returns:
            List of supported instrument types (e.g., ['STK', 'FOREX', 'CRYPTO'])
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health and status of the data provider.
        
        Returns:
            Dictionary with health information:
            {
                "healthy": bool,
                "connected": bool,
                "last_request_time": datetime,
                "error_count": int,
                "rate_limit_status": dict,
                "provider_info": dict
            }
        """
        pass
    
    @abstractmethod
    async def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the data provider.
        
        Returns:
            Dictionary with provider information:
            {
                "name": str,
                "version": str,
                "capabilities": list,
                "rate_limits": dict,
                "data_coverage": dict
            }
        """
        pass
    
    # Optional methods that providers can override for enhanced functionality
    
    async def get_market_hours(
        self,
        symbol: str,
        date: datetime,
        instrument_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get market hours for a symbol on a specific date.
        
        Args:
            symbol: Trading symbol
            date: Date to check market hours for
            instrument_type: Optional instrument type
            
        Returns:
            Dictionary with market hours info, or None if not supported:
            {
                "market_open": datetime,
                "market_close": datetime,
                "is_trading_day": bool,
                "timezone": str
            }
        """
        logger.debug(f"Market hours not implemented for provider {self.__class__.__name__}")
        return None
    
    async def get_contract_details(
        self,
        symbol: str,
        instrument_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed contract information for a symbol.
        
        Args:
            symbol: Trading symbol
            instrument_type: Optional instrument type
            
        Returns:
            Dictionary with contract details, or None if not supported:
            {
                "symbol": str,
                "exchange": str,
                "currency": str,
                "instrument_type": str,
                "tick_size": float,
                "multiplier": int,
                "description": str
            }
        """
        logger.debug(f"Contract details not implemented for provider {self.__class__.__name__}")
        return None
    
    async def search_symbols(
        self,
        query: str,
        instrument_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for symbols matching a query.
        
        Args:
            query: Search query string
            instrument_type: Optional instrument type filter
            limit: Maximum number of results
            
        Returns:
            List of symbol information dictionaries:
            [{
                "symbol": str,
                "description": str,
                "exchange": str,
                "instrument_type": str
            }]
        """
        logger.debug(f"Symbol search not implemented for provider {self.__class__.__name__}")
        return []


class DataProviderError(Exception):
    """Base exception for data provider errors"""
    
    def __init__(self, message: str, provider: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code


class DataProviderConnectionError(DataProviderError):
    """Exception for data provider connection errors"""
    pass


class DataProviderRateLimitError(DataProviderError):
    """Exception for data provider rate limit errors"""
    
    def __init__(self, message: str, provider: str, retry_after: Optional[float] = None):
        super().__init__(message, provider)
        self.retry_after = retry_after


class DataProviderDataError(DataProviderError):
    """Exception for data availability or quality errors"""
    pass


class DataProviderConfigError(DataProviderError):
    """Exception for data provider configuration errors"""
    pass