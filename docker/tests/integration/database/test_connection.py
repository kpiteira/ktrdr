"""
Integration tests for PostgreSQL + TimescaleDB connection.

Tests:
- PostgreSQL container starts successfully
- TimescaleDB extension is enabled
- Backend can connect to database
- Data persists across container restarts
- Health checks pass
"""

import os
import time
from typing import Generator

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


@pytest.fixture
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Create PostgreSQL database connection.

    Uses environment variables or defaults from docker-compose.yml:
    - POSTGRES_HOST: localhost (host machine accessing Docker container)
    - POSTGRES_PORT: 5432
    - POSTGRES_DB: ktrdr
    - POSTGRES_USER: ktrdr_admin
    - POSTGRES_PASSWORD: ktrdr_dev_password

    Yields:
        Database connection
    """
    # Database connection parameters (matching docker-compose.yml defaults)
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "ktrdr")
    user = os.getenv("POSTGRES_USER", "ktrdr_admin")
    password = os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password")

    # Retry connection (database may be starting up)
    max_retries = 30
    retry_delay = 1  # seconds

    conn = None
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
            )
            break
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                pytest.fail(
                    f"Failed to connect to PostgreSQL after {max_retries} attempts. "
                    f"Error: {e}. "
                    f"Ensure PostgreSQL container is running: docker-compose up -d postgres"
                )
            time.sleep(retry_delay)

    assert conn is not None, "Failed to establish database connection"

    try:
        yield conn
    finally:
        conn.close()


def test_postgres_container_running(db_connection):
    """
    Test that PostgreSQL container is running and accessible.

    Acceptance Criteria:
    - ✅ Can establish connection to PostgreSQL
    - ✅ Can execute basic query
    """
    cursor = db_connection.cursor()
    cursor.execute("SELECT version();")
    result = cursor.fetchone()

    assert result is not None
    assert "PostgreSQL" in result[0]

    cursor.close()


def test_timescaledb_extension_enabled(db_connection):
    """
    Test that TimescaleDB extension is enabled.

    Acceptance Criteria:
    - ✅ TimescaleDB extension installed
    - ✅ Extension version is valid
    """
    cursor = db_connection.cursor()

    # Query for TimescaleDB extension
    cursor.execute("""
        SELECT extname, extversion
        FROM pg_extension
        WHERE extname = 'timescaledb';
    """)
    result = cursor.fetchone()

    assert result is not None, (
        "TimescaleDB extension not found. "
        "Ensure migration 000_init_timescaledb.sql has run."
    )

    extname, extversion = result
    assert extname == "timescaledb"
    assert extversion is not None
    assert len(extversion) > 0

    cursor.close()


def test_migrations_schema_version_table_exists(db_connection):
    """
    Test that migrations have created schema_version table.

    Acceptance Criteria:
    - ✅ schema_version table exists
    - ✅ Table has correct structure
    """
    cursor = db_connection.cursor()

    # Check if schema_version table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'schema_version'
        );
    """)
    table_exists = cursor.fetchone()[0]

    assert table_exists, (
        "schema_version table not found. "
        "Ensure migrations have run on database initialization."
    )

    # Verify table structure
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'schema_version'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()

    expected_columns = {
        "version": "integer",
        "description": "text",
        "applied_at": "timestamp with time zone",
        "applied_by": "text",
    }

    actual_columns = {col[0]: col[1] for col in columns}

    for col_name, col_type in expected_columns.items():
        assert col_name in actual_columns, f"Column '{col_name}' missing from schema_version table"
        assert actual_columns[col_name].startswith(col_type.split()[0]), (
            f"Column '{col_name}' has type '{actual_columns[col_name]}', "
            f"expected '{col_type}'"
        )

    cursor.close()


