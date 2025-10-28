# Architecture: Data Management Separation

## Document Information

**Date**: 2025-01-27
**Status**: DRAFT - Ready for Review
**Version**: 1.0
**Related Documents**:
- [Design Document](./01-design-data-separation.md) - High-level design principles and patterns
- [Implementation Plan](./03-implementation-plan-data-separation.md) - Step-by-step implementation guide

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architectural Principles](#2-architectural-principles)
3. [System Architecture](#3-system-architecture)
4. [Component Architecture](#4-component-architecture)
5. [Data Flow Patterns](#5-data-flow-patterns)
6. [API Contracts](#6-api-contracts)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Quality Attributes](#8-quality-attributes)
9. [Migration Strategy](#9-migration-strategy)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the detailed architecture for separating KTRDR's data management system into two focused components: **DataRepository** (local cache) and **DataAcquisitionService** (external download), translating the design principles from [01-design-data-separation.md](./01-design-data-separation.md) into concrete specifications.

### 1.2 The Problem

The current DataManager conflates two distinct concerns:
1. **Local cache operations**: Fast, sync file I/O (LocalDataLoader)
2. **External data acquisition**: Slow, async IB downloads with Operations tracking

This conflation causes:
- Mode-based conditional complexity
- Unused IB code in Docker backend
- Difficulty testing components independently
- Unclear responsibility boundaries

See [Design Document §1](./01-design-data-separation.md#1-the-design) for detailed problem statement.

### 1.3 The Solution

**Clean Separation with Composition**:
- **DataRepository**: Standalone, sync, local cache CRUD
- **DataAcquisitionService**: ServiceOrchestrator, async, composes Repository
- **IB Code**: Moved to `ib-host-service/ib/` where it can execute
- **Backend**: HTTP-only access to IB via IbDataProvider

### 1.4 Key Architectural Decisions

| Decision | Rationale | Reference |
|----------|-----------|-----------|
| **Composition over inheritance** | Acquisition composes Repository for loose coupling | [Design §4.2](./01-design-data-separation.md#42-dataacquisitionservice) |
| **IB code in host service** | Docker can't access IB Gateway, host service can | [Design §3 Principle 3](./01-design-data-separation.md#principle-3-location-awareness) |
| **Repository is sync-only** | Cache operations don't need async complexity | [Design §4.1](./01-design-data-separation.md#41-datarepository) |
| **HTTP-only IB access** | Backend never imports IB code | [Design §4.3](./01-design-data-separation.md#43-ibdataprovider) |
| **Shared dependencies stay shared** | Don't duplicate logging, config, models | [Design §3 Principle 4](./01-design-data-separation.md#principle-4-shared-dependencies-are-ok) |

---

## 2. Architectural Principles

These principles (from [Design Document §3](./01-design-data-separation.md#3-core-principles)) govern all architectural decisions:

### 2.1 Single Responsibility
**Each component has ONE clear job.**

- DataRepository: Local cache CRUD (no IB, no Operations)
- DataAcquisitionService: External download orchestration (uses Repository for cache)
- IbDataProvider: HTTP client for IB host service (no direct IB connection)

```
DataRepository.load_from_cache() ✅ (cache operation)
DataRepository.fetch_from_ib() ❌ (not Repository's job)

DataAcquisitionService.download_data() ✅ (acquisition orchestration)
DataAcquisitionService.load_from_cache() ❌ (use Repository instead)
```

### 2.2 Composition Over Inheritance
**DataAcquisitionService composes DataRepository.**

```python
# Composition (has-a) ✅
class DataAcquisitionService(ServiceOrchestrator):
    def __init__(self):
        self.repository = DataRepository()  # Composition

    async def download_data(...):
        # Check cache
        existing = self.repository.load_from_cache(...)
        # Download from IB
        # Save via repository
        self.repository.save_to_cache(...)

# Inheritance (is-a) ❌ - Would couple them
class DataAcquisitionService(DataRepository):
    # Tight coupling, Repository can't be used alone
```

### 2.3 Location Awareness
**Code lives where it can execute.**

```
IB Gateway (Port 4002)
     ↓ TCP (only accessible from native macOS)
ib-host-service/ib/ ✅
     ↓ HTTP
Backend (Docker) ✅
     ↓ ❌ Cannot access IB Gateway directly
ktrdr/ib/ ❌ (wrong location)
```

### 2.4 Shared Dependencies Are OK
**Share utilities and models, not domain logic.**

```
Shared ✅:
- ktrdr/logging (utilities)
- ktrdr/config (configuration)
- ktrdr/data/trading_hours.py (domain models)
- ktrdr/data/local_data_loader.py (file I/O utility)

Not Shared ❌:
- DataRepository (backend domain logic)
- ktrdr/ib → ib-host-service/ib (location-specific)
```

### 2.5 Backwards Compatibility When Possible
**Keep existing APIs working.**

```
Keep (compatible):
GET /data/{symbol}/{timeframe} → DataRepository
GET /data/info → DataRepository

Deprecate (warn, then remove):
POST /data/load → Route to /data/acquire/download

New (explicit):
POST /data/acquire/download → DataAcquisitionService
```

### 2.6 Explicit Over Implicit
**Make service selection visible.**

```
# Current (implicit, mode-based) ❌
data_manager.load_data(symbol, "1d", mode="local")   # Which code path?
data_manager.load_data(symbol, "1d", mode="tail")    # Different code!

# New (explicit) ✅
data_repository.load_from_cache(symbol, "1d")        # Clear: cache
data_acquisition.download_data(symbol, "1d", "tail") # Clear: IB download
```

---

## 3. System Architecture

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│ CLIENT LAYER                                        │
│  - CLI (ktrdr data show, ktrdr data download)      │
│  - API Clients (Web UI, Scripts)                   │
│  - MCP Client                                       │
└───────────────────┬─────────────────────────────────┘
                    │
       ┌────────────┴────────────┐
       │                         │
  Fast Path                 Slow Path
  (Cache)                   (Download)
       │                         │
       ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ API LAYER        │    │ API LAYER        │
│  GET /data/...   │    │ POST             │
│                  │    │ /data/acquire/   │
└──────────────────┘    └──────────────────┘
       │                         │
       ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ DataRepository   │◄───┤DataAcquisitionSvc│
│ (Sync)           │    │ (Async + Ops)    │
│                  │    │                  │
│ LocalDataLoader  │    │ Composition! ────┘
│ DataValidator    │    │ Uses Repository
└──────────────────┘    │ for cache ops
       │                │
       │                ├─ IbDataProvider ───┐
       │                ├─ GapAnalyzer       │
       │                ├─ SegmentManager    │
       │                └─ Orchestrator      │
       │                                     │
       ▼                                     ▼ HTTP
┌──────────────────────────────────────────────────────┐
│ Local Cache Files                                    │
│  data/{symbol}_{timeframe}.pkl                       │
└──────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                   ┌────────────────────┐
                                   │ ib-host-service    │
                                   │  Port 5001         │
                                   │                    │
                                   │  ib/               │
                                   │  ├─ connection.py  │
                                   │  ├─ data_fetcher.py│
                                   │  └─ ...            │
                                   │       ↓ TCP        │
                                   │  IB Gateway (4002) │
                                   └────────────────────┘
```

### 3.2 Component Relationships

```
DataAcquisitionService
  ├─ composes → DataRepository (cache operations)
  ├─ uses → IbDataProvider (HTTP client)
  ├─ uses → DataLoadingOrchestrator (gap handling)
  ├─ uses → GapAnalyzer (gap detection)
  ├─ uses → SegmentManager (segmentation)
  └─ inherits → ServiceOrchestrator (operations tracking)

IbDataProvider
  ├─ calls → ib-host-service (HTTP)
  └─ implements → ExternalDataProvider (interface)

DataRepository
  ├─ uses → LocalDataLoader (file I/O)
  ├─ uses → DataQualityValidator (validation)
  └─ standalone (no external dependencies)

ib-host-service
  └─ imports → ib/* (local IB code)
```

### 3.3 Dependency Direction

```
Client Layer
    ↓
API Layer
    ↓
Service Layer (Repository OR Acquisition)
    ↓
Infrastructure (LocalDataLoader, IbDataProvider)
    ↓
External Systems (Files, IB Gateway)
```

**Key Rule**: Dependencies flow DOWN only. No circular dependencies.

---

## 4. Component Architecture

### 4.1 DataRepository

**Purpose**: Fast, synchronous local cache management.

**Architecture Pattern**: Simple domain service (no inheritance, just composition).

**Location**: `ktrdr/data/repository/data_repository.py`

#### Class Design

```python
class DataRepository:
    """
    Local cache repository for market data.

    Fast, synchronous operations only.
    No IB dependencies, no Operations tracking.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize with data directory."""
        self.data_dir = data_dir or os.getenv("DATA_DIR", "./data")
        self.loader = LocalDataLoader(self.data_dir)
        self.validator = DataQualityValidator()
```

#### Public Interface

```python
# Cache operations (sync)
def load_from_cache(
    self,
    symbol: str,
    timeframe: str,
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
) -> pd.DataFrame:
    """
    Load data from local cache.

    Fast, synchronous file read.
    Validates and returns DataFrame.

    Raises:
        DataNotFoundError: If cache file doesn't exist
        DataCorruptionError: If data validation fails
    """

def save_to_cache(
    self,
    symbol: str,
    timeframe: str,
    data: pd.DataFrame,
) -> None:
    """
    Save data to local cache.

    Validates data before saving.
    Creates parent directories if needed.

    Raises:
        DataValidationError: If data fails validation
    """

def get_data_range(
    self,
    symbol: str,
    timeframe: str,
) -> dict:
    """
    Get date range for cached data.

    Returns:
        {
            "start_date": datetime,
            "end_date": datetime,
            "rows": int,
            "exists": bool
        }
    """

# Quality operations (sync)
def validate_data(
    self,
    data: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> ValidationReport:
    """Validate data quality."""

def repair_data(
    self,
    data: pd.DataFrame,
    timeframe: str,
    method: str = "auto",
) -> pd.DataFrame:
    """Repair data issues."""

def merge_data(
    self,
    existing: pd.DataFrame,
    new: pd.DataFrame,
) -> pd.DataFrame:
    """Merge existing and new data, removing duplicates."""

# Introspection (sync)
def get_summary(
    self,
    symbol: str,
    timeframe: str,
) -> dict:
    """Get summary statistics for cached data."""

def get_available_symbols(self) -> list[str]:
    """List all symbols with cached data."""

def get_available_timeframes(self, symbol: str) -> list[str]:
    """List available timeframes for symbol."""
```

#### State Model

```python
# DataRepository has minimal state
{
    "data_dir": str,          # Cache directory path
    "loader": LocalDataLoader,  # File I/O component
    "validator": DataQualityValidator,  # Validation component
}
```

#### Dependencies

```python
# Internal dependencies
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.components.data_quality_validator import DataQualityValidator

# NO dependencies on:
# - ktrdr.ib (IB code)
# - ktrdr.api.services.operations_service (Operations)
# - ktrdr.async_infrastructure (async/await)
```

---

### 4.2 DataAcquisitionService

**Purpose**: Orchestrated external data acquisition with progress tracking.

**Architecture Pattern**: ServiceOrchestrator subclass with composition.

**Location**: `ktrdr/data/acquisition/acquisition_service.py`

#### Class Design

```python
class DataAcquisitionService(ServiceOrchestrator):
    """
    External data acquisition orchestrator.

    Async operations with Operations service integration.
    Composes DataRepository for cache operations.
    """

    def __init__(self):
        """Initialize with dependencies."""
        super().__init__()  # ServiceOrchestrator features

        # Composition: has-a Repository
        self.repository = DataRepository()

        # External provider (IB)
        self.provider = IbDataProvider()

        # Gap analysis components
        self.gap_analyzer = GapAnalyzer()
        self.segment_manager = SegmentManager()

        # Orchestrator for intelligent loading
        self.orchestrator = DataLoadingOrchestrator(
            data_manager=None,  # Uses Repository instead
            repository=self.repository,
            provider=self.provider,
        )

        # Progress renderer
        self.progress_renderer = DataProgressRenderer()
```

#### Public Interface

```python
# Main download operation (async)
async def download_data(
    self,
    symbol: str,
    timeframe: str,
    mode: str = "tail",  # tail, backfill, full
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    progress_callback: Optional[Callable] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> str:  # Returns operation_id
    """
    Download data from external provider (IB).

    Creates operation, tracks progress, saves to cache.

    Flow:
    1. Create operation in OperationsService
    2. Check cache: self.repository.load_from_cache()
    3. Analyze gaps: self.gap_analyzer.detect_gaps()
    4. Create segments: self.segment_manager.create_segments()
    5. Download: self.provider.fetch_historical_data()
    6. Save: self.repository.save_to_cache()
    7. Complete: operations_service.complete_operation()

    Returns:
        operation_id for tracking progress
    """

# Provider operations (async)
async def validate_symbol(
    self,
    symbol: str,
) -> dict:
    """
    Validate symbol with external provider.

    Returns:
        {
            "valid": bool,
            "instrument_type": str,  # "STK", "FOREX", etc.
            "exchange": str,
            "currency": str
        }
    """

async def get_head_timestamp(
    self,
    symbol: str,
    timeframe: str,
) -> datetime:
    """Get earliest available data timestamp from provider."""

async def get_provider_info(self) -> dict:
    """Get provider status and capabilities."""

# Health (async)
async def health_check(self) -> dict:
    """
    Check service health.

    Returns:
        {
            "repository_healthy": bool,
            "provider_healthy": bool,
            "operations_service_healthy": bool
        }
    """
```

#### State Model

```python
# DataAcquisitionService state (via ServiceOrchestrator)
{
    "repository": DataRepository,  # Composition
    "provider": IbDataProvider,
    "gap_analyzer": GapAnalyzer,
    "segment_manager": SegmentManager,
    "orchestrator": DataLoadingOrchestrator,
    "progress_renderer": DataProgressRenderer,

    # Inherited from ServiceOrchestrator
    "operations_service": OperationsService,
    "cancellation_tokens": dict[str, CancellationToken],
}
```

#### Dependencies

```python
# Composition
from ktrdr.data.repository import DataRepository

# External provider
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

# Gap analysis
from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.segment_manager import SegmentManager

# Orchestration
from ktrdr.data.acquisition.data_loading_orchestrator import DataLoadingOrchestrator

# Progress
from ktrdr.data.acquisition.data_progress_renderer import DataProgressRenderer

# Base class
from ktrdr.async_infrastructure import ServiceOrchestrator

# Operations
from ktrdr.api.services.operations_service import OperationsService
```

---

### 4.3 IbDataProvider

**Purpose**: HTTP client for IB host service operations.

**Architecture Pattern**: Async HTTP client implementing ExternalDataProvider interface.

**Location**: `ktrdr/data/acquisition/ib_data_provider.py`

**Refactored From**: `ktrdr/data/ib_data_adapter.py` (remove direct connection mode)

#### Class Design

```python
class IbDataProvider(ExternalDataProvider):
    """
    IB data provider via host service HTTP API.

    HTTP-only. Never connects directly to IB Gateway.
    """

    def __init__(
        self,
        host_service_url: Optional[str] = None,
    ):
        """Initialize with host service URL."""
        self.host_service_url = (
            host_service_url or
            os.getenv("IB_HOST_SERVICE_URL", "http://localhost:5001")
        )
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout

        # NO IB Gateway connection
        # NO IbDataFetcher, IbSymbolValidator imports
```

#### Public Interface

```python
async def fetch_historical_data(
    self,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch historical data from IB via host service.

    HTTP POST to host service /data/historical

    Returns:
        DataFrame with OHLCV data

    Raises:
        DataProviderError: If HTTP call fails
        DataValidationError: If response data invalid
    """

async def validate_symbol(
    self,
    symbol: str,
) -> dict:
    """
    Validate symbol with IB.

    HTTP POST to host service /data/validate
    """

async def get_symbol_info(
    self,
    symbol: str,
) -> dict:
    """
    Get symbol metadata from IB.

    HTTP POST to host service /data/symbol-info
    """

async def get_head_timestamp(
    self,
    symbol: str,
    timeframe: str,
) -> datetime:
    """
    Get earliest available data timestamp.

    HTTP POST to host service /data/head-timestamp
    """

async def health_check(self) -> dict:
    """
    Check IB Gateway connection health.

    HTTP GET to host service /health
    """

async def get_provider_info(self) -> dict:
    """
    Get provider capabilities.

    Returns:
        {
            "name": "IB",
            "available": bool,
            "connection_status": str,
            "supported_timeframes": list[str]
        }
    """
```

#### HTTP Contract

**Endpoints used** (on ib-host-service):
- `POST /data/historical` - Fetch historical data
- `POST /data/validate` - Validate symbol
- `POST /data/symbol-info` - Get symbol metadata
- `POST /data/head-timestamp` - Get earliest timestamp
- `GET /health` - Health check

**Error Handling**:
```python
# HTTP errors → Domain errors
404 → DataNotFoundError("Symbol not found in IB")
500 → DataProviderError("IB host service error")
Timeout → DataProviderError("IB host service timeout")
```

#### Dependencies

```python
# HTTP client
import httpx

# Interface
from ktrdr.data.acquisition.external_data_interface import ExternalDataProvider

# Models
from ktrdr.data.trading_hours import TradingHours

# NO dependencies on ktrdr/ib (direct IB code)
# NO dependencies on ib-host-service/ib
```

---

### 4.4 Component Moves Summary

| Component | Current Location | New Location | Reason |
|-----------|-----------------|--------------|--------|
| **DataRepository** | N/A (new) | `data/repository/data_repository.py` | Extract from DataManager |
| **DataAcquisitionService** | N/A (new) | `data/acquisition/acquisition_service.py` | Extract from DataManager |
| **IbDataProvider** | `data/ib_data_adapter.py` | `data/acquisition/ib_data_provider.py` | Refactor (HTTP-only) |
| **LocalDataLoader** | `data/local_data_loader.py` | `data/local_data_loader.py` | STAYS (shared) |
| **DataQualityValidator** | `data/components/` | `data/repository/` | Used by Repository |
| **GapAnalyzer** | `data/components/` | `data/acquisition/` | Acquisition concern |
| **SegmentManager** | `data/components/` | `data/acquisition/` | Acquisition concern |
| **GapFiller** | `ib/gap_filler.py` | `data/acquisition/` | Orchestration, not IB-specific |
| **DataLoadingOrchestrator** | `data/` | `data/acquisition/` | Acquisition orchestration |
| **DataProgressRenderer** | `data/async_infrastructure/` | `data/acquisition/` | Data-specific progress |
| **ExternalDataProvider** | `data/` | `data/acquisition/` | Provider interface |
| **IB Code** (8 files) | `ktrdr/ib/` | `ib-host-service/ib/` | Location-specific |

---

## 5. Data Flow Patterns

### 5.1 Fast Path: Load from Cache

**Scenario**: User wants to view cached data.

**Flow**:
```
┌──────────┐
│  Client  │ ktrdr data show AAPL 1d
└────┬─────┘
     │ HTTP
     ▼
┌─────────────────────────┐
│ API Endpoint            │
│ GET /data/cache/AAPL/1d │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ DataService             │
│ data_repository.load... │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ DataRepository          │
│  1. Build file path     │
│  2. loader.load()       │
│  3. validator.validate()│
│  4. Apply date filter   │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ LocalDataLoader         │
│  Read data/AAPL_1d.pkl  │
└────┬────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Cache File              │
│ data/AAPL_1d.pkl        │
└─────────────────────────┘
```

**Key Points**:
- Synchronous (fast: <100ms)
- No IB involved
- No Operations service
- Pure file I/O

**Code Example**:
```python
# API endpoint
@router.get("/data/cache/{symbol}/{timeframe}")
async def get_cached_data(symbol: str, timeframe: str):
    # Simple delegation
    df = data_repository.load_from_cache(symbol, timeframe)
    return {"data": df.to_dict(orient="records")}
```

---

### 5.2 Slow Path: Download from IB

**Scenario**: User wants to download data from IB.

**Flow**:
```
┌──────────┐
│  Client  │ ktrdr data download AAPL 1d --mode tail
└────┬─────┘
     │ HTTP POST
     ▼
┌─────────────────────────────────────────────┐
│ API Endpoint                                │
│ POST /data/acquire/download                 │
│   {symbol: "AAPL", timeframe: "1d",         │
│    mode: "tail"}                            │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ DataAcquisitionService                      │
│                                             │
│ async def download_data(...):               │
│   1. Create operation                       │
│      operation_id = ops.create_operation()  │
│                                             │
│   2. Check cache via Repository             │
│      existing = repository.load_from_cache()│
│                                             │
│   3. Analyze gaps                           │
│      gaps = gap_analyzer.detect_gaps(...)   │
│                                             │
│   4. Create segments                        │
│      segments = segment_mgr.create(...)     │
│                                             │
│   5. Download from IB (loop)                │
│      for segment in segments:               │
│        raw = await provider.fetch(...)  ────┼──┐
│        ops.update_progress(...)             │  │
│                                             │  │
│   6. Save to cache via Repository           │  │
│      repository.save_to_cache(...)          │  │
│                                             │  │
│   7. Complete operation                     │  │
│      ops.complete_operation(...)            │  │
│                                             │  │
│   return operation_id                       │  │
└─────────────────────────────────────────────┘  │
                                                 │
     ┌───────────────────────────────────────────┘
     │ HTTP POST
     ▼
┌─────────────────────────────────────────────┐
│ IbDataProvider                              │
│                                             │
│ async def fetch_historical_data(...):       │
│   response = await http_client.post(        │
│     f"{host_url}/data/historical",          │
│     json={...}                              │
│   )                                         │
│   return pd.read_json(response["data"])     │
└────┬────────────────────────────────────────┘
     │ HTTP
     ▼
┌─────────────────────────────────────────────┐
│ ib-host-service (Port 5001)                 │
│                                             │
│ POST /data/historical                       │
│   ↓                                         │
│ from ib import IbDataFetcher                │
│   ↓                                         │
│ fetcher.fetch(...)                          │
│   ↓ TCP                                     │
│ IB Gateway (Port 4002)                      │
│   ↓                                         │
│ Return historical data                      │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ Backend receives DataFrame                  │
│   ↓                                         │
│ DataAcquisitionService                      │
│   ↓                                         │
│ repository.save_to_cache(...)               │
│   ↓                                         │
│ Cache File: data/AAPL_1d.pkl                │
└─────────────────────────────────────────────┘
```

**Key Points**:
- Asynchronous (slow: seconds to minutes)
- Operations service tracks progress
- Repository used twice: check cache, save results
- HTTP-only IB access (no direct imports)

**Code Example**:
```python
# API endpoint
@router.post("/data/acquire/download")
async def start_download(request: DownloadRequest):
    # Delegate to acquisition service
    operation_id = await data_acquisition.download_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        mode=request.mode,
    )
    return {"operation_id": operation_id, "status": "started"}

# Client polls for progress
@router.get("/operations/{operation_id}")
async def get_operation_status(operation_id: str):
    return await operations_service.get_operation(operation_id)
```

---

### 5.3 Import Rules Flow

**Scenario**: Backend needs to understand what it can import.

```
Backend Code (Docker):
  ✅ CAN import:
     from ktrdr.data.repository import DataRepository
     from ktrdr.data.acquisition import DataAcquisitionService
     from ktrdr.data.acquisition import IbDataProvider
     from ktrdr.data.local_data_loader import LocalDataLoader
     from ktrdr.logging import get_logger
     from ktrdr.config import get_config
     from ktrdr.data.trading_hours import TradingHours

  ❌ CANNOT import:
     from ktrdr.ib import IbDataFetcher  # NO! IB code not for backend
     from ib_host_service.ib import ...  # NO! Host service internal

Host Service Code (Native macOS):
  ✅ CAN import:
     from ib import IbDataFetcher  # Local to host service
     from ib import IbSymbolValidator  # Local to host service
     from ktrdr.logging import get_logger  # Shared utility
     from ktrdr.config import get_ib_config  # Shared config
     from ktrdr.data.trading_hours import TradingHours  # Shared model

  ❌ CANNOT import:
     from ktrdr.data.repository import DataRepository  # Backend only
     from ktrdr.data.acquisition import ...  # Backend only
```

**Enforcement**:
- Import guards in code
- CI checks for forbidden imports
- Documentation

---

## 6. API Contracts

### 6.1 Existing Endpoints (Backwards Compatible)

**Keep working, use DataRepository**:

#### GET /data/{symbol}/{timeframe}

**Current**: Works, no changes needed

**New Implementation**: Use DataRepository

```python
@router.get("/data/{symbol}/{timeframe}")
async def get_data(symbol: str, timeframe: str):
    # Simple delegation to Repository
    df = data_repository.load_from_cache(
        symbol=symbol,
        timeframe=timeframe,
    )
    return {"data": df.to_dict(orient="records")}
```

#### GET /data/info

**Current**: Works, no changes needed

**New Implementation**: Use DataRepository

```python
@router.get("/data/info")
async def get_data_info():
    symbols = data_repository.get_available_symbols()
    # ... rest of implementation
    return {"symbols": symbols, ...}
```

#### GET /data/range

**Current**: Works, no changes needed

**New Implementation**: Use DataRepository

```python
@router.get("/data/range")
async def get_data_range(symbol: str, timeframe: str):
    range_info = data_repository.get_data_range(symbol, timeframe)
    return range_info
```

---

### 6.2 New Endpoints (Explicit Acquisition)

#### POST /data/acquire/download

**Purpose**: Download data from external provider (IB)

**Request**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "mode": "tail",  // or "backfill", "full"
  "start_date": "2024-01-01",  // optional
  "end_date": "2024-12-31"     // optional
}
```

**Response**:
```json
{
  "operation_id": "op_data_20250127_abc123",
  "status": "started",
  "message": "Data download started for AAPL 1d"
}
```

**Implementation**:
```python
@router.post("/data/acquire/download")
async def download_data(request: DownloadRequest):
    operation_id = await data_acquisition.download_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        mode=request.mode,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {
        "operation_id": operation_id,
        "status": "started",
        "message": f"Data download started for {request.symbol} {request.timeframe}"
    }
```

#### POST /data/acquire/validate-symbol

**Purpose**: Validate symbol with external provider

**Request**:
```json
{
  "symbol": "AAPL"
}
```

**Response**:
```json
{
  "valid": true,
  "instrument_type": "STK",
  "exchange": "SMART",
  "currency": "USD"
}
```

#### GET /data/acquire/provider-health

**Purpose**: Check external provider health

**Response**:
```json
{
  "ib": {
    "available": true,
    "connection_status": "connected",
    "gateway_version": "10.19",
    "last_check": "2025-01-27T10:30:00Z"
  }
}
```

---

### 6.3 Deprecated Endpoints (Compatibility)

#### POST /data/load

**Status**: DEPRECATED (keep functional, warn)

**New Behavior**: Route to `/data/acquire/download` with deprecation warning

**Response**:
```json
{
  "operation_id": "op_data_20250127_abc123",
  "status": "started",
  "deprecated": true,
  "deprecation_warning": "POST /data/load is deprecated. Use POST /data/acquire/download instead.",
  "use_instead": "/data/acquire/download"
}
```

---

### 6.4 CLI Command Changes

#### Existing Commands (No Change)

```bash
# Cache operations (fast, use Repository)
ktrdr data show AAPL 1d
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data get-range AAPL 1d
```

#### New Commands (Explicit)

```bash
# Acquisition operations (slow, use AcquisitionService)
ktrdr data download AAPL 1d --mode tail
ktrdr data download AAPL 1d --mode backfill --start 2023-01-01
ktrdr data download AAPL 1d --mode full --start 2023-01-01 --end 2024-12-31

# Validate symbol
ktrdr data validate AAPL

# Check provider health
ktrdr data provider-health
```

#### Deprecated Commands (Warn)

```bash
# Still works, but shows deprecation warning
ktrdr data load AAPL 1d
# Warning: 'ktrdr data load' is deprecated. Use 'ktrdr data download' instead.
```

---

## 7. Deployment Architecture

### 7.1 Process Layout

```
┌────────────────────────────────────────────────────┐
│ Docker Container (ktrdr-backend)                   │
│  Port: 8000                                        │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ FastAPI Application                          │ │
│  │  - API endpoints (/data/*, /data/acquire/*)  │ │
│  │  - DataRepository (local cache)              │ │
│  │  - DataAcquisitionService (orchestration)    │ │
│  │  - IbDataProvider (HTTP client)              │ │
│  │  - OperationsService                         │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  Filesystem:                                       │
│    /data/{symbol}_{timeframe}.pkl                 │
└────────────────────────────────────────────────────┘
                     │
                     │ HTTP (host.docker.internal)
                     ▼
┌────────────────────────────────────────────────────┐
│ IB Host Service (Native macOS)                     │
│  Port: 5001                                        │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ FastAPI Application                          │ │
│  │  - /data/historical                          │ │
│  │  - /data/validate                            │ │
│  │  - /health                                   │ │
│  │                                              │ │
│  │  ib/                                         │ │
│  │  ├─ connection.py (IB Gateway TCP)           │ │
│  │  ├─ data_fetcher.py                          │ │
│  │  ├─ symbol_validator.py                      │ │
│  │  └─ ...                                      │ │
│  └──────────────────────────────────────────────┘ │
│                     │                              │
│                     │ TCP                          │
│                     ▼                              │
│  IB Gateway (Port 4002)                            │
└────────────────────────────────────────────────────┘
```

### 7.2 Configuration

**Backend (Docker)**:
```python
# Environment variables
IB_HOST_SERVICE_URL=http://host.docker.internal:5001
USE_IB_HOST_SERVICE=true  # Always true for backend
DATA_DIR=/data  # Local cache directory
```

**Host Service (Native)**:
```python
# ib-host-service/config.py
HOST=0.0.0.0
PORT=5001
IB_GATEWAY_HOST=localhost
IB_GATEWAY_PORT=4002
```

### 7.3 Shared Code Access

```
Backend (Docker):
  Imports from: ktrdr/*
  Accesses: ktrdr/logging, ktrdr/config, ktrdr/data/local_data_loader.py

Host Service (Native):
  Imports from: ib/* (local) + ktrdr/* (via sys.path)
  Accesses: ktrdr/logging, ktrdr/config, ktrdr/data/trading_hours.py
```

**sys.path magic** (host service):
```python
# ib-host-service/main.py
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))  # Access ktrdr/*

# Now can import shared code
from ktrdr.logging import get_logger
from ktrdr.config import get_ib_config

# And local IB code
from ib import IbDataFetcher  # Local to host service
```

---

## 8. Quality Attributes

### 8.1 Performance

| Metric | Target | How Achieved | Measurement |
|--------|--------|--------------|-------------|
| Cache read | <100ms | Direct file I/O, no async overhead | Benchmark |
| Cache write | <200ms | Direct file I/O | Benchmark |
| Download operation | 5-60s | Async, Operations tracking, HTTP to host | Integration test |
| HTTP overhead | <5ms | Local network (Docker → host) | HTTP benchmark |

**Validation Strategy**:
```python
def benchmark_repository():
    repo = DataRepository()

    # Write benchmark
    start = time.time()
    repo.save_to_cache("AAPL", "1d", test_dataframe)
    write_time = time.time() - start
    assert write_time < 0.2  # <200ms

    # Read benchmark
    start = time.time()
    df = repo.load_from_cache("AAPL", "1d")
    read_time = time.time() - start
    assert read_time < 0.1  # <100ms
```

### 8.2 Reliability

**Failure Modes**:

| Component | Failure | Impact | Mitigation |
|-----------|---------|--------|------------|
| LocalDataLoader | File not found | Load fails | DataNotFoundError, clear message |
| IbDataProvider | HTTP timeout | Download fails | Retry with backoff, mark operation failed |
| IB Gateway | Disconnected | Provider calls fail | Health check shows status, graceful error |
| Cache corruption | Invalid data | Load fails | Validation catches, DataCorruptionError |

**Error Handling Strategy**:
- Repository: Sync exceptions (DataNotFoundError, DataCorruptionError)
- Acquisition: Async exceptions + Operations failure state
- Provider: HTTP errors translated to domain errors

### 8.3 Maintainability

**Code Complexity Reduction**:
- **Before**: DataManager (~1500 LOC, mixed concerns, mode-based conditionals)
- **After**: Repository (~400 LOC) + Acquisition (~700 LOC), clear separation
- **Reduction**: 25% fewer lines, 2x clearer responsibilities

**Testing Strategy**:

```python
# Unit Tests (Fast)
class TestDataRepository:
    def test_load_from_cache_file_not_found(self):
        repo = DataRepository()
        with pytest.raises(DataNotFoundError):
            repo.load_from_cache("NONEXISTENT", "1d")

    def test_save_to_cache_creates_file(self):
        repo = DataRepository()
        repo.save_to_cache("TEST", "1d", test_df)
        assert Path("data/TEST_1d.pkl").exists()

class TestDataAcquisitionService:
    @pytest.mark.asyncio
    async def test_download_data_creates_operation(self, mock_repo, mock_provider):
        service = DataAcquisitionService()
        service.repository = mock_repository
        service.provider = mock_provider

        operation_id = await service.download_data("AAPL", "1d", "tail")
        assert operation_id.startswith("op_data_")

# Integration Tests
class TestDataFlowIntegration:
    @pytest.mark.asyncio
    async def test_download_saves_to_cache(self):
        # End-to-end: download → save → load
        service = DataAcquisitionService()
        operation_id = await service.download_data("AAPL", "1d", "tail")

        # Wait for completion
        await wait_for_operation(operation_id)

        # Verify saved to cache
        repo = DataRepository()
        df = repo.load_from_cache("AAPL", "1d")
        assert not df.empty
```

### 8.4 Scalability

**Concurrent Operations**:
- Repository: Thread-safe (file locks via LocalDataLoader)
- Acquisition: Async, handles multiple concurrent downloads
- Operations service: Tracks all operations

**Limits**:
- 100 concurrent downloads: Operations service manages
- 1000 cache files: File system handles
- HTTP connections: httpx pool manages (default 100)

---

## 9. Migration Strategy

### 9.1 Phased Implementation

See [Implementation Plan](./03-implementation-plan-data-separation.md) for detailed tasks.

**Phase 1: Move IB to Host Service** (1 week)
- Move ktrdr/ib/*.py → ib-host-service/ib/
- Update imports in host service
- Test host service with local IB code

**Phase 2: Create Repository & Acquisition** (2-3 weeks)
- Create DataRepository (extract from DataManager)
- Create DataAcquisitionService (extract from DataManager)
- Refactor IbDataAdapter → IbDataProvider (HTTP-only)
- Create new API endpoints
- Update all internal code

**Phase 3: Cleanup** (days)
- Delete old files (data_manager.py, etc.)
- Remove deprecated endpoints
- Update documentation

### 9.2 Backwards Compatibility Strategy

**Keep working during migration**:
- Existing endpoints route to new components
- Deprecation warnings guide users
- Both old and new code coexist in Phase 2
- Only delete in Phase 3 after confirmation

### 9.3 Rollback Plan

**If issues discovered**:
1. **Phase 2**: Keep old code, disable new endpoints
2. **Phase 3**: Git revert to before deletion
3. **Any phase**: Feature flag to switch between old/new

---

## Appendix A: Comparison with Current Architecture

| Aspect | Current (DataManager) | Proposed (Repository + Acquisition) |
|--------|----------------------|-------------------------------------|
| **Concerns** | Mixed (cache + IB in one class) | Separated (cache OR IB) |
| **Sync/Async** | Mixed (`mode="local"` vs `mode="tail"`) | Clear: Repository sync, Acquisition async |
| **IB Location** | ktrdr/ib (can't execute in Docker) | ib-host-service/ib (executes natively) |
| **Backend IB Access** | Tried direct import (broken) | HTTP-only (via IbDataProvider) |
| **Composition** | Monolithic | Acquisition composes Repository |
| **Testing** | Hard (need to mock IB even for cache tests) | Easy (test Repository without IB) |
| **Responsibility** | Unclear (mode determines behavior) | Clear (explicit service selection) |

## Appendix B: References

1. [Design Document](./01-design-data-separation.md) - High-level design
2. [Implementation Plan](./03-implementation-plan-data-separation.md) - Tasks
3. Current Code:
   - `ktrdr/data/data_manager.py` - Current monolithic manager
   - `ktrdr/data/ib_data_adapter.py` - Current IB adapter (has unused direct mode)
   - `ktrdr/data/local_data_loader.py` - File I/O (will be shared)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-27
**Next Review**: After implementation Phase 1
