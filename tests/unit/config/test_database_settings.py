"""
Unit tests for DatabaseSettings configuration and deprecated_field() helper.

Tests verify:
- deprecated_field() creates fields with AliasChoices for backward compatibility
- DatabaseSettings loads defaults correctly
- New env var names (KTRDR_DB_*) work
- Old env var names (DB_*) work with deprecation support
- New names take precedence when both are set
- url and sync_url computed properties produce correct connection strings
- Validation catches invalid values
- Cached getter function works correctly
- clear_settings_cache() causes new instance on next call
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ktrdr.config.settings import (
    DatabaseSettings,
    clear_settings_cache,
    deprecated_field,
    get_db_settings,
)


class TestDeprecatedFieldHelper:
    """Test the deprecated_field() helper function."""

    def test_deprecated_field_returns_field_info(self):
        """deprecated_field() should return a Pydantic FieldInfo."""
        from pydantic.fields import FieldInfo

        result = deprecated_field("default", "NEW_NAME", "OLD_NAME")
        assert isinstance(result, FieldInfo)

    def test_deprecated_field_sets_default(self):
        """deprecated_field() should set the default value."""
        result = deprecated_field("my_default", "NEW_NAME", "OLD_NAME")
        assert result.default == "my_default"

    def test_deprecated_field_accepts_additional_kwargs(self):
        """deprecated_field() should pass through additional Field kwargs."""
        result = deprecated_field(
            "default", "NEW_NAME", "OLD_NAME", description="A test field"
        )
        assert result.description == "A test field"


class TestDatabaseSettingsDefaults:
    """Test default values when environment variables are not set."""

    def setup_method(self):
        """Clear cache and env vars before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_default_host_is_localhost(self):
        """Default database host should be localhost."""
        settings = DatabaseSettings()
        assert settings.host == "localhost"

    def test_default_port_is_5432(self):
        """Default database port should be 5432."""
        settings = DatabaseSettings()
        assert settings.port == 5432

    def test_default_name_is_ktrdr(self):
        """Default database name should be ktrdr."""
        settings = DatabaseSettings()
        assert settings.name == "ktrdr"

    def test_default_user_is_ktrdr(self):
        """Default database user should be ktrdr."""
        settings = DatabaseSettings()
        assert settings.user == "ktrdr"

    def test_default_password_is_localdev(self):
        """Default database password should be localdev (insecure default)."""
        settings = DatabaseSettings()
        assert settings.password == "localdev"

    def test_default_echo_is_false(self):
        """Default database echo should be False."""
        settings = DatabaseSettings()
        assert settings.echo is False


