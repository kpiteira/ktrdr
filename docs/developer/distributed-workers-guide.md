# Distributed Workers Developer Guide

**Version**: 1.0
**Date**: 2025-11-10
**Audience**: Developers extending workers, debugging issues, or adding new worker types
**Prerequisites**: Understanding of async Python, FastAPI, and KTRDR architecture

---

## Table of Contents

1. [Understanding Workers](#understanding-workers)
2. [Creating a New Worker Type](#creating-a-new-worker-type)
3. [Worker Development Patterns](#worker-development-patterns)
4. [Testing Workers](#testing-workers)
5. [Debugging Workers](#debugging-workers)
6. [Worker API Reference](#worker-api-reference)

---

## Understanding Workers

### Worker Lifecycle

Workers follow a predictable lifecycle from startup to shutdown:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. STARTUP                                                  │
│    ├─ FastAPI app starts (uvicorn)                          │
│    ├─ WorkerAPIBase initialization                          │
│    ├─ Domain-specific endpoints registered                  │
│    └─ Self-registration with backend (POST /workers/register)│
├─────────────────────────────────────────────────────────────┤
│ 2. IDLE STATE                                               │
│    ├─ Waiting for operations                                │
│    ├─ Responding to health checks (GET /health)             │
│    └─ worker_status: "idle"                                 │
├─────────────────────────────────────────────────────────────┤
│ 3. ACCEPT OPERATION                                         │
│    ├─ Receive POST /{domain}/start                          │
│    ├─ Validate: worker in IDLE state?                       │
│    ├─ Accept: Transition to BUSY state                      │
│    ├─ Create operation in worker's OperationsService        │
│    └─ Return operation_id to backend                        │
├─────────────────────────────────────────────────────────────┤
│ 4. EXECUTE OPERATION                                        │
│    ├─ Register progress bridge                              │
│    ├─ Execute domain logic (Engine, not Service!)           │
│    ├─ Report progress via bridge                            │
│    └─ Handle cancellation tokens                            │
├─────────────────────────────────────────────────────────────┤
│ 5. COMPLETE OPERATION                                       │
│    ├─ Mark operation complete/failed                        │
│    ├─ Transition to IDLE state                              │
│    └─ worker_status: "idle"                                 │
├─────────────────────────────────────────────────────────────┤
│ 6. SHUTDOWN (optional)                                      │
│    ├─ Graceful shutdown (finish current operation)          │
│    ├─ Mark worker unavailable                               │
│    └─ Backend removes via health check timeout              │
└─────────────────────────────────────────────────────────────┘
```

### WorkerAPIBase Inheritance Pattern

**Key Concept**: WorkerAPIBase provides ~670 lines of reusable infrastructure extracted from training-host-service. Your worker inherits all this functionality and only needs to implement domain-specific logic.

**What You Get for Free**:

```python
from ktrdr.workers.base import WorkerAPIBase

class MyWorker(WorkerAPIBase):
    def __init__(self):
        super().__init__(
            worker_type=WorkerType.MY_WORKER,
            operation_type=OperationType.MY_OPERATION,
            worker_port=5005,
            backend_url=os.getenv("KTRDR_API_URL")
        )
        # Now you have:
        # - self.app (FastAPI instance with CORS)
        # - self._operations_service (OperationsService singleton)
        # - GET /api/v1/operations/* endpoints (4 endpoints, 374 lines)
        # - GET /health endpoint
        # - self-registration logic
        # - Operation lifecycle management
```

**What WorkerAPIBase Provides**:

| Component | What It Does | Lines of Code |
|-----------|--------------|---------------|
| **OperationsService** | Worker-local operation tracking | 41 lines |
| **Operations Endpoints** | GET /operations/{id}, /operations, /operations/{id}/metrics, DELETE /operations/{id}/cancel | 374 lines |
| **Health Endpoint** | Reports IDLE/BUSY status to backend | ~50 lines |
| **FastAPI Setup** | App, CORS, routers, lifecycle events | ~200 lines |
| **Self-Registration** | POST /workers/register on startup | Included |
| **Total Infrastructure** | Proven, production-ready code | **~670 lines** |

### Operations Tracking via OperationsService

Each worker has its own OperationsService instance for tracking operations running on that worker.

**Why Worker-Local OperationsService?**

- Worker needs to track operations it's executing
- Backend queries worker's operations via proxy endpoints
- Progress bridges register with worker's OperationsService
- Enables backend's existing OperationServiceProxy pattern

**How It Works**:

```python
# Worker's OperationsService (local to worker)
worker_ops_service = get_operations_service()

# 1. Worker creates operation
await worker_ops_service.create_operation(
    operation_id="ABC",
    operation_type=OperationType.BACKTESTING,
    metadata={...}
)

# 2. Worker registers progress bridge
bridge = BacktestProgressBridge(operation_id="ABC", ...)
worker_ops_service.register_local_bridge("ABC", bridge)

# 3. Backend queries worker
# GET http://worker:5003/api/v1/operations/ABC
# → Worker's OperationsService returns operation state + bridge progress

# 4. Worker completes operation
await worker_ops_service.complete_operation("ABC", result_data)
```

**Separation from Backend**:

- Backend has its own OperationsService (tracking all operations across all workers)
- Worker has its own OperationsService (tracking only operations on this worker)
- Backend queries worker's OperationsService via HTTP (OperationServiceProxy pattern)

### Progress Reporting via ProgressBridge

Workers report progress through ProgressBridge instances registered with the worker's OperationsService.

**Pattern** (from training-host-service):

```python
# 1. Create domain-specific progress bridge
bridge = BacktestProgressBridge(
    operation_id=operation_id,
    symbol="EURUSD",
    timeframe="1d",
    total_bars=10000
)

# 2. Register bridge with worker's OperationsService
self._operations_service.register_local_bridge(operation_id, bridge)

# 3. Execute work, passing bridge to Engine
engine = BacktestingEngine(config=...)
result = await asyncio.to_thread(
    engine.run,
    bridge=bridge,  # Engine updates progress via bridge
    cancellation_token=cancellation_token
)

# 4. Backend queries worker's progress
# GET /api/v1/operations/{operation_id}
# → OperationsService reads from bridge, returns progress
```

**Bridge Interface**:

```python
class BacktestProgressBridge:
    def update_progress(self, current_bar: int, total_bars: int):
        """Called by Engine during execution"""
        self.percentage = (current_bar / total_bars) * 100
        self.current_step = f"Bar {current_bar}/{total_bars}"

    def get_progress(self) -> dict:
        """Called by OperationsService when backend queries"""
        return {
            "percentage": self.percentage,
            "current_step": self.current_step,
            "estimated_remaining": self.estimate_time()
        }
```

---

## Creating a New Worker Type

Let's walk through creating a new worker type step-by-step, using BacktestWorker as the reference pattern.

### Step 1: Define Worker Purpose

First, clearly define:
- What operations will this worker execute?
- What resources does it need (CPU, GPU, memory)?
- What makes it different from existing workers?

**Example**: "DataProcessingWorker executes data cleaning and transformation operations. Requires 8 cores, 16GB RAM. CPU-only."

### Step 2: Create Worker Class

Create a new file inheriting from WorkerAPIBase:

```python
# ktrdr/data/data_processing_worker.py

import os
import uuid
from typing import Optional
from fastapi import BackgroundTasks
from pydantic import BaseModel

from ktrdr.workers.base import WorkerAPIBase
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.models.operations import OperationType

class DataProcessingWorker(WorkerAPIBase):
    """Worker for data cleaning and transformation operations."""

    def __init__(
        self,
        worker_port: int = 5005,
        backend_url: Optional[str] = None,
    ):
        # Initialize base class (gets all infrastructure for free)
        super().__init__(
            worker_type=WorkerType.DATA_PROCESSING,  # Add to WorkerType enum
            operation_type=OperationType.DATA_PROCESSING,  # Add to OperationType enum
            worker_port=worker_port,
            backend_url=backend_url or os.getenv("KTRDR_API_URL", "http://backend:8000"),
        )

        # Register domain-specific endpoint
        self._register_data_processing_endpoint()

    def _register_data_processing_endpoint(self):
        """Register the domain-specific /data-processing/start endpoint."""

        @self.app.post("/data-processing/start")
        async def start_data_processing(
            request: DataProcessingStartRequest,
            background_tasks: BackgroundTasks,
        ):
            """
            Start a data processing operation.

            Operation ID Synchronization:
            - Accepts optional task_id from backend
            - Returns same operation_id to backend
            - Enables consistent operation tracking
            """
            # Use backend's operation ID if provided, generate if not
            operation_id = request.task_id or f"worker_dp_{uuid.uuid4().hex[:12]}"

            # Execute work in background
            background_tasks.add_task(
                self._execute_data_processing_work,
                operation_id,
                request
            )

            # Return immediately with operation_id
            return {
                "success": True,
                "operation_id": operation_id,  # Same as backend's task_id!
                "status": "started",
                "worker_id": self.worker_id,
            }

    async def _execute_data_processing_work(
        self,
        operation_id: str,
        request: DataProcessingStartRequest,
    ):
        """
        Execute data processing work.

        Pattern from training-host-service:
        1. Create operation in worker's OperationsService
        2. Create and register progress bridge
        3. Execute actual work (Engine, not Service!)
        4. Complete operation
        """
        try:
            # 1. Create operation in worker's OperationsService
            await self._operations_service.create_operation(
                operation_id=operation_id,
                operation_type=OperationType.DATA_PROCESSING,
                metadata={
                    "source_file": request.source_file,
                    "operations": request.operations,
                    "worker_id": self.worker_id,
                },
            )

            # 2. Create and register progress bridge
            bridge = DataProcessingProgressBridge(
                operation_id=operation_id,
                total_rows=request.estimated_rows,
            )
            self._operations_service.register_local_bridge(operation_id, bridge)

            # 3. Execute actual work (Engine, not Service!)
            engine = DataProcessingEngine(
                source_file=request.source_file,
                operations=request.operations,
            )

            # Get cancellation token from OperationsService
            cancellation_token = self._operations_service.get_cancellation_token(
                operation_id
            )

            # Run in thread pool (blocking I/O operation)
            result = await asyncio.to_thread(
                engine.process,
                progress_callback=bridge.update_progress,
                cancellation_token=cancellation_token,
            )

            # 4. Complete operation
            await self._operations_service.complete_operation(
                operation_id,
                result_data={
                    "rows_processed": result.rows_processed,
                    "output_file": result.output_file,
                    "duration_seconds": result.duration,
                },
            )

        except Exception as e:
            # Mark operation as failed
            await self._operations_service.fail_operation(
                operation_id,
                error_message=str(e),
            )
            raise
```

### Step 3: Define Request Model

```python
# ktrdr/api/models/data_processing.py

from typing import List, Optional
from pydantic import BaseModel, Field

class DataProcessingStartRequest(BaseModel):
    """Request model for starting data processing operation."""

    # Operation ID synchronization (from backend)
    task_id: Optional[str] = Field(
        default=None,
        description="Backend's operation ID (for ID synchronization)"
    )

    # Domain-specific parameters
    source_file: str = Field(..., description="Path to source data file")
    operations: List[str] = Field(..., description="List of operations to perform")
    estimated_rows: int = Field(default=0, description="Estimated row count")
```

### Step 4: Create Progress Bridge

```python
# ktrdr/data/data_processing_progress_bridge.py

from ktrdr.async_infrastructure.progress_bridge import ProgressBridge

class DataProcessingProgressBridge(ProgressBridge):
    """Progress bridge for data processing operations."""

    def __init__(self, operation_id: str, total_rows: int):
        super().__init__(operation_id)
        self.total_rows = total_rows
        self.current_row = 0
        self.current_operation = ""

    def update_progress(self, current_row: int, operation: str):
        """Called by Engine during processing."""
        self.current_row = current_row
        self.current_operation = operation

        # Calculate percentage
        if self.total_rows > 0:
            percentage = (current_row / self.total_rows) * 100
        else:
            percentage = 0

        # Update via base class
        self.set_progress(
            percentage=percentage,
            current_step=f"{operation}: {current_row}/{self.total_rows} rows"
        )

    def get_progress(self) -> dict:
        """Called by OperationsService when backend queries."""
        return {
            "percentage": self.get_percentage(),
            "current_step": self.get_current_step(),
            "current_row": self.current_row,
            "total_rows": self.total_rows,
            "current_operation": self.current_operation,
        }
```

### Step 5: Create Worker Entry Point

```python
# ktrdr/data/data_processing_worker_main.py

import uvicorn
from ktrdr.data.data_processing_worker import DataProcessingWorker

if __name__ == "__main__":
    # Create worker instance
    worker = DataProcessingWorker(
        worker_port=5005,
    )

    # Get FastAPI app from worker
    app = worker.app

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5005,
        log_level="info",
    )
```

### Step 6: Add Worker to Docker Compose

```yaml
# docker-compose.yml

services:
  # ... existing services ...

  data-processing-worker:
    build: .
    command: ["uv", "run", "python", "-m", "ktrdr.data.data_processing_worker_main"]
    environment:
      - KTRDR_API_URL=http://backend:8000
      - WORKER_PORT=5005
      - WORKER_TYPE=data_processing
    networks:
      - ktrdr-network
    # Scale: docker-compose up -d --scale data-processing-worker=3
```

### Step 7: Test Your Worker

```bash
# Start backend
docker-compose up -d backend

# Start your worker
docker-compose up -d data-processing-worker

# Verify registration
curl http://localhost:8000/api/v1/workers | jq '.[] | select(.worker_type=="data_processing")'

# Test operation
curl -X POST http://localhost:8000/api/v1/data-processing/start \
  -H "Content-Type: application/json" \
  -d '{"source_file": "test.csv", "operations": ["clean", "transform"]}'

# Check progress
curl http://localhost:8000/api/v1/operations/{operation_id}
```

---

## Worker Development Patterns

### Pattern 1: Operation ID Synchronization

**Problem**: Backend and worker need to track the same operation with a consistent ID.

**Solution**: Backend passes its operation_id as `task_id`, worker returns same ID.

**Implementation**:

```python
@app.post("/worker-operation/start")
async def start_operation(request: OperationRequest):
    # Accept backend's operation ID or generate new one
    operation_id = request.task_id or f"worker_{uuid.uuid4().hex[:12]}"

    # Create operation with SAME ID
    await operations_service.create_operation(operation_id, ...)

    # Return same ID to backend
    return {"operation_id": operation_id, ...}  # Backend and worker now synchronized!
```

**Why It Matters**:
- Backend can query worker using same ID: `GET /api/v1/operations/{operation_id}`
- Users see consistent operation_id in both backend and worker logs
- Simplifies debugging and progress tracking

### Pattern 2: Accepting Optional task_id

**Best Practice**: Always accept optional `task_id` in your request model.

```python
class MyOperationRequest(BaseModel):
    task_id: Optional[str] = Field(
        default=None,
        description="Backend's operation ID for synchronization"
    )
    # ... other fields ...
```

### Pattern 3: Registering Progress Bridges

**Pattern** (from training-host-service):

```python
async def _execute_work(self, operation_id: str, request):
    # 1. Create operation
    await self._operations_service.create_operation(operation_id, ...)

    # 2. Create progress bridge
    bridge = MyProgressBridge(operation_id, ...)

    # 3. Register bridge BEFORE executing work
    self._operations_service.register_local_bridge(operation_id, bridge)

    # 4. Execute work (Engine updates bridge)
    result = await engine.run(bridge=bridge, ...)

    # 5. OperationsService automatically serves progress from bridge
    # when backend queries: GET /api/v1/operations/{operation_id}
```

**Why Register Before Execution?**

Backend may query progress immediately after dispatching. If bridge isn't registered, worker returns incomplete progress data.

### Pattern 4: Handling Cancellation Tokens

**Pattern** (from training-host-service):

```python
async def _execute_work(self, operation_id: str, request):
    # Get cancellation token from OperationsService
    cancellation_token = self._operations_service.get_cancellation_token(operation_id)

    # Pass token to Engine
    result = await engine.run(
        ...,
        cancellation_token=cancellation_token  # Engine checks periodically
    )
```

**Engine Implementation**:

```python
class MyEngine:
    def run(self, cancellation_token):
        for step in steps:
            # Check cancellation before expensive operation
            if cancellation_token.is_cancelled():
                raise OperationCancelledException("Operation cancelled by user")

            # Perform work
            process_step(step)
```

### Pattern 5: Error Handling and Recovery

**Best Practice**: Always mark operations as failed when exceptions occur.

```python
async def _execute_work(self, operation_id: str, request):
    try:
        # Create operation
        await self._operations_service.create_operation(operation_id, ...)

        # Execute work
        result = await engine.run(...)

        # Mark success
        await self._operations_service.complete_operation(operation_id, result)

    except OperationCancelledException as e:
        # User cancelled - mark as cancelled
        await self._operations_service.cancel_operation(operation_id)
        raise

    except Exception as e:
        # Unexpected error - mark as failed
        await self._operations_service.fail_operation(
            operation_id,
            error_message=str(e)
        )
        # Re-raise so FastAPI logs the error
        raise
```

---

## Testing Workers

### Unit Testing Worker Endpoints

**Test Structure**:

```python
# tests/unit/workers/test_data_processing_worker.py

import pytest
from fastapi.testclient import TestClient
from ktrdr.data.data_processing_worker import DataProcessingWorker

@pytest.fixture
def worker():
    """Create worker instance for testing."""
    return DataProcessingWorker(
        worker_port=5005,
        backend_url="http://test-backend:8000"
    )

@pytest.fixture
def client(worker):
    """Create test client."""
    return TestClient(worker.app)

def test_start_endpoint_accepts_task_id(client):
    """Test that start endpoint accepts and returns task_id."""
    response = client.post(
        "/data-processing/start",
        json={
            "task_id": "test-operation-123",
            "source_file": "test.csv",
            "operations": ["clean"],
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["operation_id"] == "test-operation-123"  # ID synchronization!
    assert data["status"] == "started"

def test_start_endpoint_generates_id_if_not_provided(client):
    """Test that start endpoint generates operation_id if task_id not provided."""
    response = client.post(
        "/data-processing/start",
        json={
            "source_file": "test.csv",
            "operations": ["clean"],
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "operation_id" in data
    assert data["operation_id"].startswith("worker_dp_")

def test_health_endpoint_reports_idle(client):
    """Test that health endpoint reports idle status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["healthy"] is True
    assert data["worker_status"] == "idle"

def test_operations_endpoint_exists(client):
    """Test that operations proxy endpoint exists (from WorkerAPIBase)."""
    response = client.get("/api/v1/operations")

    assert response.status_code == 200
    # Should return empty list initially
```

### Integration Testing with Backend

**Test Structure**:

```python
# tests/integration/test_worker_backend_integration.py

import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.integration
async def test_worker_registration():
    """Test that worker successfully registers with backend."""
    # Start backend (test instance)
    # Start worker

    # Verify worker appears in registry
    async with AsyncClient() as client:
        response = await client.get("http://backend:8000/api/v1/workers")
        workers = response.json()

        # Find our worker
        my_worker = next(
            (w for w in workers if w["worker_type"] == "data_processing"),
            None
        )

        assert my_worker is not None
        assert my_worker["status"] == "AVAILABLE"

@pytest.mark.integration
async def test_operation_dispatch_and_progress():
    """Test full operation flow: dispatch → execute → progress → complete."""
    async with AsyncClient() as client:
        # 1. Start operation via backend
        response = await client.post(
            "http://backend:8000/api/v1/data-processing/start",
            json={
                "source_file": "test.csv",
                "operations": ["clean"],
            }
        )
        operation_id = response.json()["operation_id"]

        # 2. Poll progress
        for _ in range(10):
            await asyncio.sleep(1)

            response = await client.get(
                f"http://backend:8000/api/v1/operations/{operation_id}"
            )
            operation = response.json()

            if operation["status"] == "completed":
                break

        # 3. Verify completion
        assert operation["status"] == "completed"
        assert operation["progress"]["percentage"] == 100
```

### Manual Testing with curl

**Quick Manual Tests**:

```bash
# 1. Check worker registered
curl http://localhost:8000/api/v1/workers | jq

# 2. Check worker health directly
curl http://localhost:5005/health | jq

# 3. Start operation via backend
OPERATION_ID=$(curl -X POST http://localhost:8000/api/v1/data-processing/start \
  -H "Content-Type: application/json" \
  -d '{"source_file": "test.csv", "operations": ["clean"]}' \
  | jq -r '.operation_id')

# 4. Poll progress
watch -n 1 "curl -s http://localhost:8000/api/v1/operations/$OPERATION_ID | jq '.progress'"

# 5. Query worker directly (verify proxy)
curl http://localhost:5005/api/v1/operations/$OPERATION_ID | jq
```

### End-to-End Testing Scenarios

**Scenario: Worker Recovery After Crash**

```python
@pytest.mark.e2e
async def test_worker_recovery_after_crash():
    """Test that worker automatically recovers and re-registers after crash."""
    # 1. Start worker
    worker_process = start_worker()

    # 2. Verify registered
    assert await is_worker_registered("data-processing-worker-1")

    # 3. Kill worker (simulate crash)
    worker_process.kill()

    # 4. Wait for backend to detect (30s = 3 health checks)
    await asyncio.sleep(35)

    # 5. Verify worker marked unavailable
    assert await is_worker_status("data-processing-worker-1", "TEMPORARILY_UNAVAILABLE")

    # 6. Restart worker
    worker_process = start_worker()

    # 7. Verify re-registered and available
    await asyncio.sleep(2)
    assert await is_worker_status("data-processing-worker-1", "AVAILABLE")
```

---

## Debugging Workers

### Common Issues and Solutions

#### Issue 1: Worker Not Registering

**Symptoms**:
- Worker starts successfully
- Worker doesn't appear in `GET /api/v1/workers`
- No errors in worker logs

**Diagnosis**:

```bash
# Check worker logs
docker logs data-processing-worker

# Look for registration attempt
# Should see: "Registering worker with backend at http://backend:8000"

# Check backend logs
docker logs ktrdr-backend

# Look for registration endpoint hit
# Should see: POST /workers/register
```

**Common Causes**:

1. **Wrong KTRDR_API_URL**:
   ```bash
   # Check worker environment
   docker exec data-processing-worker env | grep KTRDR_API_URL

   # Should match backend URL
   # Docker: http://backend:8000
   # Proxmox: http://192.168.1.100:8000
   ```

2. **Network connectivity**:
   ```bash
   # Test from worker container
   docker exec data-processing-worker curl http://backend:8000/health

   # Should return 200 OK
   ```

3. **Backend not running**:
   ```bash
   # Check backend status
   docker ps | grep backend

   # Check backend health
   curl http://localhost:8000/health
   ```

**Solution**:
- Fix KTRDR_API_URL environment variable
- Ensure backend is running and reachable
- Check Docker network configuration

#### Issue 2: Worker Shows as TEMPORARILY_UNAVAILABLE

**Symptoms**:
- Worker appears in registry
- Status: TEMPORARILY_UNAVAILABLE
- Worker seems to be running

**Diagnosis**:

```bash
# Check worker health endpoint directly
curl http://localhost:5005/health

# Should return:
# {
#   "healthy": true,
#   "worker_status": "idle",
#   ...
# }

# Check backend health check logs
docker logs ktrdr-backend | grep "Health check"
```

**Common Causes**:

1. **Health endpoint not responding**:
   - Worker crashed but container still running
   - Worker port blocked by firewall

2. **Health checks timing out**:
   - Worker overloaded (processing heavy operation)
   - Network latency issues

**Solution**:
- Restart worker if crashed
- Check firewall rules
- Verify worker not overloaded (check CPU/memory)

#### Issue 3: Operations Failing to Dispatch

**Symptoms**:
- Backend returns "No workers available"
- Workers shown as AVAILABLE in registry
- Health checks passing

**Diagnosis**:

```bash
# Check worker registry
curl http://localhost:8000/api/v1/workers | jq

# Verify worker_type matches
# Expected: "data_processing"
# If wrong: Update worker_type in worker initialization
```

**Common Causes**:

1. **Worker type mismatch**:
   - Worker registered as "data-processing"
   - Backend looking for "data_processing"
   - Enums must match exactly

2. **Capability requirements not met**:
   - Backend requires GPU, worker has none
   - Check capability filtering logic

**Solution**:
- Ensure worker_type matches exactly (check WorkerType enum)
- Verify capability requirements in backend selection logic

### Checking Worker Registry

**View All Workers**:

```bash
# Get all registered workers
curl http://localhost:8000/api/v1/workers | jq

# Output:
# [
#   {
#     "worker_id": "data-processing-worker-1",
#     "worker_type": "data_processing",
#     "endpoint_url": "http://192.168.1.205:5005",
#     "status": "AVAILABLE",
#     "capabilities": {"cores": 8, "memory_gb": 16},
#     "last_health_check": "2025-11-10T10:30:00Z",
#     "health_check_failures": 0
#   },
#   ...
# ]
```

**Filter by Worker Type**:

```bash
# Get only data processing workers
curl http://localhost:8000/api/v1/workers | jq '.[] | select(.worker_type=="data_processing")'
```

**Check Specific Worker**:

```bash
# Get worker by ID
WORKER_ID="data-processing-worker-1"
curl "http://localhost:8000/api/v1/workers/$WORKER_ID" | jq
```

### Checking Operation Status

**Query via Backend** (normal flow):

```bash
# User's view: Query backend
curl http://localhost:8000/api/v1/operations/$OPERATION_ID | jq

# Backend serves from cache (1s TTL)
# Only queries worker if cache stale
```

**Query Worker Directly** (debugging):

```bash
# Debug: Query worker directly
curl http://localhost:5005/api/v1/operations/$OPERATION_ID | jq

# Should return same data as backend
# If different: Check operation ID synchronization
```

### Log Locations and What to Look For

**Docker Logs**:

```bash
# Worker logs
docker logs data-processing-worker

# Look for:
# - "Worker registered successfully" (on startup)
# - "Starting operation: {operation_id}" (when accepting work)
# - "Operation completed: {operation_id}" (when finishing)
# - Errors/exceptions during execution

# Backend logs
docker logs ktrdr-backend

# Look for:
# - "Worker registered: {worker_id}" (when worker registers)
# - "Selected worker: {worker_id}" (when dispatching)
# - "Health check failed: {worker_id}" (when worker unhealthy)
```

**Proxmox LXC Logs**:

```bash
# Worker logs (inside LXC)
pct exec 301 -- tail -f /opt/ktrdr/logs/worker.log

# Systemd logs
pct exec 301 -- journalctl -u ktrdr-worker -f
```

### Health Check Debugging

**Test Health Endpoint**:

```bash
# Check worker health
curl http://localhost:5005/health | jq

# Expected response:
# {
#   "healthy": true,
#   "service": "data-processing-worker",
#   "timestamp": "2025-11-10T10:30:00Z",
#   "status": "operational",
#   "worker_status": "idle",  # or "busy"
#   "current_operation": null  # or operation_id if busy
# }
```

**Simulate Backend Health Check**:

```bash
# Exactly what backend does
time curl -X GET http://localhost:5005/health

# Should respond < 5 seconds (backend timeout)
# If > 5 seconds: Worker overloaded or network issue
```

---

## Worker API Reference

### Standard Endpoints (from WorkerAPIBase)

These endpoints are provided by WorkerAPIBase and available on all workers.

#### GET /health

**Purpose**: Health check endpoint for backend monitoring

**Response**:

```json
{
    "healthy": true,
    "service": "data-processing-worker",
    "timestamp": "2025-11-10T10:30:00.123Z",
    "status": "operational",
    "worker_status": "idle",  // "idle" or "busy"
    "current_operation": null  // operation_id if busy
}
```

**Backend Usage**: Polls every 10 seconds, 5-second timeout

#### GET /api/v1/operations/{operation_id}

**Purpose**: Get operation status (backend queries via proxy)

**Query Parameters**:
- `force_refresh` (bool, default=false): Skip cache, query fresh state

**Response**:

```json
{
    "success": true,
    "data": {
        "operation_id": "ABC123",
        "operation_type": "data_processing",
        "status": "running",  // pending, running, completed, failed, cancelled
        "progress": {
            "percentage": 45.5,
            "current_step": "Cleaning: 4500/10000 rows",
            "estimated_remaining_seconds": 120
        },
        "created_at": "2025-11-10T10:25:00Z",
        "updated_at": "2025-11-10T10:30:00Z"
    }
}
```

#### GET /api/v1/operations/{operation_id}/metrics

**Purpose**: Get operation metrics with cursor support (incremental)

**Query Parameters**:
- `cursor` (str, optional): Last metric cursor for incremental fetch
- `limit` (int, default=100): Max metrics to return

**Response**:

```json
{
    "success": true,
    "data": {
        "operation_id": "ABC123",
        "metrics": [
            {"timestamp": "...", "name": "rows_processed", "value": 1000},
            {"timestamp": "...", "name": "errors", "value": 5}
        ],
        "cursor": "metric_cursor_456",
        "has_more": false
    }
}
```

#### GET /api/v1/operations

**Purpose**: List all operations on this worker

**Query Parameters**:
- `operation_type` (str, optional): Filter by type
- `status` (str, optional): Filter by status
- `limit` (int, default=100): Max operations to return
- `offset` (int, default=0): Pagination offset

**Response**:

```json
{
    "success": true,
    "data": {
        "operations": [...],
        "total": 42,
        "limit": 100,
        "offset": 0
    }
}
```

#### DELETE /api/v1/operations/{operation_id}/cancel

**Purpose**: Cancel running operation

**Response**:

```json
{
    "success": true,
    "message": "Operation cancelled successfully"
}
```

**Effect**: Sets cancellation token, Engine checks and stops execution

### Domain-Specific Endpoints (Worker-Implemented)

These endpoints are specific to each worker type and must be implemented by the worker.

#### POST /{domain}/start

**Pattern**: All workers implement a start endpoint for their domain

**Examples**:
- `POST /backtests/start` (BacktestWorker)
- `POST /training/start` (TrainingWorker)
- `POST /data-processing/start` (DataProcessingWorker)

**Request** (example for data-processing):

```json
{
    "task_id": "optional-backend-operation-id",  // For ID synchronization
    "source_file": "data/input.csv",
    "operations": ["clean", "transform", "validate"],
    "estimated_rows": 10000
}
```

**Response**:

```json
{
    "success": true,
    "operation_id": "ABC123",  // Same as task_id if provided
    "status": "started",
    "worker_id": "data-processing-worker-1"
}
```

**Error Response** (worker busy):

```json
{
    "error": "Worker busy",
    "current_operation": "XYZ789",
    "status_code": 503  // Service Unavailable
}
```

**Backend Handling**: Backend receives 503, retries with different worker

---

## Summary

This developer guide covered:

1. **Understanding Workers**: Lifecycle, WorkerAPIBase pattern, operations tracking, progress reporting
2. **Creating New Workers**: Step-by-step guide with complete code examples
3. **Development Patterns**: Operation ID sync, progress bridges, cancellation, error handling
4. **Testing**: Unit tests, integration tests, manual testing, E2E scenarios
5. **Debugging**: Common issues, checking registry, logs, health checks
6. **API Reference**: Standard endpoints (from WorkerAPIBase) and domain-specific patterns

**Key Takeaways**:

- WorkerAPIBase provides ~670 lines of proven infrastructure (from training-host-service)
- Workers only implement ~100 lines of domain-specific logic
- Operation ID synchronization enables consistent tracking across backend and workers
- Progress bridges connect worker execution to backend queries
- Self-registration makes workers infrastructure-agnostic (works anywhere)

**Next Steps**:
- **For Architecture**: See [Architecture Overview](../architecture-overviews/distributed-workers.md)
- **For Deployment**: See [Deployment Guide](../user-guides/deployment.md) for Docker Compose setup
- **For Operations**: Proxmox LXC deployment guide (Phase 6, coming soon)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-10
