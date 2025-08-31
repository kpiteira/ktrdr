# KTRDR Async Architecture Specification

## Executive Summary

This specification defines the async architecture principles for KTRDR, establishing consistent patterns across all system components. The architecture harmonizes data and training paths through clear async boundaries, appropriate async usage, and shared architectural patterns while preserving existing functionality and performance requirements.

## Architectural Principles

### Principle 1: Clear Async Boundaries

All inter-service communication must follow async patterns to maintain consistency and enable proper resource management.

```mermaid
graph TB
    subgraph "Async Boundary Layers"
        CLI[CLI Layer<br/>Entry points]
        API[API Layer<br/>HTTP endpoints]
        SVC[Service Layer<br/>Business orchestration]
        MGR[Manager Layer<br/>Operational logic]
        ADP[Adapter Layer<br/>External communication]
        EXT[External Systems<br/>IB, GPU, etc.]
    end
    
    CLI -->|HTTP async| API
    API -->|async calls| SVC
    SVC -->|async calls| MGR
    MGR -->|async calls| ADP
    ADP -->|HTTP/TCP async| EXT
```

**Async Boundary Rules:**

- **Layer Boundaries**: All calls between layers are async
- **Network I/O**: Any network operation must be async
- **Long Operations**: Operations >1 second must be async with progress
- **Resource Access**: File I/O and database operations are async

### Principle 2: Appropriate Async Usage

Async should be used where it provides benefit, not everywhere by default.

```mermaid
graph LR
    subgraph "Async Required"
        A1[Network I/O<br/>HTTP, TCP calls]
        A2[File I/O<br/>Large file operations]  
        A3[Database<br/>All DB operations]
        A4[Long Operations<br/>>1 second]
    end
    
    subgraph "Sync Appropriate"
        S1[Pure Computation<br/>Math, analysis]
        S2[Data Transformation<br/>DataFrame operations]
        S3[Validation<br/>Schema checks]
        S4[Configuration<br/>Settings, parsing]
    end
```

**Usage Guidelines:**

- **Computation**: CPU-bound operations remain synchronous
- **I/O Operations**: Always async for network, file, database
- **Progress Reporting**: Async support but sync-safe interfaces
- **Error Handling**: Sync within components, async across boundaries

### Principle 3: Component Responsibility Separation

Each component has a single, well-defined responsibility with clear async characteristics.

```mermaid
graph TB
    subgraph "Component Types"
        ORCH[Orchestrators<br/>Coordinate flow<br/>ASYNC]
        COMP[Computers<br/>Process data<br/>SYNC]
        FETCH[Fetchers<br/>Retrieve data<br/>ASYNC]
        VALID[Validators<br/>Check quality<br/>SYNC]
        PROG[Progress<br/>Track state<br/>THREAD-SAFE]
    end
    
    subgraph "Responsibility Matrix"
        direction TB
        R1[Business Logic → Orchestrators]
        R2[Data Processing → Computers]
        R3[External I/O → Fetchers]
        R4[Quality Assurance → Validators]
        R5[User Feedback → Progress]
    end
```

## System-Wide Patterns

### Progress Reporting Pattern

All long-running operations must implement consistent progress reporting.

```mermaid
sequenceDiagram
    participant Client
    participant Service
    participant Manager
    participant Progress
    participant Component
    
    Client->>Service: Start operation
    Service->>Manager: Execute with progress
    Manager->>Progress: Initialize (steps, callbacks)
    
    loop For each step
        Manager->>Component: Perform work
        Component->>Progress: Update progress
        Progress->>Client: Callback notification
        Progress->>Progress: Check cancellation
    end
    
    Manager->>Progress: Complete operation
    Progress->>Client: Final notification
```

**Progress Specification:**

- **Hierarchical**: Operation → Steps → Sub-steps
- **Thread-safe**: Updates from any thread context
- **Cancellable**: Check cancellation at each level
- **Consistent**: Same interface across all operations

### Error Handling Pattern

Errors flow through consistent exception hierarchy with proper async propagation.

