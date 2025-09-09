# SLICE 2: CANCELLATION EXTRACTION AND ENHANCEMENT

**Duration**: 1 week (5 days)  
**Branch**: `slice-2-cancellation-extraction`  
**Goal**: Unify cancellation patterns across data managers using ServiceOrchestrator (TrainingManager inheritance moved to Slice 3)  
**Priority**: High  
**Depends on**: Slice 1 completion

## Overview

This slice focuses on **consolidating 90% of cancellation logic in ServiceOrchestrator** by refactoring DataJobManager (formerly AsyncDataLoader) to delegate all cancellation handling to ServiceOrchestrator. This creates a unified cancellation system where domain-specific components only handle job state management.

**KEY INSIGHT**: ServiceOrchestrator already provides `execute_with_cancellation()` - we need to use it consistently rather than extract it.

**NOTE**: TrainingManager ServiceOrchestrator inheritance moved to Slice 3 for proper vertical slice alignment.

## Success Criteria

- [ ] TrainingManager inheritance moved to Slice 3 for vertical slice alignment
- [ ] DataManager uses ServiceOrchestrator.execute_with_cancellation() instead of custom patterns
- [ ] **AsyncDataLoader → DataJobManager** (renamed) uses ServiceOrchestrator.execute_with_cancellation()
- [ ] **DataJob → DataLoadingJob** (renamed) implements CancellationToken protocol
- [ ] All complex cancellation logic moved to ServiceOrchestrator
- [ ] CLI KeyboardInterrupt cancels operations through unified interface

## Key Renames in Slice 2

**File Renames:**
- `ktrdr/data/async_data_loader.py` → `ktrdr/data/components/data_job_manager.py`

**Class Renames:**
- `AsyncDataLoader` → `DataJobManager` 
- `DataJob` → `DataLoadingJob`

**Why these renames:**
- `DataJobManager` better reflects its role as a job orchestrator
- `DataLoadingJob` is more specific about what type of job
- Consistent with ServiceOrchestrator naming patterns

## Current Architecture Understanding

**DataManager Responsibilities (Already Good - Just Enhance)**:
```python
# DataManager inherits ServiceOrchestrator, gets execute_with_cancellation() for FREE:
- DataManager delegates to DataJobManager for async job orchestration
- DataJobManager implements CancellationToken protocol
- ServiceOrchestrator handles ALL cancellation complexity
```

**TrainingManager Responsibilities** (Moved to Slice 3):
```python
# TrainingManager inheritance moved to Slice 3 for vertical slice alignment
# Slice 3 will make TrainingManager inherit ServiceOrchestrator
```

**Implementation Pattern**:
1. **Extract CancellationToken Protocol**: From proven AsyncDataLoader patterns
2. **Enhance DataManager**: Use ServiceOrchestrator.execute_with_cancellation() consistently
3. **Refactor AsyncDataLoader → DataJobManager**: With ServiceOrchestrator integration
4. **Unified CLI Cancellation**: KeyboardInterrupt through ServiceOrchestrator patterns

## Tasks

### Task 2.1: Extract Generic Operation Management from AsyncDataLoader
**Day**: 1  
**Assignee**: AI IDE Agent  
**Priority**: 10

**Description**: Extract the generic async operation management patterns from AsyncDataLoader into reusable components that can be used by ServiceOrchestrator for consistent operation lifecycle management across both data and training domains.

**Acceptance Criteria**:
- [ ] Generic operation management patterns extracted from AsyncDataLoader
- [ ] CancellationToken protocol based on proven AsyncDataLoader cancellation
- [ ] Operation lifecycle management (start, progress, cancellation, cleanup)
- [ ] Thread-safe operation state management
- [ ] Integration points for ServiceOrchestrator.execute_with_cancellation()

