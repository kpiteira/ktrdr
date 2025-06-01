# 🯩 Slice Execution Spec: IB Loader (Slice 1) - Implementation Status

## 🌟 Goal

Enable fetching OHLCV historical data from Interactive Brokers to fill *either* recent gaps (*tail fill*) or older periods (*backfill*), writing clean, chronologically ordered CSVs. Respect IB pacing rules. Triggerable via CLI, API, and (eventually) UI.

---

## 🯩 Background

Currently, all OHLCV data comes from static CSV files. This slice introduces programmatic fetching from Interactive Brokers, while treating local CSVs as a persistent cache to avoid redundant queries.

---

## 📦 Inputs

| Source         | Data                                                        |                                   |
| -------------- | ----------------------------------------------------------- | --------------------------------- |
| CLI / API / UI | `symbol`, `timeframe`, `mode: 'tail' | 'backfill'`, optional date range |
| CSV            | Last known bar (tail fill) OR earliest known bar (backfill) |                                   |
| Config         | IB credentials (host/port), allowed timeframes              |                                   |

**IB Credential Defaults:**

* `host`: defaults to `localhost` (Docker: `host.docker.internal`)
* `port`: defaults to 4001 (paper) or 7496 (live), overridable via config or CLI
* **Docker Port Forwarding**: Host port 4003 → IB Gateway port 4002 via `extra_hosts`

*Note: IB rate limits are defined by IB specifications and are not configurable.*

---

## ♻️ Logic & Flow

### 1. **Mode Decision**

* **CSV not found**:
  * If no local CSV exists for a given `symbol` + `timeframe`, treat all modes (`tail`, `backfill`) as a **full initialization**.
  * `start_date` will default to the widest allowed historical range (based on IB limits for the selected timeframe).
  * `end_date = now()` unless overridden by API input.

* **Tail** (✅ **IMPLEMENTED** - Automatic Gap Filling):
  * Get latest timestamp in local CSV.
  * `start_date = latest_bar + 1 bar`
  * `end_date = now()` or API-supplied override.

* **Backfill** (⚠️ **PARTIAL** - Manual workaround only):
  * Get earliest known timestamp in CSV.
  * `start_date = earliest_bar - N bars`, where `N` is based on IB's maximum allowed request size for the selected timeframe.
  * `end_date = earliest_bar - 1 bar`

### 2. **IB Fetch Constraints**

#### ✅ Official Historical Data Request Limits

| Bar Size | Maximum Duration per Request |
| -------- | ---------------------------- |
| 1 sec    | 30 minutes                   |
| 5 secs   | 2 hours                      |
| 15 secs  | 4 hours                      |
| 30 secs  | 8 hours                      |
| 1 min    | 1 day                        |
| 5 mins   | 1 week                       |
| 15 mins  | 2 weeks                      |
| 30 mins  | 1 month                      |
| 1 hour   | 1 month                      |
| 1 day    | 1 year                       |
| 1 week   | 2 years                      |
| 1 month  | 1 year                       |

#### 🚦 Pacing Limits (Per IB)

To avoid pacing violations, adhere to the following restrictions:

* **No more than 60 historical data requests within any 10-minute period.**
* **Avoid making identical historical data requests within 15 seconds.**
* **Do not make six or more historical data requests for the same Contract, Exchange, and Tick Type within two seconds.**
* **When requesting BID\_ASK historical data, each request is counted twice.**

Violating these limits may result in pacing violations, leading to delayed responses or disconnections.

#### ✅ Retry & Backoff Strategy (IMPLEMENTED)

* **Retry Attempts:** Maximum 3 retries per failed chunk
* **Backoff Policy:** Exponential backoff: [15, 30, 60, 120, 300, 600] seconds
* **Failure Logging:** All retries logged with error and wait time
* **Abort Condition:** If all retries fail, raise detailed exception and halt process
* **Timeouts:** Per-request timeout (120s) — cancel and retry on timeout
* **Progressive Chunking:** Split large gaps into IB-compliant requests respecting duration limits

### 3. **Post-Fetch Handling**

* Fetched data is added to the CSV, ensuring it is sorted chronologically and deduplicated.
* Sort chronologically, de-dupe.
* All fetches logged to application logs

