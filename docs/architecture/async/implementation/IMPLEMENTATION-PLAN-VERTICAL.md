# Vertical Implementation Plan: DataManager-Focused Refactoring

## Overview

This implementation plan follows a vertical, incremental approach focused on decomposing and improving DataManager. Each task delivers immediate, testable value while building toward the unified async architecture. No code is created without immediate integration and testing.

## Planning Principles

### Vertical Development
Each task adds a component to DataManager and immediately integrates it, ensuring every piece of code is tested and working from day one.

### Immediate Value Delivery
Every task improves the current DataManager's maintainability, testability, or performance, providing tangible benefits even if the full migration isn't completed.

### Atomic Improvements
Each task is self-contained and can be deployed independently. If we need to stop mid-migration, we're left with an improved DataManager, not broken code.

### Test-Driven Decomposition
Extract components by first writing tests that validate current behavior, then refactor to use the component while maintaining identical behavior.

## Phase 1: DataManager Decomposition Foundation
**Duration**: 3 weeks  
**Goal**: Begin breaking down DataManager while maintaining and improving functionality

### Phase 1 Success Criteria
- DataManager complexity reduced by extracting first components
- All existing tests continue to pass
- New components are fully tested and integrated
- Performance maintained or improved
- Clear foundation for further decomposition

### Task 1.1a: Create ProgressManager Component
**Priority**: High  
**Type**: Create new component

**Description**: Create the ProgressManager component by analyzing and extracting progress reporting patterns from the current DataManager.

**Acceptance Criteria**:
- ProgressManager handles all current DataManager progress patterns
- Thread-safe progress state management implemented
- Compatible interface with existing progress callback system
- Component can be instantiated and used independently

**Deliverables**:
- `ktrdr/data/components/progress_manager.py` with complete implementation
- Unit tests for ProgressManager with >95% coverage

### Task 1.1b: Integrate ProgressManager into DataManager  
**Priority**: High  
**Type**: Integration  
**Depends on**: Task 1.1a

**Description**: Replace embedded progress logic in DataManager with ProgressManager instance while maintaining backward compatibility.

**Acceptance Criteria**:
- All existing DataManager progress behavior unchanged
- ProgressManager used in `load_data`, `load_multi_timeframe_data`, and related methods
- All existing progress-related tests continue to pass
- No performance regression

**Deliverables**:
- DataManager using ProgressManager instead of embedded progress logic
- Integration tests validating backward compatibility

### Task 1.1c: Enhance Progress Reporting Capabilities
**Priority**: Medium  
**Type**: Enhancement  
**Depends on**: Task 1.1b

**Description**: Add enhanced progress reporting features using the new ProgressManager component.

**Acceptance Criteria**:
- Better step descriptions for user feedback
- Time estimates for long operations  
- Enhanced CLI progress display validation
- No breaking changes to existing API

**Deliverables**:
- Enhanced progress reporting in CLI commands
- Validation tests for improved user experience

### Task 1.2a: Extract GapAnalyzer Core Logic
**Priority**: High  
**Type**: Extract component

**Description**: Extract gap analysis methods from DataManager into a standalone GapAnalyzer component.

**Acceptance Criteria**:
- Extract `_analyze_gaps`, `_find_internal_gaps`, `_is_meaningful_gap`, `_gap_contains_trading_days` methods
- GapAnalyzer preserves all existing gap detection behavior
- Clean interface with clear inputs/outputs
- Component can be tested independently

**Deliverables**:
- `ktrdr/data/components/gap_analyzer.py` with extracted logic
- Unit tests replicating existing gap analysis behavior

### Task 1.2b: Add Mode-Aware Gap Analysis
**Priority**: High  
**Type**: Feature enhancement  
**Depends on**: Task 1.2a

**Description**: Enhance GapAnalyzer with mode-specific analysis strategies for local, tail, backfill, and full modes.

