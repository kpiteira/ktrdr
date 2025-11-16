# TimescaleDB Integration Implementation Plan - Phases 0-2

**Version**: 1.0
**Status**: 📋 **READY FOR IMPLEMENTATION**
**Date**: 2025-11-15
**Phases Covered**: 0-2 (PostgreSQL infrastructure, TimescaleDB backend, CSV import)

---

## 📋 Plan Navigation

- **This Document**: Phases 0-2 (Infrastructure → Import)
- **Next Steps**: [IMPLEMENTATION_PLAN_PHASES_3-4.md](IMPLEMENTATION_PLAN_PHASES_3-4.md) - Migration & Cutover

---

## Overview

This implementation plan uses **Test-Driven Development** with **vertical slices**. Each phase delivers a complete, testable feature.

**Technology Stack**:
- **PostgreSQL + TimescaleDB**: Time-series optimized database (already running)
- **SQLAlchemy**: Database ORM with connection pooling (QueuePool)
- **psycopg2-binary**: PostgreSQL adapter for Python

**Quality Gates** (every task):

- Write tests FIRST (TDD)
- Pass ALL unit tests: `make test-unit`
- Pass quality checks: `make quality`
- Result in ONE commit

**Vertical Approach**: Each phase ends with a working, testable system feature.

All work will be done on a single feature branch: `feature/timescaledb-integration`

---

## Phase Structure

- **Phase**: A complete **vertical slice** delivering end-to-end functionality
- **Task**: A single, testable unit of work building toward the phase goal
- **Key**: Each phase ends with something you can **actually test and use**

---

## Phase 0: PostgreSQL + TimescaleDB Infrastructure Verification

**Goal**: Verify existing PostgreSQL + TimescaleDB infrastructure is working correctly

**Why This First**: Before writing any Python code, confirm the database foundation is solid!

**Context**: PostgreSQL + TimescaleDB is already running in Docker (not yet merged to main branch). This phase verifies the existing setup works as expected.

**End State**:

- PostgreSQL + TimescaleDB verified running and healthy
- Schema migrations verified applied correctly
- Connection pooling verified working from backend
- **TESTABLE**: All integration tests pass, can query hypertables, TimescaleDB extension loaded

---

### Task 0.1: Verify PostgreSQL + TimescaleDB Infrastructure

**Objective**: Verify existing PostgreSQL + TimescaleDB setup is running and accessible

**TDD Approach**:

- Integration tests verify database connectivity
- Manual verification of Docker Compose health
- Validation: PostgreSQL healthy, TimescaleDB extension loaded, backend can connect

**Implementation**:

1. Start TimescaleDB container (already configured):

   ```bash
   # Start development environment
   docker-compose -f docker/docker-compose.dev.yml up -d timescaledb
   ```

2. Verify container is healthy:

   ```bash
   # Check health status
   docker-compose -f docker/docker-compose.dev.yml ps timescaledb
   # Should show: State = Up (healthy)

   # Check logs for successful startup
   docker-compose -f docker/docker-compose.dev.yml logs timescaledb | tail -20
   # Should see: "database system is ready to accept connections"
   ```

3. Verify TimescaleDB extension is loaded:

   ```bash
   # Check extension is available and installed
   docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'timescaledb';"
   # Should show version numbers for both columns

   # List all extensions
   docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "\dx"
   # Should include: timescaledb | X.X.X
   ```

4. Verify backend environment variables are set:

   ```bash
   # Check backend has DB_TYPE=postgresql
   docker exec -it ktrdr-backend env | grep DB_
   # Should show:
   # DB_TYPE=postgresql
   # DB_HOST=timescaledb
   # DB_PORT=5432
   # DB_NAME=ktrdr_dev
   # DB_USER=ktrdr_dev
   # DB_POOL_SIZE=20
   # DB_MAX_OVERFLOW=10
   ```

**Quality Gate**:

```bash
# Verify TimescaleDB is running and healthy
docker-compose -f docker/docker-compose.dev.yml ps timescaledb  # Should be healthy
docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "\dx"  # List extensions

# All existing tests still pass
make test-unit
make quality
```

**Commit**: `test(db): verify PostgreSQL + TimescaleDB infrastructure`

**Estimated Time**: 30 minutes

---

### Task 0.2: Verify Schema Migrations

**Objective**: Verify existing database schema migrations have been applied correctly

**TDD Approach**:

1. Create integration tests that verify schema exists
2. Test TimescaleDB hypertable creation
3. Test indexes and constraints
4. Verify no compression is enabled (per design)

**Implementation**:

1. Verify `db/init/01_enable_timescaledb.sql` exists and is correct:

   ```sql
   -- Enable TimescaleDB extension
   CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

   -- Verify extension is loaded
   SELECT default_version, installed_version
   FROM pg_available_extensions
   WHERE name = 'timescaledb';
   ```

2. Create `db/migrations/001_create_price_data_table.sql`:

   ```sql
   -- Migration: Create price_data hypertable for OHLCV data
   -- Version: 001
   -- Date: 2025-11-15

   -- Create price_data table
   CREATE TABLE IF NOT EXISTS price_data (
       -- Time dimension (required for hypertable)
       time TIMESTAMPTZ NOT NULL,

       -- Symbol and timeframe (partitioning dimensions)
       symbol VARCHAR(32) NOT NULL,
       timeframe VARCHAR(8) NOT NULL,

       -- OHLCV data
       open DOUBLE PRECISION NOT NULL,
       high DOUBLE PRECISION NOT NULL,
       low DOUBLE PRECISION NOT NULL,
       close DOUBLE PRECISION NOT NULL,
       volume DOUBLE PRECISION NOT NULL,

       -- Metadata
       source VARCHAR(32) DEFAULT 'ib',
       created_at TIMESTAMPTZ DEFAULT NOW(),

       -- Ensure data quality
       CONSTRAINT price_data_ohlc_check CHECK (
           high >= low AND
           high >= open AND
           high >= close AND
           low <= open AND
           low <= close
       ),
       CONSTRAINT price_data_volume_check CHECK (volume >= 0)
   );

   -- Create hypertable (partitioned by time)
   -- Chunk interval: 7 days (good balance for intraday data)
   SELECT create_hypertable(
       'price_data',
       'time',
       chunk_time_interval => INTERVAL '7 days',
       if_not_exists => TRUE
   );

   -- Add space partitioning by symbol (optional, improves query performance)
   -- This creates separate chunks for each symbol
   SELECT add_dimension(
       'price_data',
       'symbol',
       number_partitions => 4,
       if_not_exists => TRUE
   );

   -- Create indexes for common query patterns

   -- Primary index: symbol + timeframe + time (most common query)
   CREATE INDEX IF NOT EXISTS idx_price_data_symbol_timeframe_time
   ON price_data (symbol, timeframe, time DESC);

   -- Time-only index (for range queries across all symbols)
   CREATE INDEX IF NOT EXISTS idx_price_data_time
   ON price_data (time DESC);

   -- Symbol-only index (for per-symbol queries)
   CREATE INDEX IF NOT EXISTS idx_price_data_symbol
   ON price_data (symbol);

   -- Source tracking index (for data quality monitoring)
   CREATE INDEX IF NOT EXISTS idx_price_data_source
   ON price_data (source);

   -- Composite index for symbol coverage queries
   CREATE INDEX IF NOT EXISTS idx_price_data_symbol_timeframe
   ON price_data (symbol, timeframe);

   -- Add table comment
   COMMENT ON TABLE price_data IS 'TimescaleDB hypertable storing OHLCV price data for all symbols and timeframes';

   -- Add retention policy (delete data older than 10 years)
   SELECT add_retention_policy(
       'price_data',
       INTERVAL '10 years',
       if_not_exists => TRUE
   );
   ```

3. Create `db/migrations/002_create_indicators_table.sql`:

   ```sql
   -- Migration: Create indicators hypertable for technical indicators
   -- Version: 002
   -- Date: 2025-11-15

   -- Create indicators table
   CREATE TABLE IF NOT EXISTS indicators (
       -- Time dimension (required for hypertable)
       time TIMESTAMPTZ NOT NULL,

       -- Symbol and timeframe (partitioning dimensions)
       symbol VARCHAR(32) NOT NULL,
       timeframe VARCHAR(8) NOT NULL,

       -- Indicator name (e.g., 'sma_20', 'rsi_14', 'macd')
       indicator_name VARCHAR(64) NOT NULL,

       -- Indicator value (stored as JSONB for flexibility)
       -- Examples:
       --   Simple value: {"value": 1.234}
       --   Multiple values: {"fast": 1.234, "slow": 5.678, "signal": 3.456}
       value JSONB NOT NULL,

       -- Metadata
       created_at TIMESTAMPTZ DEFAULT NOW(),

       -- Ensure valid indicator name
       CONSTRAINT indicators_name_check CHECK (
           indicator_name ~ '^[a-z0-9_]+$'
       )
   );

   -- Create hypertable (partitioned by time)
   -- Chunk interval: 7 days
   SELECT create_hypertable(
       'indicators',
       'time',
       chunk_time_interval => INTERVAL '7 days',
       if_not_exists => TRUE
   );

   -- Add space partitioning by symbol
   SELECT add_dimension(
       'indicators',
       'symbol',
       number_partitions => 4,
       if_not_exists => TRUE
   );

   -- Create indexes for common query patterns

   -- Primary index: symbol + timeframe + indicator + time
   CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe_indicator_time
   ON indicators (symbol, timeframe, indicator_name, time DESC);

   -- Time-only index
   CREATE INDEX IF NOT EXISTS idx_indicators_time
   ON indicators (time DESC);

   -- Symbol + indicator index (for all timeframes of one indicator)
   CREATE INDEX IF NOT EXISTS idx_indicators_symbol_indicator
   ON indicators (symbol, indicator_name);

   -- JSONB GIN index for value queries (optional, for complex queries on indicator values)
   CREATE INDEX IF NOT EXISTS idx_indicators_value_gin
   ON indicators USING GIN (value);

   -- Add table comment
   COMMENT ON TABLE indicators IS 'TimescaleDB hypertable storing technical indicator values';

   -- Add retention policy (delete data older than 10 years)
   SELECT add_retention_policy(
       'indicators',
       INTERVAL '10 years',
       if_not_exists => TRUE
   );
   ```

