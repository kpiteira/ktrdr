# Phase 2: DataManager Decomposition - Detailed Implementation Plan

## Phase Overview

Phase 2 focuses on decomposing the 2600-line DataManager god class into focused, single-responsibility components. This phase builds on the foundation established in Phase 1 and creates the core components that will handle data operations efficiently.

**Dependencies**: Phase 2 requires completion of Phase 1 (ProgressManager and AsyncHostService base class).

**Duration**: 3-4 weeks of focused development

**Branch Strategy**: `feature/datamanager-decomposition` (main development branch for Phase 2)

## Core Architecture

The decomposition follows incremental extraction + integration pattern:

```
DataManager (existing orchestrator - refactored incrementally)
├── self.gap_analyzer = GapAnalyzer()        # Extract → Integrate → Replace methods
├── self.segment_manager = SegmentManager()  # Extract → Integrate → Replace methods  
├── self.data_fetcher = DataFetcher()        # Extract → Integrate → Replace methods
├── self.data_validator = DataValidator()    # Extract → Integrate → Replace methods
└── self.data_processor = DataProcessor()    # Extract → Integrate → Replace methods
```

**Key Principle**: Each component is extracted AND immediately integrated into the existing DataManager, replacing the corresponding god-class methods while maintaining 100% API compatibility.

## Task List

### TASK-2.1: Create GapAnalyzer Component

**Type**: Create new component  
**Branch**: `feature/gap-analyzer-component` (branches from `feature/datamanager-decomposition`)  
**Files**: `ktrdr/data/components/gap_analyzer.py`, tests  
**Dependencies**: Phase 1 complete (ProgressManager available)

#### Description
Extract gap analysis logic from DataManager into a focused component that handles gap detection and classification based on loading modes. **Immediately integrate the component into DataManager and replace the corresponding god-class methods.**

#### Acceptance Criteria
- [ ] GapAnalyzer handles all four modes (local, tail, backfill, full)
- [ ] Maintains exact compatibility with current gap detection logic
- [ ] Returns structured gap information (start/end dates, priority, estimated size)
- [ ] Integrates with ProgressManager for operation reporting
- [ ] Handles edge cases (no local data, overlapping gaps, invalid date ranges)
- [ ] Performance matches or exceeds current implementation
- [ ] **Integrated into DataManager constructor: `self.gap_analyzer = GapAnalyzer()`**
- [ ] **DataManager methods delegate to component (e.g., `self.gap_analyzer.analyze_gaps()`)**
- [ ] **Original god-class gap analysis methods removed after integration**

#### Test-Driven Development Approach

**Unit Tests Required**:
Write failing tests first that verify gap analysis behavior across different scenarios. Focus on testing the core gap detection algorithm with various data scenarios including empty datasets, partial coverage, and full coverage cases.

**Integration Tests Required**:
Test the component's integration with LocalDataLoader to ensure accurate gap detection when local data exists. Verify that the component correctly identifies gaps at data boundaries and handles timezone-aware date comparisons.

**Edge Case Tests Required**:
Test boundary conditions such as requesting data before the earliest available date, handling gaps that span weekends/holidays, and processing requests with invalid date ranges.

#### Implementation Details

**Location**: `ktrdr/data/components/gap_analyzer.py`

**Key Methods**:
- `analyze_gaps()` - Main gap detection logic with mode-specific behavior
- `classify_gap_priority()` - Determines fetch priority based on gap characteristics  
- `estimate_gap_size()` - Calculates estimated data points for progress reporting

**Integration Points**:
- Must work with `LocalDataLoader` to determine existing data coverage
- Reports progress through `ProgressManager` during analysis
- Returns gap information compatible with `SegmentManager` input requirements

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/gap-analyzer-component feature/datamanager-decomposition`
2. **Development commits**: Frequent, focused commits for each method implementation
3. **PR Requirements**: 
   - All tests passing (unit, integration, edge cases)
   - MyPy type checking clean
   - 95%+ test coverage for the component
   - Performance benchmarks showing no regression

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/components/test_gap_analyzer.py -v` - Component tests pass
- `uv run mypy ktrdr/data/components/gap_analyzer.py` - Type checking passes
- `uv run black ktrdr/data/components/gap_analyzer.py tests/data/components/test_gap_analyzer.py` - Code formatting applied
- `uv run ruff ktrdr/data/components/gap_analyzer.py` - Linting passes
- `uv run bandit ktrdr/data/components/gap_analyzer.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/ -k gap_analyzer` - All related tests pass
- `uv run pytest --cov=ktrdr.data.components.gap_analyzer --cov-report=term-missing` - Coverage verification
- Performance comparison tests showing no regression from current DataManager gap analysis

