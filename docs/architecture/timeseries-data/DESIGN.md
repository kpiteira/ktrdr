# TimescaleDB Market Data Storage - Design Document

**Version**: 2.0
**Status**: Design Phase
**Date**: 2025-01-15

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Goals](#design-goals)
3. [Storage Model Design](#storage-model-design)
4. [Backend Abstraction Design](#backend-abstraction-design)
5. [Migration Strategy Design](#migration-strategy-design)
6. [Query Design](#query-design)
7. [Trade-offs & Rationale](#trade-offs--rationale)

---

## Executive Summary

This design migrates KTRDR's market data from CSV files to TimescaleDB while preserving the existing DataRepository interface. The core design uses a minimal schema (7 columns: instrument, timestamp, OHLCV) with hypertable partitioning for efficient time-range queries. A backend abstraction layer enables dual-mode operation during migration, allowing CSV and database to coexist safely.

### Key Design Elements

- **Minimal Schema**: Store only essential data (instrument, ts, OHLCV) - no metadata bloat
- **Single Table**: All instruments in one `price_data` hypertable - no per-symbol tables
- **Base Granularity Only**: Store 5-minute bars; pandas resamples for other timeframes
- **Backend Abstraction**: Repository delegates to pluggable storage backends
- **Dual-Mode Migration**: CSV and DB coexist during transition with config-driven routing

---

## Design Goals

### Functional Goals

✅ **Efficient Range Queries**: Load full date ranges quickly (<500ms for 1 year of 5m bars)
✅ **Zero Data Loss**: All historical data migrates intact with validation
✅ **Interface Preservation**: Existing DataRepository API unchanged
✅ **Multi-Symbol Support**: Store all instruments in single table

### Non-Functional Goals

✅ **Schema Simplicity**: Minimal columns, no unused metadata
✅ **Query Optimization**: Optimize for full-range loads (training/backtesting access pattern)
✅ **Migration Safety**: Rollback capability via config change
✅ **Consistency**: Adopt feature_id pattern from strategies

---

## Storage Model Design

### Schema Design

The storage model uses a minimal schema focused on essential market data only:

```sql
CREATE TABLE price_data (
    instrument TEXT NOT NULL,      -- Symbol identifier (e.g., 'AAPL', 'EURUSD')
    ts TIMESTAMPTZ NOT NULL,       -- Bar timestamp (UTC)
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (instrument, ts)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('price_data', 'ts', chunk_time_interval => INTERVAL '7 days');
```

**Design Rationale**:
- **7 columns total**: Only essential fields (instrument, time, OHLCV)
- **No metadata**: No `source`, `created_at` - keeps rows small and queries fast
- **Composite PK**: (instrument, ts) enforces uniqueness and enables efficient queries

### Hypertable Partitioning

TimescaleDB automatically partitions data into 7-day chunks:

```
price_data
├─ Chunk 2024-01-01 to 2024-01-07
├─ Chunk 2024-01-08 to 2024-01-14
├─ Chunk 2024-01-15 to 2024-01-21
└─ ... (52 chunks per year)
```

**Query Optimization**:
When querying `WHERE instrument='AAPL' AND ts >= '2024-01-01' AND ts < '2024-12-31'`:
1. Constraint exclusion: Only scan 2024 chunks (~52 chunks)
2. Index seek: Use (instrument, ts) index within each chunk
3. Sequential read: Return matching rows

### Timeframe Handling Design

The system stores ONLY 5-minute bars in the database. Other timeframes are computed on-demand:

```
Storage Layer (Database):
└─ 5-minute bars only

Application Layer (pandas):
└─ Resample to 1h, 1d, 1w as needed
```

**Why this design**:
- Markets don't align with clock hours (US stocks open 9:30 AM, not 9:00 AM)
- Training loads ALL data then resamples → Pre-computed aggregates unused
- pandas resampling respects market hours correctly

### Indicator Caching Design

Computed indicators are cached separately with per-timeframe storage:

```sql
CREATE TABLE indicators (
    instrument TEXT NOT NULL,
    timeframe TEXT NOT NULL,       -- Critical: RSI@5m ≠ RSI@1h
    feature_id TEXT NOT NULL,      -- e.g., 'rsi_14', 'macd_12_26_9'
    ts TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (instrument, timeframe, feature_id, ts)
);
```

**Design Rationale**:
- `feature_id` matches strategy config pattern (consistency)
- `timeframe` is part of PK because indicators don't aggregate (RSI@5m computed from 5m bars ≠ RSI@1h computed from 1h bars)

---

## Backend Abstraction Design

The design uses a simple backend abstraction layer:

```
DataRepository (Interface Layer)
    │
    └─> TimescaleDBBackend (always)
```

### Backend Interface

```python
class DataBackend:
    def load(self, symbol, timeframe, start_date, end_date) -> pd.DataFrame
    def save(self, symbol, timeframe, data: pd.DataFrame) -> None
    def list_symbols(self, timeframe) -> list[str]
```

### DataRepository Implementation

```python
class DataRepository:
    def __init__(self, connection_string):
        self.backend = TimescaleDBBackend(connection_string)

    def load(self, symbol, timeframe, start_date, end_date):
        return self.backend.load(symbol, timeframe, start_date, end_date)

    def save(self, symbol, timeframe, data):
        self.backend.save(symbol, timeframe, data)
```

**Design Benefits**:
- Simple, direct path to database
- No mode switching complexity
- CSV import available as operational tool (not for reads)

---

## Cutover Strategy Design

Simple one-time cutover from CSV to DB:

```
Step 1: Initial CSV Import
└─ Import all historical CSV data → DB (one-time)

Step 2: Cutover
├─ Switch DataRepository to use TimescaleDB backend
└─ Application now reads/writes DB only

Step 3: Ongoing Operations
├─ Normal operations: Read/write DB directly
└─ CSV Import tool: Available for adding new data from CSV files
```

**No Dual-Mode**: Clean cutover, no complexity

### Cutover Process

```python
# Before cutover: DataRepository uses CSV (old code)
repository = DataRepository(data_dir="./data")  # CSV-based

# Run CSV import (one-time)
csv_import_service.import_all()  # CSV → DB

# After cutover: DataRepository uses DB (new code)
repository = DataRepository(connection_string=DATABASE_URL)  # DB-based
```

### CSV Import Design (Idempotent Operation)

The import operation can run multiple times safely:

```python
def import_csv_to_db(symbol, timeframe):
    """
    Import CSV data into database (idempotent).

    Behavior:
    - Existing data (same timestamp): Skip (or warn if values differ)
    - New data: Insert into DB
    - Can run multiple times safely
    """
    csv_data = csv_backend.load(symbol, timeframe)

    for timestamp, row in csv_data.iterrows():
        existing = db.query(instrument=symbol, ts=timestamp)

        if existing:
            if not rows_equal(existing, row):
                logger.warning(f"Data mismatch at {timestamp}: CSV differs from DB")
            # Skip existing data
        else:
            db.insert(symbol, timestamp, row)  # Insert new data
```

**Use Cases**:
- Initial migration: Import all historical CSV data
- Ongoing imports: User downloads new data to CSV, then imports to DB
- Gap filling: Import specific date ranges when DB missing data

---

## Query Design

### Primary Query Pattern

Training and backtesting load full date ranges:

```python
# Application code
data = repository.load("AAPL", "5m", start="2024-01-01", end="2024-12-31")

# SQL executed
SELECT ts, open, high, low, close, volume
FROM price_data
WHERE instrument = 'AAPL'
  AND ts >= '2024-01-01'
  AND ts < '2025-01-01'
ORDER BY ts;

# Result: 105,120 rows in <500ms
```

### Index Strategy

Single index design: **Primary key (instrument, ts) only**

```sql
PRIMARY KEY (instrument, ts)
```

**Why sufficient**:
- All queries filter by `instrument` first, then `ts` range
- PK index is clustered (data sorted by instrument, ts)
- No cross-symbol queries (no need for ts-only index)
- No queries by instrument alone (no need for instrument-only index)

### Performance Targets

- Single symbol, 1 year, 5m bars: **<500ms** (vs CSV ~2s)
- Single symbol, 5 years, 5m bars: **<2s** (training typical)
- Multi-symbol (10), 1 year: **<5s** (parallel chunk scans)

---

## Trade-offs & Rationale

### Trade-off 1: No Continuous Aggregates

**Design Choice**: Store 5m only, compute other timeframes in pandas

**Sacrificed**:
- Can't query hourly/daily bars directly from DB
- Must resample in application layer

**Gained**:
- Market-aware resampling (respects 9:30 AM open, not 9:00 AM bucket)
- Simpler schema (1 table vs 3 views)
- No aggregate refresh overhead

**Rationale**: Access pattern is "load all 5m, then resample", not "query hourly bars". Aggregates solve a problem we don't have.

---

### Trade-off 2: No Compression

**Design Choice**: Store uncompressed data

**Sacrificed**:
- Use 10x more storage (~50 GB vs 5 GB)

**Gained**:
- Faster queries (no decompression overhead)
- Predictable performance

**Rationale**: Training loads 3-5 years of history (not just recent data). Decompression overhead on EVERY query outweighs storage cost ($5/month).

---

### Trade-off 3: Minimal Schema

**Design Choice**: 7 columns only (instrument, ts, OHLCV)

**Sacrificed**:
- Can't track data source (IB vs CSV)
- Can't track insert timestamp

**Gained**:
- Smaller rows (56 bytes vs 70 bytes)
- Faster queries (less data to scan)
- Simpler schema

**Rationale**: Metadata fields add bloat but provide no query value. Keep schema minimal.

---

### Trade-off 4: feature_id Standardization

**Design Choice**: Use feature_id (e.g., "rsi_14") instead of indicator_name + params

**Sacrificed**:
- Can't query "all RSI regardless of period"

**Gained**:
- Consistent with strategy config (one naming scheme)
- Simpler queries (TEXT equality vs JSONB containment)
- Faster lookups

**Rationale**: Consistency across codebase > query flexibility we don't use.

---

### Trade-off 5: Comprehensive Observability

**Design Choice**: Use OpenTelemetry spans for all database and import operations

**Sacrificed**:
- Small overhead per operation (<1ms per span)
- Additional dependencies (OpenTelemetry SDK)

**Gained**:
- Complete visibility into database performance
- Ability to diagnose slow imports without manual instrumentation
- Track data validation issues (CSV vs DB mismatches) in real-time
- Performance regression detection (compare import durations over time)

**Rationale**: Migration is a critical operation. Observability enables first-response diagnosis when users report issues. Overhead is negligible compared to database operation time (50ms query + 0.5ms span = 1% overhead).

**Instrumentation Examples**:

```python
# DataRepository operations
@trace_service_method("data.repository.load")
async def load(self, symbol, timeframe, start_date, end_date):
    # Automatically captures: symbol, timeframe, dates, duration, rows loaded

# TimescaleDB backend operations
with create_service_span("timescaledb.query") as span:
    # Captures: query duration, rows returned, connection pool status

# CSV import operations
@trace_service_method("csv_import.import_symbol")
async def import_symbol(self, symbol, timeframe):
    # Captures: rows imported, rows skipped, warnings, duration
```

**Debugging Benefits**:

Query Jaeger to identify bottlenecks:
- "Which symbol took longest to import?" → Query `csv_import.import_symbol` spans, sort by duration
- "Why is query slow?" → Check `timescaledb.query` span attributes (connection pool wait, row count)
- "Are there data mismatches?" → Count `csv_import.warnings` attributes

---

## Summary

This design provides:

✅ **Efficient storage**: Minimal schema, hypertable partitioning, optimized for range queries
✅ **Simple cutover**: One-time CSV import, clean switch to DB
✅ **Simple query model**: Single table, single index, pandas resampling
✅ **Interface stability**: DataRepository API unchanged
✅ **Market-aware**: Respect trading hours via pandas resampling
✅ **Operational flexibility**: CSV import tool for adding new data as needed

**Related Documents**:
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Component architecture and patterns
- [OBSERVABILITY.md](./OBSERVABILITY.md) - OpenTelemetry instrumentation reference
- IMPLEMENTATION_PLAN.md - Migration phases (to be created)

---

**Document End**
