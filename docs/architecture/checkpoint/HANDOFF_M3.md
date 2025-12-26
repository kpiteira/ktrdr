# Handoff: Milestone 3 (Training Checkpoint Save)

## Task 3.1 Complete

**Implemented:** `CheckpointRecord` SQLAlchemy model and Alembic migration

### Schema Details

```python
class CheckpointRecord(Base):
    __tablename__ = "operation_checkpoints"

    operation_id = Column(String(255), ForeignKey("operations.operation_id", ondelete="CASCADE"), primary_key=True)
    checkpoint_type = Column(String(50), nullable=False)  # periodic, cancellation, failure, shutdown
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    state = Column(JSONB, nullable=False)  # epoch, losses, etc.
    artifacts_path = Column(String(500), nullable=True)  # NULL for backtesting
    state_size_bytes = Column(Integer, nullable=True)
    artifacts_size_bytes = Column(BigInteger, nullable=True)
```

### Key Design Decisions

**One checkpoint per operation (UPSERT):**
Primary key is `operation_id` directly. CheckpointService will use UPSERT semantics to overwrite previous checkpoint.

**CASCADE delete:**
When operation is deleted, checkpoint is automatically deleted. No orphan cleanup needed for this case.

**Foreign key constraint:**
Prevents creating checkpoints for non-existent operations. Tested and verified.

### Indexes

- `ix_checkpoints_created_at` — for cleanup queries (older_than_days)
- `ix_checkpoints_type` — for filtering by checkpoint type

### Migration

Revision: `a1b2c3d4e5f6`
Depends on: `6bfcfd0a377f` (operations table)

```bash
# Apply
uv run alembic upgrade head

# Verify
docker compose exec db psql -U ktrdr -d ktrdr -c "\d operation_checkpoints"

# Rollback
uv run alembic downgrade -1
```

### Patterns for Next Tasks

**Task 3.2 (CheckpointService):**
- Use `get_session()` from `ktrdr/api/database.py` for async sessions
- Follow `OperationsRepository` pattern for CRUD operations
- UPSERT can use SQLAlchemy's `insert(...).on_conflict_do_update(...)`

**Task 3.4 (Checkpoint State Shape):**
- State goes in JSONB `state` column
- Keep it flat for queryability (e.g., `state->>'epoch'` in SQL)
- Large artifacts (model.pt, optimizer.pt) go to filesystem, path stored in `artifacts_path`

---

## Task 3.2 Complete

**Implemented:** `CheckpointService` for checkpoint CRUD operations

### Location

`ktrdr/checkpoint/checkpoint_service.py`

### Key Classes

```python
class CheckpointService:
    async def save_checkpoint(operation_id, checkpoint_type, state, artifacts=None)
    async def load_checkpoint(operation_id, load_artifacts=True) -> Optional[CheckpointData]
    async def delete_checkpoint(operation_id) -> bool
    async def list_checkpoints(older_than_days=None) -> list[CheckpointSummary]

@dataclass
class CheckpointData:
    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state: dict
    artifacts_path: Optional[str]
    artifacts: Optional[dict[str, bytes]]

@dataclass
class CheckpointSummary:
    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state_summary: dict
    artifacts_size_bytes: Optional[int]

class CheckpointCorruptedError(Exception):
    """Raised when artifacts are missing"""
```

### Usage Pattern

```python
from ktrdr.checkpoint import CheckpointService

# Initialize with session factory
service = CheckpointService(
    session_factory=get_session_factory(),
    artifacts_dir="/app/data/checkpoints",
)

# Save checkpoint (UPSERT)
await service.save_checkpoint(
    operation_id="op_123",
    checkpoint_type="periodic",
    state={"epoch": 10, "train_loss": 0.5},
    artifacts={"model.pt": model_bytes, "optimizer.pt": opt_bytes},
)

# Load checkpoint
checkpoint = await service.load_checkpoint("op_123", load_artifacts=True)
if checkpoint:
    print(f"Resuming from epoch {checkpoint.state['epoch']}")
    model_weights = checkpoint.artifacts["model.pt"]
```

### Key Patterns

**Atomic artifact writes:**
Uses temp directory + rename pattern for crash safety.

