"""
Comprehensive integration tests for unified IB components.

These tests require a running IB Gateway/TWS instance and test the complete
workflow of the refactored IB system including:
- Connection pool management
- Data fetching with unified components
- Symbol validation
- Pace management
- Metrics collection
- Health monitoring
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

from ktrdr.data.ib_connection_pool import (
    get_connection_pool,
    acquire_ib_connection,
    IbConnectionPool,
)
from ktrdr.data.ib_client_id_registry import ClientIdPurpose, get_client_id_registry
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.data.ib_pace_manager import get_pace_manager
from ktrdr.data.ib_metrics_collector import get_metrics_collector
from ktrdr.data.ib_health_monitor import get_health_monitor, start_health_monitoring
from ktrdr.config.ib_config import get_ib_config


@pytest.mark.integration
@pytest.mark.real_ib
@pytest.mark.skipif("not config.getoption('--run-integration', default=False)", reason="Integration tests skipped - use --run-integration to run")
class TestIbUnifiedIntegration:
    """Integration tests for unified IB components."""

    @pytest.fixture(scope="class")
    async def ib_config(self):
        """Get IB configuration."""
        try:
            config = get_ib_config()
            # Test basic connectivity before proceeding
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                result = sock.connect_ex((config.host, config.port))
                if result != 0:
                    pytest.skip(f"IB Gateway not available at {config.host}:{config.port}")
            finally:
                sock.close()
            yield config
        except Exception as e:
            pytest.skip(f"IB configuration not available: {e}")

    @pytest.fixture(scope="class")
    async def connection_pool(self, ib_config):
        """Set up connection pool for testing."""
        pool = await get_connection_pool()

        # Ensure pool is started
        if not pool._running:
            success = await pool.start()
            if not success:
                pytest.skip("Could not start connection pool")

        yield pool

        # Cleanup
        await pool.stop()

    @pytest.fixture(scope="class")
    async def health_monitor(self):
        """Set up health monitor for testing."""
        monitor = get_health_monitor()

        success = await start_health_monitoring()
        if not success:
            pytest.skip("Could not start health monitoring")

        yield monitor

        # Cleanup
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_connection_pool_basic_functionality(self, connection_pool):
        """Test basic connection pool functionality."""
        # Test pool status
        status = connection_pool.get_pool_status()
        assert status["running"] is True

        # Test connection acquisition
        async with acquire_ib_connection(
            purpose=ClientIdPurpose.DATA_MANAGER, requested_by="integration_test"
        ) as connection:

            assert connection is not None
            assert connection.client_id > 0
            assert connection.purpose == ClientIdPurpose.DATA_MANAGER
            assert connection.in_use is True
            assert connection.is_healthy() is True

            # Test IB API access
            ib = connection.ib
            assert ib.isConnected() is True

            # Get managed accounts (should work if properly connected)
            accounts = ib.managedAccounts()
            assert isinstance(accounts, list)
            assert len(accounts) > 0  # Should have at least one account

    @pytest.mark.asyncio
    async def test_multiple_purpose_connections(self, connection_pool):
        """Test connections for different purposes."""
        purposes = [
            ClientIdPurpose.DATA_MANAGER,
            ClientIdPurpose.API_POOL,
            ClientIdPurpose.GAP_FILLER,
        ]

        connections = []

        try:
            # Acquire connections for different purposes
            for purpose in purposes:
                async with acquire_ib_connection(
                    purpose=purpose, requested_by=f"integration_test_{purpose.value}"
                ) as connection:

                    connections.append(connection)
                    assert connection.purpose == purpose
                    assert connection.is_healthy()

                    # Each purpose should get a different client ID
                    client_ids = [conn.client_id for conn in connections]
                    assert len(set(client_ids)) == len(client_ids)  # All unique

        except Exception as e:
            pytest.fail(f"Failed to acquire connections for multiple purposes: {e}")

    @pytest.mark.asyncio
    async def test_data_fetcher_unified(self, connection_pool):
        """Test unified data fetcher functionality."""
        data_fetcher = IbDataFetcherUnified(component_name="integration_test_fetcher")

        # Test data fetching for a common stock
        symbol = "AAPL"
        timeframe = "1d"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        try:
            df = await data_fetcher.fetch_historical_data(
                symbol=symbol, timeframe=timeframe, start=start_date, end=end_date
            )

            assert df is not None
            assert not df.empty
            assert len(df) > 0

            # Check required columns
            required_columns = ["open", "high", "low", "close", "volume"]
            for col in required_columns:
                assert col in df.columns

            # Check data integrity
            assert (df["high"] >= df["low"]).all()
            assert (df["high"] >= df["open"]).all()
            assert (df["high"] >= df["close"]).all()
            assert (df["low"] <= df["open"]).all()
            assert (df["low"] <= df["close"]).all()
            assert (df["volume"] >= 0).all()

        except Exception as e:
            pytest.fail(f"Data fetching failed: {e}")

    @pytest.mark.asyncio
    async def test_symbol_validator_unified(self, connection_pool):
        """Test unified symbol validator functionality."""
        validator = IbSymbolValidatorUnified(
            component_name="integration_test_validator"
        )

        # Test valid symbols
        valid_symbols = ["AAPL", "MSFT", "GOOGL", "EURUSD"]

        for symbol in valid_symbols:
            try:
                is_valid = await validator.validate_symbol_async(symbol)
                assert is_valid is True, f"Symbol {symbol} should be valid"

                # Get contract details
                contract_info = await validator.get_contract_details_async(symbol)
                assert contract_info is not None
                assert contract_info.symbol is not None
                assert contract_info.asset_type is not None
                assert contract_info.exchange is not None

            except Exception as e:
                pytest.fail(f"Symbol validation failed for {symbol}: {e}")

        # Test invalid symbol
        try:
            is_valid = await validator.validate_symbol_async("INVALID_SYMBOL_12345")
            assert is_valid is False, "Invalid symbol should not validate"
        except Exception as e:
            # Invalid symbols may raise exceptions, which is acceptable
            pass

    @pytest.mark.asyncio
    async def test_head_timestamp_fetching(self, connection_pool):
        """Test head timestamp fetching functionality."""
        validator = IbSymbolValidatorUnified(
            component_name="integration_test_head_timestamp"
        )

        # Test head timestamp for common symbols
        test_cases = [
            ("AAPL", "1d"),
            ("AAPL", "1h"),
            ("EURUSD", "1d"),
        ]

        for symbol, timeframe in test_cases:
            try:
                head_timestamp = await validator.fetch_head_timestamp_async(
                    symbol, timeframe
                )

                if head_timestamp:
                    assert isinstance(head_timestamp, datetime)
                    assert head_timestamp < datetime.now(head_timestamp.tzinfo)

                    # Head timestamp should be reasonable (not too old)
                    years_ago = datetime.now(head_timestamp.tzinfo) - timedelta(
                        days=365 * 20
                    )
                    assert (
                        head_timestamp > years_ago
                    ), f"Head timestamp too old for {symbol}"

            except Exception as e:
                pytest.fail(
                    f"Head timestamp fetching failed for {symbol} {timeframe}: {e}"
                )

    @pytest.mark.asyncio
    async def test_pace_manager_functionality(self, connection_pool):
        """Test pace manager functionality."""
        pace_manager = get_pace_manager()

        # Test pace limit checking
        symbol = "AAPL"
        timeframe = "1h"
        component = "integration_test_pace"

        try:
            # This should not raise an exception for normal requests
            await pace_manager.check_pace_limits_async(
                symbol=symbol,
                timeframe=timeframe,
                component=component,
                operation="test_request",
            )

            # Get pace manager status
            status = pace_manager.get_status()
            assert "total_requests" in status
            assert "pace_violations" in status
            assert "last_updated" in status

        except Exception as e:
            pytest.fail(f"Pace manager check failed: {e}")

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self, connection_pool):
        """Test metrics collection during real operations."""
        metrics_collector = get_metrics_collector()

        # Reset metrics for clean test
        metrics_collector.reset_metrics()

        # Perform some operations
        data_fetcher = IbDataFetcherUnified(component_name="integration_test_metrics")

        symbol = "AAPL"
        timeframe = "1d"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)

        try:
            # Fetch data (should generate metrics)
            df = await data_fetcher.fetch_historical_data(
                symbol=symbol, timeframe=timeframe, start=start_date, end=end_date
            )

            # Check that metrics were collected
            component_metrics = metrics_collector.get_component_metrics(
                "integration_test_metrics"
            )
            assert component_metrics is not None
            assert component_metrics.total_operations > 0

            # Check global metrics
            global_metrics = metrics_collector.get_global_metrics()
            assert global_metrics["total_operations"] > 0
            assert global_metrics["components_active"] > 0

            # Check performance summary
            perf_summary = metrics_collector.get_performance_summary()
            assert "global" in perf_summary
            assert "components" in perf_summary
            assert "integration_test_metrics" in perf_summary["components"]

        except Exception as e:
            pytest.fail(f"Metrics collection integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, health_monitor, connection_pool):
        """Test health monitoring integration."""
        # Give the health monitor time to perform checks
        await asyncio.sleep(2)

        try:
            # Check overall health
            overall_health = health_monitor.get_overall_health()
            assert "status" in overall_health
            assert "components_total" in overall_health
            assert "monitoring_active" in overall_health
            assert overall_health["monitoring_active"] is True

            # Check component health
            components = ["connection_pool", "data_fetcher", "symbol_validator"]

            for component in components:
                component_health = health_monitor.get_component_health(component)
                # Component may not have health data yet if no operations performed
                if component_health:
                    assert "status" in component_health
                    assert "last_check" in component_health
                    assert "metrics" in component_health

            # Check alerts
            alerts = health_monitor.get_all_alerts()
            assert isinstance(alerts, list)

        except Exception as e:
            pytest.fail(f"Health monitoring integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_client_id_registry_integration(self, connection_pool):
        """Test client ID registry integration."""
        registry = get_client_id_registry()

        # Test allocation and deallocation
        client_id = registry.allocate_client_id(
            ClientIdPurpose.DATA_MANAGER, "integration_test_registry"
        )

        assert client_id is not None
        assert client_id > 0

        # Check that ID is tracked
        allocations = registry.get_allocations()
        assert client_id in allocations
        assert allocations[client_id]["purpose"] == ClientIdPurpose.DATA_MANAGER.value

        # Test deallocation
        registry.deallocate_client_id(client_id, "integration_test_cleanup")

        # Check that ID is no longer tracked
        allocations = registry.get_allocations()
        assert client_id not in allocations

    @pytest.mark.asyncio
    async def test_end_to_end_data_workflow(self, connection_pool):
        """Test complete end-to-end data workflow."""
        # This test simulates a complete data fetching workflow
        # using all unified components together

        try:
            # 1. Validate symbol
            validator = IbSymbolValidatorUnified(component_name="e2e_test_validator")
            symbol = "AAPL"

            is_valid = await validator.validate_symbol_async(symbol)
            assert is_valid, f"Symbol {symbol} should be valid"

            # 2. Get head timestamp
            head_timestamp = await validator.fetch_head_timestamp_async(symbol, "1d")
            assert head_timestamp is not None, "Should have head timestamp"

            # 3. Fetch recent data
            data_fetcher = IbDataFetcherUnified(component_name="e2e_test_fetcher")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)

            df = await data_fetcher.fetch_historical_data(
                symbol=symbol, timeframe="1d", start=start_date, end=end_date
            )

            assert df is not None and not df.empty, "Should fetch data successfully"
            assert len(df) > 0, "Should have at least some data"

            # 4. Validate data integrity
            assert "close" in df.columns, "Should have close prices"
            assert (df["close"] > 0).all(), "All prices should be positive"

            # 5. Check that metrics were collected
            metrics_collector = get_metrics_collector()

            validator_metrics = metrics_collector.get_component_metrics(
                "e2e_test_validator"
            )
            fetcher_metrics = metrics_collector.get_component_metrics(
                "e2e_test_fetcher"
            )

            assert validator_metrics is not None, "Should have validator metrics"
            assert fetcher_metrics is not None, "Should have fetcher metrics"
            assert (
                validator_metrics.total_operations > 0
            ), "Should have validator operations"
            assert (
                fetcher_metrics.total_operations > 0
            ), "Should have fetcher operations"

        except Exception as e:
            pytest.fail(f"End-to-end workflow failed: {e}")

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, connection_pool):
        """Test error handling and recovery mechanisms."""
        data_fetcher = IbDataFetcherUnified(component_name="error_test_fetcher")

        # Test with invalid date range (should handle gracefully)
        try:
            future_date = datetime.now() + timedelta(days=365)
            past_date = datetime.now() - timedelta(days=1)

            df = await data_fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe="1d",
                start=future_date,  # Invalid: start after end
                end=past_date,
            )

            # Should either return empty data or raise a handled exception
            if df is not None:
                assert df.empty, "Invalid date range should return empty data"

        except Exception as e:
            # Specific handled exceptions are acceptable
            assert (
                "date" in str(e).lower() or "range" in str(e).lower()
            ), f"Unexpected error: {e}"

        # Test with invalid symbol (should handle gracefully)
        try:
            df = await data_fetcher.fetch_historical_data(
                symbol="INVALID_SYMBOL_XYZ123",
                timeframe="1d",
                start=datetime.now() - timedelta(days=2),
                end=datetime.now(),
            )

            # Should handle invalid symbols gracefully
            if df is not None:
                assert df.empty, "Invalid symbol should return empty data"

        except Exception as e:
            # Specific handled exceptions are acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in ["symbol", "contract", "not found"]
            ), f"Unexpected error: {e}"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, connection_pool):
        """Test concurrent operations using the unified system."""
        # This test verifies that multiple concurrent operations
        # work correctly with the connection pool

        async def fetch_data(symbol: str, component_suffix: str) -> bool:
            """Helper function to fetch data for a symbol."""
            try:
                data_fetcher = IbDataFetcherUnified(
                    component_name=f"concurrent_test_{component_suffix}"
                )

                end_date = datetime.now()
                start_date = end_date - timedelta(days=2)

                df = await data_fetcher.fetch_historical_data(
                    symbol=symbol, timeframe="1d", start=start_date, end=end_date
                )

                return df is not None and not df.empty

            except Exception as e:
                print(f"Concurrent fetch failed for {symbol}: {e}")
                return False

        # Test concurrent fetches for different symbols
        symbols = ["AAPL", "MSFT", "GOOGL"]
        tasks = [fetch_data(symbol, f"symbol_{i}") for i, symbol in enumerate(symbols)]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check results
            success_count = sum(1 for result in results if result is True)
            assert (
                success_count > 0
            ), "At least some concurrent operations should succeed"

            # Check for exceptions
            exceptions = [result for result in results if isinstance(result, Exception)]
            if exceptions:
                print(f"Some concurrent operations failed: {exceptions}")
                # Don't fail the test unless all operations failed
                assert success_count > 0, "All concurrent operations failed"

        except Exception as e:
            pytest.fail(f"Concurrent operations test failed: {e}")


@pytest.mark.integration
@pytest.mark.stress
@pytest.mark.skipif("not config.getoption('--run-stress', default=False)", reason="Stress tests skipped - use --run-stress to run")
class TestIbStressTesting:
    """Stress tests for the unified IB system."""

    @pytest.mark.asyncio
    async def test_high_frequency_requests(self):
        """Test system under high frequency requests."""
        # Check for IB Gateway availability first
        try:
            config = get_ib_config()
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                result = sock.connect_ex((config.host, config.port))
                if result != 0:
                    pytest.skip(f"IB Gateway not available at {config.host}:{config.port}")
            finally:
                sock.close()
        except Exception as e:
            pytest.skip(f"IB configuration not available: {e}")
            
        # This test simulates high-frequency data requests
        # to verify pace management and connection pooling

        connection_pool = await get_connection_pool()
        data_fetcher = IbDataFetcherUnified(component_name="stress_test_fetcher")

        request_count = 20
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]

        async def make_request(i: int) -> Dict[str, Any]:
            """Make a single data request."""
            symbol = symbols[i % len(symbols)]

            try:
                start_time = time.time()

                df = await data_fetcher.fetch_historical_data(
                    symbol=symbol,
                    timeframe="1d",
                    start=datetime.now() - timedelta(days=1),
                    end=datetime.now(),
                )

                duration = time.time() - start_time

                return {
                    "success": df is not None and not df.empty,
                    "duration": duration,
                    "symbol": symbol,
                    "request_id": i,
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "symbol": symbol,
                    "request_id": i,
                }

        # Execute requests
        tasks = [make_request(i) for i in range(request_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successful_requests = [
            r for r in results if isinstance(r, dict) and r.get("success")
        ]
        failed_requests = [
            r for r in results if isinstance(r, dict) and not r.get("success")
        ]
        exceptions = [r for r in results if isinstance(r, Exception)]

        success_rate = len(successful_requests) / request_count

        print(f"Stress test results:")
        print(f"  Total requests: {request_count}")
        print(f"  Successful: {len(successful_requests)}")
        print(f"  Failed: {len(failed_requests)}")
        print(f"  Exceptions: {len(exceptions)}")
        print(f"  Success rate: {success_rate:.2%}")

        if successful_requests:
            avg_duration = sum(r["duration"] for r in successful_requests) / len(
                successful_requests
            )
            print(f"  Average duration: {avg_duration:.3f}s")

        # Assert minimum success rate (should handle pace limits gracefully)
        assert success_rate >= 0.5, f"Success rate too low: {success_rate:.2%}"


def pytest_configure(config):
    """Configure pytest for integration tests."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "stress: marks tests as stress tests")


def pytest_addoption(parser):
    """Add command line options for integration tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require IB Gateway",
    )
    parser.addoption(
        "--run-stress", action="store_true", default=False, help="Run stress tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--run-integration"])
