"""
Unit tests for IBSettings configuration.

Tests verify:
- IBSettings loads defaults correctly (matching IbConfig defaults)
- New env var names (KTRDR_IB_*) work
- Old env var names (IB_*) work with deprecation support
- New names take precedence when both are set
- Validation catches invalid values
- Helper methods work correctly
- Cached getter function works correctly
- clear_settings_cache() causes new instance on next call
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    IBSettings,
    clear_settings_cache,
    get_ib_settings,
)


class TestIBSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_host_is_127_0_0_1(self):
        """Default IB host should be 127.0.0.1."""
        settings = IBSettings()
        assert settings.host == "127.0.0.1"

    def test_default_port_is_4002(self):
        """Default IB port should be 4002 (paper trading gateway)."""
        settings = IBSettings()
        assert settings.port == 4002

    def test_default_client_id_is_1(self):
        """Default IB client_id should be 1."""
        settings = IBSettings()
        assert settings.client_id == 1

    def test_default_timeout_is_30(self):
        """Default IB timeout should be 30 seconds."""
        settings = IBSettings()
        assert settings.timeout == 30

    def test_default_readonly_is_false(self):
        """Default IB readonly should be False."""
        settings = IBSettings()
        assert settings.readonly is False

    def test_default_rate_limit_is_50(self):
        """Default IB rate_limit should be 50."""
        settings = IBSettings()
        assert settings.rate_limit == 50

    def test_default_rate_period_is_60(self):
        """Default IB rate_period should be 60 seconds."""
        settings = IBSettings()
        assert settings.rate_period == 60

    def test_default_max_retries_is_3(self):
        """Default IB max_retries should be 3."""
        settings = IBSettings()
        assert settings.max_retries == 3

    def test_default_retry_base_delay_is_2_0(self):
        """Default IB retry_base_delay should be 2.0 seconds."""
        settings = IBSettings()
        assert settings.retry_base_delay == 2.0

    def test_default_retry_max_delay_is_60_0(self):
        """Default IB retry_max_delay should be 60.0 seconds."""
        settings = IBSettings()
        assert settings.retry_max_delay == 60.0

    def test_default_pacing_delay_is_0_6(self):
        """Default IB pacing_delay should be 0.6 seconds."""
        settings = IBSettings()
        assert settings.pacing_delay == 0.6

    def test_default_max_requests_per_10min_is_60(self):
        """Default IB max_requests_per_10min should be 60."""
        settings = IBSettings()
        assert settings.max_requests_per_10min == 60


class TestIBSettingsNewEnvVars:
    """Test new KTRDR_IB_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_ib_host_overrides_default(self):
        """KTRDR_IB_HOST environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST": "192.168.1.100"}, clear=False):
            settings = IBSettings()
            assert settings.host == "192.168.1.100"

    def test_ktrdr_ib_port_overrides_default(self):
        """KTRDR_IB_PORT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "4001"}, clear=False):
            settings = IBSettings()
            assert settings.port == 4001

    def test_ktrdr_ib_client_id_overrides_default(self):
        """KTRDR_IB_CLIENT_ID environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_CLIENT_ID": "42"}, clear=False):
            settings = IBSettings()
            assert settings.client_id == 42

    def test_ktrdr_ib_timeout_overrides_default(self):
        """KTRDR_IB_TIMEOUT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_TIMEOUT": "60"}, clear=False):
            settings = IBSettings()
            assert settings.timeout == 60

    def test_ktrdr_ib_readonly_overrides_default(self):
        """KTRDR_IB_READONLY environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_READONLY": "true"}, clear=False):
            settings = IBSettings()
            assert settings.readonly is True

    def test_ktrdr_ib_rate_limit_overrides_default(self):
        """KTRDR_IB_RATE_LIMIT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_RATE_LIMIT": "100"}, clear=False):
            settings = IBSettings()
            assert settings.rate_limit == 100

    def test_ktrdr_ib_max_retries_overrides_default(self):
        """KTRDR_IB_MAX_RETRIES environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_MAX_RETRIES": "5"}, clear=False):
            settings = IBSettings()
            assert settings.max_retries == 5

    def test_ktrdr_ib_pacing_delay_overrides_default(self):
        """KTRDR_IB_PACING_DELAY environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_PACING_DELAY": "1.0"}, clear=False):
            settings = IBSettings()
            assert settings.pacing_delay == 1.0


