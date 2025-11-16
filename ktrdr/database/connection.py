"""
Database connection utilities for PostgreSQL.

Provides connection pooling, configuration management, and helper functions
for database operations.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from psycopg2.pool import SimpleConnectionPool  # type: ignore[import-untyped]

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "ktrdr"
    user: str = "ktrdr_admin"
    password: str = "ktrdr_dev_password"
    pool_min_size: int = 2
    pool_max_size: int = 10
    pool_timeout: int = 30

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Create database config from environment variables.

        Environment variables:
        - POSTGRES_HOST
        - POSTGRES_PORT
        - POSTGRES_DB
        - POSTGRES_USER
        - POSTGRES_PASSWORD

        Returns:
            DatabaseConfig instance
        """
        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "ktrdr"),
            user=os.getenv("POSTGRES_USER", "ktrdr_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password"),
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "DatabaseConfig":
        """
        Create database config from YAML file.

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            DatabaseConfig instance

        Raises:
            FileNotFoundError: If YAML file not found
            yaml.YAMLError: If YAML parsing fails
        """
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_file) as f:
            config_data = yaml.safe_load(f)

        db_config = config_data.get("database", {})

        return cls(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config.get("database", "ktrdr"),
            user=db_config.get("user", "ktrdr_admin"),
            password=db_config.get("password", "ktrdr_dev_password"),
            pool_min_size=db_config.get("pool", {}).get("min_size", 2),
            pool_max_size=db_config.get("pool", {}).get("max_size", 10),
            pool_timeout=db_config.get("pool", {}).get("timeout", 30),
        )

    @property
    def database_url(self) -> str:
        """
        Construct PostgreSQL DATABASE_URL.

        Returns:
            DATABASE_URL string
        """
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class DatabaseConnection:
    """
    Database connection manager with connection pooling.

    Manages a connection pool for efficient database access.
    Supports context manager for automatic connection cleanup.
    """

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database connection pool.

        Args:
            config: Database configuration
        """
        self.config = config
        self._pool: Optional[SimpleConnectionPool] = None
        self._init_pool()

    def _init_pool(self) -> None:
        """Initialize connection pool."""
        try:
            self._pool = SimpleConnectionPool(
                self.config.pool_min_size,
                self.config.pool_max_size,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            logger.info(
                f"Database connection pool initialized: "
                f"{self.config.pool_min_size}-{self.config.pool_max_size} connections"
            )
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise

    def get_connection(self):
        """
        Get connection from pool.

        Returns:
            psycopg2 connection object

        Raises:
            psycopg2.OperationalError: If connection cannot be obtained
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized")
        try:
            conn = self._pool.getconn()
            return conn
        except Exception as e:
            logger.error(f"Failed to get database connection: {e}")
            raise

    def release_connection(self, conn) -> None:
        """
        Release connection back to pool.

        Args:
            conn: Connection to release
        """
        if self._pool is None:
            raise RuntimeError("Connection pool not initialized")
        try:
            self._pool.putconn(conn)
        except Exception as e:
            logger.error(f"Failed to release database connection: {e}")
            raise

    def __enter__(self):
        """Context manager entry: get connection from pool."""
        self._current_conn = self.get_connection()
        return self._current_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: release connection back to pool."""
        if hasattr(self, "_current_conn"):
            self.release_connection(self._current_conn)
            delattr(self, "_current_conn")
        return False

    def close(self) -> None:
        """Close all connections in pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connection pool closed")


# Singleton instances
_database_config: Optional[DatabaseConfig] = None
_database_connection: Optional[DatabaseConnection] = None


def get_database_config() -> DatabaseConfig:
    """
    Get singleton database configuration instance.

    Returns:
        DatabaseConfig instance
    """
    global _database_config
    if _database_config is None:
        # Try to load from YAML first, fall back to env
        config_path = Path(__file__).parent.parent.parent / "config" / "database.yaml"
        if config_path.exists():
            _database_config = DatabaseConfig.from_yaml(str(config_path))
            logger.info("Database config loaded from YAML")
        else:
            _database_config = DatabaseConfig.from_env()
            logger.info("Database config loaded from environment variables")
    return _database_config


def get_database_connection() -> DatabaseConnection:
    """
    Get singleton database connection instance.

    Returns:
        DatabaseConnection instance
    """
    global _database_connection
    if _database_connection is None:
        config = get_database_config()
        _database_connection = DatabaseConnection(config)
    return _database_connection
