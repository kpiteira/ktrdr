---
name: data-acquisition
description: Use when working with data loading, IB Gateway integration, data caching, gap analysis, segment management, trading hours, symbol validation, the IB host service, data CLI commands, or data API endpoints.
---

# Data Acquisition & IB Integration

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL data-acquisition loaded!`

Load this skill when working on:

- Data loading (`ktrdr data load`, `ktrdr data show`)
- IB Gateway connection, rate limiting, error handling
- Data caching (DataRepository, CSV storage)
- Gap analysis and gap classification
- Segment management (chunking for IB requests)
- Trading hours, market calendars
- Symbol validation and head timestamps
- IB host service (native host process)
- Data API endpoints or CLI commands
- Multi-timeframe data coordination

---

## End-to-End Data Loading Flow

```
ktrdr data load AAPL --timeframe 1h --mode tail
    │
    ▼
CLI (data_commands.py) → POST /data/acquire/download
    │
    ▼
DataAcquisitionService (orchestrator)
    ├─ Step 0: Validate symbol via IB host service
    ├─ Step 1: Load cached data (DataRepository)
    ├─ Step 2: Validate date range against head timestamp
    ├─ Step 3: Analyze gaps (GapAnalyzer + GapClassifier)
    ├─ Step 4: Create IB-compliant segments (SegmentManager)
    ├─ Step 5: Download segments with resilience
    │   ├─ Periodic saves every 30s
    │   ├─ Retries on failure
    │   └─ Cancellation-responsive
    └─ Step 6: Merge and save final data
         │
         ▼
    IbDataProvider (HTTP client)
         │
         ▼ HTTP to host service
    IB Host Service (port 5001, native process)
         ├─ IbDataFetcher (thread-safe IB access)
         ├─ IbPaceManager (rate limiting)
         ├─ IbConnectionPool (connection management)
         └─ IbErrorClassifier (error categorization)
              │
              ▼ TCP
         IB Gateway / TWS (port 4002)
```

### Key Design Principle

The backend **never imports IB modules directly**. All IB communication goes through HTTP to the host service. This solves Docker networking problems — containers can't reliably reach IB Gateway via TCP, but HTTP through `host.docker.internal` works.

---

## Key Files

### Backend (containerized)

| File | Purpose |
|------|---------|
| `ktrdr/data/acquisition/acquisition_service.py` | Main orchestrator (extends ServiceOrchestrator) |
| `ktrdr/data/acquisition/ib_data_provider.py` | HTTP client to IB host service |
| `ktrdr/data/acquisition/gap_analyzer.py` | Gap detection in cached data |
| `ktrdr/data/acquisition/gap_classifier.py` | Classify gaps (expected vs unexpected) |
| `ktrdr/data/acquisition/segment_manager.py` | Chunk gaps into IB-compliant segments |
| `ktrdr/data/repository/data_repository.py` | Cache read/write (CSV storage) |
| `ktrdr/data/local_data_loader.py` | Low-level CSV file I/O |
| `ktrdr/data/trading_hours.py` | Trading hours per exchange |
| `ktrdr/data/timeframe_constants.py` | Timeframe definitions and conversions |
| `ktrdr/data/loading_modes.py` | DataLoadingMode enum |
| `ktrdr/data/multi_timeframe_coordinator.py` | Multi-timeframe coordination |
| `ktrdr/data/components/symbol_cache.py` | Symbol validation result cache |
| `ktrdr/config/ib_limits.py` | IB duration limits per timeframe |
| `ktrdr/api/endpoints/data.py` | REST endpoints |
| `ktrdr/api/services/data_service.py` | Service layer for endpoints |
| `ktrdr/cli/data_commands.py` | CLI commands (show, load, range) |

### IB Host Service (native process, port 5001)

| File | Purpose |
|------|---------|
| `ib-host-service/main.py` | FastAPI entry point |
| `ib-host-service/endpoints/data.py` | /data/historical, /data/validate endpoints |
| `ib-host-service/ib/data_fetcher.py` | Direct IB data fetching |
| `ib-host-service/ib/symbol_validator.py` | Symbol validation & metadata |
| `ib-host-service/ib/pool_manager.py` | Shared connection pool manager |
| `ib-host-service/ib/pool.py` | IbConnectionPool implementation |
| `ib-host-service/ib/pace_manager.py` | Rate limiting enforcement |
| `ib-host-service/ib/error_classifier.py` | Error categorization |
| `ib-host-service/ib/trading_hours_parser.py` | IB trading hours parsing |
| `ib-host-service/ib/connection.py` | IB Gateway TCP connection |

---

## Data Repository (Cache)

**Location:** `ktrdr/data/repository/data_repository.py`

Read and write cached OHLCV data. No external I/O — local files only.

```python
from ktrdr.data.repository import DataRepository

