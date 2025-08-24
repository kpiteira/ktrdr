# Phase 1: DataManager Decomposition Foundation
**Duration**: 3 weeks  
**Goal**: Begin breaking down DataManager while maintaining and improving functionality

## Branching Strategy

### Main Branches
- **Main branch**: `main` (protected, requires PR reviews)
- **Feature branch**: `feature/datamanager-decomposition-phase1` (created from `main`)
- **Task branches**: Created from feature branch for each atomic task

### Branch Naming Convention
- Task branches: `task/1.1a-create-progress-manager`, `task/1.1b-integrate-progress-manager`, etc.
- PR branches: Use task branch names
- Hotfix branches: `hotfix/critical-fix-description`

### PR Strategy
- **Component PRs**: Each atomic task gets its own PR to feature branch
- **Integration PRs**: Feature branch merged to main after phase completion
- **Review requirements**: All PRs require code review and passing tests

## Phase 1 Success Criteria
- DataManager complexity reduced by extracting first components
- All existing tests continue to pass
- New components are fully tested and integrated
- Performance maintained or improved
- Clear foundation for further decomposition

---

## Task 1.1a: Create ProgressManager Component

### Branch Info
- **Branch**: `task/1.1a-create-progress-manager`
- **Created from**: `feature/datamanager-decomposition-phase1`
- **PR Target**: `feature/datamanager-decomposition-phase1`

### Priority: High
### Type: Create new component
### Estimated Time: 4-6 hours

### Description
Create the ProgressManager component by analyzing and extracting progress reporting patterns from the current DataManager. This component will handle all progress tracking, callbacks, and state management for data loading operations.

### Technical Context
The current DataManager has progress reporting logic scattered throughout multiple methods:
- `load_data()` - Main progress reporting for data loading
- `load_multi_timeframe_data()` - Progress for batch operations  
- `_load_with_fallback()` - Segment-level progress tracking
- Various internal methods that update progress callbacks

The progress system uses:
- `DataLoadingProgress` dataclass for state
- Callback functions for UI updates
- Thread-safe progress updates during concurrent operations

### Detailed Implementation Steps

#### Step 1: Analyze Current Progress Patterns (1 hour)
**Location**: Study `ktrdr/data/data_manager.py` lines ~300-400, ~800-900, ~1200-1400

**Tasks**:
1. Document all current progress callback usage patterns
2. Identify all places where `DataLoadingProgress` is created/updated
3. Map out the progress reporting flow through different methods
4. Note threading concerns and concurrent access patterns

**Expected Findings**:
- Progress callbacks used in ~8-10 methods
- DataLoadingProgress updated at segment, gap, and overall operation levels
- Some progress updates happen in concurrent contexts
- Progress includes percentage, current step, items processed/total

#### Step 2: Design ProgressManager Interface (1 hour)
**Location**: Create design document or code comments

**Interface Requirements**:
```python
class ProgressManager:
    def __init__(self, callback: Optional[Callable] = None)
    def start_operation(self, total_steps: int, operation_name: str)
    def start_step(self, step_name: str, step_number: int)
    def update_step_progress(self, current: int, total: int, detail: str = "")
    def complete_step(self)
    def complete_operation(self)
    def set_cancellation_token(self, token: Any)
    def check_cancelled(self) -> bool
    def get_progress_state(self) -> DataLoadingProgress
```

**Threading Requirements**:
- Thread-safe progress state updates
- Safe callback invocation from any thread
- Atomic operations for progress calculations

#### Step 3: Implement ProgressManager Component (2-3 hours)
**Location**: `ktrdr/data/components/progress_manager.py`

**Implementation Details**:

