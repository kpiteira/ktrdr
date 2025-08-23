# KTRDR Unified Async Architecture Recommendations

## Executive Summary

Based on the comprehensive analysis of both your IB and Training service paths, I recommend a **unified async service architecture** that takes the best patterns from your Training Host Service and applies them across your entire system. Your Training Host Service already demonstrates the right architectural approach - the solution is to extend this proven pattern to all operations while fixing the CLI layer inefficiencies that affect both paths.

## The Core Problem: Architectural Inconsistency

You currently have **two parallel architectures** that handle similar problems with different approaches:

**IB Path:** Great host service pattern, but broken by DataManager sync bottleneck
**Training Path:** Superior backend async flow, but same CLI inefficiencies

The solution is **architectural unification** around your proven microservice pattern.

## Architecture Overview

### Current State vs Target State

```mermaid
graph TB
    subgraph "CURRENT: Mixed Async/Sync Architecture"
        CLI1["CLI Commands<br/>Sync + asyncio.run()"]
        HTTP1["HTTP Client<br/>New per command"]
        API1["FastAPI Endpoints<br/>Async ✅"]
        
        subgraph "Data Path - BROKEN"
            DS1["DataService<br/>Async ✅"]
            DM1["DataManager<br/>SYNC ❌"]
            DA1["DataAdapter<br/>Mixed patterns"]
        end
        
        subgraph "Training Path - BETTER"
            TS1["TrainingService<br/>Async ✅"]
            TM1["TrainingManager<br/>Async ✅"]
            TA1["TrainingAdapter<br/>Async ✅"]
        end
        
        CLI1 --> HTTP1 --> API1
        API1 --> DS1 --> DM1 --> DA1
        API1 --> TS1 --> TM1 --> TA1
        
        style DM1 fill:#ffcccc
        style DA1 fill:#ffcccc
    end
    
    subgraph "TARGET: Unified Async Architecture"
        CLI2["AsyncCLIClient<br/>Connection reuse ✅"]
        HTTP2["HTTP Client<br/>Persistent connection"]
        API2["FastAPI Endpoints<br/>Async ✅"]
        
        subgraph "Foundation Layer"
            AHS["AsyncHostService<br/>Base class"]
            ERR["Error Handling<br/>Custom exceptions"]
        end
        
        subgraph "Unified Data Path"
            DS2["DataService<br/>Async ✅"]
            DM2["AsyncDataManager<br/>Async ✅"]
            DA2["AsyncDataAdapter<br/>extends AsyncHostService"]
        end
        
        subgraph "Unified Training Path"
            TS2["TrainingService<br/>Async ✅"]
            TM2["TrainingManager<br/>Async ✅"]
            TA2["TrainingAdapter<br/>extends AsyncHostService"]
        end
        
        CLI2 --> HTTP2 --> API2
        API2 --> DS2 --> DM2 --> DA2
        API2 --> TS2 --> TM2 --> TA2
        
        DA2 -.-> AHS
        TA2 -.-> AHS
        AHS -.-> ERR
        
        style CLI2 fill:#ccffcc
        style DM2 fill:#ccffcc
        style DA2 fill:#ccffcc
        style TA2 fill:#ccffcc
        style AHS fill:#cceeff
    end
```

### Component Roles and Deployment

**Key Concept: Manager vs Adapter**

- **Manager** = Business logic (runs in backend container)
- **Adapter** = Communication interface (runs in backend container, talks to services)