---

## 🏗️ **ENHANCED ARCHITECTURE & INTELLIGENT GAP FILLING**

### **✅ CORRECTED Smart Data Orchestration Architecture**

#### **🎯 Data Loading Flow (PRODUCTION)**
```
API Request (/api/v1/data/load)
    ↓
DataService (API Adapter)
    ↓  
DataManager (SMART - Orchestrator)
    ├── Gap Analysis: Detect meaningful missing segments
    ├── Segment Planning: Split large ranges into IB-compliant chunks
    ├── For each gap:
    │   └── IbService.load_data() (DUMB - Pure IB Fetcher)
    │       └── IbDataLoader (Raw IB API calls)
    │           └── Progressive chunking if segment > IB limits
    └── Merge: Combine existing + fetched data chronologically
```

#### **🏗️ IB Infrastructure Flow (SEPARATE)**
```
API Request (/api/v1/ib/status|health|config|ranges)
    ↓
IbService (IB Infrastructure Only)
    └── IB Components (status, health, discovery, config)
```

### **🧠 DETAILED Component Responsibilities**

#### **📊 DataManager (SMART Orchestrator)**
**Primary Responsibilities**:
- **Gap Analysis**: Compare existing CSV data vs requested date range
- **Smart Filtering**: Ignore weekends, holidays, micro-gaps not worth fetching
- **Segment Planning**: Break large requests into missing pieces only
- **Mode Logic**: Handle tail/backfill/full modes with intelligent defaults
- **Date Range Determination**: Calculate optimal start/end dates
- **Local CSV Management**: Load, merge, save local data files
- **Failure Resilience**: Continue with other segments if some fail
- **Trading Calendar Awareness**: Understand market closure patterns

**Key Methods**:
- `load_data()` - Main entry point for all data loading
- `_analyze_gaps()` - Intelligent gap detection
- `_split_into_segments()` - IB-compliant chunking
- `_fetch_segments_with_resilience()` - Resilient multi-segment fetching

#### **🔌 IbService (DUMB IB Infrastructure)**
**Primary Responsibilities**:
- **Connection Management**: Status, health, cleanup operations
- **Configuration**: Get/update IB connection settings
- **Data Discovery**: Find what data ranges are available in IB
- **Raw Data Fetching**: Fetch exact date ranges when asked by DataManager

**Key Methods**:
- `get_status()` - IB connection status
- `get_health()` - IB health checks
- `get_config()` - IB configuration info
- `get_data_ranges()` - IB data discovery (binary search)
- `cleanup_connections()` - Force disconnect IB connections
- `load_data()` - **SIMPLIFIED**: Only fetch exact ranges from IB (no local logic)

**❌ IbService SHOULD NOT**:
- Analyze gaps or determine what data to fetch
- Handle CSV files or local data operations
- Make decisions about date ranges or modes
- Merge data sources

#### **🌐 DataService (API Adapter)**  
**Primary Responsibilities**:
- **API Interface**: Expose DataManager functionality to REST API
- **Request Validation**: Validate API requests before calling DataManager
- **Response Formatting**: Convert DataManager results to API responses
- **Error Handling**: Translate DataManager exceptions to API errors

#### **🔧 IbDataLoader (RAW IB API)**
**Primary Responsibilities**:
- **Raw IB Calls**: Direct ib_insync API interactions
- **Progressive Chunking**: Split large requests that exceed IB limits
- **Connection Handling**: Manage IB connections for data requests
- **Data Validation**: Basic OHLCV data quality checks

**Called By**: IbService.load_data() only (never directly by other components)

**Example Scenario**:
- **Request**: RBLX 1d from 2023-01-01 to 2025-05-30 (516 days)
- **Existing Data**: 2024-04-01 to 2025-05-01 with gap 2024-12-01 to 2024-12-10
- **Smart Analysis**: Identify 3 missing segments:
  1. `2023-01-01 → 2024-04-01` (456 days, needs progressive chunking)
  2. `2024-12-01 → 2024-12-10` (9 days, single request)  
  3. `2025-05-01 → 2025-05-30` (29 days, single request)
- **Efficient Execution**: Fetch only missing data, not entire 516-day range

### **✅ Connection Management Architecture**

