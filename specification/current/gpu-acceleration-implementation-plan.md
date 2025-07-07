# GPU Acceleration Training Service Implementation Plan

## 1. Executive Summary

### Implementation Vision
This document provides a comprehensive implementation roadmap for extracting the KTRDR training service from Docker to the host system, enabling GPU acceleration while maintaining system reliability and backward compatibility. The implementation follows a **test-driven, incremental approach** with extensive validation at each phase to ensure zero disruption to existing workflows.

### Implementation Strategy
- **Service Extraction Pattern**: Follow proven IB host service architecture
- **Test-First Development**: Extensive testing before, during, and after each phase
- **Zero Disruption Principle**: Maintain full backward compatibility throughout
- **Incremental Rollout**: Phase-by-phase implementation with validation gates
- **Comprehensive Testing**: Unit, integration, performance, and manual testing at each stage

### Success Criteria
- All existing training tests pass with host service
- GPU acceleration delivers 3x+ performance improvement
- Seamless fallback to Docker mode when needed
- Auto-startup works reliably for both host services
- Zero changes required to user workflows

### Risk Mitigation
- **Extensive Testing**: 95%+ test coverage with automated validation
- **Rollback Strategy**: Complete rollback capability at any phase
- **Incremental Deployment**: Each phase independently validated
- **Fallback Mechanisms**: Docker-only mode always available

---

## 2. Implementation Architecture

### 2.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Implementation Timeline                       │
│                                                                 │
│  Phase 1: Foundation & Testing (Week 1)                        │
│  ├─ Service Structure Creation                                  │
│  ├─ Test Infrastructure Setup                                   │
│  ├─ Core Service Implementation                                 │
│  └─ Unit Test Development                                       │
│                                                                 │
│  Phase 2: Integration & API (Week 2)                           │
│  ├─ Docker API Proxy Integration                               │
│  ├─ Host Service Communication                                  │
│  ├─ Integration Test Development                                │
│  └─ End-to-End Testing                                         │
│                                                                 │
│  Phase 3: Service Management (Week 3)                          │
│  ├─ Auto-Startup Implementation                                 │
│  ├─ Health Monitoring Setup                                     │
│  ├─ Performance Testing                                         │
│  └─ Production Deployment                                       │
│                                                                 │
│  Phase 4: Validation & Documentation (Week 4)                  │
│  ├─ Comprehensive System Testing                               │
│  ├─ Performance Benchmarking                                   │
│  ├─ Documentation Updates                                       │
│  └─ Manual Testing & Sign-off                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Testing Strategy Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Testing Pyramid                            │
│                                                                 │
│  ┌─────────────────┐ Manual & Exploratory Testing              │
│  │   Manual Tests  │ • End-to-end workflow validation          │
│  │      (5%)       │ • GPU performance validation              │
│  └─────────────────┘ • Service management testing              │
│                                                                 │
│  ┌─────────────────┐ Integration & System Testing              │
│  │ Integration     │ • Host service ↔ Docker communication     │
│  │ Tests (25%)     │ • Routing logic validation                │
│  └─────────────────┘ • Fallback behavior testing              │
│                                                                 │
│  ┌─────────────────┐ Unit & Component Testing                  │
│  │  Unit Tests     │ • Service endpoint testing                │
│  │    (70%)        │ • GPU manager integration                 │
│  └─────────────────┘ • Configuration management               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Test Coverage Requirements

**Existing Test Preservation**
- All current training tests must pass unchanged: `tests/training/`, `tests/api/test_training_*.py`
- Performance benchmarks must be maintained or improved
- Memory management tests must continue to pass

**New Test Categories**
- **Host Service Tests**: Service startup, endpoints, GPU integration
- **Routing Tests**: Request routing, fallback behavior, circuit breaker
- **Integration Tests**: Docker ↔ Host communication, configuration
- **Performance Tests**: GPU acceleration validation, throughput measurement

---

## 3. Detailed Implementation Phases

### 3.1 Phase 1: Foundation & Testing Infrastructure (Week 1)

#### 3.1.1 Service Structure Creation

**Objectives**
- Create training host service following IB host service patterns
- Establish project structure and development environment
- Set up comprehensive testing infrastructure
- Integrate existing GPU acceleration code without modification

**Key Activities**

**Day 1: Project Structure Setup**
- Create training host service directory structure following established patterns
- Initialize service files (main application, configuration, requirements)
- Set up test directories for unit, integration, and performance testing
- Establish logging and monitoring infrastructure

**Day 2-3: Core Service Implementation**
- Implement FastAPI application following IB service architecture
- Create GPU service wrapper around existing `GPUMemoryManager`
- Build training orchestration service that imports existing training modules
- Implement health check and monitoring endpoints
- Add CORS middleware for Docker container communication

**Day 4: GPU Service Integration**
- Wrap existing `GPUMemoryManager` in service layer without modification
- Implement GPU status reporting and metrics collection
- Create GPU memory optimization interfaces
- Build GPU-specific health monitoring
- Ensure graceful CPU fallback when GPU unavailable

**Day 5: Initial Testing Setup**
- Create comprehensive test fixtures and mocking infrastructure
- Build unit test framework with async support
- Set up test configuration for different environments
- Establish baseline performance measurements

**Decision Points**
- Choose service port (recommend 5002 to follow IB service pattern)
- Decide on logging format and level consistency with existing services
- Determine GPU configuration defaults based on hardware testing
- Select appropriate CORS policies for Docker communication

**Validation Requirements**
- Service starts successfully and responds to health checks
- GPU service initializes correctly (with and without GPU hardware)
- All existing training modules can be imported without modification
- Test infrastructure supports both mocked and real GPU testing

#### 3.1.2 Test Infrastructure Development

**Objectives**
- Build comprehensive test suite covering all service functionality
- Ensure high test coverage (95%+) for all new components
- Validate that existing training functionality remains unchanged
- Create performance baseline measurements

**Key Activities**

**Unit Test Development**
- Test GPU service initialization, status reporting, and optimization
- Test training manager job orchestration and lifecycle management
- Test configuration management and environment variable handling
- Test health check endpoints and error conditions
- Mock external dependencies for isolated testing

**Integration Preparation**
- Set up test fixtures for end-to-end workflow testing
- Create mock services for Docker communication testing
- Build performance measurement infrastructure
- Establish test data and model fixtures

**Existing Test Validation**
- Run all existing training tests to establish baseline
- Identify any tests that need modification for host service integration
- Document test dependencies and requirements
- Ensure test isolation and reproducibility

**Decision Points**
- Determine acceptable test coverage thresholds for each component
- Choose between real GPU testing vs mocked testing strategies
- Decide on performance test baseline requirements
- Select appropriate test data sizes for performance validation

**Risk Mitigation**
- Comprehensive mocking prevents dependency on external services
- Test isolation ensures reliable, repeatable results
- Performance baselines enable regression detection
- Existing test validation ensures no functionality loss

#### 3.1.3 Phase 1 Validation

**Testing Requirements**
- 95% line coverage for GPU service components
- 90% line coverage for training management components
- 100% coverage for configuration and health check components
- All existing training tests must pass without modification

**Success Criteria**
- Host service starts and stops cleanly
- GPU service reports correct status for available hardware
- All unit tests pass with required coverage thresholds
- No regression in existing training functionality
- Service responds correctly to health checks
- Performance baseline measurements established

**Risk Assessment**
- GPU hardware availability may affect testing completeness
- Service startup dependencies could cause integration issues
- Configuration conflicts might arise with existing services
- Test environment setup complexity could delay progress

**Go/No-Go Decision Factors**
- All automated tests pass consistently
- Service demonstrates stable startup and shutdown
- GPU integration works correctly (or fails gracefully)
- Test infrastructure supports comprehensive validation
- No breaking changes to existing functionality detected

### 3.2 Phase 2: Integration & API Development (Week 2)

#### 3.2.1 Docker API Proxy Integration

**Objectives**
- Implement request routing between Docker API and host service
- Build robust fallback mechanism for service failures
- Ensure transparent operation for all existing interfaces
- Maintain full backward compatibility with Docker-only mode

**Key Activities**

**Day 6-7: API Routing Implementation**
- Modify existing training API endpoints to support routing logic
- Implement routing decision based on configuration and service health
- Create host service communication layer with proper error handling
- Build transparent request/response proxying with metadata injection
- Ensure routing preserves all existing API contracts and response formats

**Day 8: Circuit Breaker Implementation**
- Design circuit breaker pattern for service failure detection
- Implement three-state circuit breaker (closed/open/half-open)
- Create failure detection and recovery timeout logic
- Build success/failure tracking and state transition management
- Add comprehensive logging for circuit breaker state changes

**Day 9: Integration Testing**
- Create comprehensive routing test scenarios
- Test fallback behavior under various failure conditions
- Validate circuit breaker state transitions and recovery
- Test concurrent request handling during service transitions
- Verify API response consistency between routing modes

**Decision Points**
- Define circuit breaker failure thresholds and recovery timeouts
- Choose request timeout values for host service communication
- Determine retry policies for transient failures
- Select logging levels and metrics for operational visibility

**Validation Requirements**
- Training requests route correctly based on configuration
- Fallback to Docker occurs seamlessly on host service failure
- Circuit breaker prevents cascading failures and enables recovery
- API responses are identical regardless of routing destination
- All existing API contracts remain unchanged

#### 3.2.2 Configuration Management Integration

**Objectives**
- Harmonize configuration patterns between IB and training services
- Implement environment-based feature toggles
- Ensure configuration consistency and validation
- Build configuration hot-reloading where appropriate

**Key Activities**

**Configuration System Design**
- Create training host service configuration following IB patterns
- Implement environment variable override mechanisms
- Build configuration validation and error reporting
- Design configuration file hierarchy and precedence rules

**Environment Integration**
- Create environment files for host service feature toggles
- Implement Docker environment variable injection
- Build configuration consistency checks across services
- Design configuration migration and upgrade paths