```mermaid
graph TB
    subgraph "Client Layer"
        CLI["KTRDR CLI Commands"]
        WEB["Web Dashboard"]
    end
    
    subgraph "Docker Backend Container"
        subgraph "API Layer"
            API["FastAPI Endpoints"]
        end
        
        subgraph "Service Layer"
            DS["DataService"]
            TS["TrainingService"]
        end
        
        subgraph "Manager Layer (Business Logic)"
            DM["AsyncDataManager<br/>- Coordinates data operations<br/>- Handles caching/validation<br/>- Business rules"]
            TM["TrainingManager<br/>- Coordinates training<br/>- Manages training state<br/>- Business rules"]
        end
        
        subgraph "Adapter Layer (Communication)"
            DA["AsyncDataAdapter<br/>- Communicates with IB services<br/>- Protocol translation<br/>- Connection management"]
            TA["TrainingAdapter<br/>- Communicates with training services<br/>- Protocol translation<br/>- Connection management"]
        end
        
        subgraph "Foundation"
            AHS["AsyncHostService<br/>Base class for adapters"]
        end
    end
    
    subgraph "Optional Host Services (Separate Containers)"
        IB_HOST["IB Host Service<br/>Port 8001<br/>Manages IB connections"]
        TRAIN_HOST["Training Host Service<br/>Port 8002<br/>Manages GPU/training"]
    end
    
    subgraph "External Systems"
        IB_GW["IB Gateway<br/>TWS/Gateway"]
        GPU["GPU Resources<br/>CUDA/Training"]
    end
    
    CLI --> API
    WEB --> API
    
    API --> DS --> DM --> DA
    API --> TS --> TM --> TA
    
    DA --> AHS
    TA --> AHS
    
    %% Host service paths (recommended)
    DA -->|"HTTP calls<br/>USE_IB_HOST_SERVICE=true"| IB_HOST
    TA -->|"HTTP calls<br/>USE_TRAINING_HOST_SERVICE=true"| TRAIN_HOST
    
    %% Direct connection fallback
    DA -.->|"Direct connection<br/>USE_IB_HOST_SERVICE=false"| IB_GW
    TA -.->|"Direct connection<br/>USE_TRAINING_HOST_SERVICE=false"| GPU
    
    %% Host services to external systems
    IB_HOST --> IB_GW
    TRAIN_HOST --> GPU
    
    style DM fill:#fff3e0
    style TM fill:#fff3e0
    style DA fill:#e3f2fd
    style TA fill:#e3f2fd
    style IB_HOST fill:#e1f5fe
    style TRAIN_HOST fill:#e1f5fe
```

### Component Responsibilities Explained

| Component | Purpose | Runs Where | Responsibilities |
|-----------|---------|------------|------------------|
| **AsyncDataManager** | Business Logic | Backend Container | • Data validation and caching<br/>• Business rules (date ranges, symbols)<br/>• Coordinates multiple data sources<br/>• Error handling and retry logic |
| **AsyncDataAdapter** | Communication | Backend Container | • HTTP calls to IB Host Service<br/>• Protocol translation (REST ↔ IB)<br/>• Connection management<br/>• Fallback to direct IB connections |
| **TrainingManager** | Business Logic | Backend Container | • Training workflow coordination<br/>• Model lifecycle management<br/>• Training state and progress tracking<br/>• Resource allocation decisions |
| **TrainingAdapter** | Communication | Backend Container | • HTTP calls to Training Host Service<br/>• Protocol translation (REST ↔ Training)<br/>• GPU resource communication<br/>• Fallback to local training |

**Why This Split?**

- **Manager** = "What to do" (business logic, stays in your main application)
- **Adapter** = "How to communicate" (protocol details, can be swapped out)

**Example Flow:**
1. `DataService.load_data()` → calls `AsyncDataManager.load_data()`
2. `AsyncDataManager` validates symbol, checks cache, determines date range
3. `AsyncDataManager` calls `AsyncDataAdapter.fetch_historical_data()`
4. `AsyncDataAdapter` makes HTTP call to IB Host Service OR direct IB connection
5. `AsyncDataAdapter` translates response back to standard DataFrame format
6. `AsyncDataManager` caches result and applies business rules
7. `DataService` returns final result to API

## Recommended Unified Architecture

### 1. Standardize on the Host Service Pattern

Your Training Host Service proves that the **HTTP microservice pattern works excellently**. Extend this pattern to all external operations:

**Current State:**
- IB Host Service (good, but underutilized)
- Training Host Service (excellent pattern)
- Direct IB connections (problematic)

**Target State:**
- **Unified Host Services** for all external operations
- **Standard HTTP-based communication** for all services
- **Consistent session management** for long-running operations
- **Proper resource isolation** for all external dependencies

### 2. Fix the CLI Foundation Layer

