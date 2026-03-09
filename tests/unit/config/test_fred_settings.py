"""Tests for FredSettings."""

import pytest
from pydantic import ValidationError

from ktrdr.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestFredSettingsDefaults:
    """Test FredSettings default values."""

    def test_default_api_key_empty(self, monkeypatch):
        """API key should default to empty string (not required at load time)."""
        monkeypatch.delenv("KTRDR_FRED_API_KEY", raising=False)
        monkeypatch.delenv("FRED_API_KEY", raising=False)

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.api_key == ""

    def test_default_base_url(self):
        """Base URL should default to FRED API endpoint."""
        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert (
            settings.base_url == "https://api.stlouisfed.org/fred/series/observations"
        )

    def test_default_rate_limit(self):
        """Rate limit should default to 120 requests per minute."""
        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.rate_limit == 120

    def test_default_cache_dir(self):
        """Cache dir should default to data/context/fred."""
        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.cache_dir == "data/context/fred"


class TestFredSettingsEnvVars:
    """Test FredSettings reads from environment variables."""

    def test_api_key_from_new_env(self, monkeypatch):
        """Should read API key from KTRDR_FRED_API_KEY."""
        monkeypatch.setenv("KTRDR_FRED_API_KEY", "test-key-123")

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.api_key == "test-key-123"

    def test_api_key_from_deprecated_env(self, monkeypatch):
        """Should read API key from deprecated FRED_API_KEY."""
        monkeypatch.delenv("KTRDR_FRED_API_KEY", raising=False)
        monkeypatch.setenv("FRED_API_KEY", "old-key-456")

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.api_key == "old-key-456"

    def test_new_env_takes_precedence(self, monkeypatch):
        """KTRDR_FRED_API_KEY should take precedence over FRED_API_KEY."""
        monkeypatch.setenv("KTRDR_FRED_API_KEY", "new-key")
        monkeypatch.setenv("FRED_API_KEY", "old-key")

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.api_key == "new-key"

    def test_rate_limit_from_env(self, monkeypatch):
        """Should read rate limit from KTRDR_FRED_RATE_LIMIT."""
        monkeypatch.setenv("KTRDR_FRED_RATE_LIMIT", "60")

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.rate_limit == 60


class TestFredSettingsValidation:
    """Test FredSettings validation helpers."""

    def test_has_api_key_false_when_empty(self, monkeypatch):
        """has_api_key should be False when key is empty."""
        monkeypatch.delenv("KTRDR_FRED_API_KEY", raising=False)
        monkeypatch.delenv("FRED_API_KEY", raising=False)

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.has_api_key is False

    def test_has_api_key_true_when_set(self, monkeypatch):
        """has_api_key should be True when key is non-empty."""
        monkeypatch.setenv("KTRDR_FRED_API_KEY", "some-key")

        from ktrdr.config.settings import get_fred_settings

        settings = get_fred_settings()
        assert settings.has_api_key is True

    def test_rate_limit_must_be_positive(self, monkeypatch):
        """Rate limit must be > 0."""
        monkeypatch.setenv("KTRDR_FRED_RATE_LIMIT", "0")

        from ktrdr.config.settings import get_fred_settings

        with pytest.raises(ValidationError):
            get_fred_settings()


class TestFredSettingsGetter:
    """Test get_fred_settings() caching behavior."""

    def test_getter_returns_same_instance(self):
        """get_fred_settings() should return cached instance."""
        from ktrdr.config.settings import get_fred_settings

        settings1 = get_fred_settings()
        settings2 = get_fred_settings()
        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """clear_settings_cache() should clear the fred settings cache."""
        from ktrdr.config.settings import get_fred_settings

        settings1 = get_fred_settings()
        clear_settings_cache()
        settings2 = get_fred_settings()
        assert settings1 is not settings2