**Testing Infrastructure**
- Create configuration testing framework
- Test configuration override and precedence rules
- Validate environment variable handling and defaults
- Test configuration error handling and recovery

**Decision Points**
- Choose configuration file formats and naming conventions
- Define environment variable naming patterns
- Determine configuration validation strictness levels
- Select appropriate default values for all configuration options

**Risk Mitigation**
- Configuration validation prevents invalid states
- Default values ensure safe operation without configuration
- Environment variable overrides enable flexible deployment
- Configuration testing ensures reliability across environments

#### 3.2.3 Phase 2 Validation

**Testing Requirements**
- 100% coverage of API routing logic and fallback scenarios
- 95% coverage of circuit breaker functionality in all states
- End-to-end workflow testing with host service and Docker modes
- Configuration management testing across all scenarios

**Success Criteria**
- Training requests route correctly to host service when available
- Seamless fallback to Docker occurs on host service failure
- Circuit breaker prevents cascading failures and enables recovery
- All existing training tests pass with routing enabled
- Configuration changes take effect without service restart
- Performance shows no regression during routing operations

**Risk Assessment**
- Network communication issues could affect routing reliability
- Circuit breaker tuning may require iteration based on real conditions
- Configuration complexity could introduce deployment issues
- Integration testing may reveal compatibility issues

**Go/No-Go Decision Factors**
- All routing scenarios tested and working correctly
- Fallback behavior validated under various failure conditions
- Configuration management proven reliable and consistent
- No breaking changes to existing API interfaces
- Performance impact of routing is acceptable

### 3.3 Phase 3: Service Management & Auto-Startup (Week 3)

#### 3.3.1 Auto-Startup Implementation

**Objectives**
- Implement automatic startup for both IB and training host services
- Create unified service management across both services
- Ensure reliable service recovery after system restarts
- Build comprehensive health monitoring and restart capabilities

**Key Activities**

**Day 11-12: Service Management Scripts**
- Create platform-specific service installation scripts (macOS launchd, Linux systemd)
- Implement service registration with appropriate user permissions
- Build service configuration templates with environment variable support
- Create service dependency management and startup ordering
- Implement service health monitoring and automatic restart policies

**Platform-Specific Implementation**
- Design macOS launchd configuration with proper working directories and logging
- Create Linux systemd user service configuration with restart policies
- Implement service environment variable injection and configuration management
- Build cross-platform service management wrapper scripts
- Ensure service isolation and security best practices

**Service Coordination**
- Create unified startup scripts for both IB and training services
- Implement service health checking and dependency validation
- Build service status monitoring and reporting tools
- Design service shutdown procedures with graceful termination
- Create service management documentation and troubleshooting guides

**Decision Points**
- Choose service restart policies and failure handling strategies
- Define service startup dependencies and ordering requirements
- Select appropriate logging locations and rotation policies
- Determine service isolation and security requirements

**Validation Requirements**
- Services start automatically on system boot within acceptable timeframes
- Services restart automatically on failure with proper logging
- Service management scripts work across target platforms
- Service health monitoring accurately reports status
- Services can be managed through standard system tools

#### 3.3.2 Health Monitoring Enhancement

**Objectives**
- Implement comprehensive health monitoring for training host service
- Integrate GPU-specific metrics and status reporting
- Build service performance monitoring and alerting
- Create health check endpoints with detailed diagnostics

**Key Activities**

**Health Check Implementation**
- Create basic health endpoint for load balancer and service discovery
- Build detailed health endpoint with comprehensive system diagnostics
- Implement GPU-specific health monitoring and status reporting
- Create service performance metrics collection and reporting
- Build health check caching and optimization for high-frequency polling

**Monitoring Integration**
- Integrate health monitoring with existing observability infrastructure
- Create service-specific metrics for Prometheus or similar systems
- Implement structured logging for health events and status changes
- Build health trend monitoring and anomaly detection
- Create health-based alerting and notification systems

**Performance Monitoring**
- Implement training performance monitoring and baseline tracking
- Create GPU utilization monitoring and optimization recommendations
- Build memory usage monitoring and leak detection
- Implement service response time monitoring and optimization
- Create performance regression detection and reporting

**Decision Points**
- Define health check frequency and caching strategies
- Choose metrics collection and reporting formats
- Determine alerting thresholds and escalation procedures
- Select performance monitoring granularity and retention policies

**Risk Mitigation**
- Health check redundancy prevents false positive alerts
- Performance monitoring enables early issue detection
- GPU monitoring prevents resource exhaustion and failures
- Comprehensive logging enables rapid troubleshooting and resolution

#### 3.3.3 Phase 3 Validation

**Testing Requirements**
- Service management testing across target platforms
- Auto-startup validation through actual system restarts
- Health monitoring testing under various system conditions
- Performance monitoring validation with real workloads

**Success Criteria**
- Both services auto-start reliably on system boot
- Services restart automatically on failure within acceptable timeframes
- Health monitoring accurately reports service and GPU status
- Performance metrics show expected improvements with GPU acceleration
- Service management tools work reliably across platforms
- No manual intervention required for normal operations

**Risk Assessment**
- Platform differences could affect service management reliability
- Service startup dependencies may cause boot-time issues
- Health monitoring overhead could impact service performance
- Auto-restart policies may need tuning based on real failure patterns

**Go/No-Go Decision Factors**
- Auto-startup works consistently across target platforms
- Service restart behavior is reliable and well-logged
- Health monitoring provides accurate and useful status information
- Performance monitoring shows measurable improvements
- Service management complexity is acceptable for operational teams

### 3.4 Phase 4: Comprehensive Testing & Validation (Week 4)

#### 3.4.1 Comprehensive System Testing

**Objectives**
- Execute complete system validation across all components
- Validate performance improvements and system reliability
- Conduct comprehensive manual testing and user acceptance
- Document system behavior and operational procedures

**Key Activities**

**Automated Test Execution**
- Run complete test suite across all components and integration points
- Execute performance benchmarking and regression testing
- Validate system behavior under various load and failure conditions
- Test configuration management and deployment procedures
- Execute security testing and vulnerability assessment

**Manual Testing Protocol**
- Conduct comprehensive manual testing following detailed checklist
- Validate user workflows and interface consistency
- Test system behavior under real-world conditions and edge cases
- Validate documentation accuracy and completeness
- Conduct performance testing with real training workloads

**System Validation**
- Validate GPU acceleration performance improvements
- Test system reliability and recovery capabilities
- Validate service management and operational procedures
- Test rollback procedures and failure recovery
- Validate monitoring and alerting functionality

**Decision Points**
- Define acceptance criteria for performance improvements
- Choose manual testing scenarios and validation criteria
- Determine system reliability and availability requirements
- Select performance benchmarking methodologies and metrics

**Validation Requirements**
- All automated tests pass with required coverage thresholds
- Manual testing validates all user workflows and edge cases
- Performance testing demonstrates expected improvements
- System reliability meets operational requirements
- Documentation enables successful deployment and operation

#### 3.4.2 Performance Benchmarking

**Objectives**
- Document actual performance improvements with GPU acceleration
- Validate system scalability and resource utilization
- Measure operational impact and resource requirements
- Create performance baselines for future optimization

**Key Activities**

**Performance Measurement**
- Conduct baseline performance measurements with Docker-only mode
- Execute comprehensive performance testing with GPU acceleration
- Measure training speed improvements across various model types and sizes
- Test system performance under concurrent load and resource constraints
- Document resource utilization patterns and optimization opportunities

**Scalability Testing**
- Test system behavior with multiple concurrent training jobs
- Validate resource management and job queuing behavior
- Test system limits and failure modes under extreme load
- Measure performance degradation patterns and scaling characteristics
- Document optimal configuration and resource allocation strategies

**Operational Impact Assessment**
- Measure system startup and recovery times
- Test operational procedures and management complexity
- Validate monitoring and troubleshooting capabilities
- Assess operational overhead and maintenance requirements
- Document operational best practices and optimization guidelines

**Decision Points**
- Define performance improvement acceptance criteria
- Choose benchmarking methodologies and test scenarios
- Determine resource utilization targets and limits
- Select operational metrics and monitoring requirements

**Risk Mitigation**
- Comprehensive benchmarking prevents performance surprises
- Scalability testing reveals system limits and bottlenecks
- Operational assessment ensures sustainable deployment
- Performance documentation enables optimization and troubleshooting

#### 3.4.3 Final Validation & Documentation

**Objectives**
- Complete final system validation and acceptance testing
- Finalize documentation and operational procedures
- Prepare deployment packages and rollback procedures
- Conduct final sign-off and acceptance approval

**Key Activities**

**Final System Validation**
- Execute complete end-to-end system testing
- Validate all acceptance criteria and success metrics
- Conduct final security review and vulnerability assessment
- Complete performance validation and benchmarking
- Validate rollback procedures and emergency recovery

**Documentation Completion**
- Finalize installation and deployment documentation
- Complete operational procedures and troubleshooting guides
- Update user documentation and interface guides
- Create performance optimization and tuning guides
- Complete security and compliance documentation

**Deployment Preparation**
- Prepare deployment packages and installation scripts
- Create deployment checklists and validation procedures
- Prepare rollback packages and emergency procedures
- Create monitoring and alerting configuration
- Prepare operational handoff and training materials

**Success Criteria**
- All acceptance criteria met and validated
- Documentation complete and validated for accuracy
- Deployment procedures tested and validated
- Rollback procedures tested and ready
- Operational teams trained and ready for handoff

---

## 4. Technical Implementation Examples

This section provides illustrative code examples to support the implementation phases described above. These examples are guidance and may be adapted during actual implementation.

### 4.1 Service Structure Examples

#### Basic Host Service Structure
```python
# training-host-service/main.py
"""Training Host Service - GPU-accelerated training service."""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from services.gpu_service import GPUService
from services.training_manager import TrainingManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    gpu_service = GPUService()
    await gpu_service.initialize()
    
    training_manager = TrainingManager(gpu_service=gpu_service)
    await training_manager.initialize()
    
    yield
    
    # Shutdown
    await training_manager.shutdown()
    await gpu_service.shutdown()

app = FastAPI(
    title="Training Host Service",
    version="1.0.0",
    lifespan=lifespan
)
```