```python
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProgressState:
    """Thread-safe progress state container."""
    # Overall operation progress
    operation_name: str = ""
    overall_percentage: float = 0.0
    
    # Step tracking
    current_step: str = "Initializing"
    step_number: int = 0
    total_steps: int = 0
    step_percentage: float = 0.0
    
    # Item tracking within steps
    items_processed: int = 0
    items_total: int = 0
    current_item_detail: str = ""
    
    # Timing
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Cancellation
    is_cancelled: bool = False
    cancellation_reason: str = ""

class ProgressManager:
    """Thread-safe progress manager for data loading operations."""
    
    def __init__(self, callback: Optional[Callable[[ProgressState], None]] = None):
        self._state = ProgressState()
        self._callback = callback
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._cancellation_token = None
        
    def start_operation(self, total_steps: int, operation_name: str = "Data Operation"):
        """Initialize a new operation with specified steps."""
        with self._lock:
            self._state = ProgressState(
                operation_name=operation_name,
                total_steps=total_steps,
                start_time=datetime.now()
            )
            logger.info(f"Started operation '{operation_name}' with {total_steps} steps")
            self._notify_callback()
    
    def start_step(self, step_name: str, step_number: int):
        """Begin a new step in the operation."""
        with self._lock:
            if step_number > self._state.total_steps:
                logger.warning(f"Step {step_number} exceeds total steps {self._state.total_steps}")
            
            self._state.current_step = step_name
            self._state.step_number = step_number
            self._state.step_percentage = 0.0
            self._state.items_processed = 0
            self._state.items_total = 0
            self._state.current_item_detail = ""
            
            # Update overall percentage based on completed steps
            if self._state.total_steps > 0:
                self._state.overall_percentage = ((step_number - 1) / self._state.total_steps) * 100
            
            logger.debug(f"Started step {step_number}/{self._state.total_steps}: {step_name}")
            self._notify_callback()
    
    def update_step_progress(self, current: int, total: int, detail: str = ""):
        """Update progress within the current step."""
        with self._lock:
            self._state.items_processed = current
            self._state.items_total = total
            self._state.current_item_detail = detail
            
            # Calculate step percentage
            if total > 0:
                self._state.step_percentage = (current / total) * 100
                
                # Update overall percentage (completed steps + current step progress)
                if self._state.total_steps > 0:
                    completed_steps_pct = ((self._state.step_number - 1) / self._state.total_steps) * 100
                    current_step_pct = (self._state.step_percentage / self._state.total_steps)
                    self._state.overall_percentage = completed_steps_pct + current_step_pct
            
            # Estimate completion time based on current progress
            self._update_time_estimate()
            
            self._notify_callback()
    
    def complete_step(self):
        """Mark the current step as completed."""
        with self._lock:
            self._state.step_percentage = 100.0
            if self._state.total_steps > 0:
                self._state.overall_percentage = (self._state.step_number / self._state.total_steps) * 100
            
            logger.debug(f"Completed step {self._state.step_number}: {self._state.current_step}")
            self._notify_callback()
    
    def complete_operation(self):
        """Mark the entire operation as completed."""
        with self._lock:
            self._state.overall_percentage = 100.0
            self._state.step_percentage = 100.0
            self._state.current_step = "Completed"
            
            logger.info(f"Completed operation '{self._state.operation_name}'")
            self._notify_callback()
    
    def set_cancellation_token(self, token: Any):
        """Set a cancellation token for the operation."""
        with self._lock:
            self._cancellation_token = token
    
    def check_cancelled(self) -> bool:
        """Check if the operation has been cancelled."""
        with self._lock:
            # Check our internal cancellation state
            if self._state.is_cancelled:
                return True
            
            # Check external cancellation token if provided
            if self._cancellation_token:
                if hasattr(self._cancellation_token, 'is_cancelled'):
                    return self._cancellation_token.is_cancelled
                elif hasattr(self._cancellation_token, 'cancelled'):
                    return self._cancellation_token.cancelled()
            
            return False
    
    def cancel_operation(self, reason: str = "User requested cancellation"):
        """Cancel the current operation."""
        with self._lock:
            self._state.is_cancelled = True
            self._state.cancellation_reason = reason
            logger.info(f"Operation cancelled: {reason}")
            self._notify_callback()
    
    def get_progress_state(self) -> ProgressState:
        """Get a copy of the current progress state."""
        with self._lock:
            # Return a copy to prevent external modification
            return ProgressState(
                operation_name=self._state.operation_name,
                overall_percentage=self._state.overall_percentage,
                current_step=self._state.current_step,
                step_number=self._state.step_number,
                total_steps=self._state.total_steps,
                step_percentage=self._state.step_percentage,
                items_processed=self._state.items_processed,
                items_total=self._state.items_total,
                current_item_detail=self._state.current_item_detail,
                start_time=self._state.start_time,
                estimated_completion=self._state.estimated_completion,
                is_cancelled=self._state.is_cancelled,
                cancellation_reason=self._state.cancellation_reason
            )
    
    def _update_time_estimate(self):
        """Calculate estimated completion time based on current progress."""
        if not self._state.start_time or self._state.overall_percentage <= 0:
            return
        
        elapsed = datetime.now() - self._state.start_time
        if self._state.overall_percentage > 0:
            total_estimated_seconds = (elapsed.total_seconds() * 100) / self._state.overall_percentage
            remaining_seconds = total_estimated_seconds - elapsed.total_seconds()
            
            if remaining_seconds > 0:
                self._state.estimated_completion = datetime.now() + \
                    datetime.timedelta(seconds=remaining_seconds)
    
    def _notify_callback(self):
        """Safely invoke the progress callback."""
        if self._callback:
            try:
                self._callback(self.get_progress_state())
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
                # Don't re-raise - progress updates shouldn't break the main operation
```

