"""
Tests for ApiServiceSettings in the unified settings module.

These tests verify that ApiServiceSettings works correctly after being
moved from host_services.py to settings.py as part of Task 3.5.
"""

import os
from unittest.mock import patch

import pytest


class TestApiServiceSettings:
    """Tests for the ApiServiceSettings class."""

    def test_default_base_url(self):
        """ApiServiceSettings loads default base_url."""
        with patch.dict(os.environ, {}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings, clear_settings_cache

            clear_settings_cache()

            settings = ApiServiceSettings()
            # Default comes from metadata
            assert "localhost:8000" in settings.base_url
            assert "/api/v1" in settings.base_url

    def test_default_enabled_is_true(self):
        """API service is always enabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings

            settings = ApiServiceSettings()
            assert settings.enabled is True

    def test_default_timeout(self):
        """ApiServiceSettings has reasonable default timeout."""
        with patch.dict(os.environ, {}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings

            settings = ApiServiceSettings()
            assert settings.timeout == 30.0

    def test_env_var_override_base_url(self):
        """KTRDR_API_CLIENT_BASE_URL overrides default."""
        custom_url = "http://custom-api:9000/api/v1"
        with patch.dict(os.environ, {"api_base_url": custom_url}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings, clear_settings_cache

            clear_settings_cache()
            settings = ApiServiceSettings()
            assert settings.base_url == custom_url

    def test_env_var_override_timeout(self):
        """KTRDR_API_CLIENT_TIMEOUT overrides default."""
        with patch.dict(os.environ, {"KTRDR_API_CLIENT_TIMEOUT": "60.0"}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings, clear_settings_cache

            clear_settings_cache()
            settings = ApiServiceSettings()
            assert settings.timeout == 60.0

    def test_get_health_url(self):
        """get_health_url returns proper API health endpoint."""
        with patch.dict(os.environ, {}, clear=True):
            from ktrdr.config.settings import ApiServiceSettings

            settings = ApiServiceSettings()
            health_url = settings.get_health_url()
            assert "/system/health" in health_url


class TestGetApiServiceSettings:
    """Tests for the get_api_service_settings cached getter."""

    def test_returns_api_service_settings(self):
        """get_api_service_settings returns ApiServiceSettings instance."""
        from ktrdr.config.settings import ApiServiceSettings, get_api_service_settings

        settings = get_api_service_settings()
        assert isinstance(settings, ApiServiceSettings)

    def test_is_cached(self):
        """get_api_service_settings returns same instance on multiple calls."""
        from ktrdr.config.settings import get_api_service_settings

        settings1 = get_api_service_settings()
        settings2 = get_api_service_settings()
        assert settings1 is settings2


class TestGetApiBaseUrl:
    """Tests for the get_api_base_url convenience function."""

    def test_returns_base_url(self):
        """get_api_base_url returns the base URL string."""
        from ktrdr.config.settings import get_api_base_url

        url = get_api_base_url()
        assert isinstance(url, str)
        assert "localhost" in url or "http" in url


class TestHostServicesDeleted:
    """Tests that host_services.py has been deleted."""

    def test_host_services_module_not_importable(self):
        """ktrdr.config.host_services should not exist after migration."""
        with pytest.raises(ImportError):
            import ktrdr.config.host_services  # noqa: F401

    def test_old_ib_host_service_settings_not_importable(self):
        """Old IbHostServiceSettings from host_services.py should not exist."""
        with pytest.raises(ImportError):
            from ktrdr.config.host_services import IbHostServiceSettings  # noqa: F401

    def test_old_host_service_settings_base_not_importable(self):
        """Old HostServiceSettings base class should not exist."""
        with pytest.raises(ImportError):
            from ktrdr.config.host_services import HostServiceSettings  # noqa: F401


class TestCLICompatibility:
    """Tests that CLI modules can still access API settings."""

    def test_cli_sandbox_detect_can_get_api_url(self):
        """sandbox_detect module can get API base URL."""
        from ktrdr.cli.sandbox_detect import get_effective_api_url

        url = get_effective_api_url()
        assert isinstance(url, str)
        assert "localhost" in url or "http" in url

    def test_cli_client_core_can_resolve_url(self):
        """client/core module can resolve URL."""
        from ktrdr.cli.client.core import resolve_url

        url = resolve_url()
        assert isinstance(url, str)
        assert "localhost" in url or "http" in url