```mermaid
graph TB
    subgraph "Exception Hierarchy"
        BE[BaseError<br/>System root exception]
        SE[ServiceError<br/>Service-level errors]
        CE[ComponentError<br/>Component-level errors]
        IE[IntegrationError<br/>External system errors]
    end
    
    BE --> SE
    BE --> CE  
    BE --> IE
    
    subgraph "Error Flow"
        COMP[Component<br/>Raises specific error]
        MGR[Manager<br/>Adds context]
        SVC[Service<br/>Logs and handles]
        API[API<br/>Returns HTTP response]
    end
    
    COMP -->|ComponentError| MGR
    MGR -->|ServiceError + context| SVC
    SVC -->|HTTP status + message| API
```

**Error Handling Rules:**

- **Specific Errors**: Components raise specific exceptions
- **Context Addition**: Each layer adds relevant context
- **Logging**: Service layer logs before propagation
- **User-Friendly**: API layer translates to user messages

### Host Service Integration Pattern

External system communication follows consistent host service patterns.

```mermaid
graph TB
    subgraph "Host Service Architecture"
        MGR[Manager<br/>Business orchestration]
        ADP[Adapter<br/>Protocol translation]
        HOST[Host Service<br/>External system proxy]
        EXT[External System<br/>IB Gateway, GPU, etc.]
    end
    
    subgraph "Configuration"
        ENV[Environment Variables<br/>USE_*_HOST_SERVICE<br/>*_HOST_SERVICE_URL]
        CFG[Service Configuration<br/>Adapter initialization<br/>Fallback behavior]
    end
    
    MGR --> ADP
    ADP --> HOST
    HOST --> EXT
    
    ENV --> CFG
    CFG --> ADP
```

**Host Service Rules:**

- **Environment-Driven**: Configuration via environment variables
- **Fallback Support**: Direct connection when host unavailable
- **Consistent Interface**: Same adapter API regardless of mode
- **Health Monitoring**: Service health checks and recovery

## Data Path Architecture

### Current State Analysis

The data path requires different treatment due to operational complexity.

```mermaid
graph TB
    subgraph "Data Path Characteristics"
        DC1[Multiple Sequential Operations<br/>Gap analysis → Segmentation → Fetching]
        DC2[Complex Business Logic<br/>Mode-driven behavior<br/>Historical vs real-time]
        DC3[Progress Critical<br/>10+ minute operations<br/>User needs feedback]
        DC4[Cancellation Required<br/>Long operations must be stoppable]
    end
    
    subgraph "Required Architecture"
        RA1[Orchestrator Pattern<br/>Coordinates components<br/>Async boundaries]
        RA2[Component Pipeline<br/>Clear separation<br/>Sync where appropriate]
        RA3[Progress Integration<br/>Thread-safe reporting<br/>Hierarchical updates]
        RA4[Mode Awareness<br/>Behavior adaptation<br/>Performance optimization]
    end
    
    DC1 --> RA1
    DC2 --> RA2
    DC3 --> RA3
    DC4 --> RA4
```

### Data Path Component Specification

```mermaid
graph TB
    subgraph "Data Components (Incremental Extraction + Integration)"
        DM[DataManager<br/>ASYNC Orchestrator<br/>Refactored incrementally]
        
        GA[GapAnalyzer<br/>SYNC Computer<br/>Identifies missing data]
        SM[SegmentManager<br/>SYNC Computer<br/>Plans fetch strategy]
        DF[DataFetcher<br/>ASYNC Fetcher<br/>Retrieves from IB]
        DV[DataValidator<br/>SYNC Validator<br/>Ensures quality]
        DP[DataProcessor<br/>SYNC Computer<br/>Final preparation]
        PM[ProgressManager<br/>THREAD-SAFE<br/>Tracks all progress]
    end
    
    DM -->|self.gap_analyzer| GA
    DM -->|self.segment_manager| SM
    DM -->|self._data_fetcher| DF
    DM -->|self.data_validator| DV
    DM -->|self.data_processor| DP
    DM -->|self._progress_manager| PM
    
    PM --> GA
    PM --> SM
    PM --> DF
    PM --> DV
    PM --> DP
```

**Component Responsibilities:**

