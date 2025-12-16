# Checkpoint & Resilience System: Architecture

This document describes HOW the checkpoint and resilience system is built to satisfy the [Design](DESIGN.md).

---

## Overview

The system has two interconnected parts:

1. **Resilience Layer**: Workers re-register after backend restart; operations sync via health checks
2. **Checkpoint Layer**: Save/restore operation progress using hybrid storage (PostgreSQL + filesystem)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Backend                                                                      │
│  ├─ WorkerRegistry (in-memory, rebuilt via re-registration)                │
│  ├─ OperationsService (operations state, synced via health checks)          │
│  ├─ OrphanOperationDetector (marks stuck RUNNING as FAILED)                │
│  ├─ Resume API (POST /operations/{id}/resume)                               │
│  └─ Checkpoint endpoints (list, delete, cleanup)                            │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ Health checks (Backend → Worker, every 10s)
         │ Re-registration (Worker → Backend, every 30s)
         │
    ┌────┴────────────────────────────────────────┐
    │                                              │
    ▼                                              ▼
┌─────────────────────────┐             ┌─────────────────────────┐
│ Training Worker         │             │ Backtest Worker         │
│  ├─ ReregistrationLoop  │             │  ├─ ReregistrationLoop  │
│  ├─ CheckpointService   │             │  ├─ CheckpointService   │
│  ├─ CheckpointPolicy    │             │  ├─ CheckpointPolicy    │
│  └─ ProgressBridge      │             │  └─ ProgressBridge      │
└─────────────────────────┘             └─────────────────────────┘
         │                                        │
         └────────────┬───────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │ Shared Storage         │
         │  ├─ PostgreSQL (state) │
         │  └─ Filesystem (artifacts) │
         └────────────────────────┘