**Key Implementation Features**:
1. **Thread Safety**: Uses RLock for reentrant locking
2. **State Isolation**: Returns copies of state to prevent external modification
3. **Robust Error Handling**: Callback errors don't break progress tracking
4. **Time Estimation**: Calculates estimated completion times
5. **Cancellation Support**: Multiple ways to check/trigger cancellation
6. **Comprehensive Logging**: Debug and info logging for troubleshooting

#### Step 4: Test-Driven Development Implementation (2-3 hours)
**Location**: `tests/unit/data/components/test_progress_manager.py`

### TDD Approach: Write Failing Tests First

**Phase 1: Write Failing Tests (30 minutes)**
Define the exact behavior we want ProgressManager to have through comprehensive tests:

**Test Categories to Implement**:

1. **Interface Tests**: Verify ProgressManager initializes correctly, has required methods (`start_operation`, `start_step`, `update_step_progress`, `complete_step`, `get_progress_state`), and provides the expected ProgressState interface.

2. **Progress Calculation Tests**: Validate that percentage calculations are accurate across multiple steps, handle step transitions correctly, and calculate overall progress properly when steps have different completion times.

3. **Threading Safety Tests**: Ensure concurrent access from multiple threads doesn't corrupt state, callback invocation is thread-safe, and state consistency is maintained under concurrent updates.

4. **Cancellation Tests**: Verify internal cancellation mechanisms work, external cancellation tokens are respected, and cancellation state is properly propagated through all progress updates.

5. **Callback Integration Tests**: Test that callbacks are invoked with correct ProgressState objects, callback errors don't break progress tracking, and multiple callback scenarios work correctly.

6. **Time Estimation Tests**: Validate that completion time estimates are calculated reasonably, estimates improve in accuracy over time, and edge cases (very fast/slow operations) are handled.

7. **Edge Case Tests**: Handle zero total items gracefully, manage negative progress values appropriately, cope with progress beyond 100%, and prevent NaN values in calculations.

**Sample Test Structure**:
```python
def test_progress_calculation_accuracy(self):
    """Test: Multi-step progress calculations should be mathematically correct."""
    # Test that 4 steps with step 1 at 50% completion = 12.5% overall
    # Verify monotonic progress (never goes backwards)
    # Confirm 100% completion at operation end
```

**Phase 2: Run Tests and Verify Failures (5 minutes)**
```bash
uv run pytest tests/unit/data/components/test_progress_manager.py -v
```
Expected result: All tests fail because ProgressManager doesn't exist yet.

**Phase 3: Implement Minimal ProgressManager (1.5-2 hours)**
Create the simplest implementation that makes all tests pass:
- Focus on core interface first
- Add thread safety with proper locking
- Implement callback mechanism
- Handle edge cases as defined by tests
- Don't add features not required by tests

**Phase 4: Run Tests Until They Pass (30 minutes)**
Iteratively fix implementation guided by failing tests:
```bash
# Fix one test at a time
uv run pytest tests/unit/data/components/test_progress_manager.py::test_initialization -v
# Continue until all pass
```

### TDD Benefits for Task 1.1a
1. **Clear Requirements**: Tests define exact behavior before implementation
2. **No Over-Engineering**: Build only what's needed to pass tests  
3. **Regression Prevention**: Future changes must keep tests passing
4. **Design Validation**: Tests verify the API is usable
5. **Documentation**: Tests serve as executable specifications

### Quality Assurance Requirements
**All tasks must pass these quality checks before PR submission**:

```bash
# Code formatting
uv run black ktrdr/data/components/progress_manager.py tests/unit/data/components/test_progress_manager.py

# Linting  
uv run ruff check ktrdr/data/components/progress_manager.py tests/unit/data/components/test_progress_manager.py

# Type checking
uv run mypy ktrdr/data/components/progress_manager.py

# Security scanning
uv run bandit -r ktrdr/data/components/progress_manager.py

# Test execution with coverage
uv run pytest tests/unit/data/components/test_progress_manager.py --cov=ktrdr.data.components.progress_manager --cov-report=html --cov-fail-under=95
```

**Quality Gates**:
- All tests must pass
- Code coverage ≥95%
- No MyPy errors
- No Ruff violations
- No Bandit security issues
- Black formatting applied


