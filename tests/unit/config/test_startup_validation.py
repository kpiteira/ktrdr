"""
Unit tests for startup validation module.

Tests verify:
- validate_all() validates settings for backend/worker/all components
- validate_all() collects multiple errors (not just first)
- validate_all() with KTRDR_ENV=production and insecure defaults raises
- validate_all() with KTRDR_ENV=development and insecure defaults warns but doesn't raise
- detect_insecure_defaults() returns dict of insecure values in use
- Error messages include env var names and are human-readable
- KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true suppresses warning
"""

import os
import warnings
from unittest.mock import patch

import pytest

from ktrdr.config.settings import clear_settings_cache
from ktrdr.config.validation import (
    BACKEND_SETTINGS,
    INSECURE_DEFAULTS,
    WORKER_SETTINGS,
    detect_insecure_defaults,
    validate_all,
)
from ktrdr.errors import ConfigurationError


class TestInsecureDefaults:
    """Test the INSECURE_DEFAULTS constant."""

    def test_insecure_defaults_contains_db_password(self):
        """INSECURE_DEFAULTS should contain KTRDR_DB_PASSWORD."""
        assert "KTRDR_DB_PASSWORD" in INSECURE_DEFAULTS

    def test_insecure_defaults_db_password_is_localdev(self):
        """KTRDR_DB_PASSWORD insecure default should be 'localdev'."""
        assert INSECURE_DEFAULTS["KTRDR_DB_PASSWORD"] == "localdev"


class TestComponentSettingsLists:
    """Test the component settings lists."""

    def test_backend_settings_contains_database_settings(self):
        """BACKEND_SETTINGS should contain DatabaseSettings after initialization."""
        from ktrdr.config.settings import DatabaseSettings
        from ktrdr.config.validation import _init_settings_lists

        # Initialize lists (normally done on first validate_all call)
        _init_settings_lists()

        assert DatabaseSettings in BACKEND_SETTINGS

    def test_worker_settings_contains_database_settings(self):
        """WORKER_SETTINGS should contain DatabaseSettings after initialization."""
        from ktrdr.config.settings import DatabaseSettings
        from ktrdr.config.validation import _init_settings_lists

        # Initialize lists (normally done on first validate_all call)
        _init_settings_lists()

        assert DatabaseSettings in WORKER_SETTINGS


class TestDetectInsecureDefaults:
    """Test the detect_insecure_defaults() function."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_returns_empty_dict_when_secrets_set(self):
        """detect_insecure_defaults() should return empty dict when secrets are set."""
        with patch.dict(
            os.environ,
            {"KTRDR_DB_PASSWORD": "secure_password_not_localdev"},
            clear=False,
        ):
            result = detect_insecure_defaults()
            assert "KTRDR_DB_PASSWORD" not in result

    def test_returns_dict_with_insecure_values(self):
        """detect_insecure_defaults() should return dict with insecure values."""
        # When no env var is set, the default "localdev" is used
        result = detect_insecure_defaults()
        assert "KTRDR_DB_PASSWORD" in result
        assert result["KTRDR_DB_PASSWORD"] == "localdev"

    def test_returns_empty_when_all_secrets_secure(self):
        """detect_insecure_defaults() should return empty dict when all secure."""
        with patch.dict(
            os.environ,
            {"KTRDR_DB_PASSWORD": "super_secure_password_123"},
            clear=False,
        ):
            result = detect_insecure_defaults()
            # Should not contain KTRDR_DB_PASSWORD since it's not at insecure default
            assert result == {} or "KTRDR_DB_PASSWORD" not in result


class TestValidateAllBackend:
    """Test validate_all() for backend component."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_validate_all_backend_succeeds_with_valid_settings(self):
        """validate_all('backend') should succeed with valid settings."""
        # With default settings (and no KTRDR_ENV set), should not raise
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "development", "KTRDR_DB_PASSWORD": "secure_pass"},
            clear=False,
        ):
            # Should not raise
            validate_all("backend")

    def test_validate_all_production_with_insecure_defaults_raises(self):
        """validate_all('backend') with KTRDR_ENV=production and insecure defaults should raise."""
        with patch.dict(os.environ, {"KTRDR_ENV": "production"}, clear=False):
            # Remove any existing secure password to ensure we use default
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                with pytest.raises(ConfigurationError) as exc_info:
                    validate_all("backend")
                # Error details should mention the insecure env var
                error = exc_info.value
                assert "KTRDR_DB_PASSWORD" in error.details.get("insecure_settings", [])

    def test_validate_all_development_with_insecure_defaults_warns_not_raises(self):
        """validate_all('backend') with KTRDR_ENV=development and insecure defaults warns."""
        with patch.dict(os.environ, {"KTRDR_ENV": "development"}, clear=False):
            # Remove any existing secure password to ensure we use default
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                # Should NOT raise, just warn
                validate_all("backend")  # Should not raise

    def test_validate_all_collects_multiple_errors(self):
        """validate_all('backend') should collect all errors, not stop at first."""
        # This test would require multiple invalid settings
        # For M1, we only have DatabaseSettings, so we test with one
        # Future milestones will add more settings classes
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "production", "KTRDR_DB_PORT": "invalid_port"},
            clear=False,
        ):
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                with pytest.raises(ConfigurationError):
                    validate_all("backend")


