# SLICE 4: UNIFIED HOST SERVICE INTEGRATION

**Duration**: 1 week (5 days)  
**Branch**: `slice-4-unified-host-service-integration`  
**Goal**: Create unified host service infrastructure for both client adapters AND host services, with enhanced ServiceOrchestrator integration
**Priority**: High  
**Depends on**: Slice 1, 2, and 3 completion

## Overview

This final slice completes the unified async architecture by creating shared infrastructure that serves both client-side adapters (IbDataAdapter, TrainingAdapter) AND host services themselves. This ensures consistent patterns, shared connection pooling, and unified error handling across the entire system.

**KEY INSIGHT**: We need unified patterns not just for the client adapters that call host services, but also for the host services that receive and process these calls. Both sides should use the same async infrastructure.

**CRITICAL ARCHITECTURAL DECISION**: Instead of just renaming AsyncHostService, we create a comprehensive async infrastructure that serves:
1. **Client Adapters**: IbDataAdapter and TrainingAdapter (what call host services)  
2. **Host Services**: The actual IB and Training host services (what receive calls)
3. **ServiceOrchestrator Integration**: Enhanced integration for structured progress and cancellation

## Success Criteria

### Client-Side Improvements (Adapters)

- [ ] Unified AsyncServiceAdapter provides shared HTTP infrastructure
- [ ] Both IbDataAdapter and TrainingAdapter benefit from connection pooling
- [ ] Consistent cancellation behavior across all host service communication
- [ ] Enhanced ServiceOrchestrator integration for structured progress

### Host Service Improvements (Services)

- [ ] IB host service uses unified async patterns for data operations
- [ ] Training host service uses unified async patterns for training operations
- [ ] Both host services support structured progress reporting
- [ ] Both host services implement consistent cancellation handling

### System-Wide Benefits

- [ ] ALL existing functionality preserved (zero breaking changes)
- [ ] Shared connection pooling improves performance across all operations
- [ ] Consistent error handling and logging patterns system-wide
- [ ] Complete unified async infrastructure serving entire KTRDR ecosystem

## Tasks

### Task 4.1: Create Unified AsyncServiceAdapter Infrastructure

**Description**: Transform the existing AsyncHostService into a generic, reusable AsyncServiceAdapter that can be shared by both IB and Training systems. This provides the foundation for unified host service communication patterns.

**Why this is needed**: Currently each adapter (IB, Training) manages its own HTTP client and connection logic, leading to code duplication and inconsistent patterns. A shared infrastructure improves maintainability and performance.

**What this provides**:
- **Shared Connection Pooling**: Multiple requests reuse HTTP connections for better performance
- **Unified Error Handling**: Consistent error patterns and retry logic across all host service calls  
- **Cancellation Integration**: Works with the CancellationSystem from Slice 2 for proper operation cancellation
- **Generic Design**: No domain-specific knowledge, can serve any host service type

**Key Changes**:
- Move from `ktrdr/managers/` to `ktrdr/async_infrastructure/` to reflect its role as generic infrastructure
- Remove any domain-specific logic (IB-specific or training-specific code)
- Add abstract methods that subclasses implement for their specific needs
- Integrate with the unified cancellation system instead of managing tokens internally

**Core Components**:

1. **HostServiceConfig**: Configuration class for connection settings (timeouts, retries, connection limits)
2. **AsyncServiceAdapter**: Abstract base class with shared HTTP client management and connection pooling  
3. **Abstract Methods**: `get_service_name()` and `get_service_type()` for subclass identification
4. **HTTP Methods**: `_call_host_service_post()` and `_call_host_service_get()` with unified cancellation and retry logic
5. **Lifecycle Management**: Connection pooling, health checks, and proper resource cleanup

**Key Implementation Details**:

```python
# Abstract base for domain-specific adapters
class AsyncServiceAdapter(ABC):
    @abstractmethod
    def get_service_name(self) -> str: pass
    
    @abstractmethod  
    def get_service_type(self) -> str: pass
    
    # Shared HTTP infrastructure with connection pooling
    async def _call_host_service_post(self, endpoint, data, cancellation_token=None):
        # Unified retry logic, cancellation checking, error handling
    
    # Connection lifecycle management
    async def _get_http_client(self): 
        # Connection pooling with configurable limits
```