### Acceptance Criteria
- [ ] ProgressManager handles all current DataManager progress patterns
- [ ] Thread-safe progress state management implemented
- [ ] Compatible interface with existing progress callback system
- [ ] Component can be instantiated and used independently
- [ ] >95% test coverage achieved
- [ ] All tests pass in concurrent scenarios
- [ ] Proper error handling for callback failures
- [ ] Time estimation functionality works correctly
- [ ] Cancellation mechanisms function properly

### Deliverables
- [ ] `ktrdr/data/components/progress_manager.py` with complete implementation
- [ ] `tests/unit/data/components/test_progress_manager.py` with >95% coverage
- [ ] Documentation of progress patterns found in current DataManager
- [ ] Design document or code comments explaining interface decisions

### Testing Instructions
```bash
# Run unit tests
uv run pytest tests/unit/data/components/test_progress_manager.py -v

# Run with coverage
uv run pytest tests/unit/data/components/test_progress_manager.py --cov=ktrdr.data.components.progress_manager --cov-report=html

# Run threading stress tests
uv run pytest tests/unit/data/components/test_progress_manager.py::TestProgressManager::test_thread_safety -v --count=10
```

### PR Requirements
- [ ] All tests pass
- [ ] Code coverage >95%
- [ ] Code review by at least 1 reviewer
- [ ] No regression in existing functionality
- [ ] Clear commit messages explaining implementation choices

### Notes for Reviewer
- Focus on thread safety implementation
- Verify callback error handling doesn't break progress tracking
- Check time estimation accuracy and edge cases
- Ensure interface is flexible enough for current DataManager usage patterns

---

## Task 1.1b: Integrate ProgressManager into DataManager

### Branch Info
- **Branch**: `task/1.1b-integrate-progress-manager`
- **Created from**: `feature/datamanager-decomposition-phase1` (after Task 1.1a merged)
- **PR Target**: `feature/datamanager-decomposition-phase1`

### Priority: High
### Type: Integration
### Depends on: Task 1.1a
### Estimated Time: 6-8 hours

### Description
Replace embedded progress logic in DataManager with ProgressManager instance while maintaining exact backward compatibility with existing progress callback behavior.

### Technical Context
The current DataManager creates and manages DataLoadingProgress objects directly in multiple methods. This integration will:
1. Replace direct progress management with ProgressManager usage
2. Maintain existing callback signatures and behavior
3. Preserve all current progress reporting functionality
4. Ensure no performance regression

### Pre-Integration Analysis Required

#### Step 1: Map Current Progress Usage (1-2 hours)
**Location**: `ktrdr/data/data_manager.py`

**Tasks**:
1. Document every location where progress is currently managed:
   ```python
   # Example locations to document:
   # Line ~350: progress = DataLoadingProgress()
   # Line ~380: progress.items_processed = segments_completed
   # Line ~420: progress_callback(progress) if progress_callback
   ```

2. Create mapping document showing:
   - Current method signature for progress callbacks
   - Expected DataLoadingProgress fields in each context
   - Threading context for each progress update
   - Performance-critical progress update locations

3. Identify integration points that need careful handling:
   - Methods that create multiple progress instances
   - Concurrent progress updates during segment fetching
   - Progress state that persists across method calls

### Detailed Implementation Steps

#### Step 2: Create Compatibility Layer (2 hours)
**Location**: Update `ktrdr/data/data_manager.py`

Since existing code expects `DataLoadingProgress` objects but ProgressManager uses `ProgressState`, create a compatibility layer:

```python
# Add to DataManager class
def _create_legacy_progress(self, progress_state: ProgressState) -> DataLoadingProgress:
    """Convert ProgressState to DataLoadingProgress for backward compatibility."""
    return DataLoadingProgress(
        items_processed=progress_state.items_processed,
        items_total=progress_state.items_total,
        percentage=progress_state.overall_percentage,
        current_step=progress_state.current_step,
        estimated_completion=progress_state.estimated_completion,
        # Map other fields as needed
    )

def _progress_callback_wrapper(self, progress_state: ProgressState):
    """Wrap ProgressState in legacy format for existing callbacks."""
    if self._original_progress_callback:
        legacy_progress = self._create_legacy_progress(progress_state)
        self._original_progress_callback(legacy_progress)
```

#### Step 3: Update DataManager Constructor (30 minutes)
**Location**: `DataManager.__init__()` method

```python
def __init__(self, ...):
    # Existing initialization
    super().__init__()
    
    # Store original callback for compatibility
    self._original_progress_callback = None
    
    # Initialize ProgressManager (will be configured per operation)
    self._progress_manager = None
```

