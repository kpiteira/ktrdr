# Checkpoint Persistence System - Implementation Plan

**Document Version:** 1.0
**Date:** January 2025
**Status:** Approved

---

## Overview

This implementation plan breaks down the checkpoint persistence system into **5 vertical phases**. Each phase:
- ✅ Delivers end-to-end testable functionality
- ✅ Adds incremental value
- ✅ Builds on previous phases
- ✅ Can be deployed independently

**Estimated Timeline:** 11.5 development days

**Key Features:**
- ✅ **Startup Recovery:** Automatically recover interrupted operations on API restart
- ✅ **Checkpoint on Cancellation:** Save checkpoint when user cancels operation (Task 3.5)
- ✅ **Checkpoint on Graceful Shutdown:** Save checkpoint when worker receives SIGTERM (Task 3.5)
- ✅ **Manual Checkpoint Management:** Delete individual checkpoints or bulk cleanup
- ✅ **Enhanced Operations List:** Show checkpoint info (size, age, status, type)
- ✅ **One Checkpoint Per Operation:** Simple, efficient UPSERT model

---

## Phase 0: PostgreSQL + TimescaleDB Setup (0.5 days)

**Goal:** Add PostgreSQL with TimescaleDB to the Docker infrastructure.

**Value Delivered:** Database available for checkpoint persistence and future time-series features.

**Estimated Time:** 4 hours

### Task 0.1: Add PostgreSQL + TimescaleDB Infrastructure

**Checklist:**

**Docker Compose Configuration:**
- [ ] Add `postgres` service to `docker/docker-compose.yml` (main dev environment)
- [ ] Add `postgres` service to `docker/docker-compose.dev.yml` (distributed workers dev)
- [ ] Add `postgres` service to `docker/docker-compose.prod.yml` (production with security settings)
- [ ] Configure persistent volumes (`postgres-data`, `postgres-backups` for prod)
- [ ] Add DATABASE_URL to backend environment in all compose files
- [ ] Add DATABASE_URL to worker services in docker-compose.dev.yml
- [ ] Update service dependencies (backend depends on postgres health check)

**Database Configuration:**
- [ ] Create `config/database.yaml` with connection pooling and TimescaleDB settings
- [ ] Create/update `.env.example` with PostgreSQL environment variables
- [ ] Update CLAUDE.md with database setup instructions

**Migration Infrastructure:**
- [ ] Create `migrations/` directory
- [ ] Create `migrations/000_init_timescaledb.sql` (enable TimescaleDB extension)
- [ ] Create `scripts/run_migrations.sh` (migration runner with wait-for-db logic)
- [ ] Make migration script executable

**Integration Testing:**
- [ ] Test `./docker_dev.sh start` brings up postgres successfully
- [ ] Verify TimescaleDB extension enabled
- [ ] Test backend can connect to database
- [ ] Verify migrations auto-run on first startup
- [ ] Test data persistence across container restarts
- [ ] Create `tests/integration/database/test_connection.py`

**Acceptance Criteria:**
- ✅ PostgreSQL + TimescaleDB starts in all environments (dev, distributed, prod)
- ✅ Backend and workers can connect via DATABASE_URL
- ✅ Migrations run automatically on first startup
- ✅ Data persists across container restarts
- ✅ Health checks pass
- ✅ No connection errors in logs

**Key Implementation Details:**

**Postgres Service Configuration:**
```yaml
postgres:
  image: timescale/timescaledb:latest-pg16
  container_name: ktrdr-postgres
  ports:
    - "5432:5432"
  volumes:
    - postgres-data:/var/lib/postgresql/data
    - ../migrations:/docker-entrypoint-initdb.d:ro  # Auto-run migrations
  environment:
    - POSTGRES_DB=${POSTGRES_DB:-ktrdr}
    - POSTGRES_USER=${POSTGRES_USER:-ktrdr_admin}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-ktrdr_dev_password}
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ktrdr_admin -d ktrdr"]
```

**Backend Environment Addition:**
```yaml
backend:
  environment:
    - DATABASE_URL=postgresql://${POSTGRES_USER:-ktrdr_admin}:${POSTGRES_PASSWORD:-ktrdr_dev_password}@postgres:5432/${POSTGRES_DB:-ktrdr}
  depends_on:
    postgres:
      condition: service_healthy
```

**Files Modified/Created:**
- `docker/docker-compose.yml` (modified)
- `docker/docker-compose.dev.yml` (modified)
- `docker/docker-compose.prod.yml` (modified)
- `config/database.yaml` (new)
- `.env.example` (modified)
- `CLAUDE.md` (modified)
- `migrations/000_init_timescaledb.sql` (new)
- `scripts/run_migrations.sh` (new)
- `tests/integration/database/test_connection.py` (new)

---

### Phase 0 End-to-End Test

**Test Scenario:**
```bash
# Clean start
./docker_dev.sh stop
docker volume rm ktrdr_postgres-data 2>/dev/null || true

# Start system
./docker_dev.sh start

# Wait for all services
sleep 30

# Verify PostgreSQL + TimescaleDB
$ docker exec ktrdr-postgres psql -U ktrdr_admin -d ktrdr -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
   extname   | extversion
-------------+------------
 timescaledb | 2.13.0

# Verify migrations ran
$ docker exec ktrdr-postgres psql -U ktrdr_admin -d ktrdr -c "SELECT * FROM schema_version;"
 version |           description            |         applied_at         | applied_by
---------+----------------------------------+----------------------------+-------------
       0 | Initialize TimescaleDB extension | 2025-01-17 10:00:00+00     | ktrdr_admin

# Verify backend connection
$ docker logs ktrdr-backend | grep -i database
INFO: Database connection established
INFO: TimescaleDB extension detected

# Test persistence
$ ./docker_dev.sh restart
$ docker exec ktrdr-postgres psql -U ktrdr_admin -d ktrdr -c "SELECT * FROM schema_version;"
# Should still show migration record
```

**Success Criteria:**
- ✅ PostgreSQL container starts successfully
- ✅ TimescaleDB extension enabled
- ✅ Backend connects to database
- ✅ Migrations run on first startup
- ✅ Data persists across container restarts
- ✅ Health checks pass
- ✅ No connection errors in logs