**Acceptance Criteria**:
- Different analysis strategies implemented for each mode
- Intelligent gap classification (market closure vs missing data)
- Configuration options for analysis strategies
- ProgressManager integration for analysis progress

**Deliverables**:
- Mode-aware gap analysis capabilities
- Enhanced gap classification logic
- Progress reporting during gap analysis

### Task 1.2c: Integrate GapAnalyzer into DataManager
**Priority**: High  
**Type**: Integration  
**Depends on**: Task 1.2b

**Description**: Replace DataManager's gap analysis methods with GapAnalyzer usage while maintaining full backward compatibility.

**Acceptance Criteria**:
- DataManager uses GapAnalyzer instead of embedded gap analysis
- All existing gap analysis behavior preserved
- Mode parameters passed correctly to GapAnalyzer
- All existing tests continue to pass

**Deliverables**:
- DataManager integration with GapAnalyzer
- Integration tests validating behavior preservation

### Task 1.2d: Validate Enhanced Gap Analysis
**Priority**: Medium  
**Type**: Validation  
**Depends on**: Task 1.2c

**Description**: Comprehensive testing and validation of enhanced gap analysis capabilities.

**Acceptance Criteria**:
- Mode-specific gap analysis thoroughly tested
- Performance validation with large datasets
- Edge case testing completed
- Enhanced capabilities validated in real scenarios

**Deliverables**:
- Comprehensive test suite for enhanced gap analysis
- Performance benchmarks
- Validation report

### Task 1.3: Extract and Integrate SegmentManager Component
**Duration**: 5 days  
**Priority**: High  
**End-to-End Impact**: None (internal refactoring with enhanced capabilities)

**Description**: Extract the segment management logic from DataManager into a component that handles the complex task of splitting data requests into IB-compliant segments.

**Why This Next**: Segment management is tightly coupled with gap analysis but has clear responsibilities. Extracting it creates a clean pipeline: GapAnalyzer → SegmentManager → DataFetcher.

**Detailed Actions**:
1. **Day 1-2: Create SegmentManager with current logic**
   - Extract `_split_into_segments` and related segmentation logic from DataManager
   - Create `ktrdr/data/components/segment_manager.py` with clean interface
   - Preserve all existing IB Gateway compatibility logic
   - Add comprehensive error handling and validation

2. **Day 3: Add mode-aware segmentation enhancements**
   - Implement different segment sizing strategies for different modes
   - Add intelligent segment optimization based on timeframe and historical performance
   - Integrate with ProgressManager for segmentation progress
   - Add segment validation and compatibility checking

3. **Day 4: Integrate back into DataManager**
   - Replace segmentation logic in DataManager with SegmentManager
   - Update `_load_with_fallback` to use GapAnalyzer → SegmentManager pipeline
   - Ensure seamless integration with existing fetching logic
   - Maintain all existing segment behavior

4. **Day 5: Test and validate**
   - Comprehensive segmentation testing across all scenarios
   - IB Gateway compatibility validation
   - Mode-specific segmentation strategy testing
   - Integration testing with GapAnalyzer and existing fetch logic

**Testing Requirements**:
- All existing segmentation tests pass
- Mode-specific segmentation strategy tests
- IB Gateway compatibility tests
- SegmentManager unit tests with edge cases
- Integration tests with GapAnalyzer

**Deliverables**:
- SegmentManager component integrated into DataManager
- Enhanced segmentation strategies
- DataManager with cleaner segmentation logic
- Improved IB Gateway compatibility

### Task 1.4: Improve ServiceOrchestrator and Apply to DataManager
**Duration**: 3 days  
**Priority**: Medium  
**End-to-End Impact**: Positive (better configuration and health checking)

**Description**: Enhance ServiceOrchestrator with lessons learned from DataManager usage, then apply the improvements directly to DataManager to improve configuration management and health checking.

**Why Now**: With three components extracted, we have a better understanding of what ServiceOrchestrator needs. Rather than creating another base class, improve the existing one and apply benefits immediately.