**Implementation Details**:
```python
# File: ktrdr/async/operations.py (extracted from AsyncDataLoader patterns)
from abc import ABC, abstractmethod
from typing import Protocol, Optional, Any
import asyncio
from dataclasses import dataclass
from enum import Enum

class OperationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CancellationToken(Protocol):
    """Cancellation interface extracted from proven AsyncDataLoader patterns."""
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        ...
    
    def cancel(self, reason: str = "Operation cancelled") -> None:
        """Request cancellation with reason."""
        ...
    
    async def wait_for_cancellation(self) -> None:
        """Async wait for cancellation signal."""
        ...

@dataclass
class OperationContext:
    """Operation context with cancellation support."""
    
    operation_id: str
    operation_name: str
    status: OperationStatus = OperationStatus.PENDING
    cancellation_token: Optional[CancellationToken] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[Exception] = None
    
    def is_cancelled(self) -> bool:
        return self.cancellation_token and self.cancellation_token.is_cancelled()
    
    def cancel(self, reason: str = "Operation cancelled") -> None:
        if self.cancellation_token:
            self.cancellation_token.cancel(reason)
        self.status = OperationStatus.CANCELLED

class AsyncOperationManager:
    """Generic operation manager extracted from AsyncDataLoader patterns."""
    
    def __init__(self):
        self._operations: dict[str, OperationContext] = {}
        self._lock = asyncio.RLock()
    
    async def execute_operation(self, 
                              operation_id: str,
                              operation_name: str,
                              operation_func: Callable,
                              cancellation_token: Optional[CancellationToken] = None) -> Any:
        """Execute operation with lifecycle management and cancellation."""
        
        context = OperationContext(
            operation_id=operation_id,
            operation_name=operation_name,
            cancellation_token=cancellation_token
        )
        
        async with self._lock:
            self._operations[operation_id] = context
            
        try:
            context.status = OperationStatus.RUNNING
            context.start_time = time.time()
            
            # Check cancellation before starting
            if context.is_cancelled():
                raise OperationCancelledException(f"Operation {operation_name} was cancelled before starting")
            
            result = await operation_func(context)
            
            context.status = OperationStatus.COMPLETED
            context.end_time = time.time()
            return result
            
        except OperationCancelledException:
            context.status = OperationStatus.CANCELLED
            context.end_time = time.time()
            raise
        except Exception as e:
            context.status = OperationStatus.FAILED
            context.error = e
            context.end_time = time.time()
            raise
    
    async def cancel_operation(self, operation_id: str, reason: str = "Cancelled by request") -> bool:
        """Cancel specific operation."""
        async with self._lock:
            if operation_id in self._operations:
                self._operations[operation_id].cancel(reason)
                return True
            return False
    
    def get_operation_status(self, operation_id: str) -> Optional[OperationContext]:
        """Get operation status."""
        return self._operations.get(operation_id)

class OperationCancelledException(Exception):
    """Exception raised when operation is cancelled."""
    pass
```

**Testing Requirements**:
- [ ] Generic operation management working correctly
- [ ] CancellationToken protocol compatibility with AsyncDataLoader patterns
- [ ] Operation lifecycle management (pending → running → completed/failed/cancelled)
- [ ] Thread-safe operation state management
- [ ] Integration readiness for ServiceOrchestrator
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/async/operations.py` with extracted operation patterns
- [ ] `tests/unit/async/test_operations.py` comprehensive test suite
- [ ] CancellationToken protocol based on AsyncDataLoader success
- [ ] Generic operation management based on proven AsyncDataLoader patterns
- [ ] Integration tests showing identical cancellation behavior
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.2: Update DataManager for ServiceOrchestrator Cancellation
**Day**: 2  
**Assignee**: AI IDE Agent  
**Priority**: 9  
**Depends on**: Task 2.1

**Description**: Update DataManager to leverage ServiceOrchestrator.execute_with_cancellation() instead of custom cancellation patterns, creating consistency across all managers while preserving all existing functionality.

**Acceptance Criteria**:
- [ ] DataManager.load_data() uses ServiceOrchestrator.execute_with_cancellation()
- [ ] DataManager leverages ServiceOrchestrator patterns instead of custom async patterns
- [ ] ALL existing DataManager API and behavior preserved
- [ ] CLI data commands work identically with ServiceOrchestrator integration
- [ ] DataLoadingJob (previously DataJob) integrates with ServiceOrchestrator cancellation

**Implementation Details**:
```python
# File: ktrdr/data/data_manager.py (enhance existing ServiceOrchestrator usage)

