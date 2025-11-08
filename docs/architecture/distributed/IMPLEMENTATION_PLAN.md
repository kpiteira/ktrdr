# Distributed Training & Backtesting Implementation Plan

**Version**: 2.0 - Vertical Slices
**Status**: Ready for Implementation
**Date**: 2025-11-08

---

## Overview

This implementation plan uses **Test-Driven Development** with **vertical slices**. Each phase delivers a complete, testable feature.

**Quality Gates** (every task):
- Write tests FIRST (TDD)
- Pass ALL unit tests: `make test-unit`
- Pass quality checks: `make quality`
- Result in ONE commit

**Vertical Approach**: Each phase ends with a working, testable system feature.

All work will be done on a single feature branch: `claude/containerize-training-service-*`

---

## Phase Structure

- **Phase**: A complete **vertical slice** delivering end-to-end functionality
- **Task**: A single, testable unit of work building toward the phase goal
- **Key**: Each phase ends with something you can **actually test and use**

---

## Phase 1: Single Backtesting Worker End-to-End

**Goal**: Get ONE backtesting worker running in Docker, accepting operations, completing them

**Why This First**: Establishes the complete vertical stack with minimal infrastructure. We can test it works!

**End State**:
- Docker Compose with backend + 1 backtest worker
- Worker self-registers on startup
- Can submit a backtest → worker executes it → returns results
- **TESTABLE**: Run `docker-compose up`, submit backtest via API, see it complete

---

### Task 1.1: Docker Compose Foundation

**Objective**: Get basic Docker Compose environment working with backend + 1 backtest worker

**TDD Approach**:
- Manual testing (Docker Compose itself)
- Validation: Backend starts, worker starts, both accessible

**Implementation**:
1. Create `docker/docker-compose.dev.yml`:
   ```yaml
   version: "3.8"

   services:
     backend:
       build:
         context: ..
         dockerfile: docker/backend/Dockerfile
       ports:
         - "8000:8000"
       environment:
         - PYTHONPATH=/app
         - LOG_LEVEL=INFO
       networks:
         - ktrdr-network

     backtest-worker:
       build:
         context: ..
         dockerfile: docker/backend/Dockerfile
       command: ["uv", "run", "uvicorn", "ktrdr.backtesting.remote_api:app", "--host", "0.0.0.0", "--port", "5003"]
       environment:
         - PYTHONPATH=/app
         - BACKEND_URL=http://backend:8000
         - WORKER_TYPE=backtesting
         - LOG_LEVEL=INFO
       networks:
         - ktrdr-network

   networks:
     ktrdr-network:
       driver: bridge
   ```

2. Test:
   ```bash
   docker-compose -f docker/docker-compose.dev.yml up -d
   curl http://localhost:8000/health  # Backend should respond
   docker-compose -f docker/docker-compose.dev.yml logs backtest-worker  # Should see startup
   docker-compose -f docker/docker-compose.dev.yml down
   ```

**Quality Gate**:
```bash
# Manual verification
docker-compose -f docker/docker-compose.dev.yml up -d
docker-compose -f docker/docker-compose.dev.yml ps  # Both running
docker-compose -f docker/docker-compose.dev.yml down

make test-unit  # All existing tests still pass
make quality
```

**Commit**: `feat(docker): add Docker Compose dev environment with backend + backtest worker`

**Estimated Time**: 1 hour

---

### Task 1.2: Worker Data Models

**Objective**: Define minimal data models needed for worker registration

**TDD Approach**:
1. Create `tests/unit/api/models/test_workers.py`
2. Write tests for:
   - `WorkerType` enum (BACKTESTING, CPU_TRAINING, GPU_HOST)
   - `WorkerStatus` enum (AVAILABLE, BUSY, TEMPORARILY_UNAVAILABLE)
   - `WorkerEndpoint` dataclass
   - to_dict() / from_dict() serialization

**Implementation**:
1. Create `ktrdr/api/models/workers.py`:
   ```python
   from enum import Enum
   from dataclasses import dataclass, asdict
   from datetime import datetime
   from typing import Dict, Any, Optional

   class WorkerType(str, Enum):
       BACKTESTING = "backtesting"
       CPU_TRAINING = "cpu_training"
       GPU_HOST = "gpu_host"

   class WorkerStatus(str, Enum):
       AVAILABLE = "available"
       BUSY = "busy"
       TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"

   @dataclass
   class WorkerEndpoint:
       worker_id: str
       worker_type: WorkerType
       endpoint_url: str
       status: WorkerStatus
       current_operation_id: Optional[str] = None
       capabilities: Dict[str, Any] = None
       last_health_check: Optional[datetime] = None
       last_healthy_at: Optional[datetime] = None
       health_check_failures: int = 0
       metadata: Dict[str, Any] = None

       def __post_init__(self):
           if self.capabilities is None:
               self.capabilities = {}
           if self.metadata is None:
               self.metadata = {}

       def to_dict(self) -> Dict[str, Any]:
           data = asdict(self)
           data['worker_type'] = self.worker_type.value
           data['status'] = self.status.value
           if self.last_health_check:
               data['last_health_check'] = self.last_health_check.isoformat()
           if self.last_healthy_at:
               data['last_healthy_at'] = self.last_healthy_at.isoformat()
           return data
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add worker data models and types`

**Estimated Time**: 1 hour