4. Create `db/migrations/run_migrations.sh`:

   ```bash
   #!/bin/bash
   # Run database migrations in order

   set -e

   DB_HOST="${DB_HOST:-localhost}"
   DB_PORT="${DB_PORT:-5432}"
   DB_NAME="${DB_NAME:-ktrdr}"
   DB_USER="${DB_USER:-ktrdr}"

   MIGRATIONS_DIR="$(dirname "$0")"

   echo "Running migrations against ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

   # Run each migration in order
   for migration in "$MIGRATIONS_DIR"/*.sql; do
       echo "Running migration: $(basename "$migration")"
       psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration"
   done

   echo "✓ All migrations completed successfully"
   ```

5. Make script executable:

   ```bash
   chmod +x db/migrations/run_migrations.sh
   ```

6. Create integration test `tests/integration/db/test_schema_migrations.py`:

   ```python
   """Integration tests for database schema migrations."""

   import os
   import pytest
   import psycopg2
   from psycopg2.extras import RealDictCursor


   @pytest.fixture
   def db_connection():
       """Create database connection for testing."""
       conn = psycopg2.connect(
           host=os.getenv("DB_HOST", "localhost"),
           port=int(os.getenv("DB_PORT", "5432")),
           dbname=os.getenv("DB_NAME", "ktrdr_dev"),
           user=os.getenv("DB_USER", "ktrdr_dev"),
           password=os.getenv("DB_PASSWORD", "ktrdr_dev_password"),
       )
       yield conn
       conn.close()


   @pytest.mark.integration
   class TestSchemaMigrations:
       """Test database schema migrations."""

       def test_timescaledb_extension_loaded(self, db_connection):
           """Test that TimescaleDB extension is loaded."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb'"
               )
               result = cursor.fetchone()

               assert result is not None
               assert result["installed_version"] is not None

       def test_price_data_table_exists(self, db_connection):
           """Test that price_data table exists."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT table_name
                   FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = 'price_data'
                   """
               )
               result = cursor.fetchone()

               assert result is not None
               assert result["table_name"] == "price_data"

       def test_price_data_is_hypertable(self, db_connection):
           """Test that price_data is a TimescaleDB hypertable."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT hypertable_name
                   FROM timescaledb_information.hypertables
                   WHERE hypertable_name = 'price_data'
                   """
               )
               result = cursor.fetchone()

               assert result is not None
               assert result["hypertable_name"] == "price_data"

       def test_price_data_columns(self, db_connection):
           """Test that price_data has correct columns."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT column_name, data_type
                   FROM information_schema.columns
                   WHERE table_name = 'price_data'
                   ORDER BY ordinal_position
                   """
               )
               columns = {row["column_name"]: row["data_type"] for row in cursor.fetchall()}

               # Verify required columns
               assert "time" in columns
               assert "symbol" in columns
               assert "timeframe" in columns
               assert "open" in columns
               assert "high" in columns
               assert "low" in columns
               assert "close" in columns
               assert "volume" in columns
               assert "source" in columns
               assert "created_at" in columns

       def test_price_data_indexes(self, db_connection):
           """Test that price_data has required indexes."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT indexname
                   FROM pg_indexes
                   WHERE tablename = 'price_data'
                   """
               )
               indexes = [row["indexname"] for row in cursor.fetchall()]

               # Verify key indexes exist
               assert "idx_price_data_symbol_timeframe_time" in indexes
               assert "idx_price_data_time" in indexes
               assert "idx_price_data_symbol" in indexes

       def test_indicators_table_exists(self, db_connection):
           """Test that indicators table exists."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT table_name
                   FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = 'indicators'
                   """
               )
               result = cursor.fetchone()

               assert result is not None
               assert result["table_name"] == "indicators"

       def test_indicators_is_hypertable(self, db_connection):
           """Test that indicators is a TimescaleDB hypertable."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT hypertable_name
                   FROM timescaledb_information.hypertables
                   WHERE hypertable_name = 'indicators'
                   """
               )
               result = cursor.fetchone()

               assert result is not None
               assert result["hypertable_name"] == "indicators"

       def test_indicators_columns(self, db_connection):
           """Test that indicators has correct columns."""
           with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
               cursor.execute(
                   """
                   SELECT column_name, data_type
                   FROM information_schema.columns
                   WHERE table_name = 'indicators'
                   ORDER BY ordinal_position
                   """
               )
               columns = {row["column_name"]: row["data_type"] for row in cursor.fetchall()}

               # Verify required columns
               assert "time" in columns
               assert "symbol" in columns
               assert "timeframe" in columns
               assert "indicator_name" in columns
               assert "value" in columns
               assert columns["value"] == "jsonb"  # JSONB type
   ```

**Quality Gate**:

```bash
# Start database (if not already running)
docker-compose -f docker/docker-compose.dev.yml up -d timescaledb

# Wait for healthy
sleep 10

# Verify migrations have been applied (check tables exist)
docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "\dt"  # Should show price_data, indicators
docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "SELECT * FROM timescaledb_information.hypertables;"  # Should list both hypertables

# Run integration tests (these will verify schema correctness)
make test-integration  # Should pass all schema tests

make test-unit
make quality
```

**Commit**: `test(db): verify TimescaleDB schema migrations applied correctly`

**Estimated Time**: 2 hours

---

### Task 0.3: Verify Database Connection and Pooling

**Objective**: Verify database connection configuration and SQLAlchemy connection pooling

**TDD Approach**:

1. Create unit tests for database configuration
2. Create integration tests for connection pooling
3. Test connection works from Python code

**Implementation**:

1. Verify dependencies exist in `pyproject.toml`:

   ```toml
   dependencies = [
       # ... existing dependencies ...
       "psycopg2-binary>=2.9.9",
       "sqlalchemy>=2.0.23",
   ]
   ```

2. Create `ktrdr/config/database.py`:

   ```python
   """Database configuration and connection management."""

   import os
   from typing import Optional
   from sqlalchemy import create_engine, Engine
   from sqlalchemy.pool import QueuePool
   from sqlalchemy.orm import sessionmaker, Session
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   class DatabaseConfig:
       """Database configuration."""

       def __init__(self):
           """Initialize database configuration from environment variables."""
           self.db_type = os.getenv("DB_TYPE", "csv")  # csv, parquet, or postgresql
           self.host = os.getenv("DB_HOST", "localhost")
           self.port = int(os.getenv("DB_PORT", "5432"))
           self.database = os.getenv("DB_NAME", "ktrdr")
           self.user = os.getenv("DB_USER", "ktrdr")
           self.password = os.getenv("DB_PASSWORD", "")
           self.pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
           self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
           self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
           self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))

       @property
       def is_postgresql(self) -> bool:
           """Check if using PostgreSQL/TimescaleDB."""
           return self.db_type == "postgresql"

       @property
       def connection_url(self) -> str:
           """Get SQLAlchemy connection URL."""
           if not self.is_postgresql:
               raise ValueError(f"Connection URL not available for db_type={self.db_type}")

           return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

       def __repr__(self) -> str:
           """String representation (hide password)."""
           return (
               f"DatabaseConfig(type={self.db_type}, host={self.host}, "
               f"port={self.port}, database={self.database}, user={self.user})"
           )


   class DatabaseConnectionManager:
       """Manages database connection pooling."""

       def __init__(self, config: Optional[DatabaseConfig] = None):
           """
           Initialize connection manager.

           Args:
               config: Database configuration (uses default if None)
           """
           self.config = config or DatabaseConfig()
           self._engine: Optional[Engine] = None
           self._session_factory: Optional[sessionmaker] = None

       @property
       def engine(self) -> Engine:
           """
           Get or create SQLAlchemy engine.

           Returns:
               SQLAlchemy engine with connection pooling

           Raises:
               ValueError: If database type is not PostgreSQL
           """
           if self._engine is None:
               if not self.config.is_postgresql:
                   raise ValueError(
                       f"Cannot create engine for db_type={self.config.db_type}. "
                       "Use DataRepository for file-based storage."
                   )

               logger.info(f"Creating database engine: {self.config}")

               self._engine = create_engine(
                   self.config.connection_url,
                   poolclass=QueuePool,
                   pool_size=self.config.pool_size,
                   max_overflow=self.config.max_overflow,
                   pool_timeout=self.config.pool_timeout,
                   pool_recycle=self.config.pool_recycle,
                   pool_pre_ping=True,  # Verify connections before using
                   echo=False,  # Set to True for SQL logging
               )

               logger.info(
                   f"Database engine created: pool_size={self.config.pool_size}, "
                   f"max_overflow={self.config.max_overflow}"
               )

           return self._engine

       @property
       def session_factory(self) -> sessionmaker:
           """
           Get or create session factory.

           Returns:
               SQLAlchemy session factory
           """
           if self._session_factory is None:
               self._session_factory = sessionmaker(bind=self.engine)
           return self._session_factory

       def get_session(self) -> Session:
           """
           Get new database session.

           Returns:
               SQLAlchemy session (must be closed by caller)

           Example:
               ```python
               manager = DatabaseConnectionManager()
               session = manager.get_session()
               try:
                   # Use session
                   result = session.execute("SELECT 1")
               finally:
                   session.close()
               ```
           """
           return self.session_factory()

       def test_connection(self) -> bool:
           """
           Test database connection.

           Returns:
               True if connection successful, False otherwise
           """
           try:
               with self.engine.connect() as conn:
                   result = conn.execute("SELECT 1")
                   result.fetchone()
               logger.info("Database connection test successful")
               return True
           except Exception as e:
               logger.error(f"Database connection test failed: {e}")
               return False

       def close(self):
           """Close all connections and dispose of engine."""
           if self._engine:
               logger.info("Closing database connection pool")
               self._engine.dispose()
               self._engine = None
               self._session_factory = None


   # Global connection manager (singleton)
   _connection_manager: Optional[DatabaseConnectionManager] = None


   def get_connection_manager() -> DatabaseConnectionManager:
       """
       Get global database connection manager.

       Returns:
           DatabaseConnectionManager singleton
       """
       global _connection_manager
       if _connection_manager is None:
           _connection_manager = DatabaseConnectionManager()
       return _connection_manager


   def get_db_session() -> Session:
       """
       Get database session (convenience function).

       Returns:
           SQLAlchemy session
       """
       return get_connection_manager().get_session()
   ```

