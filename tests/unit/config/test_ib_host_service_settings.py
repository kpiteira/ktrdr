"""
Unit tests for IBHostServiceSettings configuration.

Tests verify:
- IBHostServiceSettings loads defaults correctly
- New env var names (KTRDR_IB_HOST_*) work
- Old env var name (USE_IB_HOST_SERVICE) works with deprecation support
- New names take precedence when both are set
- Computed base_url property works correctly
- Helper methods work correctly
- Cached getter function works correctly
- clear_settings_cache() causes new instance on next call
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    IBHostServiceSettings,
    clear_settings_cache,
    get_ib_host_service_settings,
)


class TestIBHostServiceSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_host_is_localhost(self):
        """Default IB host service host should be localhost."""
        # Clear any env vars that could interfere
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.host == "localhost"

    def test_default_port_is_5001(self):
        """Default IB host service port should be 5001."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.port == 5001

    def test_default_enabled_is_false(self):
        """Default IB host service enabled should be False."""
        # Clear any env vars (like USE_IB_HOST_SERVICE) that could interfere
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.enabled is False

    def test_default_timeout_is_30(self):
        """Default IB host service timeout should be 30.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.timeout == 30.0

    def test_default_health_check_interval_is_10(self):
        """Default health check interval should be 10.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.health_check_interval == 10.0

    def test_default_max_retries_is_3(self):
        """Default max retries should be 3."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.max_retries == 3

    def test_default_retry_delay_is_1(self):
        """Default retry delay should be 1.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.retry_delay == 1.0


class TestIBHostServiceSettingsNewEnvVars:
    """Test new KTRDR_IB_HOST_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_ib_host_host_overrides_default(self):
        """KTRDR_IB_HOST_HOST environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_IB_HOST_HOST": "ib-host.local"}, clear=False
        ):
            settings = IBHostServiceSettings()
            assert settings.host == "ib-host.local"

    def test_ktrdr_ib_host_port_overrides_default(self):
        """KTRDR_IB_HOST_PORT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_PORT": "5002"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.port == 5002

    def test_ktrdr_ib_host_enabled_overrides_default(self):
        """KTRDR_IB_HOST_ENABLED environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_ENABLED": "true"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.enabled is True

    def test_ktrdr_ib_host_timeout_overrides_default(self):
        """KTRDR_IB_HOST_TIMEOUT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_TIMEOUT": "60.0"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.timeout == 60.0

    def test_ktrdr_ib_host_max_retries_overrides_default(self):
        """KTRDR_IB_HOST_MAX_RETRIES environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_MAX_RETRIES": "5"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.max_retries == 5


class TestIBHostServiceSettingsDeprecatedEnvVars:
    """Test deprecated USE_IB_HOST_SERVICE environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_use_ib_host_service_deprecated_still_works(self):
        """USE_IB_HOST_SERVICE (deprecated) should still override default."""
        with patch.dict(os.environ, {"USE_IB_HOST_SERVICE": "true"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.enabled is True

    def test_use_ib_host_service_false_works(self):
        """USE_IB_HOST_SERVICE=false should work."""
        with patch.dict(os.environ, {"USE_IB_HOST_SERVICE": "false"}, clear=False):
            settings = IBHostServiceSettings()
            assert settings.enabled is False


class TestIBHostServiceSettingsPrecedence:
    """Test that new env vars take precedence over deprecated ones."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_ib_host_enabled_takes_precedence_over_use_ib_host_service(self):
        """KTRDR_IB_HOST_ENABLED should take precedence over USE_IB_HOST_SERVICE."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST_ENABLED": "false", "USE_IB_HOST_SERVICE": "true"},
            clear=False,
        ):
            settings = IBHostServiceSettings()
            assert settings.enabled is False


class TestIBHostServiceSettingsValidation:
    """Test validation of configuration values."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_port_type_raises_validation_error(self):
        """KTRDR_IB_HOST_PORT=abc should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_PORT": "abc"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBHostServiceSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_port_range_low_raises_validation_error(self):
        """KTRDR_IB_HOST_PORT=0 should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_PORT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBHostServiceSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_timeout_zero_raises_validation_error(self):
        """KTRDR_IB_HOST_TIMEOUT=0 should raise ValidationError (must be positive)."""
        with patch.dict(os.environ, {"KTRDR_IB_HOST_TIMEOUT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                IBHostServiceSettings()
            assert "timeout" in str(exc_info.value).lower()


class TestIBHostServiceSettingsComputedProperties:
    """Test computed properties on IBHostServiceSettings."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_base_url_computed_from_host_port(self):
        """base_url should be computed from host and port."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.base_url == "http://localhost:5001"

    def test_base_url_uses_custom_host_port(self):
        """base_url should use configured host and port."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST_HOST": "ib.example.com", "KTRDR_IB_HOST_PORT": "5002"},
            clear=False,
        ):
            settings = IBHostServiceSettings()
            assert settings.base_url == "http://ib.example.com:5002"


class TestIBHostServiceSettingsHelperMethods:
    """Test helper methods on IBHostServiceSettings."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_get_health_url_returns_health_endpoint(self):
        """get_health_url() should return the health endpoint URL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert settings.get_health_url() == "http://localhost:5001/health"

    def test_get_health_url_with_custom_host_port(self):
        """get_health_url() should use custom host and port."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST_HOST": "ib.example.com", "KTRDR_IB_HOST_PORT": "5002"},
            clear=True,
        ):
            settings = IBHostServiceSettings()
            assert settings.get_health_url() == "http://ib.example.com:5002/health"

    def test_get_detailed_health_url_returns_detailed_endpoint(self):
        """get_detailed_health_url() should return the detailed health endpoint URL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = IBHostServiceSettings()
            assert (
                settings.get_detailed_health_url()
                == "http://localhost:5001/health/detailed"
            )


class TestGetIBHostServiceSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_ib_host_service_settings_instance(self):
        """get_ib_host_service_settings() should return an IBHostServiceSettings instance."""
        settings = get_ib_host_service_settings()
        assert isinstance(settings, IBHostServiceSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_ib_host_service_settings()
        settings2 = get_ib_host_service_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_ib_host_service_settings()
        clear_settings_cache()
        settings2 = get_ib_host_service_settings()
        assert settings1 is not settings2


class TestClearSettingsCache:
    """Test that clear_settings_cache() clears the IB host service settings cache."""

    def test_clear_settings_cache_clears_ib_host_service_cache(self):
        """clear_settings_cache() should clear get_ib_host_service_settings cache."""
        # Get initial instance
        settings1 = get_ib_host_service_settings()

        # Clear cache
        clear_settings_cache()

        # Get new instance - should be different object
        settings2 = get_ib_host_service_settings()
        assert settings1 is not settings2
