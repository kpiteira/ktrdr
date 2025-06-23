# Phase 0 Implementation Plan: Critical Infrastructure Fixes

## Overview

This document provides a thorough implementation plan for **Phase 0** of the KTRDR deployment evolution, focusing on resolving two critical blockers that prevent effective strategy research:

1. **IB Gateway Connectivity Issues** - Docker networking causes unreliable connections
2. **GPU Acceleration Blocked** - Docker prevents Apple M4 Pro GPU access (5-10x slower training)

## Solution Architecture

**Hybrid Approach**: Move problematic components (IB + Training) to host, keep stable services in Docker

```
Host Machine (macOS/Linux)
├── Native Processes
│   ├── IB Connector Service (Python)
│   │   └── Direct connection to IB Gateway/TWS
│   └── Training Service (Python)
│       └── Direct GPU access (Metal/CUDA)
│
└── Docker Environment
    ├── Frontend (React)
    ├── API Backend (FastAPI)
    ├── PostgreSQL
    ├── Redis
    └── MCP Server

Communication: Host ←→ Docker via exposed ports
```

## Implementation Timeline

### Week 1 Schedule

- **Day 1-2**: IB Connector Service
- **Day 3-4**: Backend Integration & Testing
- **Day 5-7**: Validation & 24-hour Stability Testing

**Note**: Training service extraction deferred to Phase 1+ for proper architectural planning

## IB Connector Service Implementation

### Problem Analysis

**Current Data Flow (Docker - Problem)**:
```
DataManager → IbDataAdapter → IB Components → Docker Network → IB Gateway
                                              ^^^^^^^^^^^^^
                                              (Breaks after sleep/wake, port issues)
```

**Solution Data Flow (Host Service)**:
```
DataManager → HTTP Call → Host IB Service → IB Components → Direct Connection → IB Gateway
              ^^^^^^^^^   ^^^^^^^^^^^^^^^
              (Same interface) (Same code, better location)
```

### Current State Analysis

**Existing IB Integration Assets (TO REUSE, NOT EXTRACT):**
- `ktrdr/data/ib_data_adapter.py` - Main data interface that needs modification
- `ktrdr/ib/` modules - Will be imported by host service (not copied)
- `ktrdr/api/endpoints/ib.py` - Container endpoints (keep unchanged)

**Key Insight**: We're not extracting/copying code, we're adding a **thin HTTP wrapper** around existing working code.

### Day 1: Host Service Foundation

**Goal**: Create minimal HTTP wrapper around existing IB integration

**Tasks**:
1. **Create Simple Service Structure**
   - Create `ib-host-service/` directory at project root
   - Set up FastAPI app that imports existing `ktrdr.ib` modules
   - Configure to run on host with direct IB Gateway access

2. **Required Endpoints (Based on IbDataAdapter interface)**
   - `POST /data/historical` - Historical OHLCV data
   - `POST /data/validate` - Symbol validation + metadata
   - `GET /data/head-timestamp` - Earliest available data timestamp  
   - `GET /health` - Connection status and stats

3. **Configuration Setup**
   - Use same environment variables as existing IB config
   - Import existing `ktrdr.config.ib_config` settings
   - Set up logging compatible with existing patterns

### Day 2: Backend Integration

**Goal**: Modify IbDataAdapter to use host service when configured

**Tasks**:
1. **Modify IbDataAdapter**
   - Add `use_host_service` and `host_service_url` parameters
   - Keep existing direct IB integration as fallback
   - Add HTTP client for host service communication

2. **Environment Configuration**
   - Add `IB_USE_HOST_SERVICE=true/false` environment variable
   - Add `IB_HOST_SERVICE_URL=http://localhost:5001` 
   - Update docker-compose for host communication

3. **Container Endpoint Compatibility**
   - Existing `ktrdr/api/endpoints/ib.py` endpoints **stay exactly the same**
   - DataManager automatically uses host service if configured
   - No external API changes required

### Service Architecture

**Simple Directory Structure**:
```
ib-host-service/
├── requirements.txt      # Same as backend: ib_insync, fastapi, etc.  
├── main.py              # FastAPI app entry point
├── config.py            # Import from ktrdr.config.ib_config
└── endpoints/
    ├── data.py          # The 4 endpoints above
    └── health.py        # Health check endpoint
```