3. Create unit tests `tests/unit/config/test_database.py`:

   ```python
   """Unit tests for database configuration."""

   import os
   import pytest
   from unittest.mock import patch, MagicMock
   from ktrdr.config.database import (
       DatabaseConfig,
       DatabaseConnectionManager,
       get_connection_manager,
   )


   class TestDatabaseConfig:
       """Test DatabaseConfig class."""

       def test_default_config(self):
           """Test default configuration values."""
           with patch.dict(os.environ, {}, clear=True):
               config = DatabaseConfig()

               assert config.db_type == "csv"
               assert config.host == "localhost"
               assert config.port == 5432
               assert config.database == "ktrdr"
               assert config.user == "ktrdr"
               assert config.pool_size == 20
               assert config.max_overflow == 10

       def test_custom_config_from_env(self):
           """Test configuration from environment variables."""
           env_vars = {
               "DB_TYPE": "postgresql",
               "DB_HOST": "timescaledb",
               "DB_PORT": "5433",
               "DB_NAME": "ktrdr_test",
               "DB_USER": "test_user",
               "DB_PASSWORD": "test_password",
               "DB_POOL_SIZE": "50",
               "DB_MAX_OVERFLOW": "20",
           }

           with patch.dict(os.environ, env_vars):
               config = DatabaseConfig()

               assert config.db_type == "postgresql"
               assert config.host == "timescaledb"
               assert config.port == 5433
               assert config.database == "ktrdr_test"
               assert config.user == "test_user"
               assert config.password == "test_password"
               assert config.pool_size == 50
               assert config.max_overflow == 20

       def test_is_postgresql(self):
           """Test is_postgresql property."""
           with patch.dict(os.environ, {"DB_TYPE": "postgresql"}):
               config = DatabaseConfig()
               assert config.is_postgresql is True

           with patch.dict(os.environ, {"DB_TYPE": "csv"}):
               config = DatabaseConfig()
               assert config.is_postgresql is False

       def test_connection_url(self):
           """Test connection URL generation."""
           env_vars = {
               "DB_TYPE": "postgresql",
               "DB_HOST": "localhost",
               "DB_PORT": "5432",
               "DB_NAME": "ktrdr",
               "DB_USER": "ktrdr",
               "DB_PASSWORD": "password123",
           }

           with patch.dict(os.environ, env_vars):
               config = DatabaseConfig()
               expected = "postgresql://ktrdr:password123@localhost:5432/ktrdr"
               assert config.connection_url == expected

       def test_connection_url_raises_for_non_postgresql(self):
           """Test connection URL raises error for non-PostgreSQL."""
           with patch.dict(os.environ, {"DB_TYPE": "csv"}):
               config = DatabaseConfig()

               with pytest.raises(ValueError, match="Connection URL not available"):
                   _ = config.connection_url

       def test_repr_hides_password(self):
           """Test string representation hides password."""
           env_vars = {
               "DB_TYPE": "postgresql",
               "DB_USER": "ktrdr",
               "DB_PASSWORD": "secret_password",
           }

           with patch.dict(os.environ, env_vars):
               config = DatabaseConfig()
               repr_str = repr(config)

               assert "secret_password" not in repr_str
               assert "ktrdr" in repr_str


   class TestDatabaseConnectionManager:
       """Test DatabaseConnectionManager class."""

       def test_init_with_config(self):
           """Test initialization with custom config."""
           config = DatabaseConfig()
           manager = DatabaseConnectionManager(config=config)

           assert manager.config is config
           assert manager._engine is None
           assert manager._session_factory is None

       def test_init_with_default_config(self):
           """Test initialization with default config."""
           manager = DatabaseConnectionManager()

           assert isinstance(manager.config, DatabaseConfig)

       @patch("ktrdr.config.database.create_engine")
       def test_engine_property_creates_engine(self, mock_create_engine):
           """Test engine property creates engine on first access."""
           env_vars = {
               "DB_TYPE": "postgresql",
               "DB_HOST": "localhost",
               "DB_NAME": "ktrdr",
               "DB_USER": "ktrdr",
               "DB_PASSWORD": "password",
           }

           with patch.dict(os.environ, env_vars):
               manager = DatabaseConnectionManager()

               # Access engine
               engine = manager.engine

               # Verify create_engine was called
               assert mock_create_engine.called
               call_args = mock_create_engine.call_args

               # Verify connection URL
               assert call_args[0][0] == "postgresql://ktrdr:password@localhost:5432/ktrdr"

               # Verify pool settings
               assert call_args[1]["pool_size"] == 20
               assert call_args[1]["max_overflow"] == 10
               assert call_args[1]["pool_pre_ping"] is True

       def test_engine_raises_for_non_postgresql(self):
           """Test engine raises error for non-PostgreSQL."""
           with patch.dict(os.environ, {"DB_TYPE": "csv"}):
               manager = DatabaseConnectionManager()

               with pytest.raises(ValueError, match="Cannot create engine"):
                   _ = manager.engine

       @patch("ktrdr.config.database.create_engine")
       def test_get_session(self, mock_create_engine):
           """Test get_session returns SQLAlchemy session."""
           mock_engine = MagicMock()
           mock_create_engine.return_value = mock_engine

           env_vars = {"DB_TYPE": "postgresql"}
           with patch.dict(os.environ, env_vars):
               manager = DatabaseConnectionManager()
               session = manager.get_session()

               assert session is not None

       @patch("ktrdr.config.database.create_engine")
       def test_test_connection_success(self, mock_create_engine):
           """Test test_connection with successful connection."""
           mock_engine = MagicMock()
           mock_connection = MagicMock()
           mock_result = MagicMock()

           mock_engine.connect.return_value.__enter__.return_value = mock_connection
           mock_connection.execute.return_value = mock_result
           mock_create_engine.return_value = mock_engine

           env_vars = {"DB_TYPE": "postgresql"}
           with patch.dict(os.environ, env_vars):
               manager = DatabaseConnectionManager()
               result = manager.test_connection()

               assert result is True
               assert mock_connection.execute.called

       @patch("ktrdr.config.database.create_engine")
       def test_test_connection_failure(self, mock_create_engine):
           """Test test_connection with failed connection."""
           mock_engine = MagicMock()
           mock_engine.connect.side_effect = Exception("Connection failed")
           mock_create_engine.return_value = mock_engine

           env_vars = {"DB_TYPE": "postgresql"}
           with patch.dict(os.environ, env_vars):
               manager = DatabaseConnectionManager()
               result = manager.test_connection()

               assert result is False

       @patch("ktrdr.config.database.create_engine")
       def test_close(self, mock_create_engine):
           """Test close disposes of engine."""
           mock_engine = MagicMock()
           mock_create_engine.return_value = mock_engine

           env_vars = {"DB_TYPE": "postgresql"}
           with patch.dict(os.environ, env_vars):
               manager = DatabaseConnectionManager()

               # Access engine to create it
               _ = manager.engine

               # Close
               manager.close()

               # Verify dispose was called
               assert mock_engine.dispose.called
               assert manager._engine is None
   ```