---

### Task 1.3: Minimal WorkerRegistry

**Objective**: Create WorkerRegistry that can register and retrieve workers (no health checks yet)

**TDD Approach**:
1. Create `tests/unit/api/services/test_worker_registry.py`
2. Write tests for:
   - `register_worker()` - adds worker
   - `register_worker()` again - updates (idempotent)
   - `get_worker(worker_id)` - retrieves
   - `list_workers()` - lists all

**Implementation**:
1. Create `ktrdr/api/services/worker_registry.py`:
   ```python
   from typing import Dict, Optional, List
   from ktrdr.api.models.workers import WorkerEndpoint, WorkerType, WorkerStatus
   from datetime import datetime
   import logging

   logger = logging.getLogger(__name__)

   class WorkerRegistry:
       """Minimal worker registry - just registration and retrieval."""

       def __init__(self):
           self._workers: Dict[str, WorkerEndpoint] = {}

       def register_worker(
           self,
           worker_id: str,
           worker_type: WorkerType,
           endpoint_url: str,
           capabilities: Optional[Dict] = None
       ) -> WorkerEndpoint:
           """Register or update a worker (idempotent)."""
           if worker_id in self._workers:
               # Update existing
               worker = self._workers[worker_id]
               worker.endpoint_url = endpoint_url
               worker.capabilities = capabilities or {}
               worker.status = WorkerStatus.AVAILABLE
               logger.info(f"Worker {worker_id} re-registered")
           else:
               # Create new
               worker = WorkerEndpoint(
                   worker_id=worker_id,
                   worker_type=worker_type,
                   endpoint_url=endpoint_url,
                   status=WorkerStatus.AVAILABLE,
                   capabilities=capabilities or {},
                   last_healthy_at=datetime.utcnow()
               )
               self._workers[worker_id] = worker
               logger.info(f"Worker {worker_id} registered ({worker_type})")

           return worker

       def get_worker(self, worker_id: str) -> Optional[WorkerEndpoint]:
           """Get worker by ID."""
           return self._workers.get(worker_id)

       def list_workers(
           self,
           worker_type: Optional[WorkerType] = None,
           status: Optional[WorkerStatus] = None
       ) -> List[WorkerEndpoint]:
           """List workers with optional filters."""
           workers = list(self._workers.values())

           if worker_type:
               workers = [w for w in workers if w.worker_type == worker_type]
           if status:
               workers = [w for w in workers if w.status == status]

           return workers
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add minimal WorkerRegistry for registration and retrieval`

**Estimated Time**: 1.5 hours

---

### Task 1.4: Worker Registration API Endpoint

**Objective**: Add POST /workers/register endpoint

**TDD Approach**:
1. Create `tests/unit/api/endpoints/test_workers.py`
2. Write tests for successful registration, idempotency, validation

**Implementation**:
1. Create `ktrdr/api/endpoints/workers.py`:
   ```python
   from fastapi import APIRouter, Depends
   from pydantic import BaseModel
   from typing import Dict, Any, Optional
   from ktrdr.api.models.workers import WorkerType
   from ktrdr.api.services.worker_registry import WorkerRegistry

   router = APIRouter(prefix="/workers", tags=["workers"])

   # Singleton registry
   _worker_registry: Optional[WorkerRegistry] = None

   def get_worker_registry() -> WorkerRegistry:
       global _worker_registry
       if _worker_registry is None:
           _worker_registry = WorkerRegistry()
       return _worker_registry

   class WorkerRegistrationRequest(BaseModel):
       worker_id: str
       worker_type: WorkerType
       endpoint_url: str
       capabilities: Dict[str, Any] = {}

   class WorkerRegistrationResponse(BaseModel):
       worker_id: str
       worker_type: WorkerType
       status: str
       message: str

   @router.post("/register", response_model=WorkerRegistrationResponse)
   async def register_worker(
       request: WorkerRegistrationRequest,
       registry: WorkerRegistry = Depends(get_worker_registry)
   ):
       """Register a worker with the backend."""
       worker = registry.register_worker(
           worker_id=request.worker_id,
           worker_type=request.worker_type,
           endpoint_url=request.endpoint_url,
           capabilities=request.capabilities
       )

       return WorkerRegistrationResponse(
           worker_id=worker.worker_id,
           worker_type=worker.worker_type,
           status=worker.status.value,
           message=f"Worker {worker.worker_id} registered successfully"
       )

   @router.get("")
   async def list_workers(
       registry: WorkerRegistry = Depends(get_worker_registry)
   ):
       """List all registered workers."""
       workers = registry.list_workers()
       return {
           "total": len(workers),
           "workers": [w.to_dict() for w in workers]
       }
   ```

2. Add to `ktrdr/api/main.py`:
   ```python
   from ktrdr.api.endpoints import workers

   app.include_router(workers.router, prefix="/api/v1")
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add worker registration API endpoint`

**Estimated Time**: 1.5 hours

---

### Task 1.5: Worker Self-Registration on Startup

**Objective**: Make backtest worker call POST /workers/register when it starts

**TDD Approach**:
1. Create `tests/unit/backtesting/test_worker_registration.py`
2. Mock httpx to test registration logic

