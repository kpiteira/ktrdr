"""Tests for DataSettings."""

import pytest

from ktrdr.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestDataSettingsDefaults:
    """Test DataSettings default values."""

    def test_default_data_dir(self):
        """Data dir should default to data."""
        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.data_dir == "data"

    def test_default_models_dir(self):
        """Models dir should default to models."""
        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.models_dir == "models"

    def test_default_cache_dir(self):
        """Cache dir should default to data/cache."""
        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.cache_dir == "data/cache"

    def test_default_max_segment_size(self):
        """Max segment size should default to 5000."""
        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.max_segment_size == 5000

    def test_default_periodic_save_interval(self):
        """Periodic save interval should default to 0.5 minutes."""
        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.periodic_save_interval == 0.5


class TestDataSettingsEnvVars:
    """Test DataSettings with KTRDR_DATA_* env vars."""

    def test_data_dir_from_env(self, monkeypatch):
        """Should read data_dir from KTRDR_DATA_DIR."""
        monkeypatch.setenv("KTRDR_DATA_DIR", "/tmp/ktrdr-data")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.data_dir == "/tmp/ktrdr-data"

    def test_models_dir_from_env(self, monkeypatch):
        """Should read models_dir from KTRDR_DATA_MODELS_DIR."""
        monkeypatch.setenv("KTRDR_DATA_MODELS_DIR", "/opt/models")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.models_dir == "/opt/models"

    def test_cache_dir_from_env(self, monkeypatch):
        """Should read cache_dir from KTRDR_DATA_CACHE_DIR."""
        monkeypatch.setenv("KTRDR_DATA_CACHE_DIR", "/tmp/cache")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.cache_dir == "/tmp/cache"

    def test_max_segment_size_from_env(self, monkeypatch):
        """Should read max_segment_size from KTRDR_DATA_MAX_SEGMENT_SIZE."""
        monkeypatch.setenv("KTRDR_DATA_MAX_SEGMENT_SIZE", "10000")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.max_segment_size == 10000

    def test_periodic_save_interval_from_env(self, monkeypatch):
        """Should read periodic_save_interval from KTRDR_DATA_PERIODIC_SAVE_INTERVAL."""
        monkeypatch.setenv("KTRDR_DATA_PERIODIC_SAVE_INTERVAL", "1.5")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.periodic_save_interval == 1.5


class TestDataSettingsDeprecatedNames:
    """Test DataSettings with deprecated env var names."""

    def test_deprecated_data_dir(self, monkeypatch):
        """Deprecated DATA_DIR should still work."""
        monkeypatch.setenv("DATA_DIR", "/old/data/path")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.data_dir == "/old/data/path"

    def test_deprecated_models_dir(self, monkeypatch):
        """Deprecated MODELS_DIR should still work."""
        monkeypatch.setenv("MODELS_DIR", "/old/models/path")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.models_dir == "/old/models/path"

    def test_deprecated_max_segment_size(self, monkeypatch):
        """Deprecated DATA_MAX_SEGMENT_SIZE should still work."""
        monkeypatch.setenv("DATA_MAX_SEGMENT_SIZE", "7500")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.max_segment_size == 7500

    def test_deprecated_periodic_save(self, monkeypatch):
        """Deprecated DATA_PERIODIC_SAVE_MIN should still work."""
        monkeypatch.setenv("DATA_PERIODIC_SAVE_MIN", "2.0")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.periodic_save_interval == 2.0


class TestDataSettingsPrecedence:
    """Test that new names take precedence over deprecated names."""

    def test_new_name_takes_precedence(self, monkeypatch):
        """KTRDR_DATA_* should take precedence over deprecated names."""
        monkeypatch.setenv("KTRDR_DATA_DIR", "/new/path")
        monkeypatch.setenv("DATA_DIR", "/old/path")

        from ktrdr.config.settings import get_data_settings

        settings = get_data_settings()
        assert settings.data_dir == "/new/path"


class TestDataSettingsValidation:
    """Test DataSettings validation."""

    def test_max_segment_size_must_be_positive(self, monkeypatch):
        """Max segment size must be > 0."""
        monkeypatch.setenv("KTRDR_DATA_MAX_SEGMENT_SIZE", "0")

        from ktrdr.config.settings import get_data_settings

        with pytest.raises(Exception) as exc_info:
            get_data_settings()
        assert "greater than 0" in str(exc_info.value)

    def test_periodic_save_interval_must_be_positive(self, monkeypatch):
        """Periodic save interval must be > 0."""
        monkeypatch.setenv("KTRDR_DATA_PERIODIC_SAVE_INTERVAL", "0")

        from ktrdr.config.settings import get_data_settings

        with pytest.raises(Exception) as exc_info:
            get_data_settings()
        assert "greater than 0" in str(exc_info.value)


class TestDataSettingsGetter:
    """Test get_data_settings() caching behavior."""

    def test_getter_returns_same_instance(self):
        """get_data_settings() should return cached instance."""
        from ktrdr.config.settings import get_data_settings

        settings1 = get_data_settings()
        settings2 = get_data_settings()
        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """clear_settings_cache() should clear the data settings cache."""
        from ktrdr.config.settings import get_data_settings

        settings1 = get_data_settings()
        clear_settings_cache()
        settings2 = get_data_settings()
        assert settings1 is not settings2