```

---

## Part 1: Resilience

### Component: Worker Re-Registration on Missed Health Checks

**Location:** `ktrdr/workers/base.py` (addition to WorkerAPIBase)

**Responsibility:** Detect backend restart by noticing missed health checks, then re-register.

**How it works:**
- Backend health-checks each worker every 10 seconds (existing)
- Worker's `/health` endpoint updates `_last_health_check_received` timestamp
- Background task checks: if >30 seconds since last health check → backend probably restarted
- Worker attempts to re-register with backend

```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing init ...
        self._last_health_check_received: Optional[datetime] = None
        self._health_check_timeout: int = 30  # seconds
        self._reregistration_check_interval: int = 10  # seconds

    @self.app.get("/health")
    async def health_check():
        """Health endpoint - called by backend every 10s."""
        # Track when backend last checked on us
        self._last_health_check_received = datetime.utcnow()

        return {
            "healthy": True,
            "worker_id": self.worker_id,
            "worker_status": "busy" if self._current_operation_id else "idle",
            "current_operation": self._current_operation_id,
        }

    async def _start_reregistration_monitor(self) -> None:
        """Start background task that detects missed health checks."""
        self._monitor_task = asyncio.create_task(self._monitor_health_checks())

    async def _monitor_health_checks(self) -> None:
        """Detect if backend stopped health-checking us (probably restarted)."""
        while True:
            try:
                await asyncio.sleep(self._reregistration_check_interval)

                if self._last_health_check_received is None:
                    # Never received a health check - backend might not know us
                    continue

                elapsed = (datetime.utcnow() - self._last_health_check_received).total_seconds()

                if elapsed > self._health_check_timeout:
                    logger.warning(
                        f"No health check from backend in {elapsed:.0f}s - "
                        "checking if we need to re-register"
                    )
                    await self._ensure_registered()
                    # Reset timer after check
                    self._last_health_check_received = datetime.utcnow()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Re-registration monitor error: {e}")

    async def _ensure_registered(self) -> None:
        """Check if registered, register only if not (idempotent)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check if backend knows us
                response = await client.get(
                    f"{self.backend_url}/api/v1/workers/{self.worker_id}"
                )

                if response.status_code == 200:
                    # Already registered - nothing to do
                    logger.debug("Already registered with backend")
                    return

                # Not registered - register now
                logger.info("Not registered with backend - registering")
                await self._register_with_backend()

        except httpx.ConnectError:
            # Backend not reachable - will retry next interval
            logger.warning("Cannot reach backend for registration check")

    async def _register_with_backend(self) -> None:
        """Register this worker with backend, including current operation."""
        payload = {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "endpoint_url": self._get_endpoint_url(),
            "capabilities": self._get_capabilities(),
            "current_operation_id": self._current_operation_id,  # Key for sync!
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/workers/register",
                json=payload
            )
            response.raise_for_status()
            logger.info("Re-registered with backend successfully")
```

**Key insights:**
- Worker only takes action when something is wrong (missed health checks)
- Registration is idempotent: check first, only register if not already registered
- Re-registration includes `current_operation_id` so backend can sync operation status

---

### Component: Operations Sync (Backend)

**Location:** `ktrdr/api/services/worker_registry.py` (enhancement)

**Responsibility:** When worker registers/re-registers with an operation, sync that operation's status.

```python
class WorkerRegistry:
    def register_worker(
        self,
        worker_id: str,
        worker_type: WorkerType,
        endpoint_url: str,
        capabilities: Optional[dict] = None,
        current_operation_id: Optional[str] = None,  # NEW
    ) -> WorkerEndpoint:
        """Register or update a worker, syncing operation status if needed."""

        # ... existing registration logic ...

        # NEW: Sync operation status if worker reports it's running something
        if current_operation_id:
            await self._sync_operation_status(worker_id, current_operation_id)

        return worker

    async def _sync_operation_status(
        self,
        worker_id: str,
        operation_id: str
    ) -> None:
        """Ensure operation status matches worker reality."""
        operations_service = get_operations_service()
        operation = await operations_service.get_operation(operation_id)

        if operation is None:
            logger.warning(f"Worker {worker_id} claims unknown operation {operation_id}")
            return

        if operation.status != OperationStatus.RUNNING:
            # Worker says it's running this, but our records say otherwise
            # Trust the worker - it's the source of truth
            logger.info(
                f"Syncing operation {operation_id}: {operation.status} → RUNNING "
                f"(worker {worker_id} is running it)"
            )
            await operations_service.update_status(
                operation_id,
                OperationStatus.RUNNING,
                worker_id=worker_id
            )
```

---

### Component: Orphan Operation Detector

**Location:** `ktrdr/api/services/orphan_detector.py` (new)

**Responsibility:** Find RUNNING operations with no worker and mark them FAILED.

```python
class OrphanOperationDetector:
    """Detect and handle operations stuck in RUNNING state."""

    def __init__(
        self,
        operations_service: OperationsService,
        worker_registry: WorkerRegistry,
        orphan_timeout_seconds: int = 60,
        check_interval_seconds: int = 15,
    ):
        self._operations_service = operations_service
        self._worker_registry = worker_registry
        self._orphan_timeout = orphan_timeout_seconds
        self._check_interval = check_interval_seconds
        self._task: Optional[asyncio.Task] = None

        # Track when we first saw each potential orphan
        self._potential_orphans: dict[str, datetime] = {}

    async def start(self) -> None:
        """Start background orphan detection loop."""
        self._task = asyncio.create_task(self._detection_loop())
        logger.info(f"Orphan detector started (timeout: {self._orphan_timeout}s)")

    async def stop(self) -> None:
        """Stop background task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _detection_loop(self) -> None:
        """Periodically check for orphan operations."""
        while True:
            try:
                await self._check_for_orphans()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orphan detection error: {e}")
                await asyncio.sleep(self._check_interval)

    async def _check_for_orphans(self) -> None:
        """Find RUNNING operations with no worker and handle them."""
        now = datetime.utcnow()

        # Get all RUNNING operations
        running_ops = await self._operations_service.list_operations(
            status=OperationStatus.RUNNING
        )

        # Get all workers and their current operations
        workers = self._worker_registry.list_workers()
        claimed_operations = {
            w.current_operation_id
            for w in workers
            if w.current_operation_id
        }

        for op in running_ops:
            op_id = op.operation_id

            if op_id in claimed_operations:
                # Worker is running this - not an orphan
                self._potential_orphans.pop(op_id, None)
                continue

            # No worker claims this operation
            if op_id not in self._potential_orphans:
                # First time seeing this as potential orphan
                self._potential_orphans[op_id] = now
                logger.debug(f"Potential orphan detected: {op_id}")
                continue

            # Check if timeout exceeded
            first_seen = self._potential_orphans[op_id]
            elapsed = (now - first_seen).total_seconds()

            if elapsed >= self._orphan_timeout:
                # Timeout exceeded - mark as FAILED
                logger.warning(
                    f"Orphan operation {op_id} - no worker claimed it after "
                    f"{elapsed:.0f}s, marking FAILED"
                )
                await self._operations_service.update_status(
                    op_id,
                    OperationStatus.FAILED,
                    error_message="Operation was RUNNING but no worker claimed it"
                )
                self._potential_orphans.pop(op_id, None)
