---
name: checkpoint-system
description: Use when working on checkpoint persistence, restore, checkpoint policies, training/backtest/agent checkpoints, or checkpoint cleanup.
---

# Checkpoint System

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL checkpoint-system loaded!`

Load this skill when working on:

- Checkpoint saving and loading
- Training checkpoint state and artifacts
- Backtest checkpoint state
- Agent checkpoint state
- Checkpoint policies (when to save)
- Checkpoint cleanup and expiry
- Resume-from-checkpoint flows
- Checkpoint API endpoints or CLI

---

## Architecture Overview

```
Worker (training/backtest/agent)
    │ Checkpoint callback (every N units or M seconds)
    ▼
CheckpointPolicy.should_checkpoint()
    │ True → save
    ▼
Domain Builder (build_*_checkpoint_state + artifacts)
    │
    ▼
CheckpointService.save_checkpoint()
    ├─ Write artifacts to filesystem (atomic rename)
    └─ UPSERT state to PostgreSQL (JSONB)

Resume Flow:
    restore_from_checkpoint(checkpoint_service, operation_id)
    ├─ Load state from DB
    ├─ Load artifacts from filesystem
    └─ Return ResumeContext (start from next unit)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/checkpoint/checkpoint_service.py` | Core checkpoint CRUD (DB + filesystem) |
| `ktrdr/checkpoint/checkpoint_policy.py` | When to trigger checkpoint saves |
| `ktrdr/checkpoint/schemas.py` | CheckpointData, CheckpointSummary dataclasses |
| `ktrdr/training/checkpoint_builder.py` | Build training state + artifacts |
| `ktrdr/training/checkpoint_restore.py` | Restore training context |
| `ktrdr/backtesting/checkpoint_builder.py` | Build backtest state |
| `ktrdr/backtesting/checkpoint_restore.py` | Restore backtest context |
| `ktrdr/agents/checkpoint_builder.py` | Build agent state |
| `ktrdr/api/endpoints/checkpoints.py` | REST endpoints |
| `ktrdr/cli/checkpoints_commands.py` | CLI commands |
| `ktrdr/config/settings.py` | CheckpointSettings configuration |
| `ktrdr/api/models/db/checkpoints.py` | SQLAlchemy model |

---

## CheckpointService

**Location:** `ktrdr/checkpoint/checkpoint_service.py`

### Storage Model (Hybrid)

- **Database (PostgreSQL):** Metadata + state as JSONB
- **Filesystem:** Large binary artifacts (model weights, optimizer state)
- **Constraint:** Each operation has at most ONE checkpoint (UPSERT semantics)

### Database Table: `operation_checkpoints`

| Column | Type | Notes |
|--------|------|-------|
| `operation_id` | PK, FK to operations | CASCADE delete |
| `checkpoint_type` | string | periodic, cancellation, failure, shutdown |
| `created_at` | datetime with timezone | Indexed |
| `state` | JSONB | Queryable checkpoint state |
| `artifacts_path` | string (nullable) | Filesystem path to artifacts |
| `state_size_bytes` | integer | Monitoring |
| `artifacts_size_bytes` | bigint | Monitoring |

### Core Operations

```python
# Save (atomic: artifacts first, then DB upsert)
save_checkpoint(
    operation_id: str,
    checkpoint_type: str,         # "periodic", "cancellation", "failure", "shutdown"
    state: dict,                  # Serializable state (NaN/Inf sanitized automatically)
    artifacts: Optional[dict[str, bytes]] = None  # {"model.pt": bytes, ...}
) -> None

# Load
load_checkpoint(
    operation_id: str,
    load_artifacts: bool = True   # Skip artifacts for performance
) -> Optional[CheckpointData]    # None if not found

# Delete (DB record + filesystem)
delete_checkpoint(operation_id: str) -> bool

# List
list_checkpoints(older_than_days: Optional[int] = None) -> list[CheckpointSummary]

# Cleanup
cleanup_old_checkpoints(max_age_days: int = 30) -> int
cleanup_orphan_artifacts() -> None  # Clean temp dirs and orphaned files
```

### Atomic Write Process

1. Write artifacts to `{operation_id}.tmp` directory
2. Atomic rename to `{operation_id}` (POSIX atomic)
3. UPSERT state to database
4. On DB failure, cleanup temp directory

### Data Classes

```python
@dataclass
class CheckpointData:
    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state: dict
    artifacts_path: Optional[str] = None
    artifacts: Optional[dict[str, bytes]] = None