---

### Phase 0 Summary

**Deliverables:**
1. PostgreSQL + TimescaleDB added to all Docker Compose files (dev, distributed, prod)
2. Database configuration and environment variables
3. Migration infrastructure with auto-run on startup
4. Integration tests verifying database connectivity

**Time Estimate:** 4 hours (0.5 days)

**Dependencies for Phase 1:**
- ✅ PostgreSQL running and accessible
- ✅ TimescaleDB extension enabled
- ✅ Migration framework in place
- ✅ Backend can connect to database

**Next Step:** Proceed to Phase 1 - Core Infrastructure

---

## Phase 1: Core Infrastructure (2 days)

**Goal:** Establish checkpoint storage foundation with PostgreSQL + filesystem.

**Value Delivered:** Can save and load checkpoints (basic CRUD).

**Estimated Time:** 2 days

### Task 1.1: Database Schema & Configuration (3 hours)

**Checklist:**
- [ ] Create `migrations/001_add_checkpoint_tables.sql`
  - `operations` table (if not exists)
  - `operation_checkpoints` table (PK: operation_id, UPSERT support)
  - Trigger: `cleanup_checkpoint_on_completion()`
- [ ] Create `config/persistence.yaml`
  - Checkpoint policies (training, backtesting)
  - Database connection config
  - Cleanup policies
- [ ] Test migration on dev database
- [ ] Verify config loads without errors

**Acceptance Criteria:**
- ✅ Tables created with proper constraints
- ✅ Trigger fires on status change
- ✅ Config file validates correctly

**Files:**
- `migrations/001_add_checkpoint_tables.sql` (new)
- `config/persistence.yaml` (new)

---

### Task 1.2: CheckpointService Implementation (6 hours)

**Checklist:**
- [ ] Create `ktrdr/checkpoint/policy.py`
  - `CheckpointPolicy` dataclass
  - `CheckpointDecisionEngine.should_checkpoint()`
  - Config loader: `load_checkpoint_policies()`
- [ ] Create `ktrdr/checkpoint/service.py`
  - `CheckpointService` class
  - `save_checkpoint()` with UPSERT and atomic filesystem writes
  - `load_checkpoint()` with DB + filesystem retrieval
  - `delete_checkpoint()` with cleanup
  - Artifact storage (temp → rename pattern)
- [ ] Write comprehensive unit tests
  - Policy decision logic
  - Service CRUD operations (mocked DB + filesystem)
  - Error handling and rollback scenarios

**Acceptance Criteria:**
- ✅ Policy logic works (time-based, force checkpoint)
- ✅ UPSERT replaces old checkpoints
- ✅ Old artifacts cleaned up automatically
- ✅ Atomic writes (temp → rename)
- ✅ Transaction rollback cleans up artifacts
- ✅ 90%+ test coverage

**Files:**
- `ktrdr/checkpoint/policy.py` (new)
- `ktrdr/checkpoint/service.py` (new)
- `tests/unit/checkpoint/test_policy.py` (new)
- `tests/unit/checkpoint/test_service.py` (new)

---

### Task 1.3: Integration Testing (2 hours)

**Checklist:**
- [ ] Create `tests/integration/checkpoint/test_basic_flow.py`
- [ ] Test: save → load → delete with real PostgreSQL
- [ ] Test: UPSERT behavior (save twice, verify only 1 row)
- [ ] Test: filesystem artifact management
- [ ] Test: cleanup trigger on operation completion

**Acceptance Criteria:**
- ✅ Full CRUD flow works end-to-end
- ✅ Only 1 checkpoint per operation (UPSERT verified)
- ✅ DB and filesystem stay in sync
- ✅ Cleanup works correctly

**Files:**
- `tests/integration/checkpoint/test_basic_flow.py` (new)

---

### Phase 1 End-to-End Test

**Test Scenario:**
```python
def test_phase1_checkpoint_crud():
    # Setup
    service = CheckpointService()
    policy = load_checkpoint_policies()["training"]

    # Save checkpoint
    checkpoint_id = service.save_checkpoint(
        operation_id="op_test_001",
        state={"epoch": 10, "loss": 0.5},
        checkpoint_type="epoch_snapshot",
        metadata={"epoch": 10}
    )

    # Load checkpoint
    loaded = service.load_checkpoint("op_test_001")
    assert loaded["epoch"] == 10

    # Save again (UPSERT)
    checkpoint_id_2 = service.save_checkpoint(
        operation_id="op_test_001",
        state={"epoch": 20, "loss": 0.3},
        checkpoint_type="epoch_snapshot",
        metadata={"epoch": 20}
    )

    # Verify only 1 checkpoint exists
    loaded = service.load_checkpoint("op_test_001")
    assert loaded["epoch"] == 20

    # Delete checkpoint
    service.delete_checkpoint("op_test_001")
    assert service.load_checkpoint("op_test_001") is None
```

**Success Criteria:**
- ✅ Test passes
- ✅ Database has 0 rows after delete
- ✅ Filesystem has 0 artifact directories after delete

---

## Phase 2: Training Checkpoints (2 days)

**Goal:** Training operations create checkpoints and can resume from them.

**Value Delivered:** Training survives interruptions.

**Estimated Time:** 2 days

### Task 2.1: Training State Capture & Checkpoint Integration (8 hours)

**Checklist:**
- [ ] Add state management to `ModelTrainer`
  - `get_checkpoint_state()` - capture epoch, model, optimizer, scheduler, history, best_model
  - `restore_checkpoint_state()` - restore from checkpoint
- [ ] Integrate `CheckpointService` into training loop
  - Inject service into `ModelTrainer`
  - Add checkpoint decision logic (check policy each epoch)
  - Call `save_checkpoint()` when `should_checkpoint()` returns True
  - Handle checkpoint failures gracefully (training continues)
- [ ] Add `resume_training()` to `TrainingService`
  - Load checkpoint → restore state → continue training
  - Handle missing/corrupted checkpoints
- [ ] Write comprehensive unit tests
  - State capture/restore (PyTorch state_dicts)
  - Checkpoint integration (mocked CheckpointService)
  - Resume logic

