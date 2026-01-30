"""
Unit tests for database.py migration to get_db_settings().

Tests verify that database.py uses the new settings infrastructure
instead of direct os.getenv() calls.
"""

from unittest.mock import MagicMock, patch

from ktrdr.config import clear_settings_cache


class TestDatabaseUsesSettings:
    """Test that database module uses get_db_settings()."""

    def setup_method(self):
        """Reset module state before each test."""
        clear_settings_cache()
        # Reset the global engine/session factory
        import ktrdr.api.database as db_module

        db_module._engine = None
        db_module._session_factory = None

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_get_database_url_uses_settings(self):
        """get_database_url() should use get_db_settings().url."""
        from ktrdr.api.database import get_database_url
        from ktrdr.config import get_db_settings

        # Get URL from both sources
        url_from_function = get_database_url()
        url_from_settings = get_db_settings().url

        # They should match
        assert url_from_function == url_from_settings

    def test_get_engine_uses_settings_for_echo(self):
        """get_engine() should use get_db_settings().echo for echo setting."""
        # Reset engine to force re-creation
        import ktrdr.api.database as db_module

        db_module._engine = None

        with patch("ktrdr.api.database.get_db_settings") as mock_get_settings:
            # Create a mock settings object
            mock_settings = MagicMock()
            mock_settings.url = "postgresql+asyncpg://user:pass@host:5432/db"
            mock_settings.echo = True
            mock_settings.host = "host"
            mock_settings.port = 5432
            mock_settings.name = "db"
            mock_get_settings.return_value = mock_settings

            engine = db_module.get_engine()

            # Verify settings were accessed
            mock_get_settings.assert_called()
            # Engine should have been created with echo=True
            assert engine.echo is True

        # Reset for other tests
        db_module._engine = None

    def test_no_os_getenv_for_db_vars(self):
        """database.py should not use os.getenv for DB_* variables."""
        import inspect

        from ktrdr.api import database

        # Get the source code of the module
        source = inspect.getsource(database)

        # Check that deprecated env var patterns are not present
        deprecated_patterns = [
            'os.getenv("DB_HOST"',
            'os.getenv("DB_PORT"',
            'os.getenv("DB_NAME"',
            'os.getenv("DB_USER"',
            'os.getenv("DB_PASSWORD"',
            'os.getenv("DB_ECHO"',
        ]

        for pattern in deprecated_patterns:
            assert pattern not in source, f"Found deprecated pattern: {pattern}"


class TestDatabaseUrlConstruction:
    """Test that database URL is correctly constructed from settings."""

    def setup_method(self):
        """Reset state before each test."""
        clear_settings_cache()
        import ktrdr.api.database as db_module

        db_module._engine = None
        db_module._session_factory = None

    def teardown_method(self):
        """Clear cache after each test."""
        clear_settings_cache()

    def test_url_format_is_asyncpg(self):
        """Database URL should use asyncpg driver."""
        from ktrdr.api.database import get_database_url

        url = get_database_url()
        assert url.startswith("postgresql+asyncpg://")

    def test_url_contains_default_values(self):
        """With no env vars set, URL should use defaults."""
        from ktrdr.api.database import get_database_url

        url = get_database_url()
        # Default values: localhost:5432/ktrdr with user ktrdr
        assert "localhost" in url
        assert "5432" in url
        assert "ktrdr" in url