#### PR Guidelines

**PR Title**: `feat: implement GapAnalyzer component for DataManager decomposition`

**PR Description Template**:
```markdown
## Summary
Extracts gap analysis logic from DataManager into focused GapAnalyzer component.

## Changes
- New GapAnalyzer class with mode-specific gap detection
- Comprehensive test suite covering all modes and edge cases  
- Performance benchmarks showing equivalent or better performance
- Integration with ProgressManager for operation tracking

## Testing
- [ ] Unit tests for all gap detection scenarios
- [ ] Integration tests with LocalDataLoader
- [ ] Edge case handling (empty data, invalid ranges, etc.)
- [ ] Performance benchmarks vs current implementation

## Quality Checks
- [ ] All tests passing
- [ ] Type checking clean (MyPy)
- [ ] Code formatted (Black) and linted (Ruff)
- [ ] Security scan clean (Bandit)
- [ ] 95%+ test coverage
```

**Review Requirements**:
- Code review focusing on gap detection logic correctness
- Performance review comparing benchmarks
- Architecture review ensuring component fits decomposition strategy

### TASK-2.2: Create SegmentManager Component  

**Type**: Create new component  
**Branch**: `feature/segment-manager-component` (branches from `feature/gap-analyzer-component`)  
**Files**: `ktrdr/data/components/segment_manager.py`, tests  
**Dependencies**: GapAnalyzer component (TASK-2.1)

#### Description
Extract request segmentation logic from DataManager into a component that creates optimal fetch segments based on gap analysis and loading modes.

#### Acceptance Criteria
- [ ] Creates fetch segments with mode-appropriate sizing strategies
- [ ] Handles segment prioritization for efficient fetching
- [ ] Manages segment retry logic and failure handling
- [ ] Reports segmentation progress through ProgressManager
- [ ] Maintains compatibility with current segmentation behavior
- [ ] Optimizes segment sizes based on data density and timeframe

#### Test-Driven Development Approach

**Unit Tests Required**:
Write failing tests that verify segment creation logic for different gap sizes and modes. Test that segments are appropriately sized for efficient IB Gateway communication while respecting rate limits.

**Integration Tests Required**:
Test integration with GapAnalyzer output to ensure segments properly cover identified gaps. Verify that segment prioritization works correctly when multiple gaps exist.

**Performance Tests Required**:
Test segment creation performance with large gap sets and verify that segmentation doesn't become a bottleneck in the data loading process.

#### Implementation Details

**Location**: `ktrdr/data/components/segment_manager.py`

**Key Methods**:
- `create_segments()` - Generate fetch segments from gap analysis
- `prioritize_segments()` - Order segments for optimal fetching
- `handle_segment_retry()` - Manage failed segment retry logic

**Segmentation Strategy**:
Different segment sizes per mode to optimize for typical use cases:
- **tail mode**: Small segments (1-7 days) for recent data
- **backfill mode**: Larger segments (30-90 days) for historical data  
- **full mode**: Mixed strategy based on gap characteristics

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/segment-manager-component feature/gap-analyzer-component`
2. **Wait for GapAnalyzer PR merge** before starting implementation
3. **Development commits**: Focus on one segmentation strategy at a time
4. **PR Requirements**: Integration tests with GapAnalyzer, performance benchmarks

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/components/test_segment_manager.py -v` - Component tests pass
- `uv run mypy ktrdr/data/components/segment_manager.py` - Type checking passes
- `uv run black ktrdr/data/components/segment_manager.py tests/data/components/test_segment_manager.py` - Formatting applied
- `uv run ruff ktrdr/data/components/segment_manager.py` - Linting passes
- `uv run bandit ktrdr/data/components/segment_manager.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/ -k "gap_analyzer or segment_manager"` - Integration tests pass
- `uv run pytest --cov=ktrdr.data.components.segment_manager --cov-report=term-missing` - Coverage verification
- Performance tests comparing segmentation efficiency

#### PR Guidelines

**PR Title**: `feat: implement SegmentManager component for optimal fetch segmentation`

**Review Focus**: Segmentation algorithm efficiency, integration with GapAnalyzer, segment sizing strategies

### TASK-2.3: Create DataFetcher Component