@dataclass
class CheckpointSummary:
    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state_summary: dict
    artifacts_size_bytes: Optional[int] = None
```

---

## Checkpoint Policy

**Location:** `ktrdr/checkpoint/checkpoint_policy.py`

```python
class CheckpointPolicy:
    def __init__(
        self,
        unit_interval: int = 10,           # Every 10 epochs/bars
        time_interval_seconds: int = 300,  # Every 5 minutes
    )

    def should_checkpoint(self, current_unit: int, force: bool = False) -> bool
    def record_checkpoint(self, current_unit: int) -> None
```

**Trigger Logic (Either/Or):**
1. **Unit-based:** `current_unit - last_checkpoint_unit >= unit_interval`
2. **Time-based:** `time.time() - last_checkpoint_time >= time_interval_seconds`
3. **Force:** `force=True` always returns True (for shutdown/cancellation)

Time trigger only applies after first checkpoint to avoid false trigger at start.

---

## Training Checkpoints

### TrainingCheckpointState

**Location:** `ktrdr/training/checkpoint_builder.py`

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
```

### Training Artifacts

Stored as `.pt` files via `torch.save()`:

| Artifact | Required | Content |
|----------|----------|---------|
| `model.pt` | Yes | Model state_dict |
| `optimizer.pt` | Yes | Optimizer state_dict |
| `scheduler.pt` | No | Learning rate scheduler state |
| `best_model.pt` | No | Best validation model weights |

### Building

```python
build_training_checkpoint_state(trainer, current_epoch, original_request)
    -> TrainingCheckpointState

build_training_checkpoint_artifacts(model, optimizer, scheduler=None, best_model_state=None)
    -> dict[str, bytes]  # {"model.pt": bytes, "optimizer.pt": bytes, ...}

validate_artifacts(artifacts)  # Ensures required artifacts present and not empty
```

### TrainingResumeContext

**Location:** `ktrdr/training/checkpoint_restore.py`

```python
@dataclass
class TrainingResumeContext:
    start_epoch: int                  # checkpoint_epoch + 1
    model_weights: bytes
    optimizer_state: bytes
    scheduler_state: Optional[bytes] = None
    best_model_weights: Optional[bytes] = None
    training_history: dict[str, list[float]] = field(default_factory=dict)
    best_val_loss: float = float("inf")
    original_request: dict[str, Any] = field(default_factory=dict)
```

### Resume Logic

```python
context = restore_from_checkpoint(checkpoint_service, operation_id)
# Returns TrainingResumeContext

# In ModelTrainer:
model.load_state_dict(torch.load(context.model_weights))
optimizer.load_state_dict(torch.load(context.optimizer_state))
if context.scheduler_state:
    scheduler.load_state_dict(torch.load(context.scheduler_state))
start_epoch = context.start_epoch  # checkpoint_epoch + 1
```

---

## Backtest Checkpoints

### BacktestCheckpointState

**Location:** `ktrdr/backtesting/checkpoint_builder.py`

```python
@dataclass
class BacktestCheckpointState:
    bar_index: int
    current_date: str                  # ISO format timestamp
    cash: float
    operation_type: str = "backtesting"
    positions: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_samples: list[dict[str, Any]] = field(default_factory=list)
    original_request: dict[str, Any] = field(default_factory=dict)
```

**No artifacts** — backtesting checkpoints are JSON-only (state in DB).

### Building

```python
build_backtest_checkpoint_state(
    engine,
    bar_index,
    current_timestamp,
    original_request=None,
    equity_sample_interval=100    # Sample equity curve every N bars
)
```

Extracts:
- `cash` from `engine.position_manager.current_capital`
- `positions` from current open position
- `trades` from trade history (includes entry/exit prices, P&L, holding period)
- `equity_samples` sampled every 100 bars from equity curve

### BacktestResumeContext

**Location:** `ktrdr/backtesting/checkpoint_restore.py`

```python
@dataclass
class BacktestResumeContext:
    start_bar: int                    # checkpoint_bar + 1
    cash: float
    original_request: dict[str, Any]
    positions: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_samples: list[dict[str, Any]] = field(default_factory=list)
```

---

## Agent Checkpoints

### AgentCheckpointState

