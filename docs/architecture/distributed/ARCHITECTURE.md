# Distributed Training & Backtesting Architecture
## Technical Implementation Specification

**Version**: 2.0
**Status**: Implementation Ready
**Date**: 2025-11-08

---

## Table of Contents

1. [Component Specifications](#component-specifications)
2. [Worker Registry Implementation](#worker-registry-implementation)
3. [Service Orchestrator Enhancements](#service-orchestrator-enhancements)
4. [Worker API Specifications](#worker-api-specifications)
5. [Configuration Management](#configuration-management)
6. [Docker Compose Setup](#docker-compose-setup)
7. [Proxmox LXC Setup](#proxmox-lxc-setup)
8. [Testing Specifications](#testing-specifications)

---

## Component Specifications

### WorkerRegistry

**Purpose**: Centralized registry for worker discovery, health checking, and selection

**Location**: `ktrdr/api/services/worker_registry.py`

**Dependencies**:
```python
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import httpx
import docker  # for Docker discovery mode
from proxmoxer import ProxmoxAPI  # for Proxmox discovery mode
```

**Data Models**:

```python
class WorkerType(Enum):
    """Types of workers in the system."""
    GPU_HOST = "gpu_host"           # Native host service with GPU
    CPU_TRAINING = "cpu_training"   # Container-based CPU training
    BACKTESTING = "backtesting"     # Container-based backtesting

class WorkerStatus(Enum):
    """Worker availability status."""
    AVAILABLE = "available"   # Idle and healthy
    BUSY = "busy"            # Running operation
    UNHEALTHY = "unhealthy"  # Health check failed
    UNKNOWN = "unknown"      # Not yet checked

@dataclass
class WorkerEndpoint:
    """Represents a discovered worker endpoint."""
    worker_id: str                    # Unique identifier
    worker_type: WorkerType          # Type of worker
    endpoint_url: str                # HTTP endpoint (e.g., "http://192.168.1.201:5003")
    status: WorkerStatus             # Current status
    current_operation_id: Optional[str]  # Operation ID if busy
    capabilities: Dict[str, Any]     # Worker capabilities (gpu, memory, etc.)
    last_health_check: datetime      # Last successful health check
    health_check_failures: int       # Consecutive failures
    metadata: Dict[str, Any]         # Additional metadata (node, container ID, etc.)
```

**Class Interface**:

```python
class WorkerRegistry:
    """
    Central registry for worker discovery and management.

    Supports multiple discovery modes:
    - docker: Discover workers via Docker API (dev)
    - proxmox: Discover workers via Proxmox API (prod)
    - manual: Static configuration (GPU hosts)
    """

    def __init__(
        self,
        discovery_mode: str,
        config: Dict[str, Any],
        health_check_interval: int = 10,
        health_check_timeout: int = 5,
        health_failure_threshold: int = 3
    ):
        """
        Initialize worker registry.

        Args:
            discovery_mode: "docker", "proxmox", or "manual"
            config: Mode-specific configuration
            health_check_interval: Seconds between health checks
            health_check_timeout: Timeout for health check requests
            health_failure_threshold: Failures before marking unhealthy
        """
        self._discovery_mode = discovery_mode
        self._config = config
        self._workers: Dict[str, WorkerEndpoint] = {}
        self._health_check_interval = health_check_interval
        self._health_check_timeout = health_check_timeout
        self._health_failure_threshold = health_failure_threshold
        self._last_selection: Dict[WorkerType, int] = {}  # For round-robin
        self._http_client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Start background tasks (discovery, health checks)."""
        self._http_client = httpx.AsyncClient(timeout=self._health_check_timeout)

        # Initial discovery
        await self.discover_workers()

        # Start background tasks
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._health_check_loop())

    async def stop(self):
        """Stop background tasks and cleanup."""
        if self._http_client:
            await self._http_client.aclose()

    # Discovery methods

    async def discover_workers(self):
        """Discover workers based on configured mode."""
        if self._discovery_mode == "docker":
            await self._discover_docker_workers()
        elif self._discovery_mode == "proxmox":
            await self._discover_proxmox_workers()
        elif self._discovery_mode == "manual":
            await self._discover_manual_workers()
        else:
            raise ValueError(f"Unknown discovery mode: {self._discovery_mode}")

    async def _discover_docker_workers(self):
        """Discover workers via Docker API or DNS."""
        # Implementation varies based on approach (see Docker Compose Setup)
        pass

    async def _discover_proxmox_workers(self):
        """Discover workers via Proxmox API."""
        # Implementation in Proxmox LXC Setup section
        pass

    async def _discover_manual_workers(self):
        """Load workers from static configuration."""
        # Used for GPU hosts
        pass

    # Worker selection

    def get_available_workers(
        self,
        worker_type: WorkerType,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> List[WorkerEndpoint]:
        """
        Get all available workers matching criteria.

        Args:
            worker_type: Type of worker to find
            capabilities: Required capabilities (e.g., {"gpu": True})

        Returns:
            List of available workers, sorted by least recently used
        """
        workers = [
            w for w in self._workers.values()
            if w.worker_type == worker_type
            and w.status == WorkerStatus.AVAILABLE
        ]

        # Filter by capabilities
        if capabilities:
            workers = [
                w for w in workers
                if all(w.capabilities.get(k) == v for k, v in capabilities.items())
            ]

        # Sort by last selection (least recently used first)
        workers.sort(key=lambda w: w.metadata.get("last_selected", 0))

        return workers

    def select_worker(
        self,
        worker_type: WorkerType,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> Optional[WorkerEndpoint]:
        """
        Select a worker using round-robin algorithm.

        Returns None if no workers available.
        """
        workers = self.get_available_workers(worker_type, capabilities)

        if not workers:
            return None

        # Round-robin: select first (least recently used)
        worker = workers[0]

        # Mark selection time for future round-robin
        worker.metadata["last_selected"] = datetime.utcnow().timestamp()

        return worker

    # Worker state management

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

    def mark_unhealthy(self, worker_id: str):
        """Mark worker as unhealthy."""
        if worker_id in self._workers:
            self._workers[worker_id].status = WorkerStatus.UNHEALTHY

    # Health checking

    async def health_check_worker(self, worker_id: str) -> bool:
        """
        Perform health check on worker.

        Returns True if healthy, False otherwise.
        """
        if worker_id not in self._workers:
            return False

        worker = self._workers[worker_id]

        try:
            response = await self._http_client.get(
                f"{worker.endpoint_url}/health",
                timeout=self._health_check_timeout
            )

            if response.status_code == 200:
                # Parse response to get worker status
                data = response.json()
                worker_status = data.get("worker_status", "idle")

                # Update worker status
                if worker_status == "busy":
                    worker.status = WorkerStatus.BUSY
                    worker.current_operation_id = data.get("current_operation")
                elif worker_status == "idle":
                    worker.status = WorkerStatus.AVAILABLE
                    worker.current_operation_id = None

                # Reset failure counter
                worker.health_check_failures = 0
                worker.last_health_check = datetime.utcnow()

                return True
            else:
                worker.health_check_failures += 1

        except Exception as e:
            worker.health_check_failures += 1

        # Mark unhealthy if threshold exceeded
        if worker.health_check_failures >= self._health_failure_threshold:
            worker.status = WorkerStatus.UNHEALTHY

        return False

    async def _health_check_loop(self):
        """Background task to check worker health."""
        while True:
            try:
                # Check all workers
                for worker_id in list(self._workers.keys()):
                    await self.health_check_worker(worker_id)

                await asyncio.sleep(self._health_check_interval)

            except Exception as e:
                # Log error but keep running
                await asyncio.sleep(self._health_check_interval)

    async def _discovery_loop(self):
        """Background task to rediscover workers."""
        # Run discovery every 30 seconds (workers may be added/removed)
        while True:
            await asyncio.sleep(30)
            try:
                await self.discover_workers()
            except Exception as e:
                # Log error but keep running
                pass

    # Utility methods

    def get_worker(self, worker_id: str) -> Optional[WorkerEndpoint]:
        """Get worker by ID."""
        return self._workers.get(worker_id)

    def list_workers(
        self,
        worker_type: Optional[WorkerType] = None,
        status: Optional[WorkerStatus] = None
    ) -> List[WorkerEndpoint]:
        """List all workers, optionally filtered."""
        workers = list(self._workers.values())

        if worker_type:
            workers = [w for w in workers if w.worker_type == worker_type]

        if status:
            workers = [w for w in workers if w.status == status]

        return workers
```

---

## Service Orchestrator Enhancements

**Location**: `ktrdr/async_infrastructure/service_orchestrator.py`

**New Abstract Methods**:

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Dict, Any
from ktrdr.api.services.worker_registry import WorkerRegistry, WorkerEndpoint

T = TypeVar('T')

class ServiceOrchestrator(ABC, Generic[T]):
    """
    Base class for service orchestrators with worker registry support.

    Existing methods preserved, new methods added for worker-based dispatch.
    """

    def __init__(
        self,
        operations_service: OperationsService,
        worker_registry: Optional[WorkerRegistry] = None  # NEW
    ):
        self.operations_service = operations_service
        self.worker_registry = worker_registry

    # NEW: Worker selection (service-specific)

    @abstractmethod
    def _select_worker(
        self,
        operation_context: Any
    ) -> Optional[WorkerEndpoint]:
        """
        Select optimal worker for operation.

        Implementation varies by service:
        - TrainingService: Priority GPU hosts, fallback CPU workers
        - BacktestingService: Any available backtest worker

        Returns None if no workers available.
        """
        pass

    @abstractmethod
    def _get_required_capabilities(
        self,
        operation_context: Any
    ) -> Dict[str, Any]:
        """
        Return required worker capabilities for operation.

        Examples:
        - {"gpu": True, "min_memory_gb": 16}
        - {} (no special requirements)
        """
        pass

    # NEW: Worker dispatch

    async def _dispatch_to_worker(
        self,
        worker: WorkerEndpoint,
        operation_context: Any,
        max_retries: int = 3
    ) -> str:
        """
        Dispatch operation to worker with retry logic.

        Args:
            worker: Selected worker endpoint
            operation_context: Operation-specific context
            max_retries: Max retry attempts

        Returns:
            Remote operation ID

        Raises:
            NoWorkersAvailableError: All workers busy/unavailable
            WorkerDispatchError: Failed to dispatch after retries
        """
        pass

    # ENHANCED: Start managed operation with worker dispatch

    async def start_managed_operation(
        self,
        operation_func: Callable,
        operation_context: Any,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Enhanced flow with worker selection and dispatch.

        1. Create operation record
        2. Select worker
        3. Dispatch to worker
        4. Register proxy for progress tracking
        5. Return operation_id
        """
        # 1. Create operation
        operation_id = await self.operations_service.create_operation(
            operation_type=self._get_operation_type(),
            metadata=self._build_metadata(operation_context)
        )

        try:
            # 2. Select worker
            worker = self._select_worker(operation_context)

            if not worker:
                await self.operations_service.fail_operation(
                    operation_id,
                    error="No workers available"
                )
                raise NoWorkersAvailableError(
                    f"No {self._get_operation_type()} workers available"
                )

            # 3. Dispatch to worker
            remote_operation_id = await self._dispatch_to_worker(
                worker,
                operation_context
            )

            # 4. Register proxy
            proxy = OperationServiceProxy(base_url=worker.endpoint_url)
            await self.operations_service.register_remote_proxy(
                backend_operation_id=operation_id,
                proxy=proxy,
                host_operation_id=remote_operation_id
            )

            # 5. Mark worker busy
            if self.worker_registry:
                self.worker_registry.mark_busy(worker.worker_id, operation_id)

            return {
                "operation_id": operation_id,
                "worker_id": worker.worker_id,
                "worker_url": worker.endpoint_url
            }

        except Exception as e:
            await self.operations_service.fail_operation(
                operation_id,
                error=str(e)
            )
            raise
```

**Training Service Implementation**:

```python
# ktrdr/api/services/training_service.py

class TrainingService(ServiceOrchestrator):
    """Training service with hybrid GPU/CPU routing."""

    def _select_worker(
        self,
        operation_context: TrainingOperationContext
    ) -> Optional[WorkerEndpoint]:
        """
        Priority-based worker selection.

        1. Check if GPU required/preferred
        2. Try GPU hosts (high priority)
        3. Fallback to CPU workers
        4. Return None if no workers available
        """
        requires_gpu = operation_context.training_config.get("force_gpu", False)
        prefers_gpu = operation_context.training_config.get("prefer_gpu", True)

        # PRIORITY 1: GPU hosts
        if requires_gpu or prefers_gpu:
            gpu_workers = self.worker_registry.get_available_workers(
                worker_type=WorkerType.GPU_HOST,
                capabilities={"gpu": True}
            )

            if gpu_workers:
                # Select GPU host (round-robin)
                return gpu_workers[0]

            elif requires_gpu:
                # GPU required but none available → fail
                raise NoGPUWorkersAvailableError(
                    "GPU training requested but no GPU workers available"
                )

        # PRIORITY 2: CPU training workers
        cpu_workers = self.worker_registry.get_available_workers(
            worker_type=WorkerType.CPU_TRAINING
        )

        if cpu_workers:
            return cpu_workers[0]

        # No workers available
        return None

    def _get_required_capabilities(
        self,
        operation_context: TrainingOperationContext
    ) -> Dict[str, Any]:
        """Return required capabilities for training."""
        return {
            "gpu": operation_context.training_config.get("force_gpu", False),
            "min_memory_gb": 8
        }
```

**Backtesting Service Implementation**:

```python
# ktrdr/api/services/backtesting_service.py

class BacktestingService(ServiceOrchestrator):
    """Backtesting service with simple worker selection."""

    def _select_worker(
        self,
        operation_context: BacktestOperationContext
    ) -> Optional[WorkerEndpoint]:
        """
        Simple worker selection for backtesting.

        Returns any available backtest worker.
        """
        workers = self.worker_registry.get_available_workers(
            worker_type=WorkerType.BACKTESTING
        )

        if not workers:
            return None

        # Round-robin selection
        return workers[0]

    def _get_required_capabilities(
        self,
        operation_context: BacktestOperationContext
    ) -> Dict[str, Any]:
        """Backtesting has no special requirements."""
        return {}
```

---

## Worker API Specifications

### Training Worker API

**Location**: `ktrdr/training/training_worker_api.py` (NEW)

**Purpose**: FastAPI service for CPU training workers

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import asyncio
from datetime import datetime

app = FastAPI(title="KTRDR Training Worker")

# Worker state
worker_state = {
    "status": "idle",  # idle | busy | error
    "current_operation_id": None,
    "worker_id": os.getenv("WORKER_ID", "unknown"),
    "started_at": datetime.utcnow().isoformat(),
    "capabilities": {
        "gpu": False,
        "worker_type": "cpu_training",
        "cores": os.cpu_count(),
        "memory_gb": 8  # Estimate
    }
}

# Request/Response models

class TrainingStartRequest(BaseModel):
    """Request to start training operation."""
    strategy_name: str
    symbols: list[str]
    timeframes: list[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    training_config: dict = {}

class TrainingStartResponse(BaseModel):
    """Response from training start."""
    operation_id: str
    worker_id: str
    status: str
    message: str

# Endpoints

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "worker_status": worker_state["status"],
        "current_operation": worker_state["current_operation_id"],
        "worker_id": worker_state["worker_id"],
        "capabilities": worker_state["capabilities"],
        "uptime_seconds": (
            datetime.utcnow() - datetime.fromisoformat(worker_state["started_at"])
        ).total_seconds()
    }

@app.post("/training/start", response_model=TrainingStartResponse)
async def start_training(
    request: TrainingStartRequest,
    background_tasks: BackgroundTasks
):
    """
    Start training operation.

    Rejects if worker is already busy.
    """
    # Check if busy
    if worker_state["status"] == "busy":
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Worker busy",
                "current_operation": worker_state["current_operation_id"]
            }
        )

    # Generate operation ID
    operation_id = str(uuid.uuid4())

    # Mark busy
    worker_state["status"] = "busy"
    worker_state["current_operation_id"] = operation_id

    # Start training in background
    background_tasks.add_task(
        run_training_operation,
        operation_id=operation_id,
        request=request
    )

    return TrainingStartResponse(
        operation_id=operation_id,
        worker_id=worker_state["worker_id"],
        status="started",
        message=f"Training started for {request.symbols}"
    )

async def run_training_operation(
    operation_id: str,
    request: TrainingStartRequest
):
    """
    Background task to run training.

    Uses existing TrainingService infrastructure.
    """
    from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator
    from ktrdr.api.services.operations_service import get_operations_service

    operations_service = get_operations_service()

    try:
        # Register operation with local OperationsService
        await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata={"symbols": request.symbols, "timeframes": request.timeframes}
        )

        # Run training (same as backend local mode)
        orchestrator = LocalTrainingOrchestrator(
            operation_id=operation_id,
            # ... pass request parameters
        )

        result = await orchestrator.run()

        # Mark operation complete
        await operations_service.complete_operation(
            operation_id,
            result=result
        )

        # Mark worker idle
        worker_state["status"] = "idle"
        worker_state["current_operation_id"] = None

    except Exception as e:
        # Mark operation failed
        await operations_service.fail_operation(
            operation_id,
            error=str(e)
        )

        # Mark worker error (will return to idle on next operation)
        worker_state["status"] = "error"
        worker_state["error"] = str(e)
```

### Backtest Worker API Enhancement

**Location**: `ktrdr/backtesting/remote_api.py` (ENHANCE EXISTING)

**Add worker state tracking**:

```python
# Add at module level (after imports)

worker_state = {
    "status": "idle",
    "current_operation_id": None,
    "worker_id": os.getenv("WORKER_ID", "unknown"),
    "started_at": datetime.utcnow().isoformat()
}

# Enhance health endpoint
@app.get("/health")
async def health():
    """Enhanced health check with worker status."""
    return {
        "status": "healthy",
        "worker_status": worker_state["status"],
        "current_operation": worker_state["current_operation_id"],
        "worker_id": worker_state["worker_id"],
        "uptime_seconds": (
            datetime.utcnow() - datetime.fromisoformat(worker_state["started_at"])
        ).total_seconds()
    }

# Enhance start endpoint
@app.post("/backtests/start")
async def start_backtest(request: BacktestStartRequest):
    """Enhanced with busy rejection."""

    # Check if busy
    if worker_state["status"] == "busy":
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Worker busy",
                "current_operation": worker_state["current_operation_id"]
            }
        )

    # Generate operation ID
    operation_id = str(uuid.uuid4())

    # Mark busy
    worker_state["status"] = "busy"
    worker_state["current_operation_id"] = operation_id

    # ... existing logic to start backtest ...

    # On completion (in background task):
    # worker_state["status"] = "idle"
    # worker_state["current_operation_id"] = None
```

---

## Configuration Management

### Configuration Files

**Development** (`config/workers.dev.yaml`):

```yaml
# Worker discovery configuration for development (Mac)

discovery_mode: docker

docker:
  # Use Docker service names (simplest)
  use_service_names: true

  services:
    - name: backtest-worker
      port: 5003
      type: backtesting

    - name: training-worker
      port: 5004
      type: training

# No GPU hosts in development
gpu_hosts: []

# Health check configuration
health_check:
  interval_seconds: 10
  timeout_seconds: 5
  failure_threshold: 3
```

**Production** (`config/workers.prod.yaml`):

```yaml
# Worker discovery configuration for production (Proxmox)

discovery_mode: proxmox

proxmox:
  api_url: "https://proxmox.local:8006"
  user: "ktrdr@pve"
  token_name: "worker-discovery"
  token_value: "${PROXMOX_TOKEN}"  # From environment variable
  verify_ssl: false

  # Tags to identify workers
  worker_tags:
    backtest: "ktrdr-backtest-worker"
    training: "ktrdr-training-worker"

# GPU hosts (manual configuration)
gpu_hosts:
  - id: "gpu-host-1"
    url: "http://192.168.1.100:5002"
    capabilities:
      gpu: true
      gpu_type: "CUDA"
      gpu_memory_gb: 24
      device_name: "NVIDIA RTX 4090"

  - id: "gpu-host-2"
    url: "http://192.168.1.101:5002"
    capabilities:
      gpu: true
      gpu_type: "CUDA"
      gpu_memory_gb: 16
      device_name: "NVIDIA RTX 3080"

# Health check configuration
health_check:
  interval_seconds: 10
  timeout_seconds: 5
  failure_threshold: 3
```

### Configuration Loading

**Location**: `ktrdr/api/services/worker_config.py` (NEW)

```python
import os
import yaml
from typing import Dict, Any

def load_worker_config() -> Dict[str, Any]:
    """
    Load worker configuration based on environment.

    Defaults to dev config, can override with WORKER_CONFIG env var.
    """
    config_file = os.getenv(
        "WORKER_CONFIG",
        "config/workers.dev.yaml"
    )

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Substitute environment variables
    config = _substitute_env_vars(config)

    return config

def _substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively substitute ${VAR} with environment variables."""
    if isinstance(config, dict):
        return {k: _substitute_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_substitute_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        var_name = config[2:-1]
        return os.getenv(var_name, config)
    else:
        return config
```

---

## Docker Compose Setup

### Development Environment

**File**: `docker/docker-compose.dev.yml`

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ..
      dockerfile: docker/backend/Dockerfile.dev
    image: ktrdr-backend:dev
    container_name: ktrdr-backend
    ports:
      - "8000:8000"
    volumes:
      - ../ktrdr:/app/ktrdr
      - ../data:/app/data
      - ../models:/app/models
      - ../strategies:/app/strategies
      - ../config:/app/config
      - ../logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - WORKER_CONFIG=/app/config/workers.dev.yaml
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - ktrdr-network
    depends_on:
      - training-worker
      - backtest-worker

  training-worker:
    image: ktrdr-backend:dev
    command: ["uvicorn", "ktrdr.training.training_worker_api:app", "--host", "0.0.0.0", "--port", "5004", "--reload"]
    expose:
      - "5004"
    volumes:
      - ../ktrdr:/app/ktrdr
      - ../data:/app/data:ro
      - ../models:/app/models
      - ../strategies:/app/strategies:ro
      - ../config:/app/config:ro
      - ../logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - WORKER_TYPE=training
      - WORKER_ID=${HOSTNAME}
      - USE_TRAINING_HOST_SERVICE=false
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
      - LOG_LEVEL=INFO
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - ktrdr-network
    labels:
      - "ktrdr.worker.type=training"

  backtest-worker:
    image: ktrdr-backend:dev
    command: ["uvicorn", "ktrdr.backtesting.remote_api:app", "--host", "0.0.0.0", "--port", "5003", "--reload"]
    expose:
      - "5003"
    volumes:
      - ../ktrdr:/app/ktrdr
      - ../data:/app/data:ro
      - ../models:/app/models:ro
      - ../strategies:/app/strategies:ro
      - ../config:/app/config:ro
      - ../logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - WORKER_TYPE=backtesting
      - WORKER_ID=${HOSTNAME}
      - USE_REMOTE_BACKTEST_SERVICE=false
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
      - LOG_LEVEL=INFO
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - ktrdr-network
    labels:
      - "ktrdr.worker.type=backtesting"

networks:
  ktrdr-network:
    driver: bridge
```

### Docker Discovery Implementation

**Location**: `ktrdr/api/services/worker_registry.py`

```python
async def _discover_docker_workers(self):
    """
    Discover workers via Docker service names (simple approach).

    Uses Docker Compose service DNS resolution.
    """
    services = self._config.get("docker", {}).get("services", [])

    for service in services:
        service_name = service["name"]
        port = service["port"]
        worker_type_str = service["type"]

        # Map to WorkerType enum
        if worker_type_str == "backtesting":
            worker_type = WorkerType.BACKTESTING
        elif worker_type_str == "training":
            worker_type = WorkerType.CPU_TRAINING
        else:
            continue

        # Create worker endpoint using service name
        # Docker Compose creates DNS entry for service name
        worker_id = f"docker-service-{service_name}"

        self._workers[worker_id] = WorkerEndpoint(
            worker_id=worker_id,
            worker_type=worker_type,
            endpoint_url=f"http://{service_name}:{port}",
            status=WorkerStatus.UNKNOWN,
            current_operation_id=None,
            capabilities={},
            last_health_check=datetime.utcnow(),
            health_check_failures=0,
            metadata={"service_name": service_name}
        )
```

### Scaling Workers

```bash
# Start dev environment
docker-compose -f docker/docker-compose.dev.yml up -d

# Scale backtest workers
docker-compose -f docker/docker-compose.dev.yml up -d --scale backtest-worker=3

# Scale training workers
docker-compose -f docker/docker-compose.dev.yml up -d --scale training-worker=2

# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f backtest-worker

# Stop
docker-compose -f docker/docker-compose.dev.yml down
```

---

## Proxmox LXC Setup

### LXC Template Creation

**Script**: `scripts/create-lxc-template.sh`

```bash
#!/bin/bash
# Create LXC template for KTRDR workers

set -e

TEMPLATE_ID=200
PROXMOX_NODE="pve"  # Your Proxmox node name
STORAGE="local-lvm"
TEMPLATE_NAME="ktrdr-worker-template"

echo "Creating LXC template ${TEMPLATE_ID}..."

# Create container from Ubuntu template
pct create ${TEMPLATE_ID} local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname ${TEMPLATE_NAME} \
  --memory 2048 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --storage ${STORAGE} \
  --rootfs ${STORAGE}:8 \
  --unprivileged 1 \
  --features nesting=1

echo "Starting container for configuration..."
pct start ${TEMPLATE_ID}

# Wait for container to boot
sleep 10

echo "Installing dependencies..."
pct exec ${TEMPLATE_ID} -- bash -c '
  apt update
  apt install -y python3.11 python3-pip git curl wget

  # Install uv
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Clone KTRDR repo
  mkdir -p /opt
  cd /opt
  git clone https://github.com/yourusername/ktrdr.git
  cd ktrdr

  # Install dependencies
  /root/.cargo/bin/uv sync

  # Create systemd service template
  cat > /etc/systemd/system/ktrdr-worker@.service <<EOF
[Unit]
Description=KTRDR Worker (%i)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ktrdr
Environment="PYTHONPATH=/opt/ktrdr"
Environment="WORKER_ID=%H"
ExecStart=/root/.cargo/bin/uv run uvicorn ktrdr.%i.remote_api:app --host 0.0.0.0 --port %p
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
'

echo "Stopping container..."
pct stop ${TEMPLATE_ID}

echo "Converting to template..."
pct template ${TEMPLATE_ID}

echo "Template created successfully!"
echo "Template ID: ${TEMPLATE_ID}"
echo "Next: Clone this template to create workers"
```

### Worker Deployment Script

**Script**: `scripts/deploy-lxc-workers.sh`

```bash
#!/bin/bash
# Deploy LXC workers from template

set -e

TEMPLATE_ID=200
PROXMOX_NODE="pve"

# Deploy backtest workers
echo "Deploying backtest workers..."
for i in {1..5}; do
  VMID=$((300 + i))
  IP="192.168.1.$((200 + i))"
  HOSTNAME="ktrdr-backtest-worker-${i}"

  echo "Creating ${HOSTNAME} (${VMID})..."

  # Clone from template
  pct clone ${TEMPLATE_ID} ${VMID} \
    --hostname ${HOSTNAME} \
    --description "KTRDR Backtest Worker ${i}"

  # Set static IP
  pct set ${VMID} --net0 name=eth0,bridge=vmbr0,ip=${IP}/24,gw=192.168.1.1

  # Add tag for discovery
  pct set ${VMID} --tags ktrdr-backtest-worker

  # Start container
  pct start ${VMID}

  # Wait for boot
  sleep 5

  # Start worker service
  pct exec ${VMID} -- bash -c '
    cd /opt/ktrdr
    git pull
    systemctl enable ktrdr-worker@backtesting.service
    systemctl start ktrdr-worker@backtesting.service
  '

  echo "✓ ${HOSTNAME} deployed and started"
done

# Deploy training workers
echo "Deploying training workers..."
for i in {1..3}; do
  VMID=$((400 + i))
  IP="192.168.1.$((210 + i))"
  HOSTNAME="ktrdr-training-worker-${i}"

  echo "Creating ${HOSTNAME} (${VMID})..."

  pct clone ${TEMPLATE_ID} ${VMID} \
    --hostname ${HOSTNAME} \
    --description "KTRDR Training Worker ${i}"

  pct set ${VMID} --net0 name=eth0,bridge=vmbr0,ip=${IP}/24,gw=192.168.1.1
  pct set ${VMID} --tags ktrdr-training-worker

  pct start ${VMID}
  sleep 5

  pct exec ${VMID} -- bash -c '
    cd /opt/ktrdr
    git pull
    systemctl enable ktrdr-worker@training.service
    systemctl start ktrdr-worker@training.service
  '

  echo "✓ ${HOSTNAME} deployed and started"
done

echo ""
echo "Deployment complete!"
echo "Backtest workers: 301-305"
echo "Training workers: 401-403"
```

### Proxmox Discovery Implementation

**Location**: `ktrdr/api/services/worker_registry.py`

```python
async def _discover_proxmox_workers(self):
    """
    Discover workers via Proxmox API.

    Finds LXC containers with specific tags.
    """
    from proxmoxer import ProxmoxAPI

    proxmox_config = self._config.get("proxmox", {})

    # Initialize Proxmox API client
    proxmox = ProxmoxAPI(
        proxmox_config["api_url"].replace("https://", "").replace(":8006", ""),
        user=proxmox_config["user"],
        token_name=proxmox_config["token_name"],
        token_value=proxmox_config["token_value"],
        verify_ssl=proxmox_config.get("verify_ssl", False)
    )

    worker_tags = proxmox_config.get("worker_tags", {})
    backtest_tag = worker_tags.get("backtest", "ktrdr-backtest-worker")
    training_tag = worker_tags.get("training", "ktrdr-training-worker")

    # Iterate through all Proxmox nodes
    for node in proxmox.nodes.get():
        node_name = node['node']

        # Get all LXC containers on this node
        try:
            containers = proxmox.nodes(node_name).lxc.get()
        except Exception as e:
            continue

        for container in containers:
            vmid = container['vmid']
            status = container.get('status', 'unknown')

            # Skip if not running
            if status != 'running':
                continue

            # Get container config
            try:
                config = proxmox.nodes(node_name).lxc(vmid).config.get()
            except Exception as e:
                continue

            # Parse tags
            tags = config.get('tags', '').split(',')
            tags = [t.strip() for t in tags]

            # Determine worker type
            worker_type = None
            port = None

            if backtest_tag in tags:
                worker_type = WorkerType.BACKTESTING
                port = 5003
            elif training_tag in tags:
                worker_type = WorkerType.CPU_TRAINING
                port = 5004
            else:
                continue  # Not a KTRDR worker

            # Parse IP address from net0
            net0 = config.get('net0', '')
            # Format: "name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1"
            ip_match = re.search(r'ip=(\d+\.\d+\.\d+\.\d+)', net0)

            if not ip_match:
                continue

            ip_address = ip_match.group(1)

            # Register worker
            worker_id = f"lxc-{node_name}-{vmid}"
            hostname = config.get('hostname', f"ct-{vmid}")

            self._workers[worker_id] = WorkerEndpoint(
                worker_id=worker_id,
                worker_type=worker_type,
                endpoint_url=f"http://{ip_address}:{port}",
                status=WorkerStatus.UNKNOWN,
                current_operation_id=None,
                capabilities={
                    "cores": config.get('cores', 2),
                    "memory_gb": config.get('memory', 2048) / 1024
                },
                last_health_check=datetime.utcnow(),
                health_check_failures=0,
                metadata={
                    "vmid": vmid,
                    "node": node_name,
                    "hostname": hostname,
                    "ip": ip_address
                }
            )
```

---

## Testing Specifications

### Unit Tests

**Location**: `tests/unit/api/services/test_worker_registry.py`

```python
import pytest
from ktrdr.api.services.worker_registry import (
    WorkerRegistry,
    WorkerType,
    WorkerStatus,
    WorkerEndpoint
)

@pytest.fixture
def worker_registry():
    """Create worker registry with manual mode."""
    config = {
        "manual": {
            "workers": []
        }
    }
    return WorkerRegistry(discovery_mode="manual", config=config)

def test_register_worker(worker_registry):
    """Test manual worker registration."""
    worker = WorkerEndpoint(
        worker_id="test-worker-1",
        worker_type=WorkerType.BACKTESTING,
        endpoint_url="http://localhost:5003",
        status=WorkerStatus.AVAILABLE,
        current_operation_id=None,
        capabilities={},
        last_health_check=datetime.utcnow(),
        health_check_failures=0,
        metadata={}
    )

    worker_registry._workers[worker.worker_id] = worker

    assert len(worker_registry.list_workers()) == 1
    assert worker_registry.get_worker("test-worker-1") == worker

def test_select_worker_round_robin(worker_registry):
    """Test round-robin worker selection."""
    # Register 3 workers
    for i in range(3):
        worker = WorkerEndpoint(
            worker_id=f"worker-{i}",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url=f"http://localhost:500{i}",
            status=WorkerStatus.AVAILABLE,
            current_operation_id=None,
            capabilities={},
            last_health_check=datetime.utcnow(),
            health_check_failures=0,
            metadata={"last_selected": 0}
        )
        worker_registry._workers[worker.worker_id] = worker

    # Select workers (should round-robin)
    selected = []
    for _ in range(6):
        worker = worker_registry.select_worker(WorkerType.BACKTESTING)
        selected.append(worker.worker_id)

    # Should cycle through all workers
    assert selected == ["worker-0", "worker-1", "worker-2", "worker-0", "worker-1", "worker-2"]

def test_mark_busy(worker_registry):
    """Test marking worker as busy."""
    worker = WorkerEndpoint(
        worker_id="test-worker",
        worker_type=WorkerType.BACKTESTING,
        endpoint_url="http://localhost:5003",
        status=WorkerStatus.AVAILABLE,
        current_operation_id=None,
        capabilities={},
        last_health_check=datetime.utcnow(),
        health_check_failures=0,
        metadata={}
    )
    worker_registry._workers[worker.worker_id] = worker

    # Mark busy
    worker_registry.mark_busy("test-worker", "op-123")

    # Verify
    worker = worker_registry.get_worker("test-worker")
    assert worker.status == WorkerStatus.BUSY
    assert worker.current_operation_id == "op-123"

    # Should not be in available list
    available = worker_registry.get_available_workers(WorkerType.BACKTESTING)
    assert len(available) == 0
```

### Integration Tests

**Location**: `tests/integration/distributed/test_worker_dispatch.py`

```python
import pytest
from httpx import AsyncClient
from ktrdr.api.main import app

@pytest.mark.asyncio
async def test_backtest_dispatch_to_docker_worker():
    """Test backtesting operation dispatched to Docker worker."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Start backtest
        response = await client.post("/api/v1/backtests/start", json={
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30"
        })

        assert response.status_code == 200
        data = response.json()

        operation_id = data["operation_id"]
        assert operation_id is not None

        # Poll for completion
        for _ in range(30):  # 30 seconds max
            response = await client.get(f"/api/v1/operations/{operation_id}")
            data = response.json()

            if data["status"] == "completed":
                break

            await asyncio.sleep(1)

        assert data["status"] == "completed"
        assert "total_return" in data["results"]

@pytest.mark.asyncio
async def test_training_dispatch_cpu_worker():
    """Test CPU training dispatched to training worker."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/trainings/start", json={
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
            "strategy_name": "test_strategy",
            "force_gpu": False  # Force CPU
        })

        assert response.status_code == 200
        data = response.json()

        operation_id = data["operation_id"]

        # Verify routed to CPU worker (not GPU host)
        # Check via worker_id or logs
```

---

**Document End**

This architecture document provides all technical implementation details needed to build the distributed system. Refer to DESIGN.md for high-level design rationale and patterns.