```

---

### Component: Enhanced Health Check Response

**Location:** `ktrdr/workers/base.py` (existing, enhanced)

The health check already includes `current_operation`. Ensure it's always accurate:

```python
@self.app.get("/health")
async def health_check():
    """Health check endpoint - reports worker status and current operation."""
    active_ops = await self._operations_service.list_operations(
        operation_type=self.operation_type,
        active_only=True
    )

    current_op = active_ops[0] if active_ops else None

    return {
        "healthy": True,
        "service": f"{self.worker_type.value}-worker",
        "worker_id": self.worker_id,  # Include for clarity
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational",
        "worker_status": "busy" if current_op else "idle",
        "current_operation": current_op.operation_id if current_op else None,
    }
```

---

### Resilience Data Flow

**Backend Restart Recovery:**

```
Backend restarts
     │
     ▼
WorkerRegistry empty, OrphanDetector starts
Health check loop starts (calls workers every 10s)
     │
     │ Meanwhile, worker notices:
     │ "Backend hasn't health-checked me in 30s"
     │
     ▼
Worker calls POST /workers/register
  with current_operation_id="op_123"
     │
     ▼
WorkerRegistry._sync_operation_status()
  - Finds op_123 in DB (status may be stale)
  - Updates status to RUNNING
  - Associates with this worker
     │
     ▼
System recovered - op_123 shows correct status
```

**Worker Crash Recovery:**

```
Worker crashes
     │
     ▼
Backend health check fails (3x over 30s)
     │
     ▼
Worker marked TEMPORARILY_UNAVAILABLE
     │
     ▼
OrphanDetector sees op_123 is RUNNING
  but no worker claims it
     │
     ▼
After 60s timeout, op_123 marked FAILED
     │
     ▼
