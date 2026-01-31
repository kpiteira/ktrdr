"""
Unit tests for OperationsSettings configuration.

Tests verify:
- OperationsSettings loads defaults correctly
- New env var names (KTRDR_OPS_*) work
- Old env var names work with deprecation support (OPERATIONS_CACHE_TTL)
- New names take precedence when both are set
- Validation catches invalid values
- Cached getter function works correctly
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    OperationsSettings,
    clear_settings_cache,
    get_operations_settings,
)


class TestOperationsSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_cache_ttl_is_1_second(self):
        """Default cache TTL should be 1.0 second."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OperationsSettings()
            assert settings.cache_ttl == 1.0

    def test_default_max_operations_is_10000(self):
        """Default max operations should be 10000."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OperationsSettings()
            assert settings.max_operations == 10000

    def test_default_cleanup_interval_seconds_is_3600(self):
        """Default cleanup interval should be 3600 seconds (1 hour)."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OperationsSettings()
            assert settings.cleanup_interval_seconds == 3600

    def test_default_retention_days_is_7(self):
        """Default retention should be 7 days."""
        with patch.dict(os.environ, {}, clear=True):
            settings = OperationsSettings()
            assert settings.retention_days == 7


class TestOperationsSettingsNewEnvVars:
    """Test new KTRDR_OPS_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_ops_cache_ttl_overrides_default(self):
        """KTRDR_OPS_CACHE_TTL should override default."""
        with patch.dict(os.environ, {"KTRDR_OPS_CACHE_TTL": "5.0"}, clear=False):
            settings = OperationsSettings()
            assert settings.cache_ttl == 5.0

    def test_ktrdr_ops_max_operations_overrides_default(self):
        """KTRDR_OPS_MAX_OPERATIONS should override default."""
        with patch.dict(os.environ, {"KTRDR_OPS_MAX_OPERATIONS": "50000"}, clear=False):
            settings = OperationsSettings()
            assert settings.max_operations == 50000

    def test_ktrdr_ops_cleanup_interval_seconds_overrides_default(self):
        """KTRDR_OPS_CLEANUP_INTERVAL_SECONDS should override default."""
        with patch.dict(
            os.environ, {"KTRDR_OPS_CLEANUP_INTERVAL_SECONDS": "7200"}, clear=False
        ):
            settings = OperationsSettings()
            assert settings.cleanup_interval_seconds == 7200

    def test_ktrdr_ops_retention_days_overrides_default(self):
        """KTRDR_OPS_RETENTION_DAYS should override default."""
        with patch.dict(os.environ, {"KTRDR_OPS_RETENTION_DAYS": "30"}, clear=False):
            settings = OperationsSettings()
            assert settings.retention_days == 30


class TestOperationsSettingsDeprecatedEnvVars:
    """Test deprecated environment variable support."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_operations_cache_ttl_deprecated_name_works(self):
        """OPERATIONS_CACHE_TTL (deprecated) should still work."""
        with patch.dict(os.environ, {"OPERATIONS_CACHE_TTL": "2.5"}, clear=False):
            settings = OperationsSettings()
            assert settings.cache_ttl == 2.5


class TestOperationsSettingsEnvVarPrecedence:
    """Test that new env var names take precedence over deprecated names."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_new_cache_ttl_takes_precedence(self):
        """KTRDR_OPS_CACHE_TTL takes precedence over OPERATIONS_CACHE_TTL."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_OPS_CACHE_TTL": "10.0",
                "OPERATIONS_CACHE_TTL": "0.5",
            },
            clear=False,
        ):
            settings = OperationsSettings()
            assert settings.cache_ttl == 10.0


class TestOperationsSettingsValidation:
    """Test validation of configuration values."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_negative_cache_ttl_raises_error(self):
        """Negative cache TTL should raise validation error."""
        with patch.dict(os.environ, {"KTRDR_OPS_CACHE_TTL": "-1.0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                OperationsSettings()
            assert "greater than or equal to 0" in str(exc_info.value)

    def test_zero_max_operations_raises_error(self):
        """Zero max operations should raise validation error."""
        with patch.dict(os.environ, {"KTRDR_OPS_MAX_OPERATIONS": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                OperationsSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_negative_cleanup_interval_raises_error(self):
        """Negative cleanup interval should raise validation error."""
        with patch.dict(
            os.environ, {"KTRDR_OPS_CLEANUP_INTERVAL_SECONDS": "-100"}, clear=False
        ):
            with pytest.raises(ValidationError) as exc_info:
                OperationsSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_zero_retention_days_raises_error(self):
        """Zero retention days should raise validation error."""
        with patch.dict(os.environ, {"KTRDR_OPS_RETENTION_DAYS": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                OperationsSettings()
            assert "greater than 0" in str(exc_info.value)


class TestGetOperationsSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_getter_returns_operations_settings_instance(self):
        """get_operations_settings() should return an OperationsSettings instance."""
        settings = get_operations_settings()
        assert isinstance(settings, OperationsSettings)

    def test_getter_returns_same_instance_on_repeated_calls(self):
        """get_operations_settings() should return the same cached instance."""
        settings1 = get_operations_settings()
        settings2 = get_operations_settings()
        assert settings1 is settings2

    def test_clear_cache_causes_new_instance(self):
        """After clear_settings_cache(), a new instance should be created."""
        settings1 = get_operations_settings()
        clear_settings_cache()
        settings2 = get_operations_settings()
        assert settings1 is not settings2

    def test_getter_picks_up_env_var_changes_after_clear(self):
        """After clear, new env var values should be picked up."""
        with patch.dict(os.environ, {}, clear=True):
            settings1 = get_operations_settings()
            assert settings1.cache_ttl == 1.0  # default

            clear_settings_cache()

            with patch.dict(os.environ, {"KTRDR_OPS_CACHE_TTL": "5.0"}, clear=False):
                settings2 = get_operations_settings()
                assert settings2.cache_ttl == 5.0