**Key Implementation Pattern**:
```python
# ib-host-service/endpoints/data.py
from ktrdr.ib import IbDataFetcher, IbSymbolValidator  # Import existing modules!

@app.post("/data/historical") 
async def get_historical_data(request: HistoricalDataRequest):
    # Use the EXACT same code that's currently in IbDataAdapter
    fetcher = IbDataFetcher()
    result = await fetcher.fetch_historical_data(
        request.symbol, request.timeframe, request.start, request.end
    )
    return result.to_json()
```

**Modified IbDataAdapter Pattern**:
```python
# ktrdr/data/ib_data_adapter.py - Modified
class IbDataAdapter(ExternalDataProvider):
    def __init__(self, use_host_service=False, host_service_url=None):
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url
        
        if not use_host_service:
            # Initialize IB components directly (current way)
            self.data_fetcher = IbDataFetcher()
            self.symbol_validator = IbSymbolValidator()

    async def fetch_historical_data(self, symbol, timeframe, start, end, instrument_type=None):
        if self.use_host_service:
            # Make HTTP call to host service
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.host_service_url}/data/historical", 
                    json={...})
                return pd.read_json(response.json())
        else:
            # Use existing IB integration directly (current way)
            return await self.data_fetcher.fetch_historical_data(...)
```

**Benefits of This Approach**:
- **No code duplication** - host service imports existing `ktrdr.ib` modules
- **No new container endpoints** - existing API stays the same
- **Easy rollback** - environment variable toggle
- **Same working code** - just runs in different network context

**Note**: Training service extraction has been deferred to Phase 1+ for proper architectural planning. Current Phase 0 focuses solely on critical IB connectivity issues.

## Backend Integration

### Current State Analysis

**Backend Integration Points:**
- `ktrdr/api/endpoints/ib.py` - IB-related API endpoints
- `ktrdr/data/ib_data_adapter.py` - Main integration point that needs modification
- `ktrdr/api/dependencies.py` - Dependency injection
- `docker/docker-compose.yml` - Container orchestration

### Day 3: Environment Configuration

**Goal**: Configure backend to communicate with IB Connector host service

**Tasks**:
1. **Environment Variables**
   - Add `IB_CONNECTOR_URL` to docker-compose
   - Update `ktrdr/config/settings.py` to support host service URL
   - Implement feature toggle for using host service vs. native integration

2. **Docker Compose Updates**
   - Add `extra_hosts` configuration for Docker-to-host communication
   - Update environment variables section
   - Maintain backward compatibility with existing setup

3. **Health Check Integration**
   - Update existing health endpoint in `ktrdr/api/endpoints/system.py`
   - Add IB Connector host service connectivity checks
   - Implement circuit breaker pattern for host service failures

### Day 4: IB Data Adapter Modifications

**Goal**: Update IbDataAdapter to use host service when configured

**Tasks**:
1. **IB Data Adapter Updates**
   - Modify `ktrdr/data/ib_data_adapter.py` to optionally use host service
   - Implement fallback to existing IB integration if host service unavailable
   - Maintain existing interface for seamless integration

2. **API Endpoint Compatibility**
   - Existing `ktrdr/api/endpoints/ib.py` endpoints **stay exactly the same**
   - Changes are internal to IbDataAdapter only
   - No external API changes required

3. **Error Handling**
   - Add host service connectivity error handling
   - Implement retry logic with exponential backoff
   - Maintain existing error response formats

### Integration Architecture

**Configuration Management**:
```python
# ktrdr/config/settings.py additions
IB_CONNECTOR_URL = os.getenv("IB_CONNECTOR_URL", None)
USE_IB_HOST_SERVICE = os.getenv("USE_IB_HOST_SERVICE", "false").lower() == "true"
```

**IbDataAdapter Modification Pattern**:
```python
# ktrdr/data/ib_data_adapter.py modifications
class IbDataAdapter(ExternalDataProvider):
    def __init__(self, use_host_service=False, host_service_url=None):
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url
        
        if not use_host_service:
            # Initialize IB components directly (current way)
            self.data_fetcher = IbDataFetcher()
            self.symbol_validator = IbSymbolValidator()

    async def fetch_historical_data(self, symbol, timeframe, start, end, instrument_type=None):
        if self.use_host_service:
            # Make HTTP call to host service
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.host_service_url}/data/historical", 
                    json={...})
                return pd.read_json(response.json())
        else:
            # Use existing IB integration directly (current way)
            return await self.data_fetcher.fetch_historical_data(...)
```

