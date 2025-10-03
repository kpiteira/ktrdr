# SLICE 1: GENERIC PROGRESS FOUNDATION

**Duration**: 1 week (5 days)  
**Goal**: Enhance existing ServiceOrchestrator with ProgressManager rich features to create unified async progress infrastructure  
**Priority**: High  
**Branch**: `slice-1-generic-progress-foundation`

## Branch and PR Strategy

**Branch Management**:

- Create branch: `git checkout -b slice-1-generic-progress-foundation`
- Create draft PR at start of slice for continuous review
- Each task commits with comprehensive testing (`make test` + `make quality`)
- Branch merged at slice end after complete validation

## Overview

This slice enhances the existing **ServiceOrchestrator.execute_with_progress()** method with the rich capabilities from ProgressManager. Rather than extracting or creating new infrastructure, we integrate ProgressManager's sophisticated features (TimeEstimationEngine, hierarchical progress, context-aware messaging) into ServiceOrchestrator patterns, making them available to all manager classes that inherit from it.

**KEY INSIGHT**: ServiceOrchestrator already provides `execute_with_progress()` - we enhance it rather than replace it.

## Success Criteria

- [ ] ServiceOrchestrator.execute_with_progress() enhanced with ProgressManager rich features
- [ ] DataProgressRenderer integrates with enhanced ServiceOrchestrator methods
- [ ] DataManager leverages enhanced ServiceOrchestrator instead of direct ProgressManager usage
- [ ] 100% backward compatibility with existing CLI and API
- [ ] All existing tests pass + comprehensive new test coverage
- [ ] Enhanced ServiceOrchestrator provides foundation for all future async enhancements

## Current Architecture Understanding

### Existing ProgressManager Features (PRESERVE ALL)

- **Hierarchical Progress**: Operation → Steps → Sub-steps → Items
- **Learning-based Time Estimation**: Context-aware with persistent cache
- **Rich Context Messages**: Symbol/timeframe/mode integration  
- **Thread-safe Operations**: RLock for concurrent access
- **Smart Message Enhancement**: Domain-specific rendering logic
- **Comprehensive State Tracking**: 20+ progress state fields

### Integration Strategy

- Work WITH existing component architecture via DataManagerBuilder
- Enhance ServiceOrchestrator.execute_with_progress() with ProgressManager features
- Create DataProgressRenderer that preserves ALL existing ProgressManager capabilities
- Maintain existing DataManager public API for zero breaking changes
- Integrate through builder pattern, not direct replacement

## Tasks

### Task 1.1: Enhance ServiceOrchestrator with ProgressManager Features

**Day**: 1  
**Assignee**: AI IDE Agent  
**Priority**: 10  

**Description**: Enhance the existing ServiceOrchestrator.execute_with_progress() method by integrating ProgressManager's rich features (TimeEstimationEngine, hierarchical progress, context awareness), making them available to all ServiceOrchestrator-based managers.

**Acceptance Criteria**:

- [ ] ServiceOrchestrator.execute_with_progress() enhanced with ProgressManager capabilities
- [ ] TimeEstimationEngine integration available to all ServiceOrchestrator subclasses
- [ ] Hierarchical progress tracking integrated into ServiceOrchestrator
- [ ] Thread-safe progress state management using RLock (preserve existing pattern)
- [ ] Domain-specific progress rendering through ServiceOrchestrator enhancement
- [ ] Zero loss of functionality from existing ProgressManager

**Implementation Details**:

```python
# File: ktrdr/async_infrastructure/progress.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
import threading

@dataclass
class GenericProgressState:
    """Generic progress state - domain-agnostic core."""
    operation_id: str
    current_step: int
    total_steps: int
    percentage: float
    message: str
    start_time: datetime = field(default_factory=datetime.now)
    
    # Generic context - domain defines content
    context: dict[str, Any] = field(default_factory=dict)
    
    # Generic timing
    estimated_remaining: Optional[timedelta] = None
    
    # Generic item tracking
    items_processed: int = 0
    total_items: Optional[int] = None

class ProgressRenderer(ABC):
    """Abstract progress renderer for domain-specific display."""
    
    @abstractmethod
    def render_message(self, state: GenericProgressState) -> str:
        """Render progress message for this domain."""
        pass
    
    @abstractmethod
    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """Enhance state with domain-specific information."""
        pass

class GenericProgressManager:
    """Domain-agnostic progress manager - extracted from existing ProgressManager."""
    
    def __init__(self, 
                 callback: Optional[Callable[[GenericProgressState], None]] = None,
                 renderer: Optional[ProgressRenderer] = None):
        self.callback = callback
        self.renderer = renderer
        self._state: Optional[GenericProgressState] = None
        self._lock = threading.RLock()  # Same as existing ProgressManager
    
    def start_operation(self, operation_id: str, total_steps: int, 
                       context: dict[str, Any] = None) -> None:
        """Start tracking operation - generic interface."""
        with self._lock:
            self._state = GenericProgressState(
                operation_id=operation_id,
                current_step=0,
                total_steps=total_steps,
                percentage=0.0,
                message=f"Starting {operation_id}",
                context=context or {}
            )
            
            # Use renderer if available
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)
            
            self._trigger_callback()
    
    def update_progress(self, step: int, message: str = None, 
                       items_processed: int = 0, context: dict[str, Any] = None) -> None:
        """Update progress - generic interface."""
        with self._lock:
            if not self._state:
                return
                
            self._state.current_step = step
            self._state.percentage = min(100.0, (step / self._state.total_steps) * 100.0)
            self._state.items_processed = items_processed
            
            # Update context
            if context:
                self._state.context.update(context)
            
            # Use renderer for message
            if self.renderer:
                self._state = self.renderer.enhance_state(self._state)
                self._state.message = self.renderer.render_message(self._state)
            elif message:
                self._state.message = message
            
            self._trigger_callback()
    
    def complete_operation(self) -> None:
        """Mark operation complete."""
        with self._lock:
            if self._state:
                self._state.current_step = self._state.total_steps
                self._state.percentage = 100.0
                if self.renderer:
                    self._state.message = self.renderer.render_message(self._state)
                else:
                    self._state.message = f"Operation {self._state.operation_id} completed"
                self._trigger_callback()
    
    def _trigger_callback(self):
        """Trigger progress callback - preserve existing pattern."""
        if self.callback and self._state:
            try:
                self.callback(self._state)
            except Exception as e:
                # Same error handling as existing ProgressManager
                import logging
                logging.getLogger(__name__).warning(f"Progress callback failed: {e}")
```

**Testing Requirements**:

- [ ] All tests from existing ProgressManager must pass when using GenericProgressManager
- [ ] Unit tests for GenericProgressManager with >95% coverage  
- [ ] Thread safety validation with concurrent operations
- [ ] Callback failure handling tests
- [ ] Progress state transitions validation
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:

- [ ] `ktrdr/async_infrastructure/progress.py` with generic infrastructure
- [ ] `tests/unit/async/test_progress.py` comprehensive test suite
- [ ] Thread safety validation tests
- [ ] Documentation for ProgressRenderer integration pattern

---

### Task 1.2: Create DataProgressRenderer with ALL Existing Features

**Day**: 2  
**Assignee**: AI IDE Agent  
**Priority**: 10  
**Depends on**: Task 1.1

**Description**: Create DataProgressRenderer that preserves ALL sophisticated features from the existing ProgressManager including time estimation, hierarchical progress, and rich context messaging.

**Acceptance Criteria**:

- [ ] DataProgressRenderer implements ProgressRenderer interface
- [ ] Preserves existing TimeEstimationEngine integration
- [ ] Maintains hierarchical progress display (Operation → Steps → Sub-steps → Items)
- [ ] Renders messages with symbol, timeframe, mode context
- [ ] Preserves ALL existing ProgressState fields and functionality
- [ ] Maintains learning-based time estimation with persistent cache
- [ ] Thread-safe context enhancement and message rendering

**Implementation Details**:

```python
# File: ktrdr/data/async/__init__.py (create package)
# File: ktrdr/data/async/data_progress_renderer.py

from datetime import datetime, timedelta
from typing import Any, Optional
from ktrdr.async.progress import ProgressRenderer, GenericProgressState
from ktrdr.data.components.progress_manager import TimeEstimationEngine, ProgressState

class DataProgressRenderer(ProgressRenderer):
    """Preserves ALL existing ProgressManager features with domain-specific rendering."""
    
    def __init__(self, 
                 time_estimation_engine: Optional[TimeEstimationEngine] = None,
                 enable_hierarchical_progress: bool = True):
        """Initialize with existing ProgressManager capabilities."""
        self.time_estimator = time_estimation_engine
        self.enable_hierarchical = enable_hierarchical_progress
        
        # Track operation context for time estimation
        self._operation_start_time: Optional[datetime] = None
        self._operation_type: Optional[str] = None
    
    def render_message(self, state: GenericProgressState) -> str:
        """Render data-specific progress message with ALL existing enhancements."""
        base_message = self._extract_base_message(state.message)
        
        # Add data-specific context (preserve existing logic)
        context = state.context
        parts = [base_message]
        
        # Symbol, timeframe, mode context
        symbol = context.get('symbol', 'Unknown')
        timeframe = context.get('timeframe', 'Unknown') 
        mode = context.get('mode', 'Unknown')
        
        if symbol != 'Unknown' or timeframe != 'Unknown':
            context_str = f"({symbol} {timeframe}"
            if mode != 'Unknown':
                context_str += f", {mode} mode"
            context_str += ")"
            parts.append(context_str)
        
        # Step progress
        if state.total_steps > 0:
            parts.append(f"[{state.current_step}/{state.total_steps}]")
        
        # Item progress (preserve existing functionality)
        if state.total_items and state.total_items > 0:
            items_str = f"{state.items_processed}/{state.total_items} items"
            parts.append(f"({items_str})")
        
        # Time estimation (preserve existing functionality)
        if state.estimated_remaining:
            parts.append(f"ETA: {self._format_timedelta(state.estimated_remaining)}")
        
        return " ".join(parts)
    
    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """Enhance generic state with ALL existing ProgressManager features."""
        
        # Time estimation enhancement (preserve existing logic)
        if self.time_estimator and state.context:
            if not self._operation_start_time and state.current_step == 0:
                self._operation_start_time = state.start_time
                self._operation_type = state.operation_id
            
            # Calculate estimated remaining time
            if self._operation_start_time and state.current_step > 0:
                elapsed = (datetime.now() - self._operation_start_time).total_seconds()
                if state.percentage > 0:
                    estimated_total = elapsed / (state.percentage / 100.0)
                    estimated_remaining = max(0, estimated_total - elapsed)
                    state.estimated_remaining = timedelta(seconds=estimated_remaining)
        
        # Add hierarchical progress context
        if self.enable_hierarchical and state.context:
            # Extract step details if available
            step_name = state.context.get('current_step_name')
            if step_name:
                state.context['enhanced_step_name'] = step_name
            
            # Add sub-step progress
            step_current = state.context.get('step_current', 0)
            step_total = state.context.get('step_total', 0)
            if step_total > 0:
                state.context['step_progress'] = f"{step_current}/{step_total}"
        
        return state
    
    def create_legacy_compatible_state(self, generic_state: GenericProgressState) -> ProgressState:
        """Convert generic state back to rich ProgressState for backward compatibility."""
        
        # Create full ProgressState with all existing fields
        return ProgressState(
            operation_id=generic_state.operation_id,
            current_step=generic_state.current_step,
            total_steps=generic_state.total_steps,
            message=generic_state.message,
            percentage=generic_state.percentage,
            estimated_remaining=generic_state.estimated_remaining,
            start_time=generic_state.start_time,
            
            # Preserve existing fields
            steps_completed=generic_state.current_step,
            steps_total=generic_state.total_steps,
            expected_items=generic_state.total_items,
            items_processed=generic_state.items_processed,
            operation_context=generic_state.context,
            
            # Extract from context if available
            current_step_name=generic_state.context.get('current_step_name'),
            step_current=generic_state.context.get('step_current', 0),
            step_total=generic_state.context.get('step_total', 0),
            step_detail=generic_state.context.get('step_detail', ''),
            current_item_detail=generic_state.context.get('current_item_detail'),
        )
    
    def _extract_base_message(self, message: str) -> str:
        """Extract base message without previous context."""
        if '(' in message and ')' in message:
            return message[:message.find('(')].strip()
        return message
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta for display (preserve existing logic)."""
        seconds = int(td.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
```

**Testing Requirements**:

- [ ] All existing ProgressManager message formats preserved
- [ ] Time estimation accuracy matches existing implementation
- [ ] Hierarchical progress display working correctly
- [ ] Context enhancement with various data scenarios
- [ ] Legacy compatibility state conversion
- [ ] Thread safety under concurrent rendering
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:

- [ ] `ktrdr/data/async/data_progress_renderer.py` with complete feature preservation
- [ ] `tests/unit/data/async/test_data_progress_renderer.py` comprehensive test suite
- [ ] Time estimation integration tests
- [ ] Legacy compatibility validation tests

---

### Task 1.3: Enhance DataManagerBuilder with Async Infrastructure

**Day**: 3  
**Assignee**: AI IDE Agent  
**Priority**: 9  
**Depends on**: Task 1.2

**Description**: Enhance the existing DataManagerBuilder to create and integrate the generic async infrastructure while preserving all existing component creation and initialization patterns.

**Acceptance Criteria**:

- [ ] DataManagerBuilder creates generic async infrastructure components
- [ ] DataProgressRenderer initialized with existing TimeEstimationEngine
- [ ] GenericProgressManager configured with DataProgressRenderer
- [ ] All existing component creation logic preserved
- [ ] Builder pattern maintains fluent interface
- [ ] Enhanced configuration passed to DataManager constructor

**Implementation Details**:

```python
# File: ktrdr/data/data_manager_builder.py (enhancement)

from ktrdr.async.progress import GenericProgressManager
from ktrdr.data.async.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.progress_manager import TimeEstimationEngine

class DataManagerConfiguration:
    """Enhanced configuration with async infrastructure."""
    
    def __init__(self):
        # Existing configuration preserved
        self.data_dir: Optional[str] = None
        self.max_gap_percentage: float = 5.0
        self.default_repair_method: str = "ffill"
        self.ib_host_service_config: Optional[IbHostServiceConfig] = None
        
        # Existing component instances preserved
        self.data_loader: Optional[LocalDataLoader] = None
        self.data_validator: Optional[DataQualityValidator] = None
        self.gap_classifier: Optional[GapClassifier] = None
        self.gap_analyzer: Optional[GapAnalyzer] = None
        self.segment_manager: Optional[SegmentManager] = None
        self.data_processor: Optional[DataProcessor] = None
        self.data_loading_orchestrator: Optional[DataLoadingOrchestrator] = None
        self.health_checker: Optional[DataHealthChecker] = None
        self.external_provider: Optional[IbDataAdapter] = None
        
        # NEW: Generic async infrastructure
        self.generic_progress_manager: Optional[GenericProgressManager] = None
        self.data_progress_renderer: Optional[DataProgressRenderer] = None
        self.time_estimation_engine: Optional[TimeEstimationEngine] = None

class DataManagerBuilder:
    """Enhanced builder with async infrastructure creation."""
    
    def build(self) -> "DataManager":
        """Build DataManager with enhanced async infrastructure."""
        config = DataManagerConfiguration()
        
        # 1. Load configurations (existing logic preserved)
        self._load_ib_configuration(config)
        self._validate_configuration(config)
        
        # 2. Create existing components (preserve all existing logic)
        self._create_data_loader(config)
        self._create_data_validator(config) 
        self._create_gap_components(config)
        self._create_segment_manager(config)
        self._create_data_processor(config)
        self._create_health_checker(config)
        self._create_external_provider(config)
        self._create_data_loading_orchestrator(config)
        
        # 3. NEW: Create async infrastructure
        self._create_async_infrastructure(config)
        
        # 4. Create DataManager with enhanced configuration
        from ktrdr.data.data_manager import DataManager
        return DataManager(
            data_dir=config.data_dir,
            max_gap_percentage=config.max_gap_percentage,
            default_repair_method=config.default_repair_method,
            builder_config=config  # Pass full configuration
        )
    
    def _create_async_infrastructure(self, config: DataManagerConfiguration):
        """Create generic async infrastructure with existing features."""
        
        # Create time estimation engine (preserve existing logic)
        cache_dir = Path.home() / ".ktrdr" / "cache"
        cache_file = cache_dir / "progress_time_estimation.pkl"
        config.time_estimation_engine = TimeEstimationEngine(cache_file)
        
        # Create data progress renderer with existing features
        config.data_progress_renderer = DataProgressRenderer(
            time_estimation_engine=config.time_estimation_engine,
            enable_hierarchical_progress=True
        )
        
        # Create generic progress manager
        config.generic_progress_manager = GenericProgressManager(
            renderer=config.data_progress_renderer
        )
        
        logger.info("Created generic async infrastructure with preserved features")
```

