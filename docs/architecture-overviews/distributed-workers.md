# Distributed Workers Architecture Overview

**Version**: 1.0
**Date**: 2025-11-10
**Audience**: Technical stakeholders, architects, senior developers
**Status**: Production-Ready Architecture

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Key Components](#key-components)
3. [Worker Types & Capabilities](#worker-types--capabilities)
4. [Communication Patterns](#communication-patterns)
5. [Deployment Models](#deployment-models)
6. [Design Decisions & Trade-offs](#design-decisions--trade-offs)

---

## Executive Summary

### What is the Distributed Workers Architecture?

The KTRDR distributed workers architecture enables **horizontal scaling** of training and backtesting operations across a cluster of compute nodes. It transforms KTRDR from a single-process application into a distributed system where:

- **Backend** orchestrates operations (receives requests, selects workers, tracks progress)
- **Workers** execute operations (training models, running backtests)
- **Operations** scale horizontally (add more workers = more concurrent operations)

### Why Did We Build It This Way?

**GPU Access Constraints**:
- Docker containers cannot efficiently access GPU (CUDA/MPS) on host systems
- Training with GPU is 10x-100x faster than CPU
- Solution: GPU training runs on native host services, CPU operations run in containers

**Horizontal Scaling Requirements**:
- Need to run 10+ training and 20+ backtesting operations concurrently
- Each operation is resource-intensive (CPU, memory)
- Solution: Distribute operations across multiple workers with guaranteed resources

**Development/Production Parity**:
- Development uses Docker Compose on Mac
- Production uses Proxmox LXC containers on Linux
- Solution: Infrastructure-agnostic architecture (same backend code everywhere)

### Architecture Principles

1. **Separation of Concerns**: Backend orchestrates, workers execute
2. **Push-Based Discovery**: Workers self-register (cloud-native pattern)
3. **Stateless Workers**: Workers hold no persistent state; all state in backend
4. **Environment Abstraction**: Same backend code works in dev and prod
5. **Graceful Degradation**: System continues with partial worker availability

---

## Key Components

### 1. WorkerAPIBase (~670 Lines of Reusable Infrastructure)

**What Is It?**

WorkerAPIBase is a reusable base class extracted from the proven training-host-service implementation. It provides all the common infrastructure that every worker needs, eliminating ~570 lines of code duplication per worker.

**Where It Came From**:

The training-host-service (port 5002) already implemented the complete worker pattern successfully. Instead of duplicating this 670-line implementation for each new worker type, we extracted it into a reusable base class.

**What It Provides** (extracted from training-host-service):

```
┌──────────────────────────────────────────────────────────────┐
│                     WorkerAPIBase                            │
│         (Extracted from training-host-service)               │
│                                                              │
│  ✅ OperationsService singleton (41 lines)                  │
│     └─ Worker-local operation tracking                      │
│                                                              │
│  ✅ Operations proxy endpoints (374 lines!)                 │
│     ├─ GET /api/v1/operations/{operation_id}               │
│     ├─ GET /api/v1/operations/{operation_id}/metrics       │
│     ├─ GET /api/v1/operations                              │
│     └─ DELETE /api/v1/operations/{operation_id}/cancel     │
│                                                              │
│  ✅ Health endpoint (/health)                               │
│     └─ Reports busy/idle status to backend                  │
│                                                              │
│  ✅ FastAPI app setup with CORS                             │
│     └─ Production-ready FastAPI configuration               │
│                                                              │
│  ✅ Self-registration with backend                          │
│     └─ Automatic registration on startup                    │
│                                                              │
│  Total: ~670 lines of proven, working code                  │
└──────────────────────────────────────────────────────────────┘
```

**Code Reuse Benefits**:

| Component | Before (Duplication) | After (Extraction) | Savings |
|-----------|---------------------|-------------------|---------|
| Operations endpoints | 374 lines × N workers | 374 lines (once) | 374 × (N-1) |
| OperationsService | 41 lines × N workers | 41 lines (once) | 41 × (N-1) |
| Health/FastAPI setup | ~255 lines × N workers | ~255 lines (once) | 255 × (N-1) |
| **Total per worker** | **~670 lines** | **~100 lines** | **~570 lines** |
| **For 2 workers** | **~1340 lines** | **~770 lines** | **570 lines!** |

**Worker Implementation Example**:

```python
# Before: 670 lines of boilerplate per worker
# After: ~100 lines of domain-specific logic

class BacktestWorker(WorkerAPIBase):
    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url=os.getenv("KTRDR_API_URL")
        )

        # Register domain-specific endpoint
        @self.app.post("/backtests/start")
        async def start_backtest(request: BacktestStartRequest):
            operation_id = request.task_id or generate_id()
            result = await self._execute_work(operation_id, request)
            return {"operation_id": operation_id, **result}
```

**Key Pattern: Operation ID Synchronization**

Workers accept an optional `task_id` from the backend and return the same `operation_id`. This ensures backend and worker track the same operation:

```python
# Backend creates operation with ID "ABC"
backend_operation_id = "ABC"

# Backend dispatches to worker with task_id="ABC"
response = await worker.post("/backtests/start", json={"task_id": "ABC", ...})

# Worker uses same ID: operation_id = "ABC"
worker_operation_id = response["operation_id"]  # Returns "ABC"

# Now backend can query worker: GET /api/v1/operations/ABC
```

### 2. WorkerRegistry (Service Discovery & Lifecycle Management)

**What Is It?**

WorkerRegistry is the central component that maintains the real-time registry of all workers, their health status, capabilities, and availability.

**Core Responsibilities**:

1. **Accept Worker Registrations** (push-based):
   ```python
   POST /workers/register
   {
       "worker_id": "backtest-worker-1",
       "worker_type": "backtesting",
       "endpoint_url": "http://192.168.1.201:5003",
       "capabilities": {"cores": 4, "memory_gb": 8}
   }
   ```

2. **Monitor Worker Health** (continuous):
   - Background task polls each worker's `/health` endpoint every 10 seconds
   - 3 consecutive failures → Worker marked `TEMPORARILY_UNAVAILABLE`
   - 5 minutes unavailable → Worker removed from registry
   - Workers automatically re-register on recovery (idempotent)

3. **Select Optimal Worker** (round-robin):
   - Filter by worker type (training vs backtesting)
   - Filter by capabilities (e.g., GPU required)
   - Filter by status (AVAILABLE only)
   - Select least-recently-used (fairness)

4. **Track Worker State**:
   - AVAILABLE: Worker ready to accept operations
   - BUSY: Worker currently executing an operation
   - TEMPORARILY_UNAVAILABLE: Health checks failing

**Worker Lifecycle**:

```
Worker Starts
    │
    └─> POST /workers/register
        │
        ▼
    Added to Registry (AVAILABLE)
        │
        ├─> Health checks every 10s
        │   └─> Success: Remains AVAILABLE
        │   └─> 3 failures: TEMPORARILY_UNAVAILABLE
        │       └─> 5 minutes: REMOVED
        │
        ├─> Accept operation: BUSY
        │   └─> Complete operation: AVAILABLE
        │
        └─> Worker crashes/restarts
            └─> Re-registers (idempotent)
```

### 3. Backend as Orchestrator (Never Executes Operations)

**What Changed?**

In the distributed architecture, the backend **never executes operations locally**. It's purely an orchestrator:

- ❌ **Before**: Backend could run backtests and training locally
- ✅ **Now**: Backend only dispatches to workers

**Backend Responsibilities**:

1. **Receive User Requests**:
   - `POST /backtests/start` → User wants to start a backtest
   - `POST /training/start` → User wants to train a model

2. **Select Worker**:
   ```python
   # Service-specific selection strategy
   worker = worker_registry.select_worker(
       worker_type=WorkerType.BACKTESTING,
       capabilities={}  # No special requirements
   )
   ```

3. **Dispatch Operation**:
   ```python
   # Send operation to selected worker
   response = await http_client.post(
       f"{worker.endpoint_url}/backtests/start",
       json={"task_id": operation_id, ...}
   )
   ```

4. **Track Progress**:
   - Register operation in OperationsService
   - Register proxy to worker's operation endpoint
   - Cache worker progress (1s TTL)
   - Serve cached progress to users (minimize worker queries)

5. **Return Operation ID**:
   - User polls: `GET /operations/{id}`
   - Backend serves from cache (fast)
   - Backend queries worker only on cache miss (1s+ old)

**Benefit**: Clean separation of concerns, enables horizontal scaling, simplifies backend code.

### 4. Self-Registration Pattern (Push-Based Discovery)

**What Is It?**

Workers proactively register themselves with the backend on startup, rather than backend discovering workers through infrastructure APIs.

**Why Push-Based?**

| Aspect | Push-Based (Chosen) | Pull-Based (Alternative) |
|--------|---------------------|--------------------------|
| **Complexity** | Simple (no infrastructure APIs) | Complex (Docker/Proxmox/K8s APIs) |
| **Portability** | Works everywhere | Environment-specific code |
| **Speed** | Immediate (on startup) | Delayed (discovery loop) |
| **Recovery** | Automatic (re-register) | Manual or complex logic |
| **Cloud-Native** | Yes (K8s, Consul pattern) | Infrastructure-dependent |

**How It Works**:

```
Worker Startup:
1. Worker service starts (uvicorn app)
2. Worker waits for health check to pass
3. Worker calls POST /workers/register
4. Backend adds worker to registry
5. Worker is immediately available

Worker Recovery:
1. Worker crashes/restarts
2. Worker calls POST /workers/register
3. Backend updates existing record (idempotent)
4. Worker is immediately available
```

**Configuration**:

Workers only need to know the backend URL:

```bash
# Environment variable (Docker, LXC, bare metal, cloud - same everywhere)
KTRDR_API_URL=http://backend:8000  # Docker
KTRDR_API_URL=http://192.168.1.100:8000  # Proxmox/LXC
KTRDR_API_URL=http://ktrdr-backend.example.com  # Cloud
```

---

## Worker Types & Capabilities

### 1. BacktestWorker (CPU-Only, Containerized)

**Purpose**: Execute backtesting operations on historical data

**Characteristics**:
- CPU-only (no GPU benefit for backtesting)
- Runs in Docker containers (dev) or LXC containers (prod)
- Horizontally scalable (add unlimited workers)
- Port: 5003

**Capabilities**:
```json
{
    "worker_type": "backtesting",
    "cores": 4,
    "memory_gb": 8,
    "gpu": false
}
```

**Endpoint**:
```python
POST /backtests/start
{
    "task_id": "optional-backend-operation-id",
    "model_path": "/app/models/...",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2023-01-01",
    "end_date": "2024-12-31"
}
```

### 2. TrainingWorker (CPU, Containerized)

**Purpose**: Execute training operations on CPU (fallback from GPU)

**Characteristics**:
- CPU-only (slower than GPU, but always available)
- Runs in Docker containers (dev) or LXC containers (prod)
- Horizontally scalable (add unlimited workers)
- Port: 5004

**Capabilities**:
```json
{
    "worker_type": "training",
    "cores": 8,
    "memory_gb": 16,
    "gpu": false
}
```

**Use Case**: When GPU workers are busy or unavailable, CPU workers ensure operations always succeed (with acceptable performance trade-off).

### 3. Training Host Service (GPU, Bare Metal/LXC)

**Purpose**: Execute training operations with GPU acceleration (10x-100x faster)

**Characteristics**:
- GPU access (CUDA or MPS)
- Runs as native process (Docker can't access GPU efficiently)
- Limited scalability (expensive hardware)
- Port: 5002

**Capabilities**:
```json
{
    "worker_type": "training",
    "cores": 16,
    "memory_gb": 64,
    "gpu": true,
    "gpu_type": "CUDA",  // or "MPS" for Mac
    "gpu_count": 2,
    "gpu_memory_gb": 24
}
```

**Priority**: GPU workers are always tried first (when available) before falling back to CPU workers.

### 4. Capability-Based Routing (GPU-First, CPU-Fallback)

**Training Service Worker Selection**:

```python
def select_training_worker(context):
    # Priority 1: Try GPU workers (10x-100x faster)
    gpu_workers = registry.get_available_workers(
        worker_type=WorkerType.TRAINING,
        capabilities={"gpu": True}
    )
    if gpu_workers:
        return gpu_workers[0]  # Round-robin from GPU pool

    # Priority 2: Fallback to CPU workers (always works)
    cpu_workers = registry.get_available_workers(
        worker_type=WorkerType.TRAINING,
        capabilities={"gpu": False}
    )
    if cpu_workers:
        return cpu_workers[0]  # Round-robin from CPU pool

    # No workers available
    raise RuntimeError("No training workers available")
```

**Benefit**: Maximizes GPU utilization (high-value resource) while ensuring operations always succeed (CPU fallback).

---

## Communication Patterns

### 1. Worker Registration (Worker → Backend)

**Pattern**: Push-based registration on startup

```
Worker                     Backend (WorkerRegistry)
  │                              │
  │─ POST /workers/register ────>│
  │  {worker_id, type, url}      │
  │                              ├─ Add to registry
  │                              ├─ Status: AVAILABLE
  │<─── 200 OK ──────────────────│
```

**Frequency**: Once on startup, idempotent re-registration on restarts

### 2. Operation Dispatch (Backend → Worker)

**Pattern**: Synchronous HTTP request with operation ID synchronization

```
Backend                           Worker
  │                                │
  ├─ POST /backtests/start ───────>│
  │  {task_id: "ABC", ...}         │
  │                                ├─ Check: IDLE?
  │                                ├─ Accept: state = BUSY
  │                                ├─ Create operation: "ABC"
  │<─── {operation_id: "ABC"} ────┤
  │                                │
  ├─ Register proxy: ABC → worker │
  └─ Mark worker: BUSY             │
```

**Operation ID Synchronization**: Backend passes its operation ID as `task_id`, worker returns same ID. This enables backend to query worker using consistent ID.

### 3. Progress Tracking (Backend ← Worker, via User Poll)

**Pattern**: Cache-based pull (preserves existing OperationsService pattern)

```
User             Backend (OperationsService)      Worker
  │                     │                            │
  ├─ GET /operations/ABC──>│                            │
  │                     ├─ Check cache (1s TTL)        │
  │                     │  Cache fresh? ──> Return     │
  │                     │  (age < 1s)                  │
  │                     │                              │
  │                     ├─ Cache stale? ──────────────>│
  │                     │  (age >= 1s)  GET /ops/ABC  │
  │                     │<────────────────────────────│
  │                     ├─ Update cache                │
  │<────────────────────┤                            │
```

**Key Properties**:
- No active polling: Backend only queries worker when user requests status
- 1s cache TTL: Prevents excessive worker queries (existing OPERATIONS_CACHE_TTL)
- User-initiated: Workers don't push updates, backend pulls on demand
- Preserves pattern: No changes to existing OperationsService caching logic

### 4. Health Checks (Backend → Worker, Continuous)

**Pattern**: Periodic polling with threshold-based failure detection

```
Backend Health Monitor         Worker
  │                              │
  ├─ GET /health (every 10s) ───>│
  │                              │
  │<─── 200 OK ───────────────────┤
  │  {status: "idle"}            │
  │                              │
  ├─ Update status: AVAILABLE    │
  └─ Reset failure counter       │
```

**Failure Handling**:

```
Time    Health Check      Worker State    Registry Status
──────────────────────────────────────────────────────────
T+0s    200 OK            Running         AVAILABLE
T+10s   Timeout (1/3)     Crashed         AVAILABLE
T+20s   Timeout (2/3)     Crashed         AVAILABLE
T+30s   Timeout (3/3)     Crashed         TEMPORARILY_UNAVAILABLE
T+5m    Cleanup runs      Crashed         REMOVED

Worker restarts and re-registers:
T+5m    POST /register    Restarted       AVAILABLE (re-added)
```

### 5. Worker Rejection (Worker → Backend, Busy State)

**Pattern**: HTTP 503 with automatic retry

```
Backend                    Worker (BUSY)
  │                           │
  ├─ POST /backtests/start ──>│
  │                           ├─ Check state: BUSY?
  │<─── 503 Service Busy ─────┤
  │  {current_operation: "XYZ"}│
  │                           │
  ├─ Remove from candidates   │
  ├─ Select different worker  │
  └─ Retry (max 3 attempts)   │
```

**Benefit**: Simple exclusivity enforcement without worker-side queuing.

---

## Deployment Models

### 1. Docker Compose (Development/Testing)

**Infrastructure**: Docker Desktop on Mac/Windows/Linux

**Topology**:

```
┌────────────────────────────────────────┐
│ Docker Network (ktrdr-network)         │
│                                        │
│  ┌──────────┐                          │
│  │ Backend  │ :8000                    │
│  └────┬─────┘                          │
│       │                                │
│  ┌────┴────┐                           │
│  │         │                           │
│  ▼         ▼                           │
│ ┌────┐  ┌────┐                         │
│ │Train│ │Back│ (1-N instances)         │
│ │Work││Work│ docker-compose scale     │
│ └────┘  └────┘                         │
└────────────────────────────────────────┘
```

**Starting Workers**:

```bash
# Start backend + default workers
docker-compose up -d

# Scale backtesting workers dynamically
docker-compose up -d --scale backtest-worker=5

# Scale training workers
docker-compose up -d --scale training-worker=3
```

**Worker Discovery**: DNS-based (service names like `backend`, `backtest-worker`)

**Use Cases**:
- Local development
- Integration testing
- Rapid iteration (hot reload with volume mounts)

### 2. Proxmox LXC (Production)

**Infrastructure**: Proxmox VE cluster with LXC containers

**Topology**:

```
┌───────────────────────────────────────────────────┐
│ Proxmox Cluster                                   │
│                                                   │
│  Node 1                  Node 2                   │
│  ┌────────────┐          ┌────────────┐          │
│  │ Backend LXC│          │ GPU Host   │          │
│  │ 192.168.1  │          │ 192.168.1  │          │
│  │ .100:8000  │          │ .101:5002  │          │
│  └──────┬─────┘          └────────────┘          │
│         │                                         │
│  ┌──────┴──────┐                                  │
│  │             │                                  │
│  ▼             ▼                                  │
│ ┌──────┐    ┌──────┐    ┌──────┐                 │
│ │ LXC  │    │ LXC  │    │ LXC  │                 │
│ │ 301  │    │ 302  │    │ 401  │                 │
│ │Backtest│   │Backtest│  │Training│                │
│ │.201  │    │.202  │    │.211  │                 │
│ └──────┘    └──────┘    └──────┘                 │
└───────────────────────────────────────────────────┘
```

**Worker Provisioning**:

1. Clone LXC template (pre-installed KTRDR, Python, uv)
2. Assign static IP address
3. Configure environment variables (KTRDR_API_URL, WORKER_TYPE)
4. Start systemd service
5. Worker self-registers with backend

**Worker Startup** (systemd service):

```ini
[Service]
ExecStart=/opt/ktrdr/.venv/bin/uvicorn ktrdr.backtesting.backtest_worker:app \
    --host 0.0.0.0 --port 5003
Environment="KTRDR_API_URL=http://192.168.1.100:8000"
Environment="WORKER_TYPE=backtesting"
```

**Scaling**: Clone more LXC containers from template, assign IPs

**Use Cases**:
- Production deployments
- High-performance backtesting (lower overhead than Docker)
- Leveraging existing Proxmox infrastructure

### 3. Hybrid GPU Architecture (Both Environments)

**Problem**: Docker containers can't efficiently access GPU

**Solution**: GPU training runs as native host service

**Architecture**:

```
Backend
  │
  ├─ Training Request (prefer_gpu=true)
  │
  ├─> GPU Available? ─YES─> GPU Host Service :5002 (Native)
  │                           │
  │                           └─> CUDA/MPS (Direct access)
  │
  └─> GPU Busy? ──YES──> Training Worker :5004 (Container)
                          └─> CPU-only (Always works)
```

**GPU Host Service**:
- Runs as native Python process (not containerized)
- Direct access to CUDA (NVIDIA) or MPS (Apple Silicon)
- Registers with backend like any other worker
- Same WorkerAPIBase pattern, different capabilities

**Benefit**: Maximizes GPU utilization (10x-100x faster) with CPU fallback (unlimited scale).

---

## Design Decisions & Trade-offs

### 1. Why Push-Based Registration vs Pull-Based Discovery?

**Decision**: Workers self-register (push) rather than backend discovering workers (pull)

**Trade-offs**:

| Aspect | Push-Based (Chosen) | Pull-Based |
|--------|---------------------|------------|
| **Infrastructure Dependency** | None (works everywhere) | High (Docker/Proxmox/K8s APIs) |
| **Code Complexity** | Low (single endpoint) | High (per-environment discovery logic) |
| **Registration Speed** | Immediate (on startup) | Delayed (discovery loop interval) |
| **Failure Recovery** | Automatic (re-register) | Complex (track dead workers) |
| **Cloud-Native** | Yes (K8s/Consul pattern) | Infrastructure-specific |

**Rationale**: Simplicity and portability outweigh security concerns (trusted network assumption). Same pattern works in Docker, LXC, bare metal, and cloud.

### 2. Why WorkerAPIBase Extraction?

**Decision**: Extract 670 lines of common code from training-host-service into reusable base class

**Alternative**: Duplicate infrastructure code in each worker

**Trade-offs**:

| Aspect | WorkerAPIBase (Chosen) | Duplication |
|--------|------------------------|-------------|
| **Code Volume** | ~100 lines per worker | ~670 lines per worker |
| **Maintenance** | Fix once, all workers benefit | Fix in each worker |
| **Consistency** | Guaranteed (same base) | Drift over time |
| **Proven Pattern** | Yes (from training-host) | N/A |
| **Savings (2 workers)** | 570 lines | 0 lines |

**Rationale**: Training-host-service already proved this pattern works. Extract it once, reuse everywhere. Massive code reduction (570 lines for 2 workers).

### 3. Why Container Exclusivity (1 Operation Per Worker)?

**Decision**: Each worker handles exactly 1 operation at a time

**Alternative**: Workers handle multiple concurrent operations

**Trade-offs**:

| Aspect | Exclusive (Chosen) | Concurrent |
|--------|--------------------|------------|
| **Resource Predictability** | Guaranteed | Contention |
| **Performance** | Consistent | Variable |
| **Capacity Planning** | Simple (N workers = N ops) | Complex |
| **Complexity** | Low (IDLE/BUSY state) | High (queue, scheduling) |
| **Scalability** | Horizontal (add workers) | Vertical (bigger workers) |

**Rationale**: Training/backtesting are resource-intensive. Guaranteed resources ensure consistent performance. Horizontal scaling (cheap containers) is easier than managing concurrency.

### 4. Why 1s Cache TTL for Progress?

**Decision**: Keep existing 1s cache for operation progress

**Alternative**: Real-time updates (websockets, SSE)

**Trade-offs**:

| Aspect | 1s Cache (Chosen) | Real-time (Websockets) |
|--------|-------------------|------------------------|
| **Complexity** | Simple (HTTP) | Complex (connection mgmt) |
| **Latency** | Up to 1s delay | Immediate |
| **Scalability** | Excellent (stateless) | Limited (stateful) |
| **Infrastructure** | Standard HTTP | Websocket support needed |
| **Acceptable?** | Yes (ops are minutes-hours) | Overkill |

**Rationale**: 1s delay is acceptable for training/backtesting (operations run for minutes to hours). Simplicity and scalability are more valuable than real-time updates.

### 5. Why Stateless Workers?

**Decision**: Workers hold no persistent state; all state in backend

**Alternative**: Workers maintain local operation history/state

**Trade-offs**:

| Aspect | Stateless (Chosen) | Stateful |
|--------|--------------------|----------|
| **Worker Failure** | Simple (just restart) | Complex (recover state) |
| **Worker Replacement** | Trivial (clone new worker) | Migration needed |
| **State Consistency** | Single source of truth | Distributed (sync issues) |
| **Scalability** | Easy (workers identical) | Harder (state management) |

**Rationale**: Stateless workers are simpler to manage, replace, and scale. Backend is already stateful (OperationsService), so no additional complexity.

### 6. Why Health Check Intervals (10s, 3 failures, 5min removal)?

**Decision**: 10s polling, 3 failures threshold, 5min removal

**Trade-offs**:

| Interval | Detection Speed | Network Overhead | False Positives |
|----------|----------------|------------------|-----------------|
| 1s | Very fast (3s) | High (N req/s) | High |
| **10s (Chosen)** | **Fast (30s)** | **Low (N req/10s)** | **Low** |
| 60s | Slow (3min) | Very low | Very low |

**Rationale**: 10s balances fast failure detection with low overhead. 3 failures (30s) tolerates transient network issues. 5min removal matches Proxmox infrastructure (host failure scenarios).

---

## Summary

The distributed workers architecture transforms KTRDR into a horizontally scalable system through:

1. **WorkerAPIBase**: Reusable infrastructure (~670 lines) extracted from training-host-service
2. **WorkerRegistry**: Central service discovery with push-based registration and health monitoring
3. **Backend Orchestrator**: Never executes operations, only orchestrates (selects workers, tracks progress)
4. **Self-Registration**: Workers push registrations to backend (infrastructure-agnostic, cloud-native)
5. **GPU-First Routing**: Training operations prefer GPU (10x-100x faster) with CPU fallback (always works)
6. **Stateless Workers**: All state in backend, workers are ephemeral and replaceable

**Deployment Flexibility**:
- Docker Compose for development (easy setup, fast iteration)
- Proxmox LXC for production (lower overhead, existing infrastructure)
- Hybrid GPU architecture (native host services + containers)

**Operational Benefits**:
- Horizontal scaling: Add workers = more capacity
- Graceful degradation: System continues with partial availability
- Self-healing: Workers automatically recover and re-register
- Environment parity: Same backend code in dev and prod

**Next Steps**:
- **For Developers**: See [Developer Guide](../developer/distributed-workers-guide.md) for implementation details
- **For Operators**: See [Deployment Guide](../user-guides/deployment.md) for Docker Compose setup
- **For Production**: Proxmox LXC deployment will be documented in Phase 6

---

**Document Status**: Production-Ready
**Related Documents**:
- [Design Document](../architecture/distributed/DESIGN.md) - Design rationale and goals
- [Architecture Document](../architecture/distributed/ARCHITECTURE.md) - Detailed technical specifications
- [Implementation Plan](../architecture/distributed/IMPLEMENTATION_PLAN_PHASES_5-6.md) - Phase-by-phase implementation guide