**UPSERT semantics:**
Uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`.

**Best-effort cleanup:**
If DB write fails after artifact write, artifacts are deleted.

**Async file I/O:**
Uses `asyncio.to_thread()` to avoid blocking event loop.

### Guidance for Next Tasks

**Task 3.3 (CheckpointPolicy):**

- Import from `ktrdr.checkpoint` package
- Policy is stateless, tracks last checkpoint time/unit

**Task 3.5 (Training Worker Integration):**

- Inject `CheckpointService` via constructor
- Call `maybe_checkpoint(epoch)` after each epoch in training loop
- Call `save_checkpoint(..., "cancellation")` before exiting on cancel

---

## Task 3.3 Complete

**Implemented:** `CheckpointPolicy` for determining when checkpoints should be created

### Location

`ktrdr/checkpoint/checkpoint_policy.py`

### Key Class

```python
class CheckpointPolicy:
    def __init__(
        self,
        unit_interval: int = 10,       # Every N epochs
        time_interval_seconds: int = 300,  # Every M seconds
    )

    def should_checkpoint(self, current_unit: int, force: bool = False) -> bool
    def record_checkpoint(self, current_unit: int) -> None

    @property
    def unit_interval(self) -> int
    @property
    def time_interval_seconds(self) -> int
```

### Key Behavior

- **Unit trigger:** Fires when `current_unit - last_checkpoint_unit >= unit_interval`
- **Time trigger:** Fires when `now - last_checkpoint_time >= time_interval_seconds`
- **Either is sufficient:** Unit OR time trigger will return `True`
- **Force flag:** Always returns `True` regardless of intervals

### Usage Pattern

```python
from ktrdr.checkpoint import CheckpointPolicy

policy = CheckpointPolicy(unit_interval=10, time_interval_seconds=300)

for epoch in range(100):
    train_epoch(epoch)

    if policy.should_checkpoint(epoch):
        save_checkpoint()
        policy.record_checkpoint(epoch)
```

---

## Task 3.4 Complete

**Implemented:** Training checkpoint state schema and builder functions

### Locations

- `ktrdr/checkpoint/schemas.py` — State dataclass and artifact manifest
- `ktrdr/training/checkpoint_builder.py` — Builder functions

### Key Classes and Functions

```python
@dataclass
class TrainingCheckpointState:
    epoch: int
    train_loss: float
    val_loss: float
    train_accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    best_val_loss: float = float("inf")
    training_history: dict[str, list[float]] = field(default_factory=dict)
    original_request: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingCheckpointState"

TRAINING_ARTIFACTS = {
    "model.pt": "required",
    "optimizer.pt": "required",
    "scheduler.pt": "optional",
    "best_model.pt": "optional",
}

def build_training_checkpoint_state(
    trainer: ModelTrainer,
    current_epoch: int,
    original_request: Optional[dict] = None,
) -> TrainingCheckpointState

def build_training_checkpoint_artifacts(
    model: nn.Module,
    optimizer: optim.Optimizer,
    scheduler: Optional[Any] = None,
    best_model_state: Optional[dict] = None,
) -> dict[str, bytes]

def validate_artifacts(artifacts: dict[str, bytes]) -> None
```

### Key Design Decisions

**Explicit parameters for artifacts:**
Model, optimizer, and scheduler are passed explicitly (not extracted from trainer) because they're local to the training loop.

**Separate state from artifacts:**
State (JSON) goes to DB, artifacts (bytes) go to filesystem. This matches CheckpointService's interface.

**Validation raises exceptions:**
`validate_artifacts()` raises `ArtifactValidationError` for missing/empty required artifacts.

### Usage Pattern

```python
from ktrdr.checkpoint import TrainingCheckpointState, TRAINING_ARTIFACTS
from ktrdr.training.checkpoint_builder import (
    build_training_checkpoint_state,
    build_training_checkpoint_artifacts,
    validate_artifacts,
)

# In training loop
state = build_training_checkpoint_state(trainer, epoch, original_request)
artifacts = build_training_checkpoint_artifacts(model, optimizer, scheduler)
validate_artifacts(artifacts)