**Testing Requirements**:

- [ ] All existing DataManagerBuilder tests pass
- [ ] Builder creates all async infrastructure components
- [ ] Time estimation engine properly configured
- [ ] DataProgressRenderer properly initialized
- [ ] GenericProgressManager properly configured
- [ ] Builder fluent interface preserved
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:

- [ ] Enhanced DataManagerBuilder with async infrastructure
- [ ] Updated DataManagerConfiguration with async components
- [ ] Integration validation tests
- [ ] Builder pattern preservation tests

---

### Task 1.4: Integrate Enhanced DataManager with Async Infrastructure

**Day**: 4  
**Assignee**: AI IDE Agent  
**Priority**: 9  
**Depends on**: Task 1.3

**Description**: Update DataManager to use the enhanced configuration with generic async infrastructure while maintaining 100% backward compatibility with existing public API.

**Acceptance Criteria**:

- [ ] DataManager constructor accepts enhanced configuration
- [ ] load_data() method uses GenericProgressManager instead of creating ProgressManager directly
- [ ] All existing progress callback patterns work identically
- [ ] CLI automatically receives enhanced progress messages
- [ ] All existing DataManager public API preserved
- [ ] Legacy ProgressState compatibility maintained

**Implementation Details**:

```python
# File: ktrdr/data/data_manager.py (enhancement)

class DataManager(ServiceOrchestrator):
    """Enhanced DataManager with generic async infrastructure."""
    
    def __init__(self,
                 data_dir: Optional[str] = None,
                 max_gap_percentage: float = 5.0,
                 default_repair_method: str = "ffill",
                 builder: Optional[DataManagerBuilder] = None,
                 builder_config: Optional[DataManagerConfiguration] = None):  # NEW
        """Initialize DataManager with optional enhanced configuration."""
        
        # Existing initialization logic preserved
        if builder is None:
            builder = (
                create_default_datamanager_builder()
                .with_data_directory(data_dir)
                .with_gap_settings(max_gap_percentage)
                .with_repair_method(default_repair_method)
            )
        
        # Extract components from builder
        built_config = builder_config or builder.get_configuration()
        
        # Store existing components (preserved)
        self.data_loader = built_config.data_loader
        self.data_validator = built_config.data_validator
        self.gap_classifier = built_config.gap_classifier
        self.gap_analyzer = built_config.gap_analyzer
        self.segment_manager = built_config.segment_manager
        self.data_processor = built_config.data_processor
        self.data_loading_orchestrator = built_config.data_loading_orchestrator
        self.health_checker = built_config.health_checker
        self._external_provider = built_config.external_provider
        
        # Store existing configuration (preserved)
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method
        
        # NEW: Store async infrastructure
        self._generic_progress_manager = built_config.generic_progress_manager
        self._data_progress_renderer = built_config.data_progress_renderer
        
        # Call parent constructor
        super().__init__()
        
        logger.info(f"DataManager initialized with async infrastructure: {built_config.generic_progress_manager is not None}")
    
    def load_data(self, symbol: str, timeframe: str, mode: str = "local",
                  progress_callback: Optional[Callable] = None, **kwargs) -> pd.DataFrame:
        """Load data using enhanced async infrastructure with backward compatibility."""
        
        # Create legacy-compatible progress callback wrapper
        enhanced_callback = None
        if progress_callback:
            enhanced_callback = self._create_legacy_callback_wrapper(progress_callback)
        
        # Configure GenericProgressManager for this operation
        if self._generic_progress_manager:
            # Create new instance for this operation (preserve existing pattern)
            operation_progress = GenericProgressManager(
                callback=enhanced_callback,
                renderer=self._data_progress_renderer
            )
        else:
            # Fallback to existing ProgressManager if async infrastructure not available
            from ktrdr.data.components.progress_manager import ProgressManager
            operation_progress = ProgressManager(progress_callback)
            return self._load_with_fallback_legacy(symbol, timeframe, mode, operation_progress, **kwargs)
        
        # Start operation with data context
        operation_progress.start_operation(
            operation_id=f"load_data_{symbol}_{timeframe}",
            total_steps=5,  # Preserve existing step count
            context={
                'symbol': symbol,
                'timeframe': timeframe,
                'mode': mode,
                'operation_type': 'data_load',
                **kwargs
            }
        )
        
        # Use enhanced _load_with_fallback
        try:
            result = self._load_with_fallback_enhanced(
                symbol=symbol,
                timeframe=timeframe,
                mode=mode,
                progress_manager=operation_progress,
                **kwargs
            )
            
            operation_progress.complete_operation()
            return result
            
        except Exception as e:
            logger.error(f"Data load failed: {e}")
            raise
    
    def _create_legacy_callback_wrapper(self, legacy_callback: Callable) -> Callable:
        """Wrap legacy progress callback to work with GenericProgressState."""
        
        def wrapper(generic_state: GenericProgressState):
            # Convert to legacy ProgressState
            legacy_state = self._data_progress_renderer.create_legacy_compatible_state(generic_state)
            legacy_callback(legacy_state)
        
        return wrapper
    
    def _load_with_fallback_enhanced(self, symbol: str, timeframe: str, mode: str,
                                   progress_manager: GenericProgressManager, **kwargs) -> pd.DataFrame:
        """Enhanced _load_with_fallback using GenericProgressManager."""
        
        # Step 1: Validate symbol and timeframe
        progress_manager.update_progress(
            step=1,
            message="Validating symbol and timeframe",
            context={'current_step_name': 'validation', 'current_operation': 'validation'}
        )
        # ... existing validation logic
        
        # Step 2: Check local data availability  
        progress_manager.update_progress(
            step=2,
            message="Checking local data availability",
            context={'current_step_name': 'local_check', 'current_operation': 'local_data'}
        )
        # ... existing local data logic
        
        # Continue with existing steps using enhanced progress reporting
        # ... all remaining steps with progress_manager.update_progress()
        
        return result
    
    def _load_with_fallback_legacy(self, symbol: str, timeframe: str, mode: str,
                                 progress_manager, **kwargs) -> pd.DataFrame:
        """Fallback to existing ProgressManager logic if async infrastructure unavailable."""
        # Preserve existing _load_with_fallback logic exactly
        return self._load_with_fallback_original(symbol, timeframe, mode, progress_manager, **kwargs)
```

