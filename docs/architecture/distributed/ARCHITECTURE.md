# Distributed Training & Backtesting Architecture

**Version**: 2.0
**Status**: Architecture Approved
**Date**: 2025-11-08

---

## Table of Contents

1. [System Context](#system-context)
2. [Architectural Overview](#architectural-overview)
3. [Architectural Layers](#architectural-layers)
4. [Core Components](#core-components)
5. [Key Architectural Patterns](#key-architectural-patterns)
6. [Component Interactions](#component-interactions)
7. [Environment-Specific Architecture](#environment-specific-architecture)
8. [Cross-Cutting Concerns](#cross-cutting-concerns)
9. [Scalability and Performance](#scalability-and-performance)
10. [Trade-offs and Design Decisions](#trade-offs-and-design-decisions)

---

## System Context

### Purpose

The distributed architecture enables KTRDR to scale training and backtesting operations horizontally across multiple compute nodes while preserving the existing async infrastructure and progress tracking capabilities.

### Key Requirements

- **Horizontal Scalability**: Add more compute capacity by adding more workers
- **Worker Exclusivity**: Each worker processes only one operation at a time
- **Hybrid Execution**: Support both GPU host services (for GPU access) and containerized workers (for CPU operations)
- **Unified Progress Tracking**: Maintain existing OperationsService pattern with remote proxy support
- **Environment Flexibility**: Work seamlessly in both development (Docker Compose) and production (Proxmox LXC) environments
- **Minimal Disruption**: Preserve existing ServiceOrchestrator and async infrastructure patterns

### Architecture Drivers

1. **GPU Access Constraint**: Docker containers cannot efficiently access GPU (CUDA/MPS), requiring native host services
2. **Development Parity**: Development on Mac requires different infrastructure (Docker) than production (Proxmox)
3. **Operational Simplicity**: Push-based registration eliminates infrastructure-specific discovery complexity
4. **Self-Healing**: Workers must automatically recover from failures and re-register

---

## Architectural Overview

### System Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        KTRDR Backend                            │
│                      (Central Orchestrator)                     │
│                                                                 │
│  ┌────────────────┐      ┌──────────────────┐                  │
│  │ TrainingService│      │BacktestingService│                  │
│  │ (Orchestrator) │      │   (Orchestrator) │                  │
│  └────────┬───────┘      └────────┬─────────┘                  │
│           │                       │                            │
│           └───────────┬───────────┘                            │
│                       │                                        │
│              ┌────────▼────────┐                               │
│              │ WorkerRegistry  │                               │
│              │  (Push-based)   │                               │
│              └────────┬────────┘                               │
└───────────────────────┼────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │GPU Host  │   │Training  │   │Backtest  │
  │Service   │   │Worker    │   │Worker    │
  │(Native)  │   │(Container)│  │(Container)│
  └──────────┘   └──────────┘   └──────────┘
   CUDA/MPS       CPU-only       CPU-only
```

### Architectural Principles

1. **Separation of Concerns**: Backend orchestrates, workers execute
2. **Push-Based Discovery**: Workers self-register (cloud-native pattern)
3. **Stateless Workers**: Workers hold no persistent state; all state in backend
4. **Environment Abstraction**: Same backend code works in dev and prod
5. **Graceful Degradation**: System continues with partial worker availability

---

## Architectural Layers

The system is organized into three primary architectural layers:

### 1. Orchestration Layer (Backend)

**Responsibility**: Receives user requests, selects workers, dispatches operations, tracks progress

**Key Components**:
- Service Orchestrators (TrainingService, BacktestingService)
- WorkerRegistry (worker lifecycle management)
- OperationsService (operation state and progress tracking)

**Characteristics**:
- Stateful (maintains operation records and worker registry)
- Single instance (centralized coordination)
- Environment-agnostic (works with any worker infrastructure)

### 2. Worker Layer

**Responsibility**: Execute training/backtesting operations, report progress, maintain exclusivity

**Key Components**:
- Training Worker API (CPU training execution)
- Backtest Worker API (backtesting execution)
- GPU Host Services (GPU training execution)
- Local OperationsService instance (worker-local state)

**Characteristics**:
- Stateless (no persistent data)
- Horizontally scalable (add more workers = more capacity)
- Self-registering (push-based discovery)
- Environment-specific (Docker Compose in dev, LXC in prod, native for GPU)

### 3. Infrastructure Layer

**Responsibility**: Container/VM orchestration, networking, resource allocation

**Implementations**:
- **Development**: Docker Compose (Mac)
- **Production**: Proxmox LXC (Linux hosts)
- **GPU**: Native processes (direct hardware access)

---

## Core Components

### WorkerRegistry

**Architectural Role**: Central service discovery and worker lifecycle management

**Key Responsibilities**:
1. Accept push-based worker registrations
2. Maintain real-time worker health status
3. Select optimal worker for operations (round-robin load balancing)
4. Remove dead workers after threshold exceeded
5. Track worker capabilities (GPU, memory, cores)

**Design Pattern**: **Registry Pattern** with **Health Monitoring**

**Core Concepts**:

```python
# Worker lifecycle states
WorkerStatus = AVAILABLE | BUSY | TEMPORARILY_UNAVAILABLE

# Worker registration (push-based)
POST /workers/register
{
    "worker_id": "lxc-worker-301",
    "worker_type": "backtesting",
    "endpoint_url": "http://192.168.1.201:5003",
    "capabilities": {"cores": 4, "memory_gb": 8}
}

# Backend maintains registry
registry = {
    "worker_id": WorkerEndpoint(
        status=AVAILABLE,
        last_health_check=datetime,
        health_check_failures=0,
        ...
    )
}
```

**Health Monitoring Strategy**:
- Background task polls workers every 10 seconds
- 3 consecutive failures → TEMPORARILY_UNAVAILABLE
- 5 minutes unavailable → REMOVED from registry
- Workers re-register on startup (idempotent)

**Worker Selection Algorithm**:
1. Filter by worker type (training vs backtesting)
2. Filter by required capabilities (e.g., GPU)
3. Filter by status (AVAILABLE only)
4. Select least-recently-used (round-robin fairness)

### ServiceOrchestrator (Enhanced)

**Architectural Role**: Base abstraction for service managers with distributed dispatch capability

**Existing Responsibilities** (preserved):
- Async operation lifecycle management
- Progress tracking via GenericProgressManager
- Cancellation token integration
- OperationsService integration

**New Responsibilities** (added):
- Worker selection strategy (service-specific)
- Remote worker dispatch
- Proxy registration for progress bridging

**Design Pattern**: **Template Method Pattern** with **Strategy Pattern** for worker selection

**Architecture Enhancement**:

```python
class ServiceOrchestrator(ABC, Generic[T]):
    """
    Base class for all service managers.

    Existing: Operation lifecycle, progress tracking, cancellation
    New: Worker selection and remote dispatch
    """

    # NEW: Service-specific worker selection strategy
    @abstractmethod
    def _select_worker(self, operation_context) -> Optional[WorkerEndpoint]:
        """
        Each service defines its own worker selection logic:

        TrainingService:
            1. Try GPU hosts (if GPU preferred/required)
            2. Fallback to CPU workers
            3. Fail if no workers available

        BacktestingService:
            1. Select any available backtest worker
            2. Fail if none available
        """
        pass

    # ENHANCED: Unified operation start flow
    async def start_managed_operation(self, operation_func, context):
        """
        Orchestration flow:

        1. Create operation record (OperationsService)
        2. Select worker (service-specific strategy)
        3. Dispatch to worker (HTTP request)
        4. Register proxy (for progress tracking)
        5. Mark worker busy (WorkerRegistry)
        6. Return operation_id
        """
```

**Worker Selection Example** (Training Service):

```python
class TrainingService(ServiceOrchestrator):
    def _select_worker(self, context: TrainingContext):
        requires_gpu = context.training_config.get("force_gpu", False)
        prefers_gpu = context.training_config.get("prefer_gpu", True)

        # Priority 1: GPU hosts (if needed/preferred)
        if requires_gpu or prefers_gpu:
            gpu_workers = self.worker_registry.get_available_workers(
                worker_type=WorkerType.GPU_HOST,
                capabilities={"gpu": True}
            )

            if gpu_workers:
                return gpu_workers[0]  # Round-robin selection
            elif requires_gpu:
                raise NoGPUWorkersAvailableError()

        # Priority 2: CPU workers (fallback)
        cpu_workers = self.worker_registry.get_available_workers(
            worker_type=WorkerType.CPU_TRAINING
        )

        return cpu_workers[0] if cpu_workers else None
```

This pattern enables **hybrid execution**: GPU operations prefer GPU hosts, but can fallback to CPU if configured; backtesting uses any available worker.

### Worker API Architecture

**Architectural Role**: Standardized interface for workers to receive operations and report status

**Design Pattern**: **REST API** with **State Machine** (idle → busy → idle)

**Core Responsibilities**:
1. Accept operation requests
2. Enforce exclusivity (reject if busy)
3. Execute operation in background
4. Report health and status
5. Track progress via local OperationsService

**Worker State Machine**:

```
        ┌──────┐
        │ IDLE │ ◄────────────────┐
        └──┬───┘                  │
           │                      │
           │ POST /training/start │
           ▼                      │
        ┌──────┐                  │
        │ BUSY │                  │
        └──┬───┘                  │
           │                      │
           │ operation completes  │
           └──────────────────────┘
```

**Exclusivity Enforcement** (critical for resource management):

```python
@app.post("/training/start")
async def start_training(request: TrainingStartRequest):
    # EXCLUSIVITY CHECK
    if worker_state["status"] == "busy":
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail={
                "error": "Worker busy",
                "current_operation": worker_state["current_operation_id"]
            }
        )

    # Accept operation
    operation_id = str(uuid.uuid4())
    worker_state["status"] = "busy"
    worker_state["current_operation_id"] = operation_id

    # Execute in background
    background_tasks.add_task(run_training, operation_id, request)

    return {"operation_id": operation_id}
```

When backend receives 503, it **automatically retries with a different worker** (handled by ServiceOrchestrator dispatch logic).

### Remote Progress Tracking Architecture

**Architectural Challenge**: How does backend track progress of operations running on remote workers?

**Solution**: **Proxy Pattern** with **Pull-Based Polling**

**Architecture**:

```
Backend                           Worker
┌────────────────────┐           ┌─────────────────────┐
│ OperationsService  │           │ Local               │
│  (Backend State)   │           │ OperationsService   │
│                    │           │  (Worker State)     │
│  operation_id: XYZ │◄─polling──│  operation_id: ABC  │
│  status: running   │           │  status: running    │
│  progress: 45%     │           │  progress: 45%      │
└────────────────────┘           └─────────────────────┘
         ▲                                │
         │                                │
         │         ┌─────────────────┐    │
         └─────────┤OperationService │────┘
                   │     Proxy       │
                   └─────────────────┘
                   GET /operations/ABC
                   every 1 second
```

**Flow**:
1. Backend creates operation record (operation_id: XYZ)
2. Backend dispatches to worker, gets remote operation_id (ABC)
3. Backend registers proxy mapping: XYZ → (worker_url, ABC)
4. Backend polls worker every 1s: `GET worker_url/operations/ABC`
5. Backend updates local operation state from worker response
6. User polls backend: `GET /operations/XYZ` (served from cache)

**Key Properties**:
- **Decoupling**: Workers don't need to know about backend
- **Simplicity**: Standard REST polling (no websockets, no pub/sub)
- **Caching**: 1s cache TTL on backend prevents excessive polling
- **Transparency**: Users see unified operation state regardless of execution location

---

## Key Architectural Patterns

### 1. Push-Based Service Registration

**Pattern**: Workers self-register with backend on startup

**Why This Pattern**:
- **Infrastructure Agnostic**: Works with Docker, LXC, VMs, bare metal, cloud
- **Simpler**: No infrastructure-specific discovery code (no Docker API, no Proxmox API)
- **Faster**: Immediate registration (no discovery loop delay)
- **Cloud-Native**: Standard pattern used by Kubernetes, Consul, Eureka

**Implementation Concept**:

```python
# Worker startup script
async def on_startup():
    """Called when worker starts"""
    await register_with_backend()

async def register_with_backend():
    """Push registration to backend"""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BACKEND_URL}/workers/register",
            json={
                "worker_id": socket.gethostname(),
                "worker_type": "backtesting",
                "endpoint_url": f"http://{get_ip()}:5003",
                "capabilities": get_system_capabilities()
            }
        )
```

**Registration is Idempotent**: Workers can re-register after restarts; backend updates existing record.

### 2. Health-Based Availability

**Pattern**: Backend continuously monitors worker health; marks unavailable if health checks fail

**State Transitions**:

```
AVAILABLE ──(3 failed checks)──> TEMPORARILY_UNAVAILABLE ──(5 min)──> REMOVED
    ▲                                        │
    │                                        │
    └────────(successful health check)──────┘
```

**Health Check Design**:

```python
# Backend polls worker
async def health_check_worker(worker_id: str) -> bool:
    response = await http_client.get(f"{worker.endpoint_url}/health")

    if response.status_code == 200:
        data = response.json()

        # Update worker status from health response
        worker.status = parse_status(data["worker_status"])  # idle → AVAILABLE
        worker.current_operation_id = data.get("current_operation")
        worker.health_check_failures = 0  # Reset counter

        return True
    else:
        worker.health_check_failures += 1

        if worker.health_check_failures >= 3:
            worker.status = TEMPORARILY_UNAVAILABLE

        return False
```

**Why 3 Failures**: Tolerates transient network issues (e.g., brief switch failure)

**Why 5 Minutes Before Removal**: In Proxmox environment, unreachable worker typically means host is down (user's infrastructure knowledge). 5 minutes is reasonable grace period before assuming permanent failure.

### 3. Hybrid Orchestration (GPU + Containers)

**Pattern**: Service-specific worker selection strategies enable GPU priority with container fallback

**Architectural Rationale**:

Training operations can run on either GPU or CPU, but GPU is strongly preferred for performance:
- GPU training: 10x-100x faster
- CPU training: Always available (can add unlimited workers)

**Strategy**:

```
Training Request
    │
    ▼
┌─────────────────┐
│ GPU Required?   │──YES──> Select GPU Host ──(none available)──> FAIL
└────────┬────────┘
         │ NO
         ▼
┌─────────────────┐
│ GPU Preferred?  │──YES──> Try GPU Host ──(none available)──> CPU Worker
└────────┬────────┘
         │ NO
         ▼
   CPU Worker
```

**Architectural Benefit**: Maximizes GPU utilization (high-value resource) while maintaining CPU scalability (low-cost resource).

Backtesting has no GPU benefit → Always uses containerized workers (simpler).

### 4. Environment Abstraction

**Pattern**: Backend code is environment-agnostic; worker infrastructure varies by environment

**Architecture**:

```python
# Backend (same everywhere)
class WorkerRegistry:
    def __init__(self, config: WorkerConfig):
        self.workers: Dict[str, WorkerEndpoint] = {}
        # Worker registration is ALWAYS via POST /workers/register
        # No environment-specific code in backend

# Workers register themselves (environment-specific startup)

# Development (docker-compose.yml)
services:
  backtest-worker:
    command: ["uvicorn", "ktrdr.backtesting.remote_api:app", ...]
    # Worker calls BACKEND_URL/workers/register on startup

# Production (LXC systemd service)
[Service]
ExecStart=/opt/ktrdr/uv run uvicorn ktrdr.backtesting.remote_api:app
# Worker calls BACKEND_URL/workers/register on startup
```

**Key Insight**: Push-based registration eliminates all environment-specific logic from backend. Backend only cares about HTTP endpoints, not how workers are deployed.

### 5. Round-Robin Load Balancing

**Pattern**: Distribute operations evenly across available workers

**Algorithm**:

```python
def select_worker(worker_type: WorkerType) -> WorkerEndpoint:
    # 1. Get all available workers of requested type
    workers = [w for w in registry.workers.values()
               if w.worker_type == worker_type
               and w.status == AVAILABLE]

    # 2. Sort by last selection time (least recently used first)
    workers.sort(key=lambda w: w.metadata.get("last_selected", 0))

    # 3. Select first (LRU = round-robin fairness)
    selected = workers[0]

    # 4. Mark selection time for next round
    selected.metadata["last_selected"] = time.time()

    return selected
```

**Properties**:
- **Fairness**: All workers get equal share of operations (assuming equal capacity)
- **Simplicity**: No complex scheduling logic
- **Stateless**: Selection state is just a timestamp (survives backend restarts)

**Future Enhancement**: Could add weighted round-robin based on worker capabilities (cores, memory).

---

## Component Interactions

### Operation Dispatch Flow

**Sequence**: User starts training operation

```
User                  Backend                WorkerRegistry         Worker
 │                      │                          │                  │
 │──POST /training──────>│                          │                  │
 │                      │                          │                  │
 │                      │──select_worker()────────>│                  │
 │                      │<─────worker──────────────│                  │
 │                      │                          │                  │
 │                      │──POST /training/start──────────────────────>│
 │                      │<──operation_id─────────────────────────────│
 │                      │                          │                  │
 │                      │──mark_busy()────────────>│                  │
 │                      │                          │                  │
 │<──operation_id───────│                          │                  │
 │                      │                          │                  │
 │                      │                          │                  │
 │  (poll progress)     │                          │                  │
 │──GET /operations/123─>│                          │                  │
 │                      │──proxy.get_status()────────────────────────>│
 │                      │<──progress──────────────────────────────────│
 │<──progress───────────│                          │                  │
```

**Key Steps**:
1. Backend selects worker (round-robin from registry)
2. Backend dispatches operation to worker (HTTP POST)
3. Worker starts operation, returns remote operation_id
4. Backend registers proxy for progress polling
5. Backend marks worker as BUSY
6. User polls backend for progress
7. Backend polls worker (via proxy), caches result, serves user

### Worker Registration Flow

**Sequence**: New worker comes online

```
Worker                     Backend
  │                          │
  │──POST /workers/register─>│
  │  {worker_id, url, ...}   │
  │                          │──(add to registry)
  │<──200 OK─────────────────│
  │                          │
  │                          │
  │      (every 10s)         │
  │<──GET /health────────────│
  │                          │
  │──200 OK─────────────────>│
  │  {status: idle}          │──(update status: AVAILABLE)
```

**Idempotency**: If worker re-registers (after restart), backend updates existing record instead of creating duplicate.

### Worker Failure Recovery Flow

**Sequence**: Worker becomes unavailable

```
Time  Backend Health Check              Worker State    Registry State
────────────────────────────────────────────────────────────────────────
T+0s  GET /health ──> 200 OK            Running         AVAILABLE
T+10s GET /health ──> timeout (1/3)     Crashed         AVAILABLE
T+20s GET /health ──> timeout (2/3)     Crashed         AVAILABLE
T+30s GET /health ──> timeout (3/3)     Crashed         TEMPORARILY_UNAVAILABLE
...
T+5m  Cleanup task runs                 Crashed         REMOVED

(Worker restarts)
T+5m  POST /workers/register ──> 200     Restarted       AVAILABLE (re-registered)
```

**Key Properties**:
- **Grace Period**: 3 failures (30s) before marking unavailable
- **Removal Threshold**: 5 minutes before removing from registry
- **Auto-Recovery**: Worker re-registers on restart (no manual intervention)

---

## Environment-Specific Architecture

### Development Environment (Docker Compose)

**Infrastructure**: Docker Compose on Mac

**Topology**:

```
┌─────────────────────────────────────────┐
│ Docker Network (ktrdr-network)          │
│                                         │
│  ┌──────────────┐                       │
│  │   Backend    │ :8000                 │
│  │  (FastAPI)   │                       │
│  └──────┬───────┘                       │
│         │                               │
│    ┌────┴────┐                          │
│    │         │                          │
│    ▼         ▼                          │
│ ┌─────┐  ┌─────┐                        │
│ │Train│  │Back │  (1-N instances via    │
│ │Work │  │Work │   docker-compose scale)│
│ └─────┘  └─────┘                        │
│                                         │
└─────────────────────────────────────────┘
```

**Worker Discovery**: DNS-based (Docker Compose service names)

**Scaling**:
```bash
# Add more workers dynamically
docker-compose up -d --scale backtest-worker=5
```

Each worker:
- Calls `POST http://backend:8000/workers/register` on startup
- Uses service name `backend` (Docker DNS resolution)
- Receives unique hostname from Docker (e.g., `backtest-worker_1`, `backtest-worker_2`)

**Configuration** (`docker-compose.yml`):

```yaml
services:
  backend:
    ports: ["8000:8000"]
    networks: [ktrdr-network]

  training-worker:
    command: ["uvicorn", "ktrdr.training.training_worker_api:app", ...]
    environment:
      BACKEND_URL: http://backend:8000
      WORKER_TYPE: training
    networks: [ktrdr-network]
    # Scale: docker-compose up -d --scale training-worker=3
```

### Production Environment (Proxmox LXC)

**Infrastructure**: Proxmox cluster with LXC containers

**Topology**:

```
┌────────────────────────────────────────────────────────────┐
│ Proxmox Cluster                                            │
│                                                            │
│  Node 1                    Node 2                          │
│  ┌────────────────┐        ┌────────────────┐             │
│  │ Backend VM     │        │ GPU Host       │             │
│  │ 192.168.1.100  │        │ 192.168.1.101  │             │
│  └────────────────┘        └────────────────┘             │
│                                                            │
│  ┌────────────────┐        ┌────────────────┐             │
│  │ LXC 301        │        │ LXC 302        │             │
│  │ Backtest Worker│        │ Backtest Worker│             │
│  │ 192.168.1.201  │        │ 192.168.1.202  │             │
│  └────────────────┘        └────────────────┘             │
│                                                            │
│  ┌────────────────┐        ┌────────────────┐             │
│  │ LXC 401        │        │ LXC 402        │             │
│  │ Training Worker│        │ Training Worker│             │
│  │ 192.168.1.211  │        │ 192.168.1.212  │             │
│  └────────────────┘        └────────────────┘             │
└────────────────────────────────────────────────────────────┘
```

**Worker Discovery**: Push-based registration (workers call backend URL)

**LXC Container Configuration**:
- Cloned from template (pre-installed KTRDR, uv, Python)
- Static IP assignment
- Systemd service auto-starts worker on boot
- Tagged for organizational purposes (not used for discovery)

**Worker Startup** (systemd service):

```ini
[Service]
ExecStart=/opt/ktrdr/uv run uvicorn ktrdr.backtesting.remote_api:app \
    --host 0.0.0.0 --port 5003
Environment="BACKEND_URL=http://192.168.1.100:8000"
Environment="WORKER_TYPE=backtesting"
Environment="WORKER_ID=%H"  # Hostname
```

On startup, worker calls:
```
POST http://192.168.1.100:8000/workers/register
{
    "worker_id": "ktrdr-backtest-worker-1",
    "endpoint_url": "http://192.168.1.201:5003",
    ...
}
```

**Scaling**: Clone more LXC containers from template, assign IPs, start services

### GPU Host Services (Both Environments)

**Infrastructure**: Native processes on host with GPU

**Rationale**: Docker containers cannot efficiently access CUDA/MPS → Run as host service

**Architecture**:

```
Backend ──(HTTP)──> GPU Host Service :5002 ──(direct)──> CUDA/MPS
                    (Native Python Process)
```

**Discovery**: Manual configuration (static endpoints in config file)

```yaml
# config/workers.prod.yaml
gpu_hosts:
  - id: "gpu-host-1"
    url: "http://192.168.1.101:5002"
    capabilities:
      gpu: true
      gpu_type: "CUDA"
      gpu_memory_gb: 24
```

Backend registers GPU hosts on startup (no push registration from GPU hosts, since they're pre-existing services).

---

## Cross-Cutting Concerns

### Error Handling

**Architectural Strategy**: Graceful degradation with automatic retry

**Scenarios**:

1. **No Workers Available**:
   - Backend fails operation immediately with clear error
   - User sees: "No workers available for training"
   - Operation state: FAILED

2. **Worker Busy** (503 response):
   - Backend automatically retries with different worker (up to 3 attempts)
   - If all workers busy: Fail with "All workers busy, retry later"
   - Operation state: FAILED

3. **Worker Crashes During Operation**:
   - Health checks detect failure (worker stops responding)
   - Backend marks worker TEMPORARILY_UNAVAILABLE
   - Operation state: RUNNING (worker may have completed before crash)
   - User polls operation: Eventually times out or worker recovers and reports result

4. **Network Partition** (worker unreachable):
   - Health checks fail, worker marked TEMPORARILY_UNAVAILABLE
   - After 5 minutes: Worker removed from registry
   - When network recovers: Worker re-registers automatically
   - In-flight operations: Lost (operation shows RUNNING indefinitely)
   - **Future Enhancement**: Operation timeout detection

### Security

**Current Architecture**: Trusted network (no authentication)

**Assumptions**:
- All workers run on trusted infrastructure (private network)
- No external access to worker endpoints
- Backend is only public-facing component

**Production Considerations**:
- Backend should enforce authentication (existing pattern)
- Worker-to-backend communication over private network
- No worker-to-worker communication required

**Future Enhancements** (if needed):
- Mutual TLS between backend and workers
- API tokens for worker registration
- Rate limiting on worker registration endpoint

### Monitoring and Observability

**Architectural Hooks**:

1. **Worker Registry State**: Expose `/workers` endpoint listing all workers, status, health
   ```json
   {
       "total_workers": 8,
       "available": 5,
       "busy": 2,
       "unavailable": 1,
       "workers": [...]
   }
   ```

2. **Health Check Metrics**: Track health check success/failure rates
3. **Operation Metrics**: Track operation dispatch time, completion rate
4. **Worker Utilization**: Track busy vs idle time per worker

**Logging Strategy**:
- Backend logs: Worker registration, selection, dispatch, health check failures
- Worker logs: Operation start/complete, errors
- Structured logging with correlation IDs (operation_id, worker_id)

### Configuration Management

**Architectural Principle**: Environment-specific configuration, not hardcoded

**Configuration Files**:

```
config/
  workers.dev.yaml      # Development (Docker Compose)
  workers.prod.yaml     # Production (Proxmox LXC)
```

**Environment Variable**: `WORKER_CONFIG` specifies which config to load

**Configuration Schema**:

```yaml
# Minimal config (push-based registration)
health_check:
  interval_seconds: 10
  timeout_seconds: 5
  failure_threshold: 3
  removal_threshold_seconds: 300

# Optional: GPU hosts (manual registration)
gpu_hosts:
  - id: "gpu-host-1"
    url: "http://192.168.1.101:5002"
    capabilities: {gpu: true, gpu_type: "CUDA"}
```

**No Worker Endpoints in Config**: Workers self-register (push-based), so config doesn't specify worker URLs.

---

## Scalability and Performance

### Horizontal Scalability

**Training Operations**:
- **GPU-bound**: Limited by number of GPU hosts (expensive, specialized hardware)
- **CPU fallback**: Unlimited scaling (add more LXC containers)
- Scaling factor: 1 operation per worker

**Backtesting Operations**:
- **CPU-only**: Unlimited scaling (add more LXC containers)
- Scaling factor: 1 operation per worker

**Example Capacity**:
- 3 GPU hosts → 3 concurrent GPU training operations
- 5 CPU training workers → 5 concurrent CPU training operations
- 10 backtest workers → 10 concurrent backtesting operations

**Total**: 18 concurrent operations (with simple resource addition)

### Performance Characteristics

**Operation Dispatch Latency**:
- Worker selection: O(n) where n = number of workers (~10-100 workers → <1ms)
- Worker dispatch: 1 HTTP request (~10-50ms local network)
- Total overhead: <100ms (negligible compared to operation duration)

**Progress Polling Overhead**:
- Backend polls workers every 1s (cached)
- User polls backend (served from cache)
- Network overhead: Minimal (1 request/worker/second)

**Health Check Overhead**:
- 1 request per worker every 10s
- For 20 workers: 2 requests/second
- Negligible network/CPU impact

### Bottlenecks and Mitigations

**Potential Bottleneck**: Backend becomes single point of contention

**Current Mitigation**:
- Async I/O (FastAPI) → Handles thousands of concurrent requests
- Caching (1s TTL) → Reduces worker polling frequency
- Stateless workers → No backend-to-worker state synchronization

**Future Scaling** (if needed):
- Multiple backend instances with shared database (PostgreSQL)
- Distributed worker registry (Redis-backed)
- Load balancer in front of backend instances

**Estimated Capacity** (single backend instance):
- 100+ workers
- 1000+ operations/hour
- Limited by operation duration, not backend throughput

---

## Trade-offs and Design Decisions

### Decision 1: Push vs Pull Registration

**Chosen**: Push-based (workers register with backend)

**Alternative**: Pull-based (backend discovers workers via infrastructure APIs)

**Trade-offs**:

| Aspect | Push-Based (Chosen) | Pull-Based |
|--------|---------------------|------------|
| **Complexity** | Simple (no infrastructure API integration) | Complex (Docker API, Proxmox API, etc.) |
| **Environment Portability** | Works everywhere (infrastructure-agnostic) | Requires environment-specific code |
| **Startup Latency** | Immediate (worker registers on startup) | Delayed (waits for discovery loop) |
| **Failure Recovery** | Automatic (worker re-registers) | Requires discovery loop to detect |
| **Security** | Requires trust (anyone can register) | More controlled (backend controls discovery) |

**Rationale**: Simplicity and portability outweigh security concerns (trusted network assumption).

### Decision 2: Worker Exclusivity (1 Operation Per Worker)

**Chosen**: Each worker handles exactly 1 operation at a time

**Alternative**: Workers handle multiple concurrent operations

**Trade-offs**:

| Aspect | Exclusive (Chosen) | Concurrent |
|--------|-------------------|------------|
| **Resource Predictability** | Guaranteed resources per operation | Resource contention |
| **Scheduling Complexity** | Simple (worker is available or not) | Complex (worker capacity tracking) |
| **Operation Performance** | Consistent (no interference) | Variable (depends on other operations) |
| **Worker Utilization** | Lower (idle between operations) | Higher (always processing) |
| **Scalability** | Horizontal (add more workers) | Vertical (bigger workers) |

**Rationale**: Training and backtesting are resource-intensive; guaranteed resources ensure consistent performance. Horizontal scaling (cheap containers) is easier than managing concurrency.

### Decision 3: Health Check Intervals

**Chosen**: 10s polling interval, 3 failures threshold, 5min removal

**Trade-offs**:

| Interval | Detection Speed | Network Overhead | False Positives |
|----------|----------------|------------------|-----------------|
| 1s | Very fast | High | High (transient issues) |
| **10s (Chosen)** | **Fast (30s)** | **Low** | **Low** |
| 60s | Slow (3min) | Very low | Very low |

**Rationale**: 10s balances fast failure detection with low overhead. 3 failures (30s) tolerates transient network issues. 5min removal matches user's infrastructure characteristics (Proxmox host failure scenarios).

### Decision 4: 1s Cache TTL (OperationsService)

**Chosen**: Keep existing 1s cache for operation status

**Alternative**: Real-time websockets or Server-Sent Events

**Trade-offs**:

| Aspect | 1s Cache (Chosen) | Real-time (Websockets) |
|--------|-------------------|------------------------|
| **Complexity** | Simple (HTTP polling) | Complex (connection management) |
| **Latency** | Up to 1s delay | Immediate updates |
| **Scalability** | Excellent (stateless HTTP) | Limited (stateful connections) |
| **Browser Compatibility** | Universal | Good (modern browsers) |
| **Infrastructure** | Standard HTTP | Requires websocket support |

**Rationale**: 1s delay is acceptable for training/backtesting operations (minutes to hours duration). Simplicity and scalability are more valuable than real-time updates.

### Decision 5: Stateless Workers

**Chosen**: Workers hold no persistent state; all state in backend

**Alternative**: Workers maintain local operation history/state

**Trade-offs**:

| Aspect | Stateless (Chosen) | Stateful |
|--------|--------------------|----------|
| **Worker Failure Recovery** | Simple (just re-register) | Complex (state recovery) |
| **Worker Replacement** | Trivial (clone new worker) | Requires data migration |
| **State Consistency** | Single source of truth (backend) | Distributed state (sync issues) |
| **Query Performance** | Backend lookup only | Could be faster (local state) |

**Rationale**: Stateless workers are simpler to manage, replace, and scale. Backend is already stateful (OperationsService), so no additional complexity.

---

## Summary

This architecture enables KTRDR to scale training and backtesting operations horizontally while preserving existing async infrastructure patterns. The key architectural principles are:

1. **Push-Based Registration**: Workers self-register, making the system infrastructure-agnostic
2. **Health Monitoring**: Continuous health checks with automatic failure detection and recovery
3. **Hybrid Execution**: GPU host services for performance, containerized workers for scalability
4. **Environment Abstraction**: Same backend code works in dev (Docker) and prod (LXC)
5. **Stateless Workers**: All state in backend, workers are ephemeral and replaceable
6. **Round-Robin Load Balancing**: Fair distribution of operations across available workers

The architecture is designed for **operational simplicity** (minimal manual intervention), **horizontal scalability** (add more workers = more capacity), and **graceful degradation** (system continues with partial worker availability).

For implementation details, see `IMPLEMENTATION_PLAN.md`.

For design rationale and high-level concepts, see `DESIGN.md`.