**Detailed Actions**:
1. **Day 1: Enhance ServiceOrchestrator**
   - Add common async execution patterns (`execute_with_progress`, `execute_with_cancellation`)
   - Improve error handling integration points
   - Add standardized health check interface
   - Enhance configuration management with validation

2. **Day 2: Apply enhancements to DataManager**
   - Update DataManager to use enhanced ServiceOrchestrator capabilities
   - Implement standardized health checks for data operations
   - Use improved configuration management for IB host service settings
   - Add async execution pattern usage where beneficial

3. **Day 3: Test and validate**
   - Validate enhanced ServiceOrchestrator functionality
   - Test DataManager integration with improvements
   - Health check functionality testing
   - Configuration management validation

**Testing Requirements**:
- ServiceOrchestrator enhancement tests
- DataManager integration tests with enhancements
- Health check functionality tests
- Configuration management tests

**Deliverables**:
- Enhanced ServiceOrchestrator with new capabilities
- DataManager using improved ServiceOrchestrator features
- Better configuration and health checking
- Foundation for training manager improvements

### Task 1.5a: Create AsyncHostService Base Class
**Priority**: High  
**Type**: Create new component

**Description**: Create the AsyncHostService abstract base class to provide unified host service communication patterns.

**Acceptance Criteria**:
- Abstract base class with service identification and configuration methods
- HTTP client lifecycle management with async context manager patterns
- Custom exception hierarchy for host service communication failures
- Clean interface suitable for both IB and Training adapters

**Deliverables**:
- `ktrdr/managers/async_host_service.py` with complete base class implementation
- Unit tests for base class functionality

### Task 1.5b: Implement Connection Management and Health Checking
**Priority**: High  
**Type**: Feature implementation  
**Depends on**: Task 1.5a

**Description**: Add connection pooling, health checking, and retry logic to AsyncHostService.

**Acceptance Criteria**:
- Connection pooling with configurable limits and timeouts
- Standardized health check interface
- Retry logic with exponential backoff
- Request metrics and monitoring capabilities

**Deliverables**:
- Enhanced AsyncHostService with connection management
- Health checking capabilities
- Tests for connection pooling and retry logic

### Task 1.5c: Refactor IbDataAdapter to Use AsyncHostService
**Priority**: High  
**Type**: Refactor existing component  
**Depends on**: Task 1.5b

**Description**: Update IbDataAdapter to extend AsyncHostService instead of implementing its own HTTP patterns.

**Acceptance Criteria**:
- IbDataAdapter inherits from AsyncHostService
- Remove duplicate connection management code
- Maintain full backward compatibility with existing IB operations
- All existing IB tests continue to pass

**Deliverables**:
- Refactored IbDataAdapter using unified base class
- Integration tests validating maintained functionality

### Task 1.5d: Refactor TrainingAdapter to Use AsyncHostService
**Priority**: High  
**Type**: Refactor existing component  
**Depends on**: Task 1.5b

**Description**: Update TrainingAdapter to extend AsyncHostService for consistency with IB adapter.

**Acceptance Criteria**:
- TrainingAdapter inherits from AsyncHostService
- Eliminate duplicate HTTP client management code
- Training host service operations benefit from connection pooling
- All existing training tests continue to pass

**Deliverables**:
- Refactored TrainingAdapter using unified base class
- Integration tests validating training functionality

### Task 1.5e: Validate Host Service Harmonization
**Priority**: Medium  
**Type**: Validation  
**Depends on**: Task 1.5c, Task 1.5d

**Description**: Comprehensive testing and validation of unified host service patterns.

**Acceptance Criteria**:
- Connection pool behavior validated across both IB and Training scenarios
- Error handling consistency verified for both adapter types
- Health checking functionality working for both services
- Performance benefits from connection pooling measured

**Deliverables**:
- Comprehensive integration test suite
- Performance benchmarks showing connection pooling benefits
- Validation report for host service harmonization