**Implementation**:
1. Modify `ktrdr/backtesting/remote_api.py`:
   ```python
   import os
   import httpx
   import asyncio
   import socket
   from fastapi import FastAPI

   app = FastAPI(title="KTRDR Backtest Worker")

   # Worker state
   WORKER_ID = os.getenv("WORKER_ID", socket.gethostname())
   BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
   WORKER_TYPE = "backtesting"

   worker_state = {
       "status": "idle",
       "current_operation_id": None
   }

   async def register_with_backend():
       """Register this worker with the backend."""
       registration_url = f"{BACKEND_URL}/api/v1/workers/register"

       payload = {
           "worker_id": WORKER_ID,
           "worker_type": WORKER_TYPE,
           "endpoint_url": f"http://{WORKER_ID}:5003",  # In Docker, use hostname
           "capabilities": {}
       }

       max_retries = 5
       for attempt in range(max_retries):
           try:
               async with httpx.AsyncClient(timeout=10.0) as client:
                   response = await client.post(registration_url, json=payload)
                   response.raise_for_status()
                   print(f"✓ Worker {WORKER_ID} registered with backend")
                   return
           except Exception as e:
               wait_time = 2 ** attempt  # Exponential backoff
               print(f"✗ Registration attempt {attempt+1}/{max_retries} failed: {e}")
               if attempt < max_retries - 1:
                   print(f"  Retrying in {wait_time}s...")
                   await asyncio.sleep(wait_time)

       print(f"✗ Failed to register after {max_retries} attempts")

   @app.on_event("startup")
   async def on_startup():
       """Startup event handler."""
       await register_with_backend()

   @app.get("/health")
   async def health():
       """Health check endpoint."""
       return {
           "status": "healthy",
           "worker_status": worker_state["status"],
           "current_operation": worker_state["current_operation_id"],
           "worker_id": WORKER_ID
       }

   # ... rest of existing backtest API code ...
   ```

**Quality Gate**:
```bash
make test-unit
make quality

# Manual Docker test
docker-compose -f docker/docker-compose.dev.yml up -d
sleep 5
curl http://localhost:8000/api/v1/workers  # Should see registered worker
docker-compose -f docker/docker-compose.dev.yml down
```

**Commit**: `feat(backtesting): add self-registration on worker startup`

**Estimated Time**: 1.5 hours

---

### Task 1.6: End-to-End Test - Single Backtest

**Objective**: Submit a backtest, verify worker executes it, returns results

**TDD Approach**:
1. Create `tests/e2e/test_single_backtest_worker.py`
2. Use Docker Compose test fixtures

**Implementation**:
1. Write E2E test that:
   - Starts Docker Compose (backend + 1 worker)
   - Waits for worker registration
   - Submits backtest via API
   - Polls for completion
   - Verifies results
   - Cleans up

**Quality Gate**:
```bash
make test-unit
make test-e2e  # This E2E test
make quality
```

**Commit**: `test(e2e): add end-to-end test for single backtest worker`

**Estimated Time**: 2 hours

---

**Phase 1 Checkpoint**:
✅ Docker Compose works with backend + 1 worker
✅ Worker self-registers on startup
✅ Can submit backtest → worker executes → completes
✅ **TESTABLE**: Real end-to-end workflow works!

**Total Phase 1 Time**: ~8.5 hours

---

## Phase 2: Multiple Workers + Health Monitoring

**Goal**: Scale to multiple workers, add health monitoring, test concurrent operations

**Why This Second**: Builds on working system, adds reliability and concurrency

**End State**:
- Can scale workers: `docker-compose up --scale backtest-worker=3`
- Health checks monitor worker status
- Round-robin load balancing
- Dead workers automatically removed
- **TESTABLE**: Run 5 concurrent backtests across 3 workers

---

### Task 2.1: Worker Selection (Round-Robin)

**Objective**: Add logic to select worker for dispatch

**TDD Approach**:
1. Add tests to `test_worker_registry.py`:
   - `select_worker(worker_type)` - returns least recently used
   - Round-robin behavior over multiple calls

**Implementation**:
1. Add to WorkerRegistry:
   ```python
   def get_available_workers(
       self,
       worker_type: WorkerType
   ) -> List[WorkerEndpoint]:
       """Get available workers of given type, sorted by last selection."""
       workers = [
           w for w in self._workers.values()
           if w.worker_type == worker_type
           and w.status == WorkerStatus.AVAILABLE
       ]

       # Sort by last_selected (least recently used first)
       workers.sort(key=lambda w: w.metadata.get("last_selected", 0))
       return workers

   def select_worker(self, worker_type: WorkerType) -> Optional[WorkerEndpoint]:
       """Select worker using round-robin."""
       workers = self.get_available_workers(worker_type)
       if not workers:
           return None

       worker = workers[0]
       worker.metadata["last_selected"] = datetime.utcnow().timestamp()
       return worker

   def mark_busy(self, worker_id: str, operation_id: str):
       """Mark worker as busy."""
       if worker_id in self._workers:
           self._workers[worker_id].status = WorkerStatus.BUSY
           self._workers[worker_id].current_operation_id = operation_id

   def mark_available(self, worker_id: str):
       """Mark worker as available."""
       if worker_id in self._workers:
           self._workers[worker_id].status = WorkerStatus.AVAILABLE
           self._workers[worker_id].current_operation_id = None
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add round-robin worker selection`

**Estimated Time**: 1.5 hours

---