Both IB and Training commands suffer from the **same CLI inefficiencies**. Create a unified CLI foundation that eliminates these problems:

**Current Problem Pattern (Both Paths):**
```python
@command()
def some_command(...):
    asyncio.run(_some_command_async(...))  # Creates new event loop every time
    
async def _some_command_async(...):
    async with httpx.AsyncClient() as client:  # Creates new HTTP client every time
        response = await client.request(...)
```

**Recommended Solution Pattern:**
```python
# New unified CLI foundation
class UnifiedAsyncCLI:
    def __init__(self):
        self._loop = None
        self._http_client = None
        self._api_client = None
    
    async def __aenter__(self):
        # Reusable event loop and HTTP client
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._api_client = KtrdrApiClient(self._http_client)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()

# Commands use the unified foundation
@command()
def train_model(...):
    async def _train_async():
        async with UnifiedAsyncCLI() as cli:
            return await cli.api_client.start_training(...)
    
    return asyncio.run(_train_async())

@command() 
def show_data(...):
    async def _show_async():
        async with UnifiedAsyncCLI() as cli:
            return await cli.api_client.get_data(...)
    
    return asyncio.run(_show_async())
```

### 3. Unify the Backend Service Layer

Create a standard async service foundation that both data and training operations can use:

**Standard Async Service Base:**
```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import httpx

class AsyncHostService(ABC):
    """Base class for all host service integrations."""
    
    def __init__(
        self, 
        service_name: str,
        use_host_service: bool = False,
        host_service_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.service_name = service_name
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for host service communication."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def _call_host_service_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Standard POST call to host service."""
        if not self.use_host_service:
            raise RuntimeError(f"{self.service_name} host service not enabled")
        
        client = await self._get_client()
        url = f"{self.host_service_url}{endpoint}"
        
        try:
            response = await client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ServiceConnectionError(f"{self.service_name} host service request failed: {str(e)}")
    
    async def _call_host_service_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Standard GET call to host service."""
        if not self.use_host_service:
            raise RuntimeError(f"{self.service_name} host service not enabled")
        
        client = await self._get_client()
        url = f"{self.host_service_url}{endpoint}"
        
        try:
            response = await client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ServiceConnectionError(f"{self.service_name} host service request failed: {str(e)}")
    
    async def close(self):
        """Clean up HTTP client resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check if the service is healthy and available."""
        pass
```

### 4. Standardize Service Adapters

Both data and training adapters should follow the same pattern:

**Unified Data Adapter (Async):**
```python
class AsyncDataAdapter(AsyncHostService):
    """Unified async data adapter for IB operations."""
    
    def __init__(self, use_host_service: bool = False, host_service_url: str = None):
        super().__init__(
            service_name="IB",
            use_host_service=use_host_service,
            host_service_url=host_service_url or "http://localhost:5001"
        )
        
        # Initialize local components only if not using host service
        if not use_host_service:
            self.symbol_validator = IbSymbolValidator()
            self.data_fetcher = IbDataFetcher()
        else:
            self.symbol_validator = None
            self.data_fetcher = None
    
    async def fetch_historical_data(self, symbol: str, timeframe: str, **kwargs) -> pd.DataFrame:
        """Fetch historical data using host service or local connection."""
        if self.use_host_service:
            # Use host service (recommended)
            response = await self._call_host_service_post("/data/historical", {
                "symbol": symbol,
                "timeframe": timeframe,
                **kwargs
            })
            # Convert response to DataFrame
            return pd.DataFrame(response["data"])
        else:
            # Local connection (fallback)
            return await self.data_fetcher.fetch_data_async(symbol, timeframe, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IB service health."""
        if self.use_host_service:
            return await self._call_host_service_get("/health")
        else:
            # Local health check
            return {"status": "healthy", "mode": "local"}

class AsyncTrainingAdapter(AsyncHostService):
    """Unified async training adapter."""
    
    def __init__(self, use_host_service: bool = False, host_service_url: str = None):
        super().__init__(
            service_name="Training",
            use_host_service=use_host_service,
            host_service_url=host_service_url or "http://localhost:5002"
        )
        
        # Initialize local trainer only if not using host service
        if not use_host_service:
            from .train_strategy import StrategyTrainer
            self.local_trainer = StrategyTrainer()
        else:
            self.local_trainer = None
    
    async def start_training_session(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start training using host service or local trainer."""
        if self.use_host_service:
            # Use host service (recommended)
            return await self._call_host_service_post("/training/start", config)
        else:
            # Local training (fallback)
            return await self.local_trainer.train_async(config)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check training service health."""
        if self.use_host_service:
            return await self._call_host_service_get("/health")
        else:
            return {"status": "healthy", "mode": "local"}
```

