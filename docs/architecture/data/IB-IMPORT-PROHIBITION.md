# IB Import Prohibition

## ⛔ Critical Architectural Rule

**The backend must NEVER import from `ktrdr/ib`.**

All IB-specific functionality is accessed exclusively through the IB Host Service via HTTP.

## Why This Rule Exists

### 1. **Docker Networking Limitations**
- IB Gateway requires direct TCP connection (port 4002)
- Docker networking adds complexity and latency
- Host service runs outside Docker for direct IB Gateway access

### 2. **Provider Independence**
- Backend should work with any data provider (IB, Polygon, Alpha Vantage, etc.)
- IB-specific code belongs in the IB Host Service, not the backend
- Allows switching providers without changing backend code

### 3. **Separation of Concerns**
- **Backend**: Generic data orchestration, business logic
- **IB Host Service**: IB-specific connection management, rate limiting, error handling

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Backend (Docker Container)                                  │
│                                                              │
│  ┌────────────────────────────────────────────┐            │
│  │ DataManager                                 │            │
│  │  └─ IbDataProvider (HTTP-only)             │            │
│  └────────────────────────────────────────────┘            │
│                                                              │
│  🚫 NEVER imports from ktrdr.ib                             │
│  ✅ ONLY uses IbDataProvider (HTTP client)                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ IB Host Service (Port 5001)                                │
│                                                              │
│  ┌────────────────────────────────────────────┐            │
│  │ IbPaceManager (rate limiting)               │            │
│  │ IbConnectionPool (connection management)    │            │
│  │ IbErrorClassifier (error handling)          │            │
│  └────────────────────────────────────────────┘            │
│                                                              │
│  ✅ Contains ALL IB-specific logic                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Direct TCP
                          ▼
                    IB Gateway (Port 4002)
```

## What Belongs Where

### ✅ Backend (`ktrdr/data/`, `ktrdr/api/`, `ktrdr/cli/`)

**Generic, provider-agnostic components:**
- `IbDataProvider` - HTTP client for host service
- `GapAnalyzer` - Detects missing data
- `SegmentManager` - Divides requests into chunks
- `DataLoadingOrchestrator` - Coordinates download flow
- `ValidationResult` - Generic validation structure

### ✅ IB Host Service (`ib-host-service/ib/`)

**IB-specific implementation:**
- `IbPaceManager` - IB rate limiting (60 req/10min)
- `IbConnectionPool` - IB connection lifecycle
- `IbErrorClassifier` - IB error codes (162, 200, etc.)
- `IbDataFetcher` - Direct IB Gateway communication

## Verification

To verify the backend has no IB imports:

```bash
# Should return ZERO results
grep -r "from ktrdr.ib import" ktrdr/ --exclude-dir=ib

# Alternative check
grep -r "from ktrdr\.ib\." ktrdr/ --exclude-dir=ib
```

**Expected output:** No matches (only comments allowed)

## Common Violations and Fixes

### ❌ WRONG: Direct IB Import

```python
# ❌ Backend importing IB-specific code
from ktrdr.ib import IbPaceManager

pace_manager = IbPaceManager()
stats = pace_manager.get_stats()
```

### ✅ CORRECT: HTTP Call to Host Service

```python
# ✅ Backend using HTTP to get stats from host service
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

provider = IbDataProvider()
health = await provider.health_check()
stats = health.get("provider_info", {})
```

### ❌ WRONG: Using IbConnectionPool

```python
# ❌ Backend managing IB connections directly
from ktrdr.ib.pool_manager import get_shared_ib_pool

pool = get_shared_ib_pool()
async with pool.get_connection() as conn:
    data = await conn.fetch_data(...)
```

### ✅ CORRECT: HTTP Request

```python
# ✅ Backend requesting data via HTTP
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

provider = IbDataProvider()
data = await provider.fetch_historical_data(
    symbol="AAPL",
    timeframe="1h",
    start_date=start,
    end_date=end
)
```

## Host Service Handles

The IB Host Service internally manages:

1. **Rate Limiting**
   - IbPaceManager tracks 60 requests / 10 minutes
   - Automatically waits when approaching limit
   - Returns HTTP 429 if rate limited

2. **Connection Management**
   - IbConnectionPool maintains persistent connections
   - Handles reconnection on failures
   - Manages multiple client IDs

3. **Error Handling**
   - IbErrorClassifier interprets IB error codes
   - Translates to generic HTTP status codes
   - Provides actionable error messages

## Benefits

✅ **Provider Independence**: Switch data providers without changing backend
✅ **Simplified Docker**: No IB Gateway networking in Docker
✅ **Better Testing**: Mock HTTP responses instead of IB Gateway
✅ **Clear Boundaries**: IB logic isolated in dedicated service
✅ **Scalability**: Multiple backends can share one host service

## Enforcement

This rule is enforced by:

1. **Code Review**: Check for IB imports in PRs
2. **Automated Tests**: CI runs verification command
3. **Architecture Reviews**: Periodic audits
4. **Documentation**: This file and design docs

## Related Documents

- [Data Separation Design](./01-design-data-separation.md)
- [Data Separation Architecture](./02-architecture-data-separation.md)
- [Implementation Plan](./03-implementation-plan-v2-revised.md)
- [IB Host Service README](../../../ib-host-service/README.md)

## Last Updated

- **Date**: 2025-01-01
- **Task**: Task 3.5 - Verify No IB Imports
- **Status**: ✅ All IB imports removed from backend