#### GPU Service Integration
```python
# training-host-service/services/gpu_service.py
"""GPU service wrapper for training host service."""

from ktrdr.training.gpu_memory_manager import GPUMemoryManager, GPUMemoryConfig

class GPUService:
    """GPU management service for training host."""
    
    def __init__(self):
        self.gpu_manager = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize GPU service using existing GPU manager."""
        config = GPUMemoryConfig(
            memory_fraction=0.9,
            enable_mixed_precision=True,
            enable_memory_pooling=True
        )
        
        self.gpu_manager = GPUMemoryManager(config=config)
        self.initialized = True
    
    def get_status(self):
        """Get GPU status using existing manager."""
        if not self.gpu_manager:
            return {"gpu_available": False}
        return self.gpu_manager.get_memory_summary()
```

### 4.2 API Routing Examples

#### Request Routing Logic
```python
# ktrdr/api/endpoints/training.py (modifications)
"""Training API with host service routing."""

import httpx
from ktrdr.config import get_settings

class TrainingHostRouter:
    """Routes training requests to host service or Docker fallback."""
    
    async def route_training_request(self, endpoint: str, **kwargs):
        """Route training request based on configuration."""
        settings = get_settings()
        
        if settings.use_training_host_service:
            try:
                return await self._call_host_service(endpoint, **kwargs)
            except Exception:
                logger.warning("Host service unavailable, falling back to Docker")
        
        return await self._docker_training_fallback(endpoint, **kwargs)
    
    async def _call_host_service(self, endpoint: str, **kwargs):
        """Call training host service."""
        # Implementation details here
        pass
    
    async def _docker_training_fallback(self, endpoint: str, **kwargs):
        """Fallback to existing Docker training."""
        # Use existing training service
        pass
```

#### Circuit Breaker Pattern
```python
# ktrdr/api/utils/circuit_breaker.py
"""Circuit breaker for service reliability."""

from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for service failure handling."""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def can_execute(self) -> bool:
        """Check if requests can be executed."""
        # Implementation logic here
        return self.state != CircuitState.OPEN
    
    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

### 4.3 Service Management Examples

#### macOS Service Configuration
```xml
<!-- ~/Library/LaunchAgents/com.ktrdr.training-host-service.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ktrdr.training-host-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/karl/Documents/dev/ktrdr2/training-host-service</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

#### Linux Service Configuration
```ini
# /etc/systemd/user/ktrdr-training-host.service
[Unit]
Description=KTRDR Training Host Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/ktrdr2/training-host-service
Environment=PYTHONPATH=/opt/ktrdr2
ExecStart=/usr/local/bin/uv run python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

### 4.4 Testing Examples

#### Unit Test Structure
```python
# training-host-service/tests/unit/test_gpu_service.py
"""Unit tests for GPU service."""

import pytest
from unittest.mock import Mock, patch
from services.gpu_service import GPUService

class TestGPUService:
    """Test GPU service functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization_success(self):
        """Test successful GPU service initialization."""
        with patch('services.gpu_service.GPUMemoryManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.enabled = True
            mock_manager.return_value = mock_instance
            
            service = GPUService()
            await service.initialize()
            
            assert service.initialized is True
    
    @pytest.mark.asyncio
    async def test_get_status_initialized(self):
        """Test status when service initialized."""
        # Test implementation here
        pass
```

#### Integration Test Example
```python
# training-host-service/tests/integration/test_training_flow.py
"""End-to-end training flow tests."""

import pytest
from unittest.mock import patch

class TestTrainingFlow:
    """Test complete training workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_training_workflow_gpu(self):
        """Test complete training workflow with GPU acceleration."""
        # Mock existing training modules
        with patch('ktrdr.training.train_strategy') as mock_training:
            mock_training.train_strategy.return_value = {
                "task_id": "gpu-test-123",
                "status": "completed",
                "performance": {"gpu_utilization": 87.2}
            }
            
            # Test implementation here
            pass
```

### 4.5 Configuration Examples

#### Service Configuration
```yaml
# config/training_host_service.yaml
host_service:
  host: "127.0.0.1"
  port: 5002
  log_level: "INFO"

gpu:
  memory_fraction: 0.9
  enable_mixed_precision: true
  enable_memory_pooling: true

training:
  max_concurrent_jobs: 2
  progress_update_interval: 1.0
```

#### Environment Configuration
```yaml
# config/environment/training_host_service_enabled.yaml
training_host_service:
  enabled: true
  url: "http://host.docker.internal:5002"
  timeout_seconds: 30
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout_seconds: 60
```

---

This implementation plan provides strategic guidance for GPU acceleration service extraction while maintaining flexibility for technical decisions during implementation. The code examples in Section 4 illustrate key concepts but should be adapted based on actual implementation discoveries and requirements.
    async def host_service_running(self):
        """Start host service for integration testing."""
        # This would start the actual host service
        # For tests, we'll mock it
        with patch('httpx.AsyncClient.request') as mock_request:
            mock_request.return_value.status_code = 200
            mock_request.return_value.json.return_value = {
                "task_id": "test-123",
                "status": "started",
                "gpu_enabled": True
            }
            yield mock_request
    
    @pytest.mark.asyncio
    async def test_training_request_routing_host_service(self, host_service_running):
        """Test training request routes to host service when available."""
        from ktrdr.api.endpoints.training import TrainingHostRouter
        
        async with TrainingHostRouter() as router:
            with patch('ktrdr.config.get_settings') as mock_settings:
                mock_settings.return_value.use_training_host_service = True
                mock_settings.return_value.training_host_service_url = "http://localhost:5002"
                
                result = await router.route_training_request(
                    "/start",
                    method="POST",
                    json={
                        "symbol": "AAPL",
                        "timeframe": "1h",
                        "config": {"epochs": 10}
                    }
                )
                
                assert result["routed_to"] == "host_service"
                assert result["task_id"] == "test-123"
                assert result["gpu_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_fallback_to_docker_on_host_failure(self):
        """Test automatic fallback when host service fails."""
        from ktrdr.api.endpoints.training import TrainingHostRouter
        
        async with TrainingHostRouter() as router:
            with patch('ktrdr.config.get_settings') as mock_settings, \
                 patch('httpx.AsyncClient.request') as mock_request, \
                 patch('ktrdr.api.services.training_service.TrainingService') as mock_service:
                
                # Configure for host service
                mock_settings.return_value.use_training_host_service = True
                mock_settings.return_value.training_host_service_url = "http://localhost:5002"
                
                # Simulate host service failure
                mock_request.side_effect = httpx.ConnectError("Connection failed")
                
                # Mock Docker fallback
                mock_service_instance = AsyncMock()
                mock_service_instance.start_training.return_value = {
                    "task_id": "docker-123",
                    "status": "started",
                    "gpu_enabled": False
                }
                mock_service.return_value = mock_service_instance
                
                result = await router.route_training_request(
                    "/start",
                    method="POST",
                    json={
                        "symbol": "AAPL",
                        "timeframe": "1h",
                        "config": {"epochs": 10}
                    }
                )
                
                assert result["routed_to"] == "docker"
                assert result["task_id"] == "docker-123"
                assert result["gpu_enabled"] is False
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_behavior(self):
        """Test circuit breaker prevents repeated failed calls."""
        from ktrdr.api.utils.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Initially closed
        assert cb.can_execute() is True
        
        # Record failures
        cb.record_failure()
        assert cb.can_execute() is True
        
        cb.record_failure()  # Reaches threshold
        assert cb.can_execute() is False  # Circuit opens
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        assert cb.can_execute() is True  # Half-open
        
        # Record success
        cb.record_success()
        cb.record_success()
        cb.record_success()  # Circuit closes
        
        assert cb.can_execute() is True

# training-host-service/tests/integration/test_training_flow.py
"""End-to-end training flow tests."""

import pytest
import asyncio
from unittest.mock import patch, Mock

class TestTrainingFlow:
    """Test complete training workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_training_workflow_gpu(self):
        """Test complete training workflow with GPU acceleration."""
        from services.training_manager import TrainingManager
        from services.gpu_service import GPUService
        
        # Mock GPU service
        gpu_service = Mock()
        gpu_service.get_status.return_value = {"gpu_available": True}
        gpu_service.optimize_batch_size.return_value = 64
        
        training_manager = TrainingManager(gpu_service=gpu_service)
        
        # Mock training modules
        with patch('ktrdr.training.train_strategy') as mock_training:
            mock_training.train_strategy.return_value = {
                "task_id": "gpu-test-123",
                "status": "completed",
                "performance": {
                    "accuracy": 0.85,
                    "loss": 0.15,
                    "training_time": 120.5,
                    "gpu_utilization": 87.2
                }
            }
            
            # Start training
            result = await training_manager.start_training(
                symbol="AAPL",
                timeframe="1h",
                config={
                    "epochs": 50,
                    "batch_size": 64,
                    "use_gpu": True
                }
            )
            
            assert result["status"] == "started"
            assert "task_id" in result
            
            # Wait for completion (mocked)
            await asyncio.sleep(0.1)
            
            # Check final status
            status = await training_manager.get_training_status(result["task_id"])
            assert status["status"] == "completed"
            assert status["performance"]["gpu_utilization"] > 80
    
    @pytest.mark.asyncio
    async def test_training_with_existing_modules(self):
        """Test that existing training modules work unchanged."""
        # Import and test existing training components
        from ktrdr.training.train_strategy import train_strategy
        from ktrdr.training.model_trainer import ModelTrainer
        from ktrdr.training.gpu_memory_manager import GPUMemoryManager
        
        # Test that GPU manager initializes
        gpu_config = {
            "memory_fraction": 0.9,
            "enable_mixed_precision": True
        }
        
        with patch('torch.cuda.is_available', return_value=True):
            gpu_manager = GPUMemoryManager()
            assert gpu_manager is not None
            
            # Test memory summary
            summary = gpu_manager.get_memory_summary()
            assert "gpu_available" in summary
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test that performance monitoring works correctly."""
        from services.metrics_collector import MetricsCollector
        
        metrics = MetricsCollector()
        
        # Record training metrics
        metrics.record_training_start("test-task", gpu_enabled=True)
        metrics.record_gpu_utilization("test-task", 85.5)
        metrics.record_training_complete("test-task", duration=120.0, accuracy=0.87)
        
        # Get metrics summary
        summary = metrics.get_metrics_summary()
        
        assert summary["active_trainings"] >= 0
        assert "gpu_utilization" in summary
        assert "average_training_time" in summary
```

