"""
Unit tests for ObservabilitySettings configuration.

Tests verify:
- ObservabilitySettings loads defaults correctly
- KTRDR_OTEL_* env vars override defaults
- Deprecated OTLP_ENDPOINT env var still works
- get_observability_settings() caching works
"""

import os
from unittest.mock import patch

from ktrdr.config.settings import (
    ObservabilitySettings,
    clear_settings_cache,
    get_observability_settings,
)


class TestObservabilitySettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_enabled(self):
        """Default enabled should be True."""
        settings = ObservabilitySettings()
        assert settings.enabled is True

    def test_default_otlp_endpoint(self):
        """Default OTLP endpoint should be http://jaeger:4317."""
        settings = ObservabilitySettings()
        assert settings.otlp_endpoint == "http://jaeger:4317"

    def test_default_service_name(self):
        """Default service name should be ktrdr."""
        settings = ObservabilitySettings()
        assert settings.service_name == "ktrdr"

    def test_default_console_output(self):
        """Default console_output should be False."""
        settings = ObservabilitySettings()
        assert settings.console_output is False


class TestObservabilitySettingsEnvOverrides:
    """Test environment variable overrides."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_otel_enabled_overrides_default(self):
        """KTRDR_OTEL_ENABLED should override default."""
        with patch.dict(os.environ, {"KTRDR_OTEL_ENABLED": "false"}, clear=False):
            settings = ObservabilitySettings()
            assert settings.enabled is False

    def test_ktrdr_otel_otlp_endpoint_overrides_default(self):
        """KTRDR_OTEL_OTLP_ENDPOINT should override default."""
        with patch.dict(
            os.environ,
            {"KTRDR_OTEL_OTLP_ENDPOINT": "http://custom:4317"},
            clear=False,
        ):
            settings = ObservabilitySettings()
            assert settings.otlp_endpoint == "http://custom:4317"

    def test_ktrdr_otel_service_name_overrides_default(self):
        """KTRDR_OTEL_SERVICE_NAME should override default."""
        with patch.dict(
            os.environ, {"KTRDR_OTEL_SERVICE_NAME": "my-service"}, clear=False
        ):
            settings = ObservabilitySettings()
            assert settings.service_name == "my-service"

    def test_ktrdr_otel_console_output_overrides_default(self):
        """KTRDR_OTEL_CONSOLE_OUTPUT should override default."""
        with patch.dict(os.environ, {"KTRDR_OTEL_CONSOLE_OUTPUT": "true"}, clear=False):
            settings = ObservabilitySettings()
            assert settings.console_output is True


class TestObservabilitySettingsDeprecatedNames:
    """Test deprecated environment variable name support."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_deprecated_otlp_endpoint_still_works(self):
        """Deprecated OTLP_ENDPOINT should still work."""
        with patch.dict(
            os.environ, {"OTLP_ENDPOINT": "http://legacy:4317"}, clear=False
        ):
            settings = ObservabilitySettings()
            assert settings.otlp_endpoint == "http://legacy:4317"

    def test_new_name_takes_precedence(self):
        """New env var name should take precedence over deprecated."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_OTEL_OTLP_ENDPOINT": "http://new:4317",
                "OTLP_ENDPOINT": "http://legacy:4317",
            },
            clear=False,
        ):
            settings = ObservabilitySettings()
            assert settings.otlp_endpoint == "http://new:4317"


class TestGetObservabilitySettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_observability_settings_instance(self):
        """get_observability_settings() should return an ObservabilitySettings instance."""
        settings = get_observability_settings()
        assert isinstance(settings, ObservabilitySettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_observability_settings()
        settings2 = get_observability_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_observability_settings()
        clear_settings_cache()
        settings2 = get_observability_settings()
        assert settings1 is not settings2
