# SLICE 2.5: COMPLETE ASYNC INFRASTRUCTURE CLEANUP

**Duration**: 3 days  
**Branch**: `slice-2.5-complete-async-cleanup`  
**Goal**: Complete elimination of legacy async patterns and ProgressManager cleanup after SLICE-1 and SLICE-2 foundation  
**Priority**: Critical (Technical Debt)  
**Depends on**: SLICE-1 and SLICE-2 completion

## Overview

This slice addresses the remaining technical debt and completes the async infrastructure cleanup started in SLICE-1 and SLICE-2. After thorough analysis, we need to eliminate the final legacy patterns and consolidate the async infrastructure into a clean, unified system.

**KEY INSIGHT**: We have successfully built the generic async infrastructure, but legacy patterns still exist that violate the unified approach and create maintenance burden.

## Success Criteria

- [ ] **Complete elimination** of all `hasattr()` cancellation pattern checking
- [ ] **ProgressManager class removal** after component migration to GenericProgressManager
- [ ] **TimeEstimationEngine extraction** to async infrastructure 
- [ ] **Clean CLI progress interface** to use GenericProgressState directly
- [ ] **Single import paths** for all async infrastructure components
- [ ] **Zero legacy async patterns** remaining in codebase

## Critical Issues Identified

### 🚨 **PRIORITY 1: hasattr() Cancellation Pattern Elimination**

**Files with Legacy Patterns**:
```python
# ktrdr/managers/base.py - ServiceOrchestrator
if hasattr(token, "is_cancelled_requested"):
    return token.is_cancelled_requested
elif hasattr(token, "is_set"):
    return token.is_set()
elif hasattr(token, "is_cancelled"):
    return token.is_cancelled()

# ktrdr/managers/async_host_service.py - AsyncHostService (base class for IbDataAdapter, etc.)
if hasattr(cancellation_token, "is_cancelled_requested"):
    is_cancelled = cancellation_token.is_cancelled_requested
elif hasattr(cancellation_token, "is_set"):
    is_cancelled = cancellation_token.is_set()
elif hasattr(cancellation_token, "cancelled"):
    is_cancelled = cancellation_token.cancelled()
```

**Impact**: Violates SLICE-2 unified cancellation system goals across both core ServiceOrchestrator and host service adapters.

### 📊 **PRIORITY 2: ProgressManager Infrastructure Cleanup**

**Current State**:
- **ProgressManager class**: Still exists (28KB!) but mostly superseded
- **TimeEstimationEngine**: Still in `data/components/progress_manager.py` (should be generic)
- **ProgressState**: Used by CLI - should migrate to GenericProgressState directly
- **Component Dependencies**: Some components still use old ProgressManager

**Active Usage Found**:
- `multi_timeframe_coordinator.py`: `ProgressManager(progress_callback)`
- CLI files: Import `ProgressState` for display - **should use GenericProgressState instead**
- DataProgressRenderer: Imports `TimeEstimationEngine` from old location

### 🧵 **PRIORITY 3: threading.Event Analysis**

**Service Lifecycle Controls (LEGITIMATE - NOT cancellation patterns)**:
```python
# ktrdr/training/data_optimization.py - Data prefetching control
self.stop_prefetching = threading.Event()  # Performance optimization

# ktrdr/ib/gap_filler.py - Background service control  
self._stop_event = threading.Event()       # Service lifecycle

# ktrdr/ib/connection.py - Connection thread control
self.stop_event = threading.Event()        # IB connection management
```

**Analysis**: These are **legitimate service lifecycle controls**, NOT async operation cancellation patterns. They control background services, not individual operations that should use CancellationToken.

## Tasks

### Task 2.5.1: Eliminate All hasattr() Cancellation Patterns

**Day**: 1  
**Assignee**: AI IDE Agent  
**Priority**: 10

**Description**: Completely eliminate the `hasattr()` multi-pattern cancellation checking from ServiceOrchestrator and AsyncHostService, enforcing the unified CancellationToken protocol established in SLICE-2.

**Acceptance Criteria**:
- [ ] ServiceOrchestrator `_is_token_cancelled()` method uses only CancellationToken protocol
- [ ] AsyncHostService cancellation checking uses only CancellationToken protocol  
- [ ] All legacy token types removed from documentation and type hints
- [ ] Unified cancellation interface enforced across all managers
- [ ] Zero `hasattr()` cancellation checking remains in codebase

**Implementation Details**:

```python
# File: ktrdr/managers/base.py
# REMOVE the entire _is_token_cancelled method and replace with:

def _is_token_cancelled(self, token: CancellationToken) -> bool:
    """
    Check if a cancellation token is cancelled.
    
    Args:
        token: Unified cancellation token
        
    Returns:
        True if token indicates cancellation, False otherwise
    """
    return token.is_cancelled()

# File: ktrdr/managers/async_host_service.py  
# REPLACE the entire cancellation checking section with:

def _check_cancellation_token(self, cancellation_token: Optional[CancellationToken]) -> bool:
    """Check unified cancellation token status."""
    if cancellation_token is None:
        return False
    return cancellation_token.is_cancelled()
```

**Breaking Change Impact**: 
- Any code passing non-CancellationToken objects will fail with clear type errors
- This is **intentional** to enforce the unified system

**Testing Requirements**:
- [ ] All existing cancellation tests pass with CancellationToken protocol
- [ ] Type checking passes with unified CancellationToken types
- [ ] ServiceOrchestrator cancellation works consistently 
- [ ] No regression in cancellation responsiveness
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/managers/base.py` with unified cancellation checking only
- [ ] `ktrdr/managers/async_host_service.py` with unified cancellation checking only
- [ ] Updated type hints enforcing CancellationToken protocol
- [ ] Tests validating unified cancellation behavior
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.5.2: Extract TimeEstimationEngine to Generic Infrastructure

**Day**: 1  
**Assignee**: AI IDE Agent  
**Priority**: 9  
**Depends on**: None (parallel with Task 2.5.1)

**Description**: Extract TimeEstimationEngine from the data-specific ProgressManager to the generic async infrastructure, making time estimation available for all operation types (data, training, etc.).

**Acceptance Criteria**:
- [ ] TimeEstimationEngine moved to `ktrdr/async_infrastructure/time_estimation.py`
- [ ] Remove all data-specific logic from TimeEstimationEngine
- [ ] Update all imports to use new generic location
- [ ] DataProgressRenderer uses generic TimeEstimationEngine
- [ ] Time estimation cache remains compatible and functional

**Implementation Details**:

```python
# File: ktrdr/async_infrastructure/time_estimation.py (NEW)
"""
Generic time estimation engine for async operations.

Provides learning-based time estimation for any type of operation
using persistent cache and operation context analysis.
"""

import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class TimeEstimationEngine:
    """
    Learning-based time estimation engine for async operations.
    
    This engine is domain-agnostic and can learn timing patterns for any
    type of operation - data loading, training, processing, etc.
    
    Key features:
    - Persistent cache across sessions
    - Context-aware estimation based on operation parameters
    - Learning from operation history
    - Thread-safe operation tracking
    """
    
    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize with optional cache file path."""
        self.cache_file = cache_file or (Path.home() / ".ktrdr" / "cache" / "time_estimation.pkl")
        self.operation_history: Dict[str, list] = {}
        self._load_cache()
    
    def estimate_remaining_time(self, 
                              operation_type: str,
                              progress_percentage: float,
                              elapsed_time: timedelta,
                              context: Dict[str, Any] = None) -> Optional[timedelta]:
        """
        Estimate remaining time based on current progress and historical data.
        
        Args:
            operation_type: Type of operation (e.g., "data_load", "model_train")
            progress_percentage: Current progress (0-100)
            elapsed_time: Time elapsed so far
            context: Additional context for estimation accuracy
            
        Returns:
            Estimated remaining time or None if insufficient data
        """
        if progress_percentage <= 0:
            return None
            
        # Create context key for cache lookup
        context_key = self._create_context_key(operation_type, context)
        
        # Get historical data
        if context_key not in self.operation_history:
            # No history, use simple linear projection
            if progress_percentage > 0:
                total_estimated = elapsed_time.total_seconds() / (progress_percentage / 100.0)
                remaining_seconds = total_estimated - elapsed_time.total_seconds()
                return timedelta(seconds=max(0, remaining_seconds))
            return None
        
        # Use historical data for better estimation
        history = self.operation_history[context_key]
        if len(history) < 2:
            # Insufficient history, fall back to linear
            total_estimated = elapsed_time.total_seconds() / (progress_percentage / 100.0)  
            remaining_seconds = total_estimated - elapsed_time.total_seconds()
            return timedelta(seconds=max(0, remaining_seconds))
        
        # Calculate weighted average of recent operations
        recent_operations = history[-5:]  # Use last 5 operations
        avg_total_time = sum(op['total_time'] for op in recent_operations) / len(recent_operations)
        
        # Estimate remaining based on average and current progress
        estimated_total = avg_total_time
        remaining_seconds = estimated_total - elapsed_time.total_seconds()
        
        return timedelta(seconds=max(0, remaining_seconds))
    
    def record_operation_completion(self,
                                  operation_type: str, 
                                  total_time: timedelta,
                                  context: Dict[str, Any] = None):
        """Record completed operation for future estimation."""
        context_key = self._create_context_key(operation_type, context)
        
        if context_key not in self.operation_history:
            self.operation_history[context_key] = []
            
        self.operation_history[context_key].append({
            'total_time': total_time.total_seconds(),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        })
        
        # Keep only recent history to prevent unlimited growth
        if len(self.operation_history[context_key]) > 20:
            self.operation_history[context_key] = self.operation_history[context_key][-20:]
        
        self._save_cache()
    
    def _create_context_key(self, operation_type: str, context: Dict[str, Any] = None) -> str:
        """Create cache key from operation type and relevant context."""
        if not context:
            return operation_type
            
        # Include relevant context factors that affect timing
        key_factors = []
        key_factors.append(operation_type)
        
        # Add generic context factors that commonly affect operation timing
        for factor in ['symbol', 'timeframe', 'mode', 'dataset_size', 'model_type']:
            if factor in context:
                key_factors.append(f"{factor}={context[factor]}")
                
        return "|".join(key_factors)
    
    def _load_cache(self):
        """Load operation history from cache file."""
        if not self.cache_file.exists():
            return
            
        try:
            with open(self.cache_file, 'rb') as f:
                self.operation_history = pickle.load(f)
            logger.debug(f"Loaded time estimation cache with {len(self.operation_history)} operation types")
        except Exception as e:
            logger.warning(f"Failed to load time estimation cache: {e}")
            self.operation_history = {}
    
    def _save_cache(self):
        """Save operation history to cache file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.operation_history, f)
        except Exception as e:
            logger.warning(f"Failed to save time estimation cache: {e}")