**Acceptance Criteria:**
- ✅ Training state fully serializable/restorable
- ✅ Checkpoints saved at correct intervals
- ✅ Training continues if checkpoint fails
- ✅ Can resume from epoch N, start at N+1
- ✅ Training history, best model, early stopping state preserved
- ✅ Logs checkpoint events

**Files:**
- `ktrdr/training/model_trainer.py` (modified)
- `ktrdr/api/services/training/training_service.py` (modified)
- `tests/unit/training/test_model_trainer_checkpoint.py` (new)
- `tests/unit/training/test_training_checkpoint.py` (new)
- `tests/unit/training/test_training_resume.py` (new)

---

### Task 2.2: Integration Testing (3 hours)

**Checklist:**
- [ ] Create `tests/integration/training/test_training_checkpoint_resume.py`
- [ ] Test: train → interrupt → resume → complete with real model
- [ ] Verify epoch resume point correct
- [ ] Verify training history preserved
- [ ] Verify final model correctness

**Acceptance Criteria:**
- ✅ Full training checkpoint & resume flow works end-to-end
- ✅ Interrupted training at epoch N resumes at N+1
- ✅ Final model matches expected performance

**Files:**
- `tests/integration/training/test_training_checkpoint_resume.py` (new)

---

### Phase 2 End-to-End Test

**Test Scenario:**
```python
def test_phase2_training_checkpoint_resume():
    # Start training (100 epochs)
    training_service = TrainingService()
    op1 = training_service.train_multi_symbol_strategy(
        strategy_config_path="config/test_strategy.yaml",
        symbols=["AAPL"],
        timeframes=["1d"],
        epochs=100
    )

    # Wait for checkpoint (epoch 10)
    wait_for_epoch(op1.operation_id, 10)

    # Interrupt training
    cancel_operation(op1.operation_id)

    # Verify checkpoint exists
    checkpoint = checkpoint_service.load_checkpoint(op1.operation_id)
    assert checkpoint["epoch"] == 10

    # Resume training
    op2 = training_service.resume_training(
        new_operation_id=generate_operation_id(),
        checkpoint_state=checkpoint
    )

    # Wait for completion
    wait_for_completion(op2.operation_id)

    # Verify trained 90 more epochs (not 100)
    assert op2.total_epochs == 90
    assert op2.final_epoch == 100
```

**Success Criteria:**
- ✅ Training interrupted at epoch 10
- ✅ Checkpoint saved with epoch=10 state
- ✅ Resume continues from epoch 11
- ✅ Final model trained for 100 total epochs

---

## Phase 3: Operations Service Integration (3 days)

**Goal:** Operations API supports checkpoint & resume with cancellation and shutdown handling.

**Value Delivered:** Users can resume operations via CLI/API. Checkpoints created on cancellation and graceful shutdown.

**Estimated Time:** 3 days

### Task 3.1: Operations Persistence & Startup Recovery (5 hours)

**Checklist:**
- [ ] Add operations persistence to `OperationsService`
  - `persist_operation()`, `load_operations()` from PostgreSQL
  - `load_operations_with_checkpoints()` - join with checkpoint metadata
  - Update `create_operation()`, `update_progress()`, `complete_operation()`, `fail_operation()` to persist
- [ ] Implement startup recovery
  - Add `recover_interrupted_operations()` to `OperationsService`
  - Add startup event handler to `ktrdr/api/main.py`
  - Mark all RUNNING operations as FAILED on API restart
- [ ] Write unit tests
  - Operations persistence
  - Startup recovery logic

**Acceptance Criteria:**
- ✅ Operations survive API restart
- ✅ Can query operations with checkpoint info (has_checkpoint, checkpoint_size)
- ✅ On API startup, RUNNING ops → FAILED (orphan recovery)
- ✅ Recovery logged: "Recovered N interrupted operations"
- ✅ Operations become resumable after recovery

**Files:**
- `ktrdr/api/main.py` (modified - startup event)
- `ktrdr/api/services/operations_service.py` (modified)
- `tests/unit/operations/test_operations_persistence.py` (new)
- `tests/unit/operations/test_startup_recovery.py` (new)

---

### Task 3.2: Resume Operation Implementation (5 hours)

**Checklist:**
- [ ] Add `resume_operation()` to `OperationsService`
  - Validate operation is resumable (FAILED/CANCELLED only)
  - Load checkpoint via `CheckpointService`
  - Dispatch to appropriate service (TrainingService/BacktestingService)
  - Create new operation with `resumed_from` link
  - Delete original checkpoint after resume starts
- [ ] Add API endpoint: `POST /api/v1/operations/{operation_id}/resume`
  - Pydantic models for request/response
  - Error handling (404, 400, 500)
- [ ] Write comprehensive tests
  - Resume operation logic
  - API endpoint tests
  - Error scenarios

**Acceptance Criteria:**
- ✅ Resume validates status (FAILED/CANCELLED only)
- ✅ Loads checkpoint correctly
- ✅ Creates new operation linked to original
- ✅ Returns error if no checkpoint found
- ✅ Original checkpoint deleted after resume
- ✅ API returns 200 with new operation_id on success

**Files:**
- `ktrdr/api/services/operations_service.py` (modified)
- `ktrdr/api/endpoints/operations.py` (modified)
- `ktrdr/api/models/operations.py` (modified)
- `tests/unit/operations/test_resume_operation.py` (new)
- `tests/api/test_operations_resume.py` (new)

---

### Task 3.3: CLI Commands & Checkpoint Management (5 hours)

**Checklist:**
- [ ] Add CLI resume command
  - `ktrdr operations resume <operation_id>`
  - Display progress of new operation
  - Error handling
- [ ] Add checkpoint management commands
  - `ktrdr operations delete-checkpoint <operation_id>`
  - `ktrdr operations cleanup-cancelled`
  - `ktrdr operations cleanup-old --days N`
- [ ] Update `ktrdr operations list` to show checkpoint info
  - has_checkpoint, checkpoint_size_mb, checkpoint_age
- [ ] Add API endpoint: `DELETE /api/v1/operations/{operation_id}/checkpoint`
- [ ] Write comprehensive tests
  - CLI command tests
  - API checkpoint management tests