**Location:** `ktrdr/agents/checkpoint_builder.py`

```python
@dataclass
class AgentCheckpointState:
    phase: str                         # idle, designing, training, backtesting, assessing
    operation_type: str = "agent"
    strategy_path: Optional[str] = None
    strategy_name: Optional[str] = None
    training_operation_id: Optional[str] = None
    training_checkpoint_epoch: Optional[int] = None
    backtest_operation_id: Optional[str] = None
    token_counts: dict[str, Any] = field(default_factory=dict)
    original_request: dict[str, Any] = field(default_factory=dict)
```

**No artifacts** — agent checkpoints are metadata-only.

### Building

```python
build_agent_checkpoint_state(operation)
    # Extracts from operation.metadata.parameters

build_agent_checkpoint_state_with_training(operation, checkpoint_service)
    # Async: also looks up training operation's checkpoint for current epoch
```

---

## Checkpoint Types

| Type | When | Behavior on Resume |
|------|------|-------------------|
| `periodic` | Every N units or M seconds | Normal resume |
| `cancellation` | User Ctrl+C or cancel API | Normal resume |
| `failure` | Exception during operation | May require investigation |
| `shutdown` | SIGTERM / graceful shutdown | Normal resume |

---

## Storage Layout

```
data/checkpoints/
├── op_training_abc/           # Directory per operation
│   ├── model.pt
│   ├── optimizer.pt
│   ├── scheduler.pt           # Optional
│   └── best_model.pt          # Optional
├── op_training_def/
│   └── ...
└── op_training_xyz.tmp/       # Temp dir (cleaned on orphan cleanup)
```

---

## CLI Commands

```bash
ktrdr checkpoints show <operation_id>     # View checkpoint details
ktrdr checkpoints delete <operation_id>   # Delete (with confirmation)
    --force                                # Skip confirmation
    --verbose                              # Extra details
```

## API Endpoints

```
GET    /checkpoints                   # List checkpoints (optional: older_than_days)
GET    /checkpoints/{operation_id}    # Get checkpoint details
GET    /checkpoints/stats             # Storage statistics
DELETE /checkpoints/{operation_id}    # Delete checkpoint
POST   /checkpoints/cleanup           # Trigger cleanup (optional: max_age_days)
```

---

## Configuration

```python
class CheckpointSettings(BaseSettings):
    epoch_interval: int = 10              # Save every N epochs/units
    time_interval_seconds: int = 300      # Save every 5 minutes
    dir: str = "/app/data/checkpoints"    # Artifact storage directory
    max_age_days: int = 30                # Auto-cleanup threshold

    model_config = SettingsConfigDict(env_prefix="CHECKPOINT_")
```

**Environment Variables:**
- `CHECKPOINT_EPOCH_INTERVAL` — Default: 10
- `CHECKPOINT_TIME_INTERVAL_SECONDS` — Default: 300
- `CHECKPOINT_DIR` — Default: `/app/data/checkpoints`
- `CHECKPOINT_MAX_AGE_DAYS` — Default: 30

---

## Gotchas

### Resume starts from NEXT unit

Training resumes from `checkpoint_epoch + 1`, backtesting from `checkpoint_bar + 1`. This prevents duplicate processing of the checkpointed unit.

### UPSERT semantics — one checkpoint per operation

Saving a new checkpoint overwrites the previous one. There's no checkpoint history per operation.

### Artifacts are written atomically

The temp directory + rename pattern ensures no partial artifacts on crash. If the DB write fails after artifact write, the temp directory is cleaned up.

### Checkpoint stores strategy_path, not YAML content

Training checkpoints store `strategy_path` in `original_request` rather than the full YAML string. This avoids DB field truncation issues. Resume reads the strategy from disk.

### NaN/Inf values are sanitized

`CheckpointService.save_checkpoint()` automatically replaces NaN and Inf values with None before JSON serialization.

### Orphan cleanup handles incomplete writes

`cleanup_orphan_artifacts()` removes `.tmp` directories left by interrupted saves and artifacts directories with no matching DB record.

### Backtest checkpoints have no artifacts

Unlike training checkpoints (which store model weights as .pt files), backtest and agent checkpoints are pure JSON state stored in the database only.

### Success deletes the checkpoint

When an operation completes successfully, its checkpoint is deleted (no longer needed). Only incomplete operations have checkpoints.