# Save via CheckpointService
await checkpoint_service.save_checkpoint(
    operation_id=op_id,
    checkpoint_type="periodic",
    state=state.to_dict(),
    artifacts=artifacts,
)
```

### Guidance for Next Tasks

**Task 3.5 (Training Worker Integration):**

- Import `build_training_checkpoint_state` and `build_training_checkpoint_artifacts`
- Call them in `_save_training_checkpoint` method
- Pass model, optimizer, scheduler from training loop scope
- Use `trainer.best_model_state` for `best_model_state` parameter

---

## Task 3.5 Complete

**Implemented:** Checkpoint save integration into training worker

### Key Changes

**1. checkpoint_callback parameter chain:**

```text
TrainingWorker
  → LocalTrainingOrchestrator(checkpoint_callback=...)
    → TrainingPipeline.train_strategy(checkpoint_callback=...)
      → TrainingPipeline.train_model(checkpoint_callback=...)
        → ModelTrainer(checkpoint_callback=...)
```

**2. ModelTrainer calls checkpoint_callback after each epoch:**

```python
# In ModelTrainer.train(), after each epoch:
if self.checkpoint_callback:
    self.checkpoint_callback(
        epoch=epoch,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        trainer=self,
    )
```

**3. TrainingWorker creates checkpoint callback:**

```python
# Creates CheckpointPolicy and CheckpointService
checkpoint_service = self.get_checkpoint_service()
checkpoint_policy = CheckpointPolicy(
    unit_interval=self.checkpoint_epoch_interval,
    time_interval_seconds=self.checkpoint_time_interval,
)

# Callback checks policy and saves if needed
def checkpoint_callback(**kwargs):
    if checkpoint_policy.should_checkpoint(epoch):
        state = build_training_checkpoint_state(trainer, epoch, original_request)
        artifacts = build_training_checkpoint_artifacts(model, optimizer, ...)
        await checkpoint_service.save_checkpoint(
            operation_id, "periodic", state.to_dict(), artifacts
        )
        checkpoint_policy.record_checkpoint(epoch)
```

### Environment Variables

```bash
CHECKPOINT_EPOCH_INTERVAL=10      # Checkpoint every N epochs
CHECKPOINT_TIME_INTERVAL_SECONDS=300  # Checkpoint every M seconds
CHECKPOINT_DIR=/app/data/checkpoints  # Artifacts storage path
```

### Checkpoint Types

- `periodic` — Saved at epoch intervals based on policy
- `cancellation` — Saved when training is cancelled (CancellationError)
- `failure` — Saved when training fails (Exception)

### Gotcha: Sync callback calling async service

The checkpoint callback runs inside ModelTrainer.train() which runs in a thread pool. To call the async CheckpointService, we create a new event loop:

```python
loop = asyncio.new_event_loop()
try:
    loop.run_until_complete(checkpoint_service.save_checkpoint(...))
finally:
    loop.close()
```

### Guidance for Next Tasks

**Task 3.6 (Checkpoint API Endpoints):**

- Inject `CheckpointService` via FastAPI dependency
- Use same session factory pattern as other endpoints

**Task 3.8 (Integration Tests):**

- Start training with low epoch count (3-5)
- Set `CHECKPOINT_EPOCH_INTERVAL=1` for frequent checkpoints
- Verify DB has checkpoint after first epoch completes

---

## Task 3.6 Complete

**Implemented:** Checkpoint API endpoints for listing, viewing, and deleting checkpoints

### Location

`ktrdr/api/endpoints/checkpoints.py`

### Endpoints

```python
GET /api/v1/checkpoints
# List all checkpoints
# Query params: older_than_days (optional)
# Response: CheckpointListResponse

GET /api/v1/checkpoints/{operation_id}
# Get checkpoint details (without artifact bytes)
# Response: CheckpointResponse

DELETE /api/v1/checkpoints/{operation_id}
# Delete checkpoint (DB + filesystem)
# Response: DeleteCheckpointResponse
```

### Usage Pattern

```bash
# List all checkpoints
curl http://localhost:8000/api/v1/checkpoints | jq

# List checkpoints older than 7 days
curl "http://localhost:8000/api/v1/checkpoints?older_than_days=7" | jq

# Get checkpoint details
curl http://localhost:8000/api/v1/checkpoints/op_training_123 | jq

