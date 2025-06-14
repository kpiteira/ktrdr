"""
Tests for IB Configuration
"""

import os
import pytest
from unittest.mock import patch

from ktrdr.config.ib_config import IbConfig, get_ib_config, reset_ib_config


class TestIbConfig:
    """Test IB configuration functionality."""

    def test_default_values(self):
        """Test default configuration values."""
        config = IbConfig()

        assert config.host == "127.0.0.1"
        assert config.port == 4002  # Gateway default
        assert config.client_id == 1
        assert config.timeout == 10  # From .env file
        assert config.readonly is False
        assert config.rate_limit == 50
        assert config.rate_period == 60
        assert config.max_retries == 3
        assert config.retry_base_delay == 2.0
        assert config.retry_max_delay == 60.0
        assert config.pacing_delay == 0.6
        assert config.max_requests_per_10min == 60

    def test_environment_variables(self):
        """Test loading from environment variables."""
        env_vars = {
            "IB_HOST": "192.168.1.100",
            "IB_PORT": "7496",
            "IB_CLIENT_ID": "42",
            "IB_TIMEOUT": "30",
            "IB_READONLY": "true",
            "IB_RATE_LIMIT": "100",
            "IB_RATE_PERIOD": "120",
            "IB_MAX_RETRIES": "5",
            "IB_RETRY_DELAY": "5.0",
            "IB_RETRY_MAX_DELAY": "120.0",
            "IB_PACING_DELAY": "1.0",
            "IB_MAX_REQUESTS_10MIN": "50",
        }

        with patch.dict(os.environ, env_vars):
            config = IbConfig()

            assert config.host == "192.168.1.100"
            assert config.port == 7496  # Live trading
            assert config.client_id == 42
            assert config.timeout == 30
            assert config.readonly is True
            assert config.rate_limit == 100
            assert config.rate_period == 120
            assert config.max_retries == 5
            assert config.retry_base_delay == 5.0
            assert config.retry_max_delay == 120.0
            assert config.pacing_delay == 1.0
            assert config.max_requests_per_10min == 50

    def test_invalid_port(self):
        """Test invalid port validation."""
        with patch.dict(os.environ, {"IB_PORT": "99999"}):
            with pytest.raises(ValueError, match="Invalid port number"):
                IbConfig()

        with patch.dict(os.environ, {"IB_PORT": "0"}):
            with pytest.raises(ValueError, match="Invalid port number"):
                IbConfig()

    def test_invalid_rate_limit(self):
        """Test invalid rate limit validation."""
        with patch.dict(os.environ, {"IB_RATE_LIMIT": "0"}):
            with pytest.raises(ValueError, match="Rate limit must be positive"):
                IbConfig()

        with patch.dict(os.environ, {"IB_RATE_LIMIT": "-10"}):
            with pytest.raises(ValueError, match="Rate limit must be positive"):
                IbConfig()

    def test_invalid_timeout(self):
        """Test invalid timeout validation."""
        with patch.dict(os.environ, {"IB_TIMEOUT": "0"}):
            with pytest.raises(ValueError, match="Timeout must be positive"):
                IbConfig()

    def test_invalid_retry_delays(self):
        """Test invalid retry delay validation."""
        with patch.dict(os.environ, {"IB_RETRY_DELAY": "0"}):
            with pytest.raises(ValueError, match="Retry base delay must be positive"):
                IbConfig()

        with patch.dict(
            os.environ, {"IB_RETRY_DELAY": "10.0", "IB_RETRY_MAX_DELAY": "5.0"}
        ):
            with pytest.raises(
                ValueError, match="Retry max delay.*must be greater than"
            ):
                IbConfig()

    def test_paper_trading_detection(self):
        """Test paper trading port detection."""
        # Test paper trading ports
        for port in [7497, 4002]:
            with patch.dict(os.environ, {"IB_PORT": str(port)}):
                config = IbConfig()
                assert config.is_paper_trading() is True
                assert config.is_live_trading() is False

    def test_live_trading_detection(self):
        """Test live trading port detection."""
        # Test live trading ports
        for port in [7496, 4001]:
            with patch.dict(os.environ, {"IB_PORT": str(port)}):
                config = IbConfig()
                assert config.is_paper_trading() is False
                assert config.is_live_trading() is True

    def test_get_chunk_size(self):
        """Test chunk size retrieval for different bar sizes."""
        config = IbConfig()

        assert config.get_chunk_size("1 min") == 1
        assert config.get_chunk_size("5 mins") == 7
        assert config.get_chunk_size("1 hour") == 1  # Actual value from config
        assert config.get_chunk_size("1 day") == 365
        assert config.get_chunk_size("unknown") == 1  # Default

    def test_get_connection_config(self):
        """Test getting connection config for IbConnectionManager."""
        config = IbConfig()
        conn_config = config.get_connection_config()

        assert conn_config["host"] == config.host
        assert conn_config["port"] == config.port
        assert conn_config["client_id"] == config.client_id
        assert conn_config["timeout"] == config.timeout
        assert conn_config["readonly"] == config.readonly

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = IbConfig()
        data = config.to_dict()

        assert data["host"] == "127.0.0.1"
        assert data["port"] == 4002  # From .env file
        assert data["client_id"] == 1
        assert data["timeout"] == 10
        assert data["readonly"] is False
        assert data["is_paper"] is True
        assert data["is_live"] is False
        assert "rate_limit" in data
        assert "pacing_delay" in data

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "host": "192.168.1.1",
            "port": 7496,
            "client_id": 99,
            "timeout": 20,
            "readonly": True,
            "rate_limit": 75,
            "extra_field": "ignored",  # Should be filtered out
        }

        config = IbConfig.from_dict(data)

        assert config.host == "192.168.1.1"
        assert config.port == 7496
        assert config.client_id == 99
        assert config.timeout == 20
        assert config.readonly is True
        assert config.rate_limit == 75

    def test_get_ib_config_singleton(self):
        """Test that get_ib_config returns singleton."""
        reset_ib_config()  # Clear any existing instance

        config1 = get_ib_config()
        config2 = get_ib_config()

        assert config1 is config2

    def test_reset_ib_config(self):
        """Test resetting configuration."""
        config1 = get_ib_config()
        reset_ib_config()
        config2 = get_ib_config()

        assert config1 is not config2

    def test_chunk_days_comprehensive(self):
        """Test all defined chunk sizes."""
        config = IbConfig()

        expected_chunks = {
            "1 secs": 0.02,
            "5 secs": 0.08,
            "15 secs": 0.17,
            "30 secs": 0.33,
            "1 min": 1,
            "5 mins": 7,
            "15 mins": 14,
            "30 mins": 30,
            "1 hour": 1,  # Actual value from config
            "1 day": 365,
            "1 week": 730,
            "1 month": 365,
        }

        for bar_size, expected_days in expected_chunks.items():
            assert config.get_chunk_size(bar_size) == expected_days
