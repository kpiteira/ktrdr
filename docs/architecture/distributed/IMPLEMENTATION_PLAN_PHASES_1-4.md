# Distributed Training & Backtesting Implementation Plan - Phases 1-4

**Version**: 2.0 - Vertical Slices
**Status**: ✅ **COMPLETED** - Phase 4 Done!
**Date**: 2025-11-08
**Phases Covered**: 1-4 (WorkerAPIBase pattern extraction)

---

## 📋 Plan Navigation

- **This Document**: Phases 1-4 (COMPLETED ✅)
- **Next Steps**: [Phases 5-6](IMPLEMENTATION_PLAN_PHASES_5-6.md) - Production Deployment 🚀
- **Advanced Topics**: [Production Enhancements](../advanced/PRODUCTION_ENHANCEMENTS.md) - Security, observability, load testing

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
- Worker exclusivity enforced (503 rejection when busy)
- TrainingService integrated with WorkerRegistry
- **TESTABLE**: Submit training → executes on CPU worker → completes

---

### Task 3.1: Training Worker API & Self-Registration

**Objective**: Create training worker API with self-registration (similar to backtest worker)

**TDD Approach**:

1. Create `tests/unit/training/test_training_worker_api.py`
2. Test worker startup, registration, basic endpoints

**Implementation**:

1. Create `ktrdr/training/training_worker_api.py`:

   ```python
   # Similar structure to ktrdr/backtesting/remote_api.py
   # - FastAPI app
   # - /health endpoint
   # - /training/start endpoint
   # - Self-registration on startup
   ```

2. Create `ktrdr/training/worker_registration.py` (or reuse backtest pattern)

3. Add to `docker/docker-compose.dev.yml`:

   ```yaml
   training-worker:
     image: ktrdr-backend:dev
     environment:
       - WORKER_TYPE=training
       - WORKER_PORT=5004
       - KTRDR_API_URL=http://backend:8000
     command: ["uvicorn", "ktrdr.training.training_worker_api:app", "--host", "0.0.0.0", "--port", "5004"]
   ```

**Quality Gate**:

```bash
make test-unit
make quality

# Manual test
docker-compose -f docker/docker-compose.dev.yml up -d training-worker
curl http://localhost:8000/api/v1/workers  # Should see training worker registered
```

**Commit**: `feat(training): create training worker API with self-registration`

**Estimated Time**: 2.5 hours

---

### Task 3.2: Training Worker Exclusivity & Health Status

**Objective**: Workers reject requests with 503 when busy, health reports actual status

**TDD Approach**:

1. Add tests for exclusivity enforcement
2. Test health endpoint reports 'busy' vs 'idle'

**Implementation**:

1. Modify `/training/start` endpoint in `training_worker_api.py`:

   ```python
   @app.post("/training/start")
   async def start_training(request: TrainingStartRequest):
       # EXCLUSIVITY CHECK: Reject if worker already busy
       ops_service = get_operations_service()
       active_ops, _, _ = await ops_service.list_operations(
           operation_type=OperationType.TRAINING,
           active_only=True
       )

       if active_ops:
           current_operation = active_ops[0].operation_id
           raise HTTPException(
               status_code=503,  # Service Unavailable
               detail={
                   "error": "Worker busy",
                   "message": f"Worker executing operation {current_operation}",
                   "current_operation": current_operation,
               }
           )

       # Accept operation and execute...
   ```

2. Update `/health` endpoint to report actual status:

   ```python
   @app.get("/health")
   async def health_check():
       ops_service = get_operations_service()
       active_ops, _, _ = await ops_service.list_operations(
           operation_type=OperationType.TRAINING,
           active_only=True
       )

       worker_status = "busy" if active_ops else "idle"
       current_operation = active_ops[0].operation_id if active_ops else None

       return {
           "healthy": True,
           "service": "training-worker",
           "worker_status": worker_status,  # Used by backend health checks
           "current_operation": current_operation,
           "active_operations_count": len(active_ops),
       }
   ```

**Quality Gate**:

```bash
make test-unit
make quality
```

**Commit**: `feat(training): add worker exclusivity with 503 rejection and health status reporting`

**Estimated Time**: 2 hours

---

### Task 3.3: Integrate TrainingService with WorkerRegistry

**Objective**: TrainingService uses WorkerRegistry for worker selection with GPU/CPU hybrid logic

**TDD Approach**:

1. Create `tests/unit/training/test_training_service_integration.py`
2. Test worker selection (GPU first, CPU fallback)
3. Test 503 retry logic
4. Test no workers available scenario

**Implementation**:

1. Modify `ktrdr/training/training_manager.py`:

   ```python
   def __init__(self, worker_registry: Optional[WorkerRegistry] = None):
       super().__init__()
       self.operations_service = get_operations_service()
       self.worker_registry = worker_registry

       # Check GPU host service
       self.use_gpu_host = os.getenv("USE_TRAINING_HOST_SERVICE", "false").lower() in ("true", "1", "yes")

       if self.use_gpu_host:
           self.adapter = TrainingHostAdapter(...)
       elif not worker_registry:
           logger.warning("No GPU host and no WorkerRegistry - will fail if training requested")

   async def run_training(...):
       if self.use_gpu_host:
           # Dispatch to GPU host service
           return await self._run_on_gpu_host(...)
       else:
           # Dispatch to CPU workers via registry
           return await self._run_on_worker(...)

   async def _run_on_worker(...):
       # Similar to BacktestingService._run_remote_backtest()
       # 1. Select worker (CPU training workers)
       # 2. Dispatch with retry on 503
       # 3. Register remote proxy
       # 4. Mark worker busy
       # 5. Return immediately
   ```

2. Add hybrid selection logic:

   ```python
   def select_training_worker(self) -> Optional[WorkerEndpoint]:
       """
       Select training worker with GPU-first, CPU-fallback logic.

       For now: Only CPU workers (WorkerType.TRAINING)
       Future: Check worker capabilities for GPU support
       """
       if self.worker_registry:
           return self.worker_registry.select_worker(WorkerType.TRAINING)
       return None
   ```

3. Implement 503 retry logic (same pattern as BacktestingService):
   - Try selected worker
   - On 503, select different worker
   - Max 3 retries
   - Clear error if all workers busy

**Quality Gate**:

```bash
make test-unit
make quality
```

**Commit**: `feat(training): integrate TrainingService with WorkerRegistry for distributed execution`

**Estimated Time**: 3 hours

---

### Task 3.4: End-to-End Test - Training Workers

**Objective**: Submit training operation, verify completes on CPU worker

**TDD Approach**:

1. Create `tests/e2e/test_training_workers.py`
2. Test scenarios:
   - Training with CPU worker → succeeds
   - Multiple concurrent training requests → distributed across workers
   - 4th request when 3 workers busy → retries and fails gracefully

**Implementation**:

```python
@pytest.mark.e2e
async def test_training_on_cpu_worker():
    """Training succeeds with CPU workers available."""
    # Start backend + training-worker
    # Submit training operation
    # Poll for completion
    # Verify results
    # Verify worker was used (not local execution)

@pytest.mark.e2e
async def test_training_worker_exclusivity():
    """Training workers enforce one operation at a time."""
    # Start backend + 1 training-worker
    # Submit 2 training operations
    # First accepted, second rejected with 503
    # Second retries and waits for first to complete
```

**Quality Gate**:

```bash
make test-unit
make test-e2e
make quality
```

**Commit**: `test(e2e): add end-to-end tests for training workers`

**Estimated Time**: 2 hours

---

**Phase 3 Checkpoint**:
✅ Training workers running in Docker
✅ Worker exclusivity enforced (503 rejection)
✅ Health checks report actual worker status
✅ TrainingService integrated with WorkerRegistry
✅ Hybrid GPU/CPU selection logic (GPU host first, then CPU workers)
✅ 503 retry logic with different workers
✅ **TESTABLE**: Training operation completes on CPU worker

**Total Phase 3 Time**: ~9.5 hours

---

## Phase 4: Worker Base Class Extraction (From Training Host Service)

**Goal**: Extract proven working pattern from training-host-service into reusable `WorkerAPIBase` class

**Why This Fourth**: training-host-service already solves all worker infrastructure problems. Extract this working code before adding more workers.

**Source**: training-host-service (port 5002) - **670 lines of proven working code**

**End State**:

- `WorkerAPIBase` containing 670 lines extracted from training-host-service
- BacktestWorker reduced to ~100 lines (domain logic only)
- TrainingWorker reduced to ~100 lines (domain logic only)
- All workers follow identical pattern from training-host-service
- **TESTABLE**: Workers function identically to training-host-service

**Architectural Benefit**:

- Copy what works (training-host-service pattern already proven)
- DRY principle (374 lines of operations endpoints used once!)
- Consistency (all workers identical infrastructure from training-host-service)
- Bug prevention (fixes applied once benefit all workers)

**Critical Success Factor**: **Copy verbatim from training-host-service. Don't invent, don't "improve", just extract!**

---

### Task 4.1: Extract WorkerAPIBase from Training Host Service

**Objective**: Create `ktrdr/workers/base.py` by extracting working code from training-host-service

**Source Files** (copy from training-host-service):

1. `training-host-service/services/operations.py` (41 lines)
2. `training-host-service/endpoints/operations.py` (374 lines!)
3. `training-host-service/endpoints/health.py` (~50 lines)
4. `training-host-service/main.py` (FastAPI setup, ~200 lines)

**TDD Approach**:

1. Write tests for WorkerAPIBase with mock worker subclass
2. Verify operations endpoints work (all 4 endpoints)
3. Verify health endpoint reports busy/idle correctly
4. Verify FastAPI app setup with CORS
5. Test with mypy --strict

**Implementation Steps**:

**Step 1: Create `ktrdr/workers/base.py`** (~670 lines total)