#### Step 4: Update Primary Data Loading Methods (2-3 hours)
**Location**: Methods like `load_data()`, `load_multi_timeframe_data()`

**For `load_data()` method**:
```python
async def load_data(
    self,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    source: str = "ib",
    mode: str = "local",
    progress_callback: Optional[Callable[[DataLoadingProgress], None]] = None,
    cancellation_token: Optional[Any] = None
) -> pd.DataFrame:
    """Load data with ProgressManager integration."""
    
    # Store callback for compatibility wrapper
    self._original_progress_callback = progress_callback
    
    # Create ProgressManager for this operation
    self._progress_manager = ProgressManager(
        callback=self._progress_callback_wrapper if progress_callback else None
    )
    
    # Set cancellation token if provided
    if cancellation_token:
        self._progress_manager.set_cancellation_token(cancellation_token)
    
    # Determine total steps based on mode
    total_steps = self._calculate_total_steps(mode, source)
    self._progress_manager.start_operation(total_steps, f"Loading {symbol} {timeframe} data")
    
    try:
        # Step 1: Load local data (if applicable)
        if mode != "remote_only":  # Example condition
            self._progress_manager.start_step("Loading local data", 1)
            local_data = await self._load_local_data_with_progress(symbol, timeframe)
            self._progress_manager.complete_step()
        
        # Step 2: Analyze gaps (if needed)
        if mode in ["tail", "backfill", "full"]:
            self._progress_manager.start_step("Analyzing data gaps", 2)
            gaps = await self._analyze_gaps_with_progress(local_data, start_date, end_date, mode)
            self._progress_manager.complete_step()
        
        # Continue with other steps...
        
        self._progress_manager.complete_operation()
        return final_data
        
    except Exception as e:
        self._progress_manager.cancel_operation(f"Error: {str(e)}")
        raise
    finally:
        # Clean up
        self._progress_manager = None
        self._original_progress_callback = None

def _calculate_total_steps(self, mode: str, source: str) -> int:
    """Calculate total steps based on operation parameters."""
    if mode == "local":
        return 2  # Load local + validate
    elif mode in ["tail", "backfill"]:
        return 5  # Load local + analyze gaps + segment + fetch + validate
    elif mode == "full":
        return 6  # Load local + analyze gaps + segment + fetch + merge + validate
    else:
        return 3  # Default case
```

#### Step 5: Update Internal Helper Methods (2-3 hours)
**Location**: Methods like `_load_with_fallback()`, `_fetch_segment_sync()`, etc.

Each internal method that currently does progress reporting needs to be updated:

```python
async def _load_with_fallback(self, symbol: str, timeframe: str, ...) -> pd.DataFrame:
    """Load data with fallback logic using ProgressManager."""
    
    # Check if we have an active progress manager
    if not self._progress_manager:
        # Fallback to old behavior for backward compatibility
        return await self._load_with_fallback_legacy(symbol, timeframe, ...)
    
    # Use ProgressManager for progress updates
    segments = self._create_segments(...)  # Existing logic
    
    # Update step progress as we process segments
    for i, segment in enumerate(segments):
        # Check for cancellation
        if self._progress_manager.check_cancelled():
            raise asyncio.CancelledError("Operation cancelled by user")
        
        self._progress_manager.update_step_progress(
            current=i,
            total=len(segments),
            detail=f"Fetching {segment.symbol} from {segment.start_date} to {segment.end_date}"
        )
        
        # Existing segment processing logic
        segment_data = await self._fetch_segment(segment)
        # ... process segment_data
    
    return combined_data
```

### Integration Testing Strategy

#### Step 6: Test-Driven Integration Development (2-3 hours)
**Location**: `tests/integration/data/test_datamanager_progress_integration.py`

### TDD Approach for Integration

**Phase 1: Write Failing Integration Tests First (45 minutes)**
Define the exact integration behavior we need before changing DataManager:

**Integration Test Categories**:

1. **Backward Compatibility Tests**: Ensure existing progress callback APIs work unchanged, verify DataLoadingProgress objects are still provided to callbacks, and confirm all existing progress-related tests continue to pass.

2. **Progress Step Description Tests**: Validate that progress steps have descriptive names (not generic "Step 1"), verify mode-specific step patterns, and ensure step descriptions include relevant context.

3. **Cancellation Integration Tests**: Test that cancellation works through ProgressManager, verify external cancellation tokens are respected, and confirm graceful cancellation with appropriate error messages.