## Phase 2: DataManager Async Transformation
**Duration**: 2.5 weeks  
**Goal**: Transform DataManager's sync/async patterns and complete decomposition

### Phase 2 Success Criteria
- All DataManager async/sync issues resolved
- Remaining components extracted and integrated
- DataManager becomes a clean orchestrator
- Performance improvements measurable
- All functionality preserved

### Task 2.1: Fix DataManager Async/Sync Boundaries
**Duration**: 4 days  
**Priority**: High  
**End-to-End Impact**: Positive (major performance improvement)

**Description**: Eliminate all `asyncio.run()` calls inside DataManager by creating proper async internal methods, delivering the major performance improvement.

**Why Now**: With components extracted, the async boundaries are clearer. This task delivers the biggest performance improvement while components are still fresh.

**Detailed Actions**:
1. **Day 1-2: Create async versions of all internal methods**
   - Replace `_fetch_segment_sync` with `_fetch_segment_async`
   - Replace `_fetch_head_timestamp_sync` with `_fetch_head_timestamp_async`
   - Remove all `asyncio.run()` calls from internal methods
   - Use `asyncio.to_thread()` for CPU-bound operations that need async wrapper

2. **Day 3: Update method call chains to be properly async**
   - Ensure all internal method calls use await instead of sync calls
   - Update `_load_with_fallback` to be fully async internally
   - Maintain sync public API for backward compatibility
   - Add proper async context management

3. **Day 4: Test and validate performance improvements**
   - Comprehensive async behavior testing
   - Performance benchmarking showing elimination of event loop overhead
   - Memory usage validation
   - Regression testing for all functionality

**Testing Requirements**:
- All existing DataManager functionality tests pass
- Async behavior validation tests
- Performance improvement benchmarks (target: 30-50% improvement)
- Memory usage regression tests
- Concurrent operation tests

**Deliverables**:
- DataManager with proper async/sync boundaries
- Major performance improvement (30-50% faster operations)
- Eliminated event loop creation overhead
- Foundation for further async improvements

### Task 2.2: Extract and Integrate DataValidator Component
**Duration**: 4 days  
**Priority**: Medium  
**End-to-End Impact**: None (internal refactoring with enhanced capabilities)

**Description**: Extract data validation and repair functionality from DataManager into a focused component, then integrate it back with enhanced validation capabilities.

**Detailed Actions**:
1. **Day 1-2: Create DataValidator with current logic**
   - Extract all validation methods from DataManager
   - Create `ktrdr/data/components/data_validator.py`
   - Include all repair strategies (ffill, bfill, interpolate, etc.)
   - Preserve existing validation behavior

2. **Day 3: Add enhanced validation capabilities**
   - Improve outlier detection with configurable thresholds
   - Add data quality scoring and reporting
   - Integrate with ProgressManager for validation progress
   - Add validation rule configuration system

3. **Day 4: Integrate back into DataManager**
   - Replace validation logic with DataValidator usage
   - Ensure seamless integration with existing workflows
   - Test enhanced validation capabilities
   - Validate performance and accuracy

**Testing Requirements**:
- All existing validation tests pass
- Enhanced validation capability tests
- DataValidator unit tests with edge cases
- Performance validation tests
- Integration tests with other components

**Deliverables**:
- DataValidator component integrated into DataManager
- Enhanced validation and repair capabilities
- DataManager with cleaner validation logic
- Improved data quality assurance

### Task 2.3: Extract and Integrate DataProcessor Component
**Duration**: 3 days  
**Priority**: Medium  
**End-to-End Impact**: None (internal refactoring with enhanced capabilities)

**Description**: Extract data processing functionality (merging, resampling, transformation) from DataManager into a focused component.

**Detailed Actions**:
1. **Day 1: Create DataProcessor with current logic**
   - Extract merging, resampling, and transformation methods
   - Create `ktrdr/data/components/data_processor.py`
   - Preserve all existing processing behavior
   - Add comprehensive error handling

