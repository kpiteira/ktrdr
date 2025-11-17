"""
Unit tests for database connection utilities.

Tests database connection management, connection pooling, and error handling.
"""

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from ktrdr.database.connection import (
    DatabaseConfig,
    DatabaseConnection,
    get_database_config,
    get_database_connection,
)


class TestDatabaseConfig:
    """Test database configuration loading."""

    def test_database_config_from_env(self, monkeypatch):
        """Test loading database config from environment variables."""
        monkeypatch.setenv("POSTGRES_HOST", "test-host")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

        config = DatabaseConfig.from_env()

        assert config.host == "test-host"
        assert config.port == 5433
        assert config.database == "test_db"
        assert config.user == "test_user"
        assert config.password == "test_password"

    def test_database_config_defaults(self):
        """Test database config uses defaults when env vars not set."""
        config = DatabaseConfig.from_env()

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "ktrdr"
        assert config.user == "ktrdr_admin"
        # password should have a default

    def test_database_config_from_yaml(self, tmp_path):
        """Test loading database config from YAML file."""
        yaml_content = """
database:
  host: yaml-host
  port: 5434
  database: yaml_db
  user: yaml_user
  password: yaml_password
  pool:
    min_size: 2
    max_size: 10
    timeout: 30
"""
        yaml_file = tmp_path / "database.yaml"
        yaml_file.write_text(yaml_content)

        config = DatabaseConfig.from_yaml(str(yaml_file))

        assert config.host == "yaml-host"
        assert config.port == 5434
        assert config.database == "yaml_db"
        assert config.user == "yaml_user"
        assert config.password == "yaml_password"
        assert config.pool_min_size == 2
        assert config.pool_max_size == 10
        assert config.pool_timeout == 30

    def test_database_url_construction(self):
        """Test DATABASE_URL string construction."""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="ktrdr",
            user="test_user",
            password="test_pass",
        )

        expected_url = "postgresql://test_user:test_pass@localhost:5432/ktrdr"
        assert config.database_url == expected_url


class TestDatabaseConnection:
    """Test database connection management."""

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_database_connection_init(self, mock_pool_class):
        """Test DatabaseConnection initialization creates connection pool."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="ktrdr",
            user="test_user",
            password="test_pass",
            pool_min_size=2,
            pool_max_size=10,
        )

        db = DatabaseConnection(config)

        # Verify pool was created with correct parameters
        mock_pool_class.assert_called_once_with(
            2,  # minconn
            10,  # maxconn
            host="localhost",
            port=5432,
            database="ktrdr",
            user="test_user",
            password="test_pass",
        )
        assert db._pool == mock_pool

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_get_connection(self, mock_pool_class):
        """Test getting connection from pool."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        conn = db.get_connection()

        mock_pool.getconn.assert_called_once()
        assert conn == mock_conn

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_release_connection(self, mock_pool_class):
        """Test releasing connection back to pool."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        db.release_connection(mock_conn)

        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_context_manager(self, mock_pool_class):
        """Test DatabaseConnection as context manager."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        with db as conn:
            assert conn == mock_conn

        # Verify connection released after context
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_context_manager_with_exception(self, mock_pool_class):
        """Test context manager releases connection even on exception."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        with pytest.raises(ValueError):
            with db as _:
                raise ValueError("Test error")

        # Verify connection still released
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_close_all_connections(self, mock_pool_class):
        """Test closing all connections in pool."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        db.close()

        mock_pool.closeall.assert_called_once()

    @patch("ktrdr.database.connection.SimpleConnectionPool")
    def test_connection_error_handling(self, mock_pool_class):
        """Test connection error handling."""
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = psycopg2.OperationalError("Connection failed")
        mock_pool_class.return_value = mock_pool

        config = DatabaseConfig()
        db = DatabaseConnection(config)

        with pytest.raises(psycopg2.OperationalError):
            db.get_connection()


class TestDatabaseHelpers:
    """Test database helper functions."""

    def test_get_database_config(self):
        """Test get_database_config returns singleton instance."""
        # Reset singleton to force fresh load
        import ktrdr.database.connection as db_module

        db_module._database_config = None

        config1 = get_database_config()
        config2 = get_database_config()

        assert config1 == config2
        assert config1 is config2  # Same instance (singleton)

    @patch("ktrdr.database.connection.DatabaseConnection")
    def test_get_database_connection(self, mock_db_class):
        """Test get_database_connection returns singleton instance."""
        # Reset singletons to force fresh creation
        import ktrdr.database.connection as db_module

        db_module._database_connection = None
        db_module._database_config = None

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        db1 = get_database_connection()
        db2 = get_database_connection()

        assert db1 == db2
        # Should only create instance once (singleton)
        assert mock_db_class.call_count == 1