# Factory function for easy access
def create_time_estimation_engine(cache_file: Optional[Path] = None) -> TimeEstimationEngine:
    """Create a TimeEstimationEngine instance with default cache location."""
    if cache_file is None:
        cache_dir = Path.home() / ".ktrdr" / "cache"
        cache_file = cache_dir / "time_estimation.pkl"
    
    return TimeEstimationEngine(cache_file)
```

**Migration Strategy**:
1. Create new generic TimeEstimationEngine
2. Update DataProgressRenderer to import from new location
3. Update DataManagerBuilder to use generic engine
4. Remove TimeEstimationEngine from old ProgressManager file

**Testing Requirements**:
- [ ] All existing time estimation functionality preserved
- [ ] Cache compatibility maintained (no data loss)
- [ ] DataProgressRenderer works with generic TimeEstimationEngine
- [ ] Time estimation accuracy maintained or improved
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] `ktrdr/async_infrastructure/time_estimation.py` with generic TimeEstimationEngine
- [ ] Updated DataProgressRenderer imports
- [ ] Updated DataManagerBuilder configuration  
- [ ] Migration tests validating functionality preservation
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.5.3: Complete ProgressManager Migration and CLI GenericProgressState Migration

**Day**: 2  
**Assignee**: AI IDE Agent  
**Priority**: 8  
**Depends on**: Task 2.5.2

**Description**: Complete the migration of remaining components from ProgressManager to GenericProgressManager, migrate CLI to use GenericProgressState directly, then remove the obsolete ProgressManager class.

**Acceptance Criteria**:
- [ ] `multi_timeframe_coordinator.py` migrated to GenericProgressManager
- [ ] CLI migrated to use GenericProgressState directly (no compatibility layer)
- [ ] ProgressManager class removed from `progress_manager.py`
- [ ] All components use GenericProgressManager consistently
- [ ] File size reduction: `progress_manager.py` 28KB → ~8KB

**Implementation Details**:

**Step 1: Migrate CLI to GenericProgressState**
```python
# File: ktrdr/cli/progress_display_enhanced.py (update imports)
# OLD:
# from ktrdr.data.components.progress_manager import ProgressState

# NEW:
from ktrdr.async_infrastructure.progress import GenericProgressState

