"""
Unit tests for OrphanDetectorSettings configuration.

Tests verify:
- Default values are sensible (60s timeout, 15s interval)
- Environment variables override defaults
- Invalid values (negative, zero) raise validation errors
- Cached getter function works correctly
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    OrphanDetectorSettings,
    clear_settings_cache,
    get_orphan_detector_settings,
)


class TestOrphanDetectorSettingsDefaults:
    """Test default values when environment variables are not set."""

    def test_default_timeout_is_60_seconds(self):
        """Default orphan timeout should be 60 seconds."""
        settings = OrphanDetectorSettings()
        assert settings.timeout_seconds == 60

    def test_default_check_interval_is_15_seconds(self):
        """Default check interval should be 15 seconds."""
        settings = OrphanDetectorSettings()
        assert settings.check_interval_seconds == 15


class TestOrphanDetectorSettingsEnvironment:
    """Test environment variable configuration."""

    def test_timeout_configurable_via_environment(self):
        """ORPHAN_TIMEOUT_SECONDS environment variable should override default."""
        with patch.dict(os.environ, {"ORPHAN_TIMEOUT_SECONDS": "120"}):
            settings = OrphanDetectorSettings()
            assert settings.timeout_seconds == 120

    def test_check_interval_configurable_via_environment(self):
        """ORPHAN_CHECK_INTERVAL_SECONDS environment variable should override default."""
        with patch.dict(os.environ, {"ORPHAN_CHECK_INTERVAL_SECONDS": "30"}):
            settings = OrphanDetectorSettings()
            assert settings.check_interval_seconds == 30

    def test_both_settings_configurable_together(self):
        """Both settings should be configurable simultaneously."""
        with patch.dict(
            os.environ,
            {
                "ORPHAN_TIMEOUT_SECONDS": "90",
                "ORPHAN_CHECK_INTERVAL_SECONDS": "10",
            },
        ):
            settings = OrphanDetectorSettings()
            assert settings.timeout_seconds == 90
            assert settings.check_interval_seconds == 10


class TestOrphanDetectorSettingsValidation:
    """Test validation of configuration values."""

    def test_negative_timeout_raises_error(self):
        """Negative timeout value should raise validation error."""
        with patch.dict(os.environ, {"ORPHAN_TIMEOUT_SECONDS": "-1"}):
            with pytest.raises(ValidationError) as exc_info:
                OrphanDetectorSettings()
            assert "timeout_seconds" in str(exc_info.value)

    def test_zero_timeout_raises_error(self):
        """Zero timeout value should raise validation error."""
        with patch.dict(os.environ, {"ORPHAN_TIMEOUT_SECONDS": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                OrphanDetectorSettings()
            assert "timeout_seconds" in str(exc_info.value)

    def test_negative_check_interval_raises_error(self):
        """Negative check interval should raise validation error."""
        with patch.dict(os.environ, {"ORPHAN_CHECK_INTERVAL_SECONDS": "-5"}):
            with pytest.raises(ValidationError) as exc_info:
                OrphanDetectorSettings()
            assert "check_interval_seconds" in str(exc_info.value)

    def test_zero_check_interval_raises_error(self):
        """Zero check interval should raise validation error."""
        with patch.dict(os.environ, {"ORPHAN_CHECK_INTERVAL_SECONDS": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                OrphanDetectorSettings()
            assert "check_interval_seconds" in str(exc_info.value)


class TestGetOrphanDetectorSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_orphan_detector_settings_instance(self):
        """Getter should return an OrphanDetectorSettings instance."""
        settings = get_orphan_detector_settings()
        assert isinstance(settings, OrphanDetectorSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_orphan_detector_settings()
        settings2 = get_orphan_detector_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_orphan_detector_settings()
        clear_settings_cache()
        settings2 = get_orphan_detector_settings()
        # Note: They may be equal but should be different objects
        # after cache clear (though values may be the same)
        # This test verifies the cache mechanism works
        assert settings1 is not settings2