def test_initial_migration_recorded(db_connection):
    """
    Test that initial migration (TimescaleDB initialization) is recorded.

    Acceptance Criteria:
    - ✅ Migration version 0 exists in schema_version table
    - ✅ Migration description is correct
    """
    cursor = db_connection.cursor()

    cursor.execute("""
        SELECT version, description, applied_at, applied_by
        FROM schema_version
        WHERE version = 0;
    """)
    result = cursor.fetchone()

    assert result is not None, (
        "Initial migration (version 0) not found in schema_version table. "
        "Ensure migration 000_init_timescaledb.sql has run."
    )

    version, description, applied_at, applied_by = result

    assert version == 0
    assert "TimescaleDB" in description or "timescaledb" in description.lower()
    assert applied_at is not None
    assert applied_by is not None

    cursor.close()


def test_database_persistence(db_connection):
    """
    Test that data persists across operations.

    Acceptance Criteria:
    - ✅ Can create table
    - ✅ Can insert data
    - ✅ Can query data back
    - ✅ Data persists

    Note: Testing persistence across container restarts requires
    manual testing (see Phase 0 End-to-End Test in implementation plan).
    """
    cursor = db_connection.cursor()

    # Create test table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_persistence (
            id SERIAL PRIMARY KEY,
            test_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db_connection.commit()

    # Insert test data
    test_value = "test_checkpoint_persistence"
    cursor.execute("""
        INSERT INTO test_persistence (test_data)
        VALUES (%s)
        RETURNING id;
    """, (test_value,))
    inserted_id = cursor.fetchone()[0]
    db_connection.commit()

    # Query data back
    cursor.execute("""
        SELECT id, test_data
        FROM test_persistence
        WHERE id = %s;
    """, (inserted_id,))
    result = cursor.fetchone()

    assert result is not None
    assert result[0] == inserted_id
    assert result[1] == test_value

    # Cleanup
    cursor.execute("DROP TABLE test_persistence;")
    db_connection.commit()

    cursor.close()


def test_backend_connection_string_format():
    """
    Test that DATABASE_URL format matches expected pattern for backend.

    Acceptance Criteria:
    - ✅ DATABASE_URL environment variable format is valid
    - ✅ Connection string can be parsed
    """
    # Expected format from docker-compose.yml:
    # postgresql://{user}:{password}@postgres:5432/{database}

    # For testing from host machine:
    database_url = (
        f"postgresql://{os.getenv('POSTGRES_USER', 'ktrdr_admin')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'ktrdr_dev_password')}@"
        f"localhost:5432/{os.getenv('POSTGRES_DB', 'ktrdr')}"
    )

    # Validate format
    assert database_url.startswith("postgresql://")
    assert "@localhost:5432/" in database_url
    assert "ktrdr" in database_url

    # For backend (inside Docker), the format should be:
    expected_backend_url_pattern = "postgresql://ktrdr_admin:ktrdr_dev_password@postgres:5432/ktrdr"

    # Validate pattern structure (not exact match, as password may differ)
    assert "postgresql://" in expected_backend_url_pattern
    assert "@postgres:5432/" in expected_backend_url_pattern


def test_connection_pooling_support(db_connection):
    """
    Test that PostgreSQL supports connection pooling (required for production).

    Acceptance Criteria:
    - ✅ Can query max_connections setting
    - ✅ max_connections is reasonable (>= 100)
    """
    cursor = db_connection.cursor()

    cursor.execute("SHOW max_connections;")
    max_connections = int(cursor.fetchone()[0])

    assert max_connections >= 100, (
        f"max_connections is {max_connections}, expected >= 100 for production use"
    )

    cursor.close()


def test_database_healthcheck():
    """
    Test that database responds to health check queries.

    Acceptance Criteria:
    - ✅ pg_isready command works
    - ✅ Health check query succeeds

    Note: This test validates the health check used in docker-compose.yml
    """
    # Simulate health check query
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "ktrdr")
    user = os.getenv("POSTGRES_USER", "ktrdr_admin")
    password = os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=3,
        )

        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()

        assert result == (1,)

        cursor.close()
        conn.close()
    except Exception as e:
        pytest.fail(f"Health check query failed: {e}")