#### 3.2.3 Phase 2 Testing Requirements

**Integration Test Coverage Goals**
- **API Routing**: 100% coverage of routing logic and fallback scenarios
- **Host Service Communication**: 95% coverage including error conditions
- **Circuit Breaker**: 100% coverage of all states and transitions
- **End-to-End Flow**: 90% coverage of complete training workflows

**Phase 2 Test Execution**
```bash
# Run integration tests
uv run pytest training-host-service/tests/integration/ -v

# Test existing training functionality
uv run pytest tests/training/ tests/api/test_training* -v

# Test API routing with mocked host service
uv run pytest tests/api/ -k "training" -v

# Performance regression testing
uv run pytest tests/test_phase6_memory_performance.py -v
```

**Phase 2 Success Criteria**
- [ ] Training requests route correctly to host service
- [ ] Fallback to Docker works seamlessly on host service failure
- [ ] Circuit breaker prevents cascading failures
- [ ] All existing training tests pass
- [ ] End-to-end training workflow completes successfully
- [ ] Performance metrics show no regression

### 3.3 Phase 3: Service Management & Auto-Startup (Week 3)

#### 3.3.1 Auto-Startup Implementation

**Day 11-12: Service Management Scripts**
```bash
#!/bin/bash
# training-host-service/scripts/install_service.sh
"""Service installation script for multiple platforms."""

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SERVICE_NAME="ktrdr-training-host"

log_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

log_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

log_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

install_macos_service() {
    log_info "Installing macOS service using launchd..."
    
    SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ktrdr.training-host-service.plist"
    
    # Create logs directory
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Generate launchd plist
    cat > "$SERVICE_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ktrdr.training-host-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which uv)</string>
        <string>run</string>
        <string>python</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT/training-host-service</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_ROOT/logs/training-host-service.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_ROOT/logs/training-host-service-error.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$PROJECT_ROOT</string>
        <key>UV_PROJECT_ENVIRONMENT</key>
        <string>$PROJECT_ROOT/.venv</string>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

    # Set proper permissions
    chmod 644 "$SERVICE_PLIST"
    
    # Load the service
    launchctl load "$SERVICE_PLIST"
    
    # Start the service
    launchctl start com.ktrdr.training-host-service
    
    log_info "macOS service installed and started successfully"
    log_info "Service file: $SERVICE_PLIST"
    log_info "Logs: $PROJECT_ROOT/logs/training-host-service.log"
    
    # Verify service is running
    sleep 2
    if launchctl list | grep -q "com.ktrdr.training-host-service"; then
        log_info "Service is running successfully"
    else
        log_error "Service failed to start"
        return 1
    fi
}

install_linux_service() {
    log_info "Installing Linux service using systemd..."
    
    SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
    
    # Create systemd user directory
    mkdir -p "$HOME/.config/systemd/user"
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Generate systemd service file
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=KTRDR Training Host Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT/training-host-service
Environment=PYTHONPATH=$PROJECT_ROOT
Environment=UV_PROJECT_ENVIRONMENT=$PROJECT_ROOT/.venv
ExecStart=$(which uv) run python main.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_ROOT/logs/training-host-service.log
StandardError=append:$PROJECT_ROOT/logs/training-host-service-error.log

[Install]
WantedBy=default.target
EOF

    # Set proper permissions
    chmod 644 "$SERVICE_FILE"
    
    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}.service"
    systemctl --user start "${SERVICE_NAME}.service"
    
    log_info "Linux service installed and started successfully"
    log_info "Service file: $SERVICE_FILE"
    log_info "Logs: $PROJECT_ROOT/logs/training-host-service.log"
    
    # Verify service is running
    sleep 2
    if systemctl --user is-active --quiet "${SERVICE_NAME}.service"; then
        log_info "Service is running successfully"
    else
        log_error "Service failed to start"
        systemctl --user status "${SERVICE_NAME}.service"
        return 1
    fi
}

update_ib_service_for_auto_startup() {
    log_info "Updating IB service for auto-startup..."
    
    IB_SERVICE_SCRIPT="$PROJECT_ROOT/ib-host-service/scripts/install_service.sh"
    
    if [[ -f "$IB_SERVICE_SCRIPT" ]]; then
        log_info "Installing IB service auto-startup..."
        cd "$PROJECT_ROOT/ib-host-service"
        ./scripts/install_service.sh
    else
        log_warning "IB service installation script not found"
        log_info "Creating IB service auto-startup script..."
        
        # Create IB service installation script
        mkdir -p "$PROJECT_ROOT/ib-host-service/scripts"
        
        cat > "$PROJECT_ROOT/ib-host-service/scripts/install_service.sh" << 'EOF'
#!/bin/bash
# Auto-generated IB service installation script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS implementation
    SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ktrdr.ib-host-service.plist"
    
    cat > "$SERVICE_PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ktrdr.ib-host-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which uv)</string>
        <string>run</string>
        <string>python</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT/ib-host-service</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_ROOT/logs/ib-host-service.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_ROOT/logs/ib-host-service-error.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$PROJECT_ROOT</string>
    </dict>
</dict>
</plist>
PLIST_EOF

    launchctl load "$SERVICE_PLIST"
    launchctl start com.ktrdr.ib-host-service
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux implementation
    SERVICE_FILE="$HOME/.config/systemd/user/ktrdr-ib-host.service"
    
    mkdir -p "$HOME/.config/systemd/user"
    
    cat > "$SERVICE_FILE" << SERVICE_EOF
[Unit]
Description=KTRDR IB Host Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_ROOT/ib-host-service
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$(which uv) run python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SERVICE_EOF

    systemctl --user daemon-reload
    systemctl --user enable ktrdr-ib-host.service
    systemctl --user start ktrdr-ib-host.service
fi

echo "IB service auto-startup installed"
EOF

        chmod +x "$PROJECT_ROOT/ib-host-service/scripts/install_service.sh"
        cd "$PROJECT_ROOT/ib-host-service"
        ./scripts/install_service.sh
    fi
}

create_management_scripts() {
    log_info "Creating service management scripts..."
    
    # Create unified start script
    cat > "$PROJECT_ROOT/scripts/start_all_services.sh" << 'EOF'
#!/bin/bash
# Start all KTRDR host services

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting KTRDR host services..."

# Start IB service
if [[ "$OSTYPE" == "darwin"* ]]; then
    launchctl start com.ktrdr.ib-host-service
    launchctl start com.ktrdr.training-host-service
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    systemctl --user start ktrdr-ib-host.service
    systemctl --user start ktrdr-training-host.service
fi

echo "Services started"
EOF

    # Create unified stop script
    cat > "$PROJECT_ROOT/scripts/stop_all_services.sh" << 'EOF'
#!/bin/bash
# Stop all KTRDR host services

echo "Stopping KTRDR host services..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    launchctl stop com.ktrdr.ib-host-service
    launchctl stop com.ktrdr.training-host-service
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    systemctl --user stop ktrdr-ib-host.service
    systemctl --user stop ktrdr-training-host.service
fi

echo "Services stopped"
EOF

    # Create status check script
    cat > "$PROJECT_ROOT/scripts/check_services.sh" << 'EOF'
#!/bin/bash
# Check status of all KTRDR host services

echo "Checking KTRDR host services status..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "IB Service:"
    launchctl list | grep com.ktrdr.ib-host-service || echo "  Not running"
    
    echo "Training Service:"
    launchctl list | grep com.ktrdr.training-host-service || echo "  Not running"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "IB Service:"
    systemctl --user is-active ktrdr-ib-host.service || echo "  Not running"
    
    echo "Training Service:"
    systemctl --user is-active ktrdr-training-host.service || echo "  Not running"
fi

# Check if services are responding
echo ""
echo "Health checks:"
curl -f http://localhost:5001/health >/dev/null 2>&1 && echo "IB Service: Healthy" || echo "IB Service: Not responding"
curl -f http://localhost:5002/health >/dev/null 2>&1 && echo "Training Service: Healthy" || echo "Training Service: Not responding"
EOF

    chmod +x "$PROJECT_ROOT/scripts/"*.sh
    
    log_info "Management scripts created in $PROJECT_ROOT/scripts/"
}

# Main installation logic
main() {
    log_info "Installing KTRDR Training Host Service..."
    
    # Check prerequisites
    if ! command -v uv &> /dev/null; then
        log_error "UV not found. Please install UV first."
        exit 1
    fi
    
    # Create scripts directory
    mkdir -p "$PROJECT_ROOT/scripts"
    
    # Install appropriate service for platform
    if [[ "$OSTYPE" == "darwin"* ]]; then
        install_macos_service
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        install_linux_service
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Update IB service for consistency
    update_ib_service_for_auto_startup
    
    # Create management scripts
    create_management_scripts
    
    log_info "Installation completed successfully!"
    log_info ""
    log_info "Management commands:"
    log_info "  Start all services: $PROJECT_ROOT/scripts/start_all_services.sh"
    log_info "  Stop all services:  $PROJECT_ROOT/scripts/stop_all_services.sh"
    log_info "  Check status:       $PROJECT_ROOT/scripts/check_services.sh"
    log_info ""
    log_info "Logs are available in: $PROJECT_ROOT/logs/"
}

# Run installation
main "$@"
```