- **DataManager**: Orchestrates pipeline, handles async boundaries
- **GapAnalyzer**: Pure computation to identify missing data ranges
- **SegmentManager**: Pure computation to plan optimal fetch strategy
- **DataFetcher**: Async I/O for external data retrieval
- **DataValidator**: Pure computation for data quality checks
- **DataProcessor**: Pure computation for final data preparation
- **ProgressManager**: Thread-safe progress coordination

### Mode-Driven Behavior Specification

Data loading behavior adapts based on operational mode:

```mermaid
graph LR
    subgraph "Mode Behaviors"
        LOCAL[local<br/>• No gap analysis<br/>• No fetching<br/>• Return existing only]
        TAIL[tail<br/>• Recent gaps only<br/>• Small segments<br/>• Fast updates]
        BACKFILL[backfill<br/>• Historical gaps<br/>• Large segments<br/>• Efficiency focus]
        FULL[full<br/>• Complete analysis<br/>• Mixed strategy<br/>• Comprehensive]
    end
    
    subgraph "Component Adaptation"
        GA_LOCAL[GapAnalyzer<br/>Returns empty]
        GA_TAIL[GapAnalyzer<br/>Last data → now]
        GA_BACK[GapAnalyzer<br/>Start → first data]
        GA_FULL[GapAnalyzer<br/>Complete range]
        
        SM_TAIL[SegmentManager<br/>1-7 day segments]
        SM_BACK[SegmentManager<br/>30-90 day segments]
        SM_FULL[SegmentManager<br/>Adaptive sizing]
    end
    
    LOCAL --> GA_LOCAL
    TAIL --> GA_TAIL --> SM_TAIL
    BACKFILL --> GA_BACK --> SM_BACK
    FULL --> GA_FULL --> SM_FULL
```

## Training Path Architecture

### Current State Assessment

The training path demonstrates proper async architecture principles.

```mermaid
graph TB
    subgraph "Training Path Success Factors"
        TF1[Clear Delegation<br/>Manager → Host Service<br/>Simple coordination]
        TF2[Proper Async Usage<br/>Network I/O only<br/>No forced async]
        TF3[Clean Boundaries<br/>Consistent interfaces<br/>Environment-driven config]
        TF4[Host Service Pattern<br/>External complexity isolation<br/>HTTP communication]
    end
    
    subgraph "Training Architecture"
        TM[TrainingManager<br/>ASYNC Orchestrator]
        TA[TrainingAdapter<br/>ASYNC Fetcher]
        THS[Training Host Service<br/>External proxy]
        GPU[GPU Resources<br/>External system]
    end
    
    TM --> TA --> THS --> GPU
```

**Training Path Principles (Keep These):**

- **Delegation Model**: Manager delegates complex operations to host service
- **Status Monitoring**: Periodic async checks rather than continuous processing
- **Environment Configuration**: Host service usage controlled by environment
- **Clean Interfaces**: Consistent API regardless of host service vs direct

### Training Path Enhancements

Apply system-wide patterns to training path:

- **Progress Reporting**: Integrate ProgressManager for long training operations
- **Error Standardization**: Use consistent exception hierarchy
- **Cancellation Support**: Enable training operation cancellation
- **Connection Pooling**: Optimize HTTP connections for status polling

## Cross-Path Harmonization

### Shared Infrastructure

Both paths utilize common infrastructure components:

```mermaid
graph TB
    subgraph "Shared Components"
        PM[ProgressManager<br/>Thread-safe progress<br/>Used by both paths]
        AHS[AsyncHostService<br/>Base communication<br/>Host service pattern]
        EH[ErrorHandling<br/>Exception hierarchy<br/>Consistent errors]
        CP[ConnectionPool<br/>HTTP optimization<br/>Resource efficiency]
    end
    
    subgraph "Data Path Usage"
        DM[DataManager] --> PM
        DA[DataAdapter] --> AHS
        DC[Data Components] --> EH
        DF[DataFetcher] --> CP
    end
    
    subgraph "Training Path Usage"
        TM[TrainingManager] --> PM
        TA[TrainingAdapter] --> AHS
        TC[Training Components] --> EH
        TT[Training Tasks] --> CP
    end
```

### Pattern Consistency

Both paths follow the same architectural patterns:

| Aspect | Data Path | Training Path | Shared Pattern |
|--------|-----------|---------------|----------------|
| **Orchestration** | DataManager | TrainingManager | Async coordination |
| **External I/O** | DataFetcher | TrainingAdapter | Async communication |
| **Progress** | ProgressManager | ProgressManager | Thread-safe reporting |
| **Errors** | Component → Manager → Service | Component → Manager → Service | Context enrichment |
| **Configuration** | Environment-driven | Environment-driven | Host service pattern |

### Interface Standardization

Common interfaces across both paths:

```python
# Orchestrator Interface
class AsyncOrchestrator:
    async def execute_operation(self, params, progress_callback)
    def get_configuration_info(self) -> dict
    async def health_check(self) -> dict
    
# External Communication Interface  
class AsyncCommunicator:
    async def execute_request(self, request) -> response
    def get_statistics(self) -> dict
    async def health_check(self) -> dict

# Progress Interface
class ProgressReporter:
    def start_operation(self, total_steps, name)
    def update_progress(self, current, total, detail)
    def check_cancelled(self) -> bool
    def complete_operation(self)
```

## Performance Specifications

### Connection Management

All HTTP communication must implement connection pooling:

```mermaid
graph TB
    subgraph "Connection Strategy"
        CP[Connection Pool<br/>HTTP/1.1 keep-alive<br/>Maximum efficiency]
        
        subgraph "Pool Configuration"
            PC1[Max Connections: 20<br/>Per host service]
            PC2[Keep-Alive: 300s<br/>Connection reuse]
            PC3[Timeout: 30s<br/>Request timeout]
            PC4[Retry: Exponential<br/>Backoff strategy]
        end
    end
    
    subgraph "Performance Targets"
        PT1[30%+ Improvement<br/>Multi-request operations]
        PT2[2-3x Faster<br/>Parallel operations]  
        PT3[<1s Response<br/>Cancellation handling]
        PT4[<100ms Overhead<br/>Component boundaries]
    end
```

### Cancellation Requirements

All long-running operations must support sub-second cancellation:

- **Check Frequency**: Every I/O operation or 1-second intervals
- **Response Time**: <1 second from cancellation to acknowledgment
- **Clean Shutdown**: Proper resource cleanup on cancellation
- **State Preservation**: Save partial progress where possible

## Quality Requirements

### Testing Specifications

Each component type requires specific testing approaches:

```mermaid
graph TB
    subgraph "Test Categories"
        UT[Unit Tests<br/>Individual components<br/>95%+ coverage]
        IT[Integration Tests<br/>Component interactions<br/>All scenarios]
        PT[Performance Tests<br/>Benchmark validation<br/>Target metrics]
        ET[E2E Tests<br/>Real system behavior<br/>Production scenarios]
    end
    
    subgraph "Async-Specific Testing"
        AT1[Concurrency Tests<br/>Multiple operations<br/>Thread safety]
        AT2[Cancellation Tests<br/>Interrupt scenarios<br/>Clean shutdown]
        AT3[Timeout Tests<br/>Network failures<br/>Graceful degradation]
        AT4[Progress Tests<br/>Callback behavior<br/>State consistency]
    end
```

### Code Quality Standards

- **Type Hints**: All async functions must have complete type annotations
- **Documentation**: Async behavior explicitly documented
- **Error Handling**: All async operations must handle cancellation
- **Resource Management**: Proper async context managers for resources

## Migration Specifications

### Compatibility Requirements

During migration, both old and new patterns must coexist:

- **Feature Flags**: Enable/disable new architecture per operation
- **Interface Compatibility**: Existing APIs continue to work
- **Rollback Capability**: Each component can be independently reverted
- **Performance Monitoring**: Continuous comparison of old vs new

### Validation Criteria

Migration success validated through:

- **Functional Parity**: All existing operations work identically
- **Performance Improvement**: Measurable gains in target metrics
- **Error Reduction**: Fewer async-related issues
- **Code Maintainability**: Reduced complexity metrics

## Implementation Guidance for AI

### Component Implementation Patterns

#### ✅ Orchestrator (Async) - Incremental Extraction Pattern