4. Create integration test `tests/integration/db/test_database_connection.py`:

   ```python
   """Integration tests for database connections."""

   import os
   import pytest
   from ktrdr.config.database import (
       DatabaseConfig,
       DatabaseConnectionManager,
       get_connection_manager,
   )


   @pytest.fixture
   def db_config():
       """Create database config for testing."""
       return DatabaseConfig()


   @pytest.mark.integration
   class TestDatabaseConnection:
       """Test database connection integration."""

       def test_connection_manager_connects(self, db_config):
           """Test that connection manager can connect to database."""
           if not db_config.is_postgresql:
               pytest.skip("PostgreSQL not configured")

           manager = DatabaseConnectionManager(config=db_config)

           # Test connection
           assert manager.test_connection() is True

       def test_connection_manager_executes_query(self, db_config):
           """Test that connection manager can execute queries."""
           if not db_config.is_postgresql:
               pytest.skip("PostgreSQL not configured")

           manager = DatabaseConnectionManager(config=db_config)
           session = manager.get_session()

           try:
               result = session.execute("SELECT 1 as test")
               row = result.fetchone()
               assert row[0] == 1
           finally:
               session.close()

       def test_connection_pool_reuses_connections(self, db_config):
           """Test that connection pool reuses connections."""
           if not db_config.is_postgresql:
               pytest.skip("PostgreSQL not configured")

           manager = DatabaseConnectionManager(config=db_config)

           # Get multiple sessions
           sessions = [manager.get_session() for _ in range(5)]

           # All sessions should be valid
           for session in sessions:
               result = session.execute("SELECT 1")
               assert result.fetchone()[0] == 1
               session.close()

       def test_global_connection_manager(self, db_config):
           """Test global connection manager singleton."""
           if not db_config.is_postgresql:
               pytest.skip("PostgreSQL not configured")

           manager1 = get_connection_manager()
           manager2 = get_connection_manager()

           # Should be same instance
           assert manager1 is manager2
   ```

**Quality Gate**:

```bash
# Start database and backend (if not already running)
docker-compose -f docker/docker-compose.dev.yml up -d timescaledb backend

# Wait for services to be healthy
sleep 15

# Run unit tests (verify DatabaseConfig and DatabaseConnectionManager)
make test-unit

# Run integration tests (verify actual connection works)
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_NAME=ktrdr_dev
export DB_USER=ktrdr_dev
export DB_PASSWORD=ktrdr_dev_password
make test-integration

# Manual connection test from backend container
docker exec -it ktrdr-backend python -c "from ktrdr.config.database import get_connection_manager; print(get_connection_manager().test_connection())"
# Should print: True

make quality
```

**Commit**: `test(db): verify database connection pooling works correctly`

**Estimated Time**: 1.5 hours

---

**Phase 0 Checkpoint**:
✅ PostgreSQL + TimescaleDB verified running and healthy
✅ Schema migrations verified applied correctly (hypertables exist, no compression per design)
✅ Database connection pooling verified working with SQLAlchemy
✅ Integration tests verify database connectivity and schema correctness
✅ **TESTABLE**: Can connect to database, query hypertables, execute SQL from Python

**Total Phase 0 Time**: ~4 hours (reduced from 7 hours since infrastructure already exists)

---

## Phase 1: TimescaleDB Backend Implementation

**Goal**: Create TimescaleDBBackend that implements DataBackend interface for reading/writing price data

**Why This Second**: Now that infrastructure is ready, implement the backend that actually uses it!

**End State**:

- TimescaleDBBackend can save/load price data
- Backend supports all DataBackend interface methods
- Full observability instrumentation
- Integration tests verify data persistence
- **TESTABLE**: Save DataFrame → query from database → load DataFrame → verify identical

---

### Task 1.1: TimescaleDB Backend Data Models

**Objective**: Create data models for TimescaleDB backend (PriceBar dataclass)

**TDD Approach**:

1. Create unit tests for PriceBar dataclass
2. Test to_dict(), from_dict() serialization
3. Test DataFrame conversion methods

**Implementation**:

1. Create `ktrdr/data/backends/timescaledb/models.py`:

   ```python
   """Data models for TimescaleDB backend."""

   from dataclasses import dataclass, asdict
   from datetime import datetime
   from typing import Dict, Any, List
   import pandas as pd


   @dataclass
   class PriceBar:
       """
       Price bar (OHLCV) data model for TimescaleDB.

       Maps to price_data table schema.
       """

       time: datetime
       symbol: str
       timeframe: str
       open: float
       high: float
       low: float
       close: float
       volume: float
       source: str = "ib"
       created_at: datetime = None

       def __post_init__(self):
           """Set default values after initialization."""
           if self.created_at is None:
               self.created_at = datetime.utcnow()

       def to_dict(self) -> Dict[str, Any]:
           """
           Convert to dictionary for database insertion.

           Returns:
               Dictionary with all fields
           """
           return asdict(self)

       @classmethod
       def from_dict(cls, data: Dict[str, Any]) -> "PriceBar":
           """
           Create PriceBar from dictionary.

           Args:
               data: Dictionary with price bar data

           Returns:
               PriceBar instance
           """
           return cls(**data)

       @classmethod
       def from_dataframe_row(
           cls,
           row: pd.Series,
           symbol: str,
           timeframe: str,
           source: str = "ib",
       ) -> "PriceBar":
           """
           Create PriceBar from DataFrame row.

           Args:
               row: Pandas Series with OHLCV data (index is timestamp)
               symbol: Symbol name
               timeframe: Timeframe string
               source: Data source

           Returns:
               PriceBar instance
           """
           return cls(
               time=row.name if isinstance(row.name, datetime) else pd.to_datetime(row.name),
               symbol=symbol,
               timeframe=timeframe,
               open=float(row["open"]),
               high=float(row["high"]),
               low=float(row["low"]),
               close=float(row["close"]),
               volume=float(row["volume"]),
               source=source,
           )

       def to_series(self) -> pd.Series:
           """
           Convert to Pandas Series (for DataFrame construction).

           Returns:
               Series with OHLCV data (time as index)
           """
           return pd.Series(
               {
                   "open": self.open,
                   "high": self.high,
                   "low": self.low,
                   "close": self.close,
                   "volume": self.volume,
               },
               name=self.time,
           )


   def dataframe_to_price_bars(
       df: pd.DataFrame,
       symbol: str,
       timeframe: str,
       source: str = "ib",
   ) -> List[PriceBar]:
       """
       Convert DataFrame to list of PriceBar instances.

       Args:
           df: DataFrame with OHLCV data (DatetimeIndex)
           symbol: Symbol name
           timeframe: Timeframe string
           source: Data source

       Returns:
           List of PriceBar instances
       """
       return [
           PriceBar.from_dataframe_row(row, symbol, timeframe, source)
           for _, row in df.iterrows()
       ]


   def price_bars_to_dataframe(bars: List[PriceBar]) -> pd.DataFrame:
       """
       Convert list of PriceBar instances to DataFrame.

       Args:
           bars: List of PriceBar instances

       Returns:
           DataFrame with OHLCV data (DatetimeIndex)
       """
       if not bars:
           return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

       series_list = [bar.to_series() for bar in bars]
       df = pd.DataFrame(series_list)
       df.index.name = "time"
       return df
   ```

2. Create unit tests `tests/unit/data/backends/timescaledb/test_models.py`:

   ```python
   """Unit tests for TimescaleDB data models."""

   import pytest
   import pandas as pd
   from datetime import datetime
   from ktrdr.data.backends.timescaledb.models import (
       PriceBar,
       dataframe_to_price_bars,
       price_bars_to_dataframe,
   )


   class TestPriceBar:
       """Test PriceBar dataclass."""

       def test_init(self):
           """Test PriceBar initialization."""
           bar = PriceBar(
               time=datetime(2024, 1, 1, 9, 30),
               symbol="AAPL",
               timeframe="1d",
               open=150.0,
               high=152.0,
               low=149.0,
               close=151.0,
               volume=1000000.0,
           )

           assert bar.time == datetime(2024, 1, 1, 9, 30)
           assert bar.symbol == "AAPL"
           assert bar.timeframe == "1d"
           assert bar.open == 150.0
           assert bar.high == 152.0
           assert bar.low == 149.0
           assert bar.close == 151.0
           assert bar.volume == 1000000.0
           assert bar.source == "ib"
           assert bar.created_at is not None

       def test_to_dict(self):
           """Test to_dict serialization."""
           bar = PriceBar(
               time=datetime(2024, 1, 1),
               symbol="AAPL",
               timeframe="1d",
               open=150.0,
               high=152.0,
               low=149.0,
               close=151.0,
               volume=1000000.0,
           )

           data = bar.to_dict()

           assert data["time"] == datetime(2024, 1, 1)
           assert data["symbol"] == "AAPL"
           assert data["open"] == 150.0
           assert "created_at" in data

       def test_from_dict(self):
           """Test from_dict deserialization."""
           data = {
               "time": datetime(2024, 1, 1),
               "symbol": "AAPL",
               "timeframe": "1d",
               "open": 150.0,
               "high": 152.0,
               "low": 149.0,
               "close": 151.0,
               "volume": 1000000.0,
               "source": "ib",
               "created_at": datetime.utcnow(),
           }

           bar = PriceBar.from_dict(data)

           assert bar.symbol == "AAPL"
           assert bar.open == 150.0

       def test_from_dataframe_row(self):
           """Test from_dataframe_row conversion."""
           df = pd.DataFrame(
               {
                   "open": [150.0],
                   "high": [152.0],
                   "low": [149.0],
                   "close": [151.0],
                   "volume": [1000000.0],
               },
               index=pd.DatetimeIndex([datetime(2024, 1, 1)]),
           )

           row = df.iloc[0]
           bar = PriceBar.from_dataframe_row(row, "AAPL", "1d")

           assert bar.symbol == "AAPL"
           assert bar.timeframe == "1d"
           assert bar.time == datetime(2024, 1, 1)
           assert bar.open == 150.0

       def test_to_series(self):
           """Test to_series conversion."""
           bar = PriceBar(
               time=datetime(2024, 1, 1),
               symbol="AAPL",
               timeframe="1d",
               open=150.0,
               high=152.0,
               low=149.0,
               close=151.0,
               volume=1000000.0,
           )

           series = bar.to_series()

           assert series.name == datetime(2024, 1, 1)
           assert series["open"] == 150.0
           assert series["high"] == 152.0
           assert series["volume"] == 1000000.0


   class TestDataFrameConversion:
       """Test DataFrame conversion functions."""

       def test_dataframe_to_price_bars(self):
           """Test dataframe_to_price_bars conversion."""
           df = pd.DataFrame(
               {
                   "open": [150.0, 151.0],
                   "high": [152.0, 153.0],
                   "low": [149.0, 150.0],
                   "close": [151.0, 152.0],
                   "volume": [1000000.0, 1100000.0],
               },
               index=pd.DatetimeIndex([datetime(2024, 1, 1), datetime(2024, 1, 2)]),
           )

           bars = dataframe_to_price_bars(df, "AAPL", "1d")

           assert len(bars) == 2
           assert bars[0].symbol == "AAPL"
           assert bars[0].open == 150.0
           assert bars[1].open == 151.0

       def test_price_bars_to_dataframe(self):
           """Test price_bars_to_dataframe conversion."""
           bars = [
               PriceBar(
                   time=datetime(2024, 1, 1),
                   symbol="AAPL",
                   timeframe="1d",
                   open=150.0,
                   high=152.0,
                   low=149.0,
                   close=151.0,
                   volume=1000000.0,
               ),
               PriceBar(
                   time=datetime(2024, 1, 2),
                   symbol="AAPL",
                   timeframe="1d",
                   open=151.0,
                   high=153.0,
                   low=150.0,
                   close=152.0,
                   volume=1100000.0,
               ),
           ]

           df = price_bars_to_dataframe(bars)

           assert len(df) == 2
           assert df.index[0] == datetime(2024, 1, 1)
           assert df.iloc[0]["open"] == 150.0
           assert df.iloc[1]["open"] == 151.0

       def test_price_bars_to_dataframe_empty(self):
           """Test price_bars_to_dataframe with empty list."""
           df = price_bars_to_dataframe([])

           assert len(df) == 0
           assert list(df.columns) == ["open", "high", "low", "close", "volume"]

       def test_round_trip_conversion(self):
           """Test DataFrame → PriceBar → DataFrame round trip."""
           original_df = pd.DataFrame(
               {
                   "open": [150.0, 151.0],
                   "high": [152.0, 153.0],
                   "low": [149.0, 150.0],
                   "close": [151.0, 152.0],
                   "volume": [1000000.0, 1100000.0],
               },
               index=pd.DatetimeIndex([datetime(2024, 1, 1), datetime(2024, 1, 2)]),
           )

           # Convert to bars and back
           bars = dataframe_to_price_bars(original_df, "AAPL", "1d")
           result_df = price_bars_to_dataframe(bars)

           # Verify identical
           pd.testing.assert_frame_equal(original_df, result_df)
   ```