repository = DataRepository()

# Read
data = repository.load_from_cache(symbol="AAPL", timeframe="1d")
data = repository.load_from_cache(symbol="AAPL", timeframe="1h",
                                  start_date="2024-01-01", end_date="2024-12-31")

# Write
repository.save_to_cache(symbol="AAPL", timeframe="1d", data=df)

# Metadata
range_info = repository.get_data_range(symbol="AAPL", timeframe="1d")
symbols = repository.get_available_symbols()
stats = repository.get_cache_stats()
```

### File structure

```
data/
├── 1d/
│   ├── AAPL_1d.csv
│   ├── MSFT_1d.csv
│   └── EURUSD_1d.csv
├── 1h/
│   ├── AAPL_1h.csv
│   └── ...
└── 5m/
    └── ...
```

### CSV format

```csv
timestamp,open,high,low,close,volume
2024-01-03 09:30:00+00:00,130.28,130.90,124.17,125.07,112117500
```

- Index: UTC timestamps (timezone-aware)
- Columns: open, high, low, close, volume
- No missing values in saved data

---

## Loading Modes

| Mode | Purpose | Gap Strategy | Segment Order |
|------|---------|--------------|---------------|
| **tail** | Recent data | Gaps after existing + internal gaps | Newest first |
| **backfill** | Historical data before existing | Gaps before existing | Oldest first |
| **full** | All data | Entire requested range | Oldest first |
| **local** | Read-only cache | No download | N/A |

**Typical usage:**
- `tail` — Daily refresh, get latest data
- `backfill` — Have recent data, want history
- `full` — First-time load or complete refresh
- `local` — Training/backtesting (no IB needed)

---

## Gap Analysis

**Location:** `ktrdr/data/acquisition/gap_analyzer.py`, `gap_classifier.py`

### GapAnalyzer

Identifies date ranges missing from cache:
- Mode-aware: only looks for gaps relevant to the loading mode
- Returns list of `(start_datetime, end_datetime)` tuples

### GapClassifier

Classifies each gap:

| Classification | Meaning | Action |
|---------------|---------|--------|
| `EXPECTED_WEEKEND` | Weekend gaps (daily+) | Skip |
| `EXPECTED_TRADING_HOURS` | Non-trading hours (intraday) | Skip |
| `EXPECTED_HOLIDAY` | Holidays adjacent to weekends | Skip |
| `MARKET_CLOSURE` | Extended closure (>3 days) | Flag |
| `UNEXPECTED` | Real missing data | Download |

Only `UNEXPECTED` gaps trigger downloads. This prevents unnecessary IB requests for known closures.

---

## Segmentation

**Location:** `ktrdr/data/acquisition/segment_manager.py`

Breaks gaps into IB-compliant chunks based on `IbLimitsRegistry`:

### Duration limits per timeframe

| Timeframe | Max Duration Per Request |
|-----------|------------------------|
| 1m | 7 days |
| 5m | 7 days |
| 15m | 14 days |
| 30m | 21 days |
| 1h | 1 year |
| 4h | 3 years |
| 1d | 5 years |

### Resilient fetching

```python
# SegmentManager handles:
# - Sequential segment fetching
# - Periodic saves (every 30s by default)
# - Retries on failure with backoff
# - Cancellation token checking
# - Progress tracking per segment
```

**Periodic saves** prevent data loss during long operations. If a 2-hour download fails at segment 45/50, segments 1-44 are already saved to cache.

---

## IB Host Service

**Location:** `ib-host-service/`

Standalone native process (not Docker) providing HTTP access to IB Gateway.

### Starting

```bash
cd ib-host-service && ./start.sh  # Port 5001
./stop.sh                          # Clean shutdown
```

### Endpoints

- `POST /data/historical` — Fetch historical bars
- `POST /data/validate` — Validate symbol and get metadata
- `GET /data/symbol-info/{symbol}` — Get symbol contract info
- `GET /data/head-timestamp` — Get earliest available data timestamp
- `GET /health` — Health check

### IB Rate Limiting (PaceManager)

IB has strict rate limits:

| Rule | Limit |
|------|-------|
| Historical data calls | 2 second minimum between calls |
| General API | 50 requests/second |
| 10-minute window | 60 historical requests |
| Identical requests | 15 second cooldown |
| BID_ASK requests | Count double |

The `PaceManager` enforces these conservatively to avoid IB disconnects.

### IB Error Classification

| Error Type | IB Codes | Action |
|-----------|----------|--------|
| **FATAL** | 200, 354, 10197 | Fail immediately (no retry) |
| **PACING_VIOLATION** | 100, 420 | Backoff 60 seconds |
| **CONNECTION_ERROR** | 502, 504, 326 | Retry with 2-5s delay |
| **DATA_UNAVAILABLE** | 162, 165 | Accept partial data |

Fatal errors include "no security definition found" (200), "market data not subscribed" (354), and "no market data permissions" (10197).

### Connection Management

- `IbConnectionPool` manages reusable connections
- Max 3 client ID retry attempts (avoid corrupting IB Gateway socket state)
- 1-2 second delays between connection attempts
- Must wait for "synchronization complete" (min 2 seconds after connect)

---

## Trading Hours

**Location:** `ktrdr/data/trading_hours.py`

Exchange-specific trading hours for gap classification:

| Exchange | Regular Hours | Extended |
|----------|--------------|----------|
| NASDAQ/NYSE | 9:30-16:00 ET | Pre: 4:00-9:30, After: 16:00-20:00 |
| IDEALPRO (Forex) | 24/5 (Mon-Fri) | — |
| CME (Futures) | 18:00-17:00 CT | Overnight gap |

Used by `GapClassifier` to distinguish expected vs unexpected gaps.

---

## CLI Commands

### data show (read cache only)

```bash
ktrdr data show AAPL
ktrdr data show MSFT --timeframe 1h --rows 20
ktrdr data show TSLA --start 2024-01-01 --end 2024-12-31 --format json