**Acceptance Criteria**:

- [ ] **File Structure**: AsyncServiceAdapter moved to `ktrdr/async_infrastructure/service_adapter.py` (generic location)
- [ ] **Generic Design**: Zero domain-specific knowledge (no IB or training logic in base class)
- [ ] **Abstract Interface**: Subclasses must implement `get_service_name()` and `get_service_type()`
- [ ] **Connection Pooling**: HTTP client reused across requests with configurable connection limits
- [ ] **Unified Cancellation**: Integrates with CancellationSystem from Slice 2 (not embedded tokens)
- [ ] **Error Handling**: Consistent retry logic and error translation across all HTTP operations
- [ ] **Resource Management**: Proper connection lifecycle with cleanup on close
- [ ] **Backward Compatibility**: All existing imports updated, functionality preserved

**Deliverables**:

- [ ] Refactored generic AsyncServiceAdapter infrastructure
- [ ] Updated imports across all adapters (IbDataAdapter, TrainingAdapter, etc.)
- [ ] Comprehensive test suite validating generic functionality
- [ ] Performance benchmarks showing connection pooling benefits

---

### Task 4.2: Enhance IbDataAdapter with Unified Infrastructure

**Description**: Update IbDataAdapter to inherit from the generic AsyncServiceAdapter, eliminating duplicate HTTP management code and gaining shared connection pooling benefits.

**Why this is needed**: The current IbDataAdapter has its own HTTP client management, retry logic, and error handling. By using the unified infrastructure, we eliminate code duplication and ensure consistent patterns across all adapters.

**What this provides**:
- **Eliminated Code Duplication**: Remove ~100+ lines of duplicate HTTP client management
- **Performance Benefits**: Connection pooling improves multi-request IB operations  
- **Consistent Error Handling**: Same error patterns as training adapter
- **Unified Cancellation**: Automatic integration with orchestration cancellation system

**Technical Changes**:
- Change `IbDataAdapter` from plain class to inherit `AsyncServiceAdapter`
- Remove duplicate HTTP client creation and management methods
- Update all host service calls to use base class methods with cancellation tokens
- Maintain all existing IB-specific functionality (data parsing, validation, etc.)

**Impact on Existing Code**:
- All existing IB operations continue to work exactly the same
- No changes to public API or method signatures
- Internal HTTP communication becomes more efficient and consistent

**Key Implementation Changes**:

```python
# Before: IbDataAdapter with duplicate HTTP management
class IbDataAdapter:
    def __init__(self, host_service_url):
        self._http_client = None  # Duplicate client management
        self._setup_http_client()  # Duplicate setup logic
    
# After: IbDataAdapter inheriting unified infrastructure  
class IbDataAdapter(AsyncServiceAdapter):
    def __init__(self, host_service_url, enabled=True):
        config = HostServiceConfig(base_url=host_service_url, max_connections=10)
        super().__init__(config)  # Unified connection pooling
    
    def get_service_name(self) -> str:
        return "IB Data Service"
        
    async def fetch_data(self, symbol, timeframe, cancellation_token=None):
        # Use base class method with automatic cancellation integration
        response = await self._call_host_service_post("/data/fetch", data, cancellation_token)
        return self._parse_data_response(response)  # Keep existing IB-specific logic
```

**Acceptance Criteria**:

- [ ] **Class Inheritance**: IbDataAdapter inherits from AsyncServiceAdapter (not plain class)
- [ ] **Code Reduction**: Remove ~100+ lines of duplicate HTTP client management code
- [ ] **Abstract Methods**: Implement `get_service_name()` and `get_service_type()` for IB identification
- [ ] **Cancellation Integration**: All IB host service calls accept and use cancellation_token parameter
- [ ] **Connection Pooling**: Multiple IB requests reuse HTTP connections automatically
- [ ] **Backward Compatibility**: All existing IB operations work identically (no API changes)
- [ ] **Error Handling**: IB errors use unified HostServiceError patterns
- [ ] **Performance**: Connection pooling provides measurable performance improvement for multi-request operations

**Deliverables**:

- [ ] Refactored IbDataAdapter with unified infrastructure inheritance
- [ ] Validation that all existing IB functionality preserved
- [ ] Performance benchmarks showing connection pooling benefits for IB operations
- [ ] Integration tests with ServiceOrchestrator cancellation

---

### Task 4.3: Enhance TrainingAdapter with Unified Infrastructure

**Description**: Update TrainingAdapter to inherit from AsyncServiceAdapter, following the same pattern as IbDataAdapter for consistency and shared infrastructure benefits.

**Why this is needed**: TrainingAdapter currently has its own HTTP management similar to IbDataAdapter. Using unified infrastructure ensures consistent patterns and eliminates duplication across all adapters.

**What this provides**:
- **Consistency**: Same patterns as IbDataAdapter for maintainability
- **Performance**: Connection pooling for training host service communications
- **Reliability**: Unified retry logic and error handling for training operations
- **Cancellation**: Seamless integration with training cancellation from Slice 3

**Key Changes**:
- Inherit from AsyncServiceAdapter instead of plain class
- Remove duplicate HTTP client management (similar cleanup as IB adapter)
- Use base class methods for all host service communication
- Maintain all training-specific functionality (session management, status polling, etc.)

**Acceptance Criteria**:

- [ ] **Class Inheritance**: TrainingAdapter inherits from AsyncServiceAdapter
- [ ] **Code Reduction**: Remove duplicate HTTP client management code  
- [ ] **Abstract Methods**: Implement `get_service_name()` and `get_service_type()` for training identification
- [ ] **Cancellation Integration**: Training host service calls use cancellation_token from Slice 3
- [ ] **Connection Pooling**: Training operations benefit from connection reuse
- [ ] **Backward Compatibility**: All existing training functionality preserved
- [ ] **Consistency**: Same patterns as IbDataAdapter for maintainability

**Deliverables**:

- [ ] Refactored TrainingAdapter with unified infrastructure
- [ ] Validation of all existing training functionality  
- [ ] Performance benchmarks for training host service communication
- [ ] Integration tests with training orchestration and cancellation

---

### Task 4.4: Enhance Host Services with Unified Async Infrastructure

**Description**: Update the actual host services (IB host service and Training host service) to use unified async patterns, not just the client adapters. This ensures consistency across the entire system.

**Why this is critical**: Currently we're only addressing client-side adapters. The host services themselves should also use consistent async patterns, structured progress reporting, and cancellation handling.

**What this addresses**:
- **IB Host Service**: The service that receives IB data requests and interfaces with Interactive Brokers
- **Training Host Service**: The service that receives training requests and manages training operations  
- **Progress Integration**: Both services should provide structured progress that integrates with ServiceOrchestrator
- **Cancellation Support**: Both services should respect cancellation requests from client operations

**Host Service Enhancements**:

1. **Structured Progress Reporting**: Host services report progress in structured format (not strings)
2. **Cancellation Handling**: Host services check for cancellation and stop operations appropriately
3. **Unified Error Patterns**: Consistent error responses across both host services
4. **Health Check Endpoints**: Standard health check implementations
5. **Logging and Monitoring**: Consistent logging patterns across both services

**Technical Approach**:
- Create shared host service base classes for common functionality
- Implement structured progress reporting from host services to client adapters
- Add cancellation check mechanisms within host service operations
- Standardize error response formats across both services

**Acceptance Criteria**:

- [ ] **IB Host Service**: Uses unified async patterns for data operations
- [ ] **Training Host Service**: Uses unified async patterns for training operations  
- [ ] **Structured Progress**: Both services provide structured progress (not raw strings)
- [ ] **Cancellation Support**: Both services check and respond to cancellation requests
- [ ] **Error Consistency**: Unified error response formats across both services
- [ ] **Health Checks**: Standard health check endpoints for both services
- [ ] **Documentation**: Clear API documentation for both enhanced services

**Deliverables**:

- [ ] Enhanced IB host service with unified async patterns
- [ ] Enhanced Training host service with unified async patterns
- [ ] Structured progress integration from both host services
- [ ] Cancellation handling implementation in both services
- [ ] API documentation for enhanced host service endpoints

---

### Task 4.5: Validate Complete System Integration

**Description**: Comprehensive testing and validation of the complete unified async infrastructure, ensuring both client adapters AND host services work together seamlessly with consistent patterns.

