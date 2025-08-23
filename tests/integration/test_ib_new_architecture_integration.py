"""
Integration tests for new IB architecture with dedicated threads.

These tests validate that the redesigned IB system works correctly:
- Persistent connections survive across multiple operations
- No "handler is closed" errors during normal operation
- DataManager uses new ExternalDataProvider interface
- Error handling based on official IB documentation
- Proper pacing enforcement
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

from ktrdr.config.ib_config import get_ib_config
from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.ib import IbConnectionPool, IbErrorClassifier, IbPaceManager


@pytest.mark.integration
@pytest.mark.real_ib
@pytest.mark.asyncio
@pytest.mark.skipif(
    "not config.getoption('--run-integration', default=False)",
    reason="Integration tests skipped - use --run-integration to run",
)
class TestIbNewArchitectureIntegration:
    """Integration tests for new IB architecture."""

    @pytest.fixture(scope="class")
    def ib_config(self):
        """Get IB configuration."""
        try:
            config = get_ib_config()
            # Test basic connectivity before proceeding
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((config.host, config.port))
                if result != 0:
                    pytest.skip(
                        f"IB Gateway not available at {config.host}:{config.port}"
                    )
            return config
        except Exception as e:
            pytest.skip(f"IB configuration error: {e}")

    @pytest.fixture(scope="class")
    def connection_pool(self, ib_config):
        """Create connection pool for testing."""
        pool = IbConnectionPool(
            host=ib_config.host, port=ib_config.port, max_connections=2
        )
        yield pool
        # Cleanup happens automatically when pool goes out of scope

    @pytest.fixture(scope="class")
    def data_adapter(self, ib_config):
        """Create data adapter for testing."""
        adapter = IbDataAdapter(
            host=ib_config.host, port=ib_config.port, max_connections=2
        )
        yield adapter
        # No explicit cleanup needed - adapter manages its own pool

    async def test_connection_persistence_across_operations(self, connection_pool):
        """Test that connections persist across multiple operations (fixes the core issue)."""
        connection_ids = set()

        # Perform multiple operations and track connection IDs
        for i in range(5):
            async with connection_pool.get_connection() as conn:
                # Record the connection ID
                connection_ids.add(conn.client_id)

                # Perform IB operation
                async def get_current_time(ib):
                    return await ib.reqCurrentTimeAsync()

                current_time = await conn.execute_request(get_current_time)
                assert current_time is not None

                # Small delay between operations
                await asyncio.sleep(0.1)

        # Should reuse connections (not create 5 different ones)
        assert (
            len(connection_ids) <= 2
        ), f"Too many connections created: {connection_ids}"

    async def test_no_handler_closed_errors(self, connection_pool):
        """Test that we don't get 'handler is closed' errors with new architecture."""
        errors_caught = []

        # Perform operations that previously caused handler closed errors
        for i in range(10):
            try:
                async with connection_pool.get_connection() as conn:
                    # This pattern previously caused handler closed errors
                    async def get_accounts(ib):
                        return await ib.reqManagedAcctsAsync()

                    accounts = await conn.execute_request(get_accounts)
                    assert accounts is not None

            except Exception as e:
                error_str = str(e).lower()
                if "handler is closed" in error_str or "transport closed" in error_str:
                    errors_caught.append(e)
                else:
                    # Other errors are OK (permission errors, etc.)
                    pass

        assert (
            len(errors_caught) == 0
        ), f"Handler closed errors detected: {errors_caught}"

    async def test_data_manager_uses_new_adapter(self):
        """Test that DataManager uses the new ExternalDataProvider interface."""
        data_manager = DataManager(enable_ib=True)

        # Verify it uses the new adapter
        assert data_manager.external_provider is not None
        assert data_manager.external_provider.__class__.__name__ == "IbDataAdapter"

        # Test basic functionality through the interface
        timeframes = await data_manager.external_provider.get_supported_timeframes()
        assert "1h" in timeframes
        assert "1d" in timeframes

    async def test_data_adapter_symbol_validation(self, data_adapter):
        """Test symbol validation through the new adapter."""
        # Test valid symbol
        is_valid = await data_adapter.validate_symbol("AAPL")
        assert is_valid, "AAPL should be a valid symbol"

        # Test invalid symbol
        is_valid = await data_adapter.validate_symbol("INVALID_SYMBOL_XYZ")
        assert not is_valid, "Invalid symbol should return False"

    async def test_data_adapter_historical_data(self, data_adapter):
        """Test historical data fetching through the new adapter."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=2)

        try:
            data = await data_adapter.fetch_historical_data(
                symbol="AAPL", timeframe="1h", start=start_date, end=end_date
            )

            assert not data.empty, "Should receive historical data"
            assert "open" in data.columns
            assert "high" in data.columns
            assert "low" in data.columns
            assert "close" in data.columns
            assert "volume" in data.columns

        except Exception as e:
            # Market data permission errors are OK
            if "not subscribed" in str(e).lower() or "permission" in str(e).lower():
                pytest.skip(f"Market data permissions required: {e}")
            else:
                raise

    async def test_pace_manager_enforcement(self):
        """Test that pace manager enforces official IB pacing rules."""
        pace_manager = IbPaceManager()

        # Test general rate limiting
        for i in range(50):
            await pace_manager.wait_if_needed()

        # 51st request should cause a wait
        start_time = time.time()
        await pace_manager.wait_if_needed()
        elapsed = time.time() - start_time

        # Should have waited to respect 50 req/sec limit
        assert elapsed > 0.5, "Should have waited for rate limiting"

    async def test_error_classifier_accuracy(self):
        """Test that error classifier uses official IB documentation."""
        # Test known error codes
        error_type, wait_time = IbErrorClassifier.classify(
            326, "Client id is already in use"
        )
        assert error_type.value == "connection"
        assert wait_time == 2.0

        # Test pacing violation
        error_type, wait_time = IbErrorClassifier.classify(
            100, "Max rate of messages per second has been exceeded"
        )
        assert error_type.value == "pacing"
        assert wait_time == 60.0

        # Test that 162/165 are NOT pacing violations (this was the correction)
        error_type, wait_time = IbErrorClassifier.classify(
            162, "Historical Market Data Service error message"
        )
        assert (
            error_type.value == "data_unavail"
        ), "162 should be data unavailable, not pacing"

    async def test_connection_health_monitoring(self, connection_pool):
        """Test connection health monitoring functionality."""
        health = await connection_pool.health_check()

        assert "healthy" in health
        assert "total_connections" in health
        assert "can_create_new" in health

        # Create a connection and verify stats
        async with connection_pool.get_connection() as conn:
            assert conn.is_healthy()

            stats = conn.get_stats()
            assert stats["client_id"] > 0
            assert "requests_processed" in stats
            assert "errors_encountered" in stats

    async def test_concurrent_operations_stability(self, connection_pool):
        """Test that concurrent operations don't cause threading issues."""

        async def perform_operation(operation_id):
            async with connection_pool.get_connection() as conn:

                async def get_time(ib):
                    return await ib.reqCurrentTimeAsync()

                result = await conn.execute_request(get_time)
                return (operation_id, result)

        # Run 5 concurrent operations
        tasks = [perform_operation(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]

        # Filter out permission-related exceptions (those are OK)
        real_exceptions = []
        for exc in exceptions:
            exc_str = str(exc).lower()
            if "permission" not in exc_str and "not subscribed" not in exc_str:
                real_exceptions.append(exc)

        assert len(real_exceptions) == 0, f"Unexpected exceptions: {real_exceptions}"

    async def test_data_manager_end_to_end(self):
        """Test DataManager with new architecture end-to-end."""
        data_manager = DataManager(enable_ib=True)

        # Test that it can validate symbols
        try:
            # This should work without any handler closed errors
            result = data_manager.is_head_timestamp_available("AAPL", "1h")
            # Result doesn't matter - just that no threading errors occur
            assert isinstance(result, bool)
        except Exception as e:
            # Permission errors are OK
            if "permission" in str(e).lower() or "not subscribed" in str(e).lower():
                pytest.skip(f"Market data permissions required: {e}")
            else:
                raise


if __name__ == "__main__":
    pytest.main([__file__])