### Task 2.2: Health Check Infrastructure

**Objective**: Add health checking without background task yet

**TDD Approach**:
1. Add tests for `health_check_worker(worker_id)`
2. Mock httpx calls

**Implementation**:
1. Add to WorkerRegistry:
   ```python
   async def health_check_worker(self, worker_id: str) -> bool:
       """Perform health check on a worker."""
       if worker_id not in self._workers:
           return False

       worker = self._workers[worker_id]

       try:
           async with httpx.AsyncClient(timeout=5.0) as client:
               response = await client.get(f"{worker.endpoint_url}/health")

               if response.status_code == 200:
                   data = response.json()

                   # Update status from health response
                   worker_status = data.get("worker_status", "idle")
                   if worker_status == "busy":
                       worker.status = WorkerStatus.BUSY
                       worker.current_operation_id = data.get("current_operation")
                   else:
                       worker.status = WorkerStatus.AVAILABLE
                       worker.current_operation_id = None

                   worker.health_check_failures = 0
                   worker.last_health_check = datetime.utcnow()
                   worker.last_healthy_at = datetime.utcnow()
                   return True

       except Exception as e:
           logger.warning(f"Health check failed for {worker_id}: {e}")

       worker.health_check_failures += 1
       worker.last_health_check = datetime.utcnow()

       if worker.health_check_failures >= 3:
           worker.status = WorkerStatus.TEMPORARILY_UNAVAILABLE

       return False
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add health check logic`

**Estimated Time**: 1.5 hours

---

### Task 2.3: Background Health Check Task

**Objective**: Start background task that continuously health checks workers

**TDD Approach**:
1. Test start() and stop() methods
2. Test background task runs checks

**Implementation**:
1. Add to WorkerRegistry:
   ```python
   def __init__(self):
       self._workers: Dict[str, WorkerEndpoint] = {}
       self._health_check_task: Optional[asyncio.Task] = None
       self._health_check_interval = 10  # seconds

   async def start(self):
       """Start background health check task."""
       if self._health_check_task is None:
           self._health_check_task = asyncio.create_task(self._health_check_loop())
           logger.info("Worker registry started")

   async def stop(self):
       """Stop background health check task."""
       if self._health_check_task:
           self._health_check_task.cancel()
           try:
               await self._health_check_task
           except asyncio.CancelledError:
               pass
           self._health_check_task = None
           logger.info("Worker registry stopped")

   async def _health_check_loop(self):
       """Background task to health check all workers."""
       while True:
           try:
               for worker_id in list(self._workers.keys()):
                   await self.health_check_worker(worker_id)
               await asyncio.sleep(self._health_check_interval)
           except asyncio.CancelledError:
               break
           except Exception as e:
               logger.error(f"Health check loop error: {e}")
               await asyncio.sleep(self._health_check_interval)
   ```

2. Integrate into API startup (modify `ktrdr/api/main.py`):
   ```python
   from ktrdr.api.endpoints.workers import get_worker_registry

   @app.on_event("startup")
   async def startup():
       registry = get_worker_registry()
       await registry.start()

   @app.on_event("shutdown")
   async def shutdown():
       registry = get_worker_registry()
       await registry.stop()
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add background health check task`

**Estimated Time**: 2 hours

---

### Task 2.4: Dead Worker Cleanup

**Objective**: Remove workers unavailable for > 5 minutes

**TDD Approach**:
1. Test cleanup logic with mocked timestamps

**Implementation**:
1. Add to WorkerRegistry:
   ```python
   def __init__(self):
       # ... existing init ...
       self._removal_threshold_seconds = 300  # 5 minutes

   def _cleanup_dead_workers(self):
       """Remove workers that have been unavailable for too long."""
       now = datetime.utcnow()
       to_remove = []

       for worker_id, worker in self._workers.items():
           if worker.status == WorkerStatus.TEMPORARILY_UNAVAILABLE:
               if worker.last_healthy_at:
                   time_unavailable = (now - worker.last_healthy_at).total_seconds()
                   if time_unavailable > self._removal_threshold_seconds:
                       to_remove.append(worker_id)

       for worker_id in to_remove:
           del self._workers[worker_id]
           logger.info(f"Removed dead worker: {worker_id}")

   async def _health_check_loop(self):
       """Background task with cleanup."""
       while True:
           try:
               for worker_id in list(self._workers.keys()):
                   await self.health_check_worker(worker_id)

               # Cleanup after health checks
               self._cleanup_dead_workers()

               await asyncio.sleep(self._health_check_interval)
           # ... rest unchanged ...
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): auto-remove dead workers after 5 minutes`

**Estimated Time**: 1 hour

---

### Task 2.5: Docker Compose Scaling

**Objective**: Update Docker Compose to support worker scaling

**Implementation**:
1. Update `docker-compose.dev.yml`:
   ```yaml
   backtest-worker:
     # ... existing config ...
     environment:
       - WORKER_ID=${HOSTNAME}  # Docker generates unique hostnames when scaling
   ```

2. Test scaling:
   ```bash
   docker-compose -f docker/docker-compose.dev.yml up -d --scale backtest-worker=3
   curl http://localhost:8000/api/v1/workers  # Should see 3 workers
   ```