class EnhancedCLIProgressDisplay:
    def update_progress(self, progress_state: GenericProgressState) -> None:
        """Update progress display with generic state information."""
        # Access fields that exist in GenericProgressState:
        # - operation_id, current_step, total_steps, percentage, message
        # - start_time, estimated_remaining, items_processed, total_items
        # - context dict for additional data
        
        # For CLI-specific data, access via context:
        symbol = progress_state.context.get('symbol', 'Unknown')
        timeframe = progress_state.context.get('timeframe', 'Unknown')
        current_step_name = progress_state.context.get('current_step_name')
```

**Step 2: Migrate MultiTimeframeCoordinator**
```python
# File: ktrdr/data/multi_timeframe_coordinator.py (update)

# OLD import:
# from ktrdr.data.components.progress_manager import ProgressManager

# NEW imports:
from ktrdr.async_infrastructure.progress import GenericProgressManager
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.async_infrastructure.time_estimation import create_time_estimation_engine

class MultiTimeframeCoordinator:
    def load_multi_timeframe_data(self, ...):
        # OLD: 
        # progress_manager = ProgressManager(progress_callback)
        
        # NEW:
        time_engine = create_time_estimation_engine()
        renderer = DataProgressRenderer(time_estimation_engine=time_engine)
        progress_manager = GenericProgressManager(
            callback=progress_callback,
            renderer=renderer
        )
        
        # Use GenericProgressManager API
        progress_manager.start_operation(
            operation_id=f"multi_timeframe_{symbol}",
            total_steps=len(timeframes) + 1,
            context={'symbol': symbol, 'timeframes': timeframes}
        )
```

**Step 3: Remove ProgressManager Class**
```python
# File: ktrdr/data/components/progress_manager.py (major reduction)
"""
Legacy progress components.

This file now contains only TimeEstimationEngine (DEPRECATED - use
ktrdr.async_infrastructure.time_estimation instead) and utilities
for backward compatibility.
"""

# REMOVE: class ProgressManager (entire ~600 lines)
# REMOVE: All domain-specific message logic  
# REMOVE: Complex initialization logic
# KEEP: Only deprecated imports for transition period

# Deprecated imports for backward compatibility - will be removed in future version
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine  # noqa: F401
from ktrdr.async_infrastructure.legacy_compatibility import ProgressState  # noqa: F401

import warnings

warnings.warn(
    "ktrdr.data.components.progress_manager is deprecated. "
    "Use ktrdr.async_infrastructure.time_estimation for TimeEstimationEngine "
    "and ktrdr.async_infrastructure.legacy_compatibility for ProgressState.",
    DeprecationWarning,
    stacklevel=2
)
```

**Step 3: Update CLI Data Commands**
```python
# File: ktrdr/cli/data_commands.py (update)
# OLD:
# from ktrdr.data.components.progress_manager import ProgressState

# NEW:
from ktrdr.async_infrastructure.progress import GenericProgressState

# Update callback creation to work with GenericProgressState
def create_enhanced_progress_callback(console, show_details=True):
    # CLI callback now receives GenericProgressState directly
    def enhanced_progress_callback(progress_state: GenericProgressState) -> None:
        # Use progress_state.context for CLI-specific data
        pass