4. **Performance Regression Tests**: Measure operation times with and without progress callbacks, ensure ProgressManager integration doesn't add significant overhead (< 20% slower), and validate memory usage remains stable.

5. **Concurrent Operation Tests**: Test multiple simultaneous data loading operations, verify each operation has independent progress tracking, and ensure thread safety in concurrent scenarios.

6. **Mode-Specific Progress Tests**: Validate different loading modes have different progress patterns, confirm mode-specific step counts and descriptions, and test all modes (local, tail, backfill, full).

7. **Error Scenario Tests**: Test progress reporting during error conditions, ensure progress never goes backwards during errors, and verify partial progress is reported before failures.

**Sample Integration Test Structure**:
```python
def test_backward_compatible_progress_callbacks(self):
    """Test: Existing callbacks must receive DataLoadingProgress objects unchanged."""
    # Verify callback signature remains the same
    # Check all required fields are present
    # Ensure progress progression is monotonic
```

**Phase 2: Run Tests and Verify Failures (5 minutes)**
```bash
uv run pytest tests/integration/data/test_datamanager_progress_integration.py -v
```
Expected result: Tests fail because DataManager isn't using ProgressManager yet.

**Phase 3: Implement DataManager Integration (2-2.5 hours)**
Guided by failing tests, implement:
- Add ProgressManager instance to DataManager
- Create compatibility wrapper for legacy callbacks
- Update load_data() to use ProgressManager steps
- Add mode-specific step calculations
- Implement cancellation integration

**Phase 4: Run Tests Until They Pass (30 minutes)**
Fix integration issues iteratively:
```bash
# Fix one test at a time
uv run pytest tests/integration/data/test_datamanager_progress_integration.py::test_backward_compatible_progress_callbacks -v
```

### TDD Integration Benefits
1. **Backward Compatibility Guaranteed**: Tests ensure no API changes
2. **Performance Regression Prevention**: Built-in performance benchmarks
3. **Error Scenario Coverage**: Edge cases tested from the start
4. **Mode-Specific Validation**: Each loading mode validated independently
5. **Concurrent Operation Safety**: Multi-threading issues caught early

### Quality Assurance Requirements  
**Integration tests must pass these quality checks**:

```bash
# Code formatting
uv run black ktrdr/data/data_manager.py tests/integration/data/test_datamanager_progress_integration.py

# Linting
uv run ruff check ktrdr/data/data_manager.py tests/integration/data/test_datamanager_progress_integration.py

# Type checking  
uv run mypy ktrdr/data/data_manager.py

# Security scanning
uv run bandit -r ktrdr/data/data_manager.py

# Integration test execution
uv run pytest tests/integration/data/test_datamanager_progress_integration.py -v --tb=short

# Full test suite regression check
uv run pytest tests/unit/data/test_data_manager.py -v
```

**Integration Quality Gates**:
- All integration tests pass
- All existing DataManager unit tests pass
- No MyPy errors in modified files
- No Ruff violations
- No Bandit security issues
- Performance tests show < 20% overhead

import asyncio
from ktrdr.data.data_manager import DataManager
from ktrdr.data.models import DataLoadingProgress

class TestDataManagerProgressIntegration:
    
    @pytest.fixture
    def data_manager(self):
        return DataManager()
    
    async def test_backward_compatible_progress_callback(self, data_manager):
        """Ensure existing progress callback behavior is preserved."""
        progress_updates = []
        
        def progress_callback(progress: DataLoadingProgress):
            # This should still receive DataLoadingProgress objects
            assert isinstance(progress, DataLoadingProgress)
            progress_updates.append(progress)
        
        # This should work exactly as before
        result = await data_manager.load_data(
            symbol="AAPL",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-01-10",
            progress_callback=progress_callback
        )
        
        # Verify we got progress updates
        assert len(progress_updates) > 0
        
        # Verify progress updates have expected fields
        for progress in progress_updates:
            assert hasattr(progress, 'percentage')
            assert hasattr(progress, 'current_step')
            assert hasattr(progress, 'items_processed')
            assert hasattr(progress, 'items_total')
        
        # Verify final progress shows completion
        assert progress_updates[-1].percentage == 100.0
    
    async def test_cancellation_integration(self, data_manager):
        """Test cancellation through ProgressManager."""
        class CancellationToken:
            def __init__(self):
                self.is_cancelled = False
        
        token = CancellationToken()
        
        # Start operation with cancellation token
        task = asyncio.create_task(
            data_manager.load_data(
                symbol="AAPL",
                timeframe="1m",  # More data to allow cancellation
                start_date="2024-01-01",
                end_date="2024-12-31",
                cancellation_token=token
            )
        )
        
        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        token.is_cancelled = True
        
        # Should raise cancellation error
        with pytest.raises(asyncio.CancelledError):
            await task
    
    async def test_no_performance_regression(self, data_manager, benchmark):
        """Ensure ProgressManager integration doesn't slow down operations."""
        
        def load_data_operation():
            return asyncio.run(
                data_manager.load_data(
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-01-05",
                    mode="local"  # Fast operation for benchmarking
                )
            )
        
        # Benchmark should be within 10% of baseline
        result = benchmark(load_data_operation)
        assert result is not None
