"""
Unit tests for APISettings configuration.

Tests verify:
- APISettings loads defaults correctly
- KTRDR_API_* env vars override defaults
- CORS settings parse comma-separated strings
- Environment and log_level validation works
- get_api_settings() caching works
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    APISettings,
    clear_settings_cache,
    get_api_settings,
)


class TestAPISettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_host(self):
        """Default API host should be 127.0.0.1."""
        settings = APISettings()
        assert settings.host == "127.0.0.1"

    def test_default_port(self):
        """Default API port should be 8000."""
        settings = APISettings()
        assert settings.port == 8000

    def test_default_environment(self):
        """Default environment should be development."""
        settings = APISettings()
        assert settings.environment == "development"

    def test_default_log_level(self):
        """Default log_level should be INFO."""
        settings = APISettings()
        assert settings.log_level == "INFO"

    def test_default_cors_origins(self):
        """Default CORS origins should be ['*']."""
        settings = APISettings()
        assert settings.cors_origins == ["*"]

    def test_default_cors_allow_credentials(self):
        """Default cors_allow_credentials should be True."""
        settings = APISettings()
        assert settings.cors_allow_credentials is True

    def test_default_cors_allow_methods(self):
        """Default cors_allow_methods should be ['*']."""
        settings = APISettings()
        assert settings.cors_allow_methods == ["*"]

    def test_default_cors_allow_headers(self):
        """Default cors_allow_headers should be ['*']."""
        settings = APISettings()
        assert settings.cors_allow_headers == ["*"]

    def test_default_cors_max_age(self):
        """Default cors_max_age should be 600."""
        settings = APISettings()
        assert settings.cors_max_age == 600

    def test_default_api_prefix(self):
        """Default api_prefix should be /api/v1."""
        settings = APISettings()
        assert settings.api_prefix == "/api/v1"


class TestAPISettingsEnvOverrides:
    """Test environment variable overrides."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_api_port_overrides_default(self):
        """KTRDR_API_PORT should override default."""
        with patch.dict(os.environ, {"KTRDR_API_PORT": "9000"}, clear=False):
            settings = APISettings()
            assert settings.port == 9000

    def test_ktrdr_api_host_overrides_default(self):
        """KTRDR_API_HOST should override default."""
        with patch.dict(os.environ, {"KTRDR_API_HOST": "0.0.0.0"}, clear=False):
            settings = APISettings()
            assert settings.host == "0.0.0.0"

    def test_ktrdr_api_environment_overrides_default(self):
        """KTRDR_API_ENVIRONMENT should override default."""
        with patch.dict(
            os.environ, {"KTRDR_API_ENVIRONMENT": "production"}, clear=False
        ):
            settings = APISettings()
            assert settings.environment == "production"

    def test_ktrdr_api_log_level_overrides_default(self):
        """KTRDR_API_LOG_LEVEL should override default."""
        with patch.dict(os.environ, {"KTRDR_API_LOG_LEVEL": "DEBUG"}, clear=False):
            settings = APISettings()
            assert settings.log_level == "DEBUG"

    def test_ktrdr_api_cors_max_age_overrides_default(self):
        """KTRDR_API_CORS_MAX_AGE should override default."""
        with patch.dict(os.environ, {"KTRDR_API_CORS_MAX_AGE": "3600"}, clear=False):
            settings = APISettings()
            assert settings.cors_max_age == 3600


class TestAPISettingsCORSFromEnv:
    """Test CORS list fields from environment variables.

    pydantic-settings expects JSON arrays for list fields from env vars.
    """

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_cors_origins_from_json_array(self):
        """CORS origins should parse JSON array from env."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_API_CORS_ORIGINS": '["http://localhost:3000","http://localhost:8080"]'
            },
            clear=False,
        ):
            settings = APISettings()
            assert settings.cors_origins == [
                "http://localhost:3000",
                "http://localhost:8080",
            ]

    def test_cors_allow_methods_from_json_array(self):
        """CORS methods should parse JSON array from env."""
        with patch.dict(
            os.environ,
            {"KTRDR_API_CORS_ALLOW_METHODS": '["GET","POST","PUT"]'},
            clear=False,
        ):
            settings = APISettings()
            assert settings.cors_allow_methods == ["GET", "POST", "PUT"]

    def test_cors_allow_headers_from_json_array(self):
        """CORS headers should parse JSON array from env."""
        with patch.dict(
            os.environ,
            {"KTRDR_API_CORS_ALLOW_HEADERS": '["Content-Type","Authorization"]'},
            clear=False,
        ):
            settings = APISettings()
            assert settings.cors_allow_headers == ["Content-Type", "Authorization"]

    def test_cors_origins_single_value_as_json(self):
        """Single CORS origin works as JSON array."""
        with patch.dict(
            os.environ,
            {"KTRDR_API_CORS_ORIGINS": '["http://localhost:3000"]'},
            clear=False,
        ):
            settings = APISettings()
            assert settings.cors_origins == ["http://localhost:3000"]


class TestAPISettingsValidation:
    """Test field validation."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_environment_raises_error(self):
        """Invalid environment value should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_API_ENVIRONMENT": "invalid"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                APISettings()
            assert "environment" in str(exc_info.value).lower()

    def test_valid_environments_accepted(self):
        """Valid environment values should be accepted."""
        for env in ["development", "staging", "production"]:
            with patch.dict(os.environ, {"KTRDR_API_ENVIRONMENT": env}, clear=False):
                settings = APISettings()
                assert settings.environment == env

    def test_environment_case_insensitive(self):
        """Environment should be case-insensitive."""
        with patch.dict(
            os.environ, {"KTRDR_API_ENVIRONMENT": "PRODUCTION"}, clear=False
        ):
            settings = APISettings()
            assert settings.environment == "production"

    def test_invalid_log_level_raises_error(self):
        """Invalid log level should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_API_LOG_LEVEL": "INVALID"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                APISettings()
            assert "log_level" in str(exc_info.value).lower()

    def test_valid_log_levels_accepted(self):
        """Valid log level values should be accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            with patch.dict(os.environ, {"KTRDR_API_LOG_LEVEL": level}, clear=False):
                settings = APISettings()
                assert settings.log_level == level

    def test_log_level_case_insensitive(self):
        """Log level should be case-insensitive."""
        with patch.dict(os.environ, {"KTRDR_API_LOG_LEVEL": "debug"}, clear=False):
            settings = APISettings()
            assert settings.log_level == "DEBUG"

    def test_invalid_port_type_raises_error(self):
        """Non-integer port should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_API_PORT": "not_a_number"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                APISettings()
            assert "port" in str(exc_info.value).lower()


class TestGetAPISettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_api_settings_instance(self):
        """get_api_settings() should return an APISettings instance."""
        settings = get_api_settings()
        assert isinstance(settings, APISettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_api_settings()
        settings2 = get_api_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_api_settings()
        clear_settings_cache()
        settings2 = get_api_settings()
        assert settings1 is not settings2
