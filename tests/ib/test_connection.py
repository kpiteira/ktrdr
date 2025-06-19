"""
Unit tests for IB Connection

Tests the dedicated thread connection management functionality.
"""

import unittest
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock
from ktrdr.ib.connection import IbConnection, ConnectionRequest


class TestIbConnection(unittest.TestCase):
    """Test IB connection with dedicated thread."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_id = 1
        self.host = "localhost"
        self.port = 4002

    def test_connection_initialization(self):
        """Test connection initialization."""
        conn = IbConnection(self.client_id, self.host, self.port)

        self.assertEqual(conn.client_id, self.client_id)
        self.assertEqual(conn.host, self.host)
        self.assertEqual(conn.port, self.port)
        self.assertFalse(conn.connected)
        self.assertIsNone(conn.thread)
        self.assertIsNone(conn.loop)
        self.assertEqual(conn.idle_timeout, 180.0)  # 3 minutes
        self.assertEqual(conn.requests_processed, 0)
        self.assertEqual(conn.errors_encountered, 0)

    def test_connection_repr(self):
        """Test string representations."""
        conn = IbConnection(self.client_id, self.host, self.port)

        str_repr = str(conn)
        self.assertIn(str(self.client_id), str_repr)
        self.assertIn("healthy=False", str_repr)

        detailed_repr = repr(conn)
        self.assertIn(str(self.client_id), detailed_repr)
        self.assertIn(self.host, detailed_repr)
        self.assertIn(str(self.port), detailed_repr)

    def test_get_stats(self):
        """Test statistics collection."""
        conn = IbConnection(self.client_id, self.host, self.port)
        stats = conn.get_stats()

        expected_keys = {
            "client_id",
            "connected",
            "healthy",
            "requests_processed",
            "errors_encountered",
            "last_activity",
            "seconds_since_activity",
            "idle_timeout",
            "thread_alive",
            "ib_connected",
            "queue_size",
        }
        self.assertEqual(set(stats.keys()), expected_keys)

        self.assertEqual(stats["client_id"], self.client_id)
        self.assertFalse(stats["connected"])
        self.assertFalse(stats["healthy"])
        self.assertEqual(stats["requests_processed"], 0)
        self.assertEqual(stats["errors_encountered"], 0)
        self.assertEqual(stats["idle_timeout"], 180.0)
        self.assertFalse(stats["thread_alive"])
        self.assertFalse(stats["ib_connected"])
        self.assertEqual(stats["queue_size"], 0)

    def test_health_check_no_thread(self):
        """Test health check when no thread is running."""
        conn = IbConnection(self.client_id, self.host, self.port)
        self.assertFalse(conn.is_healthy())

    @patch("ktrdr.ib.connection.IB")
    def test_start_connection_thread(self, mock_ib_class):
        """Test starting the connection thread."""
        mock_ib = Mock()
        mock_ib_class.return_value = mock_ib

        conn = IbConnection(self.client_id, self.host, self.port)

        # Mock the thread starting
        with patch("threading.Thread") as mock_thread_class:
            mock_thread = Mock()
            mock_thread.is_alive.return_value = True
            mock_thread_class.return_value = mock_thread

            result = conn.start()

            self.assertTrue(result)
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()

    def test_stop_connection(self):
        """Test stopping the connection gracefully."""
        conn = IbConnection(self.client_id, self.host, self.port)

        # Mock a running thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        conn.thread = mock_thread

        conn.stop(timeout=1.0)

        self.assertTrue(conn.stop_event.is_set())
        mock_thread.join.assert_called_once_with(timeout=1.0)

    def test_connection_request_structure(self):
        """Test ConnectionRequest data structure."""
        mock_func = Mock()
        args = (1, 2, 3)
        kwargs = {"a": 1, "b": 2}
        mock_future = Mock()
        timestamp = time.time()

        request = ConnectionRequest(
            func=mock_func,
            args=args,
            kwargs=kwargs,
            request_id="test-request-1",
            result_future=mock_future,
            timestamp=timestamp,
        )

        self.assertEqual(request.func, mock_func)
        self.assertEqual(request.args, args)
        self.assertEqual(request.kwargs, kwargs)
        self.assertEqual(request.result_future, mock_future)
        self.assertEqual(request.timestamp, timestamp)

    @patch("ktrdr.ib.connection.IB")
    def test_execute_request_not_healthy(self, mock_ib_class):
        """Test execute_request fails when connection not healthy."""
        conn = IbConnection(self.client_id, self.host, self.port)

        async def test_async():
            with self.assertRaises(ConnectionError) as context:
                await conn.execute_request(Mock())

            self.assertIn("not healthy", str(context.exception))

        asyncio.run(test_async())

    def test_calculate_duration_for_ib(self):
        """Test IB duration string calculation helper (if needed in real implementation)."""
        # This would test the helper methods used in the actual IB operations
        # For now, we'll just test the basic structure is maintained
        conn = IbConnection(self.client_id, self.host, self.port)

        # Test that the connection maintains proper state
        self.assertIsNotNone(conn.ib)
        self.assertFalse(conn.connected)
        self.assertEqual(conn.request_queue.qsize(), 0)

    def test_idle_timeout_calculation(self):
        """Test idle timeout detection."""
        conn = IbConnection(self.client_id, self.host, self.port)

        # Set last activity to 4 minutes ago
        conn.last_activity = time.time() - 240  # 4 minutes

        # Should be considered idle (timeout is 3 minutes)
        stats = conn.get_stats()
        self.assertGreater(stats["seconds_since_activity"], 180)

    def test_error_counting(self):
        """Test error counting functionality."""
        conn = IbConnection(self.client_id, self.host, self.port)

        # Simulate some errors
        conn.errors_encountered = 5

        stats = conn.get_stats()
        self.assertEqual(stats["errors_encountered"], 5)

    def test_request_counting(self):
        """Test request counting functionality."""
        conn = IbConnection(self.client_id, self.host, self.port)

        # Simulate some processed requests
        conn.requests_processed = 10

        stats = conn.get_stats()
        self.assertEqual(stats["requests_processed"], 10)


class TestConnectionIntegration(unittest.TestCase):
    """Integration tests for connection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client_id = 2
        self.host = "localhost"
        self.port = 4002

    @patch("ktrdr.ib.connection.IB")
    def test_connection_lifecycle_mock(self, mock_ib_class):
        """Test complete connection lifecycle with mocked IB."""
        mock_ib = Mock()
        mock_ib.isConnected.return_value = True
        mock_ib_class.return_value = mock_ib

        conn = IbConnection(self.client_id, self.host, self.port)

        # Mock successful connection
        async def mock_connect_async(*args, **kwargs):
            conn.connected = True

        mock_ib.connectAsync = mock_connect_async

        # Start connection (with mocked event loop)
        with patch.object(conn, "_run_sync_loop"):
            result = conn.start()
            self.assertTrue(result)

            # Verify thread started
            self.assertIsNotNone(conn.thread)

            # Stop connection
            conn.stop()

            # Verify cleanup
            self.assertTrue(conn.stop_event.is_set())

    def test_queue_operations(self):
        """Test request queue operations."""
        conn = IbConnection(self.client_id, self.host, self.port)

        # Initially empty
        self.assertEqual(conn.request_queue.qsize(), 0)

        # Mock request
        mock_func = Mock()
        mock_future = Mock()
        request = ConnectionRequest(
            func=mock_func,
            args=(),
            kwargs={},
            request_id="test-request-2",
            result_future=mock_future,
            timestamp=time.time(),
        )

        # Add request (sync put)
        conn.request_queue.put_nowait(request)
        self.assertEqual(conn.request_queue.qsize(), 1)

        # Get request
        retrieved_request = conn.request_queue.get_nowait()
        self.assertEqual(retrieved_request.func, mock_func)
        self.assertEqual(conn.request_queue.qsize(), 0)


if __name__ == "__main__":
    unittest.main()