```

### User Testing Points

#### When to Request User Testing
**After Task 1.1b PR is merged**, request user to test:

1. **CLI Command Testing**:
   ```bash
   # Test basic data loading with progress
   uv run ktrdr data show AAPL 1d --start 2024-01-01 --end 2024-01-10
   
   # Test with verbose progress
   uv run ktrdr data load MSFT 1h --start 2024-01-01 --end 2024-01-03 --verbose
   ```

2. **Progress Reporting Validation**:
   - Verify progress messages are still clear and informative
   - Check that progress percentages are accurate
   - Confirm cancellation (Ctrl+C) works properly

3. **Performance Validation**:
   - Compare operation times before/after integration
   - Check memory usage during large data loads
   - Verify no new error messages or warnings

#### User Testing Script
**Location**: `docs/testing/task-1.1b-user-testing.md`

```markdown
# Task 1.1b User Testing Script

## Test Scenarios

### Scenario 1: Basic Data Loading
1. Run: `uv run ktrdr data show AAPL 1d --start 2024-01-01 --end 2024-01-10`
2. Observe: Progress messages should appear and be informative
3. Expected: Same behavior as before, with clear progress updates

### Scenario 2: Long Operation with Cancellation
1. Run: `uv run ktrdr data load MSFT 1h --start 2023-01-01 --end 2023-12-31`
2. Wait for progress to start, then press Ctrl+C
3. Expected: Clean cancellation with appropriate message

### Scenario 3: Performance Comparison
1. Time a familiar data loading operation
2. Compare with previous performance
3. Expected: No significant performance regression

## Success Criteria
- [ ] All commands work as before
- [ ] Progress reporting is clear and accurate
- [ ] Cancellation works properly
- [ ] No performance regression
- [ ] No new error messages
```

### Acceptance Criteria
- [ ] All existing DataManager progress behavior unchanged
- [ ] ProgressManager used in `load_data`, `load_multi_timeframe_data`, and related methods
- [ ] All existing progress-related tests continue to pass
- [ ] No performance regression (within 5% of baseline)
- [ ] Backward compatibility with existing progress callback signatures maintained
- [ ] Cancellation functionality works through ProgressManager
- [ ] Memory usage remains stable
- [ ] Thread safety maintained in concurrent scenarios

### Deliverables
- [ ] DataManager using ProgressManager instead of embedded progress logic
- [ ] Integration tests validating backward compatibility
- [ ] Performance benchmark results
- [ ] User testing documentation and results
- [ ] Updated DataManager with clean progress management

### PR Requirements
- [ ] All existing tests pass
- [ ] New integration tests pass
- [ ] Performance benchmarks within acceptable range
- [ ] Code review by at least 1 reviewer
- [ ] User testing completed successfully
- [ ] Clear commit messages explaining integration approach

### Notes for Reviewer
- Pay special attention to backward compatibility
- Verify no changes to public API
- Check performance impact with realistic data sizes
- Ensure proper cleanup of ProgressManager instances
- Validate thread safety in concurrent scenarios

---

## Task 1.1c: Enhance Progress Reporting Capabilities

### Branch Info
- **Branch**: `task/1.1c-enhance-progress-capabilities`
- **Created from**: `feature/datamanager-decomposition-phase1` (after Task 1.1b merged)
- **PR Target**: `feature/datamanager-decomposition-phase1`

### Priority: Medium
### Type: Enhancement
### Depends on: Task 1.1b
### Estimated Time: 4-6 hours

### Description
Add enhanced progress reporting features using the new ProgressManager component, including better step descriptions, time estimates, and improved CLI progress display.

### Technical Context
Now that ProgressManager is integrated, we can add enhancements that weren't possible with the old embedded progress system:
1. More detailed step descriptions
2. Accurate time estimation
3. Better CLI progress visualization
4. Enhanced error reporting in progress messages

### Detailed Implementation Steps

#### Step 1: Enhance Step Descriptions (1-2 hours)
**Location**: `ktrdr/data/data_manager.py`

Update progress reporting to use more descriptive step names:

```python
# Before: Generic step names
self._progress_manager.start_step("Loading data", 1)