```

**Testing Requirements**:
- [ ] MultiTimeframeCoordinator works with GenericProgressManager
- [ ] CLI progress displays work identically with GenericProgressState
- [ ] All existing progress functionality preserved
- [ ] File size reduction achieved (28KB → ~8KB)
- [ ] No functional regressions in progress tracking
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:
- [ ] Updated CLI to use GenericProgressState directly (no compatibility layer)
- [ ] Updated MultiTimeframeCoordinator using GenericProgressManager
- [ ] Reduced `progress_manager.py` with deprecation warnings
- [ ] Migration validation tests
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

### Task 2.5.4: Validate Complete Infrastructure Cleanup

**Day**: 3  
**Assignee**: AI IDE Agent  
**Priority**: 10  
**Depends on**: All previous tasks

**Description**: Comprehensive validation that all legacy async patterns have been eliminated and the unified async infrastructure is working correctly across all components.

**Acceptance Criteria**:
- [ ] **Zero** `hasattr()` cancellation patterns in codebase
- [ ] **Zero** direct ProgressManager class instantiations  
- [ ] **All** components use GenericProgressManager or ServiceOrchestrator patterns
- [ ] **All** imports point to correct async infrastructure locations
- [ ] **CLI uses GenericProgressState** directly without compatibility layers
- [ ] **Complete** functionality preservation with enhanced capabilities

**Validation Strategy**:

1. **Pattern Audit**:
   ```bash
   # Must return zero results:
   grep -r "hasattr.*cancel" ktrdr/
   grep -r "hasattr.*is_set" ktrdr/ 
   grep -r "ProgressManager(" ktrdr/
   ```

2. **Import Validation**:
   ```bash
   # Verify clean import paths:
   grep -r "from.*progress_manager.*import" ktrdr/
   grep -r "TimeEstimationEngine" ktrdr/
   grep -r "ProgressState" ktrdr/cli/  # Should now import GenericProgressState
   ```

3. **Threading.Event Validation**:
   ```bash
   # Should only return legitimate service lifecycle controls:
   grep -r "threading\.Event" ktrdr/
   # Expected: only in training/data_optimization.py, ib/gap_filler.py, ib/connection.py
   ```

4. **Functionality Testing**:
   - All data operations cancelable through unified system
   - Progress tracking works consistently across all operations
   - CLI progress displays work identically with GenericProgressState
   - Host service adapters use unified cancellation

**Testing Requirements**:
- [ ] **Complete test suite**: All 1,289+ tests must pass
- [ ] **Pattern validation**: Zero legacy patterns detected
- [ ] **Import validation**: All imports use correct async infrastructure paths
- [ ] **Functionality validation**: No regressions in any component
- [ ] **Performance validation**: No significant performance impact
- [ ] **CLI validation**: Progress displays work identically
- [ ] **Quality checks**: `make quality` must pass

**Deliverables**:
- [ ] Comprehensive cleanup validation report
- [ ] Pattern audit results showing zero legacy patterns
- [ ] Import audit showing clean dependency paths
- [ ] Performance comparison showing no regressions
- [ ] Documentation of unified async infrastructure usage
- [ ] All tests pass: `make test`
- [ ] Code quality checks pass: `make quality`

---

## Integration Points for Future Slices

### SLICE-3 Integration Readiness
- [ ] Unified CancellationToken protocol proven across all operations
- [ ] GenericProgressManager ready for training system integration
- [ ] TimeEstimationEngine available for training operation timing
- [ ] Clean async infrastructure ready for training manager inheritance

### Training System Benefits
- [ ] TrainingManager can inherit ServiceOrchestrator with proven patterns
- [ ] Training operations can use same progress and cancellation infrastructure
- [ ] Time estimation available for training job duration prediction
- [ ] CLI integration ready for training progress displays

## Success Metrics

### Technical Debt Elimination
- [ ] **28KB → 8KB**: ProgressManager file size reduction (71% cleanup)
- [ ] **Zero legacy patterns**: Complete elimination of hasattr() and threading.Event
- [ ] **Clean imports**: Single source of truth for all async infrastructure
- [ ] **Unified protocols**: CancellationToken and GenericProgressManager everywhere

### Quality Metrics
- [ ] **100% test preservation**: All existing tests pass
- [ ] **Zero regressions**: All functionality preserved
- [ ] **Performance maintained**: No significant overhead from cleanup
- [ ] **Code quality**: All quality checks pass

### Foundation Quality
- [ ] **Ready for SLICE-3**: Clean foundation for training system integration
- [ ] **Maintainable**: Single patterns eliminate confusion and bugs
- [ ] **Extensible**: Generic infrastructure supports any operation type
- [ ] **Consistent**: Same patterns work across data, training, and future operations

## Risk Mitigation

### Breaking Changes
- **Risk**: CLI progress displays break during ProgressState migration
- **Mitigation**: Legacy compatibility module provides identical interface

### Performance Impact  
- **Risk**: GenericProgressManager slower than optimized ProgressManager
- **Mitigation**: Lightweight implementation with performance testing

### Migration Complexity
- **Risk**: Complex migration introduces bugs in critical components
- **Mitigation**: Incremental migration with comprehensive testing at each step

### Import Path Changes
- **Risk**: Import path changes break external integrations  
- **Mitigation**: Deprecation warnings and backward compatibility imports during transition

## Notes

This slice completes the async infrastructure foundation by eliminating all technical debt and legacy patterns. The result is a clean, unified system where:

- **All cancellation** goes through CancellationToken protocol
- **All progress tracking** goes through GenericProgressManager + domain renderers  
- **All time estimation** goes through generic TimeEstimationEngine
- **All async patterns** are consistent across the entire system

The clean foundation enables confident extension to training systems in SLICE-3 and provides a maintainable async infrastructure for all future development.