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
import json

from ktrdr.logging import get_logger
from ktrdr.errors import DataError, ConnectionError as KtrdrConnectionError
from .external_data_interface import (
    ExternalDataProvider,
    DataProviderError,
    DataProviderConnectionError,
    DataProviderRateLimitError,
    DataProviderDataError,
)

# Import IB module components
from ktrdr.ib import IbErrorClassifier, IbErrorType

# HTTP client for host service communication
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = get_logger(__name__)


class IbDataAdapter(ExternalDataProvider):
    """
    Adapter that implements ExternalDataProvider interface using the IB module.

    This adapter provides a clean interface between the data layer and the
    IB-specific implementation, handling connection management, error translation,
    and data formatting.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4002,
        max_connections: int = 3,
        use_host_service: bool = False,
        host_service_url: Optional[str] = None,
    ):
        """
        Initialize IB data adapter.

        Args:
            host: IB Gateway/TWS host (used for direct connection)
            port: IB Gateway/TWS port (used for direct connection)
            max_connections: Maximum number of IB connections (direct mode only)
            use_host_service: Whether to use host service instead of direct IB connection
            host_service_url: URL of the IB host service (e.g., http://localhost:5001)
        """
        self.host = host
        self.port = port
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url or "http://localhost:5001"

        # Validate configuration
        if use_host_service and not HTTPX_AVAILABLE:
            raise DataProviderError(
                "httpx library required for host service mode but not available",
                provider="IB",
            )

        # Initialize appropriate components based on mode
        if not use_host_service:
            # Direct IB connection mode (existing behavior)
            from ktrdr.ib import IbSymbolValidator, IbDataFetcher, ValidationResult

            self.symbol_validator = IbSymbolValidator(
                component_name="data_adapter_validator"
            )
            self.data_fetcher = IbDataFetcher()
            logger.info(
                f"IbDataAdapter initialized for direct IB connection {host}:{port}"
            )
        else:
            # Host service mode
            self.symbol_validator = None
            self.data_fetcher = None
            logger.info(
                f"IbDataAdapter initialized for host service at {self.host_service_url}"
            )

        # Statistics
        self.requests_made = 0
        self.errors_encountered = 0
        self.last_request_time: Optional[datetime] = None

    async def _call_host_service_post(
        self, endpoint: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make POST request to host service."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        url = f"{self.host_service_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise DataProviderConnectionError(
                f"Host service request failed: {str(e)}", provider="IB"
            )
        except Exception as e:
            raise DataProviderError(
                f"Host service communication error: {str(e)}", provider="IB"
            )

    async def _call_host_service_get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make GET request to host service."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        url = f"{self.host_service_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params or {})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise DataProviderConnectionError(
                f"Host service request failed: {str(e)}", provider="IB"
            )
        except Exception as e:
            raise DataProviderError(
                f"Host service communication error: {str(e)}", provider="IB"
            )

    async def validate_and_get_metadata(self, symbol: str, timeframes: List[str]):
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
            if self.use_host_service:
                # Use host service for validation
                response = await self._call_host_service_post(
                    "/data/validate", {"symbol": symbol, "timeframes": timeframes}
                )

                if not response["success"]:
                    raise DataProviderDataError(
                        response.get("error", f"Validation failed for {symbol}"),
                        provider="IB",
                    )

                # Convert response to ValidationResult-like structure
                from ktrdr.ib import ValidationResult, ContractInfo

                contract_info = None
                if response.get("contract_info"):
                    # Create ContractInfo from response data
                    contract_info = ContractInfo(**response["contract_info"])

                # Convert ISO timestamps back to datetime objects
                head_timestamps = {}
                if response.get("head_timestamps"):
                    for tf, timestamp_str in response["head_timestamps"].items():
                        if timestamp_str:
                            head_timestamps[tf] = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        else:
                            head_timestamps[tf] = None

                validation_result = ValidationResult(
                    is_valid=response.get("is_valid", False),
                    symbol=symbol,
                    error_message=response.get("error_message"),
                    contract_info=contract_info,
                    head_timestamps=head_timestamps,
                )
            else:
                # Use direct IB connection (existing behavior)
                validation_result = (
                    await self.symbol_validator.validate_symbol_with_metadata(
                        symbol, timeframes
                    )
                )

            self._update_stats()

            if not validation_result.is_valid:
                # Convert to data provider error for consistent interface
                raise DataProviderDataError(
                    validation_result.error_message or f"Symbol {symbol} not found",
                    provider="IB",
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
        instrument_type: Optional[str] = None,
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

            # Let host service determine instrument type via IB validation
            # No backend heuristics - IB is the authoritative source

            if self.use_host_service:
                # Use host service for data fetching
                response = await self._call_host_service_post(
                    "/data/historical",
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "instrument_type": instrument_type,
                    },
                )

                if not response["success"]:
                    raise DataProviderDataError(
                        response.get("error", f"Data fetch failed for {symbol}"),
                        provider="IB",
                    )

                # Convert JSON response back to DataFrame
                if response.get("data"):
                    result = pd.read_json(response["data"], orient="index")
                    # Ensure datetime index
                    if not result.empty:
                        result.index = pd.to_datetime(result.index)
                else:
                    result = pd.DataFrame()
            else:
                # Use direct IB connection (existing behavior)
                result = await self.data_fetcher.fetch_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    instrument_type=instrument_type,
                )

            self._update_stats()
            return result

        except Exception as e:
            self.errors_encountered += 1
            self._handle_ib_error(e, "fetch_historical_data")

    async def validate_symbol(
        self, symbol: str, instrument_type: Optional[str] = None
    ) -> bool:
        """
        Validate symbol using IB module or host service.

        Args:
            symbol: Trading symbol to validate
            instrument_type: Optional instrument type

        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            if self.use_host_service:
                # Use host service for validation
                response = await self._call_host_service_post(
                    "/data/validate",
                    {
                        "symbol": symbol,
                        "timeframes": [],  # Simple validation doesn't need timeframes
                    },
                )

                result = response["success"] and response.get("is_valid", False)
            else:
                # Use direct IB connection (existing behavior)
                result = await self.symbol_validator.validate_symbol_async(symbol)

            self._update_stats()
            return result

        except Exception as e:
            self.errors_encountered += 1
            logger.warning(f"Symbol validation failed for {symbol}: {e}")
            return False

    async def get_symbol_info(self, symbol: str):
        """
        Get comprehensive symbol information from host service or direct IB.

        This restores the same symbol validation and caching functionality
        the Data Manager used to have for intelligent segment planning.

        Args:
            symbol: Trading symbol

        Returns:
            ValidationResult with full symbol metadata
        """
        try:
            if self.use_host_service:
                # Use host service for symbol info
                response = await self._call_host_service_get(
                    f"/data/symbol-info/{symbol}"
                )

                if not response["success"]:
                    raise DataProviderDataError(
                        response.get(
                            "error", f"Symbol info lookup failed for {symbol}"
                        ),
                        provider="IB",
                    )

                # Convert response to ValidationResult-like structure
                from ktrdr.ib import ValidationResult, ContractInfo

                contract_info = None
                if response.get("contract_info"):
                    contract_info = ContractInfo(**response["contract_info"])

                # Convert ISO timestamps back to datetime objects
                head_timestamps = {}
                if response.get("head_timestamps"):
                    for tf, timestamp_str in response["head_timestamps"].items():
                        if timestamp_str:
                            head_timestamps[tf] = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        else:
                            head_timestamps[tf] = None

                validation_result = ValidationResult(
                    is_valid=response.get("is_valid", False),
                    symbol=symbol,
                    error_message=response.get("error_message"),
                    contract_info=contract_info,
                    head_timestamps=head_timestamps,
                )
            else:
                # Use direct IB connection (existing behavior)
                validation_result = (
                    await self.symbol_validator.validate_symbol_with_metadata(
                        symbol, []
                    )
                )

            self._update_stats()
            return validation_result

        except Exception as e:
            self.errors_encountered += 1
            if isinstance(e, DataProviderError):
                raise
            else:
                self._handle_ib_error(e, "get_symbol_info")

    async def get_head_timestamp(
        self, symbol: str, timeframe: str, instrument_type: Optional[str] = None
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
            if self.use_host_service:
                # Use host service for head timestamp lookup
                response = await self._call_host_service_get(
                    "/data/head-timestamp",
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "instrument_type": instrument_type,
                    },
                )

                if response["success"] and response.get("timestamp"):
                    dt = datetime.fromisoformat(
                        response["timestamp"].replace("Z", "+00:00")
                    )
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    self._update_stats()
                    return dt

                return None
            else:
                # Use direct IB connection (existing behavior)
                head_timestamp_iso = (
                    await self.symbol_validator.fetch_head_timestamp_async(
                        symbol, timeframe
                    )
                )

                if head_timestamp_iso:
                    # Convert ISO string back to datetime
                    dt = datetime.fromisoformat(
                        head_timestamp_iso.replace("Z", "+00:00")
                    )
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
        self, symbol: str, timeframe: str, instrument_type: Optional[str] = None
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
        """Check health of IB components or host service"""
        try:
            if self.use_host_service:
                # Check host service health
                response = await self._call_host_service_get("/health")

                # Convert host service response to expected format
                return {
                    "healthy": response.get("healthy", False),
                    "connected": response.get("ib_status", {}).get("connected", False),
                    "last_request_time": self.last_request_time,
                    "error_count": self.errors_encountered,
                    "rate_limit_status": {},
                    "provider_info": {
                        "mode": "host_service",
                        "host_service_url": self.host_service_url,
                        "host_service_status": response,
                        "requests_made": self.requests_made,
                    },
                }
            else:
                # Direct IB connection health check (existing behavior)
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
                        "mode": "direct_connection",
                        "data_fetcher_stats": data_fetcher_stats,
                        "validator_stats": validator_stats,
                        "pool_stats": pool_health,
                        "requests_made": self.requests_made,
                    },
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "last_request_time": self.last_request_time,
                "error_count": self.errors_encountered + 1,
                "rate_limit_status": {},
                "provider_info": {"error": str(e)},
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
                "multiple_instruments",
            ],
            "rate_limits": {
                "general_requests_per_second": 50,
                "historical_requests_interval_seconds": 2,
                "historical_requests_per_10_minutes": 60,
            },
            "data_coverage": {
                "instruments": await self.get_supported_instruments(),
                "timeframes": await self.get_supported_timeframes(),
                "markets": ["US", "Europe", "Asia", "Forex", "Crypto"],
            },
        }

    def _validate_timeframe(self, timeframe: str):
        """Validate timeframe format"""
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "3h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]
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
        if hasattr(error, "code"):
            error_code = error.code

        # Classify the error
        error_type, wait_time = IbErrorClassifier.classify(error_code, error_message)

        logger.error(
            f"IB error in {operation}: {error_message} (type={error_type.value})"
        )

        # Translate to appropriate data provider error
        if error_type == IbErrorType.PACING_VIOLATION:
            raise DataProviderRateLimitError(
                f"IB rate limit exceeded: {error_message}",
                provider="IB",
                retry_after=wait_time,
            )
        elif error_type == IbErrorType.CONNECTION_ERROR:
            raise DataProviderConnectionError(
                f"IB connection error: {error_message}",
                provider="IB",
                error_code=str(error_code),
            )
        elif error_type == IbErrorType.DATA_UNAVAILABLE:
            raise DataProviderDataError(
                f"IB data unavailable: {error_message}",
                provider="IB",
                error_code=str(error_code),
            )
        elif error_type == IbErrorType.FATAL:
            raise DataProviderError(
                f"IB fatal error: {error_message}",
                provider="IB",
                error_code=str(error_code),
            )
        else:
            # Default to generic data error
            raise DataProviderError(
                f"IB error: {error_message}", provider="IB", error_code=str(error_code)
            )