# After: Descriptive step names with context
self._progress_manager.start_step(f"Loading local {symbol} data from cache", 1)
self._progress_manager.start_step(f"Analyzing gaps in {symbol} {timeframe} data", 2)
self._progress_manager.start_step(f"Creating fetch segments for {len(gaps)} gaps", 3)
self._progress_manager.start_step(f"Fetching {total_segments} data segments from IB", 4)
```

#### Step 2: Add Time Estimation Display (1-2 hours)
**Location**: `ktrdr/cli/commands/data.py` (or wherever CLI progress is displayed)

Enhance CLI commands to show time estimates:

```python
def enhanced_progress_callback(progress_state: ProgressState):
    """Enhanced progress callback with time estimates."""
    # Existing progress display
    percentage = progress_state.overall_percentage
    step = progress_state.current_step
    
    # Add time estimation
    if progress_state.estimated_completion:
        remaining = progress_state.estimated_completion - datetime.now()
        remaining_str = f" (ETA: {remaining.total_seconds():.0f}s)"
    else:
        remaining_str = ""
    
    # Enhanced progress message
    if progress_state.current_item_detail:
        detail = f" - {progress_state.current_item_detail}"
    else:
        detail = ""
    
    print(f"\r{percentage:5.1f}% {step}{detail}{remaining_str}", end="", flush=True)
```

#### Step 3: User Testing Integration (1-2 hours)
**Location**: Create user testing documentation

**User Testing Points for Enhanced Features**:

After this task is complete, request user testing for:

1. **Enhanced Progress Messages**:
   ```bash
   # Test detailed step descriptions
   uv run ktrdr data load AAPL 1d --start 2024-01-01 --end 2024-01-31 --verbose
   ```
   - Verify step descriptions are more informative
   - Check that time estimates appear and are reasonable
   - Confirm progress detail messages are helpful

2. **Time Estimation Accuracy**:
   - Run longer operations and verify time estimates
   - Check that estimates improve over time
   - Validate estimates are shown in user-friendly format

### Acceptance Criteria
- [ ] Better step descriptions for user feedback
- [ ] Time estimates for long operations visible in CLI
- [ ] Enhanced CLI progress display validation
- [ ] No breaking changes to existing API
- [ ] Time estimates are reasonably accurate (within 50% after 25% completion)
- [ ] Progress messages are informative and user-friendly

### Deliverables
- [ ] Enhanced progress reporting in CLI commands
- [ ] Validation tests for improved user experience
- [ ] User testing documentation and results

### User Testing Script
**Location**: `docs/testing/task-1.1c-user-testing.md`

```markdown
# Task 1.1c Enhanced Progress Features User Testing

## Test Scenarios

### Scenario 1: Enhanced Step Descriptions
1. Run: `uv run ktrdr data load AAPL 1d --start 2024-01-01 --end 2024-01-31`
2. Observe: Step descriptions should be more detailed and informative
3. Expected: Clear indication of what specific operation is happening

### Scenario 2: Time Estimation
1. Run a longer operation: `uv run ktrdr data load MSFT 1h --start 2024-01-01 --end 2024-01-31`
2. Observe: Time estimates should appear and update
3. Expected: Reasonable time estimates that improve in accuracy

### Scenario 3: Progress Detail Messages
1. Run: `uv run ktrdr data load GOOGL 5m --start 2024-08-01 --end 2024-08-03`
2. Observe: Detail messages showing specific segments being processed
3. Expected: Informative details about current processing step

## Success Criteria
- [ ] Step descriptions are more informative than before
- [ ] Time estimates appear and are reasonable
- [ ] Progress details help understand current operation
- [ ] No regression in functionality
- [ ] Progress display is clean and readable
```

---

# End of Phase 1 Detailed Plan

This detailed plan for Phase 1 shows the level of detail needed for each task. I'll create similar detailed plans for the remaining phases if this approach looks good to you. Each task includes:

1. **Technical Context**: Why this task matters
2. **Detailed Implementation Steps**: Specific code locations and approaches
3. **Comprehensive Testing**: Unit, integration, and user testing
4. **Branching Strategy**: Clear branch names and PR targets
5. **User Testing Points**: When and how to involve the user
6. **Acceptance Criteria**: Clear definition of "done"
7. **Reviewer Notes**: What to focus on during code review

Would you like me to continue with similarly detailed plans for Phases 2 and 3?