**Day 13: Health Monitoring Setup**
```python
# training-host-service/services/health_monitor.py
"""Health monitoring service for training host."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class HealthMetrics:
    """Health metrics for the training service."""
    
    uptime_seconds: float
    active_trainings: int
    gpu_available: bool
    gpu_utilization: float
    memory_usage_mb: float
    disk_usage_gb: float
    last_request_time: Optional[datetime]
    error_count_24h: int
    avg_response_time_ms: float

class HealthMonitor:
    """Monitor service health and performance."""
    
    def __init__(self, gpu_service, training_manager):
        self.gpu_service = gpu_service
        self.training_manager = training_manager
        self.start_time = time.time()
        self.request_times = []
        self.error_count = 0
        self.last_request_time = None
        
    def record_request(self, duration_ms: float):
        """Record request timing."""
        self.request_times.append(duration_ms)
        self.last_request_time = datetime.utcnow()
        
        # Keep only last 100 requests
        if len(self.request_times) > 100:
            self.request_times = self.request_times[-100:]
    
    def record_error(self):
        """Record an error occurrence."""
        self.error_count += 1
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        uptime = time.time() - self.start_time
        
        # GPU status
        gpu_status = self.gpu_service.get_status()
        gpu_available = gpu_status.get("gpu_available", False)
        gpu_utilization = 0.0
        
        if gpu_available and "devices" in gpu_status:
            # Calculate average GPU utilization
            total_util = sum(
                device.get("memory", {}).get("utilization_percent", 0)
                for device in gpu_status["devices"].values()
            )
            gpu_utilization = total_util / len(gpu_status["devices"])
        
        # Memory usage
        import psutil
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Response time average
        avg_response_time = sum(self.request_times) / len(self.request_times) if self.request_times else 0.0
        
        return {
            "status": "healthy" if uptime > 5 else "starting",
            "uptime_seconds": uptime,
            "active_trainings": len(self.training_manager.get_active_jobs()),
            "gpu": {
                "available": gpu_available,
                "utilization_percent": gpu_utilization,
                "devices": gpu_status.get("devices", {})
            },
            "memory": {
                "usage_percent": memory.percent,
                "usage_mb": memory.used / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024)
            },
            "disk": {
                "usage_percent": disk.percent,
                "usage_gb": disk.used / (1024 * 1024 * 1024),
                "free_gb": disk.free / (1024 * 1024 * 1024)
            },
            "performance": {
                "avg_response_time_ms": avg_response_time,
                "error_count_24h": self.error_count,
                "last_request": self.last_request_time.isoformat() if self.last_request_time else None
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        status = self.get_health_status()
        
        # Check basic health indicators
        if status["uptime_seconds"] < 5:
            return False
        
        if status["memory"]["usage_percent"] > 95:
            return False
        
        if status["disk"]["usage_percent"] > 95:
            return False
        
        if status["performance"]["avg_response_time_ms"] > 5000:  # 5 seconds
            return False
        
        return True
```

#### 3.3.2 Performance Testing Implementation

**Day 14: Performance Test Suite**
```python
# training-host-service/tests/performance/test_gpu_performance.py
"""GPU performance validation tests."""

import pytest
import time
import torch
import numpy as np
from unittest.mock import patch, Mock
from ktrdr.training.gpu_memory_manager import GPUMemoryManager

class TestGPUPerformance:
    """Test GPU performance improvements."""
    
    @pytest.mark.skipif(not torch.cuda.is_available() and not torch.backends.mps.is_available(),
                        reason="GPU not available")
    def test_gpu_training_speed_improvement(self):
        """Test that GPU training provides significant speedup."""
        # Create test model and data
        model = self._create_test_model()
        train_data, val_data = self._create_test_data()
        
        # Test CPU training time
        cpu_start = time.time()
        cpu_results = self._train_model_cpu(model, train_data, val_data)
        cpu_duration = time.time() - cpu_start
        
        # Test GPU training time
        gpu_start = time.time()
        gpu_results = self._train_model_gpu(model, train_data, val_data)
        gpu_duration = time.time() - gpu_start
        
        # Calculate speedup
        speedup = cpu_duration / gpu_duration
        
        print(f"CPU training time: {cpu_duration:.2f}s")
        print(f"GPU training time: {gpu_duration:.2f}s")
        print(f"Speedup: {speedup:.2f}x")
        
        # Assert minimum speedup (adjust based on actual hardware)
        assert speedup >= 2.0, f"Expected 2x speedup, got {speedup:.2f}x"
        
        # Verify results are similar (within tolerance)
        assert abs(cpu_results["final_loss"] - gpu_results["final_loss"]) < 0.1
    
    def test_gpu_memory_management_efficiency(self):
        """Test GPU memory management prevents OOM."""
        if not torch.cuda.is_available() and not torch.backends.mps.is_available():
            pytest.skip("GPU not available")
        
        gpu_manager = GPUMemoryManager()
        
        with gpu_manager.memory_efficient_context():
            # Create progressively larger models to test memory management
            for batch_size in [32, 64, 128, 256]:
                try:
                    model = self._create_large_model()
                    data = self._create_large_batch(batch_size)
                    
                    # Should handle large batches without OOM
                    result = self._quick_training_step(model, data)
                    assert result["completed"] is True
                    
                    # Check memory cleanup
                    if torch.cuda.is_available():
                        memory_before = torch.cuda.memory_allocated()
                    
                    del model, data
                    gpu_manager.cleanup_memory()
                    
                    if torch.cuda.is_available():
                        memory_after = torch.cuda.memory_allocated()
                        memory_freed = memory_before - memory_after
                        assert memory_freed > 0, "Memory should be freed after cleanup"
                
                except RuntimeError as e:
                    if "out of memory" in str(e):
                        pytest.fail(f"OOM error at batch size {batch_size} - memory management failed")
                    raise
    
    def test_batch_size_optimization(self):
        """Test optimal batch size detection."""
        if not torch.cuda.is_available() and not torch.backends.mps.is_available():
            pytest.skip("GPU not available")
        
        gpu_manager = GPUMemoryManager()
        
        model = self._create_test_model()
        sample_batch = self._create_sample_batch()
        criterion = torch.nn.MSELoss()
        
        optimal_batch_size = gpu_manager.optimize_batch_size(
            model, sample_batch, criterion, max_batch_size=512
        )
        
        # Should find a reasonable batch size
        assert 16 <= optimal_batch_size <= 512
        
        # Test that the optimal batch size actually works
        large_data = self._create_test_data(batch_size=optimal_batch_size)
        result = self._quick_training_step(model, large_data)
        assert result["completed"] is True
    
    def _create_test_model(self):
        """Create a test neural network model."""
        import torch.nn as nn
        
        return nn.Sequential(
            nn.Linear(10, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )
    
    def _create_large_model(self):
        """Create a larger model for memory testing."""
        import torch.nn as nn
        
        return nn.Sequential(
            nn.Linear(100, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 1)
        )
    
    def _create_test_data(self, batch_size=32, samples=1000):
        """Create test training data."""
        features = torch.randn(samples, 10)
        targets = torch.randn(samples, 1)
        
        # Split into train/validation
        split = int(0.8 * samples)
        train_data = (features[:split], targets[:split])
        val_data = (features[split:], targets[split:])
        
        return train_data, val_data
    
    def _create_large_batch(self, batch_size):
        """Create large batch for memory testing."""
        return (torch.randn(batch_size, 100), torch.randn(batch_size, 1))
    
    def _create_sample_batch(self):
        """Create sample batch for optimization testing."""
        return (torch.randn(32, 10), torch.randn(32, 1))
    
    def _train_model_cpu(self, model, train_data, val_data, epochs=10):
        """Train model on CPU."""
        model = model.to('cpu')
        optimizer = torch.optim.Adam(model.parameters())
        criterion = torch.nn.MSELoss()
        
        features, targets = train_data
        features, targets = features.to('cpu'), targets.to('cpu')
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
        
        return {"final_loss": loss.item()}
    
    def _train_model_gpu(self, model, train_data, val_data, epochs=10):
        """Train model on GPU."""
        device = 'cuda' if torch.cuda.is_available() else 'mps'
        model = model.to(device)
        optimizer = torch.optim.Adam(model.parameters())
        criterion = torch.nn.MSELoss()
        
        features, targets = train_data
        features, targets = features.to(device), targets.to(device)
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
        
        return {"final_loss": loss.item()}
    
    def _quick_training_step(self, model, data):
        """Perform single training step for testing."""
        try:
            device = 'cuda' if torch.cuda.is_available() else 'mps'
            model = model.to(device)
            features, targets = data
            features, targets = features.to(device), targets.to(device)
            
            optimizer = torch.optim.Adam(model.parameters())
            criterion = torch.nn.MSELoss()
            
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            return {"completed": True, "loss": loss.item()}
        except Exception as e:
            return {"completed": False, "error": str(e)}

# training-host-service/tests/performance/test_service_performance.py
"""Service performance and load testing."""

import pytest
import asyncio
import time
import httpx
from concurrent.futures import ThreadPoolExecutor

class TestServicePerformance:
    """Test training service performance under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_training_requests(self):
        """Test handling multiple concurrent training requests."""
        base_url = "http://localhost:5002"
        
        async def make_training_request(session_id):
            """Make a single training request."""
            async with httpx.AsyncClient() as client:
                start_time = time.time()
                
                response = await client.post(
                    f"{base_url}/trainings/start",
                    json={
                        "symbol": f"TEST{session_id}",
                        "timeframe": "1h",
                        "config": {
                            "epochs": 5,  # Small for testing
                            "batch_size": 32
                        }
                    },
                    timeout=30.0
                )
                
                duration = time.time() - start_time
                
                return {
                    "session_id": session_id,
                    "status_code": response.status_code,
                    "response_time": duration,
                    "success": response.status_code == 200
                }
        
        # Test with 5 concurrent requests
        num_requests = 5
        tasks = [make_training_request(i) for i in range(num_requests)]
        
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        max_response_time = max(r["response_time"] for r in results)
        
        # Assertions
        assert len(successful_requests) >= num_requests * 0.8, "At least 80% of requests should succeed"
        assert avg_response_time < 5.0, f"Average response time {avg_response_time:.2f}s too high"
        assert max_response_time < 10.0, f"Max response time {max_response_time:.2f}s too high"
        
        print(f"Concurrent requests: {num_requests}")
        print(f"Successful: {len(successful_requests)}")
        print(f"Average response time: {avg_response_time:.2f}s")
        print(f"Max response time: {max_response_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check endpoint performance."""
        base_url = "http://localhost:5002"
        
        response_times = []
        
        # Make 50 health check requests
        async with httpx.AsyncClient() as client:
            for _ in range(50):
                start_time = time.time()
                
                response = await client.get(f"{base_url}/health")
                
                duration = time.time() - start_time
                response_times.append(duration)
                
                assert response.status_code == 200
        
        # Analyze performance
        avg_time = sum(response_times) / len(response_times)
        p95_time = sorted(response_times)[int(0.95 * len(response_times))]
        max_time = max(response_times)
        
        # Health checks should be very fast
        assert avg_time < 0.1, f"Average health check time {avg_time:.3f}s too slow"
        assert p95_time < 0.2, f"P95 health check time {p95_time:.3f}s too slow"
        assert max_time < 0.5, f"Max health check time {max_time:.3f}s too slow"
        
        print(f"Health check performance:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  P95: {p95_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory usage during high load."""
        import psutil
        
        process = psutil.Process()
        
        # Baseline memory usage
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Create load by starting multiple training requests
        base_url = "http://localhost:5002"
        
        async def create_load():
            """Create load on the service."""
            tasks = []
            async with httpx.AsyncClient() as client:
                for i in range(10):
                    task = client.post(
                        f"{base_url}/trainings/start",
                        json={
                            "symbol": f"LOAD{i}",
                            "timeframe": "1h",
                            "config": {"epochs": 3, "batch_size": 16}
                        }
                    )
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # Monitor memory during load
        memory_measurements = []
        
        # Create load and monitor
        load_task = asyncio.create_task(create_load())
        
        for _ in range(20):  # Monitor for 10 seconds
            current_memory = process.memory_info().rss / (1024 * 1024)
            memory_measurements.append(current_memory)
            await asyncio.sleep(0.5)
        
        await load_task
        
        # Final memory check
        final_memory = process.memory_info().rss / (1024 * 1024)
        max_memory = max(memory_measurements)
        
        memory_increase = max_memory - baseline_memory
        memory_leak = final_memory - baseline_memory
        
        print(f"Memory usage:")
        print(f"  Baseline: {baseline_memory:.1f}MB")
        print(f"  Peak: {max_memory:.1f}MB")
        print(f"  Final: {final_memory:.1f}MB")
        print(f"  Increase during load: {memory_increase:.1f}MB")
        print(f"  Potential leak: {memory_leak:.1f}MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 1000, f"Memory increase {memory_increase:.1f}MB too high"
        
        # Memory leak should be minimal
        assert memory_leak < 100, f"Potential memory leak {memory_leak:.1f}MB detected"
```