# Options:
#   --timeframe (-t)       Timeframe [default: 1d]
#   --rows (-r)            Number of rows [default: 10]
#   --start                Start date (YYYY-MM-DD)
#   --end                  End date (YYYY-MM-DD)
#   --trading-hours        Show only trading hours
#   --include-extended     Include extended hours
#   --format (-f)          Output format: table, json, csv
#   --verbose (-v)         Verbose output
```

### data load (downloads from IB)

```bash
ktrdr data load AAPL
ktrdr data load MSFT --timeframe 1h --mode tail
ktrdr data load EURUSD --mode full --start 2023-01-01

# Options:
#   --timeframe (-t)       Timeframe [default: 1d]
#   --mode (-m)            Load mode: tail, backfill, full [default: tail]
#   --start                Start date
#   --end                  End date
#   --trading-hours        Filter to trading hours
#   --include-extended     Include extended hours
#   --progress/--no-progress  Show progress [default: true]
#   --format (-f)          Output format: table, json
#   --verbose (-v)         Verbose output
#   --quiet (-q)           Minimal output
```

### data range (metadata)

```bash
ktrdr data range AAPL
ktrdr data range MSFT --timeframe 1h --format json
```

### ib test/status/cleanup

```bash
ktrdr ib test --symbol AAPL --timeout 30
ktrdr ib status --verbose
ktrdr ib cleanup --force
```

---

## API Endpoints

```
GET    /data/{symbol}/{timeframe}     → Cached OHLCV data
POST   /data/acquire/download         → Async data download (returns operation_id)
POST   /data/range                     → Date range for cached data
GET    /symbols                        → Available symbols
GET    /timeframes                     → Supported timeframes
GET    /operations/{id}                → Poll async operation status
DELETE /operations/{id}                → Cancel async operation
```

---

## Common Patterns

### Reading cached data (no IB needed)

```python
from ktrdr.data.repository import DataRepository