**Type**: Create new component  
**Branch**: `feature/data-fetcher-component` (branches from `feature/segment-manager-component`)  
**Files**: `ktrdr/data/components/data_fetcher.py`, tests  
**Dependencies**: SegmentManager component (TASK-2.2)

#### Description  
Extract data fetching logic from DataManager into a component that handles IB communication, retries, rate limiting, and incremental saving with detailed progress reporting.

#### Acceptance Criteria
- [ ] Fetches segments with proper retry logic and backoff strategies
- [ ] Handles IB Gateway rate limiting and connection management
- [ ] Provides detailed progress reporting for long-running operations
- [ ] Supports operation cancellation at segment boundaries
- [ ] Implements incremental saving to prevent data loss
- [ ] Maintains compatibility with current IB communication patterns

#### Test-Driven Development Approach

**Unit Tests Required**:
Write failing tests for retry logic, rate limiting behavior, and progress reporting accuracy. Test that the component properly handles various IB Gateway error conditions and timeout scenarios.

**Integration Tests Required**:
Test integration with SegmentManager to ensure proper segment processing order. Verify that progress reporting accurately reflects fetch completion across multiple segments.

**Mock Tests Required**:
Use IB Gateway mocks to test retry strategies, rate limiting, and error handling without requiring actual IB connections. Ensure the component behaves correctly under various network conditions.

#### Implementation Details

**Location**: `ktrdr/data/components/data_fetcher.py`

**Key Features**:
- Wraps `IbDataAdapter` with enhanced retry and progress logic
- Implements exponential backoff for failed requests
- Provides cancellation points between segment fetches
- Reports progress at segment and sub-segment levels
- Handles incremental data saving to prevent loss

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/data-fetcher-component feature/segment-manager-component`
2. **Wait for SegmentManager PR merge** before starting
3. **Development approach**: Implement fetching logic first, then add progress/cancellation features
4. **PR Requirements**: Comprehensive IB Gateway integration tests

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/components/test_data_fetcher.py -v` - Component tests pass
- `uv run mypy ktrdr/data/components/data_fetcher.py` - Type checking passes  
- `uv run black ktrdr/data/components/data_fetcher.py tests/data/components/test_data_fetcher.py` - Formatting applied
- `uv run ruff ktrdr/data/components/data_fetcher.py` - Linting passes
- `uv run bandit ktrdr/data/components/data_fetcher.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/ -k "data_fetcher"` - All fetcher tests pass
- `uv run pytest tests/integration/test_ib_integration.py` - IB integration tests pass
- Network resilience tests with connection failures and timeouts
- Performance tests ensuring no regression in fetch speeds

#### PR Guidelines

**PR Title**: `feat: implement DataFetcher component with progress and retry capabilities`

**Review Focus**: IB integration correctness, retry logic robustness, progress reporting accuracy

### TASK-2.4: Create DataValidator Component

**Type**: Create new component  
**Branch**: `feature/data-validator-component` (branches from `feature/data-fetcher-component`)  
**Files**: `ktrdr/data/components/data_validator.py`, tests  
**Dependencies**: DataFetcher component (TASK-2.3)

#### Description
Extract data validation and quality checking logic from DataManager into a focused component that handles data integrity, gap detection in fetched data, and automatic repair strategies.

#### Acceptance Criteria
- [ ] Validates data completeness and identifies missing periods
- [ ] Detects and handles data quality issues (outliers, invalid values)
- [ ] Implements automatic repair strategies for common data problems
- [ ] Provides detailed validation reporting and recommendations
- [ ] Maintains backward compatibility with current validation logic
- [ ] Supports different validation strictness levels based on use case

#### Test-Driven Development Approach

**Unit Tests Required**:
Write failing tests for various data quality scenarios including missing data points, extreme outliers, and invalid price sequences. Test that validation rules correctly identify problematic data while avoiding false positives.

**Data Quality Tests Required**:
Test validation behavior with real-world data anomalies such as stock splits, dividend adjustments, and trading halts. Ensure the component can distinguish between actual market events and data quality issues.

**Repair Strategy Tests Required**:
Test automatic repair mechanisms such as interpolation for small gaps and outlier correction. Verify that repairs maintain data integrity and don't introduce artifacts that affect analysis.

#### Implementation Details

**Location**: `ktrdr/data/components/data_validator.py`