**Acceptance Criteria:**
- ✅ Can resume via CLI
- ✅ Can delete individual checkpoints
- ✅ Can bulk cleanup cancelled/old checkpoints
- ✅ List shows checkpoint metadata
- ✅ All commands have error handling

**Files:**
- `ktrdr/cli/commands/operations.py` (modified)
- `ktrdr/api/endpoints/operations.py` (modified)
- `tests/cli/test_operations_resume.py` (new)
- `tests/cli/test_operations_cleanup.py` (new)
- `tests/api/test_checkpoint_management.py` (new)

---

### Task 3.4: Integration Testing (2 hours)

**Checklist:**
- [ ] Create `tests/integration/api/test_full_resume_flow.py`
- [ ] Test: CLI → API → OperationsService → TrainingService → Resume
- [ ] Test: API crash → startup recovery → resume
- [ ] Test error scenarios

**Acceptance Criteria:**
- ✅ Full resume flow works end-to-end via CLI
- ✅ API crash recovery verified
- ✅ Error cases handled gracefully

**Files:**
- `tests/integration/api/test_full_resume_flow.py` (new)

---

### Task 3.5: Checkpoint on Cancellation & Graceful Shutdown (4 hours)

**Checklist:**
- [ ] Update checkpoint policy for cancellation events
  - Add `checkpoint_on_cancellation: bool` to `CheckpointPolicy`
  - Add to training/backtesting configs in `config/persistence.yaml`
- [ ] Implement checkpoint-on-cancellation in `OperationsService`
  - Modify `cancel_operation()` to create checkpoint before status change
  - Get current operation state from worker/service
  - Save checkpoint with type "CANCELLATION"
  - Handle cases where state cannot be retrieved (operation not running)
- [ ] Implement graceful shutdown checkpoint for workers
  - Add signal handlers (SIGTERM, SIGINT) to `WorkerAPIBase`
  - On shutdown signal, trigger checkpoint save for any running operation
  - Save checkpoint with type "SHUTDOWN"
  - Wait for checkpoint completion before worker exits
- [ ] Update distributed workers architecture
  - Add shutdown checkpoint logic to `BacktestWorker`
  - Add shutdown checkpoint logic to `TrainingWorker`
  - Coordinate with backend to get operation state
- [ ] Write comprehensive tests
  - Unit test: checkpoint-on-cancellation logic
  - Unit test: graceful shutdown handler
  - Integration test: cancel operation → checkpoint created
  - Integration test: worker SIGTERM → checkpoint created
  - Integration test: resume from cancellation checkpoint
  - Integration test: resume from shutdown checkpoint

**Acceptance Criteria:**
- ✅ Cancelling operation creates checkpoint (if policy enabled)
- ✅ Checkpoint contains current execution state (epoch/bar, progress)
- ✅ Worker graceful shutdown (SIGTERM) creates checkpoint
- ✅ Operations can resume from cancellation checkpoint
- ✅ Operations can resume from shutdown checkpoint
- ✅ No checkpoint created if operation hasn't started yet
- ✅ No checkpoint created if operation already has checkpoint (avoid duplicate)
- ✅ Checkpoint-on-cancellation respects policy flag
- ✅ Shutdown timeout: max 10 seconds to complete checkpoint
- ✅ Logs checkpoint events with clear reason ("user_cancellation", "graceful_shutdown")

**Implementation Details:**

**Policy Update (`ktrdr/checkpoint/policy.py`):**
```python
@dataclass
class CheckpointPolicy:
    checkpoint_interval_seconds: float
    force_checkpoint_every_n: int
    delete_on_completion: bool
    checkpoint_on_failure: bool
    checkpoint_on_cancellation: bool  # NEW
```

**Checkpoint Type Enum (`ktrdr/checkpoint/types.py`):**
```python
from enum import Enum

class CheckpointType(str, Enum):
    """Types of checkpoints that can be created."""
    TIMER = "TIMER"              # Time-based checkpoint (every N seconds)
    FORCE = "FORCE"              # Force checkpoint (every N epochs/bars)
    CANCELLATION = "CANCELLATION"  # User cancelled operation
    SHUTDOWN = "SHUTDOWN"        # Worker graceful shutdown
    FAILURE = "FAILURE"          # Operation failed
```

**Centralized Checkpoint Method (`ktrdr/api/services/operations_service.py`):**
```python
async def create_checkpoint(
    self,
    operation_id: str,
    checkpoint_type: CheckpointType,
    metadata: Optional[dict] = None
) -> bool:
    """
    Create checkpoint for operation (centralized method used by all checkpoint triggers).

    Args:
        operation_id: Operation to checkpoint
        checkpoint_type: Type of checkpoint (TIMER, FORCE, CANCELLATION, SHUTDOWN, FAILURE)
        metadata: Optional metadata (reason, signal, etc.)

    Returns:
        True if checkpoint created successfully, False otherwise
    """
    try:
        # Get current state from worker/service
        current_state = await self._get_operation_state(operation_id)

        if not current_state:
            logger.warning(f"Cannot create checkpoint for {operation_id}: no state available")
            return False

        # Save checkpoint
        checkpoint_service = get_checkpoint_service()
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_state=current_state,
            checkpoint_type=checkpoint_type.value,
            metadata=metadata or {}
        )

        logger.info(
            f"Created {checkpoint_type.value} checkpoint for {operation_id}",
            extra={"operation_id": operation_id, "checkpoint_type": checkpoint_type.value}
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to create {checkpoint_type.value} checkpoint for {operation_id}: {e}",
            exc_info=True,
            extra={"operation_id": operation_id, "checkpoint_type": checkpoint_type.value}
        )
        return False
```

**Cancel Operation Logic (Refactored):**
```python
async def cancel_operation(self, operation_id: str, reason: Optional[str] = None):
    # ... existing cancellation logic ...

    # Create checkpoint before marking as CANCELLED (if policy enabled)
    if policy.checkpoint_on_cancellation:
        await self.create_checkpoint(
            operation_id=operation_id,
            checkpoint_type=CheckpointType.CANCELLATION,
            metadata={"cancellation_reason": reason}
        )
        # Note: Continue with cancellation even if checkpoint fails

    operation.status = OperationStatus.CANCELLED
    # ... rest of cancellation logic ...
```