**Docker Compose Integration**:
```yaml
# docker/docker-compose.yml updates
services:
  backend:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - IB_CONNECTOR_URL=http://host.docker.internal:5001
      - USE_IB_HOST_SERVICE=true
```

## Validation & Testing

### Day 5-7: Comprehensive Testing

**Goal**: Validate IB Connector service works and meets success criteria

**Testing Areas**:

1. **IB Connector Service Validation**
   - **Stability Test**: 24+ hour connection stability
   - **Sleep/Wake Test**: Handle macOS sleep/wake cycles
   - **Load Test**: 1000+ historical data requests without failure
   - **Reconnection Test**: Automatic reconnection within 30 seconds
   - **Rate Limit Test**: Respect IB API limits (50 req/sec, 2 sec gaps)

2. **Backend Integration Validation**
   - **IbDataAdapter Test**: Verify host service integration works
   - **API Compatibility Test**: Existing endpoints work unchanged
   - **Fallback Test**: Graceful fallback to direct IB when host service unavailable
   - **Error Handling Test**: Proper error responses when host service fails

3. **End-to-End Pipeline Test**
   - **Data Collection Workflow**: Symbol validation → Historical data download → Storage
   - **Error Recovery**: Graceful handling of service failures
   - **Performance Test**: Compare data collection speed vs. current Docker setup

### Success Criteria Validation

**Phase 0 Success Metrics** (Revised):
- ✓ IB connection stable for 24+ hours
- ✓ Data collection pipeline functional
- ✓ Existing API compatibility maintained
- ✓ No critical failures in 48-hour test
- ✓ Easy rollback to Docker-only setup

**Test Automation**:
- Use existing test framework in `/tests`
- Add IB Connector host service connectivity tests
- Create integration test suite for hybrid architecture
- Implement monitoring for 24-hour stability validation

**Note**: Training performance improvements deferred to Phase 1+

## Operational Strategy

### Service Management
- **macOS**: Use `launchd` for automatic service startup
- **Linux**: Use `systemd` for service management
- **Development**: Simple shell scripts for start/stop/restart
- **Monitoring**: Health check endpoints for all services

### Rollback Strategy
- **Environment Toggles**: `USE_IB_HOST_SERVICE=false` reverts to Docker-only
- **Code Preservation**: Keep existing IB code paths intact
- **Quick Revert**: Ability to disable host service in under 5 minutes
- **Documentation**: Clear rollback procedures

### Security Considerations
- **Localhost Binding**: IB Connector service only accessible from localhost
- **No External Exposure**: Service not accessible from outside machine
- **No Authentication**: Development-focused, localhost security only
- **Logging**: Basic operation logging, no sensitive IB data in logs

## Risk Mitigation

### Technical Risks
- **IB Connector service failures**: Implement automatic restarts and fallbacks to Docker IB
- **Network issues**: Retry logic and circuit breakers for host service communication
- **Data inconsistency**: Validation at every pipeline stage
- **Port conflicts**: Ensure port 5001 is available for IB Connector service

### Operational Risks
- **Configuration drift**: Infrastructure as code
- **Knowledge gaps**: Comprehensive documentation
- **Dependency failures**: Vendor abstraction layers
- **Security vulnerabilities**: Regular updates and scanning

## Success Indicators

By the end of Phase 0, we should achieve:

- **IB Connection Stability**: 24+ hours without disconnection
- **Data Collection Reliability**: Consistent data download without sleep/wake issues
- **System Reliability**: 48-hour test with no critical failures
- **API Compatibility**: Existing frontend continues to work unchanged
- **Easy Rollback**: Quick revert to Docker-only setup if needed

This focused approach solves the immediate critical IB connectivity blocker while establishing patterns for future service extraction. Training performance improvements and broader architectural changes are planned for Phase 1+ when proper planning time is available.

---

## Appendix: Future Security Evolution Path

> **⚠️ IMPORTANT: This section describes FUTURE evolution possibilities, NOT current Phase 0 implementation.**
> 
> **DO NOT IMPLEMENT**: These are architectural considerations for future phases only.

### Security Evolution Capability

The Phase 0 host service architecture is designed to enable future security enhancements without requiring architectural changes. This section outlines how the simple localhost-based services can evolve into production-grade secure systems.