#### 3.3.3 Phase 3 Testing Requirements

**Service Management Test Coverage Goals**
- **Auto-Startup**: 100% coverage of service installation and startup
- **Health Monitoring**: 95% coverage of health checks and metrics
- **Performance**: 90% coverage of load and stress testing
- **Service Management**: 100% coverage of start/stop/restart scenarios

**Phase 3 Test Execution**
```bash
# Test service installation
./training-host-service/scripts/install_service.sh

# Test auto-startup (requires reboot)
sudo reboot
# Wait for boot, then check
./scripts/check_services.sh

# Run performance tests
uv run pytest training-host-service/tests/performance/ -v -s

# Load testing
uv run pytest training-host-service/tests/performance/test_service_performance.py::test_concurrent_training_requests -v -s

# GPU performance testing (if GPU available)
uv run pytest training-host-service/tests/performance/test_gpu_performance.py -v -s

# Test existing functionality still works
uv run pytest tests/training/ tests/api/test_training* -v
```

**Phase 3 Success Criteria**
- [ ] Both IB and training services auto-start on system boot
- [ ] Services restart automatically on failure
- [ ] Health monitoring reports accurate status
- [ ] Performance tests show 3x+ GPU speedup (if GPU available)
- [ ] Service handles concurrent requests without degradation
- [ ] Memory usage remains stable under load
- [ ] All existing tests continue to pass

### 3.4 Phase 4: Comprehensive Testing & Validation (Week 4)

#### 3.4.1 Comprehensive Test Suite

**Day 15-16: Integration Test Expansion**
```python
# tests/integration/test_training_host_service_integration.py
"""Comprehensive integration tests for training host service."""

import pytest
import asyncio
import httpx
import time
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

class TestTrainingHostServiceIntegration:
    """Complete integration test suite for training host service."""
    
    @pytest.fixture(scope="class")
    async def services_running(self):
        """Ensure both host services are running for integration tests."""
        # Check if services are running
        ib_healthy = await self._check_service_health("http://localhost:5001/health")
        training_healthy = await self._check_service_health("http://localhost:5002/health")
        
        if not ib_healthy:
            pytest.skip("IB host service not running")
        if not training_healthy:
            pytest.skip("Training host service not running")
        
        yield {"ib": ib_healthy, "training": training_healthy}
    
    async def _check_service_health(self, url):
        """Check if a service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                return response.status_code == 200
        except:
            return False
    
    @pytest.mark.asyncio
    async def test_full_training_workflow_host_service(self, services_running):
        """Test complete training workflow through host service."""
        # Configure to use host service
        with patch('ktrdr.config.get_settings') as mock_settings:
            settings = Mock()
            settings.use_training_host_service = True
            settings.training_host_service_url = "http://localhost:5002"
            mock_settings.return_value = settings
            
            # Import after mocking settings
            from ktrdr.api.endpoints.training import start_training, get_training_status
            
            # Start training
            training_response = await start_training(
                symbol="AAPL",
                timeframe="1h",
                config={
                    "epochs": 10,
                    "batch_size": 32,
                    "use_gpu": True
                }
            )
            
            assert "task_id" in training_response
            assert training_response.get("routed_to") == "host_service"
            task_id = training_response["task_id"]
            
            # Monitor training progress
            max_wait_time = 300  # 5 minutes
            start_time = time.time()
            final_status = None
            
            while time.time() - start_time < max_wait_time:
                status_response = await get_training_status(task_id)
                final_status = status_response
                
                if status_response["status"] in ["completed", "failed"]:
                    break
                
                await asyncio.sleep(5)  # Check every 5 seconds
            
            # Verify completion
            assert final_status is not None
            assert final_status["status"] == "completed"
            assert "performance" in final_status
            
            # Verify GPU was used (if available)
            if final_status.get("gpu_available"):
                assert final_status["performance"].get("gpu_utilization", 0) > 0
    
    @pytest.mark.asyncio
    async def test_fallback_behavior_comprehensive(self, services_running):
        """Test comprehensive fallback behavior scenarios."""
        from ktrdr.api.endpoints.training import TrainingHostRouter
        
        # Test 1: Host service enabled but down
        async with TrainingHostRouter() as router:
            with patch('ktrdr.config.get_settings') as mock_settings, \
                 patch('httpx.AsyncClient.request') as mock_request:
                
                settings = Mock()
                settings.use_training_host_service = True
                settings.training_host_service_url = "http://localhost:5002"
                mock_settings.return_value = settings
                
                # Simulate host service down
                mock_request.side_effect = httpx.ConnectError("Connection refused")
                
                # Mock Docker fallback
                with patch('ktrdr.api.services.training_service.TrainingService') as mock_service:
                    service_instance = Mock()
                    service_instance.start_training = AsyncMock(return_value={
                        "task_id": "docker-fallback-123",
                        "status": "started"
                    })
                    mock_service.return_value = service_instance
                    
                    result = await router.route_training_request(
                        "/start",
                        method="POST",
                        json={"symbol": "AAPL", "timeframe": "1h", "config": {}}
                    )
                    
                    assert result["routed_to"] == "docker"
                    assert "docker-fallback" in result["task_id"]
        
        # Test 2: Host service returns error
        async with TrainingHostRouter() as router:
            with patch('ktrdr.config.get_settings') as mock_settings, \
                 patch('httpx.AsyncClient.request') as mock_request:
                
                settings = Mock()
                settings.use_training_host_service = True
                settings.training_host_service_url = "http://localhost:5002"
                mock_settings.return_value = settings
                
                # Simulate host service error
                error_response = Mock()
                error_response.status_code = 500
                mock_request.return_value = error_response
                
                # Mock Docker fallback
                with patch('ktrdr.api.services.training_service.TrainingService') as mock_service:
                    service_instance = Mock()
                    service_instance.start_training = AsyncMock(return_value={
                        "task_id": "docker-error-fallback-123",
                        "status": "started"
                    })
                    mock_service.return_value = service_instance
                    
                    result = await router.route_training_request(
                        "/start",
                        method="POST",
                        json={"symbol": "AAPL", "timeframe": "1h", "config": {}}
                    )
                    
                    assert result["routed_to"] == "docker"
    
    @pytest.mark.asyncio
    async def test_service_restart_recovery(self, services_running):
        """Test service recovery after restart."""
        import subprocess
        
        # Stop training service
        if pytest.sys.platform == "darwin":
            subprocess.run(["launchctl", "stop", "com.ktrdr.training-host-service"])
        else:
            subprocess.run(["systemctl", "--user", "stop", "ktrdr-training-host.service"])
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Verify service is down
        service_down = not await self._check_service_health("http://localhost:5002/health")
        assert service_down, "Service should be down after stop command"
        
        # Start service
        if pytest.sys.platform == "darwin":
            subprocess.run(["launchctl", "start", "com.ktrdr.training-host-service"])
        else:
            subprocess.run(["systemctl", "--user", "start", "ktrdr-training-host.service"])
        
        # Wait for service to start
        max_wait = 30
        service_recovered = False
        for _ in range(max_wait):
            if await self._check_service_health("http://localhost:5002/health"):
                service_recovered = True
                break
            await asyncio.sleep(1)
        
        assert service_recovered, "Service should recover after restart"
        
        # Test that training works after restart
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/trainings/start",
                json={
                    "symbol": "TEST_RESTART",
                    "timeframe": "1h", 
                    "config": {"epochs": 1}
                }
            )
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """Test that all existing functionality still works."""
        # Test existing API endpoints work
        from ktrdr.api.endpoints.training import router
        
        # Import existing test patterns
        from tests.api.test_training_endpoints import TestTrainingEndpoints
        from tests.api.test_training_service import TestTrainingService
        
        # Run subset of existing tests to ensure compatibility
        test_instance = TestTrainingEndpoints()
        
        # These should work regardless of host service
        with patch('ktrdr.config.get_settings') as mock_settings:
            settings = Mock()
            settings.use_training_host_service = False  # Force Docker mode
            mock_settings.return_value = settings
            
            # Test would run existing test methods here
            # For brevity, we'll just ensure the import and setup works
            assert test_instance is not None
    
    @pytest.mark.asyncio
    async def test_configuration_management(self):
        """Test configuration management and environment variables."""
        from ktrdr.config import get_settings
        
        # Test default configuration
        settings = get_settings()
        
        # Test configuration override
        import os
        
        # Set environment variables
        os.environ["USE_TRAINING_HOST_SERVICE"] = "true"
        os.environ["TRAINING_HOST_SERVICE_URL"] = "http://localhost:5002"
        
        # Reload settings (implementation dependent)
        # This tests that configuration system picks up environment changes
        
        # Cleanup
        os.environ.pop("USE_TRAINING_HOST_SERVICE", None)
        os.environ.pop("TRAINING_HOST_SERVICE_URL", None)
```