2. **Day 2: Add enhanced processing capabilities**
   - Optimize DataFrame operations for better memory usage
   - Add flexible processing pipelines
   - Integrate with ProgressManager for processing progress
   - Add processing validation and quality checks

3. **Day 3: Integrate back into DataManager and test**
   - Replace processing logic with DataProcessor usage
   - Test enhanced processing capabilities
   - Validate performance improvements
   - Ensure integration with other components

**Testing Requirements**:
- All existing processing tests pass
- Enhanced processing capability tests
- DataProcessor unit tests
- Performance and memory usage tests
- Integration tests

**Deliverables**:
- DataProcessor component integrated into DataManager
- Enhanced processing capabilities
- Better memory usage and performance
- DataManager with cleaner processing logic

### Task 2.4: Create Async DataFetcher and Final Integration
**Duration**: 4 days  
**Priority**: High  
**End-to-End Impact**: Positive (better fetching performance and reliability)

**Description**: Create the fully async DataFetcher component that handles all network I/O, then integrate it to complete the DataManager decomposition.

**Detailed Actions**:
1. **Day 1-2: Create async DataFetcher**
   - Extract and async-ify all fetching logic from DataManager
   - Create `ktrdr/data/components/data_fetcher.py` as the only truly async component
   - Implement proper retry logic with exponential backoff
   - Add concurrent fetching capabilities with rate limiting
   - Integrate with connection management system for optimal performance

2. **Day 3: Integrate with existing adapter and progress systems**
   - Integrate with IbDataAdapter for actual data fetching
   - Add ProgressManager integration for fetch progress
   - Implement periodic progress saving to prevent data loss
   - Add proper error handling and resilience with connection health monitoring

3. **Day 4: Final integration and testing**
   - Integrate DataFetcher into DataManager
   - Complete the component pipeline: GapAnalyzer → SegmentManager → DataFetcher → DataProcessor → DataValidator
   - Test complete integrated system with connection pooling
   - Validate performance and reliability improvements

**Testing Requirements**:
- DataFetcher async operation tests
- Integration tests with all other components and connection management
- Performance tests with concurrent fetching and connection reuse
- Error handling and resilience tests with connection failures
- Complete DataManager integration tests

**Deliverables**:
- Async DataFetcher component fully integrated
- Complete DataManager decomposition achieved
- DataManager as clean orchestrator of components
- Improved fetching performance and reliability with connection pooling

### Task 2.5: DataManager Orchestrator Finalization
**Duration**: 3 days  
**Priority**: High  
**End-to-End Impact**: None (internal cleanup and optimization)

**Description**: Transform DataManager into a clean orchestrator that coordinates all components with optimal async patterns.

**Detailed Actions**:
1. **Day 1: Clean up DataManager orchestration logic**
   - Simplify DataManager to pure orchestration
   - Optimize component interaction patterns
   - Add comprehensive logging for debugging
   - Clean up any remaining legacy code

2. **Day 2: Optimize async patterns**
   - Ensure optimal async/await usage throughout
   - Add concurrent operations where beneficial
   - Optimize memory usage and resource management
   - Fine-tune performance characteristics

3. **Day 3: Final testing and validation**
   - Complete system testing with all components
   - Performance benchmarking against original DataManager
   - Memory usage validation
   - Comprehensive regression testing

**Testing Requirements**:
- Complete functional equivalence with original DataManager
- Performance improvement validation (target: 50%+ improvement)
- Memory usage optimization validation
- All existing tests passing
- New integration test suite completion

**Deliverables**:
- DataManager as clean, efficient orchestrator
- All components working together optimally
- Major performance improvements achieved
- Complete decomposition with maintained functionality

## Phase 3: Training Path Alignment and CLI Updates
**Duration**: 2 weeks  
**Goal**: Align training path with new patterns and update CLI to use async patterns