**Graceful Shutdown Handler (Refactored):**
```python
class WorkerAPIBase:
    def __init__(self, ...):
        # ... existing init ...

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

    async def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signal by creating checkpoint."""
        logger.info(f"Received shutdown signal {signum}, creating checkpoints...")

        # Get current running operations
        running_ops = [
            op for op in self.operations_service.get_all_operations()
            if op.status == OperationStatus.RUNNING
        ]

        # Create checkpoints for all running operations
        for operation in running_ops:
            await self.operations_service.create_checkpoint(
                operation_id=operation.operation_id,
                checkpoint_type=CheckpointType.SHUTDOWN,
                metadata={"shutdown_signal": signum}
            )

        # Exit gracefully
        sys.exit(0)
```

**Training Loop (Example of using centralized method):**
```python
# In ModelTrainer.train() loop
for epoch in range(start_epoch, total_epochs):
    # ... training logic ...

    # Check if should checkpoint
    should_checkpoint, reason = checkpoint_decision_engine.should_checkpoint(
        policy=policy,
        last_checkpoint_time=last_checkpoint_time,
        current_time=time.time(),
        natural_boundary=epoch,
        total_boundaries=epoch
    )

    if should_checkpoint:
        # Determine checkpoint type
        checkpoint_type = (
            CheckpointType.FORCE if "Force checkpoint" in reason
            else CheckpointType.TIMER
        )

        # Create checkpoint using centralized method
        success = await operations_service.create_checkpoint(
            operation_id=operation_id,
            checkpoint_type=checkpoint_type,
            metadata={"epoch": epoch, "reason": reason}
        )

        if success:
            last_checkpoint_time = time.time()
```

**Config Update (`config/persistence.yaml`):**
```yaml
checkpointing:
  training:
    checkpoint_interval_seconds: 300
    force_checkpoint_every_n: 50
    delete_on_completion: true
    checkpoint_on_failure: true
    checkpoint_on_cancellation: true  # NEW

  backtesting:
    checkpoint_interval_seconds: 300
    force_checkpoint_every_n: 5000
    delete_on_completion: true
    checkpoint_on_failure: true
    checkpoint_on_cancellation: true  # NEW
```

**Files:**

- `ktrdr/checkpoint/types.py` (new - CheckpointType enum)
- `ktrdr/checkpoint/policy.py` (modified - add checkpoint_on_cancellation)
- `ktrdr/api/services/operations_service.py` (modified - add create_checkpoint() method)
- `ktrdr/workers/base.py` (modified - add signal handlers)
- `ktrdr/backtesting/backtest_worker.py` (modified - use centralized create_checkpoint)
- `ktrdr/training/training_worker.py` (modified - use centralized create_checkpoint)
- `ktrdr/training/model_trainer.py` (modified - use centralized create_checkpoint)
- `ktrdr/backtesting/backtesting_engine.py` (modified - use centralized create_checkpoint)
- `config/persistence.yaml` (modified - add checkpoint_on_cancellation)
- `tests/unit/operations/test_cancel_with_checkpoint.py` (new)
- `tests/unit/operations/test_centralized_checkpoint.py` (new)
- `tests/unit/workers/test_graceful_shutdown.py` (new)
- `tests/integration/checkpoint/test_cancellation_checkpoint.py` (new)
- `tests/integration/checkpoint/test_shutdown_checkpoint.py` (new)

---

### Phase 3 End-to-End Test

**Test Scenario 1: API Crash Recovery (Primary Use Case)**
```bash
# Start training
$ ktrdr models train --strategy config/test.yaml --epochs 100
Operation started: op_training_20250117_100000
✓ Epoch 1/100 complete
✓ Epoch 5/100 complete (checkpoint saved)
...
✓ Epoch 45/100 complete (checkpoint saved)

# Simulate API crash
$ docker stop ktrdr-backend

# Restart API
$ ./start_ktrdr.sh
API starting...
Startup recovery: 1 operations marked as FAILED
API ready

# List operations
$ ktrdr operations list
ID                          | Status | Progress     | Checkpoint
op_training_20250117_100000 | FAILED | Epoch 45/100 | 52.3 MB (1 min ago)

# Resume operation
$ ktrdr operations resume op_training_20250117_100000
Resuming from epoch 45/100...
Created new operation: op_training_20250117_140000
✓ Epoch 46/100 complete
...
✓ Training complete!

# Verify checkpoints cleaned up
$ ktrdr operations list
op_training_20250117_100000 | FAILED    | Epoch 45/100 | None (deleted)
op_training_20250117_140000 | COMPLETED | Epoch 100/100| None
```

**Test Scenario 2: User Cancellation with Checkpoint (Task 3.5)**
```bash
# Start training
$ ktrdr models train --strategy config/test.yaml --epochs 100
Operation started: op_training_20250117_150000
✓ Epoch 1/100 complete
✓ Epoch 5/100 complete
✓ Epoch 10/100 complete

# Cancel manually (before any time-based checkpoint)
^C
Cancelling operation...
Saving cancellation checkpoint at epoch 10/100...
Operation cancelled at epoch 10/100

# List operations (checkpoint created on cancellation)
$ ktrdr operations list
op_training_20250117_150000 | CANCELLED | Epoch 10/100 | 52.3 MB (now, type: CANCELLATION)

# Resume from cancellation checkpoint
$ ktrdr operations resume op_training_20250117_150000
Resuming from epoch 10/100...
Created new operation: op_training_20250117_150100
✓ Epoch 11/100 complete
...
✓ Training complete!

# Cleanup cancelled checkpoints (for operations not resumed)
$ ktrdr operations cleanup-cancelled
Found 0 cancelled operations with checkpoints (1 was resumed)

# Verify original checkpoint deleted after resume
$ ktrdr operations list
op_training_20250117_150000 | CANCELLED  | Epoch 10/100  | None (deleted after resume)
op_training_20250117_150100 | COMPLETED  | Epoch 100/100 | None
```

