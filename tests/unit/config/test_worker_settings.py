"""
Unit tests for WorkerSettings configuration.

Tests verify:
- WorkerSettings loads defaults correctly
- Port default is consistent (fixes duplication #4: 5002 vs 5004 bug)
- New env var names (KTRDR_WORKER_*) work
- Old env var names (WORKER_*) work with deprecation support
- New names take precedence when both are set
- Validation catches invalid values
- Cached getter function works correctly
- clear_settings_cache() causes new instance on next call
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    WorkerSettings,
    clear_settings_cache,
    get_worker_settings,
)


class TestWorkerSettingsDefaults:
    """Test default values when environment variables are not set.

    The port default of 5003 fixes duplication #4 from the config audit:
    WORKER_PORT defaulted to 5002 in training_worker.py but 5004 in
    worker_registration.py. Using 5003 as the canonical default matches
    the most common usage (first backtest worker port).
    """

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_port_is_5003(self):
        """Default worker port should be 5003 (canonical default, fixes bug)."""
        # Clear any existing env vars that might interfere
        with patch.dict(os.environ, {}, clear=True):
            settings = WorkerSettings()
            assert settings.port == 5003

    def test_default_heartbeat_interval_is_30(self):
        """Default heartbeat interval should be 30 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = WorkerSettings()
            assert settings.heartbeat_interval == 30

    def test_default_registration_timeout_is_10(self):
        """Default registration timeout should be 10 seconds."""
        with patch.dict(os.environ, {}, clear=True):
            settings = WorkerSettings()
            assert settings.registration_timeout == 10

    def test_default_endpoint_url_is_none(self):
        """Default endpoint_url should be None (auto-detected at runtime)."""
        with patch.dict(os.environ, {}, clear=True):
            settings = WorkerSettings()
            assert settings.endpoint_url is None

    def test_default_public_base_url_is_none(self):
        """Default public_base_url should be None (auto-detected at runtime)."""
        with patch.dict(os.environ, {}, clear=True):
            settings = WorkerSettings()
            assert settings.public_base_url is None


