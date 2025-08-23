# Unified Async Architecture Implementation Plan

## Overview

This document outlines the implementation plan for the unified async architecture that will eliminate sync/async mixing issues, improve performance by 50-70%, and create consistent patterns across the entire k-trdr system.

## Current State Analysis

### Performance Issues
- **CLI Commands**: 800ms-1.2s total latency due to event loop creation overhead (200-500ms per command)
- **HTTP Overhead**: 100-200ms per request due to no connection reuse
- **DataManager Bottleneck**: 500ms+ sync blocking in async chains
- **IB Gateway Issues**: Socket corruption requiring computer reboots

### Architectural Problems
- Sync/async mixing throughout the codebase
- DataManager breaks async chains with sync operations
- No HTTP connection pooling or reuse
- Inconsistent error handling patterns
- Event loop creation per CLI command

## Implementation Strategy

### Phase 1: CLI Foundation (Week 1-2)
**Risk: Low | Impact: High**

#### 1.1 UnifiedAsyncCLI Base Class
- Single HTTP client instance reused across commands
- Proper async context manager lifecycle
- Thread-safe operation with configuration injection
- **Target**: >50% latency reduction

#### 1.2 Command Migration
- Migrate `ktrdr data show` and `ktrdr models train` 
- Maintain backward compatibility
- Add performance benchmarking

### Phase 2: Service Foundation (Week 3-4)
**Risk: Medium | Impact: High Long-term**

#### 2.1 AsyncHostService Base Class
- Abstract base class for all host service communication
- Standard HTTP client lifecycle management
- Unified error handling with custom exceptions
- Health check abstraction

#### 2.2 Error Handling System
- Custom exception hierarchy (ServiceConnectionError, ServiceTimeoutError, etc.)
- Error context preservation across async boundaries
- Consistent error messages and debugging info

### Phase 3: Data Layer Unification (Week 5-6) 
**Risk: Medium | Impact: High Performance**

#### 3.1 AsyncDataManager
- Replace sync DataManager with async version
- Support both 'ib' and 'local' data sources
- Eliminate the 500ms+ sync bottleneck
- Environment-based adapter configuration

#### 3.2 AsyncDataAdapter
- Extend AsyncHostService base class
- Support both host service and local IB connection modes
- Proper DataFrame conversion and error handling
- Thread-safe resource management

### Phase 4: Service Refactoring (Week 7)
**Risk: Low | Impact: High Maintainability**

#### 4.1 TrainingAdapter Refactoring
- Inherit from AsyncHostService base class
- Remove duplicate HTTP client management code
- Maintain all existing functionality
- Code duplication elimination

#### 4.2 DataService Integration
- Update DataService to use AsyncDataManager
- Proper async error handling and context preservation
- Integration with FastAPI endpoints

### Phase 5: Testing & Optimization (Week 8-10)
**Risk: Low | Impact: Performance**

#### 5.1 Integration Testing
- End-to-end CLI command testing
- Performance benchmarks (>50% improvement target)
- Resource cleanup and concurrent operation testing
- Error handling verification

#### 5.2 Performance Optimization
- HTTP connection pooling in AsyncHostService
- Request batching for bulk operations
- Connection pool health monitoring
- Concurrent operation support

#### 5.3 Documentation
- Architecture documentation updates
- Developer guides with new async patterns
- Migration guide and troubleshooting
- Performance metrics documentation

## Success Metrics

### Performance Targets
- **CLI Latency Reduction**: 50-70% improvement
- **No IB Gateway Restarts**: Eliminate socket corruption
- **Concurrent Training**: Support 10+ simultaneous sessions

### Code Quality Targets
- **Single Async Pattern**: Consistent throughout codebase
- **Async Bug Reduction**: 50% fewer async-related issues
- **Unified Error Handling**: Consistent across all services

### Developer Experience
- **Learning Curve**: 1-day vs 1-week for async patterns
- **Single Debugging Approach**: Unified across services
- **Consistent Behavior**: Predictable async patterns

## Risk Mitigation

### Medium Risk Areas
- **DataManager Replacement**: Comprehensive testing required
- **Service Migration**: Thorough integration testing needed
- **IB Gateway Integration**: Careful connection management

### Mitigation Strategies
- **TDD Approach**: Tests first, then implementation
- **Incremental Migration**: One component at a time
- **Performance Benchmarking**: Continuous validation
- **Comprehensive Testing**: Unit, integration, and performance tests

## Dependencies

### Internal
- Current DataManager interface understanding
- IB Host Service integration patterns
- Training Host Service success patterns

### External
- IB Gateway connection stability requirements
- HTTP client library capabilities (aiohttp)
- FastAPI async integration patterns

## Quality Gates

Each phase requires:
- ✅ All tests pass (pytest)
- ✅ Type checking passes (mypy --strict)
- ✅ Code formatting passes (black)
- ✅ Linting passes (ruff)
- ✅ Security scanning passes (bandit)
- ✅ Performance benchmarks meet targets
- ✅ Integration tests with existing systems

## Implementation Notes

### Key Patterns to Follow
1. **Training Host Service Pattern**: Proven successful microservice pattern
2. **Async Context Preservation**: Maintain error context through async chains
3. **Resource Management**: Proper cleanup and connection lifecycle
4. **Configuration Injection**: Environment-based service configuration

### Critical Success Factors
1. **TDD Approach**: Write tests before implementation
2. **Performance Validation**: Continuous benchmarking
3. **Incremental Migration**: One component at a time
4. **Comprehensive Documentation**: Support future development

This implementation plan provides a structured approach to achieving the unified async architecture while minimizing risk and maximizing the benefits of improved performance and code maintainability.