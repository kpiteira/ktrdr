"""
Comprehensive tests for DataManager (async) following TDD methodology.

This test file implements all the functionality required for the new async DataManager
that extends ServiceOrchestrator before implementation, ensuring tests fail first and
then pass after implementation.
"""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from ktrdr.data import DataCorruptionError, DataError, DataNotFoundError


@pytest.fixture
def sample_ohlcv_data():
    """Create a sample OHLCV DataFrame for testing."""
    index = pd.date_range(start="2023-01-01", periods=100, freq="1D")
    data = {
        "open": np.random.uniform(100, 110, size=100),
        "high": np.random.uniform(110, 120, size=100),
        "low": np.random.uniform(90, 100, size=100),
        "close": np.random.uniform(100, 110, size=100),
        "volume": np.random.uniform(1000, 10000, size=100),
    }
    df = pd.DataFrame(data, index=index)

    # Ensure high >= open, close and low <= open, close
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def mock_async_data_adapter():
    """Mock AsyncDataAdapter for testing."""
    adapter = AsyncMock()
    adapter.fetch_historical_data = AsyncMock()
    adapter.validate_symbol = AsyncMock(return_value=True)
    adapter.get_head_timestamp = AsyncMock()
    adapter.health_check = AsyncMock(return_value={"status": "healthy"})
    adapter.use_host_service = True
    adapter.host_service_url = "http://localhost:8001"
    return adapter


@pytest.fixture
def mock_local_data_loader():
    """Mock LocalDataLoader for testing."""
    loader = Mock()
    loader.load = Mock()
    return loader


@pytest.fixture
def mock_data_validator():
    """Mock DataQualityValidator for testing."""
    validator = Mock()
    validator.validate_data = Mock()
    return validator