**Test Scenario 3: Worker Graceful Shutdown (Task 3.5)**
```bash
# Start backtest on worker
$ ktrdr backtests run --symbol AAPL --timeframe 1h --start 2024-01-01 --end 2024-12-31
Operation started: op_backtest_20250117_160000
Running on worker: backtest-worker-1
✓ Bar 100/10000 complete
✓ Bar 500/10000 complete

# Gracefully shutdown worker (Docker restart)
$ docker restart ktrdr-backtest-worker-1
Worker received SIGTERM...
Saving shutdown checkpoint at bar 500/10000...
Checkpoint saved successfully
Worker stopped gracefully

# Worker restarts, list operations
$ ktrdr operations list
op_backtest_20250117_160000 | FAILED | Bar 500/10000 | 4.8 MB (now, type: SHUTDOWN)

# Resume from shutdown checkpoint
$ ktrdr operations resume op_backtest_20250117_160000
Resuming from bar 500/10000...
Created new operation: op_backtest_20250117_160100
Running on worker: backtest-worker-2
✓ Bar 501/10000 complete
...
✓ Backtest complete!

# Verify checkpoint deleted
$ ktrdr operations list
op_backtest_20250117_160000 | FAILED    | Bar 500/10000  | None (deleted after resume)
op_backtest_20250117_160100 | COMPLETED | Bar 10000/10000| None
```

**Success Criteria:**
- ✅ API crash → RUNNING operations marked as FAILED
- ✅ Startup recovery logged
- ✅ Can list operations from DB with checkpoint info
- ✅ Can resume FAILED operations
- ✅ Can manually cleanup checkpoints
- ✅ Checkpoints auto-deleted on successful completion
- ✅ Original operation's checkpoint deleted after resume starts
- ✅ **[Task 3.5]** User cancellation creates checkpoint with current state
- ✅ **[Task 3.5]** Can resume from cancellation checkpoint
- ✅ **[Task 3.5]** Worker graceful shutdown creates checkpoint
- ✅ **[Task 3.5]** Can resume from shutdown checkpoint
- ✅ **[Task 3.5]** Checkpoint type metadata correctly set (CANCELLATION, SHUTDOWN)

---

## Phase 4: Backtesting Checkpoints (1.5 days)

**Goal:** Backtesting operations create checkpoints and can resume.

**Value Delivered:** Backtesting survives interruptions.

**Estimated Time:** 1.5 days

### Task 4.1: Backtesting State Capture & Checkpoint Integration (6 hours)

**Checklist:**
- [ ] Add state management to backtesting components
  - `PositionManager`: `get_state()`, `restore_state()`
  - `PerformanceTracker`: `get_state()`, `restore_state()`
  - `BacktestingEngine`: `get_checkpoint_state()`
- [ ] Integrate `CheckpointService` into backtest loop
  - Inject service into `BacktestingEngine`
  - Add checkpoint decision logic (check policy each bar)
  - Call `save_checkpoint()` when `should_checkpoint()` returns True
  - Handle checkpoint failures gracefully
- [ ] Add `resume_backtest()` to `BacktestingService`
  - Load checkpoint → restore state → continue backtest
  - Rebuild feature cache from resume point
- [ ] Write comprehensive unit tests
  - State capture/restore (position, performance, trade history)
  - Checkpoint integration
  - Resume logic

**Acceptance Criteria:**
- ✅ State includes: bar_index, position, performance, config, trade history
- ✅ Checkpoints saved at correct intervals
- ✅ Can resume from bar N, start at N+1
- ✅ Position state, performance tracking, equity curve preserved
- ✅ Feature cache rebuilt correctly on resume

**Files:**
- `ktrdr/backtesting/position_manager.py` (modified)
- `ktrdr/backtesting/performance_tracker.py` (modified)
- `ktrdr/backtesting/backtesting_engine.py` (modified)
- `ktrdr/backtesting/backtesting_service.py` (modified)
- `tests/unit/backtesting/test_state_capture.py` (new)
- `tests/unit/backtesting/test_backtest_checkpoint.py` (new)
- `tests/unit/backtesting/test_backtest_resume.py` (new)

---

### Task 4.2: Integration Testing (2 hours)

**Checklist:**
- [ ] Create `tests/integration/backtesting/test_backtest_checkpoint_resume.py`
- [ ] Test: backtest → interrupt → resume → complete with real data
- [ ] Verify bar resume point correct
- [ ] Verify position/performance state preserved
- [ ] Verify final results match non-interrupted backtest

**Acceptance Criteria:**
- ✅ Full backtesting checkpoint & resume flow works end-to-end
- ✅ Interrupted backtest at bar N resumes at N+1
- ✅ Final results correct

**Files:**
- `tests/integration/backtesting/test_backtest_checkpoint_resume.py` (new)

---

### Phase 4 End-to-End Test

**Test Scenario:**
```python
def test_phase4_backtest_checkpoint_resume():
    # Start backtest (10,000 bars)
    backtest_service = BacktestingService()
    op1 = backtest_service.run_backtest(
        symbol="AAPL",
        timeframe="1h",
        start_date="2024-01-01",
        end_date="2024-12-31",
        strategy_config_path="config/test.yaml"
    )

    # Wait for checkpoint (bar 5000)
    wait_for_bar(op1.operation_id, 5000)

    # Interrupt backtest
    cancel_operation(op1.operation_id)

    # Verify checkpoint exists
    checkpoint = checkpoint_service.load_checkpoint(op1.operation_id)
    assert checkpoint["current_bar_index"] == 5000
    assert len(checkpoint["position_manager"]["trade_history"]) > 0

    # Resume backtest
    op2 = backtest_service.resume_backtest(
        new_operation_id=generate_operation_id(),
        checkpoint_state=checkpoint
    )

    # Wait for completion
    wait_for_completion(op2.operation_id)

    # Verify processed 5000 more bars (not 10,000)
    assert op2.bars_processed == 5000
    assert op2.total_bars == 10000
```

**Success Criteria:**
- ✅ Backtest interrupted at bar 5000
- ✅ Checkpoint saved with bar=5000 state
- ✅ Resume continues from bar 5001
- ✅ Final results match non-interrupted backtest

---

## Phase 5: Production Readiness (2.5 days)

**Goal:** System ready for production deployment.

**Value Delivered:** Monitoring, cleanup, validation, documentation.

**Estimated Time:** 2.5 days

### Task 5.1: Cleanup, Validation & Monitoring (7 hours)