### Phase 3 Success Criteria
- TrainingManager uses enhanced ServiceOrchestrator patterns
- Training operations benefit from connection management improvements
- CLI commands use async patterns for better performance
- Consistent architecture across data and training paths
- User experience improvements visible

### Task 3.1: Apply DataManager Lessons to TrainingManager
**Duration**: 3 days  
**Priority**: Medium  
**End-to-End Impact**: Positive (consistency and improved training management)

**Description**: Apply the enhanced ServiceOrchestrator patterns and component lessons learned from DataManager to TrainingManager for consistency, including connection management benefits.

**Detailed Actions**:
1. **Day 1: Analyze TrainingManager for improvement opportunities**
   - Compare TrainingManager with enhanced DataManager patterns
   - Identify areas where enhanced ServiceOrchestrator can be applied
   - Plan integration of ProgressManager for training operations
   - Design consistent error handling patterns

2. **Day 2: Apply enhancements to TrainingManager**
   - Integrate ProgressManager for training progress reporting
   - Use enhanced ServiceOrchestrator capabilities
   - Apply consistent error handling patterns
   - Add health checking capabilities
   - Integrate TrainingAdapter with connection management system

3. **Day 3: Test and validate TrainingManager improvements**
   - Test enhanced training progress reporting
   - Validate health check functionality
   - Test error handling improvements
   - Validate connection pooling benefits for training host service
   - Ensure no regression in training functionality

**Testing Requirements**:
- All existing training tests pass
- Enhanced progress reporting tests
- Health check functionality tests
- Error handling validation tests
- Connection pooling performance tests
- Integration tests with training host service

**Deliverables**:
- TrainingManager with consistent architecture patterns
- Enhanced training progress reporting
- Improved error handling and health checking
- Connection management benefits for training operations
- Architectural consistency between data and training paths

### Task 3.2: Update CLI Commands to Use Async Patterns
**Duration**: 4 days  
**Priority**: High  
**End-to-End Impact**: Positive (major CLI performance improvement)

**Description**: Update CLI commands to use async patterns and connection reuse, delivering significant performance improvements and better user experience.

**Why Now**: With DataManager async issues fixed and connection management in place, CLI can benefit from proper async usage and connection pooling.

**Detailed Actions**:
1. **Day 1: Create AsyncCLIClient pattern**
   - Design reusable async CLI client with connection pooling
   - Create base pattern that all CLI commands can use
   - Add progress display capabilities for long operations
   - Design cancellation support (Ctrl+C handling)
   - Integrate with existing connection management system

2. **Day 2: Update data CLI commands**
   - Update `ktrdr data show`, `ktrdr data load`, and related commands
   - Implement AsyncCLIClient pattern usage with connection reuse
   - Add real-time progress display for data operations
   - Add enhanced error reporting with actionable messages

3. **Day 3: Update training CLI commands**
   - Update `ktrdr models train` and related commands
   - Implement consistent async patterns with connection pooling
   - Add progress reporting for training operations
   - Ensure consistent user experience

4. **Day 4: Test and validate CLI improvements**
   - Test CLI command performance improvements
   - Validate progress reporting functionality
   - Test cancellation behavior
   - User experience validation and feedback

**Testing Requirements**:
- CLI command functionality tests
- Performance improvement validation (target: 50%+ faster)
- Progress reporting tests
- Cancellation behavior tests
- Connection reuse validation tests
- User experience validation

**Deliverables**:
- CLI commands with async patterns and connection reuse
- Major CLI performance improvements
- Enhanced user experience with progress reporting
- Consistent CLI patterns across all commands

### Task 3.3: End-to-End Integration and Optimization
**Duration**: 3 days  
**Priority**: Medium  
**End-to-End Impact**: Positive (complete system optimization)

**Description**: Optimize the complete flow from CLI to host services and ensure all improvements work together optimally.