**Testing Requirements**:

- [ ] All existing DataManager tests pass without modification
- [ ] load_data() produces enhanced progress messages
- [ ] Legacy progress callbacks receive identical ProgressState objects
- [ ] CLI commands show improved progress automatically
- [ ] Performance regression testing (no >5% slowdown)
- [ ] Backward compatibility with all existing usage patterns
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:

- [ ] Enhanced DataManager with async infrastructure integration
- [ ] Legacy callback wrapper for backward compatibility
- [ ] Enhanced _load_with_fallback with improved progress reporting
- [ ] Comprehensive integration test validation

---

### Task 1.5: Clean Up Legacy Progress Code and Validate Complete Integration

**Day**: 5  
**Assignee**: AI IDE Agent  
**Priority**: 10  
**Depends on**: Task 1.4

**Description**: Clean up redundant progress code from the original ProgressManager, validate complete integration, and ensure all slice goals are met with comprehensive testing.

**Acceptance Criteria**:

- [ ] Remove domain-specific logic from original ProgressManager component
- [ ] Validate all existing functionality preserved with enhanced capabilities
- [ ] All existing tests pass + comprehensive new test coverage
- [ ] CLI integration shows enhanced progress messages
- [ ] Performance benchmarking shows no regressions
- [ ] Complete slice validation and readiness for Slice 2

**Implementation Details**:

#### Clean Up Original ProgressManager

