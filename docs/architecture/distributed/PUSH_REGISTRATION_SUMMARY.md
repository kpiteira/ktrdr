# Push-Based Worker Registration Update Summary

**Version**: 2.1
**Date**: 2025-11-08

## Changes Made

### Design Document (DESIGN.md)

**Updated Sections:**
1. **Environment Strategy** - Workers self-register, no discovery needed
2. **Decision 3** - Changed from "discovery modes" to "push-based registration"
3. **System Flows** - Added worker startup & registration flow
4. **Orchestration Patterns** - Replaced "Discovery Mechanisms" with "Worker Lifecycle"
5. **Worker Lifecycle** - New section explaining registration, health monitoring, removal (5min threshold)
6. **Deployment Strategy** - Updated phases to reflect registration instead of discovery
7. **Trade-offs** - Added push-based registration trade-off

### Architecture Document (ARCHITECTURE.md)

**Updated Sections:**
1. **WorkerEndpoint** - Added `last_healthy_at` field for cleanup tracking
2. **WorkerStatus** - Added `TEMPORARILY_UNAVAILABLE` status
3. **Dependencies** - Removed Docker/Proxmox API dependencies (no longer needed)

**Sections Still To Update** (deferred for now):
- WorkerRegistry class implementation (will be rewritten during implementation)
- Configuration examples (will use actual config when implementing)
- Worker startup scripts (will write actual scripts during implementation)

## Key Configuration

### Worker Lifecycle Thresholds

```yaml
worker_lifecycle:
  # Health checking
  health_check_interval: 10      # Check every 10 seconds
  health_check_timeout: 5        # 5 second timeout per check
  health_failure_threshold: 3    # 3 consecutive failures → TEMPORARILY_UNAVAILABLE

  # Removal policy
  removal_threshold: 300         # 5 minutes (300 seconds) of unavailability → REMOVED
```

**Rationale for 5-minute threshold**:
- In Proxmox infrastructure, unreachable worker likely means entire host is down
- No point polling for extended period
- Workers auto-re-register when they come back

## Worker Registration Flow

### Startup Sequence

```
1. Worker container/LXC starts
2. Worker service starts (uvicorn ktrdr.*.remote_api:app)
3. Worker waits for service ready (internal health check)
4. Worker calls: POST http://backend:8000/api/v1/workers/register
   Body: {
     "worker_id": "backtest-worker-1",
     "worker_type": "backtesting",
     "endpoint_url": "http://192.168.1.201:5003",
     "capabilities": {"cores": 4, "memory_gb": 8}
   }
5. Backend registers worker with status AVAILABLE
6. Backend starts health monitoring (every 10s)
```

### Health Monitoring

```
Every 10 seconds:
  - GET worker.endpoint_url/health
  - Success → Reset failure counter, update last_healthy_at
  - Failure → Increment failure counter
  - If failures >= 3 → Status = TEMPORARILY_UNAVAILABLE

Every 60 seconds (cleanup task):
  - Check TEMPORARILY_UNAVAILABLE workers
  - If (now - last_healthy_at) > 5 minutes → REMOVE worker
```

### Recovery

```
Worker comes back online:
  - Worker restarts
  - Worker calls POST /workers/register (same as startup)
  - Backend either:
    * Updates existing worker (if still in registry)
    * Adds as new worker (if was removed)
  - Worker immediately AVAILABLE
```

## API Endpoints

### Backend API

```python
POST /api/v1/workers/register
  Request: WorkerRegistrationRequest
  Response: {"registered": True, "worker_id": "..."}

DELETE /api/v1/workers/deregister/{worker_id}
  Response: {"deregistered": True}

GET /api/v1/workers
  Response: List of all workers with status
```

### Worker API (unchanged)

```python
GET /health
  Response: {
    "status": "healthy",
    "worker_status": "idle" | "busy",
    "current_operation": "op_id" | null
  }
```

## Benefits

✅ **Infrastructure-agnostic** - Works with Docker, LXC, bare metal, cloud
✅ **Simpler** - No Docker API, no Proxmox API, no discovery code
✅ **Faster** - Immediate registration on startup (no discovery loop delay)
✅ **Self-healing** - Workers auto-reregister when they recover
✅ **Cloud-native** - Standard pattern (Kubernetes, Consul, Eureka)
✅ **Same everywhere** - Identical pattern in dev and prod

## Implementation Status

- [x] DESIGN.md updated with push-based registration
- [x] ARCHITECTURE.md partially updated (data models)
- [ ] Full WorkerRegistry implementation (deferred to implementation phase)
- [ ] Worker startup scripts (deferred to implementation phase)
- [ ] Configuration files (deferred to implementation phase)

**Recommendation**: Review and approve design, implement WorkerRegistry during Phase 1/2 of deployment.