**Quality Gate**:
```bash
# Manual test
docker-compose -f docker/docker-compose.dev.yml up -d --scale backtest-worker=3
sleep 10
curl http://localhost:8000/api/v1/workers | jq '.total'  # Should be 3
docker-compose -f docker/docker-compose.dev.yml down

make test-unit
make quality
```

**Commit**: `feat(docker): enable worker scaling in Docker Compose`

**Estimated Time**: 0.5 hours

---

### Task 2.6: Load Test - Concurrent Operations

**Objective**: Test multiple concurrent backtests across multiple workers

**TDD Approach**:
1. Create `tests/load/test_concurrent_backtests.py`
2. Submit 5 backtests concurrently, verify all complete

**Implementation**:
1. Write load test with asyncio concurrent submissions

**Quality Gate**:
```bash
# Start environment with 3 workers
docker-compose -f docker/docker-compose.dev.yml up -d --scale backtest-worker=3

# Run load test
pytest tests/load/test_concurrent_backtests.py -v

docker-compose -f docker/docker-compose.dev.yml down

make test-unit
make quality
```

**Commit**: `test(load): add concurrent backtesting load test`

**Estimated Time**: 1.5 hours

---

**Phase 2 Checkpoint**:
✅ Multiple workers running (scalable via Docker Compose)
✅ Health checks monitor all workers
✅ Dead workers automatically removed
✅ Round-robin load balancing works
✅ **TESTABLE**: 5 concurrent backtests across 3 workers complete successfully

**Total Phase 2 Time**: ~8 hours

---

## Phase 3: Training Workers (Vertical Slice)

**Goal**: Add training worker support with GPU/CPU fallback

**Why This Third**: Applies same pattern to training, adds hybrid GPU/CPU logic

**End State**:
- Training workers in Docker Compose
- GPU host configuration (manual)
- Hybrid worker selection (GPU first, CPU fallback)
- **TESTABLE**: Submit training → executes on CPU worker → completes

---

### Task 3.1: Training Worker API

**Objective**: Create training worker API (similar to backtest)

**TDD Approach**:
1. Create `tests/unit/training/test_training_worker_api.py`
2. Test health, start training, exclusivity

**Implementation**:
1. Create `ktrdr/training/training_worker_api.py` (similar structure to backtest worker)
2. Add self-registration on startup
3. Add to Docker Compose

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(training): create training worker API for CPU execution`

**Estimated Time**: 2 hours

---

### Task 3.2: Hybrid Worker Selection (Training)

**Objective**: Add GPU-first, CPU-fallback selection logic

**TDD Approach**:
1. Create `tests/unit/api/services/test_training_worker_selection.py`
2. Test GPU first, CPU fallback, none available

**Implementation**:
1. Add method to WorkerRegistry for hybrid selection
2. Or add to TrainingService (depending on architecture)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(training): add hybrid GPU/CPU worker selection`

**Estimated Time**: 1.5 hours

---

### Task 3.3: End-to-End Test - Training

**Objective**: Submit training operation, verify completes on CPU worker

**Implementation**:
1. Create E2E test similar to backtest E2E

**Quality Gate**:
```bash
make test-unit
make test-e2e
make quality
```

**Commit**: `test(e2e): add end-to-end test for training workers`

**Estimated Time**: 1.5 hours

---

**Phase 3 Checkpoint**:
✅ Training workers running in Docker
✅ Hybrid GPU/CPU selection works
✅ **TESTABLE**: Training operation completes on CPU worker

**Total Phase 3 Time**: ~5 hours

---

## Phase 4: Production Deployment & Continuous Delivery

**Goal**: Production-ready deployment with continuous delivery pipeline

**Why This Fourth**: MVP works, now make it production-ready with automated deployment

**End State**:
- LXC template for base environment (OS, Python, dependencies)
- Automated code deployment (separate from template - enables CD!)
- Configuration management (dev/prod environments)
- Monitoring and observability
- **TESTABLE**: Deploy code update to all workers with one command

**Key Insight**: Template = environment (changes rarely). Code = deployed separately (changes frequently). This enables continuous deployment without template rebuilding!

---

### Task 4.1: LXC Base Template Creation

**Objective**: Create reusable LXC template with base environment (NOT code!)

**Why Template Doesn't Include Code**:
- Template changes are slow (rebuild, redeploy all workers)
- Code changes are frequent (every commit/PR)
- Solution: Template = base environment, code deployed separately

**TDD Approach**:
- Automation script testing
- Template validation

**Implementation**:

1. Create `scripts/proxmox/create-base-template.sh`:
   ```bash
   #!/bin/bash
   # Creates Proxmox LXC template with base environment

   TEMPLATE_ID=9000
   TEMPLATE_NAME="ktrdr-worker-base"
   STORAGE="local-lvm"

   # Create LXC container
   pct create $TEMPLATE_ID local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
     --hostname ktrdr-worker-template \
     --memory 2048 \
     --cores 2 \
     --storage $STORAGE \
     --net0 name=eth0,bridge=vmbr0,ip=dhcp

   # Start container
   pct start $TEMPLATE_ID
   sleep 5

   # Install base environment (NOT code!)
   pct exec $TEMPLATE_ID -- bash <<'EOF'
   # Update system
   apt-get update
   apt-get upgrade -y

   # Install Python and system dependencies
   apt-get install -y python3.12 python3-pip git curl

   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create app directory (code will be deployed here)
   mkdir -p /opt/ktrdr
   chown -R root:root /opt/ktrdr

   # Install systemd service template (code-agnostic)
   cat > /etc/systemd/system/ktrdr-worker@.service <<'SYSTEMD'
   [Unit]
   Description=KTRDR %i Worker
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/ktrdr
   ExecStartPre=/opt/ktrdr/scripts/update-code.sh
   ExecStart=/opt/ktrdr/scripts/start-worker.sh %i
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   SYSTEMD

   # Clean up
   apt-get clean
   EOF

   # Stop container
   pct stop $TEMPLATE_ID

   # Convert to template
   pct template $TEMPLATE_ID

   echo "✓ Template $TEMPLATE_NAME created (ID: $TEMPLATE_ID)"
   ```