**Quality Gate**:

```bash
make test-unit
make quality
```

**Commit**: `feat(db): add TimescaleDB data models for price bars`

**Estimated Time**: 2 hours

---

### Task 1.2: TimescaleDBBackend Core Implementation

**Objective**: Implement TimescaleDBBackend with save/load/list_symbols methods

**TDD Approach**:

1. Create integration tests for save_data()
2. Create integration tests for load_data()
3. Create integration tests for list_symbols()
4. Test error handling and edge cases

**Implementation**:

1. Create `ktrdr/data/backends/timescaledb/backend.py`:

   ```python
   """TimescaleDB backend for time-series data storage."""

   from datetime import datetime
   from typing import List, Optional, Tuple
   import pandas as pd
   from sqlalchemy import text
   from sqlalchemy.orm import Session

   from ktrdr.config.database import get_connection_manager
   from ktrdr.data.backends.base import DataBackend
   from ktrdr.data.backends.timescaledb.models import (
       PriceBar,
       dataframe_to_price_bars,
       price_bars_to_dataframe,
   )
   from ktrdr.logging import get_logger
   from ktrdr.telemetry.service_telemetry import with_service_telemetry

   logger = get_logger(__name__)


   class TimescaleDBBackend(DataBackend):
       """
       TimescaleDB backend for time-series data storage.

       Implements DataBackend interface using PostgreSQL + TimescaleDB.
       Provides high-performance time-series storage with automatic compression.
       """

       def __init__(self):
           """Initialize TimescaleDB backend."""
           self.connection_manager = get_connection_manager()
           logger.info("TimescaleDB backend initialized")

       @with_service_telemetry(
           service_name="timescaledb",
           operation_name="save_data",
           attributes_from_kwargs=["symbol", "timeframe"],
       )
       def save_data(
           self,
           symbol: str,
           timeframe: str,
           data: pd.DataFrame,
           source: str = "ib",
       ) -> None:
           """
           Save price data to TimescaleDB.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               data: DataFrame with OHLCV data (DatetimeIndex)
               source: Data source identifier

           Raises:
               ValueError: If data is empty or invalid
               Exception: If database operation fails
           """
           if data.empty:
               raise ValueError(f"Cannot save empty DataFrame for {symbol} {timeframe}")

           logger.info(
               f"Saving {len(data)} bars for {symbol} {timeframe} to TimescaleDB",
               extra={
                   "symbol": symbol,
                   "timeframe": timeframe,
                   "bars_count": len(data),
                   "date_range": f"{data.index[0]} to {data.index[-1]}",
               },
           )

           # Convert DataFrame to PriceBar instances
           bars = dataframe_to_price_bars(data, symbol, timeframe, source)

           session = self.connection_manager.get_session()
           try:
               # Use INSERT ... ON CONFLICT DO UPDATE for upsert behavior
               # This ensures idempotent writes (same data can be written multiple times)
               insert_query = text("""
                   INSERT INTO price_data (time, symbol, timeframe, open, high, low, close, volume, source, created_at)
                   VALUES (:time, :symbol, :timeframe, :open, :high, :low, :close, :volume, :source, :created_at)
                   ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                       open = EXCLUDED.open,
                       high = EXCLUDED.high,
                       low = EXCLUDED.low,
                       close = EXCLUDED.close,
                       volume = EXCLUDED.volume,
                       source = EXCLUDED.source
               """)

               # Batch insert (much faster than individual inserts)
               session.execute(insert_query, [bar.to_dict() for bar in bars])
               session.commit()

               logger.info(
                   f"✓ Saved {len(bars)} bars for {symbol} {timeframe}",
                   extra={"bars_saved": len(bars)},
               )

           except Exception as e:
               session.rollback()
               logger.error(
                   f"Failed to save data for {symbol} {timeframe}: {e}",
                   exc_info=True,
               )
               raise
           finally:
               session.close()

       @with_service_telemetry(
           service_name="timescaledb",
           operation_name="load_data",
           attributes_from_kwargs=["symbol", "timeframe"],
       )
       def load_data(
           self,
           symbol: str,
           timeframe: str,
           start_date: Optional[datetime] = None,
           end_date: Optional[datetime] = None,
       ) -> pd.DataFrame:
           """
           Load price data from TimescaleDB.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               start_date: Start date (inclusive, optional)
               end_date: End date (inclusive, optional)

           Returns:
               DataFrame with OHLCV data (DatetimeIndex), empty if no data found
           """
           logger.info(
               f"Loading data for {symbol} {timeframe} from TimescaleDB",
               extra={
                   "symbol": symbol,
                   "timeframe": timeframe,
                   "start_date": start_date,
                   "end_date": end_date,
               },
           )

           session = self.connection_manager.get_session()
           try:
               # Build query with optional date filters
               query = """
                   SELECT time, open, high, low, close, volume
                   FROM price_data
                   WHERE symbol = :symbol AND timeframe = :timeframe
               """
               params = {"symbol": symbol, "timeframe": timeframe}

               if start_date:
                   query += " AND time >= :start_date"
                   params["start_date"] = start_date

               if end_date:
                   query += " AND time <= :end_date"
                   params["end_date"] = end_date

               query += " ORDER BY time ASC"

               # Execute query
               result = session.execute(text(query), params)
               rows = result.fetchall()

               if not rows:
                   logger.warning(
                       f"No data found for {symbol} {timeframe}",
                       extra={"bars_loaded": 0},
                   )
                   return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

               # Convert to DataFrame
               df = pd.DataFrame(
                   rows,
                   columns=["time", "open", "high", "low", "close", "volume"],
               )
               df.set_index("time", inplace=True)
               df.index.name = "time"

               logger.info(
                   f"✓ Loaded {len(df)} bars for {symbol} {timeframe}",
                   extra={
                       "bars_loaded": len(df),
                       "date_range": f"{df.index[0]} to {df.index[-1]}",
                   },
               )

               return df

           except Exception as e:
               logger.error(
                   f"Failed to load data for {symbol} {timeframe}: {e}",
                   exc_info=True,
               )
               raise
           finally:
               session.close()

       @with_service_telemetry(
           service_name="timescaledb",
           operation_name="list_symbols",
           attributes_from_kwargs=["timeframe"],
       )
       def list_symbols(self, timeframe: Optional[str] = None) -> List[str]:
           """
           List all symbols available in TimescaleDB.

           Args:
               timeframe: Optional timeframe filter

           Returns:
               List of symbol names (sorted)
           """
           logger.info(f"Listing symbols from TimescaleDB (timeframe={timeframe})")

           session = self.connection_manager.get_session()
           try:
               query = "SELECT DISTINCT symbol FROM price_data"
               params = {}

               if timeframe:
                   query += " WHERE timeframe = :timeframe"
                   params["timeframe"] = timeframe

               query += " ORDER BY symbol"

               result = session.execute(text(query), params)
               symbols = [row[0] for row in result.fetchall()]

               logger.info(
                   f"✓ Found {len(symbols)} symbols",
                   extra={"symbols_count": len(symbols)},
               )

               return symbols

           except Exception as e:
               logger.error(f"Failed to list symbols: {e}", exc_info=True)
               raise
           finally:
               session.close()

       @with_service_telemetry(
           service_name="timescaledb",
           operation_name="get_date_range",
           attributes_from_kwargs=["symbol", "timeframe"],
       )
       def get_date_range(
           self, symbol: str, timeframe: str
       ) -> Optional[Tuple[datetime, datetime]]:
           """
           Get available date range for symbol and timeframe.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string

           Returns:
               Tuple of (start_date, end_date), or None if no data
           """
           session = self.connection_manager.get_session()
           try:
               query = text("""
                   SELECT MIN(time) as start_date, MAX(time) as end_date
                   FROM price_data
                   WHERE symbol = :symbol AND timeframe = :timeframe
               """)

               result = session.execute(
                   query, {"symbol": symbol, "timeframe": timeframe}
               ).fetchone()

               if result and result[0] and result[1]:
                   return (result[0], result[1])

               return None

           finally:
               session.close()

       def delete_data(
           self,
           symbol: str,
           timeframe: str,
           start_date: Optional[datetime] = None,
           end_date: Optional[datetime] = None,
       ) -> int:
           """
           Delete price data from TimescaleDB.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               start_date: Start date (inclusive, optional)
               end_date: End date (inclusive, optional)

           Returns:
               Number of rows deleted
           """
           session = self.connection_manager.get_session()
           try:
               query = "DELETE FROM price_data WHERE symbol = :symbol AND timeframe = :timeframe"
               params = {"symbol": symbol, "timeframe": timeframe}

               if start_date:
                   query += " AND time >= :start_date"
                   params["start_date"] = start_date

               if end_date:
                   query += " AND time <= :end_date"
                   params["end_date"] = end_date

               result = session.execute(text(query), params)
               session.commit()

               rows_deleted = result.rowcount
               logger.info(f"Deleted {rows_deleted} rows for {symbol} {timeframe}")

               return rows_deleted

           except Exception as e:
               session.rollback()
               logger.error(f"Failed to delete data: {e}", exc_info=True)
               raise
           finally:
               session.close()
   ```