**Validation Categories**:
- **Completeness**: Check for missing time periods within expected ranges
- **Consistency**: Verify price relationships (High >= Low, etc.)
- **Quality**: Detect outliers and suspicious patterns
- **Repair**: Automatic fixes for common issues

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/data-validator-component feature/data-fetcher-component`
2. **Wait for DataFetcher PR merge** before starting
3. **Development approach**: Implement validation rules first, then repair strategies
4. **PR Requirements**: Extensive data quality test coverage

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/components/test_data_validator.py -v` - Component tests pass
- `uv run mypy ktrdr/data/components/data_validator.py` - Type checking passes
- `uv run black ktrdr/data/components/data_validator.py tests/data/components/test_data_validator.py` - Formatting applied
- `uv run ruff ktrdr/data/components/data_validator.py` - Linting passes
- `uv run bandit ktrdr/data/components/data_validator.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/ -k "data_validator"` - All validator tests pass
- `uv run pytest --cov=ktrdr.data.components.data_validator --cov-report=term-missing` - Coverage verification
- Data quality tests with various market anomaly scenarios

#### PR Guidelines

**PR Title**: `feat: implement DataValidator component for data quality assurance`

**Review Focus**: Validation rule correctness, repair strategy safety, performance impact

### TASK-2.5: Create DataProcessor Component

**Type**: Create new component  
**Branch**: `feature/data-processor-component` (branches from `feature/data-validator-component`)  
**Files**: `ktrdr/data/components/data_processor.py`, tests  
**Dependencies**: DataValidator component (TASK-2.4)

#### Description
Extract data processing logic from DataManager into a component that handles merging, resampling, transformation, and final data preparation for storage and analysis.

#### Acceptance Criteria
- [ ] Merges fetched data segments with existing local data
- [ ] Handles resampling between different timeframes
- [ ] Applies data transformations (timezone conversions, format standardization)
- [ ] Manages data deduplication and conflict resolution
- [ ] Reports processing progress for large datasets
- [ ] Maintains compatibility with current data processing pipeline

#### Test-Driven Development Approach

**Unit Tests Required**:
Write failing tests for data merging scenarios including overlapping data, duplicate timestamps, and timezone mismatches. Test resampling accuracy across different timeframe conversions.

**Integration Tests Required**:
Test the complete processing pipeline from raw fetched data to final processed output. Verify that processed data maintains consistency with existing local data formats.

**Performance Tests Required**:
Test processing performance with large datasets to ensure the component doesn't become a bottleneck. Verify that memory usage remains reasonable during processing of extended historical data.

#### Implementation Details

**Location**: `ktrdr/data/components/data_processor.py`

**Processing Pipeline**:
1. **Merge**: Combine new data with existing local data
2. **Deduplicate**: Remove duplicate entries and resolve conflicts
3. **Resample**: Convert between timeframes if needed
4. **Transform**: Apply format standardization and timezone conversion
5. **Validate**: Final validation before storage

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/data-processor-component feature/data-validator-component`
2. **Wait for DataValidator PR merge** before starting
3. **Development approach**: Implement core processing logic first, then optimization features
4. **PR Requirements**: Performance benchmarks, memory usage analysis

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/components/test_data_processor.py -v` - Component tests pass
- `uv run mypy ktrdr/data/components/data_processor.py` - Type checking passes
- `uv run black ktrdr/data/components/data_processor.py tests/data/components/test_data_processor.py` - Formatting applied
- `uv run ruff ktrdr/data/components/data_processor.py` - Linting passes
- `uv run bandit ktrdr/data/components/data_processor.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/ -k "data_processor"` - All processor tests pass
- `uv run pytest --cov=ktrdr.data.components.data_processor --cov-report=term-missing` - Coverage verification
- Performance benchmarks with large dataset processing
- Memory usage profiling during intensive processing operations

#### PR Guidelines

**PR Title**: `feat: implement DataProcessor component for data merging and transformation`

**Review Focus**: Processing accuracy, performance optimization, memory management

### TASK-2.6: Complete DataManager Component Integration

**Type**: Integration cleanup and god-class method removal  
**Branch**: `feature/datamanager-integration-cleanup` (branches from `feature/datamanager-decomposition`)  
**Files**: `ktrdr/data/data_manager.py` (refactored incrementally), tests  
**Dependencies**: All Phase 2 components integrated (TASK-2.1 through TASK-2.5)

#### Description
Complete the DataManager refactoring by removing any remaining god-class methods and ensuring all functionality delegates to the extracted and integrated components. The DataManager should be a clean orchestrator that coordinates the specialized components while maintaining 100% API compatibility.