class TestIBSettingsDeprecatedEnvVars:
    """Test deprecated IB_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ib_host_deprecated_still_works(self):
        """IB_HOST (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_HOST": "10.0.0.1"}, clear=False):
            settings = IBSettings()
            assert settings.host == "10.0.0.1"

    def test_ib_port_deprecated_still_works(self):
        """IB_PORT (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_PORT": "7497"}, clear=False):
            settings = IBSettings()
            assert settings.port == 7497

    def test_ib_client_id_deprecated_still_works(self):
        """IB_CLIENT_ID (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_CLIENT_ID": "99"}, clear=False):
            settings = IBSettings()
            assert settings.client_id == 99

    def test_ib_timeout_deprecated_still_works(self):
        """IB_TIMEOUT (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_TIMEOUT": "120"}, clear=False):
            settings = IBSettings()
            assert settings.timeout == 120

    def test_ib_readonly_deprecated_still_works(self):
        """IB_READONLY (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_READONLY": "true"}, clear=False):
            settings = IBSettings()
            assert settings.readonly is True

    def test_ib_rate_limit_deprecated_still_works(self):
        """IB_RATE_LIMIT (deprecated) should still override default."""
        with patch.dict(os.environ, {"IB_RATE_LIMIT": "75"}, clear=False):
            settings = IBSettings()
            assert settings.rate_limit == 75


class TestIBSettingsPrecedence:
    """Test that new env vars take precedence over deprecated ones."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_ib_host_takes_precedence_over_ib_host(self):
        """KTRDR_IB_HOST should take precedence when both old and new are set."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST": "new.host.com", "IB_HOST": "old.host.com"},
            clear=False,
        ):
            settings = IBSettings()
            assert settings.host == "new.host.com"

    def test_ktrdr_ib_port_takes_precedence_over_ib_port(self):
        """KTRDR_IB_PORT should take precedence when both are set."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_PORT": "4001", "IB_PORT": "4002"},
            clear=False,
        ):
            settings = IBSettings()
            assert settings.port == 4001


class TestIBSettingsValidation:
    """Test validation of configuration values."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_port_type_raises_validation_error(self):
        """KTRDR_IB_PORT=abc should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "abc"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_port_range_low_raises_validation_error(self):
        """KTRDR_IB_PORT=0 should raise ValidationError (port must be 1-65535)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_port_range_high_raises_validation_error(self):
        """KTRDR_IB_PORT=70000 should raise ValidationError (port must be 1-65535)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "70000"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_timeout_zero_raises_validation_error(self):
        """KTRDR_IB_TIMEOUT=0 should raise ValidationError (must be positive)."""
        with patch.dict(os.environ, {"KTRDR_IB_TIMEOUT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBSettings()
            assert "timeout" in str(exc_info.value).lower()

    def test_invalid_rate_limit_zero_raises_validation_error(self):
        """KTRDR_IB_RATE_LIMIT=0 should raise ValidationError (must be positive)."""
        with patch.dict(os.environ, {"KTRDR_IB_RATE_LIMIT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBSettings()
            assert "rate_limit" in str(exc_info.value).lower()


class TestIBSettingsHelperMethods:
    """Test helper methods on IBSettings."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_get_connection_config_returns_dict(self):
        """get_connection_config() should return a dictionary."""
        settings = IBSettings()
        config = settings.get_connection_config()
        assert isinstance(config, dict)
        assert "host" in config
        assert "port" in config
        assert "client_id" in config
        assert "timeout" in config
        assert "readonly" in config

    def test_get_connection_config_values_match_settings(self):
        """get_connection_config() should return values matching settings."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST": "test.host", "KTRDR_IB_PORT": "7496"},
            clear=False,
        ):
            settings = IBSettings()
            config = settings.get_connection_config()
            assert config["host"] == "test.host"
            assert config["port"] == 7496

    def test_get_chunk_size_returns_known_bar_sizes(self):
        """get_chunk_size() should return correct values for known bar sizes."""
        settings = IBSettings()
        assert settings.get_chunk_size("1 min") == 1
        assert settings.get_chunk_size("1 day") == 365
        assert settings.get_chunk_size("5 mins") == 7

    def test_get_chunk_size_returns_default_for_unknown(self):
        """get_chunk_size() should return 1 for unknown bar sizes."""
        settings = IBSettings()
        assert settings.get_chunk_size("unknown") == 1

    def test_is_paper_trading_port_4002(self):
        """is_paper_trading() should return True for port 4002."""
        settings = IBSettings()  # Default port is 4002
        assert settings.is_paper_trading() is True

    def test_is_paper_trading_port_7497(self):
        """is_paper_trading() should return True for port 7497 (TWS paper)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "7497"}, clear=False):
            settings = IBSettings()
            assert settings.is_paper_trading() is True

    def test_is_paper_trading_port_4001(self):
        """is_paper_trading() should return False for port 4001 (live)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "4001"}, clear=False):
            settings = IBSettings()
            assert settings.is_paper_trading() is False

    def test_is_live_trading_port_4001(self):
        """is_live_trading() should return True for port 4001 (live gateway)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "4001"}, clear=False):
            settings = IBSettings()
            assert settings.is_live_trading() is True

    def test_is_live_trading_port_7496(self):
        """is_live_trading() should return True for port 7496 (live TWS)."""
        with patch.dict(os.environ, {"KTRDR_IB_PORT": "7496"}, clear=False):
            settings = IBSettings()
            assert settings.is_live_trading() is True

    def test_is_live_trading_port_4002(self):
        """is_live_trading() should return False for port 4002 (paper)."""
        settings = IBSettings()  # Default port is 4002
        assert settings.is_live_trading() is False

    def test_to_dict_returns_all_fields(self):
        """to_dict() should return a dict with all fields."""
        settings = IBSettings()
        data = settings.to_dict()
        assert isinstance(data, dict)
        assert "host" in data
        assert "port" in data
        assert "client_id" in data
        assert "timeout" in data
        assert "readonly" in data
        assert "rate_limit" in data
        assert "rate_period" in data
        assert "max_retries" in data
        assert "retry_base_delay" in data
        assert "retry_max_delay" in data
        assert "pacing_delay" in data
        assert "max_requests_per_10min" in data
        assert "is_paper" in data
        assert "is_live" in data


class TestGetIBSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_ib_settings_instance(self):
        """get_ib_settings() should return an IBSettings instance."""
        settings = get_ib_settings()
        assert isinstance(settings, IBSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_ib_settings()
        settings2 = get_ib_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_ib_settings()
        clear_settings_cache()
        settings2 = get_ib_settings()
        assert settings1 is not settings2


class TestClearSettingsCache:
    """Test that clear_settings_cache() clears the IB settings cache."""

    def test_clear_settings_cache_clears_ib_cache(self):
        """clear_settings_cache() should clear get_ib_settings cache."""
        # Get initial instance
        settings1 = get_ib_settings()

        # Clear cache
        clear_settings_cache()

        # Get new instance - should be different object
        settings2 = get_ib_settings()
        assert settings1 is not settings2