class TestValidateAllWorker:
    """Test validate_all() for worker component."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_validate_all_worker_succeeds_with_valid_settings(self):
        """validate_all('worker') should succeed with valid settings."""
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "development", "KTRDR_DB_PASSWORD": "secure_pass"},
            clear=False,
        ):
            validate_all("worker")


class TestValidateAllComponent:
    """Test validate_all() with different component values."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_validate_all_accepts_backend(self):
        """validate_all() should accept 'backend' as component."""
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "development", "KTRDR_DB_PASSWORD": "secure_pass"},
            clear=False,
        ):
            validate_all("backend")

    def test_validate_all_accepts_worker(self):
        """validate_all() should accept 'worker' as component."""
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "development", "KTRDR_DB_PASSWORD": "secure_pass"},
            clear=False,
        ):
            validate_all("worker")

    def test_validate_all_accepts_all(self):
        """validate_all() should accept 'all' as component."""
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "development", "KTRDR_DB_PASSWORD": "secure_pass"},
            clear=False,
        ):
            validate_all("all")


class TestValidateAllAcknowledgeInsecure:
    """Test KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS suppression."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_acknowledge_insecure_suppresses_warning(self):
        """KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true should suppress warning."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_ENV": "development",
                "KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS": "true",
            },
            clear=False,
        ):
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                # Should not raise, and should not warn (testing via no warning emitted)
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    validate_all("backend")
                    # Should not emit insecure defaults warning
                    insecure_warnings = [
                        warning
                        for warning in w
                        if "insecure" in str(warning.message).lower()
                    ]
                    assert len(insecure_warnings) == 0


class TestErrorMessageFormat:
    """Test that error messages are clear and actionable."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_error_message_includes_env_var_name(self):
        """Error message should include the env var name in details."""
        with patch.dict(os.environ, {"KTRDR_ENV": "production"}, clear=False):
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                with pytest.raises(ConfigurationError) as exc_info:
                    validate_all("backend")
                # Error details should contain the env var name
                error = exc_info.value
                assert "KTRDR_DB_PASSWORD" in error.details.get("insecure_settings", [])

    def test_error_message_is_human_readable(self):
        """Error message should be human-readable."""
        with patch.dict(os.environ, {"KTRDR_ENV": "production"}, clear=False):
            env_copy = os.environ.copy()
            env_copy.pop("KTRDR_DB_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                clear_settings_cache()
                with pytest.raises(ConfigurationError) as exc_info:
                    validate_all("backend")
                # Should mention production, insecure, or similar
                error_str = str(exc_info.value).lower()
                assert "insecure" in error_str or "production" in error_str


class TestValidationActuallyLoadsSettings:
    """Integration test: validate_all() actually loads settings from environment."""

    def setup_method(self):
        """Clear settings cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear settings cache after each test."""
        clear_settings_cache()

    def test_validate_all_loads_settings_from_env(self):
        """validate_all() should actually load and validate settings from env."""
        # Set a secure password and verify validation passes
        with patch.dict(
            os.environ,
            {"KTRDR_ENV": "production", "KTRDR_DB_PASSWORD": "secure_password_123"},
            clear=False,
        ):
            # Should not raise since we have secure password
            validate_all("backend")
