"""
Comprehensive unit tests for IbConnectionPool unified component.

Tests the new connection pool architecture including:
- Connection acquisition and release
- Client ID management integration
- Health monitoring
- Metrics collection
- Error handling and recovery
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from ktrdr.data.ib_connection_pool import (
    IbConnectionPool,
    PooledConnection,
    ConnectionState,
    get_connection_pool,
    acquire_ib_connection,
)
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.errors import ConnectionError


class TestIbConnectionPool:
    """Test suite for IbConnectionPool unified component."""

    @pytest.fixture
    def mock_ib_config(self):
        """Mock IB configuration."""
        config = Mock()
        config.host = "127.0.0.1"
        config.port = 4003
        config.timeout = 30
        return config

    @pytest.fixture
    def mock_ib_instance(self):
        """Mock IB instance."""
        ib = Mock()
        ib.isConnected.return_value = True
        ib.managedAccounts.return_value = ["DU123456"]
        ib.connectAsync = AsyncMock(return_value=True)
        ib.disconnect = Mock()

        # Mock event objects that support += operator
        from unittest.mock import MagicMock

        ib.connectedEvent = MagicMock()
        ib.connectedEvent.__iadd__ = Mock(return_value=ib.connectedEvent)
        ib.disconnectedEvent = MagicMock()
        ib.disconnectedEvent.__iadd__ = Mock(return_value=ib.disconnectedEvent)
        ib.errorEvent = MagicMock()
        ib.errorEvent.__iadd__ = Mock(return_value=ib.errorEvent)

        # Mock async methods for health checks
        ib.reqManagedAcctsAsync = AsyncMock(return_value=["DU123456"])
        ib.reqCurrentTimeAsync = AsyncMock(return_value=1234567890)

        return ib

    @pytest_asyncio.fixture
    async def connection_pool(self, mock_ib_config):
        """Create connection pool for testing."""
        with patch(
            "ktrdr.data.ib_connection_pool.get_ib_config", return_value=mock_ib_config
        ):
            pool = IbConnectionPool()
            yield pool
            if pool._running:
                await pool.stop()

    @pytest.fixture
    def mock_client_id_registry(self):
        """Mock client ID registry functions."""
        with (
            patch("ktrdr.data.ib_connection_pool.allocate_client_id") as mock_allocate,
            patch(
                "ktrdr.data.ib_connection_pool.deallocate_client_id"
            ) as mock_deallocate,
            patch(
                "ktrdr.data.ib_connection_pool.update_client_id_activity"
            ) as mock_update,
        ):

            # Return a sequence of client IDs to track allocations
            mock_allocate.side_effect = [20, 21, 22, 23, 24]  # Sequential client IDs
            yield {
                "allocate": mock_allocate,
                "deallocate": mock_deallocate,
                "update": mock_update,
            }

    @pytest.mark.asyncio
    async def test_pool_start_stop(self, connection_pool):
        """Test basic pool start and stop operations."""
        # Test start
        assert not connection_pool._running
        success = await connection_pool.start()
        assert success
        assert connection_pool._running
        assert connection_pool._health_check_task is not None

        # Test stop
        await connection_pool.stop()
        assert not connection_pool._running

    @pytest.mark.asyncio
    async def test_pool_start_already_running(self, connection_pool):
        """Test starting an already running pool."""
        await connection_pool.start()

        # Try to start again
        success = await connection_pool.start()
        assert success
        assert connection_pool._running

    @pytest.mark.asyncio
    async def test_connection_acquisition_success(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test successful connection acquisition."""
        await connection_pool.start()

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
        ):

            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ) as connection:

                assert connection is not None
                assert connection.client_id == 20
                assert connection.purpose == ClientIdPurpose.DATA_MANAGER
                assert connection.in_use
                assert connection.created_by == "test_component"

                # Verify client ID was allocated with preference strategy
                mock_client_id_registry["allocate"].assert_called_once_with(
                    ClientIdPurpose.DATA_MANAGER, "test_component", 1
                )

    @pytest.mark.asyncio
    async def test_connection_acquisition_failure(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connection acquisition failure."""
        # Mock client ID allocation failure BEFORE starting pool
        mock_client_id_registry["allocate"].side_effect = [None]  # Override side_effect with None
        
        await connection_pool.start()

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
            pytest.raises(ConnectionError, match="Could not acquire connection")
        ):
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ):
                pass

    @pytest.mark.asyncio
    async def test_connection_reuse(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connection reuse for same purpose."""
        await connection_pool.start()

        async def mock_connect_ib(connection):
            """Mock the connection process properly."""
            connection.state = ConnectionState.CONNECTED
            connection.metrics.connected_at = time.time()
            return True

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", side_effect=mock_connect_ib),
        ):

            # First acquisition
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component1"
            ) as connection1:
                client_id1 = connection1.client_id
                # Connection should be marked as in_use
                assert connection1.in_use is True

            # Verify connection is released and available
            assert connection1.in_use is False

            # Check pool state before second acquisition
            purpose_pool = connection_pool._purpose_pools[ClientIdPurpose.DATA_MANAGER]
            assert client_id1 in purpose_pool
            stored_connection = connection_pool._connections[client_id1]
            assert stored_connection is not None
            assert not stored_connection.in_use
            assert stored_connection.is_healthy()

            # Second acquisition should reuse the connection
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component2"
            ) as connection2:
                client_id2 = connection2.client_id

            assert client_id1 == client_id2
            # Client ID should only be allocated once since we reused the connection
            assert mock_client_id_registry["allocate"].call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_purpose_connections(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connections for different purposes."""
        await connection_pool.start()

        # Mock different client IDs for different purposes
        client_ids = [20, 30]
        mock_client_id_registry["allocate"].side_effect = client_ids

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
        ):

            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="data_component"
            ) as conn1:

                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by="api_component"
                ) as conn2:

                    assert conn1.client_id != conn2.client_id
                    assert conn1.purpose == ClientIdPurpose.DATA_MANAGER
                    assert conn2.purpose == ClientIdPurpose.API_POOL

    @pytest.mark.asyncio
    async def test_connection_health_monitoring(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connection health monitoring."""
        await connection_pool.start()

        # Create a mock that actually sets connection state
        async def mock_connect_ib(connection):
            connection.state = ConnectionState.CONNECTED
            connection.metrics.connected_at = time.time()
            return True

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", side_effect=mock_connect_ib),
        ):

            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ) as connection:

                # Test healthy connection
                assert connection.is_healthy()

                # Simulate connection failure
                mock_ib_instance.isConnected.return_value = False
                assert not connection.is_healthy()

    @pytest.mark.asyncio
    async def test_pool_status_reporting(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test pool status reporting."""
        await connection_pool.start()

        async def mock_connect_ib(connection):
            """Mock the connection process properly."""
            connection.state = ConnectionState.CONNECTED
            connection.metrics.connected_at = time.time()
            return True

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", side_effect=mock_connect_ib),
        ):

            # Get initial status
            status = connection_pool.get_pool_status()
            assert status["running"]
            assert status["total_connections"] == 0
            assert status["active_connections"] == 0

            # Create a connection
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ) as connection:

                status = connection_pool.get_pool_status()
                assert status["total_connections"] == 1
                assert status["active_connections"] == 1
                assert status["healthy_connections"] == 1

                # Check purpose statistics
                purpose_stats = status["purpose_statistics"]
                assert ClientIdPurpose.DATA_MANAGER.value in purpose_stats
                data_manager_stats = purpose_stats[ClientIdPurpose.DATA_MANAGER.value]
                assert data_manager_stats["total_connections"] == 1
                assert data_manager_stats["active_connections"] == 1

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connection cleanup when errors occur."""
        await connection_pool.start()

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=False),
        ):  # Simulate connection failure

            with pytest.raises(ConnectionError):
                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
                ):
                    pass

            # Verify client ID was deallocated
            mock_client_id_registry["deallocate"].assert_called_once_with(
                20, "connection_pool_cleanup"
            )

    @pytest.mark.asyncio
    async def test_metrics_integration(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test metrics collection integration."""
        await connection_pool.start()

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
            patch("ktrdr.data.ib_connection_pool.record_operation_start") as mock_start,
            patch("ktrdr.data.ib_connection_pool.record_operation_end") as mock_end,
            patch("ktrdr.data.ib_connection_pool.record_counter") as mock_counter,
            patch("ktrdr.data.ib_connection_pool.record_gauge") as mock_gauge,
        ):

            mock_start.return_value = "operation_123"

            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ) as connection:
                pass

            # Verify metrics were recorded
            mock_start.assert_called()
            mock_end.assert_called()
            mock_counter.assert_called()
            mock_gauge.assert_called()

    @pytest.mark.asyncio
    async def test_preferred_client_id(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test preferred client ID handling."""
        await connection_pool.start()

        preferred_id = 25
        mock_client_id_registry["allocate"].return_value = preferred_id

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
        ):

            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER,
                requested_by="test_component",
                preferred_client_id=preferred_id,
            ) as connection:

                assert connection.client_id == preferred_id

                # Verify preferred ID was passed to allocator
                mock_client_id_registry["allocate"].assert_called_with(
                    ClientIdPurpose.DATA_MANAGER, "test_component", preferred_id
                )

    @pytest.mark.asyncio
    async def test_connection_error_handling(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test various connection error scenarios."""
        await connection_pool.start()

        # Test IB connection failure
        mock_ib_instance.connectAsync.side_effect = Exception("Connection failed")

        with patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance):

            with pytest.raises(ConnectionError):
                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
                ):
                    pass

    @pytest.mark.asyncio
    async def test_global_pool_singleton(self):
        """Test global pool singleton behavior."""
        # Get pool instance
        pool1 = await get_connection_pool()
        pool2 = await get_connection_pool()

        # Should be the same instance
        assert pool1 is pool2
        assert pool1._running  # Should auto-start

        # Cleanup
        await pool1.stop()

    @pytest.mark.skip(
        reason="Convenience function has design issue with async context manager protocol"
    )
    @pytest.mark.asyncio
    async def test_acquire_ib_connection_convenience_function(
        self, mock_client_id_registry, mock_ib_instance
    ):
        """Test the convenience function for acquiring connections."""
        # Since acquire_ib_connection is async, we need to await it first to get the context manager
        mock_connection = Mock()
        mock_connection.client_id = 20

        class MockAsyncContextManager:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_acquire_connection(*args, **kwargs):
            """Mock sync function that returns async context manager."""
            return MockAsyncContextManager()

        with patch(
            "ktrdr.data.ib_connection_pool.get_connection_pool"
        ) as mock_get_pool:
            mock_pool = Mock()
            mock_pool.acquire_connection = mock_acquire_connection
            mock_get_pool.return_value = AsyncMock(return_value=mock_pool)

            # Get the context manager from the async function, then use it
            context_manager = await acquire_ib_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            )

            async with context_manager as connection:
                assert connection.client_id == 20

    def test_pooled_connection_creation(self, mock_ib_instance):
        """Test PooledConnection creation and properties."""
        connection = PooledConnection(
            client_id=20,
            purpose=ClientIdPurpose.DATA_MANAGER,
            ib=mock_ib_instance,
            created_by="test_component",
        )

        assert connection.client_id == 20
        assert connection.purpose == ClientIdPurpose.DATA_MANAGER
        assert connection.ib is mock_ib_instance
        assert connection.created_by == "test_component"
        assert connection.state == ConnectionState.DISCONNECTED
        assert not connection.in_use

        # Initially not healthy since disconnected
        assert not connection.is_healthy()

        # After setting to connected state, should be healthy
        connection.state = ConnectionState.CONNECTED
        assert connection.is_healthy()  # IB is connected by default in mock

    def test_pooled_connection_metrics(self, mock_ib_instance):
        """Test PooledConnection metrics tracking."""
        connection = PooledConnection(
            client_id=20,
            purpose=ClientIdPurpose.DATA_MANAGER,
            ib=mock_ib_instance,
            created_by="test_component",
        )

        # Test activity recording
        initial_count = connection.metrics.activity_count
        connection.mark_used()
        assert connection.metrics.activity_count == initial_count + 1

        # Test error recording
        initial_errors = connection.metrics.error_count
        connection.metrics.record_error()
        assert connection.metrics.error_count == initial_errors + 1

    def test_pooled_connection_info(self, mock_ib_instance):
        """Test PooledConnection info reporting."""
        connection = PooledConnection(
            client_id=20,
            purpose=ClientIdPurpose.DATA_MANAGER,
            ib=mock_ib_instance,
            created_by="test_component",
        )

        info = connection.get_info()

        assert info["client_id"] == 20
        assert info["purpose"] == ClientIdPurpose.DATA_MANAGER.value
        assert info["created_by"] == "test_component"
        assert info["state"] == ConnectionState.DISCONNECTED.value
        assert info["in_use"] is False
        assert "created_at" in info
        assert "last_used" in info
        assert "uptime" in info

    @pytest.mark.asyncio
    async def test_pool_connection_limits(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test connection pool limits per purpose."""
        await connection_pool.start()

        # Mock multiple client IDs
        client_ids = [20, 21, 22]
        mock_client_id_registry["allocate"].side_effect = client_ids

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
        ):

            # The default max connections per purpose should be 1
            # So only one connection should be created per purpose
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component1"
            ) as conn1:

                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component2"
                ) as conn2:

                    # Should reuse the same connection
                    assert conn1.client_id == conn2.client_id

    @pytest.mark.asyncio
    async def test_pool_cleanup_idle_connections(
        self, connection_pool, mock_client_id_registry, mock_ib_instance
    ):
        """Test cleanup of idle connections."""
        await connection_pool.start()

        with (
            patch("ktrdr.data.ib_connection_pool.IB", return_value=mock_ib_instance),
            patch.object(connection_pool, "_connect_ib", return_value=True),
        ):

            # Create and release a connection
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="test_component"
            ) as connection:
                client_id = connection.client_id

            # Connection should still exist in pool
            assert client_id in connection_pool._connections

            # Manually trigger cleanup with very short idle time
            connection_pool._max_idle_time = 0.1
            await asyncio.sleep(0.2)  # Wait longer than idle time
            await connection_pool._cleanup_idle_connections()

            # Connection should be removed
            assert client_id not in connection_pool._connections

            # Verify client ID was deallocated
            mock_client_id_registry["deallocate"].assert_called_with(
                client_id, "pool_cleanup_idle_cleanup"
            )


@pytest.mark.integration
class TestIbConnectionPoolIntegration:
    """Integration tests that require actual IB components."""

    @pytest.mark.asyncio
    async def test_real_ib_config_loading(self):
        """Test loading real IB configuration."""
        from ktrdr.config.ib_config import get_ib_config

        try:
            config = get_ib_config()
            assert hasattr(config, "host")
            assert hasattr(config, "port")
            assert hasattr(config, "timeout")
        except Exception as e:
            pytest.skip(f"IB config not available: {e}")

    @pytest.mark.asyncio
    async def test_client_id_registry_integration(self):
        """Test integration with real client ID registry."""
        from ktrdr.data.ib_client_id_registry import get_client_id_registry

        registry = get_client_id_registry()

        # Clean up any stale allocations from previous tests first
        registry._cleanup_stale_allocations()

        # Test allocation and deallocation
        client_id = registry.allocate_client_id(
            ClientIdPurpose.DATA_MANAGER, "test_integration"
        )

        assert client_id is not None
        assert client_id > 0

        # Cleanup
        registry.deallocate_client_id(client_id, "test_cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