```python
"""
Worker API Base Class - Extracted from training-host-service

This module provides the complete worker infrastructure pattern that's proven
to work in training-host-service. It's extracted verbatim to ensure consistency.

Source: training-host-service/
- services/operations.py (41 lines)
- endpoints/operations.py (374 lines)
- endpoints/health.py (~50 lines)
- main.py (FastAPI setup, ~200 lines)
"""

import os
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, Depends, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from ktrdr.api.models.operations import (
    OperationListResponse,
    OperationMetricsResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class WorkerAPIBase:
    """
    Base class for all worker APIs.

    Extracted from training-host-service to provide proven working pattern.

    Provides:
    - OperationsService singleton
    - Operations proxy endpoints (/api/v1/operations/*)
    - Health endpoint (/health)
    - FastAPI app setup with CORS
    - Self-registration on startup
    """

    def __init__(
        self,
        worker_type: WorkerType,
        operation_type: OperationType,
        worker_port: int,
        backend_url: str,
    ):
        """
        Initialize worker API base.

        Args:
            worker_type: Type of worker (backtesting, training, etc.)
            operation_type: Type of operations this worker handles
            worker_port: Port for this worker service
            backend_url: URL of backend service for registration
        """
        self.worker_type = worker_type
        self.operation_type = operation_type
        self.worker_port = worker_port
        self.backend_url = backend_url

        # Worker ID (from environment or generate)
        self.worker_id = os.getenv("WORKER_ID", f"{worker_type.value}-worker-{os.urandom(4).hex()}")

        # Initialize OperationsService singleton (CRITICAL!)
        # Each worker MUST have its own instance for remote queryability
        self._operations_service: Optional[OperationsService] = None
        self._initialize_operations_service()

        # Create FastAPI app
        self.app = FastAPI(
            title=f"{worker_type.value.title()} Worker Service",
            description=f"{worker_type.value.title()} worker execution service",
            version="1.0.0",
        )

        # Add CORS middleware (for Docker communication)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register common endpoints
        self._register_operations_endpoints()
        self._register_health_endpoint()
        self._register_root_endpoint()
        self._register_startup_event()

    def _initialize_operations_service(self) -> None:
        """
        Initialize OperationsService singleton.

        Source: training-host-service/services/operations.py (verbatim copy)
        """
        if self._operations_service is None:
            self._operations_service = OperationsService()
            logger.info(f"Operations service initialized in {self.worker_type.value} worker")

    def get_operations_service(self) -> OperationsService:
        """Get or create OperationsService singleton."""
        if self._operations_service is None:
            self._initialize_operations_service()
        return self._operations_service

    def _register_operations_endpoints(self) -> None:
        """
        Register operations proxy endpoints.

        Source: training-host-service/endpoints/operations.py (374 lines - verbatim copy)

        These endpoints expose worker's OperationsService for backend queries.
        """

        @self.app.get(
            "/api/v1/operations/{operation_id}",
            response_model=OperationStatusResponse,
            summary="Get operation status",
        )
        async def get_operation_status(
            operation_id: str = Path(..., description="Unique operation identifier"),
            force_refresh: bool = Query(False, description="Force refresh from bridge"),
        ) -> OperationStatusResponse:
            """Get detailed status information for a specific operation."""
            try:
                operation = await self._operations_service.get_operation(
                    operation_id, force_refresh=force_refresh
                )

                if not operation:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Operation not found: {operation_id}",
                    )

                return OperationStatusResponse(
                    success=True,
                    data=operation,
                )

            except KeyError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting operation status: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get operation status: {str(e)}",
                )

        @self.app.get(
            "/api/v1/operations/{operation_id}/metrics",
            response_model=OperationMetricsResponse,
            summary="Get operation metrics",
        )
        async def get_operation_metrics(
            operation_id: str = Path(..., description="Unique operation identifier"),
            cursor: int = Query(0, ge=0, description="Cursor position"),
        ) -> OperationMetricsResponse:
            """Get domain-specific metrics for an operation."""
            try:
                operation = await self._operations_service.get_operation(operation_id)

                if not operation:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Operation not found: {operation_id}",
                    )

                metrics = await self._operations_service.get_operation_metrics(
                    operation_id, cursor=cursor
                )

                return OperationMetricsResponse(
                    success=True,
                    data={
                        "operation_id": operation_id,
                        "operation_type": operation.operation_type.value,
                        "metrics": metrics or [],
                        "cursor": cursor,
                    },
                )

            except KeyError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting operation metrics: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get operation metrics: {str(e)}",
                )

        @self.app.get(
            "/api/v1/operations",
            response_model=OperationListResponse,
            summary="List operations",
        )
        async def list_operations(
            status: Optional[OperationStatus] = Query(None, description="Filter by status"),
            operation_type: Optional[OperationType] = Query(None, description="Filter by type"),
            limit: int = Query(10, ge=1, le=1000, description="Maximum number"),
            offset: int = Query(0, ge=0, description="Number to skip"),
            active_only: bool = Query(False, description="Show only active operations"),
        ) -> OperationListResponse:
            """List all operations with optional filtering."""
            try:
                (operations, total_count, active_count) = await self._operations_service.list_operations(
                    status=status,
                    operation_type=operation_type,
                    limit=limit,
                    offset=offset,
                    active_only=active_only,
                )

                operation_summaries = [
                    OperationSummary(
                        operation_id=op.operation_id,
                        operation_type=op.operation_type,
                        status=op.status,
                        created_at=op.created_at,
                        progress_percentage=op.progress.percentage,
                        current_step=op.progress.current_step,
                        symbol=op.metadata.symbol,
                        duration_seconds=op.duration_seconds,
                    )
                    for op in operations
                ]

                return OperationListResponse(
                    success=True,
                    data=operation_summaries,
                    total_count=total_count,
                    active_count=active_count,
                )

            except Exception as e:
                logger.error(f"Error listing operations: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to list operations: {str(e)}",
                )

        @self.app.delete(
            "/api/v1/operations/{operation_id}/cancel",
            summary="Cancel operation",
        )
        async def cancel_operation(
            operation_id: str = Path(..., description="Unique operation identifier"),
            reason: Optional[str] = Query(None, description="Cancellation reason"),
        ) -> dict:
            """Cancel a running operation."""
            try:
                result = await self._operations_service.cancel_operation(operation_id, reason)

                return {
                    "success": True,
                    "data": result,
                }

            except KeyError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation not found: {operation_id}",
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error cancelling operation: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to cancel operation: {str(e)}",
                )

    def _register_health_endpoint(self) -> None:
        """
        Register health check endpoint.

        Source: training-host-service/endpoints/health.py (verbatim copy)
        """

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint - reports worker busy/idle status."""
            try:
                active_ops, _, _ = await self._operations_service.list_operations(
                    operation_type=self.operation_type,
                    active_only=True
                )

                return {
                    "healthy": True,
                    "service": f"{self.worker_type.value}-worker",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "operational",
                    "worker_status": "busy" if active_ops else "idle",
                    "current_operation": active_ops[0].operation_id if active_ops else None,
                }

            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                return {
                    "healthy": False,
                    "service": f"{self.worker_type.value}-worker",
                    "error": str(e),
                }

    def _register_root_endpoint(self) -> None:
        """Register root endpoint."""

        @self.app.get("/")
        async def root():
            return {
                "service": f"{self.worker_type.value.title()} Worker Service",
                "version": "1.0.0",
                "status": "running",
                "timestamp": datetime.utcnow().isoformat(),
                "worker_id": self.worker_id,
            }

    def _register_startup_event(self) -> None:
        """Register startup event for self-registration."""

        @self.app.on_event("startup")
        async def startup():
            logger.info(f"Starting {self.worker_type.value} worker...")
            logger.info(f"Worker ID: {self.worker_id}")
            logger.info(f"Worker port: {self.worker_port}")
            logger.info(f"✅ OperationsService initialized (cache_ttl={self._operations_service._cache_ttl}s)")

            # Self-register with backend
            await self.self_register()

    async def self_register(self) -> None:
        """
        Register this worker with backend.

        Pattern from training-host-service worker registration.
        """
        # Import here to avoid circular dependencies
        from ktrdr.workers.worker_registration import WorkerRegistration

        # Set environment variables for WorkerRegistration
        os.environ["WORKER_ID"] = self.worker_id
        os.environ["WORKER_PORT"] = str(self.worker_port)
        os.environ["KTRDR_API_URL"] = self.backend_url

        worker_registration = WorkerRegistration(worker_type=self.worker_type.value)
        success = await worker_registration.register()

        if success:
            logger.info(f"✅ Worker registered successfully: {self.worker_id}")
        else:
            logger.warning(f"⚠️  Worker registration failed: {self.worker_id}")
```