```
Docker Container (ktrdr-backend)
├── Main FastAPI Thread
│   └── PersistentIbConnectionManager (client_id: 1-50)
│       └── IbConnectionSync (primary connection)
│
├── Background Gap Filler Thread  
│   └── IbContextManager 
│       └── Thread-specific IbConnectionSync (client_id: 200-299)
│
└── API Request Threads
    └── Share primary connection (thread-safe)
```

### **🔗 Port Model & Docker Integration**

```
Host Machine (127.0.0.1:4003)
    ↓ Port Forwarding
Docker Container (host.docker.internal:4003) 
    ↓ Internal Connection
IB Gateway Container (localhost:4002)
```

**Configuration:**
- `IB_HOST=host.docker.internal` (Docker networking)
- `IB_PORT=4003` (forwarded port)
- `IB_CLIENT_ID=1` (primary connection)

### **🧵 Threading Challenges & Solutions**

#### **❌ Problem: Event Loop Conflicts**
```python
# This fails in background threads:
asyncio.run(ib.connectAsync())  # "This event loop is already running"
```

#### **✅ Solution: Thread-Specific Connections**
```python
# Background threads get isolated connections:
thread_id = threading.current_thread().ident
unique_client_id = 200 + (thread_id % 100)  # Range: 200-299
temp_connection = IbConnectionSync(ConnectionConfig(client_id=unique_client_id))
```

#### **🔧 Connection Lifecycle Management**
- **Primary Connection**: Persistent, managed by connection manager
- **Background Connections**: Created per-request, auto-cleanup with `__del__()`
- **Event Loop Isolation**: Each thread creates its own event loop
- **Client ID Conflicts**: Avoided via range separation (1-50 vs 200-299)

---

## 🛡 **IMPLEMENTATION STATUS**

### **✅ COMPLETED Modules**

| Module | Status | Description |
|--------|--------|-------------|
| `IbConnectionManager` | ✅ **PRODUCTION** | Persistent connection with client ID rotation (1-50) |
| `IbConnectionSync` | ✅ **PRODUCTION** | Thread-safe synchronous connection with event loop isolation |
| `IbContextManager` | ✅ **PRODUCTION** | Thread-specific connections for background operations (200-299) |
| `IbDataFetcherSync` | ✅ **PRODUCTION** | Handles IB API calls with timeout and error handling |
| `GapFillerService` | ✅ **PRODUCTION** | Automatic gap detection and progressive filling |
| `api/endpoints/ib.py` | ✅ **PRODUCTION** | Status, health, config, ranges, cleanup, load endpoints |
| `IbDataLoader` | ✅ **PRODUCTION** | Unified IB data fetching with progressive loading |
| `CLI Tool` | ✅ **PRODUCTION** | `ktrdr ib-load` command with all modes and options |

### **🔄 ENHANCED Modules**

| Module | Status | Description |
|--------|--------|-------------|
| `DataManager` | ✅ **PRODUCTION** | Enhanced with intelligent gap analysis, segment orchestration, and failure resilience |

### **❌ MISSING Modules**

| Module | Status | Description |
|--------|--------|-------------|
| Frontend Load Controls | ❌ **DEPRIORITIZED** | UI controls for data loading |

### **⚠️ PARTIAL Implementation**

| Module | Status | Description |
|--------|--------|-------------|
| Symbol Discovery | ⚠️ **WORKAROUND** | Manual CSV creation required for new symbols |
| Explicit Backfill | ⚠️ **WORKAROUND** | Delete CSV → recreate → auto-fills with max history |

---

## 📤 API Implementation Status

### **✅ IB Infrastructure Endpoints (CORRECT)**

**Endpoint**: `GET /api/v1/ib/status`
- Returns IB connection status, metrics, health indicators
- ✅ **Correctly uses IbService**

**Endpoint**: `GET /api/v1/ib/health`  
- Performs health checks on IB connection and API functionality
- ✅ **Correctly uses IbService**

**Endpoint**: `GET /api/v1/ib/config`
- Returns current IB configuration settings
- ✅ **Correctly uses IbService**

**Endpoint**: `GET /api/v1/ib/ranges`
- Discovers earliest/latest available data for symbols using IB's reqHeadTimeStamp
- ✅ **Correctly uses IbService** (pure IB discovery, no data loading)

