# TimescaleDB Migration - Observability Instrumentation Reference

**Version**: 1.0
**Status**: Design Phase
**Date**: 2025-01-15

---

## Table of Contents

1. [Overview](#overview)
2. [Instrumentation Requirements](#instrumentation-requirements)
3. [Span Definitions](#span-definitions)
4. [Attribute Mapping Extensions](#attribute-mapping-extensions)
5. [Implementation Guidelines](#implementation-guidelines)
6. [Debugging Workflows](#debugging-workflows)

---

## Overview

This document defines the OpenTelemetry instrumentation requirements for the TimescaleDB migration. All database operations, CSV imports, and data repository methods must be instrumented with spans to enable performance analysis and debugging.

### Design Principles

1. **Comprehensive Coverage**: Every external operation (database query, file I/O) gets a span
2. **Business Context**: Spans include business attributes (symbol, timeframe, operation type)
3. **Performance Visibility**: Capture durations, row counts, and resource utilization
4. **Debugging Support**: Enable first-response diagnosis via Jaeger queries
5. **Minimal Overhead**: <1ms per span, negligible compared to database operations

### Observability Stack

- **OpenTelemetry SDK**: Instrumentation framework
- **Jaeger**: Distributed tracing UI (http://localhost:16686)
- **Grafana**: Unified dashboards (http://localhost:3000)
- **Prometheus**: Metrics collection (optional, future)

---

## Instrumentation Requirements

### Required Instrumentation Locations

All code paths in these components MUST be instrumented:

1. **DataRepository** (`ktrdr/data/repository/data_repository.py`)
   - `load()` method
   - `save()` method
   - `list_symbols()` method
   - `get_date_range()` method

2. **TimescaleDBBackend** (`ktrdr/data/backends/timescaledb_backend.py`)
   - Query execution (SELECT)
   - Insert operations (INSERT, batch inserts)
   - Connection pool acquisition
   - Schema operations (CREATE TABLE, hypertable conversion)

3. **CSVImportService** (`ktrdr/data/import/csv_import_service.py`)
   - `import_all()` method (top-level operation)
   - `import_symbol()` method (per-symbol import)
   - Symbol discovery (CSV file scanning)
   - Row-level operations (existence check, value comparison, insert)

4. **Migration Verification** (utilities/scripts)
   - Data validation (CSV vs DB comparison)
   - Row count verification
   - Spot-check sampling

---

## Span Definitions

### DataRepository Spans

#### `data.repository.load`

**Purpose**: Track data loading performance from TimescaleDB

**Decorator**: `@trace_service_method("data.repository.load")`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier (e.g., "AAPL")
- `data.timeframe` (str): Timeframe (e.g., "5m", "1h")
- `data.start_date` (str): Query start date
- `data.end_date` (str): Query end date
- `data.rows_loaded` (int): Number of rows returned
- `data.backend` (str): "timescaledb" (always)
- `db.query_duration_ms` (float): Backend query execution time

**Status Codes**:
- `OK`: Data loaded successfully
- `ERROR`: Database error or DataNotFoundError

**Example**:
```python
@trace_service_method("data.repository.load")
async def load(self, symbol: str, timeframe: str, start_date: str, end_date: str):
    with create_service_span("timescaledb.query") as span:
        # Query database
        df = self.backend.load(symbol, timeframe, start_date, end_date)
        span.set_attribute("data.rows_loaded", len(df))
        span.set_attribute("data.backend", "timescaledb")
    return df
```

---

#### `data.repository.save`

**Purpose**: Track data insertion performance to TimescaleDB

**Decorator**: `@trace_service_method("data.repository.save")`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier
- `data.timeframe` (str): Timeframe
- `data.rows_saved` (int): Number of rows inserted
- `data.backend` (str): "timescaledb"
- `db.insert_duration_ms` (float): Backend insert execution time

**Status Codes**:
- `OK`: Data saved successfully
- `ERROR`: Database error (duplicate key, constraint violation)

---

#### `data.repository.list_symbols`

**Purpose**: Track symbol listing performance

**Decorator**: `@trace_service_method("data.repository.list_symbols")`

**Required Attributes**:
- `data.timeframe` (str, optional): Timeframe filter
- `data.symbols_count` (int): Number of symbols found
- `data.backend` (str): "timescaledb"

---

### TimescaleDBBackend Spans

#### `timescaledb.query`

**Purpose**: Track individual database query execution

**Context Manager**: `with create_service_span("timescaledb.query") as span:`

**Required Attributes**:
- `db.system` (str): "postgresql"
- `db.name` (str): Database name
- `db.operation` (str): "SELECT"
- `db.statement` (str): SQL query (truncate to 500 chars)
- `db.rows_affected` (int): Number of rows returned
- `db.query_duration_ms` (float): Query execution time
- `db.connection_pool.size` (int): Current pool size
- `db.connection_pool.available` (int): Available connections

**Implementation**:
```python
with create_service_span("timescaledb.query") as span:
    start = time.perf_counter()

    # Set database context
    span.set_attribute("db.system", "postgresql")
    span.set_attribute("db.name", self.db_name)
    span.set_attribute("db.operation", "SELECT")
    span.set_attribute("db.statement", query[:500])  # Truncate

    # Execute query
    result = conn.execute(query, params)

    # Record metrics
    duration_ms = (time.perf_counter() - start) * 1000
    span.set_attribute("db.query_duration_ms", duration_ms)
    span.set_attribute("db.rows_affected", len(result))

    # Connection pool status
    span.set_attribute("db.connection_pool.size", self.engine.pool.size())
    span.set_attribute("db.connection_pool.available", self.engine.pool.available())
```

---

#### `timescaledb.insert`

**Purpose**: Track data insertion operations

**Context Manager**: `with create_service_span("timescaledb.insert") as span:`

**Required Attributes**:
- `db.system` (str): "postgresql"
- `db.name` (str): Database name
- `db.operation` (str): "INSERT"
- `db.rows_affected` (int): Number of rows inserted
- `db.insert_duration_ms` (float): Insert execution time
- `db.batch_size` (int): Rows per batch (if bulk insert)

---

#### `timescaledb.connection_acquire`

**Purpose**: Track connection pool acquisition time

**Context Manager**: `with create_service_span("timescaledb.connection_acquire") as span:`

**Required Attributes**:
- `db.connection_pool.wait_time_ms` (float): Time waiting for connection
- `db.connection_pool.size` (int): Current pool size
- `db.connection_pool.available` (int): Available connections before acquisition

**Use Case**: Diagnose connection pool exhaustion

---

### CSVImportService Spans

#### `csv_import.import_all`

**Purpose**: Top-level span for importing all CSV data

**Decorator**: `@trace_service_method("csv_import.import_all")`

**Required Attributes**:
- `csv_import.total_symbols` (int): Number of symbols discovered
- `csv_import.total_rows_imported` (int): Total rows inserted across all symbols
- `csv_import.total_rows_skipped` (int): Total rows skipped (already exist)
- `csv_import.warnings_count` (int): Number of data mismatches
- `csv_import.duration_ms` (float): Total import duration
- `operation.id` (str): Associated operation ID (if tracked by OperationsService)
- `operation.type` (str): "DATA_MIGRATION"

**Span Hierarchy**:
```
csv_import.import_all
├─> csv_import.discover_symbols
├─> csv_import.import_symbol (per symbol)
│   ├─> data.repository.load (CSV)
│   ├─> csv_import.check_exists (per row)
│   ├─> csv_import.compare_values (if row exists)
│   └─> csv_import.insert_batch
│       └─> timescaledb.insert
└─> csv_import.import_symbol (next symbol)
```

---

#### `csv_import.import_symbol`

**Purpose**: Import a single symbol from CSV to database

**Decorator**: `@trace_service_method("csv_import.import_symbol")`

**Required Attributes**:
- `data.symbol` (str): Symbol being imported
- `data.timeframe` (str): Timeframe
- `csv_import.rows_imported` (int): New rows inserted
- `csv_import.rows_skipped` (int): Existing rows skipped
- `csv_import.warnings` (int): Data mismatch warnings
- `csv_import.duration_ms` (float): Symbol import duration

---

#### `csv_import.discover_symbols`

**Purpose**: Scan CSV directory for available files

**Context Manager**: `with create_service_span("csv_import.discover_symbols") as span:`

**Required Attributes**:
- `csv_import.directory` (str): CSV directory path
- `csv_import.symbols_found` (int): Number of CSV files discovered
- `csv_import.discovery_duration_ms` (float): Discovery time

---

#### `csv_import.check_exists`

**Purpose**: Check if row already exists in database (idempotency check)

**Context Manager**: `with create_service_span("csv_import.check_exists") as span:`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier
- `data.timestamp` (str): Timestamp being checked
- `csv_import.row_exists` (bool): true/false
- `db.query_duration_ms` (float): Existence check query time

**Performance Note**: This span will be created millions of times during import. Keep attribute count minimal.

---

#### `csv_import.compare_values`

**Purpose**: Compare CSV values with existing database values (data validation)

**Context Manager**: `with create_service_span("csv_import.compare_values") as span:`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier
- `data.timestamp` (str): Timestamp
- `csv_import.values_match` (bool): true/false
- `csv_import.csv_value` (str, optional): CSV OHLCV values (only if mismatch)
- `csv_import.db_value` (str, optional): Database OHLCV values (only if mismatch)

**Use Case**: Track data quality issues during import

---

#### `csv_import.insert_batch`

**Purpose**: Insert batch of new rows into database

**Context Manager**: `with create_service_span("csv_import.insert_batch") as span:`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier
- `db.batch_size` (int): Number of rows in batch
- `db.insert_duration_ms` (float): Batch insert time

---

### Migration Verification Spans

#### `migration.verify_data`

**Purpose**: Verify data integrity after migration

**Decorator**: `@trace_service_method("migration.verify_data")`

**Required Attributes**:
- `data.symbol` (str): Symbol being verified
- `data.timeframe` (str): Timeframe
- `migration.csv_row_count` (int): CSV row count
- `migration.db_row_count` (int): Database row count
- `migration.rows_match` (bool): true/false
- `migration.spot_check_passed` (bool): true/false (sample comparison)
- `migration.verification_duration_ms` (float): Verification time

---

#### `migration.compare_csv_db`

**Purpose**: Spot-check comparison of CSV vs database values

**Context Manager**: `with create_service_span("migration.compare_csv_db") as span:`

**Required Attributes**:
- `data.symbol` (str): Symbol identifier
- `migration.sample_size` (int): Number of rows compared
- `migration.mismatches` (int): Number of value mismatches
- `migration.mismatch_timestamps` (list[str]): Timestamps with differences (truncate to 10)

---

## Attribute Mapping Extensions

### Existing Mappings (Already in `service_telemetry.py`)

```python
ATTRIBUTE_MAPPING = {
    "symbol": "data.symbol",
    "timeframe": "data.timeframe",
    "start_date": "data.start_date",
    "end_date": "data.end_date",
    "batch_size": "training.batch_size",  # Can reuse for db.batch_size
    # ... other existing mappings
}
```

### New Mappings Required for TimescaleDB Migration

Add to `ktrdr/monitoring/service_telemetry.py`:

```python
ATTRIBUTE_MAPPING = {
    # ... existing mappings ...

    # CSV import attributes
    "rows_imported": "csv_import.rows_imported",
    "rows_skipped": "csv_import.rows_skipped",
    "warnings": "csv_import.warnings",
    "warnings_count": "csv_import.warnings_count",
    "total_symbols": "csv_import.total_symbols",
    "total_rows_imported": "csv_import.total_rows_imported",
    "total_rows_skipped": "csv_import.total_rows_skipped",

    # Database operation attributes
    "query_duration_ms": "db.query_duration_ms",
    "insert_duration_ms": "db.insert_duration_ms",
    "rows_affected": "db.rows_affected",
    "rows_loaded": "data.rows_loaded",
    "rows_saved": "data.rows_saved",

    # Migration verification attributes
    "csv_row_count": "migration.csv_row_count",
    "db_row_count": "migration.db_row_count",
    "rows_match": "migration.rows_match",
    "spot_check_passed": "migration.spot_check_passed",
}
```

---

## Implementation Guidelines

### Using `@trace_service_method` Decorator

For top-level service methods:

```python
from ktrdr.monitoring.service_telemetry import trace_service_method

class DataRepository:
    @trace_service_method("data.repository.load")
    async def load(self, symbol: str, timeframe: str, start_date: str, end_date: str):
        """
        Decorator automatically:
        - Creates span named "data.repository.load"
        - Maps parameters to OTEL attributes (symbol → data.symbol)
        - Sets span status (OK or ERROR)
        - Records exceptions
        """
        # Your implementation
        return data
```

### Using `create_service_span` Context Manager

For nested operations or custom spans:

```python
from ktrdr.monitoring.service_telemetry import create_service_span

class TimescaleDBBackend:
    def load(self, symbol, timeframe, start_date, end_date):
        with create_service_span("timescaledb.query") as span:
            # Set custom attributes
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.operation", "SELECT")

            # Execute operation
            start = time.perf_counter()
            result = self._execute_query(query, params)

            # Record metrics
            duration_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("db.query_duration_ms", duration_ms)
            span.set_attribute("db.rows_affected", len(result))

        return result
```

### Error Handling

Spans automatically record exceptions, but ensure proper cleanup:

```python
with create_service_span("csv_import.import_symbol", symbol=symbol) as span:
    try:
        # Import logic
        rows_imported = import_data()
        span.set_attribute("csv_import.rows_imported", rows_imported)

    except DataError as e:
        # Exception automatically recorded in span
        span.set_attribute("error.type", "DataError")
        span.set_attribute("error.symbol", symbol)
        raise  # Re-raise after recording context
```

### Performance Considerations

1. **Minimize Span Count**: Don't create spans for trivial operations (<1ms)
2. **Batch Attribute Updates**: Set multiple attributes at once when possible
3. **Truncate Large Values**: Limit string attributes to 500 chars
4. **Avoid Nested Loops**: Don't create spans inside tight loops (>1000 iterations)

**Example - Good (Batch-Level Span)**:
```python
with create_service_span("csv_import.insert_batch") as span:
    for row in batch:  # 10,000 rows
        insert_row(row)  # No span per row
    span.set_attribute("db.batch_size", len(batch))
```

**Example - Bad (Row-Level Span)**:
```python
for row in batch:  # 10,000 rows
    with create_service_span("csv_import.insert_row"):  # ❌ Too many spans!
        insert_row(row)
```

---

## Debugging Workflows

### Workflow 1: Diagnose Slow CSV Import

**Symptom**: User reports CSV import taking >10 minutes

**Steps**:

1. **Get Operation ID** from CLI output or API response
2. **Query Jaeger** for the trace:
   ```bash
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq
   ```

3. **Find Slowest Symbol**:
   ```bash
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
     .data[0].spans[] |
     select(.operationName == "csv_import.import_symbol") |
     {
       symbol: (.tags[] | select(.key == "data.symbol") | .value),
       duration_ms: (.duration / 1000)
     }' | jq -s 'sort_by(.duration_ms) | reverse | .[0]'
   ```

4. **Identify Bottleneck Phase** (check_exists vs insert_batch):
   ```bash
   # Check which phase took longest for slow symbol
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
     .data[0].spans[] |
     select(.tags[] | select(.key == "data.symbol" and .value == "AAPL")) |
     select(.operationName | startswith("csv_import.")) |
     {
       phase: .operationName,
       duration_ms: (.duration / 1000)
     }' | jq -s 'sort_by(.duration_ms) | reverse'
   ```

5. **Diagnose**:
   - If `csv_import.check_exists` is slow → Check database index, connection pool
   - If `csv_import.insert_batch` is slow → Check batch size, database contention
   - If `csv_import.compare_values` is slow → Too many warnings (data quality issue)

---

### Workflow 2: Track Data Quality Issues

**Symptom**: Need to verify data integrity after import

**Steps**:

1. **Count Warnings**:
   ```bash
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
     .data[0].spans[] |
     select(.operationName == "csv_import.import_symbol") |
     {
       symbol: (.tags[] | select(.key == "data.symbol") | .value),
       warnings: (.tags[] | select(.key == "csv_import.warnings") | .value)
     }' | jq -s 'map(select(.warnings != "0"))'
   ```

2. **Identify Affected Symbols**:
   - Query spans with `csv_import.values_match: false`
   - Check `csv_import.csv_value` vs `csv_import.db_value` attributes

3. **Validate**:
   - Use `migration.verify_data` spans to confirm row counts match
   - Check `migration.spot_check_passed` for sample comparison results

---

### Workflow 3: Monitor Database Performance

**Symptom**: Database queries slower than expected

**Steps**:

1. **Check Query Durations**:
   ```bash
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
     .data[0].spans[] |
     select(.operationName == "timescaledb.query") |
     {
       query_duration_ms: (.tags[] | select(.key == "db.query_duration_ms") | .value),
       rows: (.tags[] | select(.key == "db.rows_affected") | .value)
     }' | jq -s 'sort_by(.query_duration_ms | tonumber) | reverse | .[0:10]'
   ```

2. **Check Connection Pool Status**:
   ```bash
   curl -s "http://localhost:16686/api/traces?tag=operation.id:op_migration_..." | jq '
     .data[0].spans[] |
     select(.operationName == "timescaledb.connection_acquire") |
     {
       wait_time_ms: (.tags[] | select(.key == "db.connection_pool.wait_time_ms") | .value),
       pool_available: (.tags[] | select(.key == "db.connection_pool.available") | .value)
     }' | jq -s 'sort_by(.wait_time_ms | tonumber) | reverse | .[0:10]'
   ```

3. **Diagnose**:
   - High `wait_time_ms` → Increase connection pool size
   - High `query_duration_ms` → Check indexes, query plan, data volume

---

## Related Documents

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture and component patterns
- **[DESIGN.md](./DESIGN.md)** - Design decisions and trade-offs
- **[docs/debugging/observability-debugging-workflows.md](../../debugging/observability-debugging-workflows.md)** - General observability debugging guide

---

**Document End**