**Step 2: Create comprehensive tests** in `tests/unit/workers/test_base.py`:

```python
"""Tests for WorkerAPIBase extracted from training-host-service pattern."""

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.workers import WorkerType
from ktrdr.api.models.operations import OperationType
from ktrdr.workers.base import WorkerAPIBase


class MockWorker(WorkerAPIBase):
    """Mock worker for testing base class."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )


@pytest.mark.asyncio
class TestWorkerAPIBase:
    """Test WorkerAPIBase extracted from training-host-service."""

    def test_operations_service_initialized(self):
        """Test OperationsService is initialized on worker creation."""
        worker = MockWorker()
        assert worker._operations_service is not None

    def test_operations_endpoints_registered(self):
        """Test operations proxy endpoints are registered."""
        worker = MockWorker()
        client = TestClient(worker.app)

        # Test GET /api/v1/operations
        response = client.get("/api/v1/operations")
        assert response.status_code == 200

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_reports_idle(self):
        """Test health endpoint reports 'idle' when no operations."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["worker_status"] == "idle"
        assert data["current_operation"] is None

    # ... more tests
```

**Step 3: Verify extraction with mypy**:

```bash
mypy --strict ktrdr/workers/base.py
```

**Quality Gate**:

```bash
make test-unit  # All tests pass
make quality    # Linting, formatting, type checking pass
```

**Commit**: `feat(workers): extract WorkerAPIBase from training-host-service pattern`

**Estimated Time**: 4 hours (extraction + testing)

---

### Task 4.2: Implement BacktestWorker Using WorkerAPIBase