**Checklist:**
- [ ] Implement cleanup system
  - Create `ktrdr/checkpoint/cleanup.py`
  - Age-based cleanup (30-day retention)
  - Disk usage monitoring
  - Cron job configuration
- [ ] Implement version validation
  - `validate_checkpoint_version()` in `ktrdr/checkpoint/validation.py`
  - Version compatibility checking
  - Error handling for version mismatch
- [ ] Add monitoring & metrics
  - `CheckpointMetrics` class
  - Metrics: save_duration, load_duration, save_failures, disk_usage
  - Prometheus metrics export (if applicable)
  - Structured logging (checkpoint_id, operation_id, duration)
- [ ] Write comprehensive unit tests
  - Cleanup logic
  - Version validation
  - Metrics collection

**Acceptance Criteria:**
- ✅ Deletes checkpoints older than 30 days
- ✅ Monitors disk usage and logs warnings
- ✅ Rejects incompatible checkpoint versions
- ✅ Metrics collected for all operations
- ✅ Clear error messages logged

**Files:**
- `ktrdr/checkpoint/cleanup.py` (new)
- `ktrdr/checkpoint/validation.py` (new)
- `ktrdr/checkpoint/metrics.py` (new)
- `config/cron/checkpoint_cleanup.yaml` (new)
- `tests/unit/checkpoint/test_cleanup.py` (new)
- `tests/unit/checkpoint/test_validation.py` (new)
- `tests/unit/checkpoint/test_metrics.py` (new)

---

### Task 5.2: Error Handling & Performance Testing (5 hours)

**Checklist:**
- [ ] Test and handle error scenarios
  - Disk full scenario
  - DB connection loss scenario
  - Corrupted checkpoint scenario
  - Concurrent checkpoint writes
  - Graceful degradation (operations continue if checkpoint fails)
- [ ] Performance testing
  - Measure checkpoint save/load times
  - Test with large models (200 MB)
  - Verify training overhead < 1%
  - Verify backtesting overhead < 0.1%
- [ ] Write comprehensive tests
  - Integration tests for all error scenarios
  - Performance benchmarks

**Acceptance Criteria:**
- ✅ All error scenarios handled gracefully
- ✅ Operations continue even if checkpoint fails
- ✅ Save time < 620ms for 200 MB model
- ✅ Load time < 500ms for 200 MB model
- ✅ Training overhead < 1%, backtesting overhead < 0.1%

**Files:**
- `tests/integration/checkpoint/test_error_scenarios.py` (new)
- `tests/performance/test_checkpoint_performance.py` (new)

---

### Task 5.3: Documentation (3 hours)

**Checklist:**
- [ ] Add docstrings to all public APIs
  - CheckpointService, CheckpointPolicy, cleanup, validation
- [ ] Create user documentation
  - `docs/user-guide/resuming-operations.md` - CLI usage guide
  - CLI examples for resume, cleanup commands
- [ ] Create operations documentation
  - `docs/operations/checkpoint-maintenance.md` - maintenance guide
  - Cleanup procedures, monitoring, troubleshooting
- [ ] Update CLAUDE.md
  - Checkpoint system overview
  - Development guidelines
  - Testing patterns

**Acceptance Criteria:**
- ✅ All public APIs have clear docstrings
- ✅ User guide covers all CLI commands
- ✅ Operations guide covers cleanup, monitoring, troubleshooting
- ✅ CLAUDE.md updated with checkpoint info

**Files:**
- `ktrdr/checkpoint/*.py` (docstrings added)
- `docs/user-guide/resuming-operations.md` (new)
- `docs/operations/checkpoint-maintenance.md` (new)
- `CLAUDE.md` (modified)

---

### Phase 5 End-to-End Test

**Test Scenario:**
```python
def test_phase5_production_readiness():
    # 1. Version validation
    old_checkpoint = {"ktrdr_version": "0.4.0", ...}
    with pytest.raises(VersionMismatchError):
        validate_checkpoint_version(old_checkpoint)

    # 2. Cleanup job
    create_old_checkpoint("op_old_001", days_ago=31)
    run_cleanup_job()
    assert checkpoint_service.load_checkpoint("op_old_001") is None

    # 3. Metrics
    service.save_checkpoint(...)
    assert metrics.checkpoints_created_total.get() == 1
    assert metrics.checkpoint_save_duration_seconds.get() < 1.0

    # 4. Error handling
    fill_disk_to_capacity()
    service.save_checkpoint(...)  # Should not crash
    assert logs.contains("Failed to save checkpoint: disk full")

    # 5. Performance
    start = time.time()
    service.save_checkpoint(operation_id, large_model_state)
    duration = time.time() - start
    assert duration < 1.0  # 620ms target
```

**Success Criteria:**
- ✅ Version validation works
- ✅ Cleanup job runs successfully
- ✅ Metrics collected correctly
- ✅ Error handling graceful
- ✅ Performance targets met

---

## Testing Strategy

### Unit Tests
**Target Coverage:** >90%

- `tests/unit/checkpoint/` - All checkpoint components
- `tests/unit/training/` - Training checkpoint integration
- `tests/unit/backtesting/` - Backtesting checkpoint integration
- `tests/unit/operations/` - Operations service integration

**Run Command:**
```bash
make test-unit
```

---

### Integration Tests
**Target Coverage:** 100% of critical flows

- `tests/integration/checkpoint/` - Basic checkpoint CRUD
- `tests/integration/training/` - Training checkpoint & resume
- `tests/integration/backtesting/` - Backtest checkpoint & resume
- `tests/integration/api/` - Full API resume flow

**Run Command:**
```bash
make test-integration
```

---

### Performance Tests

- Checkpoint save time
- Checkpoint load time
- Training overhead
- Backtesting overhead

**Run Command:**
```bash
make test-performance
```

---

### Chaos Tests

- Kill API mid-checkpoint
- Disk full during checkpoint
- DB connection loss
- Corrupted checkpoint

**Run Command:**
```bash
make test-chaos
```

---

## Deployment Plan

### Development Environment
1. Run migrations: `./scripts/migrate_checkpoint_schema.sh`
2. Update config: `config/persistence.yaml`
3. Restart API: `./docker_dev.sh restart`

### Staging Environment
1. Run migrations
2. Deploy code
3. Run integration tests
4. Verify metrics

