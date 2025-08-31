"""
Integration validation tests for IB refactoring completion.

These tests validate that the refactored IB system works correctly end-to-end
without complex mocking, focusing on real integration scenarios.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from ktrdr.api.services.data_service import DataService
from ktrdr.api.services.ib_service import IbService
from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_data_adapter import IbDataAdapter


@pytest.fixture(scope="class")
def shared_data_manager():
    """Shared DataManager instance to avoid repeated initialization."""
    return DataManager()  # IB integration is always enabled now


@pytest.fixture(scope="class")
def shared_data_service():
    """Shared DataService instance to avoid repeated initialization."""
    return DataService()


@pytest.fixture(scope="class")
def shared_ib_service():
    """Shared IbService instance to avoid repeated initialization."""
    return IbService()


# Mark slow integration tests so they can be optionally skipped
pytestmark = pytest.mark.integration_slow


class TestIbRefactorValidation:
    """Test the refactored IB system integration."""

    def test_data_manager_initialization(self, shared_data_manager):
        """Test DataManager initializes with new IB adapter."""
        dm = shared_data_manager

        # Verify external provider is initialized (IB always enabled now)
        assert dm.external_provider is not None
        assert isinstance(dm.external_provider, IbDataAdapter)

        # Verify adapter type
        assert "IbDataAdapter" in str(type(dm.external_provider))

    def test_data_manager_local_mode(self, shared_data_manager):
        """Test DataManager works in local mode (no IB required)."""
        dm = shared_data_manager

        # This should work even if IB is not connected
        try:
            df = dm.load_data("NONEXISTENT", "1h", mode="local")
            # Should get empty DataFrame or DataNotFoundError
            assert df is None or df.empty
        except Exception as e:
            # DataNotFoundError is expected for non-existent symbols
            assert "Data not found" in str(e) or "DataNotFoundError" in str(type(e))

    def test_data_service_initialization(self, shared_data_service):
        """Test DataService initializes correctly."""
        ds = shared_data_service

        # Verify DataService has DataManager
        assert ds.data_manager is not None
        assert ds.operations_service is not None

        # Verify DataManager has IB components (IB always enabled now)
        assert ds.data_manager.external_provider is not None

    @pytest.mark.asyncio
    async def test_ib_service_initialization(self, shared_ib_service):
        """Test IbService initializes correctly."""
        ib_service = shared_ib_service

        # Test status method (should work even without IB connection)
        status = await ib_service.get_status()
        assert isinstance(status.ib_available, bool)
        assert hasattr(status, "connection")
        assert hasattr(status, "connection_metrics")
        assert hasattr(status, "data_metrics")

    @pytest.mark.asyncio
    async def test_ib_service_health_check(self, shared_ib_service):
        """Test IbService health check."""
        ib_service = shared_ib_service

        # Health check should work even without IB connection
        health = await ib_service.get_health()
        assert hasattr(health, "healthy")
        assert isinstance(health.healthy, bool)

    @pytest.mark.asyncio
    async def test_ib_service_config(self, shared_ib_service):
        """Test IbService configuration."""
        ib_service = shared_ib_service

        # Config should work without IB connection
        config = await ib_service.get_config()
        assert hasattr(config, "host")
        assert hasattr(config, "port")
        assert hasattr(config, "client_id_range")

    @pytest.mark.asyncio
    async def test_connection_pool_singleton(self):
        """Test connection pool singleton pattern."""
        from ktrdr.ib.pool_manager import get_shared_ib_pool

        pool1 = get_shared_ib_pool()
        pool2 = get_shared_ib_pool()

        # Should be the same instance
        assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_api_data_service_integration(self, shared_data_service):
        """Test API DataService integration with local data."""
        ds = shared_data_service

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

    def test_component_integration_structure(
        self, shared_data_manager, shared_data_service
    ):
        """Test that all components are properly integrated."""
        # Test DataManager -> IB components
        dm = shared_data_manager
        assert dm.external_provider is not None
        assert hasattr(dm.external_provider, "symbol_validator")
        assert hasattr(dm.external_provider, "data_fetcher")

        # Test DataService -> DataManager
        ds = shared_data_service
        assert ds.data_manager is not None
        assert ds.data_manager.external_provider is not None

        # Test that components have the expected interfaces
        adapter = dm.external_provider

        # Check adapter interface (implements ExternalDataProvider)
        assert hasattr(adapter, "fetch_historical_data")
        assert hasattr(adapter, "validate_and_get_metadata")
        assert hasattr(adapter, "health_check")

        # Check internal components
        assert hasattr(adapter, "symbol_validator")
        assert hasattr(adapter, "data_fetcher")

    def test_error_handling_graceful_degradation(self):
        """Test that the system works with IB host service configuration."""
        # Test with default configuration - this is lightweight and doesn't need IB setup
        dm = DataManager()
        assert dm.external_provider is not None

        # Should still work for local operations
        try:
            df = dm.load_data("TEST", "1h", mode="local")
            # Either gets data or fails gracefully
            assert df is None or isinstance(df, pd.DataFrame)
        except Exception as e:
            # Should be a data-related error, not a system error
            assert "Data not found" in str(e) or "DataNotFoundError" in str(type(e))

    @pytest.mark.asyncio
    async def test_metrics_and_monitoring(self, shared_ib_service):
        """Test that metrics collection works."""
        ib_service = shared_ib_service

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

    def test_api_response_format_consistency(self, shared_data_service):
        """Test that API response formats are consistent."""
        # This test ensures the DataService returns the expected format
        ds = shared_data_service

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
    async def test_ib_service_api_compatibility(self, shared_ib_service):
        """Test that IbService API is compatible with endpoints."""
        ib_service = shared_ib_service

        # Test all the methods used by API endpoints
        status = await ib_service.get_status()
        health = await ib_service.get_health()
        config = await ib_service.get_config()

        # Verify types match what API expects
        from ktrdr.api.models.ib import IbConfigInfo, IbHealthStatus, IbStatusResponse

        assert isinstance(status, IbStatusResponse)
        assert isinstance(health, IbHealthStatus)
        assert isinstance(config, IbConfigInfo)

    def test_backward_compatibility_imports(self):
        """Test that existing imports still work."""
        # Test key imports that should continue working
        try:
            from ktrdr.data import DataManager
            from ktrdr.data.ib_data_adapter import IbDataAdapter
            from ktrdr.ib.pool_manager import get_shared_ib_pool

            # Should not raise ImportError
            assert DataManager is not None
            assert get_shared_ib_pool is not None
            assert IbDataAdapter is not None

        except ImportError as e:
            pytest.fail(f"Backward compatibility broken: {e}")

    def test_configuration_loading(self, shared_data_manager):
        """Test that configuration loading works correctly."""
        # Test that components can load configuration
        dm = shared_data_manager

        # Should not raise configuration errors
        assert dm.data_loader is not None

        # Test that IB components initialize with config
        if dm.external_provider:
            # Should have initialized adapter
            assert hasattr(dm.external_provider, "host")
            assert hasattr(dm.external_provider, "port")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