2. Create integration tests `tests/integration/db/test_timescaledb_backend.py`:

   ```python
   """Integration tests for TimescaleDB backend."""

   import pytest
   import pandas as pd
   from datetime import datetime, timedelta
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.config.database import DatabaseConfig


   @pytest.fixture
   def backend():
       """Create TimescaleDB backend for testing."""
       config = DatabaseConfig()
       if not config.is_postgresql:
           pytest.skip("PostgreSQL not configured")

       return TimescaleDBBackend()


   @pytest.fixture
   def sample_data():
       """Create sample OHLCV data."""
       dates = pd.date_range(start="2024-01-01", periods=5, freq="D")
       df = pd.DataFrame(
           {
               "open": [100.0, 101.0, 102.0, 103.0, 104.0],
               "high": [102.0, 103.0, 104.0, 105.0, 106.0],
               "low": [99.0, 100.0, 101.0, 102.0, 103.0],
               "close": [101.0, 102.0, 103.0, 104.0, 105.0],
               "volume": [1000000.0, 1100000.0, 1200000.0, 1300000.0, 1400000.0],
           },
           index=dates,
       )
       return df


   @pytest.mark.integration
   class TestTimescaleDBBackend:
       """Integration tests for TimescaleDB backend."""

       def test_save_data(self, backend, sample_data):
           """Test saving data to TimescaleDB."""
           symbol = "TEST_SAVE"
           timeframe = "1d"

           # Clean up any existing data
           backend.delete_data(symbol, timeframe)

           # Save data
           backend.save_data(symbol, timeframe, sample_data)

           # Verify data was saved (load it back)
           loaded = backend.load_data(symbol, timeframe)

           assert len(loaded) == len(sample_data)
           pd.testing.assert_frame_equal(loaded, sample_data)

       def test_save_data_idempotent(self, backend, sample_data):
           """Test that saving same data twice is idempotent."""
           symbol = "TEST_IDEMPOTENT"
           timeframe = "1d"

           # Clean up
           backend.delete_data(symbol, timeframe)

           # Save data twice
           backend.save_data(symbol, timeframe, sample_data)
           backend.save_data(symbol, timeframe, sample_data)

           # Verify only one copy exists
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == len(sample_data)

       def test_load_data_empty(self, backend):
           """Test loading data for non-existent symbol."""
           loaded = backend.load_data("NONEXISTENT", "1d")

           assert len(loaded) == 0
           assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]

       def test_load_data_with_date_range(self, backend, sample_data):
           """Test loading data with date range filter."""
           symbol = "TEST_DATE_RANGE"
           timeframe = "1d"

           # Clean up and save
           backend.delete_data(symbol, timeframe)
           backend.save_data(symbol, timeframe, sample_data)

           # Load subset (middle 3 days)
           start_date = datetime(2024, 1, 2)
           end_date = datetime(2024, 1, 4)
           loaded = backend.load_data(symbol, timeframe, start_date, end_date)

           assert len(loaded) == 3
           assert loaded.index[0] == pd.Timestamp("2024-01-02")
           assert loaded.index[-1] == pd.Timestamp("2024-01-04")

       def test_list_symbols(self, backend, sample_data):
           """Test listing symbols."""
           symbol1 = "TEST_LIST_1"
           symbol2 = "TEST_LIST_2"
           timeframe = "1d"

           # Clean up and save
           backend.delete_data(symbol1, timeframe)
           backend.delete_data(symbol2, timeframe)
           backend.save_data(symbol1, timeframe, sample_data)
           backend.save_data(symbol2, timeframe, sample_data)

           # List all symbols
           symbols = backend.list_symbols()

           assert symbol1 in symbols
           assert symbol2 in symbols

       def test_list_symbols_with_timeframe_filter(self, backend, sample_data):
           """Test listing symbols with timeframe filter."""
           symbol = "TEST_TF_FILTER"

           # Clean up and save for different timeframes
           backend.delete_data(symbol, "1d")
           backend.delete_data(symbol, "1h")
           backend.save_data(symbol, "1d", sample_data)
           backend.save_data(symbol, "1h", sample_data)

           # List symbols for 1d timeframe only
           symbols_1d = backend.list_symbols(timeframe="1d")

           assert symbol in symbols_1d

       def test_get_date_range(self, backend, sample_data):
           """Test getting date range for symbol."""
           symbol = "TEST_DATE_RANGE_GET"
           timeframe = "1d"

           # Clean up and save
           backend.delete_data(symbol, timeframe)
           backend.save_data(symbol, timeframe, sample_data)

           # Get date range
           date_range = backend.get_date_range(symbol, timeframe)

           assert date_range is not None
           start_date, end_date = date_range
           assert start_date == pd.Timestamp("2024-01-01")
           assert end_date == pd.Timestamp("2024-01-05")

       def test_get_date_range_nonexistent(self, backend):
           """Test getting date range for non-existent symbol."""
           date_range = backend.get_date_range("NONEXISTENT", "1d")

           assert date_range is None

       def test_delete_data(self, backend, sample_data):
           """Test deleting data."""
           symbol = "TEST_DELETE"
           timeframe = "1d"

           # Save and verify
           backend.save_data(symbol, timeframe, sample_data)
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == 5

           # Delete all
           rows_deleted = backend.delete_data(symbol, timeframe)
           assert rows_deleted == 5

           # Verify deleted
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == 0

       def test_delete_data_with_date_range(self, backend, sample_data):
           """Test deleting data with date range."""
           symbol = "TEST_DELETE_RANGE"
           timeframe = "1d"

           # Save
           backend.delete_data(symbol, timeframe)
           backend.save_data(symbol, timeframe, sample_data)

           # Delete middle 3 days
           start_date = datetime(2024, 1, 2)
           end_date = datetime(2024, 1, 4)
           rows_deleted = backend.delete_data(symbol, timeframe, start_date, end_date)

           assert rows_deleted == 3

           # Verify only 2 days remain
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == 2
   ```

**Quality Gate**:

```bash
# Start database
docker-compose -f docker/docker-compose.dev.yml up -d timescaledb

# Run migrations
docker exec -it ktrdr-timescaledb-dev bash /migrations/run_migrations.sh

# Run unit tests
make test-unit

# Run integration tests
export DB_TYPE=postgresql
make test-integration

docker-compose -f docker/docker-compose.dev.yml down

make quality
```

**Commit**: `feat(db): implement TimescaleDB backend for price data storage`

**Estimated Time**: 4 hours

---

### Task 1.3: Add Observability Attribute Mappings

**Objective**: Add TimescaleDB-specific span attributes to observability configuration

**TDD Approach**:

1. Update service_telemetry.py with db.* attributes
2. Test that spans include database attributes
3. Verify attributes appear in Jaeger

**Implementation**:

1. Update `ktrdr/telemetry/service_telemetry.py`:

   ```python
   # ... existing imports ...

   # Add database attributes to SPAN_ATTRIBUTE_MAPPINGS
   SPAN_ATTRIBUTE_MAPPINGS = {
       # ... existing mappings ...

       # Database operations
       "timescaledb.save_data": [
           ("symbol", "db.symbol"),
           ("timeframe", "db.timeframe"),
           ("source", "db.source"),
       ],
       "timescaledb.load_data": [
           ("symbol", "db.symbol"),
           ("timeframe", "db.timeframe"),
           ("start_date", "db.start_date"),
           ("end_date", "db.end_date"),
       ],
       "timescaledb.list_symbols": [
           ("timeframe", "db.timeframe"),
       ],
       "timescaledb.get_date_range": [
           ("symbol", "db.symbol"),
           ("timeframe", "db.timeframe"),
       ],
   }

   # Add database attribute namespace
   DB_ATTRIBUTES = {
       "db.symbol": "Symbol being queried",
       "db.timeframe": "Timeframe being queried",
       "db.source": "Data source identifier",
       "db.start_date": "Start date filter",
       "db.end_date": "End date filter",
       "db.bars_count": "Number of bars saved/loaded",
       "db.date_range": "Date range of data",
   }
   ```

2. Add test case to `tests/unit/telemetry/test_service_telemetry.py`:

   ```python
   def test_timescaledb_attributes():
       """Test TimescaleDB span attributes."""
       from ktrdr.telemetry.service_telemetry import SPAN_ATTRIBUTE_MAPPINGS

       # Verify timescaledb mappings exist
       assert "timescaledb.save_data" in SPAN_ATTRIBUTE_MAPPINGS
       assert "timescaledb.load_data" in SPAN_ATTRIBUTE_MAPPINGS

       # Verify symbol mapping
       save_mappings = dict(SPAN_ATTRIBUTE_MAPPINGS["timescaledb.save_data"])
       assert save_mappings["symbol"] == "db.symbol"
       assert save_mappings["timeframe"] == "db.timeframe"
   ```

**Quality Gate**:

```bash
make test-unit
make quality

# Manual verification with Jaeger
docker-compose -f docker/docker-compose.dev.yml up -d timescaledb jaeger
# Run operation, check Jaeger UI for db.* attributes
```

**Commit**: `feat(telemetry): add TimescaleDB span attribute mappings`

**Estimated Time**: 1 hour

---

**Phase 1 Checkpoint**:
✅ TimescaleDB data models (PriceBar)
✅ TimescaleDBBackend implements DataBackend interface
✅ Save/load/list_symbols/get_date_range working
✅ Full observability instrumentation
✅ Integration tests verify database operations
✅ **TESTABLE**: Save DataFrame → load from database → verify identical data

**Total Phase 1 Time**: ~7 hours

---

## Phase 2: CSV Import Service

**Goal**: Create service to import existing CSV data into TimescaleDB

**Why This Third**: Now we can read/write TimescaleDB, add bulk import for migration!

**End State**:

- CSVImportService can import one symbol's data
- Service can import all symbols in data/ directory
- Idempotent imports (safe to run multiple times)
- Progress tracking and logging
- **TESTABLE**: Import CSV → query database → verify data matches CSV

---

### Task 2.1: CSV Import Data Models

**Objective**: Create data models for import results and progress

**TDD Approach**:

1. Create unit tests for ImportResult dataclass
2. Test to_dict() serialization
3. Test summary aggregation

**Implementation**:

1. Create `ktrdr/data/import_service/models.py`:

   ```python
   """Data models for CSV import service."""

   from dataclasses import dataclass, field
   from datetime import datetime
   from typing import Dict, List, Any


   @dataclass
   class ImportResult:
       """Result of importing one symbol."""

       symbol: str
       timeframe: str
       rows_imported: int
       start_date: datetime
       end_date: datetime
       duration_seconds: float
       success: bool
       error_message: str = ""

       def to_dict(self) -> Dict[str, Any]:
           """Convert to dictionary."""
           return {
               "symbol": self.symbol,
               "timeframe": self.timeframe,
               "rows_imported": self.rows_imported,
               "start_date": self.start_date.isoformat() if self.start_date else None,
               "end_date": self.end_date.isoformat() if self.end_date else None,
               "duration_seconds": self.duration_seconds,
               "success": self.success,
               "error_message": self.error_message,
           }


   @dataclass
   class ImportSummary:
       """Summary of bulk import operation."""

       total_symbols: int
       successful: int
       failed: int
       total_rows: int
       total_duration_seconds: float
       results: List[ImportResult] = field(default_factory=list)

       @property
       def success_rate(self) -> float:
           """Calculate success rate percentage."""
           if self.total_symbols == 0:
               return 0.0
           return (self.successful / self.total_symbols) * 100

       def to_dict(self) -> Dict[str, Any]:
           """Convert to dictionary."""
           return {
               "total_symbols": self.total_symbols,
               "successful": self.successful,
               "failed": self.failed,
               "total_rows": self.total_rows,
               "total_duration_seconds": self.total_duration_seconds,
               "success_rate": self.success_rate,
               "results": [r.to_dict() for r in self.results],
           }
   ```

2. Create unit tests `tests/unit/data/import_service/test_models.py`:

   ```python
   """Unit tests for CSV import service models."""

   import pytest
   from datetime import datetime
   from ktrdr.data.import_service.models import ImportResult, ImportSummary


   class TestImportResult:
       """Test ImportResult dataclass."""

       def test_init_success(self):
           """Test successful import result."""
           result = ImportResult(
               symbol="AAPL",
               timeframe="1d",
               rows_imported=1000,
               start_date=datetime(2024, 1, 1),
               end_date=datetime(2024, 12, 31),
               duration_seconds=2.5,
               success=True,
           )

           assert result.symbol == "AAPL"
           assert result.rows_imported == 1000
           assert result.success is True
           assert result.error_message == ""

       def test_init_failure(self):
           """Test failed import result."""
           result = ImportResult(
               symbol="INVALID",
               timeframe="1d",
               rows_imported=0,
               start_date=None,
               end_date=None,
               duration_seconds=0.1,
               success=False,
               error_message="File not found",
           )

           assert result.success is False
           assert result.error_message == "File not found"

       def test_to_dict(self):
           """Test to_dict serialization."""
           result = ImportResult(
               symbol="AAPL",
               timeframe="1d",
               rows_imported=1000,
               start_date=datetime(2024, 1, 1),
               end_date=datetime(2024, 12, 31),
               duration_seconds=2.5,
               success=True,
           )

           data = result.to_dict()

           assert data["symbol"] == "AAPL"
           assert data["rows_imported"] == 1000
           assert data["success"] is True
           assert "start_date" in data


   class TestImportSummary:
       """Test ImportSummary dataclass."""

       def test_init(self):
           """Test initialization."""
           summary = ImportSummary(
               total_symbols=10,
               successful=8,
               failed=2,
               total_rows=10000,
               total_duration_seconds=25.5,
           )

           assert summary.total_symbols == 10
           assert summary.successful == 8
           assert summary.failed == 2

       def test_success_rate(self):
           """Test success rate calculation."""
           summary = ImportSummary(
               total_symbols=10,
               successful=8,
               failed=2,
               total_rows=10000,
               total_duration_seconds=25.5,
           )

           assert summary.success_rate == 80.0

       def test_success_rate_zero_symbols(self):
           """Test success rate with zero symbols."""
           summary = ImportSummary(
               total_symbols=0,
               successful=0,
               failed=0,
               total_rows=0,
               total_duration_seconds=0,
           )

           assert summary.success_rate == 0.0

       def test_to_dict(self):
           """Test to_dict serialization."""
           result = ImportResult(
               symbol="AAPL",
               timeframe="1d",
               rows_imported=1000,
               start_date=datetime(2024, 1, 1),
               end_date=datetime(2024, 12, 31),
               duration_seconds=2.5,
               success=True,
           )

           summary = ImportSummary(
               total_symbols=1,
               successful=1,
               failed=0,
               total_rows=1000,
               total_duration_seconds=2.5,
               results=[result],
           )

           data = summary.to_dict()

           assert data["total_symbols"] == 1
           assert data["success_rate"] == 100.0
           assert len(data["results"]) == 1
   ```

**Quality Gate**:

```bash
make test-unit
make quality
```

**Commit**: `feat(import): add CSV import service data models`

**Estimated Time**: 1.5 hours

---

### Task 2.2: CSVImportService Core Implementation

**Objective**: Implement service to import CSV files into TimescaleDB

**TDD Approach**:

1. Create integration tests for import_symbol()
2. Create integration tests for import_all()
3. Test idempotent behavior
4. Test error handling

**Implementation**:

1. Create `ktrdr/data/import_service/csv_import_service.py`:

   ```python
   """Service for importing CSV data into TimescaleDB."""

   import time
   from pathlib import Path
   from datetime import datetime
   from typing import List, Optional
   import pandas as pd

   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.data.import_service.models import ImportResult, ImportSummary
   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   class CSVImportService:
       """
       Service for importing CSV data into TimescaleDB.

       Provides idempotent bulk import of historical price data from CSV files.
       """

       def __init__(
           self,
           backend: Optional[TimescaleDBBackend] = None,
           data_repository: Optional[DataRepository] = None,
       ):
           """
           Initialize CSV import service.

           Args:
               backend: TimescaleDB backend (creates new if None)
               data_repository: Data repository for reading CSV (creates new if None)
           """
           self.backend = backend or TimescaleDBBackend()
           self.data_repository = data_repository or DataRepository()
           logger.info("CSV import service initialized")

       def import_symbol(
           self,
           symbol: str,
           timeframe: str,
           source: str = "ib",
       ) -> ImportResult:
           """
           Import one symbol's data from CSV to TimescaleDB.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               source: Data source identifier

           Returns:
               ImportResult with import statistics
           """
           start_time = time.time()

           logger.info(f"Importing {symbol} {timeframe} from CSV to TimescaleDB")

           try:
               # Load data from CSV using DataRepository
               data = self.data_repository.load_data(symbol, timeframe)

               if data.empty:
                   logger.warning(f"No CSV data found for {symbol} {timeframe}")
                   return ImportResult(
                       symbol=symbol,
                       timeframe=timeframe,
                       rows_imported=0,
                       start_date=None,
                       end_date=None,
                       duration_seconds=time.time() - start_time,
                       success=False,
                       error_message="No CSV data found",
                   )

               # Save to TimescaleDB (idempotent - uses UPSERT)
               self.backend.save_data(symbol, timeframe, data, source=source)

               duration = time.time() - start_time

               result = ImportResult(
                   symbol=symbol,
                   timeframe=timeframe,
                   rows_imported=len(data),
                   start_date=data.index[0].to_pydatetime(),
                   end_date=data.index[-1].to_pydatetime(),
                   duration_seconds=duration,
                   success=True,
               )

               logger.info(
                   f"✓ Imported {len(data)} bars for {symbol} {timeframe} in {duration:.2f}s",
                   extra={
                       "symbol": symbol,
                       "timeframe": timeframe,
                       "rows_imported": len(data),
                       "duration_seconds": duration,
                   },
               )

               return result

           except Exception as e:
               duration = time.time() - start_time
               error_msg = str(e)

               logger.error(
                   f"Failed to import {symbol} {timeframe}: {error_msg}",
                   exc_info=True,
               )

               return ImportResult(
                   symbol=symbol,
                   timeframe=timeframe,
                   rows_imported=0,
                   start_date=None,
                   end_date=None,
                   duration_seconds=duration,
                   success=False,
                   error_message=error_msg,
               )

       def import_all(
           self,
           timeframe: str,
           symbols: Optional[List[str]] = None,
           source: str = "ib",
       ) -> ImportSummary:
           """
           Import all symbols from CSV to TimescaleDB.

           Args:
               timeframe: Timeframe to import
               symbols: Optional list of symbols (imports all if None)
               source: Data source identifier

           Returns:
               ImportSummary with aggregated results
           """
           start_time = time.time()

           # Get list of symbols to import
           if symbols is None:
               symbols = self.data_repository.list_symbols(timeframe=timeframe)

           logger.info(
               f"Starting bulk import of {len(symbols)} symbols for timeframe {timeframe}",
               extra={"total_symbols": len(symbols), "timeframe": timeframe},
           )

           results = []
           total_rows = 0
           successful = 0
           failed = 0

           # Import each symbol
           for i, symbol in enumerate(symbols, 1):
               logger.info(f"Importing {i}/{len(symbols)}: {symbol} {timeframe}")

               result = self.import_symbol(symbol, timeframe, source=source)
               results.append(result)

               if result.success:
                   successful += 1
                   total_rows += result.rows_imported
               else:
                   failed += 1

           total_duration = time.time() - start_time

           summary = ImportSummary(
               total_symbols=len(symbols),
               successful=successful,
               failed=failed,
               total_rows=total_rows,
               total_duration_seconds=total_duration,
               results=results,
           )

           logger.info(
               f"✓ Bulk import complete: {successful}/{len(symbols)} successful, "
               f"{total_rows:,} total rows in {total_duration:.2f}s",
               extra={
                   "total_symbols": len(symbols),
                   "successful": successful,
                   "failed": failed,
                   "total_rows": total_rows,
                   "duration_seconds": total_duration,
                   "success_rate": summary.success_rate,
               },
           )

           return summary
   ```

2. Create integration tests `tests/integration/data/test_csv_import_service.py`:

   ```python
   """Integration tests for CSV import service."""

   import pytest
   import pandas as pd
   from pathlib import Path
   from datetime import datetime

   from ktrdr.config.database import DatabaseConfig
   from ktrdr.data.import_service.csv_import_service import CSVImportService
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend


   @pytest.fixture
   def import_service():
       """Create CSV import service for testing."""
       config = DatabaseConfig()
       if not config.is_postgresql:
           pytest.skip("PostgreSQL not configured")

       return CSVImportService()


   @pytest.fixture
   def test_csv_file(tmp_path):
       """Create temporary CSV file for testing."""
       # Create sample data
       dates = pd.date_range(start="2024-01-01", periods=5, freq="D")
       df = pd.DataFrame(
           {
               "open": [100.0, 101.0, 102.0, 103.0, 104.0],
               "high": [102.0, 103.0, 104.0, 105.0, 106.0],
               "low": [99.0, 100.0, 101.0, 102.0, 103.0],
               "close": [101.0, 102.0, 103.0, 104.0, 105.0],
               "volume": [1000000.0, 1100000.0, 1200000.0, 1300000.0, 1400000.0],
           },
           index=dates,
       )

       # Save to CSV
       csv_path = tmp_path / "TEST_IMPORT_1d.csv"
       df.to_csv(csv_path)

       return csv_path, df


   @pytest.mark.integration
   class TestCSVImportService:
       """Integration tests for CSV import service."""

       def test_import_symbol_success(self, import_service, test_csv_file):
           """Test successful import of one symbol."""
           csv_path, original_df = test_csv_file
           symbol = "TEST_IMPORT"
           timeframe = "1d"

           # Clean up any existing data
           backend = TimescaleDBBackend()
           backend.delete_data(symbol, timeframe)

           # Import
           result = import_service.import_symbol(symbol, timeframe)

           # Verify result
           assert result.success is True
           assert result.rows_imported == 5
           assert result.symbol == symbol
           assert result.timeframe == timeframe

           # Verify data in database
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == 5

       def test_import_symbol_idempotent(self, import_service, test_csv_file):
           """Test that importing same symbol twice is idempotent."""
           csv_path, original_df = test_csv_file
           symbol = "TEST_IDEMPOTENT_IMPORT"
           timeframe = "1d"

           # Clean up
           backend = TimescaleDBBackend()
           backend.delete_data(symbol, timeframe)

           # Import twice
           result1 = import_service.import_symbol(symbol, timeframe)
           result2 = import_service.import_symbol(symbol, timeframe)

           # Both should succeed
           assert result1.success is True
           assert result2.success is True

           # Verify only one copy in database
           loaded = backend.load_data(symbol, timeframe)
           assert len(loaded) == 5

       def test_import_symbol_no_csv(self, import_service):
           """Test importing non-existent symbol."""
           result = import_service.import_symbol("NONEXISTENT", "1d")

           assert result.success is False
           assert result.rows_imported == 0
           assert "No CSV data found" in result.error_message

       def test_import_all(self, import_service):
           """Test bulk import of all symbols."""
           timeframe = "1d"

           # Import all symbols for 1d timeframe
           summary = import_service.import_all(timeframe)

           # Verify summary
           assert summary.total_symbols > 0
           assert summary.successful >= 0
           assert summary.failed >= 0
           assert summary.total_symbols == summary.successful + summary.failed

       def test_import_all_with_symbol_list(self, import_service):
           """Test bulk import with specific symbol list."""
           symbols = ["AAPL", "GOOGL"]  # Assuming these exist in test data
           timeframe = "1d"

           summary = import_service.import_all(timeframe, symbols=symbols)

           assert summary.total_symbols == 2
           assert len(summary.results) == 2
   ```

**Quality Gate**:

```bash
# Start database
docker-compose -f docker/docker-compose.dev.yml up -d timescaledb

# Run migrations
docker exec -it ktrdr-timescaledb-dev bash /migrations/run_migrations.sh

# Run unit tests
make test-unit

# Run integration tests
export DB_TYPE=postgresql
make test-integration

docker-compose -f docker/docker-compose.dev.yml down

make quality
```

**Commit**: `feat(import): implement CSV import service for bulk data migration`

**Estimated Time**: 3 hours

---

**Phase 2 Checkpoint**:
✅ CSVImportService can import one symbol
✅ Service can import all symbols in data/ directory
✅ Idempotent imports (safe to run multiple times)
✅ Progress tracking and logging
✅ Integration tests verify import correctness
✅ **TESTABLE**: Import CSV → query database → data matches

**Total Phase 2 Time**: ~4.5 hours

---

## Summary

### Total Implementation Time (Phases 0-2)

| Phase | Focus | Tasks | Time | Testable? |
|-------|-------|-------|------|-----------|
| Phase 0: Infrastructure Verification | Verify existing setup | 3 tasks | ~4 hours | ✅ Yes! |
| Phase 1: TimescaleDB Backend | Data models + Backend implementation | 3 tasks | ~7 hours | ✅ Yes! |
| Phase 2: CSV Import Service | Bulk import from CSV | 2 tasks | ~4.5 hours | ✅ Yes! |
| **Total (Verification + Implementation)** | **Ready for migration** | **8 tasks** | **~15.5 hours** | **✅ Every phase!** |

### Next Steps

**Phase 3-4** (see IMPLEMENTATION_PLAN_PHASES_3-4.md):
- Phase 3: DataRepository Migration (add TimescaleDB backend option)
- Phase 4: Production Cutover (switch default backend, update documentation)

### Quality Standards

Every task must pass:

```bash
make test-unit           # All unit tests (existing + new)
make test-integration    # Integration tests with database
make quality             # Lint + format + typecheck
```

### Git Workflow

- **One branch**: All work on `feature/timescaledb-integration`
- **One commit per task**: Clear, descriptive commit messages
- **TDD**: Write tests first, then implementation
- **Vertical**: Each phase builds complete feature

---

**Next**: See [IMPLEMENTATION_PLAN_PHASES_3-4.md](IMPLEMENTATION_PLAN_PHASES_3-4.md) for migration and cutover phases
