# Design Document: Data Architecture Separation

## Document Information
- **Date**: 2025-01-27
- **Status**: PROPOSED
- **Supersedes**: Current monolithic DataManager architecture
- **Related**: None (foundational data architecture redesign)

---

## Executive Summary

This document describes a clean architectural separation of KTRDR's data management system, solving the fundamental confusion between **local cache operations** (fast, sync) and **external data acquisition** (slow, async, requires Operations tracking).

**The Core Problem**: DataManager conflates two distinct concerns:
1. Reading/writing local cache files (LocalDataLoader - fast, simple)
2. Downloading data from IB Gateway (slow, async, requires host service, Operations, progress tracking)

**The Result**: Clean separation into DataRepository (local cache CRUD) and DataAcquisitionService (external download orchestration), with IB-specific code moved to the host service where it belongs.

---

## Table of Contents

1. [The Design](#the-design)
2. [Architecture Overview](#architecture-overview)
3. [Core Principles](#core-principles)
4. [Component Design](#component-design)
5. [Data Flow Patterns](#data-flow-patterns)
6. [Design Rationale](#design-rationale)
7. [Trade-offs and Decisions](#trade-offs-and-decisions)
8. [Success Criteria](#success-criteria)

---

## 1. The Design

### The Big Picture

Imagine a simple world where:

1. **Local cache is simple**: DataRepository reads/writes local cache files. No async, no IB, no Operations service. Just fast file I/O with validation.

2. **External download is orchestrated**: DataAcquisitionService handles the complexity—checking cache, analyzing gaps, downloading from IB, tracking progress, managing operations. Uses DataRepository for cache operations.

3. **IB code lives in host service**: All IB Gateway connection code lives in `ib-host-service/ib/` where it can access IB directly. Backend never imports IB code, only calls HTTP endpoints.

4. **Same pattern everywhere**: Whether reading cache or downloading from IB, the pattern is consistent. One concern per component.

That's it. That's the whole design.

### The Key Innovation

**Composition over Confusion**: DataAcquisitionService *composes* DataRepository (has-a relationship), not inheritance.

```
Current (CONFUSED):
DataManager
  ├─ if mode=="local": use LocalDataLoader
  └─ else: use IbDataAdapter + orchestrator + progress + operations

Proposed (CLEAR):
DataRepository (standalone)
  └─ LocalDataLoader, DataQualityValidator
      (Fast, sync, file I/O only)

DataAcquisitionService (ServiceOrchestrator)
  ├─ DataRepository (composition!)
  ├─ IbDataProvider (HTTP-only)
  ├─ DataLoadingOrchestrator
  ├─ GapAnalyzer, SegmentManager
  └─ Progress, Operations tracking
```

### Why This Works

**For Local Cache Operations**:
- Use DataRepository directly
- Fast, synchronous file reads
- No dependencies on IB, Operations, or async infrastructure
- Simple validation and repair

**For External Data Acquisition**:
- Use DataAcquisitionService
- Checks cache via DataRepository.load_from_cache()
- Analyzes gaps
- Downloads from IB via IbDataProvider (HTTP)
- Saves via DataRepository.save_to_cache()
- Tracks progress via Operations

**The Beauty**: Clear responsibility boundaries. No mode-based conditionals. No IB imports in backend.

---

## 2. Architecture Overview

### Component Map

```
┌────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                            │
│                                                            │
│  CLI: ktrdr data show AAPL 1d                             │
│  CLI: ktrdr data download AAPL 1d --mode tail             │
│  API: GET /data/cache/{symbol}/{timeframe}                │
│  API: POST /data/acquire/download                         │
└────────────────────────────────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           │                         │
      Fast Path               Slow Path
      (Cache Only)         (External Download)
           │                         │
           ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│  DataRepository     │   │ DataAcquisitionSvc  │
│  (Standalone)       │◄──┤ (ServiceOrchestrator│
│                     │   │  + Operations)      │
│  • load_from_cache  │   │                     │
│  • save_to_cache    │   │  Composition! ──────┘
│  • get_data_range   │   │  Uses Repository for
│  • validate_data    │   │  cache operations
│  • repair_data      │   │
└─────────────────────┘   └─────────────────────┘
         │                         │
         │                         │ HTTP
         │                         ▼
         │              ┌─────────────────────┐
         │              │ IbDataProvider      │
         │              │ (HTTP-only)         │
         │              └─────────────────────┘
         │                         │
         │                         │ HTTP
         │                         ▼
         │              ┌─────────────────────┐
         │              │ ib-host-service     │
         │              │  Port 5001          │
         │              │                     │
         │              │  ib/                │
         │              │  ├─ connection.py   │
         │              │  ├─ data_fetcher.py │
         │              │  └─ ...             │
         │              └─────────────────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────┐
│      Local Cache Files                  │
│      data/{symbol}_{timeframe}.pkl      │
└─────────────────────────────────────────┘
```

### The Data Flow (Simplified)

**Cache Read (Fast Path)**:
```
Client: "Show me AAPL 1d data"
  ↓
DataRepository: "Let me load from cache"
  ↓ (file read)
Cache: "Here's the DataFrame"
  ↓
DataRepository: "Validate and return"
```

**External Download (Slow Path)**:
```
Client: "Download AAPL 1d from IB"
  ↓
DataAcquisitionService: "Let me orchestrate this"
  ├─ "What do we have?" → Repository.load_from_cache()
  ├─ "What gaps exist?" → GapAnalyzer.detect_gaps()
  ├─ "Download missing data" → IbDataProvider.fetch() → HTTP → Host Service → IB Gateway
  ├─ "Save new data" → Repository.save_to_cache()
  └─ "Track progress" → Operations Service
```

### The Unification

**Same LocalDataLoader everywhere**:
```
DataRepository
  └─ LocalDataLoader (file I/O)

DataAcquisitionService
  └─ DataRepository
      └─ LocalDataLoader (same code!)
```

When acquisition needs to check cache or save data, it delegates to Repository. One source of truth for file operations.

---

## 3. Core Principles

These principles guide every decision in this design:

### Principle 1: Single Responsibility
**Each component has ONE clear job.**

- DataRepository: Local cache CRUD
- DataAcquisitionService: External download orchestration
- IbDataProvider: HTTP client for IB host service
- LocalDataLoader: File I/O operations

No component knows about or depends on others' internal implementation.

### Principle 2: Composition Over Inheritance
**DataAcquisitionService composes DataRepository.**

Not inheritance (is-a), but composition (has-a). Acquisition needs cache operations, so it has a Repository instance. Clean dependency direction: Acquisition → Repository, never reverse.

### Principle 3: Location Awareness
**Code lives where it can execute.**

IB Gateway connection code requires direct TCP access. Docker can't do this. Therefore:
- IB code lives in `ib-host-service/ib/` (native macOS process)
- Backend code never imports IB code
- Backend calls host service via HTTP

### Principle 4: Shared Dependencies Are OK
**Don't duplicate, share wisely.**

Shared across backend and host service:
- `ktrdr/logging` - Logging utilities
- `ktrdr/config` - Configuration management
- `ktrdr/data/trading_hours.py` - Trading hours models
- `ktrdr/data/local_data_loader.py` - File I/O
- `ktrdr/async_infrastructure` - Operations, Progress, Cancellation

Not shared:
- `ib-host-service/ib/` - IB-specific code (host only)
- `ktrdr/data/repository/` - Repository (backend only)
- `ktrdr/data/acquisition/` - Acquisition (backend only)

### Principle 5: Backwards Compatibility When Possible
**Don't break working APIs.**

Keep existing endpoints functional:
- `GET /data/{symbol}/{timeframe}` - Use Repository (fast)
- `POST /data/load` - Deprecate with warning, route to new endpoint
- New: `POST /data/acquire/download` - Use AcquisitionService

### Principle 6: Explicit Over Implicit
**Make data flow visible.**

No hidden mode-based routing. No conditional IB imports. Explicit service selection:
- Want cache? Use DataRepository
- Want download? Use DataAcquisitionService

---

## 4. Component Design

### 4.1 DataRepository

**Purpose**: Fast, synchronous local cache management.

**Responsibilities**:
1. Load data from local cache files
2. Save data to local cache files
3. Query available data ranges
4. Validate data quality
5. Repair data issues
6. Merge DataFrames
7. Get cache statistics

**Key Characteristics**:
- **Pure sync**: No async/await, no event loops
- **No IB dependencies**: Never imports from ktrdr/ib or calls IB
- **No Operations tracking**: Just file I/O, no long-running operations
- **Fast**: Direct file reads/writes with minimal overhead
- **Standalone**: Can be used without AcquisitionService

**Location**: `ktrdr/data/repository/data_repository.py`

**Interface** (conceptual):
```python
class DataRepository:
    def __init__(self, data_dir: str):
        self.loader = LocalDataLoader(data_dir)
        self.validator = DataQualityValidator()

    # Cache operations (sync)
    def load_from_cache(
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> DataFrame

    def save_to_cache(
        symbol: str,
        timeframe: str,
        data: DataFrame
    ) -> None

    def get_data_range(
        symbol: str,
        timeframe: str
    ) -> dict  # {"start": datetime, "end": datetime, "rows": int}

    # Quality operations (sync)
    def validate_data(data: DataFrame) -> ValidationReport
    def repair_data(data: DataFrame) -> DataFrame
    def merge_data(existing: DataFrame, new: DataFrame) -> DataFrame

    # Introspection (sync)
    def get_summary(symbol: str, timeframe: str) -> dict
    def get_available_symbols() -> list[str]
    def get_available_timeframes(symbol: str) -> list[str]
```

**Design Decision**: Repository is pure domain logic. No knowledge of HTTP, no knowledge of Operations, no knowledge of IB.

---

### 4.2 DataAcquisitionService

**Purpose**: Orchestrated external data acquisition with progress tracking.

**Responsibilities**:
1. Check cache for existing data (via Repository)
2. Analyze gaps based on download mode
3. Download missing data from external provider (IB)
4. Save downloaded data (via Repository)
5. Track progress via Operations service
6. Support cancellation
7. Report completion with results

**Key Characteristics**:
- **Async by nature**: Inherits from ServiceOrchestrator
- **Composes Repository**: Uses DataRepository for cache operations
- **Operations integrated**: Uses Operations service for progress tracking
- **Provider-based**: Uses IbDataProvider (HTTP-only) for external data
- **Orchestrated**: Uses DataLoadingOrchestrator for intelligent gap handling

**Location**: `ktrdr/data/acquisition/acquisition_service.py`

**Architecture Role**: Coordinator between client requests, cache (Repository), external providers (IB), and Operations service.

**Interface** (conceptual):
```python
class DataAcquisitionService(ServiceOrchestrator):
    def __init__(self):
        super().__init__()  # ServiceOrchestrator features
        self.repository = DataRepository()  # Composition!
        self.provider = IbDataProvider()
        self.orchestrator = DataLoadingOrchestrator(...)
        self.gap_analyzer = GapAnalyzer()
        self.segment_manager = SegmentManager()

    # Main download operation (async)
    async def download_data(
        symbol: str,
        timeframe: str,
        mode: str = "tail",  # tail, backfill, full
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        progress_callback: Optional[Callable] = None,
        cancellation_token: Optional[CancellationToken] = None
    ) -> str:  # Returns operation_id
        """
        1. Check cache: repository.load_from_cache()
        2. Analyze gaps: gap_analyzer.detect_gaps()
        3. Create segments: segment_manager.create_segments()
        4. Download: provider.fetch_historical_data()
        5. Save: repository.save_to_cache()
        6. Track: operations_service.update_progress()
        """

    # Provider operations (async)
    async def validate_symbol(symbol: str) -> bool
    async def get_head_timestamp(symbol: str, timeframe: str) -> datetime
    async def get_provider_info() -> dict

    # Health (async)
    async def health_check() -> dict
```

**Design Decision**: AcquisitionService is the ONLY component that talks to external providers. Repository never does. Clean separation of concerns.

---

### 4.3 IbDataProvider

**Purpose**: HTTP client for IB host service operations.

**Responsibilities**:
1. Fetch historical data from IB (via host service HTTP)
2. Validate symbols with IB
3. Get head timestamps (earliest available data)
4. Health check IB Gateway connection
5. Translate IB errors to domain errors

**Key Characteristics**:
- **HTTP-only**: NEVER connects directly to IB Gateway
- **No direct IB imports**: No imports from `ktrdr/ib` or `ib-host-service/ib`
- **Async by nature**: All methods are async (HTTP calls)
- **Implements ExternalDataProvider**: Clean interface for future providers
- **Host service aware**: Knows about host service URL and endpoints

**Location**: `ktrdr/data/acquisition/ib_data_provider.py`

**Refactored From**: `ktrdr/data/ib_data_adapter.py` (remove direct connection mode, keep only HTTP mode)

**Interface** (conceptual):
```python
class IbDataProvider(ExternalDataProvider):
    def __init__(self, host_service_url: str = "http://localhost:5001"):
        self.host_service_url = host_service_url
        self.client = httpx.AsyncClient()
        # NO IB Gateway connection code
        # NO IbDataFetcher, IbSymbolValidator imports

    async def fetch_historical_data(
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> DataFrame:
        # HTTP POST to host service
        response = await self.client.post(
            f"{self.host_service_url}/data/historical",
            json={...}
        )
        return pd.read_json(response.json()["data"])

    async def validate_symbol(symbol: str) -> dict
    async def get_head_timestamp(symbol: str, timeframe: str) -> datetime
    async def health_check() -> dict
```

**Design Decision**: Provider is pure HTTP client. All IB Gateway interaction happens in host service. Backend never knows about IB Gateway.

---

### 4.4 Component Moves (What Goes Where)

**Repository Gets**:
- `local_data_loader.py` (referenced, not moved - stays in ktrdr/data/)
- `data_quality_validator.py` (moved from components/)

**Acquisition Gets**:
- `data_loading_orchestrator.py` (moved from ktrdr/data/)
- `gap_analyzer.py` (moved from components/)
- `segment_manager.py` (moved from components/)
- `gap_filler.py` (moved from ktrdr/ib/)
- `data_progress_renderer.py` (moved from data/async_infrastructure/)
- `external_data_interface.py` (moved from ktrdr/data/)
- `ib_data_provider.py` (refactored from ib_data_adapter.py, HTTP-only)

**Host Service Gets**:
- `ktrdr/ib/*.py` → `ib-host-service/ib/*.py` (8 files)
  - connection.py, pool.py, pool_manager.py
  - pace_manager.py, error_classifier.py
  - data_fetcher.py, symbol_validator.py
  - trading_hours_parser.py

**Stays Shared** (in ktrdr/):
- `ktrdr/logging/*`
- `ktrdr/config/*`
- `ktrdr/data/local_data_loader.py`
- `ktrdr/data/trading_hours.py`
- `ktrdr/data/timeframe_constants.py`
- `ktrdr/async_infrastructure/*` (general purpose)

**Gets Deleted** (after migration):
- `ktrdr/data/data_manager.py` (split into Repository + Acquisition)
- `ktrdr/data/ib_data_adapter.py` (refactored into ib_data_provider.py)
- `ktrdr/data/data_manager_builder.py` (builders no longer needed)
- `ktrdr/ib/` directory (empty after moving files)

---

## 5. Data Flow Patterns

### Pattern 1: Load from Cache (Fast Path)

**Scenario**: User wants to see cached data.

```
CLI Command:
  ktrdr data show AAPL 1d
    ↓
API Endpoint:
  GET /data/cache/AAPL/1d
    ↓
DataService:
  data_repository.load_from_cache("AAPL", "1d")
    ↓
DataRepository:
  1. Check file exists: data/AAPL_1d.pkl
  2. Load with LocalDataLoader
  3. Validate with DataQualityValidator
  4. Return DataFrame
    ↓
Response to client (fast: <100ms)
```

**Key Points**:
- No IB involved
- No Operations service
- No async overhead
- Pure file I/O

---

### Pattern 2: Download from IB (Slow Path)

**Scenario**: User wants to download data from IB.

```
CLI Command:
  ktrdr data download AAPL 1d --mode tail
    ↓
API Endpoint:
  POST /data/acquire/download
    {symbol: "AAPL", timeframe: "1d", mode: "tail"}
    ↓
DataAcquisitionService:
  1. Create operation in OperationsService
     operation_id = "op_data_20250127_abc123"

  2. Check cache via Repository
     existing_data = repository.load_from_cache("AAPL", "1d")

  3. Analyze gaps
     gaps = gap_analyzer.detect_gaps(existing_data, "1d")

  4. Create download segments
     segments = segment_manager.create_segments(gaps, mode="tail")

  5. Download missing data (async, with progress)
     for segment in segments:
       raw_data = await provider.fetch_historical_data(
         "AAPL", "1d", segment.start, segment.end
       )
       # Update progress
       operations_service.update_progress(operation_id, ...)

  6. Save to cache via Repository
     repository.save_to_cache("AAPL", "1d", combined_data)

  7. Mark operation complete
     operations_service.complete_operation(operation_id, results)
    ↓
Response to client:
  {"operation_id": "op_data_20250127_abc123", "status": "started"}
    ↓
Client polls for progress:
  GET /operations/op_data_20250127_abc123
```

**Key Points**:
- Repository used twice: check cache, save results
- IbDataProvider calls host service (HTTP)
- Operations service tracks progress
- Async, long-running (seconds to minutes)

---

### Pattern 3: IB Provider Flow (Backend → Host Service → IB Gateway)

**Scenario**: Backend needs historical data from IB.

```
Backend (Docker):
  DataAcquisitionService
    ↓
  IbDataProvider.fetch_historical_data(...)
    ↓ HTTP POST
  http://localhost:5001/data/historical
    ↓
Host Service (Native macOS):
  FastAPI Endpoint /data/historical
    ↓
  from ib import IbDataFetcher
    ↓
  IbDataFetcher.fetch(...)
    ↓ TCP
  IB Gateway (Port 4002)
    ↓
  Historical data returned
    ↓ HTTP response
  Backend receives DataFrame
```

**Import Rules**:
```
❌ Backend NEVER imports:
   from ktrdr.ib import IbDataFetcher  # NO!
   from ib_host_service.ib import ...  # NO!

✅ Backend ALWAYS uses:
   IbDataProvider.fetch_historical_data()  # HTTP

✅ Host Service imports:
   from ib import IbDataFetcher  # Local to host service
```

---

## 6. Design Rationale

### Why This Design?

The current DataManager architecture attempted to handle both local cache and external acquisition, which created three fundamental problems:

**Problem 1: Conflated Concerns**
DataManager has a "mode" parameter that drastically changes behavior:
- `mode="local"`: Simple file read
- `mode="tail"`: Complex IB download with gap analysis, orchestration, progress tracking

One class, two completely different responsibilities. This violates Single Responsibility Principle and makes testing/maintenance hard.

**Problem 2: IB Import Issues**
Backend (Docker) can't import IB code because IB Gateway connection requires direct TCP access. Current IbDataAdapter tries to support both direct and HTTP modes, leading to:
- Unused direct connection code in Docker
- Confusion about which mode is active
- Import dependencies on code that can't execute

**Problem 3: Async Complexity for Simple Operations**
Loading from cache is fast and synchronous. But because DataManager also handles IB downloads (async), even simple cache reads go through async infrastructure. Unnecessary complexity.

### Why Composition Over Inheritance?

**Acquisition composes Repository (not inherits)**:
- ✅ Clear dependency direction: Acquisition → Repository (never reverse)
- ✅ Repository can be used standalone (no Acquisition dependency)
- ✅ Easy to test: Mock Repository in Acquisition tests
- ✅ Easy to replace: Swap Repository implementation without touching Acquisition
- ❌ Inheritance would couple them tightly, making Repository unusable alone

### Why Move IB to Host Service?

**IB code needs direct TCP access to IB Gateway**:
- ✅ Host service runs natively (macOS), can connect to IB Gateway
- ✅ Backend runs in Docker, cannot connect (networking limitations)
- ✅ Centralizes IB code where it can actually execute
- ✅ Backend uses HTTP (simple, works anywhere)
- ❌ Keeping IB in backend means unused code and import issues

### Why Keep Shared Dependencies?

**Some code is genuinely shared**:
- ✅ Logging: Both backend and host service need logging
- ✅ Config: Both need configuration management
- ✅ Trading hours: Domain models used by both
- ✅ LocalDataLoader: File I/O used by both (Repository saves, host service might cache)

Duplication would be worse than sharing. The key is: share utilities and models, don't share domain logic.

### What Problem Does This Solve?

**Immediate**: Clarifies data architecture, makes code easier to understand and maintain

**Architectural**: Clean separation enables:
- Testing Repository without IB
- Testing Acquisition without file I/O (mock Repository)
- Adding new providers (AlphaVantage) without touching Repository
- Optimizing cache operations without affecting acquisition

**Maintainability**: Developers can reason about components independently. Want to improve gap analysis? Look in Acquisition. Want to optimize file I/O? Look in Repository.

---

## 7. Trade-offs and Decisions

### Trade-off 1: Duplication vs Coupling

**Decision**: Accept some code duplication to avoid tight coupling.

**Rationale**:
- Repository and Acquisition both validate data
- But validation logic differs (cache validation vs IB data validation)
- Extracting a "shared validator" would couple them
- Better to have two focused validators

**Impact**:
- Positive: Clean boundaries, easy to test
- Negative: Some validation logic duplicated
- Mitigation: Shared DataQualityValidator for common cases

---

### Trade-off 2: HTTP Overhead vs Clean Architecture

**Decision**: Accept HTTP overhead for IB calls from backend.

**Rationale**:
- Backend → HTTP → Host Service adds latency (~1-5ms)
- But enables clean separation (no IB imports in backend)
- IB calls are already slow (seconds), 5ms overhead is negligible (<1%)

**Impact**:
- Positive: Clean architecture, no import issues
- Negative: Slight latency increase
- Mitigation: Negligible in practice (IB calls dominate)

---

### Trade-off 3: Backwards Compatibility vs Clean API

**Decision**: Keep existing endpoints functional, add new ones.

**Rationale**:
- Breaking existing API would disrupt users
- Can gradually migrate users to new API
- Deprecation warnings guide migration

**Impact**:
- Positive: No user disruption, smooth migration
- Negative: Maintain both APIs temporarily
- Mitigation: Remove deprecated API in Phase 3

---

### Trade-off 4: Move Files vs Refactor in Place

**Decision**: Move files to new structure (no git history preservation).

**Rationale**:
- Git history is less important than clear architecture
- Moving files makes new structure obvious
- Can always git log with --follow if needed

**Impact**:
- Positive: Clear new structure
- Negative: Git history breaks for moved files
- Mitigation: Document file moves in commit messages

---

### Trade-off 5: Composition vs Inheritance

**Decision**: DataAcquisitionService composes DataRepository.

**Rationale**:
- Composition allows Repository to be used standalone
- Inheritance would create tight coupling
- "Has-a" is more flexible than "is-a"

**Impact**:
- Positive: Loose coupling, better testability
- Negative: More explicit delegation needed
- Mitigation: Minimal code overhead, worth the clarity

---

## 8. Success Criteria

### Functional Requirements

**FR1: Local Cache Operations Work Standalone**
- ✅ Can use DataRepository without DataAcquisitionService
- ✅ Load, save, validate, repair all work synchronously
- ✅ No IB dependencies, no Operations dependencies

**FR2: External Acquisition Works with Progress**
- ✅ Can download data from IB with progress tracking
- ✅ Operations service integration works
- ✅ Gap analysis and segmentation work correctly

**FR3: Backwards Compatibility Maintained**
- ✅ Existing API endpoints still work
- ✅ Existing CLI commands still work
- ✅ Deprecation warnings guide migration

**FR4: IB Code in Host Service**
- ✅ Host service can import and use IB code
- ✅ Backend never imports IB code
- ✅ HTTP communication works correctly

### Architectural Requirements

**AR1: Clean Separation**
- ✅ DataRepository has no IB dependencies
- ✅ DataRepository has no Operations dependencies
- ✅ DataAcquisitionService composes DataRepository
- ✅ IbDataProvider is HTTP-only (no direct IB connection)

**AR2: Import Rules Enforced**
- ✅ Backend never imports from `ktrdr/ib`
- ✅ Backend never imports from `ib-host-service/ib`
- ✅ Host service imports from `ib/` (local)
- ✅ Shared imports only (logging, config, models)

**AR3: Testability**
- ✅ Can test Repository without IB
- ✅ Can test Acquisition with mocked Repository
- ✅ Can test IbDataProvider with mocked HTTP
- ✅ Integration tests cover end-to-end flows

### Performance Requirements

**PR1: Cache Operations Performance**
- ✅ Repository.load_from_cache(): <100ms for typical datasets
- ✅ Repository.save_to_cache(): <200ms for typical datasets
- ✅ No performance regression vs current DataManager

**PR2: Acquisition Performance**
- ✅ Download operations track progress correctly
- ✅ Gap analysis completes in <5s for typical cases
- ✅ HTTP overhead to host service <5ms per call

### Operational Requirements

**OR1: Debuggability**
- ✅ Clear separation makes debugging easier (which component?)
- ✅ Logging shows component boundaries
- ✅ Error messages indicate component (Repository vs Acquisition)

**OR2: Maintainability**
- ✅ Can modify Repository without touching Acquisition
- ✅ Can modify Acquisition without touching Repository
- ✅ Can add new providers without touching Repository

**OR3: Extensibility**
- ✅ Can add AlphaVantage provider without refactoring
- ✅ Can add new cache backends without touching Acquisition
- ✅ Clear pattern for adding new data sources

---

## Next Steps

1. **Review and Approval**: Team review of this design document
2. **Architecture Document**: Detailed component interfaces and API contracts
3. **Implementation Plan**: Phased migration with tasks and acceptance criteria
4. **Prototype**: Proof-of-concept for Repository and Acquisition separation
5. **Migration**: Incremental migration from current architecture

---

## Appendix A: Comparison with Current Architecture

| Aspect | Current (DataManager) | Proposed (Repository + Acquisition) |
|--------|----------------------|-------------------------------------|
| **Concerns** | Mixed (cache + IB) | Separated (cache OR IB) |
| **Sync/Async** | Mixed in one class | Clear: Repo sync, Acquisition async |
| **IB Location** | ktrdr/ib (Docker) | ib-host-service/ib (Native) |
| **Backend IB Access** | Tried to import directly | HTTP-only (via IbDataProvider) |
| **Composition** | Monolithic | Acquisition composes Repository |
| **Testing** | Hard (many mocks) | Easy (test components separately) |
| **Code Lines** | ~1500 LOC (DataManager) | ~800 LOC (Repo) + ~700 LOC (Acq) |
| **Complexity** | High (one class, many modes) | Low (two classes, single responsibility) |

## Appendix B: Glossary

**DataRepository**: Component for local cache CRUD operations (sync)

**DataAcquisitionService**: Component for external data download orchestration (async)

**IbDataProvider**: HTTP client for IB host service operations

**Composition**: Has-a relationship (Acquisition has a Repository)

**ServiceOrchestrator**: Base class for async operations with progress tracking

**Operations Service**: System for tracking long-running async operations

**Host Service**: Standalone service running natively (not in Docker) for IB access

**Gap Analysis**: Process of detecting missing data in cache

**Segmentation**: Process of dividing data requests into manageable chunks

---

**Document Version**: 1.0
**Last Updated**: 2025-01-27
**Next Review**: After architecture document completion