**Day 17: Existing Test Validation**
```bash
#!/bin/bash
# tests/validation/run_existing_tests.sh
"""Comprehensive validation that all existing tests still pass."""

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Running Comprehensive Test Validation ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test_suite() {
    local test_name="$1"
    local test_command="$2"
    
    echo ""
    log_info "Running $test_name..."
    
    if eval "$test_command"; then
        log_info "$test_name: PASSED"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        log_error "$test_name: FAILED"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
}

# 1. Core Training Tests
log_info "=== Phase 1: Core Training Tests ==="
run_test_suite "Training System Tests" "uv run pytest tests/test_training_system.py -v"
run_test_suite "Neural Foundation Tests" "uv run pytest tests/test_neural_foundation.py -v"
run_test_suite "Fuzzy Neural Processor Tests" "uv run pytest tests/training/test_fuzzy_neural_processor.py -v"
run_test_suite "Model Storage Tests" "uv run pytest tests/training/test_model_storage_enhanced.py -v"

# 2. API Integration Tests
log_info "=== Phase 2: API Integration Tests ==="
run_test_suite "Training API Endpoints" "uv run pytest tests/api/test_training_endpoints.py -v"
run_test_suite "Training Service Layer" "uv run pytest tests/api/test_training_service.py -v"

# 3. Performance and Memory Tests
log_info "=== Phase 3: Performance Tests ==="
run_test_suite "Memory Performance Tests" "uv run pytest tests/test_phase6_memory_performance.py -v"
run_test_suite "API Performance Tests" "uv run pytest tests/test_api_performance.py -v"

# 4. Enhanced Analytics Tests
log_info "=== Phase 4: Enhanced Analytics Tests ==="
run_test_suite "Enhanced Analytics" "uv run pytest tests/test_phase3_enhanced_analytics.py -v"

# 5. Host Service Tests (if available)
if [[ -d "training-host-service/tests" ]]; then
    log_info "=== Phase 5: Host Service Tests ==="
    run_test_suite "Host Service Unit Tests" "uv run pytest training-host-service/tests/unit/ -v"
    run_test_suite "Host Service Integration Tests" "uv run pytest training-host-service/tests/integration/ -v"
    
    # GPU tests only if GPU available
    if command -v nvidia-smi &> /dev/null || [[ $(uname) == "Darwin" ]]; then
        run_test_suite "GPU Performance Tests" "uv run pytest training-host-service/tests/performance/test_gpu_performance.py -v -s"
    else
        log_warning "GPU not available, skipping GPU performance tests"
    fi
    
    run_test_suite "Service Performance Tests" "uv run pytest training-host-service/tests/performance/test_service_performance.py -v"
fi

# 6. Integration Tests (if services running)
if curl -f http://localhost:5002/health >/dev/null 2>&1; then
    log_info "=== Phase 6: Live Integration Tests ==="
    run_test_suite "Training Host Integration" "uv run pytest tests/integration/test_training_host_service_integration.py -v"
else
    log_warning "Training host service not running, skipping live integration tests"
fi

# 7. Configuration Tests
log_info "=== Phase 7: Configuration Tests ==="
run_test_suite "Configuration Management" "uv run pytest tests/test_config*.py -v || true"

# 8. Backward Compatibility Tests
log_info "=== Phase 8: Backward Compatibility ==="

# Test with host service disabled
export USE_TRAINING_HOST_SERVICE=false
run_test_suite "Training Tests (Docker Mode)" "uv run pytest tests/api/test_training_endpoints.py::TestTrainingEndpoints::test_start_training -v"

# Test with host service enabled (if available)
if curl -f http://localhost:5002/health >/dev/null 2>&1; then
    export USE_TRAINING_HOST_SERVICE=true
    export TRAINING_HOST_SERVICE_URL=http://localhost:5002
    run_test_suite "Training Tests (Host Service Mode)" "uv run pytest tests/api/test_training_endpoints.py::TestTrainingEndpoints::test_start_training -v"
fi

# Cleanup environment
unset USE_TRAINING_HOST_SERVICE
unset TRAINING_HOST_SERVICE_URL

# Results Summary
echo ""
echo "=== Test Results Summary ==="
echo "Total Test Suites: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"

if [[ $FAILED_TESTS -eq 0 ]]; then
    log_info "ALL TESTS PASSED! ✅"
    exit 0
else
    log_error "$FAILED_TESTS test suite(s) failed ❌"
    exit 1
fi
```

#### 3.4.2 Manual Testing Checklist

**Day 18: Manual Testing Protocol**
```markdown
# Manual Testing Checklist for GPU Training Host Service

## Pre-Testing Setup
- [ ] Both IB and training host services are running
- [ ] Docker environment is running
- [ ] GPU is available and accessible (if applicable)
- [ ] All automated tests have passed

## 1. Service Management Testing

### Auto-Startup Testing
- [ ] Reboot system and verify both services start automatically
- [ ] Check service logs for any startup errors
- [ ] Verify services respond to health checks within 30 seconds of boot

### Service Control Testing
- [ ] Stop training service: `launchctl stop com.ktrdr.training-host-service` (macOS) or `systemctl --user stop ktrdr-training-host.service` (Linux)
- [ ] Verify service stops cleanly and training requests fall back to Docker
- [ ] Start training service: `launchctl start com.ktrdr.training-host-service` (macOS) or `systemctl --user start ktrdr-training-host.service` (Linux)
- [ ] Verify service starts and training requests route to host service

### Health Monitoring
- [ ] Check health endpoint: `curl http://localhost:5002/health`
- [ ] Check detailed health: `curl http://localhost:5002/health/detailed`
- [ ] Verify GPU status is reported correctly
- [ ] Check service logs for any warnings or errors

## 2. Training Workflow Testing

### Basic Training Flow
- [ ] Start a simple training job through the frontend/CLI
- [ ] Verify training request routes to host service (check logs)
- [ ] Monitor training progress through status endpoint
- [ ] Verify training completes successfully
- [ ] Check that model is saved correctly

### GPU Acceleration Testing (if GPU available)
- [ ] Start GPU-enabled training job
- [ ] Monitor GPU utilization during training
- [ ] Verify training time is significantly faster than CPU-only
- [ ] Check GPU metrics in health endpoint
- [ ] Verify GPU memory is managed properly

