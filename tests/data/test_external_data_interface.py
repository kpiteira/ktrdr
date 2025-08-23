"""
Unit tests for External Data Provider Interface

Tests the abstract interface for external data providers.
"""

from abc import ABC
from datetime import datetime, timezone

import pandas as pd
import pytest

from ktrdr.data.external_data_interface import (
    DataProviderConfigError,
    DataProviderConnectionError,
    DataProviderDataError,
    DataProviderError,
    DataProviderRateLimitError,
    ExternalDataProvider,
)


class MockExternalDataProvider(ExternalDataProvider):
    """Mock implementation for testing."""

    def __init__(self):
        self.fetch_calls = []
        self.validate_calls = []
        self.head_timestamp_calls = []

    async def fetch_historical_data(
        self, symbol, timeframe, start, end, instrument_type=None
    ):
        self.fetch_calls.append((symbol, timeframe, start, end, instrument_type))

        # Return mock data
        dates = pd.date_range(start=start, end=end, freq="1h")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000] * len(dates),
            },
            index=dates,
        )

    async def validate_symbol(self, symbol, instrument_type=None):
        self.validate_calls.append((symbol, instrument_type))
        return symbol != "INVALID"

    async def get_head_timestamp(self, symbol, timeframe, instrument_type=None):
        self.head_timestamp_calls.append((symbol, timeframe, instrument_type))
        return datetime(2020, 1, 1, tzinfo=timezone.utc)

    async def get_latest_timestamp(self, symbol, timeframe, instrument_type=None):
        return datetime.now(timezone.utc)

    async def get_supported_timeframes(self):
        return ["1m", "5m", "1h", "1d"]

    async def get_supported_instruments(self):
        return ["STK", "FOREX"]

    async def health_check(self):
        return {
            "healthy": True,
            "connected": True,
            "last_request_time": datetime.now(timezone.utc),
            "error_count": 0,
            "rate_limit_status": {},
            "provider_info": {"name": "Mock Provider"},
        }

    async def get_provider_info(self):
        return {
            "name": "Mock Provider",
            "version": "1.0.0",
            "capabilities": ["historical_data", "symbol_validation"],
            "rate_limits": {},
            "data_coverage": {},
        }


class TestExternalDataInterface:
    """Test external data provider interface."""

    def test_interface_is_abstract(self):
        """Test that ExternalDataProvider is abstract."""
        assert issubclass(ExternalDataProvider, ABC)

        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            ExternalDataProvider()

    @pytest.mark.asyncio
    async def test_mock_implementation(self):
        """Test mock implementation works correctly."""
        provider = MockExternalDataProvider()

        # Test fetch_historical_data
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 2, tzinfo=timezone.utc)

        data = await provider.fetch_historical_data("AAPL", "1h", start, end, "STK")

        assert isinstance(data, pd.DataFrame)
        assert "open" in data.columns
        assert "high" in data.columns
        assert "low" in data.columns
        assert "close" in data.columns
        assert "volume" in data.columns
        assert len(provider.fetch_calls) == 1
        assert provider.fetch_calls[0] == ("AAPL", "1h", start, end, "STK")

    @pytest.mark.asyncio
    async def test_symbol_validation(self):
        """Test symbol validation."""
        provider = MockExternalDataProvider()

        # Valid symbol
        is_valid = await provider.validate_symbol("AAPL", "STK")
        assert is_valid is True

        # Invalid symbol
        is_valid = await provider.validate_symbol("INVALID", "STK")
        assert is_valid is False

        assert len(provider.validate_calls) == 2

    @pytest.mark.asyncio
    async def test_head_timestamp(self):
        """Test head timestamp retrieval."""
        provider = MockExternalDataProvider()

        timestamp = await provider.get_head_timestamp("AAPL", "1h", "STK")

        assert isinstance(timestamp, datetime)
        assert timestamp.tzinfo == timezone.utc
        assert len(provider.head_timestamp_calls) == 1

    @pytest.mark.asyncio
    async def test_latest_timestamp(self):
        """Test latest timestamp retrieval."""
        provider = MockExternalDataProvider()

        timestamp = await provider.get_latest_timestamp("AAPL", "1h", "STK")

        assert isinstance(timestamp, datetime)
        assert timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_supported_timeframes(self):
        """Test supported timeframes."""
        provider = MockExternalDataProvider()

        timeframes = await provider.get_supported_timeframes()

        assert isinstance(timeframes, list)
        assert "1h" in timeframes
        assert "1d" in timeframes

    @pytest.mark.asyncio
    async def test_supported_instruments(self):
        """Test supported instruments."""
        provider = MockExternalDataProvider()

        instruments = await provider.get_supported_instruments()

        assert isinstance(instruments, list)
        assert "STK" in instruments
        assert "FOREX" in instruments

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        provider = MockExternalDataProvider()

        health = await provider.health_check()

        assert isinstance(health, dict)
        assert "healthy" in health
        assert "connected" in health
        assert health["healthy"] is True
        assert health["connected"] is True

    @pytest.mark.asyncio
    async def test_provider_info(self):
        """Test provider info."""
        provider = MockExternalDataProvider()

        info = await provider.get_provider_info()

        assert isinstance(info, dict)
        assert "name" in info
        assert "version" in info
        assert "capabilities" in info
        assert info["name"] == "Mock Provider"

    @pytest.mark.asyncio
    async def test_optional_methods_default_behavior(self):
        """Test optional methods have default implementations."""
        provider = MockExternalDataProvider()

        # These should not raise NotImplementedError
        market_hours = await provider.get_market_hours(
            "AAPL", datetime.now(timezone.utc)
        )
        assert market_hours is None

        contract_details = await provider.get_contract_details("AAPL")
        assert contract_details is None

        search_results = await provider.search_symbols("AAPL")
        assert search_results == []


class TestDataProviderExceptions:
    """Test data provider exception classes."""

    def test_base_exception(self):
        """Test base DataProviderError."""
        error = DataProviderError("Test message", "TestProvider", "ERR001")

        assert str(error) == "Test message"
        assert error.provider == "TestProvider"
        assert error.error_code == "ERR001"

    def test_connection_error(self):
        """Test DataProviderConnectionError."""
        error = DataProviderConnectionError(
            "Connection failed", "TestProvider", "CONN001"
        )

        assert isinstance(error, DataProviderError)
        assert error.provider == "TestProvider"
        assert error.error_code == "CONN001"

    def test_rate_limit_error(self):
        """Test DataProviderRateLimitError."""
        error = DataProviderRateLimitError(
            "Rate limit exceeded", "TestProvider", retry_after=60.0
        )

        assert isinstance(error, DataProviderError)
        assert error.provider == "TestProvider"
        assert error.retry_after == 60.0

    def test_data_error(self):
        """Test DataProviderDataError."""
        error = DataProviderDataError("Data not available", "TestProvider", "DATA001")

        assert isinstance(error, DataProviderError)
        assert error.provider == "TestProvider"
        assert error.error_code == "DATA001"

    def test_config_error(self):
        """Test DataProviderConfigError."""
        error = DataProviderConfigError(
            "Invalid configuration", "TestProvider", "CONFIG001"
        )

        assert isinstance(error, DataProviderError)
        assert error.provider == "TestProvider"
        assert error.error_code == "CONFIG001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