class TestDatabaseSettingsNewEnvVars:
    """Test new KTRDR_DB_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_db_host_overrides_default(self):
        """KTRDR_DB_HOST environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_DB_HOST": "db.example.com"}, clear=False):
            settings = DatabaseSettings()
            assert settings.host == "db.example.com"

    def test_ktrdr_db_port_overrides_default(self):
        """KTRDR_DB_PORT environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_DB_PORT": "5433"}, clear=False):
            settings = DatabaseSettings()
            assert settings.port == 5433

    def test_ktrdr_db_name_overrides_default(self):
        """KTRDR_DB_NAME environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_DB_NAME": "production_db"}, clear=False):
            settings = DatabaseSettings()
            assert settings.name == "production_db"

    def test_ktrdr_db_user_overrides_default(self):
        """KTRDR_DB_USER environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_DB_USER": "admin"}, clear=False):
            settings = DatabaseSettings()
            assert settings.user == "admin"

    def test_ktrdr_db_password_overrides_default(self):
        """KTRDR_DB_PASSWORD environment variable should override default."""
        with patch.dict(
            os.environ, {"KTRDR_DB_PASSWORD": "secure_password"}, clear=False
        ):
            settings = DatabaseSettings()
            assert settings.password == "secure_password"

    def test_ktrdr_db_echo_overrides_default(self):
        """KTRDR_DB_ECHO environment variable should override default."""
        with patch.dict(os.environ, {"KTRDR_DB_ECHO": "true"}, clear=False):
            settings = DatabaseSettings()
            assert settings.echo is True


class TestDatabaseSettingsDeprecatedEnvVars:
    """Test deprecated DB_* environment variable configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_db_host_deprecated_still_works(self):
        """DB_HOST (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_HOST": "old.db.com"}, clear=False):
            settings = DatabaseSettings()
            assert settings.host == "old.db.com"

    def test_db_port_deprecated_still_works(self):
        """DB_PORT (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_PORT": "5434"}, clear=False):
            settings = DatabaseSettings()
            assert settings.port == 5434

    def test_db_name_deprecated_still_works(self):
        """DB_NAME (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_NAME": "old_db"}, clear=False):
            settings = DatabaseSettings()
            assert settings.name == "old_db"

    def test_db_user_deprecated_still_works(self):
        """DB_USER (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_USER": "old_user"}, clear=False):
            settings = DatabaseSettings()
            assert settings.user == "old_user"

    def test_db_password_deprecated_still_works(self):
        """DB_PASSWORD (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_PASSWORD": "old_password"}, clear=False):
            settings = DatabaseSettings()
            assert settings.password == "old_password"

    def test_db_echo_deprecated_still_works(self):
        """DB_ECHO (deprecated) should still override default."""
        with patch.dict(os.environ, {"DB_ECHO": "true"}, clear=False):
            settings = DatabaseSettings()
            assert settings.echo is True


class TestDatabaseSettingsPrecedence:
    """Test that new env vars take precedence over deprecated ones."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_ktrdr_db_host_takes_precedence_over_db_host(self):
        """KTRDR_DB_HOST should take precedence when both old and new are set."""
        with patch.dict(
            os.environ,
            {"KTRDR_DB_HOST": "new.db.com", "DB_HOST": "old.db.com"},
            clear=False,
        ):
            settings = DatabaseSettings()
            assert settings.host == "new.db.com"

    def test_ktrdr_db_password_takes_precedence_over_db_password(self):
        """KTRDR_DB_PASSWORD should take precedence when both are set."""
        with patch.dict(
            os.environ,
            {"KTRDR_DB_PASSWORD": "new_pass", "DB_PASSWORD": "old_pass"},
            clear=False,
        ):
            settings = DatabaseSettings()
            assert settings.password == "new_pass"


class TestDatabaseSettingsComputedUrls:
    """Test computed url and sync_url properties."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_url_produces_correct_async_connection_string(self):
        """url property should produce correct async connection string."""
        settings = DatabaseSettings()
        expected = "postgresql+asyncpg://ktrdr:localdev@localhost:5432/ktrdr"
        assert settings.url == expected

    def test_url_uses_custom_values(self):
        """url property should use configured values."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_DB_HOST": "db.example.com",
                "KTRDR_DB_PORT": "5433",
                "KTRDR_DB_NAME": "mydb",
                "KTRDR_DB_USER": "myuser",
                "KTRDR_DB_PASSWORD": "mypass",
            },
            clear=False,
        ):
            settings = DatabaseSettings()
            expected = "postgresql+asyncpg://myuser:mypass@db.example.com:5433/mydb"
            assert settings.url == expected

    def test_sync_url_produces_correct_sync_connection_string(self):
        """sync_url property should produce correct sync connection string."""
        settings = DatabaseSettings()
        expected = "postgresql+psycopg2://ktrdr:localdev@localhost:5432/ktrdr"
        assert settings.sync_url == expected

    def test_sync_url_uses_custom_values(self):
        """sync_url property should use configured values."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_DB_HOST": "db.example.com",
                "KTRDR_DB_PORT": "5433",
                "KTRDR_DB_NAME": "mydb",
                "KTRDR_DB_USER": "myuser",
                "KTRDR_DB_PASSWORD": "mypass",
            },
            clear=False,
        ):
            settings = DatabaseSettings()
            expected = "postgresql+psycopg2://myuser:mypass@db.example.com:5433/mydb"
            assert settings.sync_url == expected


class TestDatabaseSettingsValidation:
    """Test validation of configuration values."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_invalid_port_type_raises_validation_error(self):
        """KTRDR_DB_PORT=abc should raise ValidationError."""
        with patch.dict(os.environ, {"KTRDR_DB_PORT": "abc"}, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                DatabaseSettings()
            assert "port" in str(exc_info.value).lower()


class TestGetDbSettings:
    """Test the cached getter function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_settings_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_returns_database_settings_instance(self):
        """get_db_settings() should return a DatabaseSettings instance."""
        settings = get_db_settings()
        assert isinstance(settings, DatabaseSettings)

    def test_returns_cached_instance(self):
        """Subsequent calls should return the same cached instance."""
        settings1 = get_db_settings()
        settings2 = get_db_settings()
        assert settings1 is settings2

    def test_cache_cleared_returns_new_instance(self):
        """After clearing cache, getter should return new instance."""
        settings1 = get_db_settings()
        clear_settings_cache()
        settings2 = get_db_settings()
        assert settings1 is not settings2


class TestClearSettingsCache:
    """Test that clear_settings_cache() clears the db settings cache."""

    def test_clear_settings_cache_clears_db_cache(self):
        """clear_settings_cache() should clear get_db_settings cache."""
        # Get initial instance
        settings1 = get_db_settings()

        # Clear cache
        clear_settings_cache()

        # Get new instance - should be different object
        settings2 = get_db_settings()
        assert settings1 is not settings2
