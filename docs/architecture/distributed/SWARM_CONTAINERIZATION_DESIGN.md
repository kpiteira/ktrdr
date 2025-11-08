# Docker Swarm Containerization Design
## Hybrid Training/Backtesting Distribution Architecture

**Version**: 1.0
**Status**: Design Phase
**Author**: System Architecture Team
**Date**: 2025-11-08

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Design Decisions](#design-decisions)
4. [Component Specifications](#component-specifications)
5. [Orchestration Patterns](#orchestration-patterns)
6. [Worker Service Implementation](#worker-service-implementation)
7. [Backend Routing Logic](#backend-routing-logic)
8. [Docker Swarm Configuration](#docker-swarm-configuration)
9. [State Management](#state-management)
10. [Deployment Strategy](#deployment-strategy)
11. [Testing Strategy](#testing-strategy)
12. [Migration Path](#migration-path)
13. [Open Questions](#open-questions)

---

## Executive Summary

This document outlines the design for containerizing KTRDR's training and backtesting services using Docker Swarm orchestration while preserving the existing GPU host service capability. The architecture enables parallel distributed execution of multiple training and backtesting operations across a cluster while maintaining the existing async operations infrastructure.

### Key Features

- **Hybrid GPU Architecture**: GPU training via native host services + CPU training via containerized Swarm workers
- **Pure Swarm Backtesting**: Containerized backtesting workers orchestrated entirely by Docker Swarm
- **Priority-Based Training Routing**: GPU host services prioritized over CPU container workers
- **Container Exclusivity**: Each worker container runs exactly 1 operation at a time
- **Minimal Backend Changes**: Preserves existing OperationsService and async infrastructure patterns
- **Horizontal Scalability**: Add workers by scaling Swarm services or adding GPU host nodes

### Design Constraints

✅ Leverage existing async architecture (OperationsService, ServiceOrchestrator, ProgressBridge)
✅ Support both GPU (host services) and CPU (containers) training
✅ Maintain pull-based progress tracking with 1s cache TTL
✅ Preserve cancellation token protocol across boundaries
✅ Ensure exactly 1 operation per worker container instance
✅ Minimize code changes to existing services

---

## Architecture Overview

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER (Unchanged)                     │
│         CLI / Web UI / MCP / External API Clients               │
│                 GET /operations/{id} (Polling)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND (Dispatch & Registry Layer)                │
│                  ktrdr-backend (Port 8000)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ OperationsService (Central Registry)                     │  │
│  │  - Operation metadata & lifecycle                        │  │
│  │  - Progress cache (1s TTL)                               │  │
│  │  - Cancellation coordination                             │  │
│  │  - Worker registry (NEW)                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ServiceOrchestrators (Enhanced)                          │  │
│  │  ├─ TrainingService                                      │  │
│  │  │   └─ Hybrid routing: GPU hosts → CPU containers      │  │
│  │  └─ BacktestingService                                   │  │
│  │      └─ Swarm-only routing                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────┬────────────────────────────┬────────────────────────────────┘
     │                            │
     │ (GPU Training)             │ (CPU Training + All Backtesting)
     │ Priority: HIGH             │ Priority: NORMAL
     ▼                            ▼
┌──────────────────────┐   ┌─────────────────────────────────────┐
│  GPU HOST SERVICES   │   │       DOCKER SWARM CLUSTER          │
│   (Native Hosts)     │   │                                     │
│                      │   │  ┌──────────────────────────────┐  │
│ ┌──────────────────┐ │   │  │  training-worker (Service)   │  │
│ │ Training Host 1  │ │   │  │  ─────────────────────────   │  │
│ │ Port: 5002       │ │   │  │  Replicas: N (e.g., 3)       │  │
│ │ GPU: CUDA 0      │ │   │  │  Image: ktrdr-backend:dev    │  │
│ │ Status: /health  │ │   │  │  Port: 5004                  │  │
│ └──────────────────┘ │   │  │  Mode: CPU training          │  │
│ ┌──────────────────┐ │   │  │  Exclusive: 1 op/container   │  │
│ │ Training Host 2  │ │   │  │  Health: /health             │  │
│ │ Port: 5002       │ │   │  │  Volumes: data, models, etc. │  │
│ │ GPU: CUDA 0      │ │   │  └──────────────────────────────┘  │
│ │ Status: /health  │ │   │             │                       │
│ └──────────────────┘ │   │        Swarm VIP LB                │
│ ┌──────────────────┐ │   │             │                       │
│ │ Training Host N  │ │   │     ┌───────┴───────┐               │
│ │ Port: 5002       │ │   │     ▼       ▼       ▼               │
│ │ GPU: MPS         │ │   │  [Rep 1] [Rep 2] [Rep 3]            │
│ │ Status: /health  │ │   │                                     │
│ └──────────────────┘ │   │  ┌──────────────────────────────┐  │
│                      │   │  │ backtest-worker (Service)    │  │
│ Backend Routing:     │   │  │ ─────────────────────────    │  │
│  - Round-robin       │   │  │ Replicas: M (e.g., 5)        │  │
│  - Health-based      │   │  │ Image: ktrdr-backend:dev     │  │
│  - Manual registry   │   │  │ Port: 5003                   │  │
│  - Priority: HIGH    │   │  │ Mode: Backtesting only       │  │
└──────────────────────┘   │  │ Exclusive: 1 op/container    │  │
                            │  │ Health: /health              │  │
                            │  │ Volumes: data (ro), models   │  │
                            │  └──────────────────────────────┘  │
                            │             │                       │
                            │        Swarm VIP LB                │
                            │             │                       │
                            │     ┌───────┴───────┬───────┐       │
                            │     ▼       ▼       ▼       ▼       │
                            │  [Rep 1] [Rep 2] [Rep 3] [Rep 4]    │
                            └─────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   SHARED STORAGE LAYER                          │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Data Volume   │  │ Model Volume │  │ Strategy Volume      │ │
│  │ (NFS/GlusterFS│  │ (NFS/Gluster)│  │ (NFS - read-only)    │ │
│  │  read-only)   │  │  read-write) │  │                      │ │
│  └───────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### Decision 1: Hybrid GPU Architecture (Q1 → Option C)

**Decision**: Preserve GPU host services while adding containerized CPU training workers

**Rationale**:
- **Preserve existing capability**: Current GPU host services work well, no need to re-engineer
- **Gradual migration path**: Can migrate to NVIDIA Docker containers later if needed
- **Flexibility**: Some nodes have GPUs (host services), others are CPU-only (containers)
- **Priority routing**: Backend can intelligently route based on operation requirements

**Trade-offs**:
- ✅ Lower migration risk
- ✅ Preserves existing GPU patterns
- ✅ Allows heterogeneous cluster (GPU + CPU nodes)
- ❌ More complex routing logic (2 worker types for training)
- ❌ GPU host services not Swarm-managed (manual lifecycle)

**Implementation**:
```python
# Training routing priority
if operation.requires_gpu and gpu_hosts_available:
    worker = select_gpu_host()  # Priority: HIGH
elif cpu_training_workers_available:
    worker = select_cpu_training_worker()  # Fallback
else:
    raise NoWorkersAvailable()
```

---

### Decision 2: Differentiated Orchestration (Q2)

**Decision**:
- **Backtesting**: Pure Swarm orchestration (backend → Swarm VIP → Swarm LB)
- **Training**: Hybrid orchestration with GPU host priority (GPU hosts → Swarm CPU workers)

**Rationale**:

#### Backtesting (Swarm-Only)
- No GPU requirement → pure containerization
- Swarm VIP provides automatic load balancing
- Backend doesn't need to track individual workers
- Simpler: `POST http://backtest-worker:5003/backtests/start`

#### Training (Hybrid Priority)
- GPU operations **must** go to host services (CUDA/MPS access)
- CPU operations can use containerized workers
- Backend checks GPU host availability first, falls back to containers
- Priority ensures GPU resources used when available

**Trade-offs**:
- ✅ Optimal resource utilization (GPU prioritized)
- ✅ Backtesting fully scalable via Swarm
- ✅ Clear separation of concerns
- ❌ Two routing patterns to maintain
- ❌ Training routing more complex than backtesting

**Implementation Flow**:

```
BACKTESTING:
Client → Backend.run_backtest()
  → POST http://backtest-worker:5003/backtests/start
    → Swarm VIP resolves to service
      → Swarm LB picks healthy replica
        → Worker accepts if available, rejects if busy
          → Backend retries with Swarm (gets different replica)

TRAINING (GPU requested):
Client → Backend.start_training(gpu=True)
  → Check GPU host registry
    → POST http://gpu-host-1:5002/training/start (if available)
      → Host accepts if available, rejects if busy
        → Backend tries next GPU host
          → If all GPU hosts busy → queue or reject

TRAINING (CPU acceptable):
Client → Backend.start_training(gpu=False)
  → Check GPU host registry first (priority)
    → If GPU available → use GPU host
    → Else → POST http://training-worker:5004/training/start
      → Swarm VIP → Swarm LB → Worker replica
        → Worker accepts if available, rejects if busy
```

---

### Decision 3: Dedicated Container Types (Q3)

**Decision**: Dedicated worker services (training-worker, backtest-worker) each running 1 operation per container instance

**Rationale**:
- **Clear separation**: Training and backtesting have different resource profiles
- **Simpler state management**: Each container tracks single operation state
- **Container exclusivity**: Worker rejects new operations when busy
- **Swarm scaling**: Can scale training and backtesting independently
- **Resource isolation**: Prevents training from impacting backtesting performance

**Trade-offs**:
- ✅ Simple worker state machine (IDLE → BUSY → IDLE)
- ✅ No inter-operation conflicts
- ✅ Independent scaling per workload type
- ✅ Clear health checks (busy = healthy but unavailable)
- ❌ Potential under-utilization if workload imbalanced
- ❌ More containers overall (2 services instead of 1 generic pool)

**Worker State Machine**:
```python
class WorkerState(Enum):
    IDLE = "idle"           # Ready to accept operations
    BUSY = "busy"           # Running operation
    ERROR = "error"         # Operation failed, cleaning up

class Worker:
    def __init__(self):
        self.state = WorkerState.IDLE
        self.current_operation_id = None

    def accept_operation(self, operation_id: str) -> bool:
        if self.state != WorkerState.IDLE:
            return False  # Reject: already busy

        self.state = WorkerState.BUSY
        self.current_operation_id = operation_id
        return True

    def complete_operation(self):
        self.state = WorkerState.IDLE
        self.current_operation_id = None
```

---

## Component Specifications

### 1. Backend Enhancements

#### 1.1 Worker Registry (NEW)

**Purpose**: Track available workers (GPU hosts + Swarm services)

**Location**: `ktrdr/api/services/worker_registry.py`

**Interface**:
```python
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

class WorkerType(Enum):
    GPU_HOST = "gpu_host"           # Native host service with GPU
    CPU_TRAINING = "cpu_training"   # Swarm training-worker replica
    BACKTESTING = "backtesting"     # Swarm backtest-worker replica

class WorkerStatus(Enum):
    AVAILABLE = "available"   # Idle and healthy
    BUSY = "busy"            # Running operation
    UNHEALTHY = "unhealthy"  # Health check failed
    UNKNOWN = "unknown"      # Not yet discovered

@dataclass
class WorkerEndpoint:
    worker_id: str                    # Unique ID (e.g., "gpu-host-1", "training-worker-rep-2")
    worker_type: WorkerType
    endpoint_url: str                 # e.g., "http://192.168.1.10:5002"
    status: WorkerStatus
    current_operation_id: Optional[str]
    capabilities: dict                # {"gpu": True, "gpu_type": "CUDA", "gpu_memory_gb": 24}
    last_health_check: datetime
    health_check_failures: int

class WorkerRegistry:
    """
    Central registry of all available workers (GPU hosts + Swarm services).

    Responsibilities:
    - Worker discovery (manual for GPU hosts, Swarm API for containers)
    - Health checking
    - Availability tracking
    - Worker selection based on criteria
    """

    def __init__(self):
        self._workers: dict[str, WorkerEndpoint] = {}
        self._gpu_host_configs: List[dict] = []  # Manual config for GPU hosts

    async def discover_workers(self):
        """Background task: discover and health-check all workers."""
        await self._discover_gpu_hosts()
        await self._discover_swarm_workers()

    async def _discover_gpu_hosts(self):
        """Query manually configured GPU host services."""
        # Read from config: gpu_hosts = [{"url": "http://...", "id": "..."}]
        pass

    async def _discover_swarm_workers(self):
        """Query Docker Swarm API for service replicas."""
        # Use Docker API: GET /services/{service_id}/tasks
        pass

    async def health_check_worker(self, worker_id: str) -> bool:
        """Check if worker is healthy via GET /health."""
        pass

    def get_available_workers(
        self,
        worker_type: WorkerType,
        capabilities: Optional[dict] = None
    ) -> List[WorkerEndpoint]:
        """Get all available workers matching criteria."""
        workers = [
            w for w in self._workers.values()
            if w.worker_type == worker_type
            and w.status == WorkerStatus.AVAILABLE
        ]

        # Filter by capabilities
        if capabilities:
            if capabilities.get("gpu"):
                workers = [w for w in workers if w.capabilities.get("gpu")]

        return workers

    def mark_busy(self, worker_id: str, operation_id: str):
        """Mark worker as busy with operation."""
        if worker_id in self._workers:
            self._workers[worker_id].status = WorkerStatus.BUSY
            self._workers[worker_id].current_operation_id = operation_id

    def mark_available(self, worker_id: str):
        """Mark worker as available."""
        if worker_id in self._workers:
            self._workers[worker_id].status = WorkerStatus.AVAILABLE
            self._workers[worker_id].current_operation_id = None

    def register_gpu_host(self, worker_id: str, endpoint_url: str, capabilities: dict):
        """Manually register a GPU host service."""
        self._workers[worker_id] = WorkerEndpoint(
            worker_id=worker_id,
            worker_type=WorkerType.GPU_HOST,
            endpoint_url=endpoint_url,
            status=WorkerStatus.UNKNOWN,
            current_operation_id=None,
            capabilities=capabilities,
            last_health_check=datetime.utcnow(),
            health_check_failures=0
        )
```

**Configuration** (`config/workers.yaml`):
```yaml
gpu_hosts:
  - id: "gpu-host-1"
    url: "http://192.168.1.10:5002"
    capabilities:
      gpu: true
      gpu_type: "CUDA"
      gpu_memory_gb: 24
      device_name: "NVIDIA RTX 4090"

  - id: "gpu-host-2"
    url: "http://192.168.1.11:5002"
    capabilities:
      gpu: true
      gpu_type: "CUDA"
      gpu_memory_gb: 16
      device_name: "NVIDIA RTX 3080"

swarm:
  services:
    training_worker:
      name: "training-worker"
      port: 5004
      replicas: 3

    backtest_worker:
      name: "backtest-worker"
      port: 5003
      replicas: 5

health_check:
  interval_seconds: 10
  timeout_seconds: 5
  failure_threshold: 3
```

---

#### 1.2 Enhanced ServiceOrchestrator Pattern

**Changes to**: `ktrdr/async_infrastructure/service_orchestrator.py`

**New Abstract Methods**:
```python
class ServiceOrchestrator(ABC, Generic[T]):

    # Existing methods...

    @abstractmethod
    def _select_worker(
        self,
        operation_context: Any,
        worker_registry: WorkerRegistry
    ) -> WorkerEndpoint:
        """
        Select optimal worker for operation.

        Implementation varies by service:
        - TrainingService: Priority GPU hosts, fallback CPU workers
        - BacktestingService: Swarm workers only
        """
        pass

    @abstractmethod
    def _get_worker_capabilities_required(self, operation_context: Any) -> dict:
        """Return required worker capabilities for operation."""
        pass
```

**Enhanced Operation Flow**:
```python
async def start_managed_operation(
    self,
    operation_func: Callable,
    operation_context: Any,
    worker_registry: WorkerRegistry,  # NEW
    **kwargs
) -> dict:
    """
    Enhanced flow with worker selection.

    1. Create operation record
    2. Select worker
    3. Dispatch to worker
    4. Register proxy for progress tracking
    5. Return operation_id
    """

    # 1. Create operation
    operation_id = await self.operations_service.create_operation(...)

    # 2. Select worker
    worker = self._select_worker(operation_context, worker_registry)
    if not worker:
        await self.operations_service.fail_operation(
            operation_id,
            error="No workers available"
        )
        raise NoWorkersAvailableError()

    # 3. Dispatch to worker
    try:
        remote_operation_id = await self._dispatch_to_worker(worker, operation_context)
    except WorkerRejectedError:
        # Worker became busy between selection and dispatch
        # Retry with different worker
        worker = self._select_worker(operation_context, worker_registry)
        remote_operation_id = await self._dispatch_to_worker(worker, operation_context)

    # 4. Register proxy
    proxy = OperationServiceProxy(base_url=worker.endpoint_url)
    await self.operations_service.register_remote_proxy(
        backend_operation_id=operation_id,
        proxy=proxy,
        host_operation_id=remote_operation_id
    )

    # 5. Mark worker busy
    worker_registry.mark_busy(worker.worker_id, operation_id)

    return {"operation_id": operation_id, "worker_id": worker.worker_id}
```

---

#### 1.3 Training Service Routing (HYBRID)

**Changes to**: `ktrdr/api/services/training_service.py`

```python
class TrainingService(ServiceOrchestrator):

    def __init__(
        self,
        operations_service: OperationsService,
        worker_registry: WorkerRegistry  # NEW
    ):
        super().__init__(operations_service)
        self.worker_registry = worker_registry

    def _select_worker(
        self,
        operation_context: TrainingOperationContext,
        worker_registry: WorkerRegistry
    ) -> WorkerEndpoint:
        """
        PRIORITY ROUTING:
        1. Check if GPU required or beneficial
        2. Try GPU hosts first (HIGH priority)
        3. Fallback to CPU training workers
        4. Raise if no workers available
        """

        requires_gpu = operation_context.training_config.get("force_gpu", False)
        prefers_gpu = operation_context.training_config.get("prefer_gpu", True)

        # PRIORITY 1: GPU hosts (if required or preferred)
        if requires_gpu or prefers_gpu:
            gpu_workers = worker_registry.get_available_workers(
                worker_type=WorkerType.GPU_HOST,
                capabilities={"gpu": True}
            )

            if gpu_workers:
                # Select best GPU host (by availability, GPU memory, etc.)
                return self._select_best_gpu_host(gpu_workers)

            elif requires_gpu:
                # GPU required but none available → fail
                raise NoGPUWorkersAvailableError(
                    "GPU training requested but no GPU workers available"
                )

        # PRIORITY 2: CPU training workers (Swarm)
        cpu_workers = worker_registry.get_available_workers(
            worker_type=WorkerType.CPU_TRAINING
        )

        if cpu_workers:
            # Swarm will handle load balancing
            # Return the service VIP endpoint (not individual replica)
            return WorkerEndpoint(
                worker_id="training-worker-service",
                worker_type=WorkerType.CPU_TRAINING,
                endpoint_url="http://training-worker:5004",  # Swarm VIP
                status=WorkerStatus.AVAILABLE,
                current_operation_id=None,
                capabilities={"gpu": False},
                last_health_check=datetime.utcnow(),
                health_check_failures=0
            )

        # No workers available
        raise NoWorkersAvailableError(
            "No training workers (GPU or CPU) available"
        )

    def _select_best_gpu_host(self, gpu_workers: List[WorkerEndpoint]) -> WorkerEndpoint:
        """
        Select best GPU host based on:
        - GPU memory available
        - Current load
        - Historical performance

        For now: simple round-robin
        """
        # TODO: Implement smarter selection
        return gpu_workers[0]

    def _get_worker_capabilities_required(
        self,
        operation_context: TrainingOperationContext
    ) -> dict:
        """Return required capabilities for training operation."""
        return {
            "gpu": operation_context.training_config.get("force_gpu", False),
            "min_memory_gb": 8,  # Minimum for training
        }
```

---

#### 1.4 Backtesting Service Routing (SWARM-ONLY)

**Changes to**: `ktrdr/api/services/backtesting_service.py`

```python
class BacktestingService(ServiceOrchestrator):

    def __init__(
        self,
        operations_service: OperationsService,
        worker_registry: WorkerRegistry  # NEW
    ):
        super().__init__(operations_service)
        self.worker_registry = worker_registry

    def _select_worker(
        self,
        operation_context: BacktestOperationContext,
        worker_registry: WorkerRegistry
    ) -> WorkerEndpoint:
        """
        SWARM-ONLY ROUTING:
        1. Return Swarm service VIP endpoint
        2. Swarm handles load balancing to replicas
        3. No need to track individual replicas
        """

        # Check if backtest-worker service is available
        backtest_workers = worker_registry.get_available_workers(
            worker_type=WorkerType.BACKTESTING
        )

        if not backtest_workers:
            raise NoWorkersAvailableError(
                "Backtesting worker service not available"
            )

        # Return Swarm service VIP (load balancing handled by Swarm)
        return WorkerEndpoint(
            worker_id="backtest-worker-service",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://backtest-worker:5003",  # Swarm VIP
            status=WorkerStatus.AVAILABLE,
            current_operation_id=None,
            capabilities={},
            last_health_check=datetime.utcnow(),
            health_check_failures=0
        )

    def _get_worker_capabilities_required(
        self,
        operation_context: BacktestOperationContext
    ) -> dict:
        """Backtesting has no special requirements."""
        return {}
```

**Key Difference**: Backtesting always returns the Swarm service VIP. Swarm's internal load balancing distributes to available replicas. Backend doesn't need to track individual backtest worker replicas.

---

### 2. Worker Service Specifications

#### 2.1 Training Worker (Swarm Service)

**Purpose**: CPU-based training worker for Swarm orchestration

**Service Name**: `training-worker`

**Image**: `ktrdr-backend:dev` (same as backend)

**Port**: 5004

**Replicas**: Configurable (e.g., 3)

**Command**:
```bash
uvicorn ktrdr.training.training_worker_api:app --host 0.0.0.0 --port 5004
```

**Environment**:
```yaml
environment:
  - PYTHONPATH=/app
  - WORKER_TYPE=training
  - WORKER_ID=${HOSTNAME}  # Swarm sets this to replica task ID
  - USE_TRAINING_HOST_SERVICE=false  # Force local mode
  - USE_IB_HOST_SERVICE=true
  - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
  - LOG_LEVEL=INFO
```

**Volumes**:
```yaml
volumes:
  - data:/app/data:ro           # Read-only data
  - models:/app/models:rw       # Read-write models
  - strategies:/app/strategies:ro
  - worker-logs:/app/logs       # Per-worker logs
```

**Health Check**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5004/health"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 30s
```

**API Endpoints** (`ktrdr/training/training_worker_api.py` - NEW):
```python
from fastapi import FastAPI, HTTPException
from ktrdr.training.training_service import TrainingService
from ktrdr.api.models.operations import OperationInfo

app = FastAPI(title="KTRDR Training Worker")

# Worker state
worker_state = {
    "status": "idle",  # idle | busy | error
    "current_operation_id": None,
    "worker_id": os.getenv("WORKER_ID", "unknown"),
    "capabilities": {
        "gpu": False,
        "worker_type": "cpu_training"
    }
}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "worker_status": worker_state["status"],
        "current_operation": worker_state["current_operation_id"],
        "capabilities": worker_state["capabilities"]
    }

@app.post("/training/start")
async def start_training(request: TrainingStartRequest):
    """
    Start training operation.

    Rejects if worker is already busy.
    """
    if worker_state["status"] == "busy":
        raise HTTPException(
            status_code=503,
            detail=f"Worker busy with operation {worker_state['current_operation_id']}"
        )

    # Accept operation
    operation_id = str(uuid.uuid4())
    worker_state["status"] = "busy"
    worker_state["current_operation_id"] = operation_id

    # Start training in background
    background_tasks.add_task(
        run_training_operation,
        operation_id=operation_id,
        request=request
    )

    return {
        "operation_id": operation_id,
        "worker_id": worker_state["worker_id"],
        "status": "started"
    }

async def run_training_operation(operation_id: str, request: TrainingStartRequest):
    """Background task to run training."""
    try:
        # Use local TrainingService (same as backend)
        result = await training_service.run_training(...)
        worker_state["status"] = "idle"
        worker_state["current_operation_id"] = None
    except Exception as e:
        worker_state["status"] = "error"
        logger.error(f"Training failed: {e}")
```

---

#### 2.2 Backtest Worker (Swarm Service)

**Purpose**: Backtesting worker for Swarm orchestration

**Service Name**: `backtest-worker`

**Image**: `ktrdr-backend:dev` (same as backend)

**Port**: 5003

**Replicas**: Configurable (e.g., 5)

**Command**:
```bash
uvicorn ktrdr.backtesting.remote_api:app --host 0.0.0.0 --port 5003
```

**Note**: This already exists! Just needs Swarm configuration.

**Environment**:
```yaml
environment:
  - PYTHONPATH=/app
  - WORKER_TYPE=backtesting
  - WORKER_ID=${HOSTNAME}
  - USE_REMOTE_BACKTEST_SERVICE=false  # Force local mode
  - USE_IB_HOST_SERVICE=true
  - LOG_LEVEL=INFO
```

**Volumes**:
```yaml
volumes:
  - data:/app/data:ro
  - models:/app/models:ro
  - strategies:/app/strategies:ro
  - worker-logs:/app/logs
```

**Enhancements Needed** (`ktrdr/backtesting/remote_api.py`):

Add worker state tracking:
```python
# Add at module level
worker_state = {
    "status": "idle",
    "current_operation_id": None,
    "worker_id": os.getenv("WORKER_ID", "unknown")
}

@app.post("/backtests/start")
async def start_backtest(request: BacktestStartRequest):
    """Enhanced with busy rejection."""
    if worker_state["status"] == "busy":
        raise HTTPException(
            status_code=503,
            detail=f"Worker busy with operation {worker_state['current_operation_id']}"
        )

    # Accept operation
    worker_state["status"] = "busy"
    worker_state["current_operation_id"] = operation_id

    # ... existing logic ...

    # On completion/error:
    worker_state["status"] = "idle"
    worker_state["current_operation_id"] = None
```

---

## Orchestration Patterns

### Pattern 1: Backtesting (Pure Swarm)

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /backtests/start
       ▼
┌─────────────────────────────────────┐
│ Backend (ktrdr-backend:8000)        │
│                                     │
│ BacktestingService.run_backtest()   │
│  ├─ Create operation in OperationsService
│  ├─ Select worker:                  │
│  │   └─ Return "backtest-worker:5003" (Swarm VIP)
│  ├─ POST http://backtest-worker:5003/backtests/start
│  │   (Swarm handles routing)        │
│  └─ Register OperationServiceProxy  │
└──────┬──────────────────────────────┘
       │ HTTP POST
       │
       ▼ (Swarm resolves VIP)
┌─────────────────────────────────────┐
│ Docker Swarm Load Balancer (VIP)    │
│                                     │
│ Service: backtest-worker            │
│ Replicas: 5                         │
│                                     │
│ Routing Algorithm: Round-robin      │
│  ├─ Check replica 1 health → UP    │
│  ├─ Check replica 2 health → UP    │
│  ├─ Check replica 3 health → BUSY (responds 503)
│  └─ Route to replica 2              │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Backtest Worker Replica 2           │
│ (Container: backtest-worker-2)      │
│                                     │
│ 1. Check worker_state["status"]    │
│    → "idle" → Accept                │
│ 2. Set status = "busy"              │
│ 3. Create operation_id              │
│ 4. Start background task            │
│ 5. Return operation_id to backend   │
│                                     │
│ Background:                         │
│  ├─ Run BacktestingEngine           │
│  ├─ Update ProgressBridge           │
│  ├─ OperationsService pulls from bridge
│  └─ On completion: status = "idle"  │
└─────────────────────────────────────┘
       │
       │ (Progress polling)
       ▼
┌─────────────────────────────────────┐
│ Client Polls:                       │
│ GET /operations/{operation_id}      │
│                                     │
│ Backend:                            │
│  ├─ Check cache (1s TTL)            │
│  ├─ If stale:                       │
│  │   └─ proxy.get_operation()       │
│  │      → GET backtest-worker:5003/operations/{op_id}
│  │        (Swarm routes to same replica)
│  └─ Return progress to client       │
└─────────────────────────────────────┘
```

**Key Points**:
- Backend uses Swarm VIP (`backtest-worker:5003`), never direct replica IPs
- Swarm load balancer distributes requests
- Workers reject if busy (503 status)
- Swarm retries on 503 (routes to different replica)
- Progress queries routed by Swarm (usually to same replica via connection persistence)

---

### Pattern 2: Training (Hybrid Priority)

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /trainings/start
       │ {"force_gpu": true}
       ▼
┌──────────────────────────────────────────────┐
│ Backend (ktrdr-backend:8000)                 │
│                                              │
│ TrainingService.start_training()             │
│  ├─ Create operation in OperationsService    │
│  ├─ Select worker (PRIORITY ROUTING):        │
│  │   ├─ Check: force_gpu = true             │
│  │   ├─ Query WorkerRegistry for GPU hosts  │
│  │   │   └─ Available GPU hosts: [gpu-host-1, gpu-host-2]
│  │   ├─ Select: gpu-host-1 (round-robin)    │
│  │   └─ Return "http://192.168.1.10:5002"   │
│  ├─ POST http://192.168.1.10:5002/training/start
│  │   (Direct to GPU host, no Swarm)         │
│  └─ Register OperationServiceProxy           │
└──────┬───────────────────────────────────────┘
       │ HTTP POST (direct)
       │
       ▼
┌──────────────────────────────────────────────┐
│ GPU Host Service 1 (Native, 192.168.1.10)    │
│ Port: 5002                                   │
│                                              │
│ HostTrainingOrchestrator                     │
│  ├─ Check if busy                            │
│  ├─ Accept operation (status = busy)         │
│  ├─ Run TrainingPipeline with GPU            │
│  │   └─ Device: cuda:0 (NVIDIA RTX 4090)    │
│  ├─ Update ProgressBridge                    │
│  └─ Return operation_id                      │
└──────────────────────────────────────────────┘

─────────────────────────────────────────────────
ALTERNATE FLOW: GPU not required, CPU fallback
─────────────────────────────────────────────────

┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /trainings/start
       │ {"prefer_gpu": true}  (not forced)
       ▼
┌──────────────────────────────────────────────┐
│ Backend                                      │
│                                              │
│ TrainingService.start_training()             │
│  ├─ Create operation                         │
│  ├─ Select worker:                           │
│  │   ├─ Check: prefer_gpu = true             │
│  │   ├─ Query GPU hosts → ALL BUSY           │
│  │   ├─ Fallback to CPU workers              │
│  │   └─ Return "http://training-worker:5004" (Swarm VIP)
│  ├─ POST http://training-worker:5004/training/start
│  └─ Register proxy                           │
└──────┬───────────────────────────────────────┘
       │
       ▼ (Swarm VIP resolution)
┌──────────────────────────────────────────────┐
│ Docker Swarm LB                              │
│ Service: training-worker                     │
│ Replicas: [1, 2, 3]                          │
│  └─ Route to replica 1 (idle)                │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ Training Worker Replica 1 (Container)        │
│                                              │
│ 1. Check worker_state → idle                 │
│ 2. Accept operation (status = busy)          │
│ 3. Run TrainingPipeline                      │
│    └─ Device: cpu (no GPU)                   │
│ 4. Update ProgressBridge                     │
│ 5. On complete: status = idle                │
└──────────────────────────────────────────────┘
```

**Priority Logic Summary**:

| GPU Request | GPU Available | Routed To | Notes |
|-------------|---------------|-----------|-------|
| `force_gpu: true` | Yes | GPU host | Direct routing |
| `force_gpu: true` | No | ERROR | Operation fails |
| `prefer_gpu: true` | Yes | GPU host | Priority routing |
| `prefer_gpu: true` | No | CPU worker (Swarm) | Fallback |
| `force_gpu: false` | - | CPU worker (Swarm) | Skip GPU check |

---

## Docker Swarm Configuration

### Swarm Stack File

**File**: `docker/swarm-stack.yml`

```yaml
version: "3.8"

services:
  # Backend service (existing, enhanced)
  backend:
    image: ktrdr-backend:dev
    ports:
      - "8000:8000"
    volumes:
      - type: volume
        source: data
        target: /app/data
        read_only: true
      - type: volume
        source: models
        target: /app/models
      - type: volume
        source: strategies
        target: /app/strategies
        read_only: true
      - type: volume
        source: logs
        target: /app/logs
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
      - USE_TRAINING_HOST_SERVICE=true  # Still use GPU hosts
      - USE_REMOTE_BACKTEST_SERVICE=true  # Now Swarm-managed
      - WORKER_REGISTRY_CONFIG=/app/config/workers.yaml
    networks:
      - ktrdr-network
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3

  # Training worker service (NEW)
  training-worker:
    image: ktrdr-backend:dev
    ports:
      - target: 5004
        published: 5004
        protocol: tcp
        mode: host  # Each replica on different node
    volumes:
      - type: volume
        source: data
        target: /app/data
        read_only: true
      - type: volume
        source: models
        target: /app/models
      - type: volume
        source: strategies
        target: /app/strategies
        read_only: true
      - type: volume
        source: worker-logs
        target: /app/logs
    environment:
      - PYTHONPATH=/app
      - WORKER_TYPE=training
      - WORKER_ID={{.Task.Name}}  # Swarm template
      - USE_TRAINING_HOST_SERVICE=false  # Local mode
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
      - LOG_LEVEL=INFO
    networks:
      - ktrdr-network
    command: ["uvicorn", "ktrdr.training.training_worker_api:app", "--host", "0.0.0.0", "--port", "5004"]
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      rollback_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      placement:
        constraints:
          - node.labels.worker_type == cpu
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5004/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

  # Backtest worker service (enhanced from existing)
  backtest-worker:
    image: ktrdr-backend:dev
    ports:
      - target: 5003
        published: 5003
        protocol: tcp
        mode: host
    volumes:
      - type: volume
        source: data
        target: /app/data
        read_only: true
      - type: volume
        source: models
        target: /app/models
        read_only: true
      - type: volume
        source: strategies
        target: /app/strategies
        read_only: true
      - type: volume
        source: worker-logs
        target: /app/logs
    environment:
      - PYTHONPATH=/app
      - WORKER_TYPE=backtesting
      - WORKER_ID={{.Task.Name}}
      - USE_REMOTE_BACKTEST_SERVICE=false
      - USE_IB_HOST_SERVICE=true
      - LOG_LEVEL=INFO
    networks:
      - ktrdr-network
    command: ["uvicorn", "ktrdr.backtesting.remote_api:app", "--host", "0.0.0.0", "--port", "5003"]
    deploy:
      replicas: 5
      update_config:
        parallelism: 2
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      placement:
        constraints:
          - node.labels.worker_type == cpu
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5003/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

networks:
  ktrdr-network:
    driver: overlay
    attachable: true

volumes:
  data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,rw
      device: ":/mnt/ktrdr/data"

  models:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,rw
      device: ":/mnt/ktrdr/models"

  strategies:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,ro
      device: ":/mnt/ktrdr/strategies"

  logs:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,rw
      device: ":/mnt/ktrdr/logs"

  worker-logs:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,rw
      device: ":/mnt/ktrdr/worker-logs"
```

---

### Swarm Deployment Commands

```bash
# Initialize Swarm (on manager node)
docker swarm init --advertise-addr 192.168.1.10

# Join worker nodes
docker swarm join --token <worker-token> 192.168.1.10:2377

# Label nodes for placement
docker node update --label-add worker_type=cpu node-2
docker node update --label-add worker_type=cpu node-3
docker node update --label-add worker_type=cpu node-4

# Deploy stack
docker stack deploy -c docker/swarm-stack.yml ktrdr

# Scale services
docker service scale ktrdr_training-worker=5
docker service scale ktrdr_backtest-worker=10

# View service status
docker service ls
docker service ps ktrdr_training-worker
docker service ps ktrdr_backtest-worker

# View logs
docker service logs ktrdr_training-worker
docker service logs ktrdr_backtest-worker

# Update service (rolling update)
docker service update --image ktrdr-backend:v2 ktrdr_training-worker

# Remove stack
docker stack rm ktrdr
```

---

## State Management

### Worker State Synchronization

**Challenge**: Workers are ephemeral; backend needs to track operations across worker restarts.

**Solution**: Backend is source of truth, workers are stateless.

**Pattern**:

1. **Backend State** (OperationsService):
   - Operation metadata
   - Progress cache
   - Worker assignment

2. **Worker State** (In-Memory):
   - Current operation ID
   - Worker status (idle/busy)
   - Progress bridge (for OperationsService to query)

3. **Worker Failure Handling**:
   ```python
   # Backend detects worker failure via health check
   if worker.health_check_failures > 3:
       # Mark operation as failed
       await operations_service.fail_operation(
           operation_id,
           error="Worker became unhealthy"
       )

       # Remove worker from registry
       worker_registry.remove_worker(worker_id)

       # Optionally: retry operation on different worker
   ```

4. **Worker Restart**:
   - Worker starts with `status=idle`, `current_operation_id=None`
   - Previous operation marked as failed by backend
   - Client sees operation status=failed, can retry

---

### Progress Tracking Across Workers

**Current Pattern** (Preserved):
```
Client polls → Backend OperationsService
  → Check cache (1s TTL)
  → If stale: Query worker via proxy
    → Worker returns progress from ProgressBridge
  → Backend updates cache
  → Return to client
```

**Swarm Enhancement**:
```
Swarm VIP ensures progress queries route to same replica (connection affinity)
If replica dies → Swarm routes to different replica
  → New replica doesn't have operation → returns 404
  → Backend detects failure → marks operation failed
```

**Sticky Sessions** (Optional Enhancement):
```yaml
# In swarm-stack.yml, add to backtest-worker/training-worker
deploy:
  endpoint_mode: dnsrr  # DNS round-robin (instead of VIP)
  # Backend tracks replica IP from initial response
  # Subsequent queries go directly to that IP
```

---

## Deployment Strategy

### Phase 1: Swarm Cluster Setup (Week 1)

**Tasks**:
1. Initialize Docker Swarm on manager node
2. Join worker nodes to Swarm
3. Set up shared storage (NFS/GlusterFS)
4. Label nodes for placement constraints
5. Create overlay network
6. Test basic Swarm functionality

**Deliverables**:
- [ ] Swarm cluster with 1 manager + N workers
- [ ] NFS volumes mounted on all nodes
- [ ] Overlay network `ktrdr-network`
- [ ] Node labels configured

---

### Phase 2: Backtesting Migration (Week 2)

**Tasks**:
1. Enhance `remote_api.py` with worker state tracking
2. Create `swarm-stack.yml` with backtest-worker service
3. Deploy backtest-worker service to Swarm
4. Update backend to use Swarm VIP (`backtest-worker:5003`)
5. Test backtesting operations
6. Monitor worker health and scaling

**Deliverables**:
- [ ] Backtest-worker service deployed (5 replicas)
- [ ] Backend routing to Swarm VIP
- [ ] Successful parallel backtesting (5 concurrent operations)
- [ ] Health checks passing
- [ ] Logs aggregated

---

### Phase 3: Worker Registry Implementation (Week 3)

**Tasks**:
1. Implement `WorkerRegistry` class
2. Create `config/workers.yaml` with GPU host configuration
3. Add worker discovery background task
4. Implement health checking logic
5. Update `ServiceOrchestrator` with worker selection
6. Test worker discovery and health monitoring

**Deliverables**:
- [ ] WorkerRegistry tracking GPU hosts
- [ ] Background task discovering Swarm workers
- [ ] Health checks running every 10s
- [ ] Worker status visible in API (`GET /workers`)

---

### Phase 4: Training Worker Deployment (Week 4)

**Tasks**:
1. Create `training_worker_api.py`
2. Add training-worker service to `swarm-stack.yml`
3. Deploy training-worker service (3 replicas)
4. Implement hybrid routing in `TrainingService`
5. Test CPU training via Swarm workers
6. Verify GPU host priority routing

**Deliverables**:
- [ ] Training-worker service deployed (3 replicas)
- [ ] Hybrid routing working (GPU priority)
- [ ] CPU training working via Swarm
- [ ] GPU training still working via host services

---

### Phase 5: Integration Testing & Optimization (Week 5)

**Tasks**:
1. End-to-end testing of all flows
2. Load testing with multiple concurrent operations
3. Worker failure/recovery testing
4. Performance tuning (cache TTL, health check intervals)
5. Documentation updates
6. Monitoring dashboards

**Deliverables**:
- [ ] All tests passing (unit, integration, e2e)
- [ ] Load test: 10 concurrent training + 20 concurrent backtesting
- [ ] Failure recovery verified
- [ ] Documentation complete
- [ ] Monitoring setup (Prometheus/Grafana)

---

## Testing Strategy

### Unit Tests

**New Components**:

1. **WorkerRegistry**:
   ```python
   # tests/unit/api/services/test_worker_registry.py
   def test_register_gpu_host()
   def test_get_available_workers()
   def test_mark_busy()
   def test_health_check_failure()
   ```

2. **Worker Selection**:
   ```python
   # tests/unit/api/services/test_training_service.py
   def test_select_gpu_host_when_available()
   def test_fallback_to_cpu_worker_when_gpu_busy()
   def test_error_when_gpu_required_and_unavailable()
   ```

3. **Worker API**:
   ```python
   # tests/unit/training/test_training_worker_api.py
   def test_accept_operation_when_idle()
   def test_reject_operation_when_busy()
   def test_worker_state_transitions()
   ```

---

### Integration Tests

**Swarm Integration**:

```python
# tests/integration/swarm/test_backtest_worker_service.py
@pytest.mark.swarm
async def test_backtest_via_swarm_vip():
    """Test backtesting routed through Swarm VIP."""
    # POST to backend
    response = await client.post("/backtests/start", json={...})
    operation_id = response.json()["operation_id"]

    # Poll for completion
    status = await poll_until_complete(operation_id)

    assert status["status"] == "completed"
    assert "total_return" in status["results"]

@pytest.mark.swarm
async def test_parallel_backtesting():
    """Test multiple concurrent backtests."""
    operations = await asyncio.gather(*[
        client.post("/backtests/start", json={...})
        for _ in range(10)
    ])

    # All should succeed
    assert all(op["success"] for op in operations)
```

**Training Hybrid Routing**:

```python
# tests/integration/swarm/test_training_hybrid_routing.py
@pytest.mark.swarm
async def test_gpu_priority_routing(mock_gpu_host):
    """Test GPU host has priority over CPU workers."""
    # Mock GPU host available
    mock_gpu_host.set_available()

    response = await client.post("/trainings/start", json={
        "prefer_gpu": True,
        ...
    })

    # Should route to GPU host
    assert response.json()["worker_type"] == "gpu_host"

@pytest.mark.swarm
async def test_cpu_fallback_when_gpu_busy(mock_gpu_host):
    """Test fallback to CPU worker when GPU busy."""
    # Mock GPU host busy
    mock_gpu_host.set_busy()

    response = await client.post("/trainings/start", json={
        "prefer_gpu": True,
        ...
    })

    # Should fallback to CPU worker
    assert response.json()["worker_type"] == "cpu_training"
```

---

### Load Tests

```python
# tests/load/test_swarm_scaling.py
import locust

class KTRDRUser(locust.HttpUser):
    @task(2)
    def start_backtest(self):
        self.client.post("/backtests/start", json={
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30"
        })

    @task(1)
    def start_training(self):
        self.client.post("/trainings/start", json={
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
            "strategy_name": "test_strategy",
            "force_gpu": False
        })

# Run: locust -f tests/load/test_swarm_scaling.py --host http://localhost:8000
# Target: 50 concurrent users, 100 requests/s
```

---

## Migration Path

### Option 1: Gradual Migration (Recommended)

**Week 1-2**: Deploy backtesting to Swarm (low risk, already containerized)
**Week 3**: Monitor and validate backtesting in production
**Week 4-5**: Deploy training workers (parallel to GPU hosts)
**Week 6**: Gradually shift training traffic to Swarm workers
**Week 7+**: Full production with GPU hosts + Swarm workers

**Rollback Plan**:
- Backtesting: Set `USE_REMOTE_BACKTEST_SERVICE=false` (instant rollback)
- Training: Keep GPU hosts, remove Swarm workers from registry

---

### Option 2: Big Bang (Higher Risk)

**Week 1-3**: Implement all components in parallel
**Week 4**: Full deployment to Swarm
**Week 5**: Production cutover

**Risk**: Higher chance of issues, harder to isolate problems

---

## Open Questions

### 1. Storage Backend

**Question**: What shared storage solution for NFS volumes?

**Options**:
- NFS server on dedicated machine
- GlusterFS for distributed storage
- Cloud storage (EFS on AWS, Filestore on GCP)
- Local volumes (non-shared, requires data sync)

**Recommendation**: NFS for simplicity, GlusterFS for HA

---

### 2. GPU Container Migration

**Question**: When to migrate GPU training to NVIDIA Docker containers?

**Options**:
- Phase 6 (after Swarm stable)
- Never (keep host services)
- Mixed (some GPU nodes containerized, some native)

**Recommendation**: Evaluate after Phase 5, based on Swarm stability

---

### 3. Auto-Scaling

**Question**: Should we implement auto-scaling for workers?

**Options**:
- Manual scaling only (`docker service scale`)
- Docker Swarm autoscaler (external tool)
- Custom autoscaler (monitor queue depth, scale workers)

**Recommendation**: Start manual, add autoscaling in Phase 6+

---

### 4. Monitoring & Observability

**Question**: What monitoring stack?

**Options**:
- Prometheus + Grafana
- ELK stack (Elasticsearch, Logstash, Kibana)
- Cloud monitoring (CloudWatch, Stackdriver)

**Recommendation**: Prometheus + Grafana for metrics, centralized logging

---

### 5. Worker Affinity

**Question**: Should we use sticky sessions for progress queries?

**Options**:
- VIP mode (Swarm routes, connection pooling may provide affinity)
- DNS RR mode + backend tracks worker IPs
- Redis cache for progress (workers write, backend reads)

**Recommendation**: Start with VIP, monitor if affinity issues occur

---

## Conclusion

This design provides a comprehensive architecture for containerizing KTRDR's training and backtesting services using Docker Swarm while preserving:

✅ Existing async infrastructure (OperationsService, ServiceOrchestrator, ProgressBridge)
✅ GPU training capability via host services
✅ Pull-based progress tracking
✅ Cancellation token protocol
✅ Minimal code changes

**Next Steps**:
1. Review and approve this design
2. Address open questions
3. Begin Phase 1 (Swarm cluster setup)
4. Iterative implementation following migration path

**Estimated Timeline**: 5-7 weeks for full deployment

**Risk Level**: Medium (gradual migration reduces risk)

**Effort**: ~2-3 engineer-weeks of development + 1 week testing

---

**Document End**