**Objective**: Create minimal BacktestWorker following training-host-service pattern

**Pattern Source**: training-host-service/endpoints/training.py + services/training_service.py

**Implementation**:

**Create `ktrdr/backtesting/backtest_worker.py`** (~100 lines):

```python
"""
Backtest Worker - Following training-host-service pattern.

This worker implements the same pattern as training-host-service but for
backtesting operations.
"""

import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge
from ktrdr.logging import get_logger
from ktrdr.workers.base import WorkerAPIBase

logger = get_logger(__name__)


class BacktestStartRequest(BaseModel):
    """Request to start a backtest (following training-host pattern)."""

    task_id: Optional[str] = Field(
        default=None,
        description="Optional task ID from backend (for operation ID synchronization)"
    )
    symbol: str
    timeframe: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0


class BacktestWorker(WorkerAPIBase):
    """Backtest worker using WorkerAPIBase."""

    def __init__(
        self,
        worker_port: int = 5003,
        backend_url: str = "http://backend:8000",
    ):
        """Initialize backtest worker."""
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Force local mode (this service should never use remote mode)
        os.environ["USE_REMOTE_BACKTEST_SERVICE"] = "false"

        # Register domain-specific endpoint
        @self.app.post("/backtests/start")
        async def start_backtest(request: BacktestStartRequest):
            """
            Start a backtest operation.

            Follows training-host-service pattern:
            - Accepts task_id from backend for ID synchronization
            - Returns operation_id back to backend
            """
            # Use backend's task_id if provided, generate if not
            operation_id = request.task_id or f"worker_backtest_{uuid.uuid4().hex[:12]}"

            # Execute work following training-host pattern
            result = await self._execute_backtest_work(operation_id, request)

            return {
                "success": True,
                "operation_id": operation_id,  # ← Return same ID to backend!
                "status": "started",
                **result,
            }

    async def _execute_backtest_work(
        self,
        operation_id: str,
        request: BacktestStartRequest,
    ) -> dict[str, Any]:
        """
        Execute backtest work.

        Follows training-host-service pattern:
        1. Create operation in worker's OperationsService
        2. Create and register progress bridge
        3. Execute actual work (Engine, not Service!)
        4. Complete operation
        """

        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Build strategy config path
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

        # 1. Create operation in worker's OperationsService
        await self._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol=request.symbol,
                timeframe=request.timeframe,
                mode="backtesting",
                start_date=start_date,
                end_date=end_date,
                parameters={
                    "strategy_name": request.strategy_name,
                    "initial_capital": request.initial_capital,
                    "commission": request.commission,
                    "slippage": request.slippage,
                    "worker_id": self.worker_id,
                },
            ),
        )

        # 2. Create and register progress bridge
        days = (end_date - start_date).days
        bars_per_day = {"1h": 24, "4h": 6, "1d": 1, "5m": 288, "1w": 0.2}
        total_bars = int(days * bars_per_day.get(request.timeframe, 1))

        bridge = BacktestProgressBridge(
            operation_id=operation_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            total_bars=max(total_bars, 100),
        )

        self._operations_service.register_local_bridge(operation_id, bridge)
        logger.info(f"Registered backtest bridge for operation {operation_id}")

        # 3. Execute actual work (Engine, not Service!)
        try:
            # Build engine configuration
            engine_config = BacktestConfig(
                symbol=request.symbol,
                timeframe=request.timeframe,
                strategy_config_path=strategy_config_path,
                model_path=None,  # Auto-discovery
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                initial_capital=request.initial_capital,
                commission=request.commission,
                slippage=request.slippage,
            )

            # Create engine
            engine = BacktestingEngine(config=engine_config)

            # Get cancellation token
            cancellation_token = self._operations_service.get_cancellation_token(operation_id)

            # Run engine in thread pool (blocking operation)
            import asyncio
            results = await asyncio.to_thread(
                engine.run,
                bridge=bridge,
                cancellation_token=cancellation_token,
            )

            # 4. Complete operation
            results_dict = results.to_dict()
            await self._operations_service.complete_operation(
                operation_id,
                results_dict,
            )

            logger.info(
                f"Backtest completed for {request.symbol} {request.timeframe}: "
                f"{results_dict.get('total_return', 0):.2%} return"
            )

            return {
                "result_summary": results_dict.get("result_summary", {}),
            }

        except Exception as e:
            # Fail operation on error
            await self._operations_service.fail_operation(operation_id, str(e))
            raise


# Create worker instance
worker = BacktestWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5003")),
    backend_url=os.getenv("KTRDR_API_URL", "http://backend:8000"),
)

# Export FastAPI app for uvicorn
app: FastAPI = worker.app
```

**Update Docker Compose**:

```yaml
backtest-worker:
  command: ["uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]
```

**Quality Gate**:

```bash
make test-unit               # All tests pass
make test-integration        # Integration tests pass
make quality                 # Linting, formatting pass

# Manual test
docker-compose up -d backtest-worker
# Submit backtest operation -> should work identically
```

**Commit**: `feat(backtesting): implement backtest worker using WorkerAPIBase`

**Estimated Time**: 2 hours

