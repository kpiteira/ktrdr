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