```python
class DataManager(ServiceOrchestrator):
    """GOOD: Incrementally refactored orchestrator with component integration"""
    
    def __init__(self):
        super().__init__()
        # Component extraction + immediate integration
        self.gap_analyzer = GapAnalyzer(gap_classifier=self.gap_classifier)
        self.segment_manager = SegmentManager()
        self._data_fetcher = DataFetcher()  # Lazy initialization
        self.data_validator = DataQualityValidator()
        self._progress_manager = None  # Per-operation initialization
    
    def load_data(self, symbol: str, mode: str, progress_callback=None) -> pd.DataFrame:
        """Delegates to components while maintaining API compatibility"""
        
        # Delegate to _load_with_fallback which uses components
        return self._load_with_fallback(symbol, timeframe, mode=mode, 
                                      progress_callback=progress_callback)
    
    def _load_with_fallback(self, symbol: str, timeframe: str, mode: str, ...) -> pd.DataFrame:
        """Component delegation (already implemented)"""
        
        # 1. Gap analysis delegation (✅ Line 1523 in current code)
        gaps = self.gap_analyzer.analyze_gaps(existing_data, requested_start, 
                                            requested_end, timeframe, symbol, loading_mode)
        
        # 2. Segmentation delegation (✅ Line 1556 in current code)  
        segments = self.segment_manager.create_segments(gaps, DataLoadingMode(mode), timeframe)
        
        # 3. Async fetching delegation (✅ Line 1044 in current code)
        successful_frames = await self._data_fetcher.fetch_segments_async(...)
        
        # 4. Validation delegation (✅ Line 448 in current code)
        df_validated, quality_report = self.data_validator.validate_data(df, symbol, timeframe)
        
        return processed_data
```

#### ❌ Orchestrator Anti-Patterns

```python
class BadDataManager:
    """BAD: Wrong decomposition approaches"""
    
    def __init__(self):
        # ❌ BAD: Creating "new" DataManager instead of refactoring existing
        pass  # Parallel implementation that breaks compatibility
    
    async def load_data(self, symbol: str) -> pd.DataFrame:
        # ❌ BAD: Big-bang replacement instead of incremental extraction
        # ❌ BAD: Not leveraging existing working methods
        # ❌ BAD: Breaking API compatibility during transition
        
        # ❌ BAD: Making sync operation async for no reason
        gaps = await asyncio.to_thread(self.gap_analyzer.analyze_gaps, symbol)
        
        # ❌ BAD: Not integrating components during extraction
        segments = self._old_segmentation_method(gaps)  # God-class method still there
        
        # ❌ BAD: Creating components but not using them
        data = await self.data_fetcher.fetch_segments(segments)
        return self._old_processing_method(data)  # Still using god-class method
```

#### ✅ Async Fetcher - Correct Pattern

```python
class DataFetcher:
    """GOOD: Pure async I/O component with proper error handling"""
    
    def __init__(self):
        self._http_client = None
        self._connection_pool = None
    
    async def fetch_segments(
        self, 
        segments: List[DateSegment], 
        progress: ProgressManager
    ) -> pd.DataFrame:
        """Fetches data with connection pooling and progress"""
        
        results = []
        
        async with self._get_http_client() as client:
            # Process segments with controlled concurrency
            semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
            
            tasks = [
                self._fetch_single_segment(client, segment, progress, semaphore)
                for segment in segments
            ]
            
            # Gather with proper error handling
            segment_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(segment_results):
                if isinstance(result, Exception):
                    raise DataFetchError(f"Segment {i} failed: {result}") from result
                results.append(result)
        
        return pd.concat(results, ignore_index=True)
    
    async def _fetch_single_segment(
        self, 
        client: httpx.AsyncClient, 
        segment: DateSegment,
        progress: ProgressManager,
        semaphore: asyncio.Semaphore
    ) -> pd.DataFrame:
        """Fetch single segment with retry and cancellation"""
        
        async with semaphore:  # Control concurrency
            for attempt in range(3):  # Retry logic
                try:
                    # Check cancellation before I/O
                    if progress.check_cancelled():
                        raise OperationCancelledError("Fetch cancelled by user")
                    
                    # Actual async I/O operation
                    response = await client.get(
                        f"/data/{segment.symbol}",
                        params=segment.to_params(),
                        timeout=30.0
                    )
                    response.raise_for_status()
                    
                    # Update progress after successful fetch
                    progress.update_step_progress(1, 1, f"Fetched {segment}")
                    
                    return self._parse_response(response)
                    
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    if attempt == 2:  # Last attempt
                        raise DataFetchError(f"Failed to fetch {segment}") from e
                    
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
```

