"""Tests for APIClientSettings (ApiServiceSettings).

Note: The class is called ApiServiceSettings but we're testing it as
API Client Settings per milestone M5.4 requirements.
"""

import pytest

from ktrdr.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestAPIClientSettingsDefaults:
    """Test APIClientSettings default values."""

    def test_default_base_url(self):
        """Base URL should default to http://localhost:8000/api/v1."""
        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.base_url == "http://localhost:8000/api/v1"

    def test_default_timeout(self):
        """Timeout should default to 30.0 seconds."""
        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.timeout == 30.0

    def test_default_max_retries(self):
        """Max retries should default to 3."""
        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.max_retries == 3

    def test_default_retry_delay(self):
        """Retry delay should default to 1.0 second."""
        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.retry_delay == 1.0


class TestAPIClientSettingsEnvVars:
    """Test APIClientSettings with KTRDR_API_CLIENT_* env vars."""

    def test_base_url_from_env(self, monkeypatch):
        """Should read base_url from KTRDR_API_CLIENT_BASE_URL."""
        monkeypatch.setenv("KTRDR_API_CLIENT_BASE_URL", "http://example.com/api/v1")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.base_url == "http://example.com/api/v1"

    def test_timeout_from_env(self, monkeypatch):
        """Should read timeout from KTRDR_API_CLIENT_TIMEOUT."""
        monkeypatch.setenv("KTRDR_API_CLIENT_TIMEOUT", "60.0")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.timeout == 60.0

    def test_max_retries_from_env(self, monkeypatch):
        """Should read max_retries from KTRDR_API_CLIENT_MAX_RETRIES."""
        monkeypatch.setenv("KTRDR_API_CLIENT_MAX_RETRIES", "5")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.max_retries == 5

    def test_retry_delay_from_env(self, monkeypatch):
        """Should read retry_delay from KTRDR_API_CLIENT_RETRY_DELAY."""
        monkeypatch.setenv("KTRDR_API_CLIENT_RETRY_DELAY", "2.5")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.retry_delay == 2.5


class TestAPIClientSettingsDeprecatedNames:
    """Test APIClientSettings with deprecated KTRDR_API_URL env var."""

    def test_deprecated_api_url(self, monkeypatch):
        """Deprecated KTRDR_API_URL should still work for base_url.

        This resolves duplication #5 from the config audit.
        """
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.base_url == "http://backend:8000"


class TestAPIClientSettingsPrecedence:
    """Test that new names take precedence over deprecated names."""

    def test_new_name_takes_precedence(self, monkeypatch):
        """KTRDR_API_CLIENT_BASE_URL should take precedence over KTRDR_API_URL."""
        monkeypatch.setenv("KTRDR_API_CLIENT_BASE_URL", "http://new.url/api/v1")
        monkeypatch.setenv("KTRDR_API_URL", "http://old.url")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.base_url == "http://new.url/api/v1"


class TestAPIClientSettingsValidation:
    """Test APIClientSettings validation."""

    def test_timeout_must_be_positive(self, monkeypatch):
        """Timeout must be > 0."""
        monkeypatch.setenv("KTRDR_API_CLIENT_TIMEOUT", "0")

        from ktrdr.config.settings import get_api_service_settings

        with pytest.raises(Exception) as exc_info:
            get_api_service_settings()
        assert "greater than 0" in str(exc_info.value)

    def test_max_retries_cannot_be_negative(self, monkeypatch):
        """Max retries must be >= 0."""
        monkeypatch.setenv("KTRDR_API_CLIENT_MAX_RETRIES", "-1")

        from ktrdr.config.settings import get_api_service_settings

        with pytest.raises(Exception) as exc_info:
            get_api_service_settings()
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_retry_delay_cannot_be_negative(self, monkeypatch):
        """Retry delay must be >= 0."""
        monkeypatch.setenv("KTRDR_API_CLIENT_RETRY_DELAY", "-1")

        from ktrdr.config.settings import get_api_service_settings

        with pytest.raises(Exception) as exc_info:
            get_api_service_settings()
        assert "greater than or equal to 0" in str(exc_info.value)


class TestAPIClientSettingsGetter:
    """Test get_api_service_settings() caching behavior."""

    def test_getter_returns_same_instance(self):
        """get_api_service_settings() should return cached instance."""
        from ktrdr.config.settings import get_api_service_settings

        settings1 = get_api_service_settings()
        settings2 = get_api_service_settings()
        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """clear_settings_cache() should clear the api service settings cache."""
        from ktrdr.config.settings import get_api_service_settings

        settings1 = get_api_service_settings()
        clear_settings_cache()
        settings2 = get_api_service_settings()
        assert settings1 is not settings2

    def test_get_api_base_url_convenience(self):
        """get_api_base_url() should return the base_url value."""
        from ktrdr.config.settings import get_api_base_url, get_api_service_settings

        assert get_api_base_url() == get_api_service_settings().base_url


class TestAPIClientSettingsHelpers:
    """Test APIClientSettings helper methods."""

    def test_get_health_url(self):
        """get_health_url() should return the health endpoint."""
        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.get_health_url() == "http://localhost:8000/api/v1/system/health"

    def test_get_health_url_strips_trailing_slash(self, monkeypatch):
        """get_health_url() should handle trailing slashes."""
        monkeypatch.setenv("KTRDR_API_CLIENT_BASE_URL", "http://example.com/api/v1/")

        from ktrdr.config.settings import get_api_service_settings

        settings = get_api_service_settings()
        assert settings.get_health_url() == "http://example.com/api/v1/system/health"