User can resume (if checkpoint exists)
```

---

## Part 2: Checkpointing

### Storage Strategy

**Hybrid Storage: Database + Filesystem**

**Metadata & State:** PostgreSQL
- Operation ID, checkpoint type, timestamps
- JSON state (epoch, loss, portfolio — small, queryable)

**Artifacts:** Filesystem (training only)
- Model weights (model.pt, optimizer.pt) — 100-500MB each
- Location: `data/checkpoints/{operation_id}/`

### What Each Operation Type Stores

**Training Checkpoint:**

| Field | Storage | Purpose |
|-------|---------|---------|
| epoch | DB JSON | Resume point |
| train_loss, val_loss | DB JSON | Progress tracking |
| train_accuracy, val_accuracy | DB JSON | Progress tracking |
| learning_rate | DB JSON | Restore optimizer |
| best_val_loss | DB JSON | Best model tracking |
| training_history | DB JSON | Loss curves |
| model.pt | Filesystem | Model weights |
| optimizer.pt | Filesystem | Optimizer state |
| scheduler.pt | Filesystem | LR scheduler (if used) |
| best_model.pt | Filesystem | Best model so far |

**Backtesting Checkpoint:**

| Field | Storage | Purpose |
|-------|---------|---------|
| bar_index | DB JSON | Resume point |
| current_date | DB JSON | Human-readable position |
| cash | DB JSON | Portfolio state |
| positions | DB JSON | Open positions |
| trade_history | DB JSON | Completed trades |
| equity_curve | DB JSON | Performance tracking |

No filesystem artifacts for backtesting — state is small enough for DB.

---

### Component: CheckpointService

**Location:** `ktrdr/checkpointing/checkpoint_service.py`

**Responsibility:** CRUD operations for checkpoints (both DB and filesystem).

```python
@dataclass
class CheckpointData:
    """Data structure for a checkpoint."""
    operation_id: str
    checkpoint_type: str  # 'periodic', 'cancellation', 'failure', 'shutdown'
    created_at: datetime
    state: dict  # JSON-serializable state
    artifacts_path: Optional[str]  # Path to artifacts directory
    artifacts: Optional[dict[str, bytes]] = None  # Loaded artifacts (lazy)


class CheckpointService:
    """Service for checkpoint CRUD operations."""

    def __init__(
        self,
        db_session: AsyncSession,
        artifacts_dir: str = "data/checkpoints",
    ):
        self._db = db_session
        self._artifacts_dir = Path(artifacts_dir)

    async def save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts: Optional[dict[str, bytes]] = None,
    ) -> None:
        """
        Save checkpoint (UPSERT - overwrites existing).

        Atomic behavior:
        1. Write artifacts to temp directory
        2. Rename to final location (atomic on POSIX)
        3. UPSERT to database
        4. If DB fails, delete artifact files
        """
        artifacts_path = None

        # Step 1-2: Write artifacts if provided
        if artifacts:
            artifacts_path = await self._write_artifacts(operation_id, artifacts)

        # Step 3: UPSERT to database
        try:
            await self._upsert_checkpoint_row(
                operation_id=operation_id,
                checkpoint_type=checkpoint_type,
                state=state,
                artifacts_path=str(artifacts_path) if artifacts_path else None,
            )
        except Exception as e:
            # Step 4: Cleanup artifacts on DB failure
            if artifacts_path and artifacts_path.exists():
                logger.warning(f"DB write failed, cleaning up artifacts: {e}")
                shutil.rmtree(artifacts_path, ignore_errors=True)
            raise

    async def load_checkpoint(
        self,
        operation_id: str,
        load_artifacts: bool = True,
    ) -> Optional[CheckpointData]:
        """Load checkpoint for resume. Returns None if not found."""
        row = await self._get_checkpoint_row(operation_id)
        if not row:
            return None

        checkpoint = CheckpointData(
            operation_id=row.operation_id,
            checkpoint_type=row.checkpoint_type,
            created_at=row.created_at,
            state=row.state,
            artifacts_path=row.artifacts_path,
        )

        # Load artifacts from filesystem if requested
        if load_artifacts and row.artifacts_path:
            checkpoint.artifacts = await self._load_artifacts(row.artifacts_path)

        return checkpoint

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint after successful completion."""
        row = await self._get_checkpoint_row(operation_id)
        if not row:
            return False

        # Delete artifacts from filesystem
        if row.artifacts_path:
            artifacts_path = Path(row.artifacts_path)
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        # Delete DB row
        await self._delete_checkpoint_row(operation_id)
        return True

    async def list_checkpoints(
        self,
        older_than_days: Optional[int] = None,
    ) -> list[CheckpointSummary]:
        """List checkpoints for admin/cleanup."""
        # Implementation queries DB with optional age filter
        ...

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Delete checkpoints older than max_age_days. Returns count deleted."""
        old_checkpoints = await self.list_checkpoints(older_than_days=max_age_days)
        count = 0
        for cp in old_checkpoints:
            if await self.delete_checkpoint(cp.operation_id):
                count += 1
        return count

    async def cleanup_orphan_artifacts(self) -> int:
        """Find and delete artifact directories with no DB row."""
        count = 0
        for dir_path in self._artifacts_dir.iterdir():
            if not dir_path.is_dir():
                continue
            operation_id = dir_path.name
            row = await self._get_checkpoint_row(operation_id)
            if row is None:
                logger.info(f"Cleaning orphan artifacts: {operation_id}")
                shutil.rmtree(dir_path, ignore_errors=True)
                count += 1
        return count

    async def _write_artifacts(
        self,
        operation_id: str,
        artifacts: dict[str, bytes]
    ) -> Path:
        """Write artifacts atomically using temp directory + rename."""
        final_path = self._artifacts_dir / operation_id
        temp_path = self._artifacts_dir / f"{operation_id}.tmp"

        # Clean up any existing temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path)

        # Write to temp directory
        temp_path.mkdir(parents=True)
        for name, data in artifacts.items():
            (temp_path / name).write_bytes(data)

        # Atomic rename (remove existing first if present)
        if final_path.exists():
            shutil.rmtree(final_path)
        temp_path.rename(final_path)

        return final_path

    async def _load_artifacts(self, artifacts_path: str) -> dict[str, bytes]:
        """Load all artifacts from directory."""
        path = Path(artifacts_path)
        if not path.exists():
            raise CheckpointCorruptedError(
                f"Artifacts directory missing: {artifacts_path}"
            )

        artifacts = {}
        for file_path in path.iterdir():
            if file_path.is_file():
                artifacts[file_path.name] = file_path.read_bytes()

        return artifacts