**Why this validation is critical**: This slice transforms both sides of the system - client adapters and host services. We need to ensure the entire system works together with improved performance, consistent cancellation, and no regressions.

**Validation Scope**:
- **Client Adapter Consistency**: Both IbDataAdapter and TrainingAdapter use identical patterns
- **Host Service Enhancement**: Both host services provide structured progress and handle cancellation
- **End-to-End Integration**: Complete data and training workflows work through unified infrastructure  
- **Performance Validation**: Connection pooling provides measurable benefits
- **Regression Testing**: All existing functionality preserved

**Testing Strategy**:

1. **Consistency Testing**: Verify both adapters follow identical patterns
2. **Performance Testing**: Measure connection pooling benefits (target: 30%+ improvement)
3. **Integration Testing**: End-to-end workflows through unified infrastructure
4. **Host Service Testing**: Verify structured progress and cancellation from both services  
5. **Regression Testing**: All existing functionality works without changes

**Acceptance Criteria**:

- [ ] **Adapter Consistency**: Both IbDataAdapter and TrainingAdapter use identical AsyncServiceAdapter patterns
- [ ] **Host Service Enhancement**: Both host services provide structured progress and handle cancellation  
- [ ] **Performance Benefits**: Connection pooling shows 30%+ improvement in multi-request scenarios
- [ ] **End-to-End Integration**: Complete data-to-training workflows work through unified infrastructure
- [ ] **Zero Regressions**: All existing functionality preserved across both systems
- [ ] **Cancellation Integration**: Unified cancellation works from client through host services
- [ ] **Error Consistency**: Unified error handling patterns across all components

**Deliverables**:

- [ ] Complete system integration validation report
- [ ] Performance benchmarks demonstrating connection pooling benefits
- [ ] Cross-system consistency verification  
- [ ] Regression test suite ensuring no functionality breaks

---

### Task 4.6: Final Documentation and Architecture Validation

**Description**: Complete the slice with comprehensive documentation of the unified async infrastructure and final validation that the entire system transformation is successful.

**Why this is needed**: Document the complete transformation from fragmented async patterns to unified infrastructure, providing clear guidance for future development and maintenance.

**Final Validation Checklist**:

1. **System Architecture**: Unified AsyncServiceAdapter serves both IB and Training systems
2. **Host Service Enhancement**: Both host services use structured progress and cancellation  
3. **Performance Gains**: Connection pooling provides measurable improvements
4. **Zero Breaking Changes**: All existing functionality preserved
5. **Documentation**: Complete developer guide for unified infrastructure

**Acceptance Criteria**:

- [ ] **Complete Infrastructure**: AsyncServiceAdapter serves all host service communication
- [ ] **Host Service Integration**: Both IB and Training host services enhanced with unified patterns
- [ ] **Performance Validation**: 30%+ improvement in multi-request operations documented
- [ ] **Zero Regressions**: All existing tests pass without modification
- [ ] **Developer Documentation**: Clear guide for using unified async infrastructure
- [ ] **Architecture Documentation**: Complete system architecture with all components

**Deliverables**:

- [ ] Final architecture documentation with unified async infrastructure
- [ ] Performance improvement benchmarks and metrics
- [ ] Developer guide for unified host service patterns
- [ ] Complete regression validation ensuring zero breaking changes

---

## Summary

This slice completes the unified async architecture by creating shared infrastructure that serves both client adapters AND host services. The transformation provides:

### Client-Side Benefits
- **Unified Infrastructure**: AsyncServiceAdapter provides shared HTTP client management
- **Performance**: Connection pooling improves multi-request operations  
- **Consistency**: Both IbDataAdapter and TrainingAdapter use identical patterns

### Host Service Benefits  
- **Structured Progress**: Both IB and Training host services provide structured progress reporting
- **Cancellation Support**: Both host services respect cancellation requests
- **Unified Patterns**: Consistent error handling and API patterns

### System-Wide Impact
- **Zero Breaking Changes**: All existing functionality preserved
- **Enhanced Performance**: Connection pooling provides measurable improvements
- **Unified Architecture**: Complete async infrastructure serving entire KTRDR ecosystem
- **Future Extensibility**: Clean patterns for adding new services or adapters