"""
IB Data Adapter

This adapter bridges the data layer to the IB module, implementing the
ExternalDataProvider interface using the new isolated IB components.

The adapter handles:
- Connection management via IbConnectionPool
- Data fetching with proper error handling
- Symbol validation using IB API
- Rate limiting and pacing enforcement
- Error translation from IB-specific to generic data errors
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import pandas as pd

from ktrdr.logging import get_logger
from ktrdr.errors import DataError, ConnectionError as KtrdrConnectionError
from .external_data_interface import (
    ExternalDataProvider,
    DataProviderError,
    DataProviderConnectionError,
    DataProviderRateLimitError,
    DataProviderDataError
)

# Import IB module components  
from ktrdr.ib import IbErrorClassifier, IbErrorType

logger = get_logger(__name__)


class IbDataAdapter(ExternalDataProvider):
    """
    Adapter that implements ExternalDataProvider interface using the IB module.
    
    This adapter provides a clean interface between the data layer and the
    IB-specific implementation, handling connection management, error translation,
    and data formatting.
    """
    
    def __init__(self, host: str = "localhost", port: int = 4002, max_connections: int = 3):
        """
        Initialize IB data adapter.
        
        Args:
            host: IB Gateway/TWS host
            port: IB Gateway/TWS port
            max_connections: Maximum number of IB connections
        """
        self.host = host
        self.port = port
        
        # Use new IB module components for clean separation
        from ktrdr.ib import IbSymbolValidator, IbDataFetcher, ValidationResult
        
        self.symbol_validator = IbSymbolValidator(component_name="data_adapter_validator")
        self.data_fetcher = IbDataFetcher()
        
        # Statistics
        self.requests_made = 0
        self.errors_encountered = 0
        self.last_request_time: Optional[datetime] = None
        
        logger.info(f"IbDataAdapter initialized for {host}:{port}")
    
    async def validate_and_get_metadata(
        self, symbol: str, timeframes: List[str]
    ):
        """
        Validate symbol and get all metadata including head timestamps for timeframes.
        
        This is the fail-fast validation step that should be called before any data operations.
        
        Args:
            symbol: Symbol to validate
            timeframes: List of timeframes to get head timestamps for
            
        Returns:
            ValidationResult with validation status and metadata
            
        Raises:
            DataProviderError: If validation fails
        """
        try:
            # Use IB module for validation
            validation_result = await self.symbol_validator.validate_symbol_with_metadata(
                symbol, timeframes
            )
            
            self._update_stats()
            
            if not validation_result.is_valid:
                # Convert to data provider error for consistent interface
                raise DataProviderDataError(
                    validation_result.error_message or f"Symbol {symbol} not found",
                    provider="IB"
                )
            
            return validation_result
            
        except Exception as e:
            self.errors_encountered += 1
            if isinstance(e, DataProviderError):
                raise
            else:
                self._handle_ib_error(e, "validate_and_get_metadata")
    
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from IB.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            instrument_type: Optional instrument type
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Validate inputs
            self._validate_timeframe(timeframe)
            self._validate_datetime_range(start, end)
            
            # Determine instrument type if not provided
            if instrument_type is None:
                # Simple heuristic: check if it looks like forex
                if "." in symbol or len(symbol.replace(".", "")) == 6:
                    instrument_type = "CASH"
                else:
                    instrument_type = "STK"
            
            # Use IB data fetcher for clean separation
            result = await self.data_fetcher.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                instrument_type=instrument_type
            )
            
            self._update_stats()
            return result
            
        except Exception as e:
            self.errors_encountered += 1
            self._handle_ib_error(e, "fetch_historical_data")
    
    async def validate_symbol(self, symbol: str, instrument_type: Optional[str] = None) -> bool:
        """
        Validate symbol using IB module.
        
        Args:
            symbol: Trading symbol to validate
            instrument_type: Optional instrument type
            
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            # Use IB module for validation
            result = await self.symbol_validator.validate_symbol_async(symbol)
            
            self._update_stats()
            return result
            
        except Exception as e:
            self.errors_encountered += 1
            logger.warning(f"Symbol validation failed for {symbol}: {e}")
            return False
    
    async def get_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        instrument_type: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Get earliest available data timestamp for symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            instrument_type: Optional instrument type
            
        Returns:
            Earliest available datetime, or None if not available
        """
        try:
            # Use IB module for head timestamp lookup
            head_timestamp_iso = await self.symbol_validator.fetch_head_timestamp_async(
                symbol, timeframe
            )
            
            if head_timestamp_iso:
                # Convert ISO string back to datetime
                dt = datetime.fromisoformat(head_timestamp_iso.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                self._update_stats()
                return dt
            
            return None
            
        except Exception as e:
            self.errors_encountered += 1
            logger.warning(f"Head timestamp lookup failed for {symbol}: {e}")
            return None
    
    
    async def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str,
        instrument_type: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Get latest available data timestamp.
        
        For IB, this is typically the current time during market hours,
        or the last close time outside market hours.
        """
        # For now, return current UTC time
        # In a more sophisticated implementation, we would check market hours
        return datetime.now(timezone.utc)
    
    async def get_supported_timeframes(self) -> List[str]:
        """Get list of supported timeframes for IB"""
        return ["1m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "1d", "1w", "1M"]
    
    async def get_supported_instruments(self) -> List[str]:
        """Get list of supported instrument types for IB"""
        return ["STK", "FOREX", "CRYPTO", "FUTURE", "OPTION", "INDEX"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of IB components"""
        try:
            # Get health from data fetcher and symbol validator
            data_fetcher_stats = self.data_fetcher.get_stats()
            validator_stats = self.symbol_validator.get_cache_stats()
            
            # Check if we can connect (basic health check)
            from ktrdr.ib.pool_manager import get_shared_ib_pool
            pool = get_shared_ib_pool()
            pool_health = await pool.health_check()
            
            return {
                "healthy": pool_health["healthy"],
                "connected": pool_health["healthy_connections"] > 0,
                "last_request_time": self.last_request_time,
                "error_count": self.errors_encountered,
                "rate_limit_status": {},
                "provider_info": {
                    "data_fetcher_stats": data_fetcher_stats,
                    "validator_stats": validator_stats,
                    "pool_stats": pool_health,
                    "requests_made": self.requests_made
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "last_request_time": self.last_request_time,
                "error_count": self.errors_encountered + 1,
                "rate_limit_status": {},
                "provider_info": {"error": str(e)}
            }
    
    async def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the IB data provider"""
        return {
            "name": "Interactive Brokers",
            "version": "1.0.0",
            "capabilities": [
                "historical_data",
                "symbol_validation", 
                "head_timestamp",
                "real_time_data",
                "multiple_instruments"
            ],
            "rate_limits": {
                "general_requests_per_second": 50,
                "historical_requests_interval_seconds": 2,
                "historical_requests_per_10_minutes": 60
            },
            "data_coverage": {
                "instruments": await self.get_supported_instruments(),
                "timeframes": await self.get_supported_timeframes(),
                "markets": ["US", "Europe", "Asia", "Forex", "Crypto"]
            }
        }
    
    def _validate_timeframe(self, timeframe: str):
        """Validate timeframe format"""
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "1d", "1w", "1M"]
        if timeframe not in valid_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
    
    def _validate_datetime_range(self, start: datetime, end: datetime):
        """Validate datetime range"""
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Datetime objects must be timezone-aware")
        
        if start >= end:
            raise ValueError("Start datetime must be before end datetime")
    
    
    def _update_stats(self):
        """Update adapter statistics"""
        self.requests_made += 1
        self.last_request_time = datetime.now(timezone.utc)
    
    def _handle_ib_error(self, error: Exception, operation: str):
        """Handle and translate IB errors to appropriate data provider errors"""
        error_message = str(error)
        
        # Try to extract error code if available
        error_code = 0
        if hasattr(error, 'code'):
            error_code = error.code
        
        # Classify the error
        error_type, wait_time = IbErrorClassifier.classify(error_code, error_message)
        
        logger.error(f"IB error in {operation}: {error_message} (type={error_type.value})")
        
        # Translate to appropriate data provider error
        if error_type == IbErrorType.PACING_VIOLATION:
            raise DataProviderRateLimitError(
                f"IB rate limit exceeded: {error_message}",
                provider="IB",
                retry_after=wait_time
            )
        elif error_type == IbErrorType.CONNECTION_ERROR:
            raise DataProviderConnectionError(
                f"IB connection error: {error_message}",
                provider="IB",
                error_code=str(error_code)
            )
        elif error_type == IbErrorType.DATA_UNAVAILABLE:
            raise DataProviderDataError(
                f"IB data unavailable: {error_message}",
                provider="IB",
                error_code=str(error_code)
            )
        elif error_type == IbErrorType.FATAL:
            raise DataProviderError(
                f"IB fatal error: {error_message}",
                provider="IB",
                error_code=str(error_code)
            )
        else:
            # Default to generic data error
            raise DataProviderError(
                f"IB error: {error_message}",
                provider="IB",
                error_code=str(error_code)
            )