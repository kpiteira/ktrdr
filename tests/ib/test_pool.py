"""
Unit tests for IB Connection Pool

Tests the simplified connection pool functionality.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from ktrdr.ib.pool import IbConnectionPool


class TestIbConnectionPool(unittest.TestCase):
    """Test IB connection pool functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.host = "localhost"
        self.port = 4002
        self.max_connections = 3
        
    def test_pool_initialization(self):
        """Test pool initialization."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        self.assertEqual(pool.host, self.host)
        self.assertEqual(pool.port, self.port)
        self.assertEqual(pool.max_connections, self.max_connections)
        self.assertEqual(len(pool.connections), 0)
        self.assertEqual(pool.next_client_id, 1)
        self.assertEqual(pool.connections_created, 0)
        self.assertEqual(pool.connections_reused, 0)
        self.assertEqual(pool.cleanup_count, 0)
    
    def test_pool_str_repr(self):
        """Test string representations."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        str_repr = str(pool)
        self.assertIn("0/3 connections", str_repr)
        
        detailed_repr = repr(pool)
        self.assertIn(self.host, detailed_repr)
        self.assertIn(str(self.port), detailed_repr)
        self.assertIn("connections=0/3", detailed_repr)
    
    def test_get_pool_stats(self):
        """Test pool statistics."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        stats = pool.get_pool_stats()
        
        expected_keys = {
            "total_connections", "healthy_connections", "unhealthy_connections",
            "max_connections", "next_client_id", "connections_created",
            "connections_reused", "cleanup_count", "host", "port"
        }
        self.assertEqual(set(stats.keys()), expected_keys)
        
        self.assertEqual(stats["total_connections"], 0)
        self.assertEqual(stats["healthy_connections"], 0)
        self.assertEqual(stats["unhealthy_connections"], 0)
        self.assertEqual(stats["max_connections"], self.max_connections)
        self.assertEqual(stats["next_client_id"], 1)
        self.assertEqual(stats["connections_created"], 0)
        self.assertEqual(stats["connections_reused"], 0)
        self.assertEqual(stats["cleanup_count"], 0)
        self.assertEqual(stats["host"], self.host)
        self.assertEqual(stats["port"], self.port)
    
    def test_get_connection_stats_empty(self):
        """Test connection statistics when pool is empty."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        stats = pool.get_connection_stats()
        
        self.assertEqual(stats, [])
    
    async def test_cleanup_all(self):
        """Test cleaning up all connections."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Add mock connections
        mock_conn1 = Mock()
        mock_conn2 = Mock()
        pool.connections = [mock_conn1, mock_conn2]
        
        await pool.cleanup_all()
        
        # Verify all connections were stopped
        mock_conn1.stop.assert_called_once()
        mock_conn2.stop.assert_called_once()
        
        # Verify pool is empty
        self.assertEqual(len(pool.connections), 0)
    
    async def test_health_check_empty_pool(self):
        """Test health check on empty pool."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        health = await pool.health_check()
        
        self.assertFalse(health["healthy"])
        self.assertEqual(health["healthy_connections"], 0)
        self.assertEqual(health["total_connections"], 0)
        self.assertEqual(health["pool_utilization"], 0.0)
        self.assertTrue(health["can_create_new"])
        self.assertEqual(health["next_client_id"], 1)
    
    async def test_health_check_with_healthy_connections(self):
        """Test health check with healthy connections."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Add mock healthy connection
        mock_conn = Mock()
        mock_conn.is_healthy.return_value = True
        mock_conn.get_stats.return_value = {"client_id": 1, "healthy": True}
        pool.connections = [mock_conn]
        
        health = await pool.health_check()
        
        self.assertTrue(health["healthy"])
        self.assertEqual(health["healthy_connections"], 1)
        self.assertEqual(health["total_connections"], 1)
        self.assertAlmostEqual(health["pool_utilization"], 1/3)
        self.assertTrue(health["can_create_new"])
    
    async def test_find_healthy_connection(self):
        """Test finding healthy connections."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Add mix of healthy and unhealthy connections
        healthy_conn = Mock()
        healthy_conn.is_healthy.return_value = True
        
        unhealthy_conn = Mock()
        unhealthy_conn.is_healthy.return_value = False
        
        pool.connections = [unhealthy_conn, healthy_conn]
        
        found_conn = await pool._find_healthy_connection()
        self.assertEqual(found_conn, healthy_conn)
    
    async def test_find_healthy_connection_none_available(self):
        """Test finding healthy connections when none available."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Add only unhealthy connections
        unhealthy_conn1 = Mock()
        unhealthy_conn1.is_healthy.return_value = False
        
        unhealthy_conn2 = Mock()
        unhealthy_conn2.is_healthy.return_value = False
        
        pool.connections = [unhealthy_conn1, unhealthy_conn2]
        
        found_conn = await pool._find_healthy_connection()
        self.assertIsNone(found_conn)
    
    async def test_cleanup_unhealthy_connections(self):
        """Test cleanup of unhealthy connections."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Add mix of healthy and unhealthy connections
        healthy_conn = Mock()
        healthy_conn.is_healthy.return_value = True
        
        unhealthy_conn1 = Mock()
        unhealthy_conn1.is_healthy.return_value = False
        
        unhealthy_conn2 = Mock()
        unhealthy_conn2.is_healthy.return_value = False
        
        pool.connections = [unhealthy_conn1, healthy_conn, unhealthy_conn2]
        
        await pool._cleanup_unhealthy_connections()
        
        # Should only have healthy connection left
        self.assertEqual(len(pool.connections), 1)
        self.assertEqual(pool.connections[0], healthy_conn)
        
        # Unhealthy connections should have been stopped
        unhealthy_conn1.stop.assert_called_once()
        unhealthy_conn2.stop.assert_called_once()
        
        # Cleanup count should be updated
        self.assertEqual(pool.cleanup_count, 2)
    
    @patch('ktrdr.ib.pool.IbConnection')
    async def test_create_new_connection_success(self, mock_ib_connection_class):
        """Test successful creation of new connection."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Mock successful connection
        mock_conn = Mock()
        mock_conn.start.return_value = True
        mock_conn.is_healthy.return_value = True
        mock_ib_connection_class.return_value = mock_conn
        
        connection = await pool._create_new_connection(timeout=30.0)
        
        self.assertEqual(connection, mock_conn)
        mock_ib_connection_class.assert_called_once_with(1, self.host, self.port)
        mock_conn.start.assert_called_once()
        self.assertEqual(pool.next_client_id, 2)
    
    @patch('ktrdr.ib.pool.IbConnection')
    async def test_create_new_connection_client_id_conflict(self, mock_ib_connection_class):
        """Test handling client ID conflicts."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # First connection fails with client ID conflict
        failed_conn = Mock()
        failed_conn.start.side_effect = Exception("Error 326: Client id is already in use")
        
        # Second connection succeeds
        success_conn = Mock()
        success_conn.start.return_value = True
        success_conn.is_healthy.return_value = True
        
        mock_ib_connection_class.side_effect = [failed_conn, success_conn]
        
        with patch('ktrdr.ib.pool.IbErrorClassifier.is_client_id_conflict', return_value=True):
            connection = await pool._create_new_connection(timeout=30.0)
        
        self.assertEqual(connection, success_conn)
        self.assertEqual(pool.next_client_id, 3)  # Should have incremented twice
    
    @patch('ktrdr.ib.pool.IbConnection')
    async def test_create_new_connection_timeout(self, mock_ib_connection_class):
        """Test connection creation timeout."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Mock connection that takes too long
        mock_conn = Mock()
        mock_conn.start.return_value = True
        mock_conn.is_healthy.return_value = False  # Never becomes healthy
        mock_ib_connection_class.return_value = mock_conn
        
        with self.assertRaises(ConnectionError) as context:
            await pool._create_new_connection(timeout=0.1)  # Very short timeout
        
        self.assertIn("Timeout", str(context.exception))
    
    async def test_acquire_connection_pool_exhausted(self):
        """Test acquire connection when pool is exhausted."""
        pool = IbConnectionPool(self.host, self.port, max_connections=1)
        
        # Fill pool with unhealthy connection
        unhealthy_conn = Mock()
        unhealthy_conn.is_healthy.return_value = False
        pool.connections = [unhealthy_conn]
        
        with self.assertRaises(ConnectionError) as context:
            await pool.acquire_connection()
        
        self.assertIn("pool exhausted", str(context.exception))
    
    async def test_context_manager(self):
        """Test context manager functionality."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Mock acquire_connection
        mock_conn = Mock()
        
        with patch.object(pool, 'acquire_connection', new_callable=AsyncMock) as mock_acquire:
            mock_acquire.return_value = mock_conn
            
            async with pool.get_connection() as conn:
                self.assertEqual(conn, mock_conn)
            
            mock_acquire.assert_called_once()
    
    async def test_execute_with_connection(self):
        """Test execute with connection helper."""
        pool = IbConnectionPool(self.host, self.port, self.max_connections)
        
        # Mock connection and execution
        mock_conn = Mock()
        mock_conn.execute_request = AsyncMock(return_value="test_result")
        
        mock_func = Mock()
        args = (1, 2, 3)
        kwargs = {"a": 1}
        
        with patch.object(pool, 'acquire_connection', new_callable=AsyncMock) as mock_acquire:
            mock_acquire.return_value = mock_conn
            
            result = await pool.execute_with_connection(mock_func, *args, **kwargs)
            
            self.assertEqual(result, "test_result")
            mock_conn.execute_request.assert_called_once_with(mock_func, *args, **kwargs)


if __name__ == "__main__":
    # Run the tests
    unittest.main()