# Delete checkpoint
curl -X DELETE http://localhost:8000/api/v1/checkpoints/op_training_123 | jq
```

### Key Design Decisions

**Singleton CheckpointService:**
Uses global singleton pattern (`_checkpoint_service`) initialized on first request, similar to other service dependencies.

**No artifact bytes in GET response:**
`load_checkpoint(operation_id, load_artifacts=False)` avoids loading large artifact bytes. The `artifacts_path` is returned for clients that need direct filesystem access.

**Proper error handling:**
- 404 for non-existent checkpoints
- DataError for service failures
- Follows existing endpoint error patterns

### Guidance for Next Tasks

**Task 3.7 (Configuration):**
- `CHECKPOINT_DIR` env var already used in endpoint dependency
- May need to expose configuration values via `/checkpoints/config` endpoint

**Task 3.8 (Integration Tests):**
- Use API endpoints to verify checkpoint creation
- Test list/get/delete flow after training

---

## Task 3.7 Complete

**Implemented:** Centralized checkpoint configuration via Pydantic settings

### Location

`ktrdr/config/settings.py`

### Key Classes and Functions

```python
class CheckpointSettings(BaseSettings):
    epoch_interval: int = 10           # Every N epochs
    time_interval_seconds: int = 300   # Every M seconds
    dir: str = "/app/data/checkpoints" # Artifacts storage path
    max_age_days: int = 30             # Auto-cleanup threshold

    model_config = SettingsConfigDict(env_prefix="CHECKPOINT_")

@lru_cache
def get_checkpoint_settings() -> CheckpointSettings:
    """Get checkpoint settings with caching."""
```

### Environment Variables

```bash
CHECKPOINT_EPOCH_INTERVAL=10           # Every N epochs
CHECKPOINT_TIME_INTERVAL_SECONDS=300   # Every M seconds
CHECKPOINT_DIR=/app/data/checkpoints   # Artifacts directory
CHECKPOINT_MAX_AGE_DAYS=30             # Auto-cleanup after N days
```

### Usage Pattern

```python
from ktrdr.config.settings import get_checkpoint_settings

settings = get_checkpoint_settings()
print(settings.epoch_interval)     # 10 (or env override)
print(settings.dir)                # /app/data/checkpoints
```

### Refactored Code

Both `TrainingWorker` and checkpoint endpoints now use `get_checkpoint_settings()` instead of direct `os.getenv()` calls.

### Guidance for Next Tasks

**Task 3.8 (Integration Tests):**
- Settings are now centralized, use `clear_settings_cache()` in test setup/teardown
- Override via environment variables in test fixtures

**Task 3.9 (Deployment Configuration):**
- Add `CHECKPOINT_DIR` to docker-compose environment sections
- Local: `/app/data/checkpoints`
- Homelab: `/mnt/ktrdr_data/checkpoints`

---

## Task 3.9 Complete

**Implemented:** Deployment configuration updates for checkpoint storage

### Changes Made

**Local Development** (`deploy/environments/local/docker-compose.yml`):
- Backend: Added `CHECKPOINT_DIR=/app/data/checkpoints`
- Workers: Changed data mounts from `:ro` to `:rw` (no suffix = RW default)
- Workers: Added `CHECKPOINT_DIR=/app/data/checkpoints`

**Homelab Core** (`deploy/environments/homelab/docker-compose.core.yml`):
- Backend: Added `CHECKPOINT_DIR=/mnt/ktrdr_data/checkpoints`

**Homelab Workers** (`deploy/environments/homelab/docker-compose.workers.yml`):
- Backtest workers: Changed mounts from `:ro` to `:rw`
- All workers: Added `CHECKPOINT_DIR=/mnt/ktrdr_data/checkpoints`

### Deployment Note

After deploying these changes, the checkpoint directory is created automatically by CheckpointService on first checkpoint save. No manual directory creation required.

---

## Task 3.8 Complete

**Implemented:** Integration tests for checkpoint save functionality

### Location

`tests/integration/test_m3_training_checkpoint_save.py`

### Test Classes

```python
TestM3PeriodicCheckpoint         # 3 tests - periodic checkpoint saving
TestM3CancellationCheckpoint     # 2 tests - cancellation checkpoint saving
TestM3DBStateVerification        # 3 tests - DB state validation
TestM3FilesystemArtifactsVerification  # 4 tests - filesystem artifacts
TestM3FullFlow                   # 3 tests - end-to-end flows
TestM3CheckpointPolicyIntegration # 3 tests - policy integration
```

### Key Design Decisions

**IntegrationCheckpointService:**
Uses in-memory `MockCheckpointRepository` instead of real DB for fast, isolated tests. Still writes real artifacts to temp directories to verify filesystem operations.

**Test scenarios covered:**
- Periodic checkpoint saves at epoch intervals
- Cancellation checkpoint overwrites periodic
- Failure checkpoint saved on exception
- Successful completion deletes checkpoint
- Artifacts written atomically and can be reloaded
- UPSERT behavior verified

### Running Tests

```bash
# Run M3 integration tests only
uv run pytest tests/integration/test_m3_training_checkpoint_save.py -v