### 5. Make All Managers Consistently Async

The DataManager should follow the same async pattern as TrainingManager:

**Async Data Manager:**
```python
class AsyncDataManager:
    """Async data manager following the same pattern as TrainingManager."""
    
    def __init__(self):
        self.data_adapter = self._initialize_data_adapter()
    
    def _initialize_data_adapter(self) -> AsyncDataAdapter:
        """Initialize data adapter based on environment variables."""
        env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
        use_host_service = env_enabled in ("true", "1", "yes")
        host_service_url = os.getenv("IB_HOST_SERVICE_URL", "http://localhost:5001")
        
        return AsyncDataAdapter(
            use_host_service=use_host_service,
            host_service_url=host_service_url
        )
    
    async def load_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: str, 
        end_date: str,
        source: str = "ib"
    ) -> pd.DataFrame:
        """Load data asynchronously."""
        if source == "ib":
            return await self.data_adapter.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
        elif source == "local":
            # Local file loading (already async-safe)
            return await self._load_local_data_async(symbol, timeframe, start_date, end_date)
        else:
            raise ValueError(f"Unknown data source: {source}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of data services."""
        return await self.data_adapter.health_check()
```

## Implementation Strategy

### Implementation Dependencies

```mermaid
graph TB
    subgraph "Phase 1: Foundation (DONE ✅)"
        P1A[AsyncCLIClient<br/>Base class]
        P1B[CLI Command Migration<br/>data show, models train]
        P1C[Performance Benchmarks<br/>50-70% improvement]
    end
    
    subgraph "Phase 2: Service Foundation"
        P2A[Error Handling System<br/>Custom exceptions]
        P2B[AsyncHostService<br/>Abstract base class]
        P2C[Integration Tests<br/>Foundation validation]
    end
    
    subgraph "Phase 3: Data Layer Unification"
        P3A[AsyncDataAdapter<br/>extends AsyncHostService]
        P3B[AsyncDataManager<br/>uses AsyncDataAdapter]
        P3C[DataService Integration<br/>async chain]
    end
    
    subgraph "Phase 4: Service Standardization"
        P4A[TrainingAdapter Refactor<br/>extends AsyncHostService]
        P4B[Code Duplication Removal<br/>shared patterns]
        P4C[Performance Optimization<br/>connection pooling]
    end
    
    %% Dependencies within phases
    P1A --> P1B --> P1C
    P2A --> P2B --> P2C
    P3A --> P3B --> P3C
    P4A --> P4B --> P4C
    
    %% Dependencies between phases
    P1C --> P2A
    P2B --> P3A
    P2C --> P3A
    P3A --> P3B
    P3C --> P4A
    
    %% Critical dependency paths
    P2B -.->|provides base class| P3A
    P2B -.->|provides base class| P4A
    P2A -.->|provides exceptions| P2B
    P3A -.->|required by| P3B
    
    style P1A fill:#ccffcc
    style P1B fill:#ccffcc  
    style P1C fill:#ccffcc
    style P2B fill:#fff3e0
    style P3A fill:#fff3e0
    style P3B fill:#fff3e0
```

### Phase 1: CLI Foundation (High Impact, Low Risk)

**Week 1-2: Create Unified CLI Base**
1. Implement `UnifiedAsyncCLI` base class
2. Migrate 2-3 high-usage commands (like `ktrdr data show`, `ktrdr models train`)
3. Measure performance improvement (should see 2-3x speedup)
4. Validate no functional regression

**Benefits:** Immediate 2-3x performance improvement for CLI commands, reduced connection overhead