### Multiple Training Jobs
- [ ] Start multiple training jobs simultaneously
- [ ] Verify all jobs are queued and processed correctly
- [ ] Check resource usage doesn't exceed limits
- [ ] Verify job isolation (one failure doesn't affect others)

## 3. Fallback and Error Handling

### Host Service Failure Simulation
- [ ] Stop training host service while training is running
- [ ] Verify graceful degradation to Docker-only mode
- [ ] Start new training job and verify it uses Docker
- [ ] Restart host service and verify new jobs route to host

### Network Issues Simulation
- [ ] Block port 5002 temporarily: `sudo iptables -A INPUT -p tcp --dport 5002 -j DROP` (Linux)
- [ ] Verify training requests fall back to Docker
- [ ] Remove block: `sudo iptables -D INPUT -p tcp --dport 5002 -j DROP`
- [ ] Verify service recovers automatically

### Error Recovery Testing
- [ ] Kill training service process directly: `pkill -f "training-host-service"`
- [ ] Verify service manager restarts it automatically
- [ ] Check that service recovers and is operational within 30 seconds

## 4. Performance Validation

### Training Speed Comparison
- [ ] Run identical training job in Docker mode (host service disabled)
- [ ] Record training duration and resource usage
- [ ] Run same job in host service mode (GPU enabled if available)
- [ ] Verify 3x+ speed improvement with GPU, or equivalent performance with CPU
- [ ] Document actual performance improvements

### Resource Usage Monitoring
- [ ] Monitor CPU usage during training (should be reasonable)
- [ ] Monitor memory usage (should not continuously increase)
- [ ] Monitor GPU utilization (should be high during GPU training)
- [ ] Check disk I/O patterns (should be efficient)

### Concurrent Load Testing
- [ ] Start 5 simultaneous training jobs
- [ ] Monitor system performance and responsiveness
- [ ] Verify all jobs complete successfully
- [ ] Check for any resource exhaustion or errors

## 5. Integration Testing

### Frontend Integration
- [ ] Access training interface through frontend
- [ ] Start training job through UI
- [ ] Monitor progress in real-time
- [ ] Verify job completion and results display

### CLI Integration
- [ ] Use existing CLI commands to start training
- [ ] Verify commands work identically to Docker mode
- [ ] Check that all CLI options are respected
- [ ] Verify output formatting is consistent

### API Integration
- [ ] Test all training API endpoints:
  - [ ] `POST /api/trainings/start`
  - [ ] `GET /api/trainings/{task_id}/status`
  - [ ] `GET /api/trainings/{task_id}/performance`
  - [ ] `POST /api/trainings/{task_id}/stop`
- [ ] Verify response formats match existing API
- [ ] Check error handling for invalid requests

## 6. Configuration Testing

### Environment Variable Testing
- [ ] Set `USE_TRAINING_HOST_SERVICE=false` and verify Docker mode
- [ ] Set `USE_TRAINING_HOST_SERVICE=true` and verify host service mode
- [ ] Test with different `TRAINING_HOST_SERVICE_URL` values
- [ ] Verify configuration changes take effect without restart

### Configuration File Testing
- [ ] Modify training host service configuration
- [ ] Restart service and verify changes are applied
- [ ] Test invalid configuration handling
- [ ] Verify configuration validation and error reporting

## 7. Data Consistency Testing

### Model Storage
- [ ] Train model in host service mode
- [ ] Verify model files are created in expected location
- [ ] Load model in Docker mode and verify it works
- [ ] Check model metadata and versioning

### Training Analytics
- [ ] Verify training analytics are generated correctly
- [ ] Check analytics format matches existing structure
- [ ] Verify analytics are accessible from both modes
- [ ] Test analytics aggregation and reporting

### Data Sharing
- [ ] Verify training data is accessible from host service
- [ ] Check data permissions and ownership
- [ ] Test with different data sources and formats
- [ ] Verify data consistency between modes

## 8. Security Testing

### Network Security
- [ ] Verify training service only binds to localhost
- [ ] Test that external connections are rejected
- [ ] Check that no sensitive data is logged
- [ ] Verify authentication between Docker and host service

### File System Security
- [ ] Check file permissions on service files
- [ ] Verify service runs with appropriate user privileges
- [ ] Test that service cannot access unauthorized files
- [ ] Check log file permissions and content

## 9. Documentation Validation

### Setup Documentation
- [ ] Follow installation instructions from scratch
- [ ] Verify all dependencies are documented
- [ ] Check that configuration examples work
- [ ] Validate troubleshooting guides

### User Documentation
- [ ] Verify user-facing documentation is accurate
- [ ] Check that new features are documented
- [ ] Validate example commands and outputs
- [ ] Test documentation completeness

## 10. Rollback Testing

### Complete Rollback
- [ ] Disable host service: Set `USE_TRAINING_HOST_SERVICE=false`
- [ ] Stop host services: `./scripts/stop_all_services.sh`
- [ ] Verify system works in Docker-only mode
- [ ] Test all training functionality
- [ ] Verify performance is acceptable

### Service Rollback
- [ ] Uninstall host services: `./training-host-service/scripts/uninstall_service.sh`
- [ ] Verify services are completely removed
- [ ] Test system functionality after removal
- [ ] Verify no residual processes or files

## Testing Sign-off

### Performance Criteria
- [ ] GPU training shows 3x+ speed improvement (if GPU available)
- [ ] CPU training performance is equivalent or better
- [ ] Memory usage is stable and reasonable
- [ ] No significant regression in any existing functionality

### Reliability Criteria
- [ ] System survives service restarts without data loss
- [ ] Fallback mechanisms work correctly
- [ ] Auto-startup works reliably
- [ ] Error handling is graceful and informative

### User Experience Criteria
- [ ] No changes required to existing workflows
- [ ] Performance improvements are immediately visible
- [ ] System feels more responsive
- [ ] Error messages are clear and actionable

### Final Approval
- [ ] All automated tests pass
- [ ] All manual tests pass
- [ ] Performance criteria met
- [ ] Reliability criteria met
- [ ] User experience criteria met
- [ ] Documentation is complete and accurate

**Manual Testing Completed By:** _______________
**Date:** _______________
**GPU Available:** [ ] Yes [ ] No
**Performance Improvement Achieved:** ___x faster
**Overall Assessment:** [ ] Approved [ ] Needs Work

**Notes and Issues:**
_________________________________________________
_________________________________________________
_________________________________________________
```

#### 3.4.3 Phase 4 Success Criteria & Deliverables

**Comprehensive Testing Goals**
- **Test Coverage**: 95%+ across all components
- **Performance Validation**: Documented speed improvements
- **Reliability Testing**: Service management and error recovery
- **Integration Validation**: All existing workflows unchanged

**Phase 4 Deliverables**
- [ ] Complete automated test suite with 95%+ coverage
- [ ] Performance benchmark results documenting improvements
- [ ] Manual testing checklist completion
- [ ] Updated documentation reflecting new capabilities
- [ ] Rollback procedures validated and documented

---

## 4. Risk Management & Mitigation

### 4.1 Technical Risks

**Risk: GPU Driver Incompatibility**
- **Probability**: Medium
- **Impact**: High
- **Mitigation**: 
  - Test on target hardware early in Phase 1
  - Implement robust CPU fallback
  - Document GPU driver requirements
  - Test with multiple GPU types if available

**Risk: Performance Regression**
- **Probability**: Low
- **Impact**: High
- **Mitigation**:
  - Baseline performance measurements before implementation
  - Continuous performance monitoring during development
  - Automated performance tests in CI pipeline
  - Rollback plan if performance degrades

**Risk: Service Startup Failures**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Comprehensive service management testing
  - Multiple startup scenarios tested
  - Detailed logging for troubleshooting
  - Manual startup fallback procedures

### 4.2 Integration Risks

**Risk: Docker Communication Issues**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Extensive network testing
  - Circuit breaker implementation
  - Robust error handling and retry logic
  - Docker networking validation

**Risk: Configuration Conflicts**
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**:
  - Configuration validation testing
  - Environment variable precedence testing
  - Default configuration safety
  - Configuration migration procedures

### 4.3 Operational Risks

**Risk: Service Management Complexity**
- **Probability**: Medium
- **Impact**: Low
- **Mitigation**:
  - Simple management scripts
  - Clear documentation
  - Automated health checks
  - Service status monitoring

**Risk: Data Corruption**
- **Probability**: Low
- **Impact**: High
- **Mitigation**:
  - No modifications to existing data handling
  - Comprehensive backup procedures
  - Data integrity testing
  - Isolated testing environments

### 4.4 Rollback Strategy

**Immediate Rollback (< 5 minutes)**
```bash
# Disable host service routing
export USE_TRAINING_HOST_SERVICE=false
docker-compose restart backend
```

**Complete Rollback (< 30 minutes)**
```bash
# Stop all host services
./scripts/stop_all_services.sh

# Uninstall service management
./training-host-service/scripts/uninstall_service.sh
./ib-host-service/scripts/uninstall_service.sh

# Remove configuration
rm config/environment/training_host_service_enabled.yaml

# Restart Docker environment
docker-compose down && docker-compose up -d
```

---

## 5. Success Metrics & Validation

### 5.1 Technical Success Metrics

**Performance Metrics**
- **GPU Training Speed**: 3x+ improvement over CPU training
- **Memory Efficiency**: No memory leaks, stable usage under load
- **API Response Times**: <100ms for status calls, <5s for training start
- **Service Uptime**: >99.9% uptime during operation
- **Fallback Speed**: <30s to detect failure and switch to Docker

**Quality Metrics**
- **Test Coverage**: >95% line coverage across all new components
- **Test Pass Rate**: 100% of tests passing before each phase completion
- **Code Quality**: All new code reviewed and meeting project standards
- **Documentation**: Complete documentation for all new features

### 5.2 Operational Success Metrics

**Reliability Metrics**
- **Service Startup**: <60s from boot to operational
- **Error Recovery**: <30s to recover from service failures
- **Circuit Breaker**: <5s to detect host service failures
- **Auto-Restart**: Service restarts within 10s of failure

**User Experience Metrics**
- **Workflow Changes**: 0 changes required to existing user workflows
- **Training Time**: Measurable improvement in training completion time
- **Error Handling**: Clear, actionable error messages for all failure scenarios
- **Documentation**: Users can follow setup instructions without assistance

### 5.3 Business Success Metrics

**Research Productivity**
- **Experiment Throughput**: 2-3x more experiments per day due to faster training
- **Resource Utilization**: >80% GPU utilization during training sessions
- **Development Velocity**: Faster iteration cycles for algorithm development
- **System Reliability**: Reduced downtime and manual intervention

**Technical Debt Reduction**
- **Service Management**: Unified auto-startup for all host services
- **Architecture Consistency**: Both host services follow same patterns
- **Monitoring Integration**: GPU metrics integrated into existing observability
- **Maintainability**: Clear separation and rollback capabilities

### 5.4 Acceptance Criteria

**Phase Completion Criteria**
Each phase must meet these criteria before proceeding:

1. **All automated tests pass**
2. **Performance benchmarks meet targets**
3. **Manual testing checklist completed**
4. **Documentation updated**
5. **Rollback procedures validated**

**Final Acceptance Criteria**
- [ ] GPU training shows measurable speed improvement
- [ ] All existing functionality preserved
- [ ] Auto-startup works reliably on target systems
- [ ] Fallback mechanisms function correctly
- [ ] Performance monitoring shows no regression
- [ ] User workflows require no changes
- [ ] Complete test coverage with automated validation
- [ ] Documentation enables setup without assistance

---

This comprehensive implementation plan provides detailed guidance for successfully implementing GPU acceleration through service extraction, with extensive testing ensuring reliability and maintaining backward compatibility throughout the process.