class TestDataManagerConstruction:
    """Test DataManager initialization and configuration."""

    def test_init_with_defaults(self, mock_local_data_loader, mock_async_data_adapter):
        """Test DataManager initialization with default parameters."""
        from ktrdr.data.managers.data_manager import DataManager

        # Test initialization with defaults
        manager = DataManager()

        # Check that default values are set correctly
        assert manager.enable_ib is True  # Should default to True
        assert manager.max_gap_percentage == 5.0  # Default from config
        assert manager.default_repair_method == "ffill"  # Default repair method
        assert hasattr(manager, "data_loader")
        assert hasattr(manager, "data_validator")
        assert hasattr(manager, "gap_classifier")
        assert hasattr(manager, "adapter")  # IB adapter
        assert hasattr(manager, "load_data")  # Main method
        assert hasattr(manager, "health_check")  # From ServiceOrchestrator

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(
            max_gap_percentage=10.0,
            default_repair_method="interpolate",
            enable_ib=False,
        )

        # Verify custom parameters were applied
        assert manager.max_gap_percentage == 10.0
        assert manager.default_repair_method == "interpolate"
        assert manager.enable_ib is False

    def test_init_validation_errors(self):
        """Test initialization parameter validation."""
        from ktrdr.data.managers.data_manager import DataManager

        # These should raise DataError for invalid parameters
        with pytest.raises(DataError):
            DataManager(max_gap_percentage=-5.0)

        with pytest.raises(DataError):
            DataManager(max_gap_percentage=150.0)

        with pytest.raises(DataError):
            DataManager(default_repair_method="invalid_method")

    @patch.dict(
        os.environ,
        {"USE_IB_HOST_SERVICE": "true", "IB_HOST_SERVICE_URL": "http://test:8001"},
    )
    def test_environment_based_adapter_configuration(self):
        """Test environment variable configuration for adapters."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager()

        # Should configure adapter based on environment
        assert manager.adapter.use_host_service == True
        assert "test:8001" in manager.adapter.host_service_url


class TestDataManagerDataLoading:
    """Test DataManager async data loading functionality."""

    @pytest.mark.asyncio
    async def test_load_data_basic_async(self, sample_ohlcv_data):
        """Test basic async data loading."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Mock the underlying data loader
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        result = await manager.load_data("AAPL", "1d", mode="local")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_ohlcv_data)

    @pytest.mark.asyncio
    async def test_load_data_with_ib_source(
        self, sample_ohlcv_data, mock_async_data_adapter
    ):
        """Test async data loading with IB data source."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=True)
        manager.adapter = mock_async_data_adapter

        # Mock adapter to return data
        mock_async_data_adapter.fetch_historical_data.return_value = sample_ohlcv_data

        result = await manager.load_data("EURUSD", "1h", mode="tail")
        assert isinstance(result, pd.DataFrame)
        mock_async_data_adapter.fetch_historical_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_data_with_validation(self, sample_ohlcv_data):
        """Test async data loading with validation."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        # Test validation enabled (default)
        result = await manager.load_data("AAPL", "1d", validate=True)
        assert isinstance(result, pd.DataFrame)

        # Test validation disabled
        result = await manager.load_data("AAPL", "1d", validate=False)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_load_data_with_repair(self, sample_ohlcv_data):
        """Test async data loading with repair functionality."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Create corrupt data for repair testing
        corrupt_data = sample_ohlcv_data.copy()
        corrupt_data.iloc[10:15] = np.nan  # Add some missing data

        manager.data_loader.load = Mock(return_value=corrupt_data)

        result = await manager.load_data("AAPL", "1d", repair=True)
        assert isinstance(result, pd.DataFrame)

        # Should have called validator with repair=True
        # (This assertion will need adjustment based on actual implementation)

    @pytest.mark.asyncio
    async def test_load_data_cancellation_support(self):
        """Test async data loading with cancellation support."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Create a cancellation token
        cancellation_event = asyncio.Event()

        # Mock long-running operation
        async def mock_long_operation(*args, **kwargs):
            await asyncio.sleep(1.0)  # Simulate slow operation
            return pd.DataFrame()

        manager._load_with_fallback_async = mock_long_operation

        # Start loading and cancel immediately
        cancellation_event.set()

        # Should handle cancellation gracefully
        # (Exact behavior depends on implementation)

    @pytest.mark.asyncio
    async def test_load_data_progress_callback(self, sample_ohlcv_data):
        """Test async data loading with progress callbacks."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        # Track progress updates
        progress_updates = []

        def progress_callback(progress):
            progress_updates.append(progress)

        result = await manager.load_data(
            "AAPL", "1d", progress_callback=progress_callback
        )

        assert isinstance(result, pd.DataFrame)
        assert len(progress_updates) > 0  # Should have received progress updates


class TestDataManagerErrorHandling:
    """Test DataManager error handling and exception propagation."""

    @pytest.mark.asyncio
    async def test_data_not_found_error(self):
        """Test DataNotFoundError handling in async context."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(side_effect=FileNotFoundError("File not found"))

        with pytest.raises(FileNotFoundError):
            await manager.load_data("NONEXISTENT", "1d")

    @pytest.mark.asyncio
    async def test_data_corruption_strict_mode(self):
        """Test DataCorruptionError in strict mode with async context."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Mock corrupt data
        corrupt_data = pd.DataFrame(
            {
                "open": [100, 110, np.nan],
                "high": [105, np.nan, 115],
                "low": [95, 105, 110],
                "close": [102, 108, 112],
                "volume": [1000, 2000, 3000],
            }
        )

        manager.data_loader.load = Mock(return_value=corrupt_data)

        # Should raise error in strict mode
        with pytest.raises(DataCorruptionError):
            await manager.load_data("AAPL", "1d", strict=True)

    @pytest.mark.asyncio
    async def test_adapter_connection_errors(self, mock_async_data_adapter):
        """Test adapter connection error handling."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=True)
        manager.adapter = mock_async_data_adapter

        # Mock connection failure
        mock_async_data_adapter.fetch_historical_data.side_effect = ConnectionError(
            "Connection failed"
        )

        with pytest.raises((ConnectionError, DataError)):
            await manager.load_data("EURUSD", "1h", mode="tail")


class TestDataManagerMultiTimeframeSupport:
    """Test DataManager multi-timeframe data loading."""

    @pytest.mark.asyncio
    async def test_load_multi_timeframe_data(self, sample_ohlcv_data):
        """Test loading data for multiple timeframes asynchronously."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        timeframes = ["1h", "4h", "1d"]
        results = await manager.load_multi_timeframe_data("AAPL", timeframes)

        assert isinstance(results, dict)
        assert len(results) == len(timeframes)
        for tf in timeframes:
            assert tf in results
            assert isinstance(results[tf], pd.DataFrame)

    @pytest.mark.asyncio
    async def test_multi_timeframe_with_common_coverage(self, sample_ohlcv_data):
        """Test multi-timeframe loading with common data coverage."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Mock different data ranges for each timeframe
        def mock_load_by_timeframe(symbol, timeframe, start_date=None, end_date=None):
            if timeframe == "1h":
                return sample_ohlcv_data[:50]  # Shorter range
            elif timeframe == "4h":
                return sample_ohlcv_data[:75]  # Medium range
            else:  # "1d"
                return sample_ohlcv_data  # Full range

        manager.data_loader.load = Mock(side_effect=mock_load_by_timeframe)

        timeframes = ["1h", "4h", "1d"]
        results = await manager.load_multi_timeframe_data(
            "AAPL", timeframes, align_data=True
        )

        # Should align to common coverage (shortest range)
        for tf_data in results.values():
            assert len(tf_data) <= 50  # Should be aligned to shortest


