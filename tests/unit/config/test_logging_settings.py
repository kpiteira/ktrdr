"""
Unit tests for LoggingSettings configuration.

Tests verify:
- LoggingSettings loads defaults correctly
- KTRDR_LOG_* env vars override defaults
- Level validation works
- get_logging_settings() caching works
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    LoggingSettings,
    clear_settings_cache,
    get_logging_settings,
)


class TestLoggingSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_level(self):
        """Default log level should be INFO."""
        settings = LoggingSettings()
        assert settings.level == "INFO"

    def test_default_format(self):
        """Default format should contain timestamp and level."""
        settings = LoggingSettings()
        assert "%(asctime)s" in settings.format
        assert "%(levelname)" in settings.format

    def test_default_json_output(self):
        """Default json_output should be False."""
        settings = LoggingSettings()
        assert settings.json_output is False


class TestLoggingSettingsEnvOverrides:
    """Test environment variable overrides."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_log_level_overrides_default(self):
        """KTRDR_LOG_LEVEL should override default."""
        with patch.dict(os.environ, {"KTRDR_LOG_LEVEL": "DEBUG"}, clear=False):
            settings = LoggingSettings()
            assert settings.level == "DEBUG"

    def test_ktrdr_log_format_overrides_default(self):
        """KTRDR_LOG_FORMAT should override default."""
        custom_format = "%(message)s"
        with patch.dict(os.environ, {"KTRDR_LOG_FORMAT": custom_format}, clear=False):
            settings = LoggingSettings()
            assert settings.format == custom_format

    def test_ktrdr_log_json_output_overrides_default(self):
        """KTRDR_LOG_JSON_OUTPUT should override default."""
        with patch.dict(os.environ, {"KTRDR_LOG_JSON_OUTPUT": "true"}, clear=False):
            settings = LoggingSettings()
            assert settings.json_output is True


class TestLoggingSettingsValidation:
    """Test field validation."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_level_raises_error(self):
        """Invalid log level should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_LOG_LEVEL": "INVALID"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                LoggingSettings()
            assert "level" in str(exc_info.value).lower()

    def test_valid_levels_accepted(self):
        """Valid log level values should be accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            with patch.dict(os.environ, {"KTRDR_LOG_LEVEL": level}, clear=False):
                settings = LoggingSettings()
                assert settings.level == level

    def test_level_case_insensitive(self):
        """Log level should be case-insensitive."""
        with patch.dict(os.environ, {"KTRDR_LOG_LEVEL": "debug"}, clear=False):
            settings = LoggingSettings()
            assert settings.level == "DEBUG"


class TestGetLoggingSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_logging_settings_instance(self):
        """get_logging_settings() should return a LoggingSettings instance."""
        settings = get_logging_settings()
        assert isinstance(settings, LoggingSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_logging_settings()
        settings2 = get_logging_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_logging_settings()
        clear_settings_cache()
        settings2 = get_logging_settings()
        assert settings1 is not settings2