#### ❌ Fetcher Anti-Patterns

```python
class BadDataFetcher:
    """BAD: Poor async patterns, no error handling"""
    
    async def fetch_segments(self, segments: List[DateSegment]) -> pd.DataFrame:
        # ❌ BAD: No connection pooling, creates client per call
        results = []
        for segment in segments:
            async with httpx.AsyncClient() as client:  # Inefficient!
                response = await client.get(f"/data/{segment}")
                results.append(response.json())  # ❌ No error handling
        
        return pd.DataFrame(results)  # ❌ No validation
```

#### ✅ Sync Computer - Correct Pattern

```python
class GapAnalyzer:
    """GOOD: Pure sync computation with mode awareness"""
    
    def analyze_gaps(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: str, 
        end_date: str,
        mode: DataLoadingMode
    ) -> List[DateGap]:
        """Pure computation - no I/O, no async needed"""
        
        # Mode-driven behavior
        if mode == DataLoadingMode.LOCAL:
            return []  # No fetching needed
        
        # Get existing data ranges (from local cache/index)
        existing_ranges = self._get_existing_data_ranges(symbol, timeframe)
        
        if mode == DataLoadingMode.TAIL:
            return self._analyze_tail_gaps(existing_ranges, end_date)
        elif mode == DataLoadingMode.BACKFILL:
            return self._analyze_backfill_gaps(existing_ranges, start_date)
        else:  # FULL
            return self._analyze_complete_gaps(existing_ranges, start_date, end_date)
    
    def _analyze_tail_gaps(self, existing: List[DateRange], end_date: str) -> List[DateGap]:
        """Find gaps from last existing data to end_date"""
        if not existing:
            return []  # No existing data, can't determine tail
        
        last_date = max(range.end for range in existing)
        if last_date >= end_date:
            return []  # No gap
        
        return [DateGap(start=last_date, end=end_date, gap_type="tail")]
```

#### ❌ Computer Anti-Patterns

```python
class BadGapAnalyzer:
    """BAD: Unnecessary async, mixed responsibilities"""
    
    async def analyze_gaps(self, symbol: str) -> List[DateGap]:
        # ❌ BAD: Making pure computation async
        await asyncio.sleep(0)  # Pointless async
        
        # ❌ BAD: Doing I/O in computation component
        async with httpx.AsyncClient() as client:
            existing = await client.get(f"/data/{symbol}")  # Wrong layer!
        
        # ❌ BAD: No mode awareness, hardcoded behavior
        return self._find_all_gaps(existing.json())
```

### Decision Tree for Async Usage

```mermaid
flowchart TD
    START[Component Decision] --> IO{Does it perform I/O?}
    
    IO -->|Yes| NETWORK{Network I/O?}
    IO -->|No| COMPUTE[Keep Sync<br/>Pure computation]
    
    NETWORK -->|Yes| ASYNC1[Make Async<br/>Use connection pooling]
    NETWORK -->|No| FILE{File I/O?}
    
    FILE -->|Yes| SIZE{Large files or<br/>slow operations?}
    FILE -->|No| COMPUTE
    
    SIZE -->|Yes| ASYNC2[Make Async<br/>Use aiofiles]
    SIZE -->|No| SYNC1[Keep Sync<br/>Small/fast files OK]
    
    COMPUTE --> TIME{Long computation<br/>>1 second?}
    
    TIME -->|Yes| THREAD[Keep Sync<br/>Wrap in asyncio.to_thread()]
    TIME -->|No| SYNC2[Keep Sync<br/>Direct call]
    
    ASYNC1 --> PROGRESS1[Add Progress Reporting]
    ASYNC2 --> PROGRESS2[Add Progress Reporting] 
    THREAD --> PROGRESS3[Add Progress Reporting]
```

### Validation Checklist for AI Implementation

#### Component Validation

