"""
Unit tests for CheckpointSettings configuration.

Tests verify:
- Default values are sensible (10 epochs, 300s time, /app/data/checkpoints, 30 days)
- Environment variables override defaults
- Invalid values (negative, zero for intervals) raise validation errors
- Cached getter function works correctly
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    CheckpointSettings,
    clear_settings_cache,
    get_checkpoint_settings,
)


class TestCheckpointSettingsDefaults:
    """Test default values when environment variables are not set."""

    def test_default_epoch_interval_is_10(self):
        """Default checkpoint epoch interval should be 10."""
        settings = CheckpointSettings()
        assert settings.epoch_interval == 10

    def test_default_time_interval_is_300_seconds(self):
        """Default checkpoint time interval should be 300 seconds."""
        settings = CheckpointSettings()
        assert settings.time_interval_seconds == 300

    def test_default_dir_is_app_data_checkpoints(self):
        """Default checkpoint directory should be /app/data/checkpoints."""
        settings = CheckpointSettings()
        assert settings.dir == "/app/data/checkpoints"

    def test_default_max_age_is_30_days(self):
        """Default checkpoint max age should be 30 days."""
        settings = CheckpointSettings()
        assert settings.max_age_days == 30


class TestCheckpointSettingsEnvironment:
    """Test environment variable configuration."""

    def test_epoch_interval_configurable_via_environment(self):
        """CHECKPOINT_EPOCH_INTERVAL environment variable should override default."""
        with patch.dict(os.environ, {"CHECKPOINT_EPOCH_INTERVAL": "5"}):
            settings = CheckpointSettings()
            assert settings.epoch_interval == 5

    def test_time_interval_configurable_via_environment(self):
        """CHECKPOINT_TIME_INTERVAL_SECONDS environment variable should override default."""
        with patch.dict(os.environ, {"CHECKPOINT_TIME_INTERVAL_SECONDS": "600"}):
            settings = CheckpointSettings()
            assert settings.time_interval_seconds == 600

    def test_dir_configurable_via_environment(self):
        """CHECKPOINT_DIR environment variable should override default."""
        with patch.dict(os.environ, {"CHECKPOINT_DIR": "/mnt/ktrdr_data/checkpoints"}):
            settings = CheckpointSettings()
            assert settings.dir == "/mnt/ktrdr_data/checkpoints"

    def test_max_age_configurable_via_environment(self):
        """CHECKPOINT_MAX_AGE_DAYS environment variable should override default."""
        with patch.dict(os.environ, {"CHECKPOINT_MAX_AGE_DAYS": "60"}):
            settings = CheckpointSettings()
            assert settings.max_age_days == 60

    def test_all_settings_configurable_together(self):
        """All settings should be configurable simultaneously."""
        with patch.dict(
            os.environ,
            {
                "CHECKPOINT_EPOCH_INTERVAL": "20",
                "CHECKPOINT_TIME_INTERVAL_SECONDS": "120",
                "CHECKPOINT_DIR": "/custom/path",
                "CHECKPOINT_MAX_AGE_DAYS": "7",
            },
        ):
            settings = CheckpointSettings()
            assert settings.epoch_interval == 20
            assert settings.time_interval_seconds == 120
            assert settings.dir == "/custom/path"
            assert settings.max_age_days == 7


class TestCheckpointSettingsValidation:
    """Test validation of configuration values."""

    def test_negative_epoch_interval_raises_error(self):
        """Negative epoch interval should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_EPOCH_INTERVAL": "-1"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            # With deprecated_field, error shows env var name not field name
            assert "greater than 0" in str(exc_info.value)

    def test_zero_epoch_interval_raises_error(self):
        """Zero epoch interval should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_EPOCH_INTERVAL": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_negative_time_interval_raises_error(self):
        """Negative time interval should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_TIME_INTERVAL_SECONDS": "-100"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_zero_time_interval_raises_error(self):
        """Zero time interval should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_TIME_INTERVAL_SECONDS": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_negative_max_age_raises_error(self):
        """Negative max age should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_MAX_AGE_DAYS": "-1"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_zero_max_age_raises_error(self):
        """Zero max age should raise validation error."""
        with patch.dict(os.environ, {"CHECKPOINT_MAX_AGE_DAYS": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                CheckpointSettings()
            assert "greater than 0" in str(exc_info.value)

    def test_empty_dir_is_allowed(self):
        """Empty directory string should be allowed (may be valid for some configs)."""
        # Note: We don't validate directory existence at config time
        # This is intentional - directory might not exist until container starts
        with patch.dict(os.environ, {"CHECKPOINT_DIR": ""}):
            settings = CheckpointSettings()
            assert settings.dir == ""


class TestCheckpointSettingsNewEnvVars:
    """Test new KTRDR_CHECKPOINT_* environment variable configuration.

    These tests verify that the new canonical env var names work correctly.
    """

    def test_ktrdr_checkpoint_epoch_interval_overrides_default(self):
        """KTRDR_CHECKPOINT_EPOCH_INTERVAL should override default."""
        with patch.dict(
            os.environ, {"KTRDR_CHECKPOINT_EPOCH_INTERVAL": "25"}, clear=False
        ):
            settings = CheckpointSettings()
            assert settings.epoch_interval == 25

    def test_ktrdr_checkpoint_time_interval_seconds_overrides_default(self):
        """KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS should override default."""
        with patch.dict(
            os.environ, {"KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS": "900"}, clear=False
        ):
            settings = CheckpointSettings()
            assert settings.time_interval_seconds == 900

    def test_ktrdr_checkpoint_dir_overrides_default(self):
        """KTRDR_CHECKPOINT_DIR should override default."""
        with patch.dict(
            os.environ, {"KTRDR_CHECKPOINT_DIR": "/new/checkpoint/path"}, clear=False
        ):
            settings = CheckpointSettings()
            assert settings.dir == "/new/checkpoint/path"

    def test_ktrdr_checkpoint_max_age_days_overrides_default(self):
        """KTRDR_CHECKPOINT_MAX_AGE_DAYS should override default."""
        with patch.dict(
            os.environ, {"KTRDR_CHECKPOINT_MAX_AGE_DAYS": "90"}, clear=False
        ):
            settings = CheckpointSettings()
            assert settings.max_age_days == 90


class TestCheckpointSettingsEnvVarPrecedence:
    """Test that new env var names take precedence over deprecated names."""

    def test_new_epoch_interval_takes_precedence(self):
        """KTRDR_CHECKPOINT_EPOCH_INTERVAL takes precedence over CHECKPOINT_EPOCH_INTERVAL."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_CHECKPOINT_EPOCH_INTERVAL": "50",
                "CHECKPOINT_EPOCH_INTERVAL": "5",
            },
            clear=False,
        ):
            settings = CheckpointSettings()
            assert settings.epoch_interval == 50

    def test_new_time_interval_takes_precedence(self):
        """KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS takes precedence over CHECKPOINT_TIME_INTERVAL_SECONDS."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS": "1800",
                "CHECKPOINT_TIME_INTERVAL_SECONDS": "60",
            },
            clear=False,
        ):
            settings = CheckpointSettings()
            assert settings.time_interval_seconds == 1800

    def test_new_dir_takes_precedence(self):
        """KTRDR_CHECKPOINT_DIR takes precedence over CHECKPOINT_DIR."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_CHECKPOINT_DIR": "/new/path",
                "CHECKPOINT_DIR": "/old/path",
            },
            clear=False,
        ):
            settings = CheckpointSettings()
            assert settings.dir == "/new/path"

    def test_new_max_age_takes_precedence(self):
        """KTRDR_CHECKPOINT_MAX_AGE_DAYS takes precedence over CHECKPOINT_MAX_AGE_DAYS."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_CHECKPOINT_MAX_AGE_DAYS": "365",
                "CHECKPOINT_MAX_AGE_DAYS": "7",
            },
            clear=False,
        ):
            settings = CheckpointSettings()
            assert settings.max_age_days == 365


class TestGetCheckpointSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_checkpoint_settings_instance(self):
        """Getter should return a CheckpointSettings instance."""
        settings = get_checkpoint_settings()
        assert isinstance(settings, CheckpointSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_checkpoint_settings()
        settings2 = get_checkpoint_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_checkpoint_settings()
        clear_settings_cache()
        settings2 = get_checkpoint_settings()
        # They should be different objects after cache clear
        assert settings1 is not settings2