```

---

### Component: CheckpointPolicy

**Location:** `ktrdr/checkpointing/checkpoint_policy.py`

**Responsibility:** Decide when to create checkpoints.

```python
class CheckpointPolicy:
    """Policy for when to create checkpoints."""

    def __init__(
        self,
        unit_interval: int = 10,           # Every N epochs/bars
        time_interval_seconds: int = 300,  # Every 5 minutes
    ):
        self._unit_interval = unit_interval
        self._time_interval = time_interval_seconds
        self._last_checkpoint_time: Optional[float] = None
        self._last_checkpoint_unit: int = 0

    def should_checkpoint(
        self,
        current_unit: int,
        force: bool = False,
    ) -> bool:
        """Check if checkpoint should be created now."""
        if force:
            return True

        now = time.time()

        # Time-based trigger
        if self._last_checkpoint_time is not None:
            if now - self._last_checkpoint_time >= self._time_interval:
                return True

        # Unit-based trigger
        if current_unit - self._last_checkpoint_unit >= self._unit_interval:
            return True

        return False

    def record_checkpoint(self, current_unit: int) -> None:
        """Record that checkpoint was created."""
        self._last_checkpoint_time = time.time()
        self._last_checkpoint_unit = current_unit
```

---

### Component: WorkerAPIBase Checkpoint Integration

**Location:** `ktrdr/workers/base.py` (additions)

```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing init ...
        self.checkpoint_service = CheckpointService(db_session, artifacts_dir)
        self.checkpoint_policy = CheckpointPolicy(
            unit_interval=config.checkpoint_unit_interval,
            time_interval_seconds=config.checkpoint_time_interval,
        )
        self._current_operation_id: Optional[str] = None
        self._shutdown_event = asyncio.Event()

        # Register SIGTERM handler
        signal.signal(signal.SIGTERM, self._sigterm_handler)

    def _sigterm_handler(self, signum, frame):
        """Handle SIGTERM for graceful shutdown."""
        logger.info("SIGTERM received - initiating graceful shutdown")
        self._shutdown_event.set()

    async def run_with_checkpointing(
        self,
        operation_id: str,
        operation_coro: Coroutine,
    ) -> Any:
        """Run operation with checkpoint support and graceful shutdown."""
        self._current_operation_id = operation_id

        operation_task = asyncio.create_task(operation_coro)
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())

        try:
            done, pending = await asyncio.wait(
                [operation_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if shutdown_task in done:
                # Graceful shutdown - save checkpoint
                await self._save_checkpoint("shutdown")
                operation_task.cancel()
                raise GracefulShutdownError("Worker shutdown requested")

            # Operation completed normally
            result = operation_task.result()

            # Delete checkpoint on successful completion
            await self.checkpoint_service.delete_checkpoint(operation_id)

            return result

        except Exception as e:
            # Save failure checkpoint
            await self._save_checkpoint("failure")
            raise
        finally:
            self._current_operation_id = None

    async def _save_checkpoint(self, checkpoint_type: str) -> None:
        """Save checkpoint with current state."""
        if not self._current_operation_id:
            return

        try:
            state = self.build_checkpoint_state()
            artifacts = self.build_checkpoint_artifacts()

            await self.checkpoint_service.save_checkpoint(
                operation_id=self._current_operation_id,
                checkpoint_type=checkpoint_type,
                state=state,
                artifacts=artifacts,
            )
            logger.info(
                f"Checkpoint saved: {self._current_operation_id} ({checkpoint_type})"
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            # Don't raise - checkpoint failure shouldn't crash operation

    async def maybe_checkpoint(self, current_unit: int) -> None:
        """Called by operation to potentially save periodic checkpoint."""
        if self.checkpoint_policy.should_checkpoint(current_unit):
            await self._save_checkpoint("periodic")
            self.checkpoint_policy.record_checkpoint(current_unit)

    # Abstract methods for subclasses
    @abstractmethod
    def build_checkpoint_state(self) -> dict:
        """Return current state for checkpointing."""
        raise NotImplementedError

    @abstractmethod
    def build_checkpoint_artifacts(self) -> Optional[dict[str, bytes]]:
        """Return artifacts for checkpointing (training only)."""
        raise NotImplementedError

    @abstractmethod
    async def restore_from_checkpoint(self, checkpoint: CheckpointData) -> None:
        """Restore state from checkpoint."""
        raise NotImplementedError
```

---

### Checkpoint Data Flow

**Periodic Checkpoint (Training):**

```
TrainingWorker                CheckpointPolicy      CheckpointService
     │                              │                      │
     │── epoch 10 complete          │                      │
     │── maybe_checkpoint(10) ─────>│                      │
     │                              │── should_checkpoint? │
     │                              │   (10 >= 10) → yes   │
     │<─ yes ──────────────────────│                      │
     │── build_checkpoint_state()   │                      │
     │── build_checkpoint_artifacts()                      │
     │── save_checkpoint() ────────────────────────────────>│
     │                              │                      │── write model.pt
     │                              │                      │── write optimizer.pt
     │                              │                      │── UPSERT to DB
     │<─ done ─────────────────────────────────────────────│
     │── policy.record_checkpoint(10)                      │
     │── continue training...       │                      │
```

**Cancellation Checkpoint:**

```
User          Backend         CancellationToken      Worker         CheckpointService
 │               │                   │                  │                   │
 │── cancel ────>│                   │                  │                   │
 │               │── set_cancelled ─>│                  │                   │
 │               │                   │── is_cancelled() │                   │
 │               │                   │<── true ─────────│                   │
 │               │                   │                  │── save_checkpoint()
 │               │                   │                  │    (type='cancellation')
 │               │                   │                  │────────────────────>│
 │               │                   │                  │                   │── write
 │               │<── cancelled ─────│                  │                   │
 │<── done ──────│                   │                  │                   │
```

**Resume Flow:**

```
User          Backend              CheckpointService           Worker
 │               │                        │                      │
 │── resume ────>│                        │                      │
 │               │── check status (CANCELLED/FAILED)             │
 │               │── load_checkpoint ────>│                      │
 │               │<── checkpoint_data ────│                      │
 │               │── update status → RUNNING                     │
 │               │── dispatch(op_id) ─────────────────────────>│
 │               │                        │                      │── load_checkpoint()
 │               │                        │<─────────────────────│
 │               │                        │── checkpoint_data ──>│
 │               │                        │                      │── restore_from_checkpoint()
 │               │                        │                      │── continue operation
 │               │                        │                      │   ...
 │               │                        │                      │── complete
 │               │                        │<── delete_checkpoint ─│
 │<── complete ──│                        │                      │
```

---

## API Contracts

### Worker Registration (Enhanced)

**Endpoint:** `POST /api/v1/workers/register`

**Request:**
```json
{
  "worker_id": "training-worker-abc123",
  "worker_type": "training",
  "endpoint_url": "http://192.168.1.201:5004",
  "capabilities": {"gpu": true, "gpu_type": "CUDA"},
  "current_operation_id": "op_training_20241213_143022_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "worker_id": "training-worker-abc123",
    "status": "AVAILABLE",
    "registered_at": "2024-12-13T14:30:00Z"
  }
}
```

### Get Worker (For Re-Registration Check)

**Endpoint:** `GET /api/v1/workers/{worker_id}`

**Response (found):**
```json
{
  "success": true,
  "data": {
    "worker_id": "training-worker-abc123",
    "worker_type": "training",
    "status": "BUSY",
    "current_operation_id": "op_training_20241213_143022_abc123"
  }
}
```

**Response (not found):**
```json
{
  "success": false,
  "error": {
    "code": "WORKER_NOT_FOUND",
    "message": "Worker not found: training-worker-abc123"
  }
}
```

### Resume Endpoint

**Endpoint:** `POST /api/v1/operations/{operation_id}/resume`

**Request:** No body required

**Response (success):**
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_20241213_143022_abc123",
    "status": "RUNNING",
    "resumed_from": {
      "checkpoint_type": "cancellation",
      "created_at": "2024-12-13T14:35:00Z",
      "epoch": 29,
      "progress_percent": 29.0
    },
    "message": "Training resumed from epoch 29"
  }
}
```

**Response (no checkpoint):**
```json
{
  "success": false,
  "error": {
    "code": "CHECKPOINT_NOT_FOUND",
    "message": "No checkpoint available for operation op_training_20241213_143022_abc123",
    "details": {
      "possible_reasons": [
        "Operation completed successfully (checkpoint deleted)",
        "Checkpoint expired (older than 30 days)",
        "Operation failed before first checkpoint"
      ]
    }
  }
}
```

**Response (checkpoint corrupted):**
```json
{
  "success": false,
  "error": {
    "code": "CHECKPOINT_CORRUPTED",
    "message": "Checkpoint corrupted - artifacts missing or invalid",
    "details": {
      "missing_artifacts": ["model.pt"]
    }
  }
}
```

**Response (operation not resumable):**
```json
{
  "success": false,
  "error": {
    "code": "OPERATION_NOT_RESUMABLE",
    "message": "Cannot resume operation with status RUNNING",
    "details": {
      "current_status": "RUNNING",
      "resumable_statuses": ["CANCELLED", "FAILED"]
    }
  }
}
```

### List Checkpoints

**Endpoint:** `GET /api/v1/checkpoints`

**Query params:**
- `operation_id` (optional): Filter by operation
- `older_than_days` (optional): Filter by age

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "operation_id": "op_training_20241213_143022_abc123",
      "checkpoint_type": "cancellation",
      "created_at": "2024-12-13T14:35:00Z",
      "state_summary": {
        "epoch": 29,
        "progress_percent": 29.0
      },
      "artifacts_size_bytes": 524288000,
      "age_days": 2
    }
  ],
  "total_count": 1
}
```

### Delete Checkpoint

**Endpoint:** `DELETE /api/v1/checkpoints/{operation_id}`

**Response:**
```json
{
  "success": true,
  "message": "Checkpoint deleted for operation op_training_20241213_143022_abc123"
}
```

---

## Database Schema

```sql
CREATE TABLE operation_checkpoints (
    -- Primary key is operation_id (one checkpoint per operation)
    operation_id VARCHAR(255) PRIMARY KEY,

    -- Checkpoint metadata
    checkpoint_type VARCHAR(50) NOT NULL,  -- 'periodic', 'cancellation', 'failure', 'shutdown'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- State (JSON, queryable)
    state JSONB NOT NULL,

    -- Artifact location (NULL for backtesting)
    artifacts_path VARCHAR(500),

    -- Size tracking for monitoring
    state_size_bytes INTEGER,
    artifacts_size_bytes BIGINT
);

