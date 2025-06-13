"""
Unit tests for IB Connection Pool

Tests comprehensive functionality including:
- Async connection acquisition and release
- Connection pooling and reuse
- Health monitoring and recovery
- Purpose-based connection management
- Resource cleanup and lifecycle
- Concurrent access scenarios
- Pool statistics and monitoring
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import List

from ktrdr.data.ib_connection_pool import (
    IbConnectionPool,
    PooledConnection,
    ConnectionState,
    ConnectionMetrics,
    get_connection_pool,
    acquire_ib_connection,
    shutdown_connection_pool
)
from ktrdr.data.ib_client_id_registry import ClientIdPurpose


class TestConnectionMetrics:
    """Test the ConnectionMetrics class."""
    
    def test_metrics_initialization(self):
        """Test metrics are properly initialized."""
        metrics = ConnectionMetrics(created_at=1234567890.0)
        
        assert metrics.created_at == 1234567890.0
        assert metrics.connected_at is None
        assert metrics.last_activity is None
        assert metrics.reconnect_count == 0
        assert metrics.request_count == 0
        assert metrics.error_count == 0
        assert metrics.total_uptime == 0.0
    
    def test_record_activity(self):
        """Test activity recording."""
        metrics = ConnectionMetrics(created_at=time.time())
        initial_count = metrics.request_count
        
        metrics.record_activity()
        
        assert metrics.request_count == initial_count + 1
        assert metrics.last_activity is not None
        assert metrics.last_activity > metrics.created_at
    
    def test_record_error(self):
        """Test error recording."""
        metrics = ConnectionMetrics(created_at=time.time())
        initial_count = metrics.error_count
        
        metrics.record_error()
        
        assert metrics.error_count == initial_count + 1
    
    def test_record_reconnect(self):
        """Test reconnection recording."""
        metrics = ConnectionMetrics(created_at=time.time())
        initial_count = metrics.reconnect_count
        
        metrics.record_reconnect()
        
        assert metrics.reconnect_count == initial_count + 1
        assert metrics.connected_at is not None
    
    def test_get_uptime(self):
        """Test uptime calculation."""
        metrics = ConnectionMetrics(created_at=time.time())
        
        # No connection time yet
        assert metrics.get_uptime() == 0.0
        
        # Set connection time
        metrics.connected_at = time.time()
        time.sleep(0.1)
        
        uptime = metrics.get_uptime()
        assert uptime > 0.0
        assert uptime < 1.0  # Should be small


class TestPooledConnection:
    """Test the PooledConnection class."""
    
    @pytest.fixture
    def mock_ib(self):
        """Create a mock IB instance."""
        ib = Mock()
        ib.isConnected.return_value = True
        return ib
    
    @pytest.fixture
    def pooled_connection(self, mock_ib):
        """Create a test pooled connection."""
        return PooledConnection(
            client_id=123,
            purpose=ClientIdPurpose.API_POOL,
            ib=mock_ib,
            created_by="test_component"
        )
    
    def test_connection_initialization(self, pooled_connection):
        """Test connection is properly initialized."""
        assert pooled_connection.client_id == 123
        assert pooled_connection.purpose == ClientIdPurpose.API_POOL
        assert pooled_connection.state == ConnectionState.DISCONNECTED
        assert pooled_connection.created_by == "test_component"
        assert pooled_connection.in_use is False
        assert pooled_connection.health_check_failures == 0
        assert pooled_connection.metrics.created_at > 0
    
    def test_mark_used(self, pooled_connection):
        """Test marking connection as used."""
        initial_time = pooled_connection.last_used
        initial_count = pooled_connection.metrics.request_count
        
        time.sleep(0.01)
        pooled_connection.mark_used()
        
        assert pooled_connection.last_used > initial_time
        assert pooled_connection.metrics.request_count == initial_count + 1
    
    def test_is_healthy_connected(self, pooled_connection):
        """Test health check for connected connection."""
        pooled_connection.state = ConnectionState.CONNECTED
        pooled_connection.ib.isConnected.return_value = True
        pooled_connection.health_check_failures = 0
        
        assert pooled_connection.is_healthy() is True
    
    def test_is_healthy_disconnected(self, pooled_connection):
        """Test health check for disconnected connection."""
        pooled_connection.state = ConnectionState.DISCONNECTED
        
        assert pooled_connection.is_healthy() is False
    
    def test_is_healthy_too_many_failures(self, pooled_connection):
        """Test health check with too many failures."""
        pooled_connection.state = ConnectionState.CONNECTED
        pooled_connection.ib.isConnected.return_value = True
        pooled_connection.health_check_failures = 5
        
        assert pooled_connection.is_healthy() is False
    
    def test_is_healthy_ib_exception(self, pooled_connection):
        """Test health check when IB throws exception."""
        pooled_connection.state = ConnectionState.CONNECTED
        pooled_connection.ib.isConnected.side_effect = Exception("Connection error")
        
        assert pooled_connection.is_healthy() is False
    
    def test_get_info(self, pooled_connection):
        """Test getting connection information."""
        pooled_connection.state = ConnectionState.CONNECTED
        pooled_connection.in_use = True
        pooled_connection.metrics.request_count = 5
        
        info = pooled_connection.get_info()
        
        assert info["client_id"] == 123
        assert info["purpose"] == "api_pool"
        assert info["state"] == "connected"
        assert info["created_by"] == "test_component"
        assert info["in_use"] is True
        assert info["request_count"] == 5
        assert "uptime" in info
        assert "is_healthy" in info


class TestIbConnectionPool:
    """Test the main IB Connection Pool functionality."""
    
    @pytest.fixture
    def mock_ib_config(self):
        """Mock IB configuration."""
        config = Mock()
        config.host = "127.0.0.1"
        config.port = 7497
        config.timeout = 30
        config.readonly = True
        return config
    
    @pytest.fixture
    def mock_client_id_registry(self):
        """Mock client ID registry."""
        registry = Mock()
        registry.allocate_client_id.return_value = 123
        registry.deallocate_client_id.return_value = True
        registry.update_last_seen.return_value = True
        return registry
    
    @pytest.fixture
    async def connection_pool(self, mock_ib_config, mock_client_id_registry):
        """Create a test connection pool."""
        # Reset singleton
        IbConnectionPool._instance = None
        
        with patch('ktrdr.data.ib_connection_pool.get_ib_config', return_value=mock_ib_config), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry', return_value=mock_client_id_registry), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', return_value=123), \
             patch('ktrdr.data.ib_connection_pool.deallocate_client_id', return_value=True), \
             patch('ktrdr.data.ib_connection_pool.update_client_id_activity', return_value=True):
            
            pool = IbConnectionPool()
            await pool.start()
            
            yield pool
            
            await pool.stop()
        
        # Clean up singleton
        IbConnectionPool._instance = None
    
    @pytest.fixture
    def mock_ib_instance(self):
        """Create a mock IB instance that behaves like a connected instance."""
        ib = Mock()
        ib.isConnected.return_value = True
        ib.connectAsync = AsyncMock()
        ib.disconnect = Mock()
        ib.reqCurrentTimeAsync = AsyncMock(return_value=time.time())
        
        # Mock event attributes
        ib.connectedEvent = Mock()
        ib.disconnectedEvent = Mock()
        ib.errorEvent = Mock()
        
        # Mock += operator for events
        ib.connectedEvent.__iadd__ = Mock(return_value=ib.connectedEvent)
        ib.disconnectedEvent.__iadd__ = Mock(return_value=ib.disconnectedEvent)
        ib.errorEvent.__iadd__ = Mock(return_value=ib.errorEvent)
        
        return ib
    
    @pytest.mark.asyncio
    async def test_singleton_pattern(self, mock_ib_config, mock_client_id_registry):
        """Test that pool follows singleton pattern."""
        IbConnectionPool._instance = None
        
        with patch('ktrdr.data.ib_connection_pool.get_ib_config', return_value=mock_ib_config), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry', return_value=mock_client_id_registry):
            
            pool1 = IbConnectionPool()
            pool2 = IbConnectionPool()
            
            assert pool1 is pool2
        
        IbConnectionPool._instance = None
    
    @pytest.mark.asyncio
    async def test_pool_start_and_stop(self, connection_pool):
        """Test pool start and stop functionality."""
        assert connection_pool._running is True
        assert connection_pool._health_check_task is not None
        
        await connection_pool.stop()
        
        assert connection_pool._running is False
        assert connection_pool._health_check_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_connection_creation(self, connection_pool, mock_ib_instance):
        """Test creating a new connection."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            assert connection is not None
            assert connection.client_id == 123
            assert connection.purpose == ClientIdPurpose.API_POOL
            assert connection.created_by == "test_component"
            assert connection.ib is mock_ib_instance
    
    @pytest.mark.asyncio
    async def test_connection_acquisition_and_release(self, connection_pool, mock_ib_instance):
        """Test acquiring and releasing connections."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            ) as connection:
                assert connection is not None
                assert connection.in_use is True
                assert connection.client_id == 123
            
            # After context, connection should be released
            assert connection.in_use is False
    
    @pytest.mark.asyncio
    async def test_connection_reuse(self, connection_pool, mock_ib_instance):
        """Test that connections are reused when available."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # First acquisition creates a connection
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component1"
            ) as connection1:
                first_client_id = connection1.client_id
            
            # Second acquisition should reuse the same connection
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component2"
            ) as connection2:
                assert connection2.client_id == first_client_id
    
    @pytest.mark.asyncio
    async def test_purpose_based_allocation(self, connection_pool, mock_ib_instance):
        """Test that different purposes get different connections."""
        client_id_counter = 100
        
        def mock_allocate_client_id(purpose, allocated_by, preferred_id=None):
            nonlocal client_id_counter
            client_id_counter += 1
            return client_id_counter
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', side_effect=mock_allocate_client_id):
            
            # Acquire connections for different purposes
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="api_component"
            ) as api_connection:
                api_client_id = api_connection.client_id
            
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.GAP_FILLER,
                requested_by="gap_component"
            ) as gap_connection:
                gap_client_id = gap_connection.client_id
            
            # Should have different client IDs
            assert api_client_id != gap_client_id
    
    @pytest.mark.asyncio
    async def test_connection_limit_enforcement(self, connection_pool, mock_ib_instance):
        """Test that connection limits are enforced."""
        # Set a low limit for testing
        connection_pool._max_connections_per_purpose[ClientIdPurpose.API_SINGLETON] = 1
        
        client_id_counter = 200
        
        def mock_allocate_client_id(purpose, allocated_by, preferred_id=None):
            nonlocal client_id_counter
            client_id_counter += 1
            return client_id_counter
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', side_effect=mock_allocate_client_id):
            
            # First connection should succeed
            async with connection_pool.acquire_connection(
                purpose=ClientIdPurpose.API_SINGLETON,
                requested_by="component1"
            ) as connection1:
                assert connection1 is not None
                
                # Second connection should reuse the first (since limit is 1)
                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.API_SINGLETON,
                    requested_by="component2"
                ) as connection2:
                    assert connection2 is not None
                    assert connection2.client_id == connection1.client_id
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, connection_pool, mock_ib_instance):
        """Test health monitoring functionality."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # Create a connection
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            assert connection is not None
            
            # Simulate health check
            await connection_pool._perform_health_checks()
            
            # Connection should still be healthy
            assert connection.health_check_failures == 0
            assert connection.is_healthy()
    
    @pytest.mark.asyncio
    async def test_unhealthy_connection_removal(self, connection_pool, mock_ib_instance):
        """Test removal of unhealthy connections."""
        # Make IB instance appear unhealthy
        mock_ib_instance.isConnected.return_value = False
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # Create a connection
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            client_id = connection.client_id
            
            # Simulate multiple failed health checks
            for _ in range(3):
                await connection_pool._perform_health_checks()
            
            # Connection should be removed
            assert client_id not in connection_pool._connections
    
    @pytest.mark.asyncio
    async def test_idle_connection_cleanup(self, connection_pool, mock_ib_instance):
        """Test cleanup of idle connections."""
        # Set short idle time for testing
        connection_pool._max_idle_time = 0.1  # 100ms
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # Create a connection
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            client_id = connection.client_id
            
            # Wait for it to become idle
            await asyncio.sleep(0.2)
            
            # Run cleanup
            await connection_pool._cleanup_idle_connections()
            
            # Connection should be removed
            assert client_id not in connection_pool._connections
    
    @pytest.mark.asyncio
    async def test_pool_status(self, connection_pool, mock_ib_instance):
        """Test getting pool status."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # Create some connections
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            status = connection_pool.get_pool_status()
            
            assert status["running"] is True
            assert status["total_connections"] == 1
            assert status["healthy_connections"] == 1
            assert "purpose_statistics" in status
            assert "pool_uptime_seconds" in status
            assert "configuration" in status
            assert "statistics" in status
    
    @pytest.mark.asyncio
    async def test_connection_details(self, connection_pool, mock_ib_instance):
        """Test getting connection details."""
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance):
            # Create a connection
            connection = await connection_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            details = connection_pool.get_connection_details()
            
            assert len(details) == 1
            assert details[0]["client_id"] == connection.client_id
            assert details[0]["purpose"] == "api_pool"
            assert details[0]["created_by"] == "test_component"
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_acquisition(self, connection_pool, mock_ib_instance):
        """Test concurrent connection acquisition."""
        client_id_counter = 300
        
        def mock_allocate_client_id(purpose, allocated_by, preferred_id=None):
            nonlocal client_id_counter
            client_id_counter += 1
            return client_id_counter
        
        async def acquire_connection(component_id):
            with patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib_instance), \
                 patch('ktrdr.data.ib_connection_pool.allocate_client_id', side_effect=mock_allocate_client_id):
                
                async with connection_pool.acquire_connection(
                    purpose=ClientIdPurpose.TEST_CONNECTIONS,
                    requested_by=f"component_{component_id}"
                ) as connection:
                    await asyncio.sleep(0.01)  # Simulate some work
                    return connection.client_id
        
        # Run multiple concurrent acquisitions
        tasks = [acquire_connection(i) for i in range(5)]
        client_ids = await asyncio.gather(*tasks)
        
        # All should succeed and return valid client IDs
        assert all(cid is not None for cid in client_ids)
        assert len(set(client_ids)) <= 5  # May reuse connections