### Production Environment
1. **Pre-deployment checklist:**
   - [ ] Migrations tested in staging
   - [ ] All tests passing
   - [ ] Disk space verified (>10 GB free)
   - [ ] PostgreSQL performance baseline captured

2. **Deployment steps:**
   - [ ] Maintenance window scheduled
   - [ ] Run database migrations
   - [ ] Deploy API code
   - [ ] Deploy CLI code
   - [ ] Restart services
   - [ ] Verify health checks

3. **Post-deployment verification:**
   - [ ] Create test checkpoint
   - [ ] Resume test checkpoint
   - [ ] Verify cleanup trigger
   - [ ] Check metrics
   - [ ] Monitor logs

---

## Risk Mitigation

### Risk: Database Performance
**Mitigation:** Monitor write latency. We expect 0.003% utilization, so this is low risk.

### Risk: Disk Space Exhaustion
**Mitigation:** Cleanup job runs daily. Disk usage alerts at 80%.

### Risk: Checkpoint Corruption
**Mitigation:** ACID transactions + atomic file writes. Chaos tests verify.

### Risk: Feature Delay
**Mitigation:** Each phase delivers value. Can deploy Phase 1-3 first, defer Phase 4-5.

---

## Success Metrics

### Functional Metrics
- ✅ Resume success rate: >99%
- ✅ Checkpoint coverage: 100% of training/backtesting operations
- ✅ Data loss: 0%

### Performance Metrics
- ✅ Checkpoint overhead: <1%
- ✅ Storage usage: <2 GB peak
- ✅ Cleanup success: 100%

### User Experience Metrics
- ✅ Time to resume: <30 seconds
- ✅ User satisfaction: Positive feedback on resume reliability

---

## Rollback Plan

If issues discovered after deployment:

1. **Disable checkpointing:**
   ```yaml
   # config/persistence.yaml
   checkpointing:
     enabled: false
   ```

2. **Revert API code:**
   ```bash
   git revert <checkpoint-pr-commit>
   ./deploy.sh
   ```

3. **Keep schema:**
   - Don't rollback migrations (safe to keep tables)
   - Can re-enable later

---

## Timeline Summary

| Phase | Duration | End Date | Deliverable |
|-------|----------|----------|-------------|
| Phase 0: PostgreSQL + TimescaleDB Setup | 0.5 days | Day 0.5 | Database infrastructure ready |
| Phase 1: Core Infrastructure | 2 days | Day 2.5 | Basic checkpoint CRUD |
| Phase 2: Training Checkpoints | 2 days | Day 4.5 | Training resume works |
| Phase 3: Operations API + Recovery + Cancellation/Shutdown | 3 days | Day 7.5 | CLI resume + startup recovery + cleanup + checkpoint on cancel/shutdown |
| Phase 4: Backtesting | 1.5 days | Day 9 | Backtest resume works |
| Phase 5: Production | 2.5 days | Day 11.5 | Production ready |

**Total: 11.5 development days (~2.3 work weeks)**

---

## Dependencies

### External Dependencies
- PostgreSQL 12+ (already available)
- Filesystem with >10 GB free space

### Internal Dependencies
- None (checkpoint system is self-contained)

### Library Dependencies
- `psycopg2` (already in project)
- `pyyaml` (already in project)
- No new dependencies required

---

## Key Design Decisions

### 1. Startup Recovery (Critical)

**Problem:** The primary use case for checkpoints is **API crashes**. If the API crashes, operations are left in `RUNNING` status and can't be resumed.

**Solution:** On API startup, automatically mark all `RUNNING` operations as `FAILED`.

**Implementation:**
```python
@app.on_event("startup")
async def startup_recovery():
    """Recover interrupted operations on API startup."""
    operations_service = get_operations_service()
    recovered = await operations_service.recover_interrupted_operations()
    logger.info(f"Startup recovery: {recovered} operations marked as FAILED")
```

**Rationale:**
- ✅ Handles the primary use case (API crash)
- ✅ Simple, explicit
- ✅ Makes interrupted operations immediately resumable
- ✅ Clear semantic: "operation didn't complete = failed"

---

### 2. Resumable Operations

**Operations can be resumed only if:**
- Status is `FAILED` OR `CANCELLED`
- Checkpoint exists for the operation

**Operations cannot be resumed:**
- `RUNNING` operations (before startup recovery runs)
- `COMPLETED` operations (already done)
- `PENDING` operations (never started)

**After startup recovery:**
- All orphaned `RUNNING` → `FAILED` → resumable ✅

---

### 3. Checkpoint Cleanup Strategy

**Automatic Cleanup:**
1. **On completion:** Checkpoint deleted when operation completes successfully
2. **On resume:** Original operation's checkpoint deleted after new operation starts
3. **Age-based:** Checkpoints older than 30 days deleted automatically

**Manual Cleanup:**
1. **Individual:** `ktrdr operations delete-checkpoint <id>`
2. **Bulk cancelled:** `ktrdr operations cleanup-cancelled`
3. **Bulk old:** `ktrdr operations cleanup-old --days 7`

**Rationale:**
- Prevents accumulation of cancelled operation checkpoints
- Gives user control over disk space
- 30-day safety net prevents forever accumulation

---

### 4. Operations List Enhancement

**Before:** Only shows in-memory operations (lost on API restart)

**After:** Shows operations from database with checkpoint metadata:
- `has_checkpoint`: bool
- `checkpoint_size_mb`: float
- `checkpoint_age_days`: int

**Example:**
```bash
$ ktrdr operations list
ID                          | Status    | Progress     | Checkpoint
op_training_20250117_100000 | FAILED    | Epoch 45/100 | 52.3 MB (2 days ago)
op_training_20250117_140000 | COMPLETED | Epoch 100/100| None
op_backtest_20250117_150000 | CANCELLED | Bar 5000/10000| 4.8 MB (1 day ago)
```

---

## Next Steps

1. **Review & approve** this implementation plan
2. **Create GitHub issues** for each phase (use task lists in plan)
3. **Assign developer** to Phase 1
4. **Setup project board** to track progress
5. **Schedule kickoff meeting** to discuss API crash scenarios

---

**End of Implementation Plan**