class DataManager(ServiceOrchestrator):
    """Enhanced to leverage ServiceOrchestrator cancellation patterns."""
    
    async def load_data(
        self,
        symbol: str,
        timeframe: str,
        mode: str = "tail",
        max_retries: int = 3,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> pd.DataFrame:
        """Load data using ServiceOrchestrator cancellation patterns."""
        
        # Use ServiceOrchestrator.execute_with_cancellation() instead of custom patterns
        return await self.execute_with_cancellation(
            operation=self._load_data_operation(
                symbol=symbol,
                timeframe=timeframe,
                mode=mode,
                max_retries=max_retries,
                progress_callback=progress_callback,
                **kwargs
            ),
            operation_name=f"Loading {symbol} {timeframe} data"
        )
    
    async def _load_data_operation(self, symbol: str, timeframe: str, mode: str, 
                                 max_retries: int, progress_callback, **kwargs) -> pd.DataFrame:
        """Core data loading operation with ServiceOrchestrator cancellation integration."""
        
        # Create DataLoadingJob with ServiceOrchestrator cancellation support
        job = DataLoadingJob(
            operation_id=self._generate_operation_id(),
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            max_retries=max_retries,
            cancellation_token=self.get_current_cancellation_token()  # From ServiceOrchestrator
        )
        
        # Use existing DataJobManager but with ServiceOrchestrator integration
        return await self.data_job_manager.execute_job(job)
    
    # All existing methods preserved, enhanced with ServiceOrchestrator patterns
```

**Testing Requirements**:
- [ ] ALL existing DataManager tests pass without modification
- [ ] ServiceOrchestrator cancellation integration working
- [ ] CLI data commands show no behavior changes
- [ ] DataLoadingJob cancellation works through ServiceOrchestrator
- [ ] Performance regression testing
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] Enhanced `ktrdr/data/data_manager.py` using ServiceOrchestrator cancellation
- [ ] `tests/unit/data/test_data_manager_cancellation.py` enhanced test suite
- [ ] Backward compatibility validation
- [ ] ServiceOrchestrator integration validation
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.3: Create Unified Cancellation Interface
**Day**: 3  
**Assignee**: AI IDE Agent  
**Priority**: 8  
**Depends on**: Task 2.1, Task 2.2 (Note: Task 2.2 TrainingManager moved to Slice 3)

**Description**: Create a unified cancellation coordinator that bridges ServiceOrchestrator patterns with AsyncDataLoader patterns and CLI KeyboardInterrupt handling, ensuring consistent cancellation behavior across all operation types.

**Acceptance Criteria**:
- [ ] Unified interface works with ServiceOrchestrator.execute_with_cancellation()
- [ ] Bridge AsyncDataLoader job cancellation with ServiceOrchestrator patterns
- [ ] CLI KeyboardInterrupt properly cancels both data operations (training in Slice 3)
- [ ] CancellationToken protocol consistent across all domains
- [ ] Cancellation state management thread-safe and reliable

**Implementation Details**:
```python
# File: ktrdr/async/cancellation.py (unified interface)

import signal
import asyncio
from typing import Optional, Callable, Any
from ktrdr.async.operations import CancellationToken, OperationCancelledException

class CancellationCoordinator:
    """Unified cancellation coordinator for all operation types."""
    
    def __init__(self):
        self._global_cancellation = asyncio.Event()
        self._operation_tokens: dict[str, CancellationToken] = {}
        self._cli_handlers_registered = False
    
    def create_token(self, operation_id: str) -> CancellationToken:
        """Create cancellation token for operation."""
        token = AsyncCancellationToken(operation_id)
        self._operation_tokens[operation_id] = token
        return token
    
    def register_cli_handlers(self):
        """Register CLI KeyboardInterrupt handlers."""
        if not self._cli_handlers_registered:
            signal.signal(signal.SIGINT, self._handle_keyboard_interrupt)
            self._cli_handlers_registered = True
    
    def _handle_keyboard_interrupt(self, signum, frame):
        """Handle Ctrl+C by cancelling all operations."""
        logger.info("KeyboardInterrupt received, cancelling all operations...")
        self.cancel_all_operations("User requested cancellation (Ctrl+C)")
    
    def cancel_all_operations(self, reason: str = "Global cancellation"):
        """Cancel all registered operations."""
        self._global_cancellation.set()
        for token in self._operation_tokens.values():
            token.cancel(reason)
    
    async def execute_with_unified_cancellation(self,
                                              operation_id: str,
                                              operation_func: Callable,
                                              operation_name: str) -> Any:
        """Execute operation with unified cancellation support."""
        
        token = self.create_token(operation_id)
        
        try:
            # Check global cancellation
            if self._global_cancellation.is_set():
                raise OperationCancelledException(f"Global cancellation active for {operation_name}")
            
            # Execute with cancellation checking
            return await operation_func(token)
            
        finally:
            # Cleanup
            self._operation_tokens.pop(operation_id, None)

# Global coordinator instance
cancellation_coordinator = CancellationCoordinator()

class AsyncCancellationToken:
    """Async cancellation token implementation."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self._cancelled = asyncio.Event()
        self._reason: Optional[str] = None
    
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()
    
    def cancel(self, reason: str = "Operation cancelled") -> None:
        self._reason = reason
        self._cancelled.set()
    
    async def wait_for_cancellation(self) -> None:
        await self._cancelled.wait()
    
    def check_cancellation(self, context: str = "") -> None:
        """Check cancellation and raise exception if cancelled."""
        if self.is_cancelled():
            raise OperationCancelledException(f"Operation cancelled: {context} ({self._reason})")
    
    @property
    def reason(self) -> Optional[str]:
        return self._reason
```

**Testing Requirements**:
- [ ] Unified cancellation interface working across all components
- [ ] CLI KeyboardInterrupt cancellation working for data operations
- [ ] ServiceOrchestrator integration seamless
- [ ] CancellationToken protocol consistency validated
- [ ] Thread safety under concurrent cancellation requests
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/async/cancellation.py` with unified interface
- [ ] `tests/unit/async/test_cancellation.py` comprehensive test suite
- [ ] CLI cancellation integration for all operation types
- [ ] ServiceOrchestrator bridge implementation
- [ ] Global cancellation coordinator
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.4: Create Unified Cancellation Interface
**Day**: 4  
**Assignee**: AI IDE Agent  
**Priority**: 8  
**Depends on**: Task 2.3

**Description**: Create a unified interface that bridges all existing cancellation patterns (CancellationToken protocol, asyncio.Event, hasattr() checking) while preserving compatibility with existing implementations.

**Acceptance Criteria**:
- [ ] Unified interface supports all existing cancellation checking patterns
- [ ] Backward compatibility with current AsyncDataLoader implementations
- [ ] Integration with ServiceOrchestrator.execute_with_cancellation()
- [ ] CLI KeyboardInterrupt properly routes through unified interface
- [ ] Performance equivalent to existing direct cancellation checks

**Implementation Details**:
```python
# File: ktrdr/async/cancellation_bridge.py

class CancellationBridge:
    """Bridge different cancellation patterns into unified interface."""
    
    @staticmethod
    def check_any_cancellation(*cancellation_sources) -> bool:
        """Check cancellation from multiple sources."""
        for source in cancellation_sources:
            if CancellationBridge._is_cancelled(source):
                return True
        return False
    
    @staticmethod
    def _is_cancelled(source) -> bool:
        """Check cancellation from any source type."""
        # CancellationToken protocol
        if hasattr(source, 'is_cancelled'):
            return source.is_cancelled()
        
        # asyncio.Event
        if hasattr(source, 'is_set'):
            return source.is_set()
        
        # Boolean flag
        if isinstance(source, bool):
            return source
        
        # None/missing source
        return False
    
    @staticmethod
    def create_unified_token(*sources) -> 'UnifiedCancellationToken':
        """Create unified token from multiple sources."""
        return UnifiedCancellationToken(sources)

class UnifiedCancellationToken:
    """Unified token that aggregates multiple cancellation sources."""
    
    def __init__(self, sources):
        self.sources = sources
    
    def is_cancelled(self) -> bool:
        return CancellationBridge.check_any_cancellation(*self.sources)
    
    def cancel(self, reason: str = "Unified cancellation") -> None:
        """Cancel all sources that support cancellation."""
        for source in self.sources:
            if hasattr(source, 'cancel'):
                source.cancel(reason)
            elif hasattr(source, 'set'):
                source.set()
```

**Testing Requirements**:
- [ ] All existing cancellation patterns supported
- [ ] Backward compatibility with AsyncDataLoader maintained
- [ ] Integration with ServiceOrchestrator working
- [ ] Performance benchmarking shows no regression
- [ ] Bridge pattern handles all existing source types
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/async/cancellation_bridge.py` with bridge implementations
- [ ] `tests/unit/async/test_cancellation_bridge.py` compatibility test suite
- [ ] Performance benchmark validation
- [ ] Backward compatibility verification
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.5: Create DataJobManager with ServiceOrchestrator Integration
**Day**: 5  
**Assignee**: AI IDE Agent  
**Priority**: 8  
**Depends on**: Task 2.4

**Description**: Rename and enhance AsyncDataLoader to DataJobManager, integrating it with ServiceOrchestrator.execute_with_cancellation() while preserving all existing job management capabilities and adding unified cancellation support.

**Acceptance Criteria**:
- [ ] AsyncDataLoader renamed to DataJobManager
- [ ] DataJobManager uses ServiceOrchestrator.execute_with_cancellation() for job execution
- [ ] DataJob renamed to DataLoadingJob with CancellationToken protocol
- [ ] All existing job management capabilities preserved
- [ ] Unified cancellation interface working for both ServiceOrchestrator and job operations

**Implementation Details**:
```python
# File: ktrdr/data/components/data_job_manager.py (renamed from async_data_loader.py)

from ktrdr.async.cancellation import CancellationToken, AsyncCancellationToken
from ktrdr.managers import ServiceOrchestrator

class DataJobManager:
    """
    Job manager for data operations with ServiceOrchestrator integration.
    
    Renamed from AsyncDataLoader, enhanced with unified cancellation.
    """
    
    def __init__(self, service_orchestrator: ServiceOrchestrator):
        self.service_orchestrator = service_orchestrator
        # Preserve all existing AsyncDataLoader initialization
    
    async def execute_job(self, job: 'DataLoadingJob') -> pd.DataFrame:
        """Execute job using ServiceOrchestrator cancellation patterns."""
        
        # Bridge job cancellation with ServiceOrchestrator
        return await self.service_orchestrator.execute_with_cancellation(
            operation=self._execute_job_operation(job),
            operation_name=f"Data job: {job.symbol} {job.timeframe}"
        )
    
    async def _execute_job_operation(self, job: 'DataLoadingJob') -> pd.DataFrame:
        """Core job execution with cancellation integration."""
        # Preserve all existing AsyncDataLoader job execution logic
        # Enhanced with unified CancellationToken support
        pass

@dataclass  
class DataLoadingJob:
    """
    Data loading job with CancellationToken protocol support.
    
    Renamed from DataJob, enhanced with unified cancellation.
    """
    
    operation_id: str
    symbol: str
    timeframe: str
    mode: str
    max_retries: int
    cancellation_token: CancellationToken
    
    # Preserve all existing DataJob fields and methods
    # Add CancellationToken protocol implementation
    
    def is_cancelled(self) -> bool:
        return self.cancellation_token.is_cancelled()
    
    def cancel(self, reason: str = "Job cancelled") -> None:
        self.cancellation_token.cancel(reason)
```

**Testing Requirements**:
- [ ] All existing AsyncDataLoader functionality preserved in DataJobManager
- [ ] ServiceOrchestrator cancellation integration working
- [ ] DataLoadingJob cancellation working through unified interface
- [ ] Job execution performance maintained
- [ ] All existing tests pass with new names
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/data/components/data_job_manager.py` (renamed and enhanced)
- [ ] `tests/unit/data/components/test_data_job_manager.py` comprehensive test suite
- [ ] DataLoadingJob with CancellationToken protocol
- [ ] ServiceOrchestrator integration validation
- [ ] Migration guide for naming changes
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.6: Validate Complete Data Cancellation Unification
**Day**: 6  
**Assignee**: AI IDE Agent  
**Priority**: 10  
**Depends on**: Task 2.5

**Description**: Comprehensive validation that data cancellation patterns are unified across ServiceOrchestrator, job management, and CLI operations, with DataManager using consistent cancellation infrastructure. (Training validation moved to Slice 3)

**Acceptance Criteria**:
- [ ] DataManager uses ServiceOrchestrator.execute_with_cancellation() consistently
- [ ] DataJobManager integrates seamlessly with ServiceOrchestrator cancellation
- [ ] CLI KeyboardInterrupt cancels data operations through unified interface
- [ ] All existing data functionality preserved with enhanced cancellation capabilities
- [ ] CancellationToken protocol working across all data operation types
- [ ] Foundation ready for training system integration in Slice 3

**Testing Strategy**:
1. **Unified Data Cancellation Testing**: All data operations cancelable through same interface
2. **CLI Integration Testing**: KeyboardInterrupt cancellation for data operations
3. **ServiceOrchestrator Testing**: Consistent patterns for DataManager
4. **Job Integration Testing**: DataJobManager cancellation through ServiceOrchestrator
5. **Regression Testing**: All existing data functionality preserved

**Testing Requirements**:
- [ ] Data cancellation working consistently across all data operations
- [ ] CLI data commands cancelable with Ctrl+C
- [ ] ServiceOrchestrator data cancellation patterns consistent
- [ ] Job-based data operations integrate with unified cancellation
- [ ] All existing data tests pass
- [ ] Foundation ready for training integration (Slice 3)
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] Complete data cancellation unification validation report
- [ ] Unified cancellation interface working across all data components
- [ ] Enhanced CLI cancellation experience for data operations
- [ ] Consistent ServiceOrchestrator usage for DataManager
- [ ] Foundation documentation for Slice 3 training integration
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

## Integration Points for Future Slices

### Slice 3 Integration Readiness
- [ ] CancellationToken protocol established and proven with data operations
- [ ] ServiceOrchestrator cancellation patterns validated and consistent
- [ ] Unified cancellation interface ready for training system integration
- [ ] CLI cancellation framework established for all operation types
- [ ] DataJobManager patterns available for TrainingJobManager implementation

### Slice 4 Integration Readiness
- [ ] Generic operation management patterns ready for host service integration
- [ ] Unified cancellation working across all local operations
- [ ] ServiceOrchestrator patterns established for both data and training (after Slice 3)

## Success Metrics

### Functional Metrics
- [ ] 100% existing data functionality preserved with enhanced cancellation
- [ ] ServiceOrchestrator cancellation patterns consistent across DataManager
- [ ] CLI KeyboardInterrupt cancellation working for all data operations
- [ ] DataJobManager (renamed AsyncDataLoader) integrated with ServiceOrchestrator

### Quality Metrics  
- [ ] >95% code coverage for new cancellation infrastructure
- [ ] <5% performance impact on data operations
- [ ] Thread safety validated under concurrent cancellation requests
- [ ] Clean separation between generic cancellation and data-specific logic

### Integration Metrics
- [ ] CancellationToken protocol ready for training system integration
- [ ] ServiceOrchestrator patterns proven and documented for Slice 3
- [ ] Unified cancellation interface working across all data components
- [ ] Foundation established for complete system cancellation unification

## Risk Mitigation

### Technical Risks
- **Risk**: Breaking existing data cancellation functionality
- **Mitigation**: Comprehensive feature mapping and extensive regression testing

- **Risk**: Performance degradation from cancellation abstraction layer
- **Mitigation**: Lightweight implementation with performance benchmarking

- **Risk**: Thread safety issues with concurrent cancellation requests
- **Mitigation**: RLock usage and concurrent testing validation

### Integration Risks
- **Risk**: Complex integration with existing DataManager ServiceOrchestrator usage
- **Mitigation**: Incremental enhancement with step-by-step validation

- **Risk**: Breaking CLI cancellation behavior for data operations
- **Mitigation**: Extensive CLI integration testing and behavior preservation

### Compatibility Risks
- **Risk**: AsyncDataLoader → DataJobManager naming changes causing integration issues
- **Mitigation**: Gradual migration with backward compatibility aliases

- **Risk**: CancellationToken protocol incompatible with existing patterns
- **Mitigation**: Bridge pattern implementation and compatibility validation

## Notes

This slice establishes the foundation for unified cancellation across the entire KTRDR system by focusing on data operations first. The proven AsyncDataLoader cancellation patterns are extracted into reusable components, and ServiceOrchestrator cancellation is made consistent across all data operations.

The focus on data operations first (with training moved to Slice 3) ensures we have a solid, proven foundation before extending the same patterns to training operations. This vertical slice approach delivers working improvements for data operations immediately while setting up the infrastructure for training integration.