-- Index for cleanup queries
CREATE INDEX idx_checkpoints_created_at ON operation_checkpoints(created_at);

-- Index for listing by type
CREATE INDEX idx_checkpoints_type ON operation_checkpoints(checkpoint_type);
```

---

## Filesystem Structure

```
data/checkpoints/
  {operation_id}/
    model.pt           # Model weights (~100-500MB)
    optimizer.pt       # Optimizer state (~100-500MB)
    scheduler.pt       # LR scheduler (if used, ~1KB)
    best_model.pt      # Best model so far (~100-500MB)
```

---

## Configuration

```yaml
resilience:
  # Worker re-registration (triggered by missed health checks)
  health_check_timeout_seconds: 30      # Re-register if no health check in this time
  reregistration_check_interval: 10     # How often worker checks for missed health checks

  # Orphan detection
  orphan_timeout_seconds: 60
  orphan_check_interval_seconds: 15

checkpointing:
  # Periodic triggers
  training_epoch_interval: 10
  backtesting_bar_interval: 10000
  time_interval_seconds: 300  # 5 minutes

  # Cleanup
  max_age_days: 30
  orphan_cleanup_interval_hours: 24

  # Storage
  artifacts_dir: data/checkpoints

  # Graceful shutdown
  shutdown_timeout_seconds: 25