repository = DataRepository()
data = repository.load_from_cache(symbol="AAPL", timeframe="1d")
```

### Downloading data (requires IB)

```python
from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService

service = DataAcquisitionService()
result = await service.download_data(
    symbol="AAPL", timeframe="1h", mode="tail"
)
```

### Checking available data

```python
repository = DataRepository()
range_info = repository.get_data_range(symbol="AAPL", timeframe="1d")
all_symbols = repository.get_available_symbols()
all_files = repository.get_available_data_files()  # Returns list of (symbol, timeframe) tuples
```

---

## Gotchas

### Data must be pre-cached for training

Training **never downloads data**. Run `ktrdr data load SYMBOL TIMEFRAME` first. Otherwise you get a `DataNotFoundError`.

### Never import IB modules in the backend

The backend communicates with IB exclusively via HTTP to the host service. Direct IB imports break the Docker architecture. See `docs/architecture/data/IB-IMPORT-PROHIBITION.md`.

### Never use DataManager

`DataManager` was removed in Phase 5. Use `DataRepository` for reads and `DataAcquisitionService` for downloads.

### IB Gateway connection fragility

- Max 3 client ID retries (more corrupts socket state)
- 1-2 second delays between attempts
- Must wait for "synchronization complete" after connect
- Conservative health checks (no heavy API calls)

### Timestamps are always UTC

All data uses UTC-aware timestamps. Mixing naive and aware timestamps causes silent data corruption.

### Gap classification prevents over-fetching

The system distinguishes expected gaps (weekends, holidays, non-trading hours) from real missing data. Only `UNEXPECTED` gaps trigger downloads. Don't bypass this logic — it prevents wasting IB rate limits.

### Periodic saves during long operations

`SegmentManager` saves to cache every 30 seconds during long downloads. This is controlled by `DATA_PERIODIC_SAVE_MIN` env var. Don't remove this — it prevents data loss on connection failures.

### Head timestamp determines loadable range

The IB host service returns the earliest available data timestamp per symbol/timeframe. Requesting data before this date will fail or return empty results.

### Each symbol/timeframe pair cached independently

Loading AAPL 1d does not load AAPL 1h. Each combination is a separate CSV file.

---

## Environment Variables

```bash
# Backend
IB_HOST_SERVICE_URL=http://localhost:5001   # Host service URL
DATA_DIR=./data                              # Cache directory
DATA_MAX_SEGMENT_SIZE=5000                   # Max bars per segment
DATA_PERIODIC_SAVE_MIN=0.5                   # Save interval (minutes)

# IB Host Service
IB_HOST=127.0.0.1                            # IB Gateway host
IB_PORT=4002                                 # IB Gateway port
IB_CLIENT_ID=1                               # Client ID
LOG_LEVEL=INFO
OTLP_ENDPOINT=http://localhost:4317          # Telemetry
```