#### Acceptance Criteria
- [ ] All god-class methods removed from DataManager (reduced from 2600+ to ~800 lines)
- [ ] Maintains 100% API compatibility with existing DataManager
- [ ] All functionality delegates to integrated components (`self.gap_analyzer`, `self.data_fetcher`, etc.)
- [ ] Implements clean async patterns throughout the workflow
- [ ] Coordinates all components with proper error handling
- [ ] Provides equivalent or better performance than original implementation
- [ ] Supports all existing loading modes and options

#### Test-Driven Development Approach

**Integration Tests Required**:
Write comprehensive failing tests that verify the complete data loading workflow works identically to the current implementation. Test all loading modes, error scenarios, and edge cases that the current DataManager handles.

**API Compatibility Tests Required**:
Test that all existing DataManager method signatures and behaviors are preserved. Ensure that services and CLI components can use the new DataManager without any changes.

**Performance Tests Required**:
Create benchmarks comparing the new orchestrator performance against the current monolithic implementation. Verify that the decomposition doesn't introduce performance regressions.

#### Implementation Details

**Location**: `ktrdr/data/data_manager.py` (incremental refactoring)

**Current Architecture** (already partially implemented):
```python
class DataManager(ServiceOrchestrator):
    def __init__(self):
        # Components already integrated:
        self.gap_analyzer = GapAnalyzer(gap_classifier=self.gap_classifier)        # ✅ Done
        self.segment_manager = SegmentManager()                                    # ✅ Done  
        self._data_fetcher = DataFetcher()                                        # ✅ Done
        self.data_validator = DataQualityValidator()                              # ✅ Done
        # TODO: Remaining integrations and cleanup

    async def load_data(self, symbol: str, timeframe: str, **options) -> pd.DataFrame:
        # Already delegates to components in _load_with_fallback():
        # 1. gaps = self.gap_analyzer.analyze_gaps(...)          # ✅ Line 1523
        # 2. segments = self.segment_manager.create_segments(...) # ✅ Line 1556  
        # 3. await self._data_fetcher.fetch_segments_async(...)  # ✅ Line 1044
        # 4. self.data_validator.validate_data(...)             # ✅ Line 448
        # TODO: Complete remaining method delegations
```

#### Branching Strategy

1. **Continue incremental approach** - components are already being integrated
2. **Create cleanup branch**: `git checkout -b feature/datamanager-integration-cleanup feature/datamanager-decomposition`
3. **Implementation approach**: 
   - **NO parallel implementation** - continue refactoring existing DataManager
   - Remove remaining god-class methods after verifying component delegation works
   - Each component integration maintains backward compatibility
4. **PR Requirements**: Regression testing focused on method delegation, performance analysis

#### User Testing Integration

**User Testing Required**: Yes - This is a major architectural change that affects core system functionality

**Testing Approach**:
1. **Parallel Implementation**: Run both old and new DataManager in parallel with identical inputs
2. **Gradual Migration**: Use feature flags to gradually migrate specific symbols/timeframes
3. **User Validation**: Request user testing with real trading workflows before full migration

**User Testing Branch**: `feature/datamanager-user-testing` (branches from orchestrator branch)

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/data/test_data_manager.py -v` - New DataManager tests pass
- `uv run pytest tests/data/test_data_manager_compatibility.py -v` - API compatibility tests pass
- `uv run mypy ktrdr/data/data_manager.py` - Type checking passes
- `uv run black ktrdr/data/data_manager.py` - Code formatting applied
- `uv run ruff ktrdr/data/data_manager.py` - Linting passes
- `uv run bandit ktrdr/data/data_manager.py` - Security scan clean

**Before PR creation**:
- `uv run pytest tests/data/` - All data module tests pass
- `uv run pytest tests/integration/` - Integration tests pass
- Performance regression testing across all loading modes
- Memory usage comparison with current implementation

#### PR Guidelines

**PR Title**: `feat: implement new DataManager orchestrator with component decomposition`

**PR Description Template**:
```markdown
## Summary
Replaces 2600-line DataManager god class with clean orchestrator coordinating specialized components.

## Architecture Changes
- DataManager reduced from 2600 to <400 lines
- Component pipeline: GapAnalyzer → SegmentManager → DataFetcher → DataValidator → DataProcessor
- Clean async patterns throughout
- Maintains 100% API compatibility

## Performance Impact
- [Include benchmark comparisons]
- [Memory usage analysis]
- [Loading time comparisons across modes]

## Testing
- [ ] Full regression test suite passes
- [ ] API compatibility verified
- [ ] Performance benchmarks show no regression
- [ ] User testing completed successfully