class TestConvenienceFunctions:
    """Test the convenience functions."""
    
    @pytest.fixture(autouse=True)
    async def reset_global_pool(self):
        """Reset global pool before each test."""
        import ktrdr.data.ib_connection_pool
        ktrdr.data.ib_connection_pool._pool = None
        yield
        await shutdown_connection_pool()
    
    @pytest.mark.asyncio
    async def test_get_connection_pool_singleton(self):
        """Test that get_connection_pool returns singleton."""
        with patch('ktrdr.data.ib_connection_pool.get_ib_config'), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry'):
            
            pool1 = await get_connection_pool()
            pool2 = await get_connection_pool()
            
            assert pool1 is pool2
    
    @pytest.mark.asyncio
    async def test_acquire_ib_connection_convenience(self):
        """Test convenience function for acquiring connections."""
        mock_ib = Mock()
        mock_ib.isConnected.return_value = True
        mock_ib.connectAsync = AsyncMock()
        mock_ib.reqCurrentTimeAsync = AsyncMock(return_value=time.time())
        mock_ib.connectedEvent = Mock()
        mock_ib.disconnectedEvent = Mock()
        mock_ib.errorEvent = Mock()
        mock_ib.connectedEvent.__iadd__ = Mock(return_value=mock_ib.connectedEvent)
        mock_ib.disconnectedEvent.__iadd__ = Mock(return_value=mock_ib.disconnectedEvent)
        mock_ib.errorEvent.__iadd__ = Mock(return_value=mock_ib.errorEvent)
        
        with patch('ktrdr.data.ib_connection_pool.get_ib_config'), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry'), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', return_value=123), \
             patch('ktrdr.data.ib_connection_pool.IB', return_value=mock_ib):
            
            async with acquire_ib_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            ) as connection:
                assert connection is not None
                assert connection.client_id == 123
    
    @pytest.mark.asyncio
    async def test_shutdown_connection_pool(self):
        """Test shutting down the global pool."""
        with patch('ktrdr.data.ib_connection_pool.get_ib_config'), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry'):
            
            pool = await get_connection_pool()
            assert pool._running is True
            
            await shutdown_connection_pool()
            
            # Pool should be stopped and cleared
            import ktrdr.data.ib_connection_pool
            assert ktrdr.data.ib_connection_pool._pool is None


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.fixture
    async def failing_pool(self):
        """Create a pool that will have various failures."""
        IbConnectionPool._instance = None
        
        mock_config = Mock()
        mock_config.host = "127.0.0.1"
        mock_config.port = 7497
        mock_config.timeout = 30
        mock_config.readonly = True
        
        mock_registry = Mock()
        mock_registry.allocate_client_id.return_value = 123
        
        with patch('ktrdr.data.ib_connection_pool.get_ib_config', return_value=mock_config), \
             patch('ktrdr.data.ib_connection_pool.get_client_id_registry', return_value=mock_registry):
            
            pool = IbConnectionPool()
            await pool.start()
            
            yield pool
            
            await pool.stop()
        
        IbConnectionPool._instance = None
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, failing_pool):
        """Test handling of connection failures."""
        # Mock IB that fails to connect
        failing_ib = Mock()
        failing_ib.connectAsync = AsyncMock(side_effect=Exception("Connection failed"))
        failing_ib.isConnected.return_value = False
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=failing_ib), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', return_value=123), \
             patch('ktrdr.data.ib_connection_pool.deallocate_client_id', return_value=True):
            
            connection = await failing_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            # Connection creation should fail gracefully
            assert connection is None
    
    @pytest.mark.asyncio
    async def test_client_id_allocation_failure(self, failing_pool):
        """Test handling when client ID allocation fails."""
        with patch('ktrdr.data.ib_connection_pool.allocate_client_id', return_value=None):
            
            connection = await failing_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            # Should fail gracefully
            assert connection is None
    
    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self, failing_pool):
        """Test handling of connection timeouts."""
        # Mock IB that times out
        slow_ib = Mock()
        slow_ib.connectAsync = AsyncMock(side_effect=asyncio.TimeoutError())
        slow_ib.isConnected.return_value = False
        
        with patch('ktrdr.data.ib_connection_pool.IB', return_value=slow_ib), \
             patch('ktrdr.data.ib_connection_pool.allocate_client_id', return_value=123), \
             patch('ktrdr.data.ib_connection_pool.deallocate_client_id', return_value=True):
            
            connection = await failing_pool._create_new_connection(
                purpose=ClientIdPurpose.API_POOL,
                requested_by="test_component"
            )
            
            # Connection creation should fail due to timeout
            assert connection is None


if __name__ == "__main__":
    pytest.main([__file__])