**Orchestrator Components Must:**
- [ ] Have async `execute_*` methods for main operations
- [ ] Use sync initialization (`__init__`)
- [ ] Coordinate other components, not implement business logic
- [ ] Include progress reporting for operations >1 second
- [ ] Handle cancellation gracefully
- [ ] Follow error propagation patterns

**Computer Components Must:**
- [ ] Be purely synchronous (no async/await)
- [ ] Perform single, well-defined computation
- [ ] Have no I/O operations (network, file, database)
- [ ] Be deterministic given same inputs
- [ ] Include mode awareness where applicable
- [ ] Have comprehensive unit tests

**Fetcher Components Must:**
- [ ] Be purely async with proper connection management
- [ ] Use connection pooling for HTTP operations
- [ ] Include retry logic with exponential backoff
- [ ] Report progress for long operations
- [ ] Handle cancellation at I/O boundaries
- [ ] Raise specific exceptions with context

#### Architecture Validation

**Async Boundary Validation:**
```python
# ✅ GOOD: Clear async boundaries
async def service_method(self):
    result = await self.manager.async_operation()  # Async boundary
    return result

def sync_computation(self, data):
    return self.computer.process(data)  # Sync boundary

# ❌ BAD: Mixed boundaries
def mixed_method(self):
    result = asyncio.run(self.manager.async_operation())  # Wrong!
    return result
```

**Progress Integration Validation:**
```python
# ✅ GOOD: Hierarchical progress
async def orchestrator_method(self, callback=None):
    progress = ProgressManager(callback)
    progress.start_operation(total_steps=3, name="Data Loading")
    
    # Each major step reports progress
    progress.start_step("Analyzing", step=1)
    gaps = self.analyzer.analyze()  # Component updates progress
    
    progress.start_step("Fetching", step=2) 
    data = await self.fetcher.fetch(segments, progress)  # Passes progress
    
    progress.complete_operation()
    return data

# ❌ BAD: No progress or inconsistent progress
async def bad_method(self):
    gaps = self.analyzer.analyze()  # No progress
    data = await self.fetcher.fetch(segments)  # No progress
    return data
```

### Common Implementation Mistakes

#### Mistake 1: Over-Async
```python
# ❌ BAD: Making everything async
class BadComponent:
    async def __init__(self):  # Wrong! Init should be sync
        self.value = await self.compute_value()
    
    async def simple_getter(self):  # Wrong! Property access
        return await asyncio.to_thread(lambda: self._value)

# ✅ GOOD: Async only where needed
class GoodComponent:
    def __init__(self):  # Sync initialization
        self.value = self._compute_value()
    
    def simple_getter(self):  # Sync property access
        return self._value
    
    async def fetch_external_data(self):  # Async for I/O
        return await self.http_client.get("/data")
```

#### Mistake 2: Blocking the Event Loop
```python
# ❌ BAD: Sync I/O in async context
async def bad_fetch(self):
    response = requests.get("http://api.com/data")  # Blocks event loop!
    return response.json()

# ✅ GOOD: Proper async I/O
async def good_fetch(self):
    async with self.http_client.get("http://api.com/data") as response:
        return await response.json()
```

#### Mistake 3: Poor Error Context
```python
# ❌ BAD: Lost error context
async def bad_operation(self):
    try:
        return await self.external_call()
    except Exception:
        return None  # Lost all error information

# ✅ GOOD: Preserved error context
async def good_operation(self):
    try:
        return await self.external_call()
    except httpx.TimeoutException as e:
        raise ServiceConnectionError(
            f"Timeout connecting to external service: {e}"
        ) from e
    except Exception as e:
        raise ServiceError(
            f"Unexpected error in operation: {e}"
        ) from e
```

## Conclusion

This specification establishes the architectural foundation for consistent async patterns across KTRDR. By defining clear principles, component responsibilities, and cross-path harmonization, the architecture enables:

- **Consistency**: Both data and training paths follow the same patterns
- **Performance**: Appropriate async usage with connection optimization
- **Maintainability**: Clear separation of concerns and shared infrastructure
- **Scalability**: Foundation for concurrent operations and future growth

The implementation guidance provides concrete examples and anti-patterns to ensure AI systems can build components that follow these architectural principles correctly.