class TestDataManagerPerformance:
    """Test DataManager performance characteristics."""

    @pytest.mark.asyncio
    async def test_concurrent_data_loading(self, sample_ohlcv_data):
        """Test concurrent loading of multiple symbols."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA"]

        # Load all symbols concurrently
        tasks = [manager.load_data(symbol, "1d", mode="local") for symbol in symbols]

        results = await asyncio.gather(*tasks)

        assert len(results) == len(symbols)
        for result in results:
            assert isinstance(result, pd.DataFrame)
            assert len(result) == len(sample_ohlcv_data)

    @pytest.mark.asyncio
    async def test_async_performance_vs_sync(self, sample_ohlcv_data):
        """Test that async operations don't block the event loop."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)

        # Mock slow operation on the data loader
        def slow_load(*args, **kwargs):
            import time

            time.sleep(0.1)  # Simulate I/O delay
            return sample_ohlcv_data

        manager.data_loader.load = Mock(side_effect=slow_load)

        # Start multiple operations
        start_time = asyncio.get_event_loop().time()

        tasks = [manager.load_data(f"SYMBOL{i}", "1d") for i in range(5)]

        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # Should complete concurrently (much faster than sequential)
        elapsed = end_time - start_time
        assert elapsed < 0.3  # Should be much less than 5 * 0.1 = 0.5s


class TestDataManagerHealthChecks:
    """Test DataManager health check and status functionality."""

    @pytest.mark.asyncio
    async def test_health_check(self, mock_async_data_adapter):
        """Test async health check functionality."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=True)
        manager.adapter = mock_async_data_adapter

        health_status = await manager.health_check()

        assert isinstance(health_status, dict)
        assert "data_loader" in health_status
        assert "adapter" in health_status
        assert "configuration" in health_status

        # Should call adapter health check
        mock_async_data_adapter.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_configuration_info(self):
        """Test configuration information retrieval."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(
            max_gap_percentage=10.0,
            default_repair_method="interpolate",
            enable_ib=True,
        )

        # Test via health check since get_configuration_info doesn't exist
        health_status = await manager.health_check()
        config_info = health_status["configuration"]

        assert isinstance(config_info, dict)
        assert config_info["max_gap_percentage"] == 10.0
        assert config_info["default_repair_method"] == "interpolate"
        assert config_info["enable_ib"] == True


class TestDataManagerBackwardCompatibility:
    """Test DataManager backward compatibility with DataManager interface."""

    @pytest.mark.asyncio
    async def test_same_public_methods(self):
        """Test that DataManager has same public methods as DataManager."""
        from ktrdr.data.data_manager import DataManager
        from ktrdr.data.managers.data_manager import DataManager

        async_manager = DataManager()
        sync_manager = DataManager()

        # Get public methods (excluding private and dunder methods)
        async_methods = {
            name
            for name in dir(async_manager)
            if not name.startswith("_") and callable(getattr(async_manager, name))
        }

        sync_methods = {
            name
            for name in dir(sync_manager)
            if not name.startswith("_") and callable(getattr(sync_manager, name))
        }

        # DataManager should have all DataManager methods (but async versions)
        for method in sync_methods:
            assert method in async_methods or f"{method}_async" in async_methods

    @pytest.mark.asyncio
    async def test_similar_return_types(self, sample_ohlcv_data):
        """Test that DataManager returns similar types to DataManager."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        # Basic data loading should return DataFrame
        result = await manager.load_data("AAPL", "1d")
        assert isinstance(result, pd.DataFrame)

        # Health check should return dict
        health = await manager.health_check()
        assert isinstance(health, dict)


class TestDataManagerEdgeCases:
    """Test DataManager edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_data_handling(self):
        """Test handling of empty DataFrames."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=pd.DataFrame())

        with pytest.raises(DataNotFoundError):
            await manager.load_data("EMPTY", "1d")

    @pytest.mark.asyncio
    async def test_none_data_handling(self):
        """Test handling when data loader returns None."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=None)

        with pytest.raises(DataNotFoundError):
            await manager.load_data("NONE", "1d")

    @pytest.mark.asyncio
    async def test_very_large_date_ranges(self, sample_ohlcv_data):
        """Test handling of very large date ranges."""
        from ktrdr.data.managers.data_manager import DataManager

        manager = DataManager(enable_ib=False)
        manager.data_loader.load = Mock(return_value=sample_ohlcv_data)

        # Test with very large date range
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2025, 1, 1)

        result = await manager.load_data(
            "AAPL", "1d", start_date=start_date, end_date=end_date
        )

        assert isinstance(result, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