```python
# File: ktrdr/data/components/progress_manager.py (cleanup)

# REMOVE: Domain-specific message enhancement logic (moved to DataProgressRenderer)
# REMOVE: _create_enhanced_message() method
# REMOVE: Symbol/timeframe/mode specific logic
# PRESERVE: TimeEstimationEngine (used by DataProgressRenderer)
# PRESERVE: Thread-safe infrastructure
# PRESERVE: Legacy compatibility for components not yet migrated

class ProgressManager:
    """Simplified ProgressManager - domain logic moved to DataProgressRenderer."""
    
    def __init__(self, callback_func: Optional[Callable] = None, **kwargs):
        """Simplified constructor - complex logic moved to generic infrastructure."""
        self.callback = callback_func
        # Preserve essential functionality for components not yet migrated
        
    # Keep essential methods for backward compatibility
    # Remove complex enhancement logic (now in DataProgressRenderer)
```

#### Validation Strategy

1. **Regression Testing**: Run complete existing test suite
2. **Enhancement Validation**: Verify progress messages are improved
3. **Performance Testing**: Benchmark against baseline
4. **Integration Testing**: Test with CLI commands
5. **Feature Parity Testing**: Compare old vs new progress outputs

**Testing Requirements**:

- [ ] 100% existing test suite passes
- [ ] Enhanced progress messages validated in CLI
- [ ] Performance benchmarking shows <5% overhead
- [ ] Memory usage stable with new infrastructure
- [ ] Thread safety validated under concurrent operations
- [ ] Legacy component compatibility maintained
- [ ] Complete test suite: `make test` must pass
- [ ] Quality checks: `make quality` must pass

**Deliverables**:

- [ ] Cleaned up legacy ProgressManager code
- [ ] Complete slice validation report
- [ ] Performance benchmark comparison
- [ ] Enhanced progress message examples
- [ ] Integration validation with CLI commands
- [ ] Foundation readiness assessment for Slice 2

---

## Integration Points for Future Slices

### Slice 2 Integration Readiness

- [ ] GenericProgressManager designed to accept CancellationToken
- [ ] Progress update points identified for cancellation checks
- [ ] Thread safety established for cancellation integration
- [ ] DataProgressRenderer ready for cancellation context

## Success Metrics

### Functional Metrics

- [ ] 100% existing functionality preserved
- [ ] Enhanced progress messages visible in CLI (symbol/timeframe/mode context)
- [ ] Zero breaking changes to public APIs
- [ ] All existing tests passing + comprehensive new coverage

### Quality Metrics

- [ ] >95% code coverage for new async infrastructure
- [ ] <5% performance impact on data operations
- [ ] Thread safety validated under concurrent operations
- [ ] Clean separation between generic and domain-specific code

### User Experience Metrics

- [ ] Progress messages now include symbol, timeframe, and mode context
- [ ] Time estimation preserved and functional
- [ ] Step progress clearly indicated [current/total]
- [ ] Hierarchical progress preserved (Operation → Steps → Sub-steps)

## Risk Mitigation

### Technical Risks

- **Risk**: Breaking existing progress functionality
- **Mitigation**: Comprehensive feature mapping and extensive regression testing

- **Risk**: Performance degradation from abstraction layer
- **Mitigation**: Lightweight implementation with performance benchmarking

- **Risk**: Loss of sophisticated time estimation features
- **Mitigation**: Complete TimeEstimationEngine preservation in DataProgressRenderer

### Integration Risks

- **Risk**: Complex integration with existing DataManager builder pattern
- **Mitigation**: Incremental enhancement with step-by-step validation

- **Risk**: Thread safety issues with concurrent operations
- **Mitigation**: RLock usage and concurrent testing validation

### Compatibility Risks

- **Risk**: Breaking existing CLI progress displays
- **Mitigation**: Legacy callback wrapper with identical ProgressState conversion

- **Risk**: Component integration issues with existing architecture
- **Mitigation**: Builder pattern enhancement preserves existing component creation

## Commit Strategy

**Each task must commit with comprehensive testing:**

```bash
# Before committing each task:
make test          # All tests must pass
make quality       # All quality checks must pass

git add .
git commit -m "feat(slice-1): [task description]

- Specific changes made
- Features preserved
- Integration points completed
- All tests passing

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Notes

This slice establishes the foundation for generic async infrastructure while preserving ALL the excellent existing features. The sophisticated time estimation, hierarchical progress, and contextual messaging that makes the current ProgressManager so valuable are preserved and enhanced through the domain renderer pattern.

The focus on working WITH the existing architecture (rather than replacing it) ensures zero disruption to current functionality while building the foundation for training system integration in Slice 4.