### Phase 2: Backend Unification (Medium Risk, High Long-term Value)

**Week 3-4: Async Service Foundation**
1. Implement `AsyncHostService` base class
2. Create unified error handling and connection patterns
3. Add comprehensive health check infrastructure

**Week 5-6: Data Manager Async Migration**
1. Create `AsyncDataManager` following TrainingManager pattern
2. Update DataService to use async DataManager
3. Migrate IB operations to use host service by default
4. Maintain backward compatibility during transition

**Benefits:** Eliminates sync/async bottleneck, consistent error handling, better resource utilization

### Phase 3: Full Unification (Low Risk, High Maintainability)

**Week 7-8: Adapter Standardization**
1. Refactor both data and training adapters to use `AsyncHostService`
2. Standardize configuration patterns
3. Unify testing approaches

**Benefits:** Single codebase pattern to maintain, shared testing infrastructure, consistent behavior

### Phase 4: Optimization and Polish

**Week 9-10: Performance Optimization**
1. Implement connection pooling
2. Add batching support for multiple operations
3. Optimize host service communication patterns

## Expected Benefits

### Immediate (Phase 1)
- **2-3x faster CLI commands** from connection reuse
- **Reduced resource usage** from eliminated event loop churning
- **Better user experience** with responsive CLI

### Medium-term (Phase 2-3)
- **No more IB Gateway corruption** from proper async handling
- **Consistent error messages** across all operations
- **Single debugging approach** for all async issues
- **Easier testing** with unified patterns

### Long-term (Phase 4+)
- **Maintainable codebase** with one async pattern
- **Scalable architecture** that can handle concurrent operations
- **Reliable operations** without sync/async mixing problems
- **Foundation for new features** following proven patterns

## Risk Assessment

**Low Risk:**
- CLI foundation changes (isolated impact, easy to revert)
- Host service adoption (already proven to work)

**Medium Risk:**
- DataManager async migration (affects many operations, but well-understood change)

**Mitigation Strategies:**
- **Feature flags** for new vs old patterns during transition
- **Parallel implementation** allowing side-by-side comparison
- **Comprehensive testing** at each phase
- **Gradual rollout** starting with low-usage operations

## Success Metrics

**Performance:**
- CLI command latency reduced by 50-70%
- Elimination of IB Gateway restart requirements
- Support for 10+ concurrent training sessions

**Code Quality:**
- Single async pattern across codebase
- 50% reduction in async-related bug reports
- Unified error handling and testing approaches

**Developer Experience:**
- New developers can understand async patterns in 1 day vs 1 week
- Single debugging approach for all async issues
- Consistent behavior across all operations

## Conclusion

Your Training Host Service already proves that the microservice async pattern works excellently. The recommended approach takes this proven success and extends it across your entire architecture, while fixing the CLI inefficiencies that affect both paths.

This isn't about rewriting everything - it's about **standardizing on your successful patterns** and **eliminating the architectural inconsistencies** that create maintenance burden and performance problems.

The result will be a **unified, maintainable, and high-performance** async architecture that leverages the best of both your current implementations while eliminating their individual weaknesses.

---

## LLM Implementation Guide

### Component Implementation Order (Critical Dependencies)

**MUST follow this exact sequence:**

1. **Error Handling Foundation** (Independent)
   - Custom exceptions: `ServiceConnectionError`, `ServiceTimeoutError`, `ServiceConfigurationError`
   - No dependencies - can be implemented anytime

2. **AsyncHostService Base Class** (Depends on: Error Handling)
   - Abstract base class for all service communication
   - Provides: `_call_host_service_post()`, `_call_host_service_get()`, `health_check()`
   - Used by: AsyncDataAdapter, TrainingAdapter

3. **AsyncDataAdapter** (Depends on: AsyncHostService)  
   - Extends AsyncHostService
   - Handles IB Host Service vs direct IB connection routing
   - Must be implemented BEFORE AsyncDataManager

4. **AsyncDataManager** (Depends on: AsyncDataAdapter)
   - Business logic layer
   - Uses AsyncDataAdapter for communication
   - Replaces synchronous DataManager