2. Create `scripts/proxmox/validate-template.sh`:
   - Clone template
   - Verify environment
   - Clean up

**Quality Gate**:
```bash
# Run on Proxmox host
./scripts/proxmox/create-base-template.sh
./scripts/proxmox/validate-template.sh

make test-unit  # Still passes
make quality
```

**Commit**: `feat(proxmox): create LXC base template for workers`

**Estimated Time**: 2 hours

---

### Task 4.2: Code Deployment Scripts (CD-Friendly!)

**Objective**: Deploy code to workers WITHOUT rebuilding templates

**Why Separate**: Enables continuous deployment - update code on all workers with one command!

**TDD Approach**:
- Script testing with mocks
- Integration test on test LXC

**Implementation**:

1. Create `scripts/deploy/update-code.sh` (runs ON each worker):
   ```bash
   #!/bin/bash
   # Updates code on worker (called by systemd service or deployment script)

   KTRDR_DIR="/opt/ktrdr"
   REPO_URL="${KTRDR_REPO_URL:-https://github.com/yourorg/ktrdr.git}"
   BRANCH="${KTRDR_BRANCH:-main}"

   cd $KTRDR_DIR

   if [ ! -d ".git" ]; then
     # First deployment - clone repo
     git clone $REPO_URL .
     git checkout $BRANCH
   else
     # Update existing repo
     git fetch origin
     git checkout $BRANCH
     git reset --hard origin/$BRANCH
   fi

   # Install/update dependencies
   /root/.cargo/bin/uv sync

   echo "✓ Code updated to $(git rev-parse --short HEAD)"
   ```

2. Create `scripts/deploy/deploy-to-workers.sh` (runs FROM control machine):
   ```bash
   #!/bin/bash
   # Deploys code update to all workers

   WORKERS_FILE="${1:-config/workers.prod.txt}"

   # Read worker list (format: worker_id,ip_address,worker_type)
   while IFS=',' read -r worker_id ip worker_type; do
     echo "Deploying to $worker_id ($ip)..."

     # SSH to worker and update code
     ssh root@$ip "bash /opt/ktrdr/scripts/deploy/update-code.sh"

     # Restart worker service
     ssh root@$ip "systemctl restart ktrdr-worker@${worker_type}"

     echo "✓ $worker_id updated and restarted"
   done < "$WORKERS_FILE"

   echo "✓ Deployment complete!"
   ```

3. Create `config/workers.prod.txt` (example):
   ```
   ktrdr-backtest-1,192.168.1.201,backtesting
   ktrdr-backtest-2,192.168.1.202,backtesting
   ktrdr-training-1,192.168.1.211,training
   ```

**Quality Gate**:
```bash
# Test on one LXC worker
./scripts/deploy/update-code.sh  # Run on worker
./scripts/deploy/deploy-to-workers.sh config/workers.test.txt  # Run from control

make test-unit
make quality
```

**Commit**: `feat(deploy): add continuous deployment scripts for workers`

**Estimated Time**: 2 hours

---

### Task 4.3: Worker Provisioning Automation

**Objective**: Automate creating new workers from template

**Implementation**:

1. Create `scripts/proxmox/provision-worker.sh`:
   ```bash
   #!/bin/bash
   # Provisions new worker from template

   WORKER_ID=$1
   WORKER_TYPE=$2  # backtesting or training
   IP_ADDRESS=$3

   TEMPLATE_ID=9000
   NEXT_ID=$(pvesh get /cluster/nextid)

   # Clone template
   pct clone $TEMPLATE_ID $NEXT_ID \
     --hostname ktrdr-${WORKER_TYPE}-${WORKER_ID} \
     --storage local-lvm

   # Configure network
   pct set $NEXT_ID --net0 name=eth0,bridge=vmbr0,ip=${IP_ADDRESS}/24,gw=192.168.1.1

   # Set environment variables
   pct set $NEXT_ID --features nesting=1

   # Start worker
   pct start $NEXT_ID
   sleep 5

   # Deploy code
   ssh root@$IP_ADDRESS "bash /opt/ktrdr/scripts/deploy/update-code.sh"

   # Configure and start service
   pct exec $NEXT_ID -- bash <<EOF
   # Set worker configuration
   cat > /opt/ktrdr/.env <<ENVFILE
   BACKEND_URL=http://192.168.1.100:8000
   WORKER_TYPE=${WORKER_TYPE}
   WORKER_ID=ktrdr-${WORKER_TYPE}-${WORKER_ID}
   ENVFILE

   # Enable and start service
   systemctl enable ktrdr-worker@${WORKER_TYPE}
   systemctl start ktrdr-worker@${WORKER_TYPE}
   EOF

   echo "✓ Worker provisioned: ktrdr-${WORKER_TYPE}-${WORKER_ID} (ID: $NEXT_ID, IP: $IP_ADDRESS)"
   ```

