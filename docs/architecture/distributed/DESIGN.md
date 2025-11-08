# Distributed Training & Backtesting Design
## Hybrid Containerized Architecture

**Version**: 2.0
**Status**: Design Phase
**Date**: 2025-11-08

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Goals](#design-goals)
3. [Environment Strategy](#environment-strategy)
4. [Core Design Decisions](#core-design-decisions)
5. [System Flows](#system-flows)
6. [Orchestration Patterns](#orchestration-patterns)
7. [Worker Exclusivity](#worker-exclusivity)
8. [State Management](#state-management)
9. [Trade-offs & Rationale](#trade-offs--rationale)
10. [Success Criteria](#success-criteria)

---

## Executive Summary

This design enables **distributed parallel execution** of training and backtesting operations across a cluster while preserving KTRDR's existing async operations infrastructure. The system supports different deployment models for development (Docker Compose on Mac) and production (Proxmox LXC), using a unified abstraction layer that provides consistent behavior across environments.

### Key Design Principles

**Consistency**: Same orchestration pattern for all manually-managed workers (GPU hosts, LXC containers)
**Environment Parity**: Dev and prod use different infrastructure but identical backend code
**Minimal Changes**: Preserves existing async infrastructure (OperationsService, ServiceOrchestrator, ProgressBridge)
**Progressive Enhancement**: Can start simple (dev), scale complex (prod) without code changes

---

## Design Goals

### Functional Goals

✅ **Parallel Execution**: Run multiple training and backtesting operations concurrently
✅ **Horizontal Scaling**: Add workers to increase throughput
✅ **GPU Priority**: Route GPU training to host services, fallback to CPU workers
✅ **Environment Flexibility**: Same codebase works on Mac (dev) and Proxmox (prod)
✅ **Operation Isolation**: Each worker runs exactly 1 operation at a time

### Non-Functional Goals

✅ **Preserve Existing Patterns**: No changes to OperationsService, progress tracking, cancellation
✅ **Simple Development**: Easy local testing without complex infrastructure
✅ **Production Ready**: Leverage existing Proxmox infrastructure for stability
✅ **Operational Simplicity**: Consistent orchestration pattern (manual, health-checked)

---

## Environment Strategy

### Development Environment (Mac)

**Infrastructure**: Docker Compose (no Swarm)
**Workers**: Docker containers that self-register on startup
**Registration**: Workers call `POST /workers/register` on startup
**Scaling**: `docker-compose up --scale backtest-worker=N`

**Rationale**:
- Developer already uses Docker on Mac
- No need for Swarm complexity in development
- Fast iteration with volume mounts (hot reload)
- Simple scaling for testing concurrent operations
- Workers auto-register, no discovery needed

### Production Environment (Proxmox)

**Infrastructure**: Proxmox LXC containers
**Workers**: LXC containers that self-register on startup
**Registration**: Workers call `POST /workers/register` on startup
**Scaling**: Clone LXC template, assign IP, start service

**Rationale**:
- Leverage existing Proxmox infrastructure
- Lower overhead than Docker for long-running CPU workloads
- Consistent with existing GPU host service pattern
- Full OS environment for debugging and monitoring
- Proxmox management tools (backups, snapshots, monitoring)
- Workers auto-register, infrastructure-agnostic

---

## Core Design Decisions

### Decision 1: Hybrid GPU Architecture

**Choice**: GPU host services (bare metal/LXC) + CPU containerized workers

**Training Routing Priority**:
1. **Try GPU First** → Check GPU host availability (10x-100x faster)
2. **GPU Available** → Route to GPU host
3. **GPU Unavailable** → Route to CPU worker (always works)

**Rationale**:
- Preserves existing GPU capability (CUDA/MPS access)
- Adds horizontal scaling via CPU workers
- Flexible: maximizes GPU utilization while ensuring operations always succeed
- Future-proof: can migrate GPU hosts to containers later if needed

**Visual**:
```
Training Request
    └─> Backend selects worker
        ├─> GPU available? → Dispatch to GPU host (10x-100x faster)
        └─> GPU busy/unavailable → Dispatch to CPU worker (always works)
```

---

### Decision 2: Differentiated Orchestration

**Choice**: Different orchestration patterns based on workload type

#### Backtesting: Pure Container Orchestration
- **Dev**: Docker Compose manages replicas, backend dispatches to service name
- **Prod**: LXC workers discovered via Proxmox API, backend does round-robin
- **Rationale**: No GPU needed, pure CPU workload, high volume

#### Training: Hybrid Orchestration with Priority
- **GPU Training**: Manual orchestration via WorkerRegistry (same as current pattern)
- **CPU Training**: Container orchestration (Docker/LXC, same as backtesting)
- **Rationale**: GPU operations must go to host services, CPU can use containers

**Key Insight**: This matches the **existing pattern** - backend already orchestrates GPU host services manually, now extends same pattern to LXC workers.

---

### Decision 3: Push-Based Worker Registration

**Choice**: Workers register themselves with backend on startup

**Registration Flow**:
1. **Worker Starts** → Calls `POST /workers/register`
2. **Backend** → Adds worker to registry
3. **Worker Re-registers** → Updates existing registration (idempotent)

**Rationale**:
- **Infrastructure-agnostic**: Works with Docker, LXC, bare metal, cloud VMs, anything
- **Faster**: Immediate registration on startup (no discovery loop delay)
- **Simpler**: No infrastructure-specific discovery code (no Docker API, Proxmox API)
- **Self-healing**: Workers automatically re-register when they come back online
- **Cloud-native**: Standard pattern used by Kubernetes, Consul, service meshes

---

### Decision 4: Dedicated Container Types

**Choice**: Separate worker services for training and backtesting

**Worker Types**:
- `backtest-worker`: Runs backtesting operations only (port 5003)
- `training-worker`: Runs CPU training operations only (port 5004)
- GPU hosts: Run GPU training operations (port 5002)

**Rationale**:
- Clear separation of concerns
- Different resource profiles (training more memory-intensive)
- Independent scaling (can scale backtesting without affecting training)
- Simpler worker state machine (IDLE/BUSY for single operation type)

---

### Decision 5: Container Exclusivity

**Choice**: Each worker runs exactly 1 operation at a time

**Mechanism**:
- Worker tracks state: `IDLE` → `BUSY` → `IDLE`
- Worker rejects new operations when `BUSY` (HTTP 503)
- Backend retries with different worker on rejection

**Rationale**:
- Prevents resource contention within container
- Predictable performance (no interference between operations)
- Simple state management (no queue, no concurrent operations)
- Easy to reason about capacity (N workers = N concurrent operations)

---

## System Flows

### Worker Startup & Registration

```
Worker Container Starts
  │
  ├─> Worker service starts (uvicorn ...)
  │
  └─> POST /workers/register
      │ {
      │   "worker_id": "backtest-worker-1",
      │   "worker_type": "backtesting",
      │   "endpoint_url": "http://192.168.1.201:5003",
      │   "capabilities": {"cores": 4, "memory_gb": 8}
      │ }
      │
      ▼
  Backend WorkerRegistry
      │
      ├─> Add to registry
      ├─> Status: AVAILABLE
      └─> Start health monitoring
```

### Backtesting Flow (Development)

```
Client
  │
  └─> POST /backtests/start
      │
      ▼
  Backend (Docker Container)
      │
      ├─> Create operation in OperationsService
      ├─> WorkerRegistry.select_worker(type=BACKTESTING)
      │   └─> Query registered workers
      │       └─> Returns: "http://backtest-worker-1:5003"
      │           (Previously registered worker)
      │
      └─> POST http://backtest-worker-1:5003/backtests/start
          │
          ▼
      Backtest Worker Container
          │
          ├─> Check state: IDLE?
          ├─> Yes → Accept (state = BUSY)
          ├─> Run BacktestingEngine
          ├─> Update ProgressBridge
          └─> On complete: state = IDLE

Progress Polling:
  Client → GET /operations/{id}
      → Backend checks cache (1s TTL)
      → If stale: Query worker via proxy
      → Worker returns progress from bridge
      → Return to client
```

### Backtesting Flow (Production)

```
Client
  │
  └─> POST /backtests/start
      │
      ▼
  Backend (Docker/LXC)
      │
      ├─> Create operation in OperationsService
      ├─> WorkerRegistry.select_worker(type=BACKTESTING)
      │   └─> Query registered workers
      │       └─> Filter: status=AVAILABLE
      │       └─> Round-robin select: worker-3
      │       └─> Returns: "http://192.168.1.203:5003"
      │           (Previously registered LXC worker)
      │
      └─> POST http://192.168.1.203:5003/backtests/start
          │
          ▼
      LXC Container (backtest-worker-3)
          │
          ├─> Check state: IDLE?
          ├─> Yes → Accept (state = BUSY)
          ├─> Run BacktestingEngine
          ├─> Update ProgressBridge
          └─> On complete: state = IDLE

      (If worker was BUSY → Backend retries with worker-4)
```

### Training Flow (Hybrid Priority Routing)

```
Client
  │
  └─> POST /trainings/start
      │ {prefer_gpu: true, symbols: ["AAPL"], ...}
      │
      ▼
  Backend
      │
      ├─> Create operation in OperationsService
      ├─> TrainingService.select_worker()
      │   │
      │   ├─> Check: prefer_gpu = true
      │   ├─> Query WorkerRegistry for GPU hosts
      │   │   └─> Available GPU hosts: [gpu-host-1, gpu-host-2]
      │   │
      │   ├─> PRIORITY 1: Select GPU host
      │   │   └─> Round-robin: gpu-host-1
      │   │   └─> POST http://192.168.1.100:5002/training/start
      │   │       ├─> Accepted → GPU training starts
      │   │       └─> Rejected (503) → Try gpu-host-2
      │   │           └─> All GPU busy → FALLBACK
      │   │
      │   └─> PRIORITY 2: Fallback to CPU worker
      │       └─> Query WorkerRegistry for CPU training workers
      │           └─> Discovery mode dependent:
      │               ├─> Dev: http://training-worker:5004
      │               └─> Prod: http://192.168.1.211:5004
      │
      └─> Worker executes training
          └─> Progress tracking via OperationServiceProxy
```

---

## Orchestration Patterns

### Manual Orchestration (Consistent Pattern)

The system uses **manual orchestration** for all worker types, which means:

**Backend Responsibilities**:
- Accept worker registrations (workers push on startup)
- Maintain registry of workers
- Health check workers periodically (every 10 seconds)
- Select worker based on availability and capabilities
- Dispatch operations to specific workers
- Handle worker rejection (busy, unhealthy)
- Retry logic with different workers
- Remove dead workers after threshold (5 minutes)

**Why This Pattern?**
1. **Infrastructure-agnostic**: Works with any infrastructure (Docker, LXC, bare metal, cloud)
2. **Self-healing**: Workers automatically re-register when they come back
3. **Simple**: No infrastructure-specific discovery code needed
4. **Fast**: Immediate registration on startup (no discovery loop delay)
5. **Standard**: Cloud-native pattern used by Kubernetes, Consul, service meshes

**What's "Manual"?**
- Worker creation/destruction (not automatic)
- Load balancing logic (backend implements round-robin)
- Removal threshold configuration (5 minutes by default)

**What's "Automatic"?**
- Worker registration (workers self-register on startup)
- Worker re-registration (on recovery)
- Health checks (background task)
- Dead worker cleanup (after threshold)
- Retry on failure (backend logic)
- Progress tracking (existing OperationsService pattern)

---

### Worker Lifecycle

The system uses a **push-based registration and health monitoring** pattern.

#### 1. Worker Registration (Startup)

**When worker starts**:
1. Worker service starts (uvicorn/FastAPI)
2. Worker waits for service to be ready (health check passes)
3. Worker calls `POST /workers/register` with:
   - Worker ID (unique identifier)
   - Worker type (backtesting, training)
   - Endpoint URL (HTTP address)
   - Capabilities (cores, memory, GPU, etc.)
4. Backend adds worker to registry with status `AVAILABLE`

**Re-registration**: If worker ID already exists, backend updates registration (idempotent)

#### 2. Health Monitoring (Continuous)

**Backend health check loop** (every 10 seconds):
- Queries each worker's `/health` endpoint
- Timeout: 5 seconds
- Successful response (200) → Worker healthy, update status from response
- Failed response → Increment failure counter

**Health failure threshold**: 3 consecutive failures
- Worker marked as `TEMPORARILY_UNAVAILABLE`
- Worker excluded from selection (no operations routed)
- Health checks continue

#### 3. Worker Removal (Cleanup)

**Removal threshold**: 5 minutes of unavailability
- If worker remains `TEMPORARILY_UNAVAILABLE` for > 5 minutes
- Worker removed from registry entirely
- Rationale: In Proxmox infrastructure, unreachable worker likely means host is down

**Cleanup task** (runs every 60 seconds):
- Checks all `TEMPORARILY_UNAVAILABLE` workers
- Calculates unavailable duration
- Removes workers exceeding threshold

#### 4. Worker Recovery (Re-registration)

**When worker comes back online**:
- Worker restarts and calls `POST /workers/register`
- Backend either:
  - Updates existing worker (if still in registry, marked unavailable)
  - Adds as new worker (if was removed)
- Worker immediately available for operations

---

### Load Balancing

**Strategy**: Round-robin with health-based filtering

**Algorithm**:
1. Filter workers: `status == AVAILABLE && health == HEALTHY`
2. Sort by last selection time (least recently used first)
3. Select first worker
4. POST operation to worker
5. If worker rejects (503 BUSY) → Remove from list, retry with next
6. If all workers reject → Return error to client (no capacity)

**Health Checks**:
- Background task queries each worker's `/health` endpoint every 10 seconds
- Worker healthy if: responds 200 within 5 seconds
- Worker unhealthy after: 3 consecutive failures
- Unhealthy workers excluded from selection

---

## Worker Exclusivity

### State Machine

Each worker maintains simple state:

```
┌─────────┐
│  IDLE   │ ◄─────────────────┐
└────┬────┘                   │
     │                        │
     │ Accept Operation       │ Complete/Fail
     ▼                        │
┌─────────┐                   │
│  BUSY   │───────────────────┘
└─────────┘
```

**IDLE State**:
- Worker ready to accept operations
- `/health` returns: `{"status": "healthy", "worker_status": "idle"}`
- POST operation → Accept (transition to BUSY)

**BUSY State**:
- Worker running operation
- `/health` returns: `{"status": "healthy", "worker_status": "busy", "current_operation": "op_123"}`
- POST operation → Reject with HTTP 503

### Rejection Handling

**Worker Rejection**:
- Returns HTTP 503 with message: "Worker busy with operation {id}"
- Backend receives 503
- Backend retries with different worker
- Max retries: 3 (try up to 3 different workers)
- If all workers busy: Return error to client

**Benefit**: Simple, explicit, no worker-side queuing

---

## State Management

### Operation State (Backend)

**Source of Truth**: Backend OperationsService

**Storage**:
- Operation metadata (id, type, status, created_at, etc.)
- Progress cache (1s TTL)
- Worker assignment (operation_id → worker_id)

**Lifecycle**:
1. Created → Backend creates operation record
2. Running → Backend dispatches to worker, registers proxy
3. Progress → Backend polls worker on demand (cache miss)
4. Completed → Backend marks complete, unregisters proxy

**Worker Failure**:
- Health check detects worker down
- Backend marks operation as failed
- Client sees operation status=failed
- Client can retry operation (new worker selected)

### Worker State (Workers)

**Storage**: In-memory (ephemeral)

**State**:
- Current operation ID
- Worker status (IDLE/BUSY)
- Progress bridge (for progress queries)

**Worker Restart**:
- Worker loses in-memory state
- Backend detects via health check failure
- Backend marks operation as failed
- Worker restarts as IDLE, ready for new operations

**Key Principle**: Workers are stateless, backend is stateful

---

## Trade-offs & Rationale

### Trade-off 1: Manual vs Automatic Orchestration

**Decision**: Manual orchestration (WorkerRegistry) instead of Swarm/K8s

**Trade-offs**:
- ❌ More backend code (WorkerRegistry, health checks, load balancing)
- ❌ Manual scaling (clone LXC vs `docker service scale`)
- ✅ Simpler infrastructure (no Swarm cluster setup)
- ✅ Consistent with existing GPU host pattern
- ✅ Works with Proxmox LXC (leverage existing infrastructure)
- ✅ More control over routing logic

**Rationale**:
Scaling is infrequent (weekly/monthly), not continuous. Manual orchestration is acceptable and provides consistency with existing GPU host management. Avoids complexity of Swarm cluster while still enabling distributed execution.

---

### Trade-off 2: LXC vs Docker in Production

**Decision**: Use Proxmox LXC for production workers

**Trade-offs**:
- ❌ Tied to Proxmox (less portable)
- ❌ Manual worker creation (vs auto-scaling)
- ✅ Lower overhead (LXC lighter than Docker)
- ✅ Leverage existing Proxmox infrastructure
- ✅ Better performance for CPU-intensive workloads
- ✅ Full OS environment (easier debugging)
- ✅ Proxmox management tools (backups, monitoring, snapshots)

**Rationale**:
Already have Proxmox infrastructure. LXC provides better performance and integrates with existing management tools. Portability not a concern (not migrating to cloud).

---

### Trade-off 3: Container Exclusivity

**Decision**: 1 operation per worker vs. multiple concurrent operations

**Trade-offs**:
- ❌ Potential under-utilization if workload imbalanced
- ❌ More workers needed for same throughput
- ✅ Simple state management (no queuing, no concurrency)
- ✅ Predictable performance (no interference)
- ✅ Easy capacity planning (N workers = N operations)
- ✅ No resource contention within container

**Rationale**:
Training and backtesting are CPU/memory intensive. Running multiple operations per worker would cause resource contention and unpredictable performance. Better to scale workers than operations per worker.

---

### Trade-off 4: Push-Based Registration

**Decision**: Workers self-register (push) vs. backend discovers workers (pull)

**Trade-offs**:
- ❌ Workers need registration logic on startup
- ❌ Workers must know backend URL (configuration)
- ✅ Infrastructure-agnostic (works anywhere)
- ✅ Faster registration (immediate, no loop delay)
- ✅ Simpler backend (no discovery code needed)
- ✅ Self-healing (workers auto re-register)
- ✅ Same pattern in dev and prod

**Rationale**:
Push-based registration is cloud-native standard (Kubernetes, Consul). Eliminates infrastructure-specific discovery code. Workers knowing backend URL is acceptable trade-off for simplicity and portability.

---

## Success Criteria

### Functional Requirements

✅ **Concurrent Execution**: Run 10+ training and 20+ backtesting operations simultaneously
✅ **GPU Priority**: GPU training operations routed to GPU hosts when available
✅ **Fallback**: CPU training operations route to CPU workers when GPU unavailable
✅ **Environment Parity**: Same operations work in dev and prod
✅ **Worker Isolation**: Each worker runs exactly 1 operation at a time

### Non-Functional Requirements

✅ **Minimal Code Changes**: Existing async infrastructure unchanged (OperationsService, ProgressBridge)
✅ **Development Simplicity**: `docker-compose up` starts functional dev environment
✅ **Production Stability**: LXC workers leverage Proxmox reliability
✅ **Operational Simplicity**: Same orchestration pattern as existing GPU hosts
✅ **Observable**: Worker status visible via API, health checks provide visibility

---

## Next Steps

1. **Review & Approve** this design document
2. **Review ARCHITECTURE.md** for technical implementation specifications
3. **Create Implementation Plan** based on architecture decisions
4. **Begin Implementation** following approved plan

**Related Documents**:
- **ARCHITECTURE.md** - Technical implementation specifications
- **IMPLEMENTATION_PLAN.md** - Phased deployment plan (draft, to be finalized after architecture review)
- **PUSH_REGISTRATION_SUMMARY.md** - Summary of push-based registration approach

---

**Document End**
