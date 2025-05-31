"""
Tests for IB Connection Manager
"""

import pytest

pytestmark = pytest.mark.skip(reason="IB integration tests disabled for unit test run")
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time

from ktrdr.data.ib_connection import IbConnectionManager, ConnectionConfig
from ktrdr.errors import ConnectionError, retry_with_backoff, RetryConfig


class TestIbConnectionManager:
    """Test IB connection manager functionality."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return ConnectionConfig(host="127.0.0.1", port=7497, client_id=999, timeout=5)

    @pytest.fixture
    def manager(self, config):
        """Create connection manager instance."""
        return IbConnectionManager(config)

    @pytest.mark.asyncio
    async def test_successful_connection(self, manager):
        """Test successful connection to IB."""
        mock_ib = Mock()
        mock_ib.connectAsync = AsyncMock(return_value=None)

        with patch("ktrdr.data.ib_connection.IB", return_value=mock_ib):
            await manager.connect()

            assert manager._connected is True
            assert manager.metrics["total_connections"] == 1
            assert manager.metrics["last_connect_time"] is not None
            mock_ib.connectAsync.assert_called_once_with(
                host="127.0.0.1", port=7497, clientId=999, readonly=False
            )

    @pytest.mark.asyncio
    async def test_connection_timeout(self, manager):
        """Test connection timeout handling."""
        mock_ib = Mock()
        # Simulate timeout
        mock_ib.connectAsync = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("ktrdr.data.ib_connection.IB", return_value=mock_ib):
            with pytest.raises(ConnectionError) as exc_info:
                await manager.connect()

            assert "Connection timeout" in str(exc_info.value)
            assert manager.metrics["failed_connections"] == 1

    def test_connection_retry_decorator_applied(self, manager):
        """Test that retry decorator is applied to connect method."""
        # Verify the retry decorator is applied by checking for __wrapped__
        assert hasattr(manager.connect, "__wrapped__")

        # The wrapped function should be the original connect method
        assert manager.connect.__wrapped__.__name__ == "connect"

    @pytest.mark.asyncio
    async def test_already_connected(self, manager):
        """Test connecting when already connected."""
        manager._connected = True
        mock_ib = Mock()

        with patch("ktrdr.data.ib_connection.IB", return_value=mock_ib):
            await manager.connect()

            # Should not attempt new connection
            mock_ib.connectAsync.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test graceful disconnect."""
        mock_ib = Mock()
        mock_ib.disconnect = Mock()

        manager.ib = mock_ib
        manager._connected = True

        await manager.disconnect()

        assert manager._connected is False
        assert manager.ib is None
        assert manager.metrics["last_disconnect_time"] is not None
        mock_ib.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, manager):
        """Test disconnect when not connected."""
        await manager.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_health_check_success(self, manager):
        """Test successful health check."""
        mock_ib = Mock()
        mock_ib.reqCurrentTimeAsync = AsyncMock(return_value=time.time())

        manager.ib = mock_ib
        manager._connected = True
        manager._last_health_check = 0

        result = await manager.is_connected()

        assert result is True
        mock_ib.reqCurrentTimeAsync.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_rate_limiting(self, manager):
        """Test health check rate limiting."""
        mock_ib = Mock()
        mock_ib.reqCurrentTimeAsync = AsyncMock()

        manager.ib = mock_ib
        manager._connected = True
        manager._last_health_check = time.time() - 1  # 1 second ago

        result = await manager.is_connected()

        assert result is True
        # Should not call health check due to rate limiting
        mock_ib.reqCurrentTimeAsync.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, manager):
        """Test health check failure."""
        mock_ib = Mock()
        mock_ib.reqCurrentTimeAsync = AsyncMock(side_effect=asyncio.TimeoutError())

        manager.ib = mock_ib
        manager._connected = True
        manager._last_health_check = 0

        result = await manager.is_connected()

        assert result is False
        assert manager._connected is False

    def test_sync_connect(self, manager):
        """Test synchronous connect wrapper."""
        with patch.object(manager, "connect", new_callable=AsyncMock):
            manager.connect_sync()
            manager.connect.assert_called_once()

    def test_sync_disconnect(self, manager):
        """Test synchronous disconnect wrapper."""
        manager.ib = Mock()  # Set mock IB instance
        with patch.object(manager, "disconnect", new_callable=AsyncMock):
            manager.disconnect_sync()
            manager.disconnect.assert_called_once()

    def test_context_manager(self, manager):
        """Test context manager functionality."""
        mock_connect = Mock()
        mock_disconnect = Mock()

        manager.connect_sync = mock_connect
        manager.disconnect_sync = mock_disconnect

        with manager as cm:
            assert cm is manager
            mock_connect.assert_called_once()

        mock_disconnect.assert_called_once()

    def test_get_connection_info(self, manager):
        """Test getting connection info."""
        manager._connected = True
        manager.metrics["total_connections"] = 5

        info = manager.get_connection_info()

        assert info["connected"] is True
        assert info["host"] == "127.0.0.1"
        assert info["port"] == 7497
        assert info["client_id"] == 999
        assert info["metrics"]["total_connections"] == 5
        assert info["connection_attempts"] == 0

    def test_default_config(self):
        """Test default configuration values."""
        manager = IbConnectionManager()

        assert manager.config.host == "127.0.0.1"
        assert manager.config.port == 7497
        assert manager.config.client_id == 1
        assert manager.config.timeout == 10
        assert manager.config.readonly is False
