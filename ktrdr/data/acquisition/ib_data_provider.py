"""
IB Data Provider (HTTP-Only)

This provider implements the ExternalDataProvider interface for IB data,
communicating exclusively via the IB host service HTTP API.

The provider handles:
- HTTP communication with IB host service
- Data fetching with proper error handling
- Symbol validation using IB host service
- Error translation from host service to generic data errors

IMPORTANT: This provider NEVER imports from ktrdr.ib.
It only communicates with IB via HTTP through the host service.
"""

from datetime import datetime, timezone
from io import StringIO
from typing import Any, Optional

import pandas as pd

from ktrdr.async_infrastructure.service_adapter import (
    AsyncServiceAdapter,
    HostServiceConfig,
)
from ktrdr.data.acquisition.external_data_interface import (
    DataProviderConnectionError,
    DataProviderDataError,
    DataProviderError,
    ExternalDataProvider,
)
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IbDataProvider(ExternalDataProvider, AsyncServiceAdapter):
    """
    IB data provider that communicates exclusively via HTTP host service.

    This provider implements the ExternalDataProvider interface using only
    HTTP calls to the IB host service. It never imports from ktrdr.ib or
    connects directly to IB Gateway.

    All IB-specific logic (connection management, rate limiting, etc.) is
    handled by the host service.
    """

    def __init__(
        self,
        host_service_url: Optional[str] = None,
    ):
        """
        Initialize IB data provider (HTTP-only).

        Args:
            host_service_url: URL of the IB host service (e.g., http://localhost:5001)
                             Defaults to http://localhost:5001
        """
        self.host_service_url = host_service_url or "http://localhost:5001"
        # Always True for HTTP-only provider (required for DataManager context manager check)
        self.use_host_service = True

        # Initialize AsyncServiceAdapter for HTTP communication
        config = HostServiceConfig(
            base_url=self.host_service_url,
            connection_pool_limit=10,  # IB-specific: 10 connections for data operations
        )
        AsyncServiceAdapter.__init__(self, config)

        logger.info(
            f"IbDataProvider initialized for host service at {self.host_service_url}"
        )

        # Statistics
        self.requests_made = 0
        self.errors_encountered = 0
        self.last_request_time: Optional[datetime] = None

    # AsyncServiceAdapter abstract method implementations
    def get_service_name(self) -> str:
        """Return service identifier for logging and metrics."""
        return "IB Data Service"

    def get_service_type(self) -> str:
        """Return service type identifier for categorization."""
        return "ib_data"

    def get_base_url(self) -> str:
        """Return service base URL from configuration."""
        return self.host_service_url

    async def get_health_check_endpoint(self) -> str:
        """Return endpoint for health checking."""
        return "/health"

    async def _ensure_client_initialized(self) -> None:
        """Ensure HTTP client is initialized (for long-lived adapter pattern)."""
        if self._http_client is None:
            await self._setup_connection_pool()

    async def _call_host_service_post(
        self, endpoint: str, data: dict[str, Any], cancellation_token=None
    ) -> dict[str, Any]:
        """Make POST request to host service using AsyncServiceAdapter."""
        # Ensure HTTP client is initialized
        await self._ensure_client_initialized()

        try:
            return await AsyncServiceAdapter._call_host_service_post(
                self, endpoint, data, cancellation_token
            )
        except Exception as e:
            # Translate AsyncServiceAdapter errors to DataProvider errors for compatibility
            self._translate_host_service_error(e)
            # This line should never be reached since _translate_host_service_error always raises
            raise  # pragma: no cover

    async def _call_host_service_get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        cancellation_token=None,
    ) -> dict[str, Any]:
        """Make GET request to host service using AsyncServiceAdapter."""
        # Ensure HTTP client is initialized
        await self._ensure_client_initialized()

        try:
            return await AsyncServiceAdapter._call_host_service_get(
                self, endpoint, params, cancellation_token
            )
        except Exception as e:
            # Translate AsyncServiceAdapter errors to DataProvider errors for compatibility
            self._translate_host_service_error(e)
            # This line should never be reached since _translate_host_service_error always raises
            raise  # pragma: no cover

    def _translate_host_service_error(self, error: Exception) -> None:
        """Translate AsyncServiceAdapter errors to DataProvider errors for compatibility."""
        from ktrdr.async_infrastructure.service_adapter import (
            HostServiceConnectionError,
            HostServiceError,
            HostServiceTimeoutError,
        )

        if isinstance(error, HostServiceConnectionError):
            raise DataProviderConnectionError(
                f"Host service connection failed: {error.message}", provider="IB"
            ) from error
        elif isinstance(error, HostServiceTimeoutError):
            raise DataProviderConnectionError(
                f"Host service timeout: {error.message}", provider="IB"
            ) from error
        elif isinstance(error, HostServiceError):
            raise DataProviderError(
                f"Host service error: {error.message}", provider="IB"
            ) from error
        else:
            raise DataProviderError(
                f"Host service communication error: {str(error)}", provider="IB"
            ) from error

    async def validate_and_get_metadata(self, symbol: str, timeframes: list[str]):
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
            # Use host service for validation
            response = await self._call_host_service_post(
                "/data/validate", {"symbol": symbol, "timeframes": timeframes}
            )

            if not response["success"]:
                raise DataProviderDataError(
                    response.get("error", f"Symbol validation failed for {symbol}"),
                    provider="IB",
                )

            # Use ValidationResult from symbol_cache (has all required fields)
            from ktrdr.data.components.symbol_cache import ValidationResult

            # Pass contract_info as dict - ValidationResult expects dict[str, Any] | None
            # (The old ktrdr.ib.ContractInfo had all IB fields, but we deleted ktrdr.ib.
            #  The backend ValidationResult.contract_info is just a dict, so pass it through.)
            contract_info = response.get("contract_info")

            # Convert ISO timestamps back to datetime objects
            head_timestamps = {}
            if response.get("head_timestamps"):
                for tf, timestamp_str in response["head_timestamps"].items():
                    if timestamp_str:
                        head_timestamps[tf] = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    else:
                        head_timestamps[tf] = None  # type: ignore[assignment]

            # Convert head_timestamps to the expected format (dict[str, str])
            head_timestamps_str = {}
            if head_timestamps:
                for tf, dt in head_timestamps.items():
                    if dt is not None:
                        head_timestamps_str[str(tf)] = dt.isoformat()

            validation_result = ValidationResult(
                is_valid=response.get("is_valid", False),
                symbol=symbol,
                error_message=response.get("error_message"),
                contract_info=contract_info,
                head_timestamps=(head_timestamps_str if head_timestamps_str else None),
                suggested_symbol=response.get("suggested_symbol"),  # Required field
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
                # For unexpected errors, wrap in DataProviderError
                raise DataProviderError(
                    f"Validation error: {str(e)}", provider="IB"
                ) from e

    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from IB via host service.

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
                result = pd.read_json(StringIO(response["data"]), orient="index")
                # Ensure datetime index
                if not result.empty:
                    result.index = pd.to_datetime(result.index)
            else:
                result = pd.DataFrame()

            self._update_stats()
            return result

        except Exception as e:
            self.errors_encountered += 1
            if isinstance(e, (DataProviderError, ValueError)):
                raise
            else:
                raise DataProviderError(f"Fetch error: {str(e)}", provider="IB") from e

    async def validate_symbol(
        self, symbol: str, instrument_type: Optional[str] = None
    ) -> bool:
        """
        Validate symbol using IB host service.

        Args:
            symbol: Trading symbol to validate
            instrument_type: Optional instrument type

        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            # Use host service for validation
            response = await self._call_host_service_post(
                "/data/validate",
                {
                    "symbol": symbol,
                    "timeframes": [],  # Simple validation doesn't need timeframes
                },
            )

            result = response["success"] and response.get("is_valid", False)

            self._update_stats()
            return result

        except Exception as e:
            self.errors_encountered += 1
            logger.warning(f"Symbol validation failed for {symbol}: {e}")
            return False

    async def get_symbol_info(self, symbol: str):
        """
        Get comprehensive symbol information from host service.

        This restores the same symbol validation and caching functionality
        for intelligent segment planning.

        Args:
            symbol: Trading symbol

        Returns:
            ValidationResult with full symbol metadata
        """
        try:
            # Use host service for symbol info
            response = await self._call_host_service_get(f"/data/symbol-info/{symbol}")

            if not response["success"]:
                raise DataProviderDataError(
                    response.get("error", f"Symbol info lookup failed for {symbol}"),
                    provider="IB",
                )

            # Use ValidationResult from symbol_cache (has all required fields)
            from ktrdr.data.components.symbol_cache import ValidationResult

            # Pass contract_info as dict - ValidationResult expects dict[str, Any] | None
            contract_info = response.get("contract_info")

            # Convert ISO timestamps back to datetime objects
            head_timestamps = {}
            if response.get("head_timestamps"):
                for tf, timestamp_str in response["head_timestamps"].items():
                    if timestamp_str:
                        head_timestamps[tf] = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    else:
                        head_timestamps[tf] = None  # type: ignore[assignment]

            # Convert head_timestamps to the expected format (dict[str, str])
            head_timestamps_str = {}
            if head_timestamps:
                for tf, dt in head_timestamps.items():
                    if dt is not None:
                        head_timestamps_str[str(tf)] = dt.isoformat()

            validation_result = ValidationResult(
                is_valid=response.get("is_valid", False),
                symbol=symbol,
                error_message=response.get("error_message"),
                contract_info=contract_info,
                head_timestamps=(head_timestamps_str if head_timestamps_str else None),
                suggested_symbol=response.get("suggested_symbol"),  # Required field
            )

            self._update_stats()
            return validation_result

        except Exception as e:
            self.errors_encountered += 1
            if isinstance(e, DataProviderError):
                raise
            else:
                raise DataProviderError(
                    f"Symbol info error: {str(e)}", provider="IB"
                ) from e

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

    async def get_supported_timeframes(self) -> list[str]:
        """Get list of supported timeframes for IB"""
        return ["1m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "1d", "1w", "1M"]

    async def get_supported_instruments(self) -> list[str]:
        """Get list of supported instrument types for IB"""
        return ["STK", "FOREX", "CRYPTO", "FUTURE", "OPTION", "INDEX"]

    async def health_check(self) -> dict[str, Any]:
        """Check health of IB host service"""
        try:
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

    async def get_provider_info(self) -> dict[str, Any]:
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