---

### Task 4.3: Implement TrainingWorker Using WorkerAPIBase

**Objective**: Create minimal TrainingWorker following training-host-service pattern

**Implementation**: Similar to Task 4.2 but for training operations

**Create `ktrdr/training/training_worker.py`** (~100 lines):

- Same pattern as BacktestWorker
- Calls TrainingManager instead of BacktestingEngine
- Follows training-host-service pattern exactly

**Commit**: `feat(training): implement training worker using WorkerAPIBase`

**Estimated Time**: 2 hours

---

### Task 4.4: Update Docker Compose & Documentation

**Objective**: Update configuration and docs

**Implementation**:

1. **Update `docker/docker-compose.yml`**:
   - Point to new worker files
   - Verify environment variables

2. **Update CLAUDE.md**:
   - Document WorkerAPIBase pattern
   - Add reference to training-host-service as source
   - Update worker architecture diagrams

3. **Run full E2E test suite**:

   ```bash
   make test-e2e --run-container-e2e
   ```

**Commit**: `docs(workers): update documentation for WorkerAPIBase pattern`

**Estimated Time**: 1 hour

---

### Phase 4 Verification

**Manual Tests**:

1. Start Docker Compose with workers
2. Submit backtest operation → should complete successfully with progress
3. Submit training operation → should complete successfully with progress
4. Query worker's `/api/v1/operations/{id}` → should return status
5. Check worker health endpoints → should report busy/idle correctly

**Success Criteria**:
✅ WorkerAPIBase extracted from training-host-service (~670 lines)
✅ BacktestWorker implemented (~100 lines)
✅ TrainingWorker implemented (~100 lines)
✅ Total: ~870 lines (vs. ~1340 if duplicated)
✅ **Savings**: ~470 lines for 2 workers
✅ All unit tests pass
✅ All integration tests pass
✅ All E2E tests pass
✅ Progress tracking works (verified manually)
✅ Worker behavior identical to training-host-service pattern

**Total Phase 4 Time**: ~9 hours

**Key Learnings**:

- ✅ Training-host-service pattern works - copy it!
- ✅ 374 lines of operations endpoints are identical - extract once!
- ✅ Operation ID synchronization via optional task_id parameter
- ✅ Progress bridge registration in worker's OperationsService
- ✅ Call Engine directly, not Service (avoids nested operations)

---

## Phase 5: Remove Local Execution Mode (Pure Distributed Architecture)

**Goal**: Eliminate local/remote duality - all operations execute on workers or host services

**Why This Fourth**: Clean up architecture, enforce distributed-only execution model

**End State**:

- No `USE_REMOTE_*_SERVICE` flags - always distributed
- Backend is orchestrator only, never executes operations
- BacktestingService always uses WorkerRegistry (no fallback)
- TrainingService always uses workers or host service (no local execution)
- Simplified codebase with single execution path
- **TESTABLE**: All operations require workers, fail gracefully if none available

**Architectural Benefit**: Cleaner separation of concerns - backend orchestrates, workers execute

---

### Task 5.1: Remove Local Backtesting Execution

**Objective**: BacktestingService requires WorkerRegistry, removes local execution code path

**TDD Approach**:

1. Update existing tests to expect RuntimeError when no workers available
2. Remove tests for local execution mode
3. Verify all tests pass with distributed-only mode

**Implementation**:

1. Modify `ktrdr/backtesting/backtesting_service.py`:

   ```python
   def __init__(self, worker_registry: WorkerRegistry):  # No Optional - required!
       """Initialize backtesting service (distributed-only mode)."""
       super().__init__()
       self.operations_service = get_operations_service()
       self.worker_registry = worker_registry  # Required, not optional
       self._operation_workers: dict[str, str] = {}

       logger.info("Backtesting service initialized (distributed mode)")

   # Remove _use_remote flag
   # Remove _should_use_remote_service() method
   # Remove _run_local_backtest() method
   # Rename _run_remote_backtest() → run_backtest_on_worker()
   ```

2. Update `ktrdr/api/endpoints/backtesting.py`:

   ```python
   async def get_backtesting_service() -> BacktestingService:
       global _backtesting_service
       if _backtesting_service is None:
           worker_registry = get_worker_registry()  # Always required
           _backtesting_service = BacktestingService(worker_registry=worker_registry)
       return _backtesting_service
   ```

3. Remove environment variable handling:
   - Delete `USE_REMOTE_BACKTEST_SERVICE` checks
   - Delete `REMOTE_BACKTEST_SERVICE_URL` (use WorkerRegistry instead)

**Quality Gate**:

```bash
make test-unit
make quality

# Manual test - should fail gracefully with no workers
docker-compose -f docker/docker-compose.dev.yml up -d backend
# (no workers started)
# Try to start backtest -> Should get clear error: "No workers available"
```

**Commit**: `refactor(backtesting): remove local execution mode, require distributed workers`

**Estimated Time**: 2 hours

---

### Task 5.2: Remove Local Training Execution

**Objective**: TrainingService requires workers or host service, removes local execution

**TDD Approach**:

1. Update tests for distributed-only mode
2. Verify graceful degradation when no workers available

**Implementation**:

1. Modify `ktrdr/training/training_manager.py`:

   ```python
   def __init__(self):
       """Initialize training service (distributed-only mode)."""
       super().__init__()

       # Check if GPU host service is configured
       self.use_gpu_host = os.getenv("USE_TRAINING_HOST_SERVICE", "false").lower() in ("true", "1", "yes")

       if self.use_gpu_host:
           # GPU host service mode
           self.adapter = TrainingHostAdapter(...)
       else:
           # CPU worker mode - require WorkerRegistry
           worker_registry = get_worker_registry()
           if not worker_registry:
               raise RuntimeError(
                   "Training requires either GPU host service or CPU workers. "
                   "Neither configured. Set USE_TRAINING_HOST_SERVICE=true or start training workers."
               )
           self.worker_registry = worker_registry
           # Use worker dispatch instead of local execution

       logger.info(f"Training service initialized (mode: {'gpu-host' if self.use_gpu_host else 'cpu-workers'})")

   # Remove local thread-based training execution
   # Training must go to either GPU host or CPU workers
   ```

2. Remove environment variable:
   - Delete local fallback when `USE_TRAINING_HOST_SERVICE=false`
   - Must explicitly choose: GPU host service OR CPU workers

**Quality Gate**:

```bash
make test-unit
make quality
```

**Commit**: `refactor(training): remove local execution mode, require distributed workers or host service`

**Estimated Time**: 2 hours

---

### Task 5.3: Clean Up Environment Variables

**Objective**: Remove `USE_REMOTE_*` flags, simplify configuration

**Implementation**:

1. Update `docker/docker-compose.dev.yml`:

   ```yaml
   backend:
     environment:
       - PYTHONPATH=/app
       - LOG_LEVEL=INFO
       - ENVIRONMENT=development
       # Removed: USE_REMOTE_BACKTEST_SERVICE (always distributed)
       # Removed: USE_IB_HOST_SERVICE (keep for now - Phase 0)
       # Kept: USE_TRAINING_HOST_SERVICE (choose GPU host vs CPU workers)
   ```

2. Update `docker/docker-compose.yml` (main dev environment):

   ```yaml
   backend:
     environment:
       # Remove USE_REMOTE_BACKTEST_SERVICE
       # Backtesting always uses workers (if docker-compose includes backtest-worker)
       # Or fails gracefully if no workers
   ```

3. Update documentation:
   - Remove references to "local vs remote" mode
   - Document "Backend orchestrates, workers execute"
   - Update architecture diagrams

**Quality Gate**:

```bash
make quality

# Manual verification
grep -r "USE_REMOTE_BACKTEST_SERVICE" . --exclude-dir=.git
# Should only find docs/history, not active code
```

**Commit**: `refactor(config): remove local/remote mode flags, enforce distributed-only architecture`

**Estimated Time**: 1 hour

---

### Task 5.4: Update Documentation

**Objective**: Document pure distributed architecture, remove local execution references

**Implementation**:

1. Update `CLAUDE.md`:

   ```markdown
   ## Distributed Architecture (Phase 4+)

   **Backend Role**: Orchestrator only
   - Selects workers via WorkerRegistry
   - Dispatches operations to workers
   - Tracks progress via proxy pattern
   - Never executes operations locally

   **Worker Role**: Execution only
   - Self-registers on startup
   - Accepts operations (or rejects with 503 if busy)
   - Reports progress via OperationsService API
   - One operation at a time (exclusive execution)

   **Host Services**: Special workers for hardware access
   - GPU training: training-host-service (MPS/CUDA access)
   - IB Gateway: ib-host-service (direct TCP connection)
   ```

2. Update `docs/architecture/distributed/ARCHITECTURE.md`:
   - Add section: "Pure Distributed Architecture (Phase 4)"
   - Remove references to local execution fallback
   - Clarify: Backend = Orchestrator, Workers = Executors

3. Update `README.md`:
   - Document that workers are required
   - Explain graceful degradation (clear errors if no workers)

**Quality Gate**:

```bash
make quality
```

**Commit**: `docs: update for pure distributed architecture, remove local execution references`

**Estimated Time**: 1.5 hours

---

### Task 5.5: Integration Test - Pure Distributed Mode

**Objective**: End-to-end test verifying distributed-only operation

**TDD Approach**:

1. Create `tests/e2e/test_distributed_only.py`
2. Test scenarios:
   - Backtest with workers → succeeds
   - Backtest without workers → fails with clear error
   - Training with GPU host → succeeds
   - Training with CPU workers → succeeds
   - Training without either → fails with clear error

**Implementation**:

```python
@pytest.mark.e2e
async def test_backtest_requires_workers():
    """Backtest fails gracefully when no workers available."""
    # Start backend only (no workers)
    # Try to start backtest
    # Expect: RuntimeError("No workers available")

@pytest.mark.e2e
async def test_backtest_with_workers():
    """Backtest succeeds with workers available."""
    # Start backend + workers
    # Start backtest
    # Expect: Success, operation completes
```