2. Create `scripts/proxmox/provision-fleet.sh`:
   - Provisions multiple workers from config file
   - Parallel provisioning for speed

**Quality Gate**:
```bash
# Provision one test worker
./scripts/proxmox/provision-worker.sh 1 backtesting 192.168.1.201

# Verify worker registers with backend
curl http://192.168.1.100:8000/api/v1/workers | jq '.total'

make test-unit
make quality
```

**Commit**: `feat(proxmox): add worker provisioning automation`

**Estimated Time**: 2 hours

---

### Task 4.4: Configuration Management

**Objective**: Environment-specific configuration (dev vs prod)

**Implementation**:

1. Create `config/workers.dev.yaml`:
   ```yaml
   backend_url: http://localhost:8000

   health_check:
     interval_seconds: 10
     timeout_seconds: 5
     failure_threshold: 3
     removal_threshold_seconds: 300

   # Docker Compose manages workers
   deployment:
     type: docker-compose
     scale:
       backtesting: 3
       training: 2
   ```

2. Create `config/workers.prod.yaml`:
   ```yaml
   backend_url: http://192.168.1.100:8000

   health_check:
     interval_seconds: 10
     timeout_seconds: 5
     failure_threshold: 3
     removal_threshold_seconds: 300

   # Proxmox LXC workers
   deployment:
     type: proxmox-lxc
     template_id: 9000
     network:
       subnet: 192.168.1.0/24
       gateway: 192.168.1.1

   workers:
     backtesting:
       count: 5
       cores: 4
       memory_mb: 8192
       ip_range: 192.168.1.201-205

     training:
       count: 3
       cores: 8
       memory_mb: 16384
       ip_range: 192.168.1.211-213
   ```

3. Create `ktrdr/config/worker_config.py`:
   ```python
   from pathlib import Path
   import yaml
   import os

   def load_worker_config() -> dict:
       """Load environment-specific worker configuration."""
       env = os.getenv("KTRDR_ENV", "dev")
       config_path = Path(f"config/workers.{env}.yaml")

       with open(config_path) as f:
           return yaml.safe_load(f)
   ```

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(config): add environment-specific worker configuration`

**Estimated Time**: 1 hour

---

### Task 4.5: Monitoring Endpoints

**Objective**: Expose metrics for observability

**Implementation**:

1. Create `ktrdr/api/endpoints/metrics.py`:
   ```python
   from fastapi import APIRouter, Depends
   from ktrdr.api.endpoints.workers import get_worker_registry

   router = APIRouter(prefix="/metrics", tags=["monitoring"])

   @router.get("/workers")
   async def worker_metrics(registry = Depends(get_worker_registry)):
       """Worker health and status metrics."""
       workers = registry.list_workers()

       # Aggregate by status
       by_status = {}
       for worker in workers:
           status = worker.status.value
           by_status[status] = by_status.get(status, 0) + 1

       # Aggregate by type
       by_type = {}
       for worker in workers:
           wtype = worker.worker_type.value
           by_type[wtype] = by_type.get(wtype, 0) + 1

       return {
           "total_workers": len(workers),
           "by_status": by_status,
           "by_type": by_type,
           "workers": [
               {
                   "id": w.worker_id,
                   "type": w.worker_type.value,
                   "status": w.status.value,
                   "current_operation": w.current_operation_id,
                   "health_failures": w.health_check_failures
               }
               for w in workers
           ]
       }

   @router.get("/prometheus")
   async def prometheus_metrics(registry = Depends(get_worker_registry)):
       """Prometheus-compatible metrics."""
       workers = registry.list_workers()

       # Count by status
       available = sum(1 for w in workers if w.status.value == "available")
       busy = sum(1 for w in workers if w.status.value == "busy")
       unavailable = sum(1 for w in workers if w.status.value == "temporarily_unavailable")

       lines = [
           "# HELP ktrdr_workers_total Total number of registered workers",
           "# TYPE ktrdr_workers_total gauge",
           f"ktrdr_workers_total {len(workers)}",
           "",
           "# HELP ktrdr_workers_available Workers in available state",
           "# TYPE ktrdr_workers_available gauge",
           f"ktrdr_workers_available {available}",
           "",
           "# HELP ktrdr_workers_busy Workers in busy state",
           "# TYPE ktrdr_workers_busy gauge",
           f"ktrdr_workers_busy {busy}",
           "",
           "# HELP ktrdr_workers_unavailable Workers in unavailable state",
           "# TYPE ktrdr_workers_unavailable gauge",
           f"ktrdr_workers_unavailable {unavailable}",
       ]

       return "\n".join(lines)
   ```

2. Add to `ktrdr/api/main.py`:
   ```python
   from ktrdr.api.endpoints import metrics
   app.include_router(metrics.router, prefix="/api/v1")
   ```

**Quality Gate**:
```bash
make test-unit
make quality

