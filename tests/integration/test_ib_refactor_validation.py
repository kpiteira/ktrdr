"""
Integration validation tests for IB refactoring completion.

These tests validate that the refactored IB system works correctly end-to-end
without complex mocking, focusing on real integration scenarios.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, timezone

from ktrdr.data.data_manager import DataManager
from ktrdr.api.services.data_service import DataService
from ktrdr.api.services.ib_service import IbService
from ktrdr.data.ib_connection_pool import get_connection_pool


class TestIbRefactorValidation:
    """Test the refactored IB system integration."""

    def test_data_manager_initialization(self):
        """Test DataManager initializes with unified IB components."""
        dm = DataManager(enable_ib=True)

        # Verify IB components are initialized
        assert dm.enable_ib is True
        assert dm.ib_data_fetcher is not None
        assert dm.ib_symbol_validator is not None

        # Verify component types
        assert "IbDataFetcherUnified" in str(type(dm.ib_data_fetcher))
        assert "IbSymbolValidatorUnified" in str(type(dm.ib_symbol_validator))

    def test_data_manager_local_mode(self):
        """Test DataManager works in local mode (no IB required)."""
        dm = DataManager(enable_ib=True)

        # This should work even if IB is not connected
        try:
            df = dm.load_data("NONEXISTENT", "1h", mode="local")
            # Should get empty DataFrame or DataNotFoundError
            assert df is None or df.empty
        except Exception as e:
            # DataNotFoundError is expected for non-existent symbols
            assert "Data not found" in str(e) or "DataNotFoundError" in str(type(e))

    def test_data_service_initialization(self):
        """Test DataService initializes correctly."""
        ds = DataService()

        # Verify DataService has DataManager
        assert ds.data_manager is not None
        assert ds.operations_service is not None

        # Verify DataManager has IB components
        assert ds.data_manager.enable_ib is True
        assert ds.data_manager.ib_data_fetcher is not None

    @pytest.mark.asyncio
    async def test_ib_service_initialization(self):
        """Test IbService initializes correctly."""
        ib_service = IbService()

        # Test status method (should work even without IB connection)
        status = await ib_service.get_status()
        assert isinstance(status.ib_available, bool)
        assert hasattr(status, "connection")
        assert hasattr(status, "connection_metrics")
        assert hasattr(status, "data_metrics")

    @pytest.mark.asyncio
    async def test_ib_service_health_check(self):
        """Test IbService health check."""
        ib_service = IbService()

        # Health check should work even without IB connection
        health = await ib_service.get_health()
        assert hasattr(health, "healthy")
        assert isinstance(health.healthy, bool)

    @pytest.mark.asyncio
    async def test_ib_service_config(self):
        """Test IbService configuration."""
        ib_service = IbService()

        # Config should work without IB connection
        config = await ib_service.get_config()
        assert hasattr(config, "host")
        assert hasattr(config, "port")
        assert hasattr(config, "client_id_range")

    @pytest.mark.asyncio
    async def test_connection_pool_singleton(self):
        """Test connection pool singleton pattern."""
        pool1 = await get_connection_pool()
        pool2 = await get_connection_pool()

        # Should be the same instance
        assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_api_data_service_integration(self):
        """Test API DataService integration with local data."""
        ds = DataService()

        # Test with a symbol that might have local data
        try:
            result = await ds.load_data("AAPL", "1h", mode="local")

            # Should have the expected response structure
            assert isinstance(result, dict)
            assert "status" in result
            assert "fetched_bars" in result
            assert "ib_requests_made" in result  # Fixed field name
            assert "execution_time_seconds" in result

            # Should be successful for local mode
            assert result["status"] in [
                "success",
                "failed",
            ]  # Either works or fails gracefully
            assert isinstance(result["fetched_bars"], int)
            assert isinstance(result["ib_requests_made"], int)
            assert (
                result["ib_requests_made"] == 0
            )  # Local mode should not make IB requests

        except Exception as e:
            # If no local data, should fail gracefully
            assert "Data not found" in str(e) or "DataNotFoundError" in str(type(e))

    def test_component_integration_structure(self):
        """Test that all components are properly integrated."""
        # Test DataManager -> IB components
        dm = DataManager(enable_ib=True)
        assert dm.ib_data_fetcher is not None
        assert dm.ib_symbol_validator is not None

        # Test DataService -> DataManager
        ds = DataService()
        assert ds.data_manager is not None
        assert ds.data_manager.ib_data_fetcher is not None

        # Test that components have the expected interfaces
        fetcher = dm.ib_data_fetcher
        validator = dm.ib_symbol_validator

        # Check fetcher interface
        assert hasattr(fetcher, "fetch_historical_data")
        assert hasattr(fetcher, "get_metrics")
        assert hasattr(fetcher, "reset_metrics")

        # Check validator interface
        assert hasattr(validator, "validate_symbol_async")
        assert hasattr(validator, "get_metrics")
        assert hasattr(validator, "get_cache_stats")

    def test_error_handling_graceful_degradation(self):
        """Test that the system degrades gracefully when IB is unavailable."""
        # Test with IB disabled
        dm_no_ib = DataManager(enable_ib=False)
        assert dm_no_ib.ib_data_fetcher is None
        assert dm_no_ib.ib_symbol_validator is None

        # Should still work for local operations
        try:
            df = dm_no_ib.load_data("TEST", "1h", mode="local")
            # Either gets data or fails gracefully
            assert df is None or isinstance(df, pd.DataFrame)
        except Exception as e:
            # Should be a data-related error, not a system error
            assert "Data not found" in str(e) or "DataNotFoundError" in str(type(e))

    @pytest.mark.asyncio
    async def test_metrics_and_monitoring(self):
        """Test that metrics collection works."""
        ib_service = IbService()

        # Get status with metrics
        status = await ib_service.get_status()

        # Verify metrics structure
        assert hasattr(status, "connection_metrics")
        assert hasattr(status, "data_metrics")

        conn_metrics = status.connection_metrics
        data_metrics = status.data_metrics

        # Check connection metrics
        assert hasattr(conn_metrics, "total_connections")
        assert hasattr(conn_metrics, "failed_connections")

        # Check data metrics
        assert hasattr(data_metrics, "total_requests")
        assert hasattr(data_metrics, "successful_requests")
        assert hasattr(data_metrics, "success_rate")


class TestIbRefactorRegressionPrevention:
    """Tests to prevent regressions in the refactored system."""

    def test_api_response_format_consistency(self):
        """Test that API response formats are consistent."""
        # This test ensures the DataService returns the expected format
        ds = DataService()

        # Mock the DataManager to return a successful result
        with patch.object(ds.data_manager, "load_data") as mock_load:
            mock_load.return_value = pd.DataFrame(
                {
                    "open": [100, 101],
                    "high": [102, 103],
                    "low": [99, 100],
                    "close": [101, 102],
                    "volume": [1000, 1100],
                }
            )

            # Test async method
            import asyncio

            async def test_async():
                result = await ds.load_data("TEST", "1h", mode="local")

                # Verify required fields are present
                required_fields = [
                    "status",
                    "fetched_bars",
                    "cached_before",
                    "merged_file",
                    "gaps_analyzed",
                    "segments_fetched",
                    "ib_requests_made",
                    "execution_time_seconds",
                    "error_message",
                ]

                for field in required_fields:
                    assert field in result, f"Missing required field: {field}"

                # Verify field types
                assert isinstance(result["status"], str)
                assert isinstance(result["fetched_bars"], int)
                assert isinstance(result["ib_requests_made"], int)
                assert isinstance(result["execution_time_seconds"], float)

                return result

            result = asyncio.run(test_async())
            assert result["status"] == "success"
            assert result["fetched_bars"] == 2

    @pytest.mark.asyncio
    async def test_ib_service_api_compatibility(self):
        """Test that IbService API is compatible with endpoints."""
        ib_service = IbService()

        # Test all the methods used by API endpoints
        status = await ib_service.get_status()
        health = await ib_service.get_health()
        config = await ib_service.get_config()

        # Verify types match what API expects
        from ktrdr.api.models.ib import IbStatusResponse, IbHealthStatus, IbConfigInfo

        assert isinstance(status, IbStatusResponse)
        assert isinstance(health, IbHealthStatus)
        assert isinstance(config, IbConfigInfo)

    def test_backward_compatibility_imports(self):
        """Test that existing imports still work."""
        # Test key imports that should continue working
        try:
            from ktrdr.data import DataManager
            from ktrdr.data.ib_connection_pool import get_connection_pool
            from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
            from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified

            # Should not raise ImportError
            assert DataManager is not None
            assert get_connection_pool is not None
            assert IbDataFetcherUnified is not None
            assert IbSymbolValidatorUnified is not None

        except ImportError as e:
            pytest.fail(f"Backward compatibility broken: {e}")

    def test_configuration_loading(self):
        """Test that configuration loading works correctly."""
        # Test that components can load configuration
        dm = DataManager(enable_ib=True)

        # Should not raise configuration errors
        assert dm.data_loader is not None

        # Test that IB components initialize with config
        if dm.ib_data_fetcher:
            # Should have default configuration
            assert hasattr(dm.ib_data_fetcher, "component_name")
            assert dm.ib_data_fetcher.component_name == "data_manager"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