```

---

## Distributed Access

### Development (Docker Compose)

```yaml
volumes:
  checkpoint-data:

services:
  backend:
    volumes:
      - checkpoint-data:/app/data/checkpoints

  training-worker:
    volumes:
      - checkpoint-data:/app/data/checkpoints

  backtest-worker:
    volumes:
      - checkpoint-data:/app/data/checkpoints
```

### Production (NFS)

All services mount same NFS share at `/app/data/checkpoints/`.

---

## Error Handling

### Resilience Errors

| Scenario | Behavior |
|----------|----------|
| Worker can't reach backend for re-registration | Log warning, retry next interval |
| Backend can't reach worker for health check | Mark worker unhealthy after 3 failures |
| Orphan operation detected | Wait timeout, then mark FAILED |

### Checkpoint Errors

| Scenario | Behavior |
|----------|----------|
| Artifact write fails (disk full) | Log error, operation continues without checkpoint |
| DB write fails after artifact write | Delete artifacts, log error, operation continues |
| Artifact load fails (file missing) | Return CHECKPOINT_CORRUPTED error |
| Resume when already RUNNING | Return OPERATION_NOT_RESUMABLE error |

### Consistency Guarantees

| Invariant | How Maintained |
|-----------|----------------|
| No orphan artifacts without DB row | Best-effort delete on DB failure + periodic sweep |
| No DB row pointing to missing artifacts | Validate on load, return CORRUPTED if missing |
| Operation status matches reality | Sync via re-registration and health checks |
| Only one checkpoint per operation | DB primary key constraint + UPSERT |

---

## SIGTERM Handling

```python
# Docker configuration
services:
  training-worker:
    stop_grace_period: 30s  # Give 30s to save checkpoint before SIGKILL
```

Worker SIGTERM flow:
1. SIGTERM received → set shutdown event
2. Current operation detects shutdown event
3. Save checkpoint (type='shutdown')
4. Cancel operation task
5. Exit cleanly

---

## Out of Scope

- Artifact compression
- Multi-region replication
- Checkpoint versioning/migration
- Encryption at rest
- Multiple checkpoints per operation
- Persisting worker registry to database
