"""
Unit tests for TrainingHostServiceSettings configuration.

Tests verify:
- TrainingHostServiceSettings loads defaults correctly
- New env var names (KTRDR_TRAINING_HOST_*) work
- Old env var names (USE_TRAINING_HOST_SERVICE, TRAINING_HOST_SERVICE_URL) work with deprecation support
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
    TrainingHostServiceSettings,
    clear_settings_cache,
    get_training_host_service_settings,
)


class TestTrainingHostServiceSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_host_is_localhost(self):
        """Default training host service host should be localhost."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.host == "localhost"

    def test_default_port_is_5002(self):
        """Default training host service port should be 5002."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.port == 5002

    def test_default_enabled_is_false(self):
        """Default training host service enabled should be False."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.enabled is False

    def test_default_timeout_is_30(self):
        """Default training host service timeout should be 30.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.timeout == 30.0

    def test_default_health_check_interval_is_10(self):
        """Default health check interval should be 10.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.health_check_interval == 10.0

    def test_default_max_retries_is_3(self):
        """Default max retries should be 3."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.max_retries == 3

    def test_default_retry_delay_is_1(self):
        """Default retry delay should be 1.0 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.retry_delay == 1.0


class TestTrainingHostServiceSettingsNewEnvVars:
    """Test new KTRDR_TRAINING_HOST_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_training_host_host_overrides_default(self):
        """KTRDR_TRAINING_HOST_HOST environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_TRAINING_HOST_HOST": "training-host.local"}, clear=False
        ):
            settings = TrainingHostServiceSettings()
            assert settings.host == "training-host.local"

    def test_ktrdr_training_host_port_overrides_default(self):
        """KTRDR_TRAINING_HOST_PORT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_TRAINING_HOST_PORT": "5003"}, clear=False):
            settings = TrainingHostServiceSettings()
            assert settings.port == 5003

    def test_ktrdr_training_host_enabled_overrides_default(self):
        """KTRDR_TRAINING_HOST_ENABLED environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_TRAINING_HOST_ENABLED": "true"}, clear=False
        ):
            settings = TrainingHostServiceSettings()
            assert settings.enabled is True

    def test_ktrdr_training_host_timeout_overrides_default(self):
        """KTRDR_TRAINING_HOST_TIMEOUT environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_TRAINING_HOST_TIMEOUT": "60.0"}, clear=False
        ):
            settings = TrainingHostServiceSettings()
            assert settings.timeout == 60.0

    def test_ktrdr_training_host_max_retries_overrides_default(self):
        """KTRDR_TRAINING_HOST_MAX_RETRIES environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_TRAINING_HOST_MAX_RETRIES": "5"}, clear=False
        ):
            settings = TrainingHostServiceSettings()
            assert settings.max_retries == 5


class TestTrainingHostServiceSettingsDeprecatedEnvVars:
    """Test deprecated USE_TRAINING_HOST_SERVICE environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_use_training_host_service_deprecated_still_works(self):
        """USE_TRAINING_HOST_SERVICE (deprecated) should still override default."""
        with patch.dict(os.environ, {"USE_TRAINING_HOST_SERVICE": "true"}, clear=False):
            settings = TrainingHostServiceSettings()
            assert settings.enabled is True

    def test_use_training_host_service_false_works(self):
        """USE_TRAINING_HOST_SERVICE=false should work."""
        with patch.dict(
            os.environ, {"USE_TRAINING_HOST_SERVICE": "false"}, clear=False
        ):
            settings = TrainingHostServiceSettings()
            assert settings.enabled is False


class TestTrainingHostServiceSettingsPrecedence:
    """Test that new env vars take precedence over deprecated ones."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_training_host_enabled_takes_precedence_over_use_training_host_service(
        self,
    ):
        """KTRDR_TRAINING_HOST_ENABLED should take precedence over USE_TRAINING_HOST_SERVICE."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_TRAINING_HOST_ENABLED": "false",
                "USE_TRAINING_HOST_SERVICE": "true",
            },
            clear=False,
        ):
            settings = TrainingHostServiceSettings()
            assert settings.enabled is False


class TestTrainingHostServiceSettingsValidation:
    """Test validation of configuration values."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_port_type_raises_validation_error(self):
        """KTRDR_TRAINING_HOST_PORT=abc should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_TRAINING_HOST_PORT": "abc"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                TrainingHostServiceSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_port_range_low_raises_validation_error(self):
        """KTRDR_TRAINING_HOST_PORT=0 should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_TRAINING_HOST_PORT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                TrainingHostServiceSettings()
            assert "port" in str(exc_info.value).lower()

    def test_invalid_timeout_zero_raises_validation_error(self):
        """KTRDR_TRAINING_HOST_TIMEOUT=0 should raise ValidationError (must be positive)."""
        with patch.dict(os.environ, {"KTRDR_TRAINING_HOST_TIMEOUT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                TrainingHostServiceSettings()
            assert "timeout" in str(exc_info.value).lower()


class TestTrainingHostServiceSettingsComputedProperties:
    """Test computed properties on TrainingHostServiceSettings."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_base_url_computed_from_host_port(self):
        """base_url should be computed from host and port."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.base_url == "http://localhost:5002"

    def test_base_url_uses_custom_host_port(self):
        """base_url should use configured host and port."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_TRAINING_HOST_HOST": "training.example.com",
                "KTRDR_TRAINING_HOST_PORT": "5003",
            },
            clear=False,
        ):
            settings = TrainingHostServiceSettings()
            assert settings.base_url == "http://training.example.com:5003"


class TestTrainingHostServiceSettingsHelperMethods:
    """Test helper methods on TrainingHostServiceSettings."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_get_health_url_returns_health_endpoint(self):
        """get_health_url() should return the health endpoint URL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert settings.get_health_url() == "http://localhost:5002/health"

    def test_get_health_url_with_custom_host_port(self):
        """get_health_url() should use custom host and port."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_TRAINING_HOST_HOST": "training.example.com",
                "KTRDR_TRAINING_HOST_PORT": "5003",
            },
            clear=True,
        ):
            settings = TrainingHostServiceSettings()
            assert (
                settings.get_health_url() == "http://training.example.com:5003/health"
            )

    def test_get_detailed_health_url_returns_detailed_endpoint(self):
        """get_detailed_health_url() should return the detailed health endpoint URL."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TrainingHostServiceSettings()
            assert (
                settings.get_detailed_health_url()
                == "http://localhost:5002/health/detailed"
            )


class TestGetTrainingHostServiceSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_training_host_service_settings_instance(self):
        """get_training_host_service_settings() should return a TrainingHostServiceSettings instance."""
        settings = get_training_host_service_settings()
        assert isinstance(settings, TrainingHostServiceSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_training_host_service_settings()
        settings2 = get_training_host_service_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_training_host_service_settings()
        clear_settings_cache()
        settings2 = get_training_host_service_settings()
        assert settings1 is not settings2


class TestClearSettingsCacheTrainingHost:
    """Test that clear_settings_cache() clears the training host service settings cache."""

    def test_clear_settings_cache_clears_training_host_service_cache(self):
        """clear_settings_cache() should clear get_training_host_service_settings cache."""
        # Get initial instance
        settings1 = get_training_host_service_settings()

        # Clear cache
        clear_settings_cache()

        # Get new instance - should be different object
        settings2 = get_training_host_service_settings()
        assert settings1 is not settings2