### Current Phase 0 Security Posture

**Intentionally Simple & Insecure (Development Only)**:
```
Docker Backend → Plain HTTP → Host Services (localhost only) → IB Gateway/GPU
                 ^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                 (No auth)    (Localhost binding = natural firewall)
```

**Security Properties**:
- ✅ **Network isolation**: Services only accessible from localhost
- ✅ **No external exposure**: Cannot be reached from outside machine
- ❌ **No authentication**: Any local process can access services
- ❌ **No audit trail**: Basic logging only
- ❌ **No encryption**: Plain HTTP communication

### Future Evolution Phases (NOT FOR IMPLEMENTATION)

#### Phase 1+: Basic Authentication
```
Docker Backend → HTTP + API Key → Host Services → IB Gateway/GPU
                 ^^^^^^^^^^^^^^   (API key validation)
```

**Potential Implementation**:
```python
# FUTURE EXAMPLE - DO NOT IMPLEMENT
@app.middleware("http")
async def auth_middleware(request, call_next):
    api_key = request.headers.get("X-API-Key")
    if not validate_api_key(api_key):
        return HTTPException(401, "Unauthorized")
    return await call_next(request)
```

#### Phase 2+: Reverse Proxy + SSL
```
Docker Backend → HTTPS → Traefik/Nginx → Host Services → IB Gateway/GPU
                 ^^^^^   ^^^^^^^^^^^^^   (SSL termination, rate limiting)
```

**Potential Implementation**:
```yaml
# FUTURE EXAMPLE - DO NOT IMPLEMENT
services:
  ib-proxy:
    image: traefik:v3.0
    labels:
      - "traefik.http.routers.ib-api.rule=Host(`ib-api.yourdomain.com`)"
      - "traefik.http.routers.ib-api.middlewares=auth-middleware"
      - "traefik.http.middlewares.auth-middleware.basicauth.users=admin:$$2y$$10$$..."
```

#### Phase 3+: Advanced Security
```
Docker Backend → HTTPS + JWT → Auth Gateway → Host Services → IB Gateway/GPU
                              ^^^^^^^^^^^^   (OAuth2, RBAC, audit logging)
```

**Potential Features**:
- Role-based access control (RBAC)
- Symbol-level permissions
- Comprehensive audit logging
- Rate limiting per user/service
- Request/response encryption

### Why Phase 0 Architecture Enables This Evolution

#### 1. **Clean HTTP Interface**
Host services already expose well-defined REST APIs with structured request/response models, making middleware addition straightforward.

#### 2. **Localhost Binding = Security Foundation**
Current localhost-only binding provides natural network isolation and is proxy-ready for future reverse proxy deployment.

#### 3. **Service Separation**
Clear boundaries between business logic (Docker backend) and external integrations (host services) enable different security policies for each layer.

#### 4. **Environment-Driven Configuration**
Existing environment variable patterns can be extended to control security features without code changes.

### Migration Path Characteristics

#### ✅ **Non-Breaking Evolution**
Each security enhancement can be added without changing core architecture or APIs.

#### ✅ **Testable Security**
Security features can be tested independently and toggled via environment variables.

#### ✅ **Gradual Rollout**
Security can be enabled incrementally:
```bash
# FUTURE EXAMPLES - DO NOT IMPLEMENT
IB_AUTH_ENABLED=false          # Phase 0: No auth
IB_AUTH_ENABLED=true           # Phase 1+: Enable auth
IB_AUTH_TYPE=api_key          # Phase 1+: API key auth
IB_AUTH_TYPE=jwt              # Phase 3+: JWT auth
```

### Key Architectural Decisions Supporting Future Security

1. **Structured Request/Response Models**: Enable easy audit logging and validation
2. **Middleware-Ready FastAPI**: Simple to add authentication layers
3. **Environment Configuration**: Security features can be toggled without code changes
4. **Service Isolation**: Clear boundaries for applying different security policies
5. **HTTP-Based Communication**: Standard protocol supports all authentication methods

### Summary

The Phase 0 implementation is intentionally simple for development velocity, but the architectural choices ensure that production-grade security can be layered on top without requiring fundamental changes to the system design.

> **REMINDER: This appendix is for future planning only. Phase 0 implementation should focus solely on solving the immediate IB connectivity and GPU acceleration issues.**