**Endpoint**: `POST /api/v1/ib/cleanup`
- Forcefully disconnects all IB connections for troubleshooting
- ✅ **Correctly uses IbService**

### **❌ MISPLACED Data Loading Endpoint (NEEDS FIXING)**

**Endpoint**: `POST /api/v1/ib/load` ❌ **WRONG LOCATION**
- Currently in IbService (incorrect)
- Should be `POST /api/v1/data/load` using DataService → DataManager

### **🎯 CORRECT Data Loading Endpoint (TO BE IMPLEMENTED)**

**Endpoint**: `POST /api/v1/data/load` ✅ **CORRECT ARCHITECTURE**
- Uses DataService → DataManager → (gap analysis) → IbService.load_data() (when needed)
- Supports all modes (tail, backfill, full) with intelligent processing
- Handles large date ranges with smart segmentation
- Returns detailed operation metrics

The **CORRECT** `/api/v1/data/load` endpoint will support:
```json
{
  "symbol": "MSFT",
  "timeframe": "1h",
  "mode": "tail",          // or "backfill" or "full"
  "start": "2023-01-01T00:00:00Z",  // optional override
  "end": "2024-01-01T00:00:00Z"      // optional override
}
```

**Validation Rules**:
* `symbol` and `timeframe` are required
* `mode` defaults to `tail` if missing
* `start` and `end` are optional but must match ISO 8601 format if provided
* `start` must be before `end`

**Response**:
```json
{
  "status": "success",
  "fetched_bars": 2432,
  "cached_before": true,
  "merged_file": "data/MSFT_1h.csv",
  "gaps_analyzed": 3,
  "segments_fetched": 2,
  "ib_requests_made": 2
}
```

**Enhanced Response Fields**:
- `gaps_analyzed` - Number of gaps identified by DataManager
- `segments_fetched` - Number of segments successfully fetched from IB
- `ib_requests_made` - Number of actual IB API calls made

---

## 🧪 Tests (Definition of Done)

| Test | Status | Implementation |
|------|--------|----------------|
| **Automatic Gap Filling** | ✅ **PASS** | Background service fills gaps every 5 minutes |
| **Progressive Chunking** | ✅ **PASS** | Large gaps split into IB-compliant requests |
| **Thread Safety** | ✅ **PASS** | Background gap filler uses isolated connections |
| **Pacing Compliance** | ✅ **PASS** | 2s delays, error detection, batch limits |
| **Data Quality** | ✅ **PASS** | Sorted, deduplicated, timezone-consistent CSVs |
| **Error Recovery** | ✅ **PASS** | Handles connection failures, retries, cleanup |
| **Connection Lifecycle** | ✅ **PASS** | Proper connect/disconnect with event loop cleanup |
| CLI Load | ❌ **MISSING** | `load_ib.py --symbol AAPL --tf 1h --mode tail` |
| Explicit Backfill | ❌ **MISSING** | API-driven backfill mode |
| New Symbol Loading | ⚠️ **WORKAROUND** | Requires manual CSV creation |

---

## 📋 **REMAINING IMPLEMENTATION**

### **✅ Priority 1: Core Infrastructure** (COMPLETED)
- ✅ Added `/api/v1/ib/load` endpoint with mode support  
- ✅ Implemented CLI tool `ktrdr ib-load` with all features
- ✅ Fixed date range logic and response parsing
- ✅ Established progressive loading foundation

### **🎯 Priority 2: Architecture Compliance** (CRITICAL - 2-3 hours)
- **Move `/api/v1/ib/load` to `/api/v1/data/load`** using DataService
- **Simplify IbService.load_data()** to pure IB fetcher (remove local logic)
- **Update GapFillerService** to use DataManager instead of IbDataLoader
- **Ensure IbService only called by DataManager** for data operations

### **🎯 Priority 3: Symbol Discovery** (2-3 hours)
- Enhance IB service to validate symbols against IB contracts
- Add auto-detection of instrument types (stock, forex, futures)
- Improve error messages for invalid symbols

### **🔧 Current Architecture Issues**