5. **TrainingAdapter Refactor** (Depends on: AsyncHostService)
   - Refactor existing TrainingAdapter to extend AsyncHostService
   - Remove duplicate HTTP client code

### File Locations and Naming

```
ktrdr/
├── exceptions/
│   ├── __init__.py
│   ├── service_exceptions.py          # ServiceConnectionError, etc.
├── base/
│   ├── __init__.py  
│   ├── async_host_service.py          # AsyncHostService abstract base
├── data/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── async_data_adapter.py      # AsyncDataAdapter
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── async_data_manager.py      # AsyncDataManager
├── training/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── training_adapter.py        # Refactored TrainingAdapter
```

### Component Interface Contracts

**AsyncHostService (Abstract Base Class)**
```python
class AsyncHostService(ABC):
    def __init__(self, service_name: str, use_host_service: bool, host_service_url: str, timeout: float)
    async def _call_host_service_post(self, endpoint: str, data: Dict) -> Dict
    async def _call_host_service_get(self, endpoint: str, params: Dict) -> Dict
    async def close(self) -> None
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]
```

**AsyncDataAdapter Interface**
```python
class AsyncDataAdapter(AsyncHostService):
    def __init__(self, use_host_service: bool, host_service_url: str)
    async def fetch_historical_data(self, symbol: str, timeframe: str, **kwargs) -> pd.DataFrame
    async def health_check(self) -> Dict[str, Any]
```

**AsyncDataManager Interface**  
```python
class AsyncDataManager:
    def __init__(self)
    async def load_data(self, symbol: str, timeframe: str, start_date: str, end_date: str, source: str) -> pd.DataFrame
    async def get_health_status(self) -> Dict[str, Any]
```

### Environment Variables and Configuration

| Variable | Purpose | Values | Default |
|----------|---------|--------|---------|
| `USE_IB_HOST_SERVICE` | Route IB calls to host service | `true`/`false` | `true` |
| `IB_HOST_SERVICE_URL` | IB host service endpoint | URL | `http://localhost:8001` |
| `USE_TRAINING_HOST_SERVICE` | Route training to host service | `true`/`false` | `true` |
| `TRAINING_HOST_SERVICE_URL` | Training host service endpoint | URL | `http://localhost:8002` |

### Error Handling Patterns

**Service Communication Errors**
```python
# When host service unavailable
raise ServiceConnectionError(f"{service_name} host service unavailable at {url}")

# When timeout occurs  
raise ServiceTimeoutError(f"{service_name} request timed out after {timeout}s")

# When configuration invalid
raise ServiceConfigurationError(f"Invalid {service_name} configuration: {details}")
```

### Testing Requirements

**Each component MUST have:**
- Unit tests with >95% coverage
- Mock tests for external service calls
- Integration tests with actual services
- Error scenario testing
- Performance benchmarks (where applicable)

**Test file locations:**
```
tests/
├── unit/
│   ├── base/
│   │   ├── test_async_host_service.py
│   ├── data/
│   │   ├── test_async_data_adapter.py
│   │   ├── test_async_data_manager.py
├── integration/
│   ├── test_data_flow_integration.py
│   ├── test_training_flow_integration.py
```

### Code Quality Gates

**Every implementation MUST pass:**
- `pytest` (all tests pass, >95% coverage)
- `mypy --strict` (type checking)
- `black ktrdr tests` (code formatting)
- `ruff ktrdr` (linting)
- Manual testing scenarios documented in tasks

### Implementation Anti-Patterns (DO NOT DO)

❌ **Don't implement AsyncDataManager before AsyncDataAdapter**
❌ **Don't create new event loops in Manager/Adapter classes**  
❌ **Don't add sync methods to async classes**
❌ **Don't bypass AsyncHostService for HTTP calls**
❌ **Don't hardcode URLs - use environment variables**
❌ **Don't ignore error handling - use custom exceptions**

### Success Validation

**How to verify correct implementation:**
1. All CLI commands work with same functionality
2. Performance improvement measurable (50%+ faster)
3. No sync/async mixing in call chains
4. Host service and local modes both work
5. Error messages are clear and actionable
6. All tests pass and coverage >95%