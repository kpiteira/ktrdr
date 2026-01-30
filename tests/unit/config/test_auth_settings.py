"""
Unit tests for AuthSettings configuration.

Tests verify:
- AuthSettings loads defaults correctly
- KTRDR_AUTH_* env vars override defaults
- jwt_secret can be overridden via env var
- get_auth_settings() caching works
"""

import os
from unittest.mock import patch

from ktrdr.config.settings import (
    AuthSettings,
    clear_settings_cache,
    get_auth_settings,
)


class TestAuthSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_jwt_secret(self):
        """Default JWT secret should be 'insecure-dev-secret' (insecure for dev)."""
        settings = AuthSettings()
        assert settings.jwt_secret == "insecure-dev-secret"

    def test_default_jwt_algorithm(self):
        """Default JWT algorithm should be HS256."""
        settings = AuthSettings()
        assert settings.jwt_algorithm == "HS256"

    def test_default_token_expire_minutes(self):
        """Default token expiry should be 60 minutes."""
        settings = AuthSettings()
        assert settings.token_expire_minutes == 60


class TestAuthSettingsEnvOverrides:
    """Test environment variable overrides."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_auth_jwt_secret_overrides_default(self):
        """KTRDR_AUTH_JWT_SECRET should override default."""
        with patch.dict(
            os.environ, {"KTRDR_AUTH_JWT_SECRET": "my-secure-secret"}, clear=False
        ):
            settings = AuthSettings()
            assert settings.jwt_secret == "my-secure-secret"

    def test_ktrdr_auth_jwt_algorithm_overrides_default(self):
        """KTRDR_AUTH_JWT_ALGORITHM should override default."""
        with patch.dict(os.environ, {"KTRDR_AUTH_JWT_ALGORITHM": "HS512"}, clear=False):
            settings = AuthSettings()
            assert settings.jwt_algorithm == "HS512"

    def test_ktrdr_auth_token_expire_minutes_overrides_default(self):
        """KTRDR_AUTH_TOKEN_EXPIRE_MINUTES should override default."""
        with patch.dict(
            os.environ, {"KTRDR_AUTH_TOKEN_EXPIRE_MINUTES": "120"}, clear=False
        ):
            settings = AuthSettings()
            assert settings.token_expire_minutes == 120


class TestGetAuthSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_auth_settings_instance(self):
        """get_auth_settings() should return an AuthSettings instance."""
        settings = get_auth_settings()
        assert isinstance(settings, AuthSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_auth_settings()
        settings2 = get_auth_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_auth_settings()
        clear_settings_cache()
        settings2 = get_auth_settings()
        assert settings1 is not settings2