**IMPLEMENTED BUT NOT USED**: DataManager has complete intelligent gap analysis but the main API endpoints bypass it!

**Current Flow** ❌ **WRONG**:
```
/api/v1/ib/load → IbService.load_data() → IbDataLoader (bypasses DataManager!)
```

**Required Flow** ✅ **CORRECT**:
```
/api/v1/data/load → DataService → DataManager → IbService.load_data() → IbDataLoader
```

**Architecture Violations**:
- Main data loading API bypasses enhanced DataManager
- IbService has local CSV logic (should be in DataManager)
- GapFillerService uses IbDataLoader directly (should use DataManager)
- Enhanced gap analysis is unused in production

---

## 🚦 **CURRENT WORKAROUNDS**

### **📊 Loading New Symbols (e.g., EURUSD_1h)**
```bash
# Create minimal CSV to trigger automatic filling
echo "timestamp,open,high,low,close,volume" > data/EURUSD_1h.csv
# System detects empty CSV and auto-fills with maximum available history
```

### **⏮️ Extending Existing Data (e.g., AAPL backfill)**  
```bash
# Check current range first
curl "http://localhost:8000/api/v1/ib/ranges?symbols=AAPL&timeframes=1h"

# Delete CSV to trigger full reload
rm data/AAPL_1h.csv
echo "timestamp,open,high,low,close,volume" > data/AAPL_1h.csv
# System auto-fills with maximum available history (up to IB limits)
```

---

## 💡 **DESIGN DECISIONS MADE**

| Decision | Status | Rationale |
|----------|--------|-----------|
| **Synchronous vs Async IB API** | ✅ **SYNC CHOSEN** | Avoids event loop conflicts in multi-threaded environment |
| **Thread-specific connections** | ✅ **IMPLEMENTED** | Isolates background operations from main API threads |
| **Progressive chunking** | ✅ **IMPLEMENTED** | Handles large gaps while respecting IB duration limits |
| **Automatic gap filling** | ✅ **IMPLEMENTED** | Keeps data fresh without manual intervention |
| **Docker port forwarding** | ✅ **IMPLEMENTED** | Enables IB Gateway access from containerized backend |
| **Client ID range separation** | ✅ **IMPLEMENTED** | Prevents conflicts between main and background connections |
| **Frontend UI** | ✅ **DEPRIORITIZED** | Focus on API and CLI interfaces first |

---

## 🎉 **PRODUCTION READINESS** 

**Current Status: 85% Complete - Enhanced DataManager Implemented But Not Used**

### **✅ Ready for Production Use**
- ✅ **Automatic gap filling**: Keeps all data up-to-date
- ✅ **IB integration**: Stable, thread-safe, pacing-compliant
- ✅ **Data quality**: Clean CSVs with proper formatting  
- ✅ **Monitoring**: API endpoints for health and status
- ✅ **Error handling**: Comprehensive retry and recovery
- ✅ **Docker integration**: Full containerized deployment with port forwarding
- ✅ **CLI interface**: Complete `ktrdr ib-load` command with all modes
- ✅ **Progressive loading**: Handles large ranges when properly invoked

### **⚠️ ENHANCED BUT UNUSED Capabilities** 
- ⚠️ **Large date ranges**: Enhanced DataManager can handle >1 year but API bypasses it
- ⚠️ **Efficient backfilling**: Smart gap analysis implemented but not used in production
- ⚠️ **Trading calendar awareness**: Implemented but main API uses old "dumb" approach
- ⚠️ **Failure resilience**: Available in DataManager but unused by current API flow
- ⚠️ **Smart orchestration**: DataManager ready but API endpoints bypass it

### **📊 Current Capability**
- ✅ **Small ranges** (<1 year): Work via current API (using old approach)
- ✅ **New symbols**: Full initialization works
- ❌ **Large ranges** (>1 year): Still fail because API bypasses enhanced DataManager
- ❌ **Complex gap scenarios**: Not optimally handled due to architecture violations
- ❌ **Trading calendar aware**: Enhanced logic exists but unused by production API
- ❌ **Partial failure resilience**: Available but unused

**Critical Issue**: Enhanced DataManager is implemented but production API doesn't use it!

**Next Priority**: Fix architecture violations to enable enhanced capabilities in production.