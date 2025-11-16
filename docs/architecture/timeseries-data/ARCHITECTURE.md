# TimescaleDB Market Data Architecture

**Version**: 2.0
**Status**: Architecture Design
**Date**: 2025-01-15

---

## Table of Contents

1. [System Context](#system-context)
2. [Architectural Overview](#architectural-overview)
3. [Architectural Layers](#architectural-layers)
4. [Core Components](#core-components)
5. [Key Architectural Patterns](#key-architectural-patterns)
6. [Component Interactions](#component-interactions)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [Trade-offs and Design Decisions](#trade-offs-and-design-decisions)

---

## System Context

### Purpose

Migrate KTRDR's market data storage from CSV files to PostgreSQL + TimescaleDB to enable efficient time-series operations while preserving the existing DataRepository API and ensuring zero data loss during migration.

### Key Requirements

- **Interface Preservation**: Synchronous DataRepository API remains unchanged
- **Zero Data Loss**: All historical data migrates intact (data is critical for backtesting)
- **Query Performance**: <500ms for typical training loads (1 year, 5m bars)
- **Dual-Mode Safety**: CSV and DB coexist during migration with fallback capability
- **Infinite Retention**: Keep all data forever (no automatic deletion)

### Architecture Drivers

1. **Access Pattern Constraint**: Training/backtesting load ALL data for date ranges (not just recent)
2. **Market Hours Reality**: Markets don't align with clock hours (9:30 AM open ≠ 9:00 AM bucket)
3. **Consistency Requirement**: Adopt feature_id pattern from strategies (standardization)
4. **Performance Priority**: Optimize for read speed over storage savings (training time > disk cost)

---

## Architectural Overview

### System Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    KTRDR Application Layer                      │
│                                                                 │
│  ┌────────────────┐      ┌──────────────────┐                  │
│  │ Training       │      │ Backtesting      │                  │
│  │ Components     │      │ Components       │                  │
│  └────────┬───────┘      └────────┬─────────┘                  │
│           │                       │                            │
│           └───────────┬───────────┘                            │
│                       │                                        │
│              ┌────────▼────────┐                               │
│              │ DataRepository  │◄────── Unchanged API          │
│              │                 │                               │
│              └────────┬────────┘                               │
└───────────────────────┼────────────────────────────────────────┘
                        │
                        ▼
                 ┌──────────┐
                 │TimescaleDB│
                 │  Backend  │
                 └──────────┘
                  Read/Write
                  (Primary)

                 ┌──────────┐
                 │CSV Import│  (Operational tool - not in data path)
                 │ Service  │
                 └──────────┘
```

### Storage Architecture

```
PostgreSQL + TimescaleDB (Shared Instance)
│
├─ price_data (Hypertable, 7-day chunks)
│  └─ Base granularity: 5-minute bars
│
├─ indicators (Hypertable, 30-day chunks)
│  └─ Per-timeframe cached calculations
│
└─ checkpoint_* tables (Existing)
   └─ Operation checkpoint system
```

### Architectural Principles

1. **Direct Database Access**: Repository uses TimescaleDB backend exclusively
2. **Schema Minimalism**: Only essential columns (instrument, ts, OHLCV)
3. **Market-Aware Design**: No clock-based aggregation (respect market hours)
4. **Interface Stability**: DataRepository API unchanged (backward compatibility)
5. **Operational Flexibility**: CSV import tool for adding data as needed

---

## Architectural Layers

The system follows a three-layer architecture:

### 1. Application Layer

**Responsibility**: Consume market data without knowledge of storage backend

**Key Components**:

- Training pipelines (model input preparation)
- Backtesting engine (historical simulation)
- Indicator calculators (technical analysis)
- Fuzzy set generators (membership functions)

**Characteristics**:

- Uses DataRepository interface exclusively
- No changes required for migration
- Synchronous data access (existing pattern)

---

### 2. Repository Abstraction Layer

**Responsibility**: Provide unified data access interface to TimescaleDB

**Component**: `DataRepository` (uses TimescaleDB backend)

**Key Responsibilities**:

1. Delegate all operations to TimescaleDB backend
2. API compatibility preservation (same interface as before)
3. Connection management (SQLAlchemy engine)

**Interface** (preserved):

```python
class DataRepository:
    def load(self, symbol, timeframe, start_date=None, end_date=None):
        """Load OHLCV data from database."""

    def save(self, symbol, timeframe, data):
        """Save OHLCV data to database."""

    def list_symbols(self, timeframe=None):
        """List available symbols from database."""

    def get_date_range(self, symbol, timeframe):
        """Get min/max dates for symbol from database."""
```

**Simple Implementation**:

```python
class DataRepository:
    def __init__(self, connection_string):
        self.backend = TimescaleDBBackend(connection_string)

    def load(self, ...):
        return self.backend.load(...)  # Direct delegation
```

---

### 3. Storage Backend Layer

**Responsibility**: Implement data persistence and retrieval

**Backend**:

#### TimescaleDBBackend (Exclusive)

- PostgreSQL connection via SQLAlchemy
- Hypertable-aware queries
- Timeframe-agnostic (stores 5m only, pandas resamples)
- Connection pooling for concurrent access
- All reads and writes go through this backend

---

## Core Components

### DataRepository

**Architectural Role**: Central data access interface to TimescaleDB

**Location**: `ktrdr/data/repository/data_repository.py`

**Implementation Pattern**:

```python
class DataRepository:
    """Repository with TimescaleDB backend."""

    def __init__(self, connection_string):
        self.backend = TimescaleDBBackend(connection_string)

    def load(self, symbol, timeframe, start_date, end_date):
        """Load data from TimescaleDB."""
        return self.backend.load(symbol, timeframe, start_date, end_date)

    def save(self, symbol, timeframe, data):
        """Save data to TimescaleDB."""
        self.backend.save(symbol, timeframe, data)
```

**Key Characteristics**:

- Stateless (no internal cache, relies on backend)
- Direct delegation to TimescaleDB
- Preserves existing interface (no breaking changes)
- Simple, straightforward implementation

---

### TimescaleDBBackend

**Architectural Role**: Primary storage implementation using PostgreSQL + TimescaleDB

**Location**: `ktrdr/data/backends/timescaledb_backend.py`

**Core Responsibilities**:

1. **Connection Management**: SQLAlchemy engine with connection pooling
2. **Query Execution**: Hypertable-aware SQL generation
3. **Data Transformation**: pandas DataFrame ↔ PostgreSQL rows
4. **Error Handling**: Database errors → DataError/DataNotFoundError

**Connection Architecture**:

```python
class TimescaleDBBackend:
    def __init__(self, connection_string, pool_size=10):
        self.engine = create_engine(
            connection_string,
            pool_size=pool_size,
            pool_pre_ping=True  # Verify connections before use
        )
```

**Query Pattern**:

```python
def load(self, symbol, timeframe, start_date, end_date):
    """
    Load OHLCV data from price_data hypertable.

    Pattern:
    1. Build SQL with timestamp range filters
    2. Execute via SQLAlchemy connection
    3. Return as pandas DataFrame (indexed by ts)
    4. Raise DataNotFoundError if empty result
    """
    query = """
        SELECT ts, open, high, low, close, volume
        FROM price_data
        WHERE instrument = :symbol
          AND ts >= :start_date
          AND ts < :end_date
        ORDER BY ts
    """
    # Hypertable automatically uses partition pruning
```

**Timeframe Handling**:

- **Storage**: Always 5-minute bars only
- **Retrieval**: pandas.resample() for other timeframes
- **Rationale**: Market-aware resampling (respects trading hours)

---

### CSVImportService

**Architectural Role**: Import CSV data into TimescaleDB (idempotent operation)

**Location**: `ktrdr/data/import/csv_import_service.py`

**Core Responsibilities**:

1. **Symbol Discovery**: Scan CSV directory for files
2. **Idempotent Import**: Load CSV → Insert new data, skip existing
3. **Conflict Detection**: Warn if CSV data differs from existing DB data
4. **Progress Tracking**: OperationsService integration
5. **Gap Filling**: Import specific date ranges on demand

**Import Flow (Idempotent)**:

```
CSV Discovery
    │
    ├─> Scan data/ directory for *.csv files
    └─> Build list: [(symbol, timeframe), ...]

For each (symbol, timeframe):
    │
    ├─> Load from CSV (CSVBackend.load)
    ├─> Validate DataFrame (required columns, DatetimeIndex)
    │
    └─> For each timestamp in CSV:
        │
        ├─> Query DB for existing data at timestamp
        │
        ├─> If exists:
        │   ├─> Compare values (warn if different)
        │   └─> Skip (idempotent)
        │
        └─> If not exists:
            └─> Insert into DB (new data)
```

**Use Cases**:

```python
# Initial migration: Import all historical data
service.import_all()

# Ongoing: User downloads new data to CSV, then imports
service.import_symbol("AAPL", "5m")  # Only inserts new timestamps

# Gap filling: Import specific date range
service.import_range("AAPL", "5m", "2024-01-01", "2024-01-31")
```

---

## Key Architectural Patterns

### Pattern 1: Backend Abstraction

**Problem**: Need to support multiple storage backends without code changes

**Solution**: Repository delegates to backend implementations via common interface

```python
# Backend interface (implicit contract)
class DataBackend:
    def load(self, symbol, timeframe, start_date, end_date) -> pd.DataFrame:
        pass

    def save(self, symbol, timeframe, data: pd.DataFrame) -> None:
        pass

# Repository delegates based on configuration
class DataRepository:
    def load(self, ...):
        return self.active_backend.load(...)
```

**Benefits**:

- Application layer unaware of storage changes
- Easy A/B testing between backends
- Graceful fallback on errors

---

### Pattern 2: Hypertable Partitioning

**Problem**: Large time-series datasets slow to query without partitioning

**Solution**: TimescaleDB hypertables with time-based chunking

```sql
-- Create table
CREATE TABLE price_data (
    instrument TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (instrument, ts)
);

-- Convert to hypertable (automatic partitioning)
SELECT create_hypertable('price_data', 'ts', chunk_time_interval => INTERVAL '7 days');
```

**Chunk Strategy**:

- **7-day chunks**: ~52 chunks per year
- **Partition pruning**: Query only scans relevant chunks
- **Index per chunk**: Each chunk has (instrument, ts) index

**Query Optimization**:

```sql
-- Query: Load AAPL for 2024
SELECT * FROM price_data
WHERE instrument = 'AAPL'
  AND ts >= '2024-01-01'
  AND ts < '2025-01-01';

-- Execution:
-- 1. Constraint exclusion: Only scan 2024 chunks (~52 chunks)
-- 2. Index seek: Use (instrument, ts) index within each chunk
-- 3. Sequential scan: Read matching rows
```

---

### Pattern 3: Feature ID Standardization

**Problem**: Need consistent indicator identification across system

**Solution**: Adopt feature_id pattern from strategies (e.g., "rsi_14", "macd_12_26_9")

**Consistency Benefit**:

```yaml
# Strategy config (existing)
indicators:
  - feature_id: rsi_14
    indicator_name: RSI
    parameters: {period: 14}
```

```sql
-- Indicator cache (new)
CREATE TABLE indicators (
    instrument TEXT,
    timeframe TEXT,
    feature_id TEXT,  -- "rsi_14" (matches strategy)
    ts TIMESTAMPTZ,
    value DOUBLE PRECISION,
    PRIMARY KEY (instrument, timeframe, feature_id, ts)
);
```

**Benefits**:

- Single naming scheme across codebase
- Simpler queries (TEXT equality vs JSONB)
- Consistent with existing patterns

---

## Component Interactions

### Data Ingestion Flow (IB → Database)

```
┌─────────────────┐
│ IB Gateway      │
└────────┬────────┘
         │ Historical bars
         ▼
┌─────────────────┐
│DataAcquisition  │
│   Service       │
└────────┬────────┘
         │ pd.DataFrame
         ▼
┌─────────────────┐
│ DataRepository  │
│  .save()        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ TimescaleDB     │
│ Backend         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TimescaleDB    │
│   price_data    │
│  (hypertable)   │
└─────────────────┘
```

---

### Data Consumption Flow (Database → Training)

```
┌─────────────────┐
│ Training        │
│ Pipeline        │
└────────┬────────┘
         │ request: AAPL, 5m, 2024-01-01 to 2024-12-31
         ▼
┌─────────────────┐
│ DataRepository  │
│  .load()        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ TimescaleDB     │
│ Backend         │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Query   │ SELECT * FROM price_data
    │         │ WHERE instrument='AAPL'
    │         │   AND ts >= '2024-01-01'
    │         │   AND ts < '2025-01-01';
    └────┬────┘
         │
         ▼
┌─────────────────┐
│ TimescaleDB     │
│ price_data      │
│ (hypertable)    │
└────────┬────────┘
         │ pd.DataFrame (105,120 rows)
         ▼
┌─────────────────┐
│ Training        │
│ Pipeline        │
│ (receives data) │
└─────────────────┘
```

---

### CSV Import Flow (Idempotent)

```
┌─────────────────┐
│ CSV Import      │
│ Service         │
└────────┬────────┘
         │
         ├─> Discover: Scan data/*.csv
         │   └─> List: [(AAPL,5m), (MSFT,5m), ...]
         │
         └─> For each (symbol, timeframe):
             │
             ├─> Load from CSV
             │   └─> CSVBackend.load()
             │
             ├─> For each timestamp:
             │   │
             │   ├─> Query DB: exists?
             │   │
             │   ├─> If exists:
             │   │   └─> Compare values, skip
             │   │
             │   └─> If not exists:
             │       └─> Insert to DB (new data)
             │
             └─> Report: X new rows, Y skipped, Z warnings
```

---

## Cross-Cutting Concerns

### Performance Optimization

**Query Performance**:

- **Hypertable partitioning**: Automatic chunk pruning
- **Primary key indexing**: (instrument, ts) clustered index
- **No compression**: Optimize for read speed (training workload)
- **Connection pooling**: Reuse connections (pool_size=10)

**Expected Performance**:

- Single symbol, 1 year, 5m bars: **<500ms** (vs CSV ~2s)
- Single symbol, 5 years, 5m bars: **<2s**
- Multi-symbol (10), 1 year: **<5s**

---

### Data Integrity

**Validation Layers**:

1. **Ingestion**: DataQualityValidator (existing)
2. **Storage**: PostgreSQL constraints (NOT NULL, PK uniqueness)
3. **Migration**: Row count + spot check comparison

**Constraints**:

```sql
-- Primary key enforces uniqueness
PRIMARY KEY (instrument, ts)

-- NOT NULL enforces completeness
open DOUBLE PRECISION NOT NULL
-- ... all OHLCV columns NOT NULL
```

---

### Error Handling

**Error Types**:

1. **DataNotFoundError**: No data for symbol/timeframe/date range
2. **DataError**: Database connection/query failures
3. **MigrationError**: Migration validation failures

**Handling Strategy**:

```python
# DataRepository error handling
try:
    return self.db_backend.load(...)
except DataNotFoundError:
    # Try CSV fallback (dual mode only)
    return self.csv_backend.load(...)
except DataError as e:
    # Log and re-raise (connection/query failure)
    logger.error(f"Database error: {e}")
    raise
```

---

### Observability

The TimescaleDB migration uses OpenTelemetry for comprehensive distributed tracing. All operations are instrumented with spans for performance analysis and debugging.

#### OpenTelemetry Spans

**DataRepository Operations**:

```python
@trace_service_method("data.repository.load")
async def load(self, symbol, timeframe, start_date, end_date):
    """
    Span attributes:
    - data.symbol: Symbol identifier (e.g., "AAPL")
    - data.timeframe: Timeframe (e.g., "5m", "1h")
    - data.start_date: Query start date
    - data.end_date: Query end date
    - data.rows_loaded: Number of rows returned
    - data.backend: "timescaledb"
    - db.query_duration_ms: Query execution time
    """

@trace_service_method("data.repository.save")
async def save(self, symbol, timeframe, data):
    """
    Span attributes:
    - data.symbol: Symbol identifier
    - data.timeframe: Timeframe
    - data.rows_saved: Number of rows inserted
    - data.backend: "timescaledb"
    - db.insert_duration_ms: Insert execution time
    """

@trace_service_method("data.repository.list_symbols")
async def list_symbols(self, timeframe):
    """
    Span attributes:
    - data.timeframe: Timeframe filter (optional)
    - data.symbols_count: Number of symbols found
    - data.backend: "timescaledb"
    """
```

**TimescaleDBBackend Operations**:

```python
with create_service_span("timescaledb.query") as span:
    """
    Span attributes:
    - db.system: "postgresql"
    - db.name: Database name
    - db.operation: "SELECT"
    - db.statement: SQL query (truncated if >500 chars)
    - db.rows_affected: Number of rows returned
    - db.query_duration_ms: Query execution time
    - db.connection_pool.size: Current pool size
    - db.connection_pool.available: Available connections
    """

with create_service_span("timescaledb.insert") as span:
    """
    Span attributes:
    - db.system: "postgresql"
    - db.name: Database name
    - db.operation: "INSERT"
    - db.rows_affected: Number of rows inserted
    - db.insert_duration_ms: Insert execution time
    - db.batch_size: Rows per batch (if bulk insert)
    """

with create_service_span("timescaledb.connection_acquire") as span:
    """
    Span attributes:
    - db.connection_pool.wait_time_ms: Time waiting for connection
    - db.connection_pool.size: Current pool size
    - db.connection_pool.available: Available connections
    """
```

**CSVImportService Operations**:

```python
@trace_service_method("csv_import.import_all")
async def import_all(self):
    """
    Top-level span for importing all CSV data.

    Span attributes:
    - csv_import.total_symbols: Number of symbols discovered
    - csv_import.total_rows_imported: Total rows inserted
    - csv_import.total_rows_skipped: Total rows skipped
    - csv_import.warnings_count: Number of data mismatches
    - csv_import.duration_ms: Total import duration
    - operation.id: Associated operation ID (if tracked)
    - operation.type: "DATA_MIGRATION"
    """

@trace_service_method("csv_import.import_symbol")
async def import_symbol(self, symbol, timeframe):
    """
    Span attributes:
    - data.symbol: Symbol being imported
    - data.timeframe: Timeframe
    - csv_import.rows_imported: New rows inserted
    - csv_import.rows_skipped: Existing rows skipped
    - csv_import.warnings: Data mismatch warnings
    - csv_import.duration_ms: Symbol import duration
    """

with create_service_span("csv_import.discover_symbols") as span:
    """
    Span attributes:
    - csv_import.directory: CSV directory path
    - csv_import.symbols_found: Number of CSV files discovered
    - csv_import.discovery_duration_ms: Discovery time
    """

with create_service_span("csv_import.check_exists") as span:
    """
    Span attributes:
    - data.symbol: Symbol identifier
    - data.timestamp: Timestamp being checked
    - csv_import.row_exists: true/false
    - db.query_duration_ms: Existence check time
    """

with create_service_span("csv_import.compare_values") as span:
    """
    Span attributes:
    - data.symbol: Symbol identifier
    - data.timestamp: Timestamp
    - csv_import.values_match: true/false
    - csv_import.csv_value: CSV OHLCV values (if mismatch)
    - csv_import.db_value: Database OHLCV values (if mismatch)
    """

with create_service_span("csv_import.insert_batch") as span:
    """
    Span attributes:
    - data.symbol: Symbol identifier
    - db.batch_size: Number of rows in batch
    - db.insert_duration_ms: Batch insert time
    """
```

**Migration/Cutover Operations**:

```python
@trace_service_method("migration.verify_data")
async def verify_migration(self, symbol, timeframe):
    """
    Span attributes:
    - data.symbol: Symbol being verified
    - data.timeframe: Timeframe
    - migration.csv_row_count: CSV row count
    - migration.db_row_count: Database row count
    - migration.rows_match: true/false
    - migration.spot_check_passed: true/false
    - migration.verification_duration_ms: Verification time
    """

with create_service_span("migration.compare_csv_db") as span:
    """
    Span attributes:
    - data.symbol: Symbol identifier
    - migration.sample_size: Number of rows compared
    - migration.mismatches: Number of value mismatches
    - migration.mismatch_timestamps: Timestamps with differences
    """
```

#### Span Hierarchy Example

Complete trace for CSV import operation:

```
csv_import.import_all (300s)
│
├─> csv_import.discover_symbols (5s)
│   └─> 47 symbols discovered
│
├─> csv_import.import_symbol [AAPL, 5m] (120s)
│   ├─> data.repository.load [CSV] (2s)
│   │   └─> 105,120 rows loaded
│   │
│   ├─> csv_import.check_exists (60s)
│   │   ├─> timescaledb.query (0.05s) × 105,120
│   │   └─> 95,000 exist, 10,120 new
│   │
│   ├─> csv_import.compare_values (5s)
│   │   └─> 3 warnings (data mismatches)
│   │
│   └─> csv_import.insert_batch (53s)
│       ├─> timescaledb.insert [batch 1-10,000] (5s)
│       └─> timescaledb.insert [batch 10,001-10,120] (0.5s)
│
├─> csv_import.import_symbol [MSFT, 5m] (95s)
│   └─> ... (same structure)
│
└─> csv_import.import_symbol [EURUSD, 5m] (85s)
    └─> ... (same structure)
```

#### Attribute Mapping Extensions

Add to `ktrdr/monitoring/service_telemetry.py`:

```python
ATTRIBUTE_MAPPING = {
    # ... existing mappings ...

    # Data operations
    "symbol": "data.symbol",
    "timeframe": "data.timeframe",
    "start_date": "data.start_date",
    "end_date": "data.end_date",

    # CSV import operations
    "rows_imported": "csv_import.rows_imported",
    "rows_skipped": "csv_import.rows_skipped",
    "warnings": "csv_import.warnings",

    # Database operations
    "query_duration_ms": "db.query_duration_ms",
    "insert_duration_ms": "db.insert_duration_ms",
    "batch_size": "db.batch_size",
    "rows_affected": "db.rows_affected",
}
```

#### Debugging with Observability

**Query by Operation ID** (CSV import):

```bash
curl -s "http://localhost:16686/api/traces?tag=operation.type:DATA_MIGRATION&limit=10" | jq
```

**Analyze Import Performance**:

```bash
# Find slowest symbol import
curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
  .data[0].spans[] |
  select(.operationName == "csv_import.import_symbol") |
  {
    symbol: (.tags[] | select(.key == "data.symbol") | .value),
    duration_ms: (.duration / 1000)
  }' | jq -s 'sort_by(.duration_ms) | reverse'
```

**Identify Database Bottlenecks**:

```bash
# Check database operation durations
curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
  .data[0].spans[] |
  select(.operationName | startswith("timescaledb.")) |
  {
    operation: .operationName,
    duration_ms: (.duration / 1000),
    rows: (.tags[] | select(.key == "db.rows_affected") | .value)
  }' | jq -s 'sort_by(.duration_ms) | reverse | .[0:10]'
```

#### Logging

**Structured Logging** (in addition to traces):

- Query execution time (slow log threshold: >1s)
- CSV import progress (rows processed, warnings)
- Data validation warnings (CSV vs DB mismatches)
- Connection pool status (on acquisition failures)

**Log Correlation**:

All logs include `operation_id` for trace correlation:

```python
logger.info(
    "CSV import completed",
    extra={
        "operation_id": operation_id,
        "symbol": symbol,
        "rows_imported": rows_imported,
    }
)
```

#### Metrics (Future)

Prometheus metrics for operational monitoring:

- `ktrdr_db_query_duration_seconds` (histogram) - Query execution time
- `ktrdr_db_connection_pool_size` (gauge) - Current pool size
- `ktrdr_db_connection_pool_available` (gauge) - Available connections
- `ktrdr_csv_import_rows_total` (counter) - Total rows imported
- `ktrdr_csv_import_duration_seconds` (histogram) - Import operation duration
- `ktrdr_csv_import_warnings_total` (counter) - Data mismatch warnings

---

## Trade-offs and Design Decisions

### Summary of Key Decisions

See [DESIGN.md](./DESIGN.md) for detailed rationale.

1. **No Continuous Aggregates**: Store 5m only, resample in pandas (market-aware)
2. **No Compression**: Optimize for read speed (training access pattern)
3. **Minimal Schema**: 7 columns only (instrument, ts, OHLCV)
4. **feature_id Standardization**: Adopt strategy pattern (consistency)
5. **Single Index**: PK (instrument, ts) sufficient (query pattern match)

---

## Next Steps

1. **Review & Approve** this architecture document
2. **Create IMPLEMENTATION_PLAN.md** with migration phases
3. **Begin Phase 0** (PostgreSQL infrastructure setup)

**Related Documents**:

- **[DESIGN.md](./DESIGN.md)** - Design decisions and trade-offs
- **[OBSERVABILITY.md](./OBSERVABILITY.md)** - OpenTelemetry instrumentation reference
- **IMPLEMENTATION_PLAN.md** - Phased migration approach (to be created)

---

**Document End**
