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
9. [Deployment Strategy](#deployment-strategy)
10. [Trade-offs & Rationale](#trade-offs--rationale)

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
**Workers**: Docker containers on same network
**Discovery**: Docker API or simple DNS-based service names
**Scaling**: `docker-compose up --scale backtest-worker=N`

**Rationale**:
- Developer already uses Docker on Mac
- No need for Swarm complexity in development
- Fast iteration with volume mounts (hot reload)
- Simple scaling for testing concurrent operations

### Production Environment (Proxmox)

**Infrastructure**: Proxmox LXC containers
**Workers**: LXC containers with static IPs
**Discovery**: Proxmox API (automatic) or manual configuration
**Scaling**: Clone LXC template, assign IP, start service

**Rationale**:
- Leverage existing Proxmox infrastructure
- Lower overhead than Docker for long-running CPU workloads
- Consistent with existing GPU host service pattern (manual orchestration)
- Full OS environment for debugging and monitoring
- Proxmox management tools (backups, snapshots, monitoring)

---

## Core Design Decisions

### Decision 1: Hybrid GPU Architecture

**Choice**: GPU host services (bare metal/LXC) + CPU containerized workers

**Training Routing Priority**:
1. **GPU Required/Preferred** → Check GPU host availability
2. **GPU Available** → Route to GPU host (highest priority)
3. **GPU Unavailable or Not Needed** → Route to CPU worker (fallback)

**Rationale**:
- Preserves existing GPU capability (CUDA/MPS access)
- Adds horizontal scaling via CPU workers
- Flexible: can run training on either GPU or CPU based on availability
- Future-proof: can migrate GPU hosts to containers later if needed

**Visual**:
```
Training Request
    └─> Backend checks requirements
        ├─> GPU needed? → Try GPU hosts (Priority: HIGH)
        │   ├─> GPU available → Dispatch to GPU host
        │   └─> GPU busy → Fallback to CPU worker (or queue/fail)
        └─> CPU acceptable → Dispatch to CPU worker
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

### Decision 3: Unified Abstraction (WorkerRegistry)

**Choice**: Environment-aware WorkerRegistry that abstracts discovery

**Modes**:
- **Docker Mode** (Dev): Discovers workers via Docker API or DNS
- **Proxmox Mode** (Prod): Discovers workers via Proxmox API
- **Manual Mode** (GPU hosts): Static configuration

**Rationale**:
- Same backend code works in both environments
- Discovery mechanism configurable via environment variable
- Backend logic (routing, health checks, load balancing) identical
- Easy to add new discovery modes (Kubernetes, cloud APIs, etc.)

**Configuration-Driven**:
```
Dev:   WORKER_DISCOVERY_MODE=docker
Prod:  WORKER_DISCOVERY_MODE=proxmox
```

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
      │   └─> Discovery mode: docker
      │       └─> Returns: "http://backtest-worker:5003"
      │           (Docker Compose service name)
      │
      └─> POST http://backtest-worker:5003/backtests/start
          │
          ▼
      Docker Network
          │ (Docker resolves service name to container IP)
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
      │   └─> Discovery mode: proxmox
      │       └─> Query Proxmox API for LXC containers
      │           with tag "ktrdr-backtest-worker"
      │       └─> Filter: status=AVAILABLE
      │       └─> Round-robin select: worker-3
      │       └─> Returns: "http://192.168.1.203:5003"
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
- Maintain registry of workers (GPU hosts, LXC containers, Docker containers)
- Health check workers periodically (every 10 seconds)
- Select worker based on availability and capabilities
- Dispatch operations to specific workers
- Handle worker rejection (busy, unhealthy)
- Retry logic with different workers

**Why Manual?**
1. **Consistency**: GPU hosts already require manual orchestration (no auto-discovery)
2. **Simplicity**: Same pattern for all worker types (GPU, LXC, Docker)
3. **Control**: Explicit worker selection and load balancing logic
4. **Flexibility**: Easy to implement custom routing (priority, capabilities, affinity)

**What's "Manual"?**
- Worker creation/destruction (not automatic)
- Worker registration (via discovery or configuration)
- Load balancing logic (backend implements round-robin)
- Health monitoring (backend implements polling)

**What's "Automatic"?**
- Worker discovery (via Docker API or Proxmox API)
- Health checks (background task)
- Retry on failure (backend logic)
- Progress tracking (existing OperationsService pattern)

---

### Discovery Mechanisms

#### Development (Docker)

**Option A: Service Name Discovery** (Simplest)
- Workers registered as Docker Compose services
- Backend uses service names: `http://backtest-worker:5003`
- Docker's internal DNS resolves to container IP
- Works with scaled services (Docker load balances)

**Option B: Docker API Discovery** (More Control)
- Backend queries Docker API for running containers
- Filters by labels: `ktrdr.worker.type=backtesting`
- Tracks individual container IPs
- Backend implements load balancing

**Recommended**: Option A for simplicity (leverages Docker's built-in DNS)

#### Production (Proxmox)

**Option A: Proxmox API Discovery** (Automatic)
- Backend queries Proxmox API on interval (every 30 seconds)
- Finds LXC containers with tags: `ktrdr-backtest-worker`, `ktrdr-training-worker`
- Reads IP addresses from container configs
- Automatically updates worker registry

**Option B: Manual Configuration** (Simple)
- Static configuration file with worker IPs
- Backend loads on startup
- Manual update when adding/removing workers

**Recommended**: Option A for dynamic discovery, Option B as fallback

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

## Deployment Strategy

### Phase 1: Development Setup (Week 1)

**Goal**: Enable local development with worker scaling

**Tasks**:
1. Create `docker-compose.dev.yml` with backend + workers
2. Implement Docker-based worker discovery
3. Test local scaling: `docker-compose up --scale backtest-worker=3`
4. Validate concurrent operations (3 backtests simultaneously)

**Deliverables**:
- [ ] Docker Compose configuration
- [ ] Workers discoverable via Docker network
- [ ] Backend routes operations to workers
- [ ] Progress tracking works end-to-end

**Success Criteria**: Can run 3 concurrent backtests on Mac

---

### Phase 2: Worker Registry Foundation (Week 2)

**Goal**: Abstract worker discovery for multi-environment support

**Tasks**:
1. Implement `WorkerRegistry` class with discovery modes
2. Implement Docker discovery mode
3. Implement manual configuration mode (for GPU hosts)
4. Add health checking background task
5. Add round-robin load balancing

**Deliverables**:
- [ ] WorkerRegistry with pluggable discovery
- [ ] Docker discovery working in dev
- [ ] Manual config for GPU hosts (existing pattern)
- [ ] Health checks running every 10s

**Success Criteria**: Backend discovers workers automatically, health status visible

---

### Phase 3: Production LXC Setup (Week 3)

**Goal**: Deploy to Proxmox with LXC workers

**Tasks**:
1. Create LXC template with KTRDR environment
2. Clone template to create workers (3 training, 5 backtesting)
3. Configure static IPs and tags
4. Implement Proxmox API discovery mode
5. Deploy backend to Proxmox

**Deliverables**:
- [ ] LXC template ready
- [ ] 8 LXC workers running (3 training, 5 backtesting)
- [ ] Proxmox discovery working
- [ ] Backend discovers LXC workers automatically

**Success Criteria**: Production backend routes to LXC workers, concurrent operations work

---

### Phase 4: Integration & Testing (Week 4)

**Goal**: Validate entire system end-to-end

**Tasks**:
1. End-to-end testing (dev and prod)
2. Load testing (10 concurrent training + 20 concurrent backtesting)
3. Failure testing (worker crashes, network issues)
4. Performance tuning (cache TTL, health check intervals)
5. Documentation updates

**Deliverables**:
- [ ] All tests passing
- [ ] Load test results documented
- [ ] Failure recovery validated
- [ ] Performance baseline established

**Success Criteria**: System handles expected load, recovers from failures gracefully

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

### Trade-off 4: Environment Parity

**Decision**: Different infrastructure for dev (Docker) and prod (LXC)

**Trade-offs**:
- ❌ Different deployment mechanisms (docker-compose vs LXC cloning)
- ❌ Different discovery modes (Docker API vs Proxmox API)
- ✅ Same backend code (abstracted via WorkerRegistry)
- ✅ Optimal for each environment (Docker on Mac, LXC on Proxmox)
- ✅ Same user experience (operations work identically)

**Rationale**:
Perfect infrastructure parity is impossible (Mac vs Linux, Docker vs Proxmox). Instead, use abstraction to provide functional parity. Backend code is identical, only discovery mechanism differs.

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

1. **Review & Approve** this design
2. **Read Architecture Document** for technical implementation details
3. **Begin Phase 1**: Development environment setup
4. **Iterative Implementation**: Follow 4-week deployment strategy
5. **Validate**: Test after each phase before proceeding

---

**Document End**