class TestWorkerSettingsNewEnvVars:
    """Test new KTRDR_WORKER_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_worker_port_overrides_default(self):
        """KTRDR_WORKER_PORT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_WORKER_PORT": "5010"}, clear=False):
            settings = WorkerSettings()
            assert settings.port == 5010

    def test_ktrdr_worker_id_overrides_default(self):
        """KTRDR_WORKER_ID environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_WORKER_ID": "my-custom-worker"}, clear=False
        ):
            settings = WorkerSettings()
            assert settings.worker_id == "my-custom-worker"

    def test_ktrdr_worker_heartbeat_interval_overrides_default(self):
        """KTRDR_WORKER_HEARTBEAT_INTERVAL should override default."""
        with patch.dict(
            os.environ, {"KTRDR_WORKER_HEARTBEAT_INTERVAL": "60"}, clear=False
        ):
            settings = WorkerSettings()
            assert settings.heartbeat_interval == 60

    def test_ktrdr_worker_registration_timeout_overrides_default(self):
        """KTRDR_WORKER_REGISTRATION_TIMEOUT should override default."""
        with patch.dict(
            os.environ, {"KTRDR_WORKER_REGISTRATION_TIMEOUT": "30"}, clear=False
        ):
            settings = WorkerSettings()
            assert settings.registration_timeout == 30

    def test_ktrdr_worker_endpoint_url_overrides_default(self):
        """KTRDR_WORKER_ENDPOINT_URL should override default."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_ENDPOINT_URL": "http://192.168.1.100:5003"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.endpoint_url == "http://192.168.1.100:5003"

    def test_ktrdr_worker_public_base_url_overrides_default(self):
        """KTRDR_WORKER_PUBLIC_BASE_URL should override default."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_PUBLIC_BASE_URL": "http://public.example.com:5003"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.public_base_url == "http://public.example.com:5003"


class TestWorkerSettingsDeprecatedEnvVars:
    """Test deprecated WORKER_* environment variable support."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_worker_port_deprecated_name_works(self):
        """WORKER_PORT (deprecated) should still work."""
        with patch.dict(os.environ, {"WORKER_PORT": "5004"}, clear=False):
            settings = WorkerSettings()
            assert settings.port == 5004

    def test_worker_id_deprecated_name_works(self):
        """WORKER_ID (deprecated) should still work."""
        with patch.dict(os.environ, {"WORKER_ID": "legacy-worker"}, clear=False):
            settings = WorkerSettings()
            assert settings.worker_id == "legacy-worker"

    def test_worker_endpoint_url_deprecated_name_works(self):
        """WORKER_ENDPOINT_URL (deprecated) should still work."""
        with patch.dict(
            os.environ,
            {"WORKER_ENDPOINT_URL": "http://legacy:5003"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.endpoint_url == "http://legacy:5003"

    def test_worker_public_base_url_deprecated_name_works(self):
        """WORKER_PUBLIC_BASE_URL (deprecated) should still work."""
        with patch.dict(
            os.environ,
            {"WORKER_PUBLIC_BASE_URL": "http://legacy-public:5003"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.public_base_url == "http://legacy-public:5003"


class TestWorkerSettingsEnvVarPrecedence:
    """Test that new env var names take precedence over deprecated names."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_new_port_takes_precedence_over_deprecated(self):
        """KTRDR_WORKER_PORT should take precedence over WORKER_PORT."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_PORT": "5010", "WORKER_PORT": "5004"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.port == 5010

    def test_new_worker_id_takes_precedence_over_deprecated(self):
        """KTRDR_WORKER_ID should take precedence over WORKER_ID."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_ID": "new-worker", "WORKER_ID": "old-worker"},
            clear=False,
        ):
            settings = WorkerSettings()
            assert settings.worker_id == "new-worker"


class TestWorkerSettingsValidation:
    """Test validation of WorkerSettings fields."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_port_must_be_valid_port_number(self):
        """Port must be between 1 and 65535."""
        with patch.dict(os.environ, {"KTRDR_WORKER_PORT": "0"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                WorkerSettings()
            assert "greater than or equal to 1" in str(exc_info.value)

    def test_port_cannot_exceed_65535(self):
        """Port cannot exceed 65535."""
        with patch.dict(os.environ, {"KTRDR_WORKER_PORT": "70000"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                WorkerSettings()
            assert "less than or equal to 65535" in str(exc_info.value)

    def test_heartbeat_interval_must_be_positive(self):
        """Heartbeat interval must be greater than 0."""
        with patch.dict(
            os.environ, {"KTRDR_WORKER_HEARTBEAT_INTERVAL": "0"}, clear=False
        ):
            with pytest.raises(ValidationError) as exc_info:
                WorkerSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_registration_timeout_must_be_positive(self):
        """Registration timeout must be greater than 0."""
        with patch.dict(
            os.environ, {"KTRDR_WORKER_REGISTRATION_TIMEOUT": "0"}, clear=False
        ):
            with pytest.raises(ValidationError) as exc_info:
                WorkerSettings()
            assert "greater than 0" in str(exc_info.value)


class TestWorkerSettingsCachedGetter:
    """Test the cached get_worker_settings() function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_getter_returns_worker_settings_instance(self):
        """get_worker_settings() should return a WorkerSettings instance."""
        settings = get_worker_settings()
        assert isinstance(settings, WorkerSettings)

    def test_getter_returns_same_instance_on_repeated_calls(self):
        """get_worker_settings() should return the same cached instance."""
        settings1 = get_worker_settings()
        settings2 = get_worker_settings()
        assert settings1 is settings2

    def test_clear_cache_causes_new_instance(self):
        """After clear_settings_cache(), a new instance should be created."""
        settings1 = get_worker_settings()
        clear_settings_cache()
        settings2 = get_worker_settings()
        assert settings1 is not settings2

    def test_getter_picks_up_env_var_changes_after_clear(self):
        """After clear, new env var values should be picked up."""
        with patch.dict(os.environ, {}, clear=True):
            settings1 = get_worker_settings()
            assert settings1.port == 5003  # default

            clear_settings_cache()

            with patch.dict(os.environ, {"KTRDR_WORKER_PORT": "5010"}, clear=False):
                settings2 = get_worker_settings()
                assert settings2.port == 5010


class TestWorkerSettingsNoBackendUrl:
    """Test that WorkerSettings does NOT have a backend_url field.

    Per the design doc: workers should use get_api_client_settings().base_url
    from M5's APIClientSettings (single source of truth for backend connection).
    """

    def test_no_backend_url_field(self):
        """WorkerSettings should not have a backend_url field."""
        settings = WorkerSettings()
        assert not hasattr(settings, "backend_url")

    def test_backend_url_env_var_is_ignored(self):
        """KTRDR_WORKER_BACKEND_URL env var should be ignored (extra=ignore)."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_BACKEND_URL": "http://backend:8000"},
            clear=False,
        ):
            settings = WorkerSettings()
            # Should not raise, but also should not have the field
            assert not hasattr(settings, "backend_url")