# Manual test
curl http://localhost:8000/api/v1/metrics/workers | jq
curl http://localhost:8000/api/v1/metrics/prometheus
```

**Commit**: `feat(monitoring): add worker metrics endpoints`

**Estimated Time**: 1.5 hours

---

### Task 4.6: CI/CD Pipeline Documentation

**Objective**: Document deployment workflow

**Implementation**:

1. Create `docs/deployment/DEPLOYMENT_GUIDE.md`:
   ```markdown
   # KTRDR Distributed Workers - Deployment Guide

   ## Continuous Deployment Workflow

   ### 1. One-Time Setup (Per Environment)

   **Create base template** (once):
   ```bash
   ./scripts/proxmox/create-base-template.sh
   ```

   **Provision workers** (once per worker):
   ```bash
   ./scripts/proxmox/provision-fleet.sh config/workers.prod.yaml
   ```

   ### 2. Deploy Code Updates (Every Commit/PR)

   **Automatic deployment** (CI/CD):
   ```bash
   # In your CI/CD pipeline (GitHub Actions, GitLab CI, etc.)
   ./scripts/deploy/deploy-to-workers.sh config/workers.prod.txt
   ```

   **Manual deployment**:
   ```bash
   # Deploy to all workers
   ./scripts/deploy/deploy-to-workers.sh

   # Deploy to specific worker
   ssh root@192.168.1.201 "bash /opt/ktrdr/scripts/deploy/update-code.sh && systemctl restart ktrdr-worker@backtesting"
   ```

   ### 3. Monitoring

   ```bash
   # Check worker status
   curl http://192.168.1.100:8000/api/v1/workers | jq

   # Prometheus metrics
   curl http://192.168.1.100:8000/api/v1/metrics/prometheus
   ```

   ## Key Concepts

   - **Template**: Base environment (OS, Python, uv) - rarely changes
   - **Code deployment**: Git pull + uv sync - changes frequently
   - **No template rebuilds needed for code updates!**
   ```

2. Create `.github/workflows/deploy-workers.yml` (example):
   ```yaml
   name: Deploy to Workers

   on:
     push:
       branches: [main]

   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3

         - name: Deploy to production workers
           env:
             SSH_KEY: ${{ secrets.PROXMOX_SSH_KEY }}
           run: |
             echo "$SSH_KEY" > key.pem
             chmod 600 key.pem
             ./scripts/deploy/deploy-to-workers.sh
   ```

**Quality Gate**:
```bash
make quality  # Docs linting
```

**Commit**: `docs(deployment): add deployment guide and CI/CD examples`

**Estimated Time**: 1.5 hours

---

**Phase 4 Checkpoint**:
✅ LXC base template created (environment only, no code)
✅ Code deployment separate from template (enables CD!)
✅ Worker provisioning automated
✅ Configuration management (dev/prod)
✅ Monitoring endpoints
✅ **TESTABLE**: Deploy code update to all workers with one command
✅ **CI/CD Ready**: No template rebuilds for code changes

**Total Phase 4 Time**: ~10 hours

---

## Summary

### Total Implementation Time

| Phase | Focus | Tasks | Time | Testable? |
|-------|-------|-------|------|-----------|
| Phase 1: Single Worker E2E | Docker + 1 backtest worker | 6 tasks | ~8.5 hours | ✅ Yes! |
| Phase 2: Multi-Worker + Health | Scaling + reliability | 6 tasks | ~8 hours | ✅ Yes! |
| Phase 3: Training Workers | Training support | 3 tasks | ~5 hours | ✅ Yes! |
| **Subtotal (MVP)** | **Distributed system (dev)** | **15 tasks** | **~21.5 hours** | **✅ Every phase!** |
| Phase 4: Production & CD | LXC, deployment, monitoring | 6 tasks | ~10 hours | ✅ Yes! |
| **Total (Complete)** | **Production-ready system** | **21 tasks** | **~31.5 hours** | **✅ Full CD pipeline!** |

### Implementation Strategy

**MVP First (Phases 1-3, ~21.5 hours)**:
- Complete distributed system working in Docker Compose
- Fully functional for development and testing
- All core features implemented
- **You can use it!**

**Production Ready (Phase 4, ~10 hours)**:
- Proxmox LXC deployment automation
- Continuous delivery pipeline (no template rebuilds!)
- Monitoring and observability
- **You can deploy it!**

### Key Improvements Over Previous Plan

**Vertical Slices**:
- ✅ Phase 1 ends with working distributed backtesting (testable!)
- ✅ Phase 2 ends with scaled, reliable system (testable!)
- ✅ Phase 3 ends with training support (testable!)

**Not Horizontal Layers**:
- ❌ No "build all models first" phase
- ❌ No "build all services first" phase
- ✅ Each phase delivers complete functionality

### Quality Standards

Every task must pass:
```bash
make test-unit      # All unit tests (existing + new)
make quality        # Lint + format + typecheck
```

### Git Workflow

- **One branch**: All work on `claude/containerize-training-service-*`
- **One commit per task**: Clear, descriptive commit messages
- **TDD**: Write tests first, then implementation
- **Vertical**: Each phase builds complete feature

---

## Next Steps

1. ✅ Review and approve DESIGN.md
2. ✅ Review and approve ARCHITECTURE.md
3. ✅ Review and approve IMPLEMENTATION_PLAN.md (this document - v2.0)
4. 🚀 Begin Phase 1, Task 1.1

---

**Ready to implement with vertical slices!** 🎯

Each phase delivers working, testable functionality from day one.