## Migration Plan
- Feature flags enable gradual rollout
- Parallel implementation allows safe transition
- Rollback plan available if issues discovered
```

**Review Requirements**:
- Architecture review by senior developers
- Performance review with benchmark analysis
- User testing completion before merge approval

### TASK-2.7: Performance Optimization and Monitoring

**Type**: Performance enhancement  
**Branch**: `feature/datamanager-performance-optimization` (branches from orchestrator branch)  
**Files**: Performance monitoring, optimization tweaks  
**Dependencies**: New DataManager orchestrator (TASK-2.6)

#### Description
Optimize the decomposed DataManager architecture for performance and implement monitoring to ensure the component-based approach delivers equivalent or better performance than the monolithic version.

#### Acceptance Criteria
- [ ] Performance meets or exceeds current DataManager benchmarks
- [ ] Memory usage optimized for large data operations
- [ ] Component communication overhead minimized
- [ ] Performance monitoring and metrics collection implemented
- [ ] Optimization opportunities identified and implemented

#### Test-Driven Development Approach

**Performance Tests Required**:
Write failing benchmark tests that establish performance targets based on current DataManager metrics. Test various scenarios including large historical loads, concurrent operations, and memory-intensive processing.

**Monitoring Tests Required**:
Test that performance monitoring correctly captures component-level metrics and identifies bottlenecks. Verify that monitoring overhead doesn't significantly impact overall performance.

**Optimization Tests Required**:
Test specific optimization strategies such as connection pooling, caching, and async operation parallelization. Ensure optimizations don't compromise data integrity or reliability.

#### Implementation Details

**Optimization Areas**:
- Connection pooling for IB Gateway communication
- Caching of gap analysis results
- Parallel processing of independent segments
- Memory usage optimization for large datasets

#### Branching Strategy

1. **Create feature branch**: `git checkout -b feature/datamanager-performance-optimization feature/new-datamanager-orchestrator`
2. **Wait for orchestrator PR merge** before starting
3. **Development approach**: Profile first, optimize second, measure results
4. **PR Requirements**: Performance improvement documentation

#### Quality Assurance Requirements

**Before each commit**:
- `uv run pytest tests/performance/test_datamanager_benchmarks.py -v` - Performance tests pass
- `uv run mypy ktrdr/data/` - Type checking passes across data module
- `uv run black ktrdr/data/` - All data module code formatted
- `uv run ruff ktrdr/data/` - All data module linting passes
- `uv run bandit ktrdr/data/` - Security scan clean across data module

**Before PR creation**:
- Performance benchmark comparison showing improvements
- Memory usage analysis demonstrating optimization
- Load testing results under various scenarios

#### PR Guidelines

**PR Title**: `perf: optimize DataManager component architecture for performance`

**Review Focus**: Performance improvement verification, monitoring effectiveness, optimization safety

## Phase 2 Completion Criteria

### Technical Milestones

- [ ] All 5 components implemented and tested (GapAnalyzer, SegmentManager, DataFetcher, DataValidator, DataProcessor)
- [ ] New DataManager orchestrator operational and backward compatible
- [ ] Performance meets or exceeds current implementation
- [ ] All existing data loading workflows function identically
- [ ] Component integration tested across all loading modes

### Quality Gates

- [ ] 95%+ test coverage across all new components
- [ ] Zero MyPy type checking errors
- [ ] All linting (Black, Ruff) and security (Bandit) checks pass
- [ ] Performance regression testing shows no degradation
- [ ] User testing completed successfully on real workflows

### User Acceptance Testing

**User Testing Scenarios**:
1. **Daily Data Updates**: Test tail mode loading for routine data updates
2. **Historical Analysis**: Test backfill mode for research and backtesting
3. **New Symbol Setup**: Test full mode for complete data initialization
4. **Error Recovery**: Test system behavior under various failure conditions

**User Testing Success Criteria**:
- All current workflows function without modification
- Performance is equivalent or better than current system
- Error handling and progress reporting work as expected
- User can successfully cancel long-running operations

### Documentation Requirements

- [ ] Component API documentation complete
- [ ] Architecture decision records for decomposition approach
- [ ] Performance analysis and optimization guide
- [ ] Migration guide for future component modifications

## Next Steps

Upon Phase 2 completion, proceed to **Phase 3**: Complete async integration and CLI optimization. Phase 3 will focus on optimizing the CLI layer, implementing connection pooling, and establishing the final async architecture patterns across the entire system.