**Detailed Actions**:
1. **Day 1: End-to-end flow optimization**
   - Trace complete request flow from CLI to host services
   - Optimize connection pooling and reuse patterns across all layers
   - Identify and resolve any remaining bottlenecks
   - Add comprehensive request tracing for debugging

2. **Day 2: Integration testing and validation**
   - Test complete workflows with both data and training operations
   - Validate performance improvements across entire system
   - Test concurrent operations and resource usage
   - Validate error handling across all layers with connection management

3. **Day 3: Final optimization and tuning**
   - Fine-tune performance parameters based on testing
   - Optimize memory usage patterns
   - Add monitoring and alerting integration
   - Document performance characteristics and recommendations

**Testing Requirements**:
- End-to-end system performance tests
- Concurrent operation tests
- Memory usage validation
- Error handling integration tests
- Connection management integration tests
- Performance regression prevention tests

**Deliverables**:
- Fully optimized end-to-end system performance
- Complete integration validation
- Performance monitoring and alerting
- System optimization documentation

### Task 3.4: Documentation and Migration Completion
**Duration**: 4 days  
**Priority**: Low  
**End-to-End Impact**: None (documentation and cleanup)

**Description**: Complete the migration with comprehensive documentation, cleanup, and knowledge transfer.

**Detailed Actions**:
1. **Day 1-2: Update architecture documentation**
   - Update system architecture diagrams
   - Document new component relationships and responsibilities
   - Update API documentation and integration guides
   - Create troubleshooting and debugging guides
   - Document connection management and performance optimizations

2. **Day 3: Clean up legacy code and patterns**
   - Remove unused imports and dependencies
   - Clean up temporary migration code
   - Archive legacy implementations properly
   - Update configuration documentation

3. **Day 4: Knowledge transfer and training**
   - Create developer onboarding documentation
   - Document maintenance procedures
   - Create performance monitoring guides
   - Conduct knowledge transfer sessions

**Testing Requirements**:
- Documentation accuracy validation
- Example code testing
- Migration completeness verification

**Deliverables**:
- Complete architecture documentation
- Clean codebase with legacy code properly archived
- Developer knowledge base and training materials
- Migration completion validation

## Benefits of This Vertical Approach

### Immediate Value Delivery
Every task improves DataManager immediately. If we stop at any point, we have a better DataManager than when we started.

### Continuous Testing
Every component is tested as soon as it's created because it's immediately integrated into DataManager.

### Risk Mitigation
No untested code accumulates. Problems are discovered and fixed immediately.

### Clear Progress
Each task delivers visible improvements in functionality, performance, or maintainability.

### Flexibility
Tasks can be reordered or skipped based on priorities without breaking the overall plan.

### Learning Integration
Lessons learned from early tasks inform later tasks, improving the overall implementation.

## Success Metrics

### Performance Improvements
- **Phase 1**: 15-25% improvement from progress, components, and connection pooling
- **Phase 2**: 30-50% improvement from complete async transformation
- **Phase 3**: Additional 20% improvement from CLI async patterns

### Code Quality Improvements
- **Reduced complexity**: From 2600-line god class to orchestrator + focused components
- **Improved testability**: Each component testable in isolation
- **Better maintainability**: Clear responsibilities and separation of concerns
- **Enhanced reliability**: Better error handling and resilience patterns

### User Experience Improvements
- **Better progress reporting**: Clear feedback during long operations
- **Faster CLI commands**: Significant latency reduction from connection reuse
- **Cancellation support**: Ability to stop long operations gracefully
- **Enhanced error messages**: More actionable error reporting

### Host Service Integration Benefits
- **Connection reuse**: Significant performance improvements from connection pooling
- **Better resilience**: Improved error handling and retry logic
- **Health monitoring**: Better visibility into host service connectivity
- **Consistent patterns**: Same connection management across data and training paths

This vertical approach ensures we make continuous progress toward the unified async architecture while delivering immediate value at every step, including the crucial host service improvements that were in the original plan.