**Quality Gate**:

```bash
make test-e2e
make test-unit
make quality
```

**Commit**: `test(e2e): add distributed-only mode integration tests`

**Estimated Time**: 2 hours

---

**Phase 5 Checkpoint**:
✅ No local execution mode in BacktestingService
✅ No local execution mode in TrainingService
✅ Backend is orchestrator-only (never executes operations)
✅ Simplified codebase with single execution path
✅ Clear error messages when workers unavailable
✅ **TESTABLE**: All operations require workers/host services, fail gracefully otherwise

**Total Phase 4 Time**: ~8.5 hours

**Architectural Achievement**: Clean separation - Backend orchestrates, Workers execute

---

## Phase 6: Production Deployment & Continuous Delivery

**Goal**: Production-ready deployment with continuous delivery pipeline

**Why This Fifth**: Architecture is clean, now make it production-ready with automated deployment

**End State**:

- LXC template for base environment (OS, Python, dependencies)
- Automated code deployment (separate from template - enables CD!)
- Configuration management (dev/prod environments)
- Monitoring and observability
- **TESTABLE**: Deploy code update to all workers with one command

**Key Insight**: Template = environment (changes rarely). Code = deployed separately (changes frequently). This enables continuous deployment without template rebuilding!

---

### Task 6.1: LXC Base Template Creation

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

   # Install Python 3.13 and system dependencies
   apt-get install -y software-properties-common git curl
   add-apt-repository ppa:deadsnakes/ppa -y
   apt-get update
   apt-get install -y python3.13 python3.13-venv python3.13-dev

   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create app directory
   mkdir -p /opt/ktrdr
   chown -R root:root /opt/ktrdr

   # PRELOAD PACKAGES: Clone repo, install all dependencies, then remove code
   cd /opt/ktrdr
   git clone https://github.com/kpiteira/ktrdr.git .

   # Install ALL packages (PyTorch, CUDA, everything - happens once in template)
   /root/.cargo/bin/uv sync

   # Remove code but KEEP .venv with installed packages
   rm -rf .git
   find . -type f -name "*.py" -delete
   find . -type f -name "*.sh" -delete
   # Keep: .venv/, pyproject.toml, uv.lock (needed for delta updates)

   # Install systemd service template (code-agnostic)
   cat > /etc/systemd/system/ktrdr-worker@.service <<'SYSTEMD'
   [Unit]
   Description=KTRDR %i Worker
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/ktrdr
   ExecStartPre=/opt/ktrdr/scripts/deploy/update-code.sh
   ExecStart=/root/.cargo/bin/uv run python -m ktrdr.workers.%i
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

### Task 6.2: Code Deployment Scripts (CD-Friendly!)

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

### Task 6.3: Worker Provisioning Automation

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

### Task 6.4: Configuration Management

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

### Task 6.5: Monitoring Endpoints

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

### Task 6.6: CI/CD Pipeline Documentation

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

**Phase 5 Checkpoint**:
✅ LXC base template created (environment only, no code)
✅ Code deployment separate from template (enables CD!)
✅ Worker provisioning automated
✅ Configuration management (dev/prod)
✅ Monitoring endpoints
✅ **TESTABLE**: Deploy code update to all workers with one command
✅ **CI/CD Ready**: No template rebuilds for code changes

**Total Phase 6 Time**: ~10 hours

---

## Summary

### Total Implementation Time

| Phase | Focus | Tasks | Time | Testable? |
|-------|-------|-------|------|-----------|
| Phase 1: Single Worker E2E | Docker + 1 backtest worker | 6 tasks | ~8.5 hours | ✅ Yes! |
| Phase 2: Multi-Worker + Health | Scaling + reliability | 6 tasks | ~8 hours | ✅ Yes! |
| Phase 3: Training Workers | Training support + integration | 4 tasks | ~9.5 hours | ✅ Yes! |
| **Subtotal (MVP - Hybrid)** | **Distributed + local modes** | **16 tasks** | **~26 hours** | **✅ Every phase!** |
| Phase 4: Pure Distributed | Remove local execution | 5 tasks | ~8.5 hours | ✅ Yes! |
| **Subtotal (Clean Architecture)** | **Pure distributed system** | **21 tasks** | **~34.5 hours** | **✅ Production-ready!** |
| Phase 5: Production & CD | LXC, deployment, monitoring | 6 tasks | ~10 hours | ✅ Yes! |
| **Total (Complete)** | **Full production system** | **27 tasks** | **~44.5 hours** | **✅ Full CD pipeline!** |

### Implementation Strategy

**MVP First (Phases 1-3, ~26 hours)**:

- Complete distributed system working in Docker Compose
- Supports both local and remote execution (hybrid)
- Fully functional for development and testing
- All core features implemented (backtesting + training workers)
- Worker exclusivity, 503 rejection, retry logic
- **You can use it!**

**Clean Architecture (Phase 4, ~8.5 hours)**:

- Remove local execution mode entirely
- Backend orchestrates only, never executes
- Simplified codebase with single execution path
- **You can trust it!**

**Production Ready (Phase 5, ~10 hours)**:

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