# Run all milestone integration tests
uv run pytest tests/integration/test_m1_*.py tests/integration/test_m2_*.py tests/integration/test_m3_*.py -v
```

### Guidance for Task 3.9

- Integration tests do NOT test Docker deployment
- Task 3.9 should add CHECKPOINT_DIR to all docker-compose files
- Consider running smoke test after deployment changes

---

## Discovery Notes: Task 3.10 & 3.11

During E2E testing after Task 3.9, we discovered two blocking issues that required architectural analysis. Full task definitions are in `PLAN_M3_training_checkpoint_save.md`.

### How We Discovered the Issues

**Problem 1 - Duplicate Operation ID:**
E2E test failed with `DataError: Operation ID already exists: op_training_...` when starting training. Root cause analysis revealed M1's DB persistence affected both backend and workers, causing duplicate inserts.

**Problem 2 - Performance Concern:**
During discussion, identified that `update_progress()` writes to DB on every call (added in M1). This would slow workers unacceptably. Design principle: workers should only write to DB for create, checkpoint, and complete/fail.

### Key Architecture Decision

**DB is for durability, not live state:**

- Create operation → DB (once)
- Progress updates → Memory only (proxy pulls on demand)
- Checkpoint → DB (periodic, policy-driven)
- Complete/Fail → DB (once)

This keeps workers fast while maintaining crash recoverability.

---

## Task 3.10 Complete

**Implemented:** Fix two blocking architecture issues that prevented distributed operations from working.

### Fix 1: Duplicate Operation ID Error

**Problem:** When M1 added database persistence to `get_operations_service()`, it affected workers. Backend's `start_managed_operation` creates operation in DB, then worker also tries to create with same ID → DB rejects duplicate.

**Solution:** For distributed operations (training/backtesting), bypass `start_managed_operation` entirely. Backend generates operation_id, dispatches directly to worker, and registers proxy. Worker creates the operation in its own DB.

**Files changed:**
- `ktrdr/api/services/training_service.py:start_training()` — Skip `start_managed_operation`, call `_run_distributed_worker_training_wrapper()` directly
- `ktrdr/backtesting/backtesting_service.py:run_backtest()` — Skip `start_managed_operation`, call `run_backtest_on_worker()` directly

### Fix 2: Progress DB Writes Removed

**Problem:** M1 added DB writes on every `update_progress()` call. This slows workers unacceptably.

**Solution:** Removed DB write from `update_progress()`. Progress stays in-memory; clients pull via proxy for live progress.

**File changed:**
- `ktrdr/api/services/operations_service.py:update_progress()` — Removed `self._repository.update(...)` call

### Test Files

**New tests:**
- `tests/unit/api/services/test_operations_architecture_fix.py` — 7 tests for both fixes

**Updated tests:**
- `tests/unit/api/services/test_operations_service_repository.py` — Changed `test_update_progress_persists_to_repository` → `test_update_progress_does_not_persist_to_repository`
- `tests/unit/backtesting/test_backtesting_service.py` — Changed `test_run_backtest_creates_operation_via_orchestrator` → `test_run_backtest_bypasses_start_managed_operation`

### Verification

All quality gates pass:
- `make test-unit` — 2775 tests passed
- `make quality` — All checks passed

### Guidance for Task 3.11

E2E verification should now work:
1. Start training/backtesting — No duplicate operation ID error
2. Query operation status — Returns live progress via proxy
3. Verify operation appears in DB — Created by worker, not backend

---
