# Checkpoint System - Architecture

This document describes HOW the checkpoint system will be built to satisfy the [Design Spec](checkpoint-simplified-spec.md).

---

## Storage Strategy

### Decision: Hybrid Storage (DB + Filesystem)

Applies to **both training and backtesting** checkpoints.

**Metadata & State:** PostgreSQL

- Operation ID, checkpoint type, timestamps
- JSON state (small, queryable, transactional)

**Artifacts:** Filesystem (training only)

- Model weights (model.pt, optimizer.pt) - 100-500MB each
- Location: `data/checkpoints/artifacts/{operation_id}/`
- Shared via Docker volume or NFS for distributed access

**Training State (in DB JSON):**

- Epoch number, batch index
- Training/validation loss and accuracy
- Learning rate, training history

**Training Artifacts (on filesystem):**

- model.pt, optimizer.pt, scheduler.pt, best_model.pt

**Backtesting State (in DB JSON only, no artifacts):**

- Current bar index
- Portfolio state (cash, positions)
- Trade history, equity curve

> **Implementation Task:** Analyze whether this data is NECESSARY and SUFFICIENT for successful restore. This analysis must be done as a prep task before coding - do not assume this list is complete.

**Why not just DB?**

- PostgreSQL BYTEA/JSONB not designed for 500MB blobs
- Filesystem is faster for large binary reads/writes
- Easier to inspect/debug artifacts on disk

**Why not just filesystem?**

- Need queryable metadata (list checkpoints, find by operation)
- Need transactional guarantees (UPSERT atomicity)
- Need age-based cleanup queries

---

## Distributed Access

### Decision: Shared Filesystem

Backend and workers access same checkpoint data via:

- **Development:** Docker named volume mounted at `/app/data/checkpoints/`
- **Production:** NFS mount or shared storage

**Flow for Resume:**

1. User calls `POST /operations/{id}/resume`
2. Backend looks up checkpoint in PostgreSQL
3. Backend dispatches to worker with only `operation_id`
4. Worker reads artifacts from shared filesystem
5. Worker loads state and resumes operation

**Why not send artifacts over HTTP?**

- 200MB+ over HTTP is slow and unreliable
- Shared filesystem is faster (local disk speed)
- Avoids memory pressure on backend

---

## Resume Strategy

### Decision: Restart Partial Unit

When cancelled mid-epoch or mid-bar-batch:

- **Training:** Resume from start of current epoch (redo partial work)
- **Backtesting:** Resume from last checkpoint bar (redo partial work)

**Why restart partial unit?**

- Simpler state management (only track completed epochs/bars)
- Reproducible results (same random seeds, same batches)
- Small performance cost (< 1 epoch or < checkpoint interval)

**Alternative considered:** Resume mid-batch

- Requires saving batch index, RNG state, data loader position
- Complex, error-prone, minimal benefit
- Not worth the complexity

---

## Checkpoint Triggers

### Training

- **Periodic:** Every N epochs (default: 10)
- **Time-based:** Every X minutes (default: 5)
- **On failure/cancellation:** Always

### Backtesting

- **Periodic:** Every N bars (default: 10000)
- **Time-based:** Every X minutes (default: 5)
- **On failure/cancellation:** Always

### Trigger Logic

CheckpointPolicy evaluates after each unit (epoch/bar batch):

1. Check if time since last checkpoint > time threshold
2. Check if units since last checkpoint > unit threshold
3. If either true, create checkpoint

---

## Key Components

### Component Ownership

| Component | Owner | Why |
|-----------|-------|-----|
| CheckpointService | **Worker** | Workers execute operations and create checkpoints |
| CheckpointPolicy | **Worker** | Workers decide when to checkpoint during execution |
| ProgressBridge | **Worker** | Workers cache state during operation |
| Resume orchestration | **Backend** | Backend dispatches resume to workers |
| List/Cleanup | **Backend** | Backend manages checkpoint lifecycle |

**Key Decision:** Workers own checkpoint creation. Backend only orchestrates resume and manages cleanup.

Workers have direct DB and filesystem access (shared volume). Backend does NOT proxy checkpoint saves.

### Inheritance Pattern

```python
class WorkerAPIBase:
    def __init__(self, ...):
        self.checkpoint_service = CheckpointService()  # Generic CRUD

    # Abstract - each worker defines what to save/restore
    def build_checkpoint_data(self) -> dict:
        raise NotImplementedError

    def restore_from_checkpoint(self, checkpoint_data: dict) -> None:
        raise NotImplementedError
```

```python
class TrainingWorker(WorkerAPIBase):
    def build_checkpoint_data(self) -> dict:
        return {
            "epoch": self.current_epoch,
            "model_state": ...,
            "optimizer_state": ...,
        }

    def restore_from_checkpoint(self, data: dict) -> None:
        self.current_epoch = data["epoch"]
        self.model.load_state_dict(...)
```

**Generic:** CheckpointService, CheckpointPolicy (configurable thresholds)

**Worker-specific:** What data to save, how to restore

**Default behavior:** CheckpointPolicy returns false (never checkpoint) unless worker explicitly configures it - workers that don't support checkpointing are never called.

### CheckpointService

Responsibility: CRUD operations for checkpoints

Owner: **Worker** (for save/load during execution), **Backend** (for list/cleanup)

```python
class CheckpointService:
    def save_checkpoint(operation_id, checkpoint_data) -> None
    def load_checkpoint(operation_id) -> dict | None
    def delete_checkpoint(operation_id) -> bool
    def list_checkpoints(filters) -> list[dict]
    def cleanup_old_checkpoints(max_age_days) -> int
```

Storage:

- Writes metadata to PostgreSQL `operation_checkpoints` table
- Writes artifacts to `data/checkpoints/artifacts/{operation_id}/`
- Uses temp → rename for atomic artifact writes

### CheckpointPolicy

Responsibility: Decide WHEN to create checkpoints

```python
class CheckpointPolicy:
    def should_checkpoint(context) -> bool
    def get_checkpoint_type(context) -> str
```

Triggers:

- Periodic: Every N epochs (training) or N bars (backtesting)
- Time-based: Every X minutes
- Event: On failure or cancellation

### ProgressBridge (per operation type)

Responsibility: Cache current state for cancellation checkpoints

```python
class TrainingProgressBridge:
    def update_state(epoch, loss, accuracy, artifacts_paths) -> None
    def get_state() -> dict
```

Why needed:

- When user cancels, need current state immediately
- Can't wait for next periodic checkpoint
- Bridge caches state after every epoch

---

## Data Flow

### Save Checkpoint (Periodic)

```
ModelTrainer              ProgressBridge              CheckpointService        Filesystem + DB
     |                         |                            |                        |
     |-- update_state() ------>|                            |                        |
     |                         |-- should_checkpoint()? --->|                        |
     |                         |<-- yes --------------------|                        |
     |                         |-- save_checkpoint() ------>|                        |
     |                         |                            |-- write artifacts ---->|
     |                         |                            |-- INSERT/UPDATE ------>|
     |<-- done ----------------|                            |                        |
```

**Key:** ModelTrainer only reports state to ProgressBridge. Bridge owns checkpoint decision and save logic. ModelTrainer stays pure.

### Save Checkpoint (Cancellation)

```
User        Backend              CancellationToken       Bridge              CheckpointService
 |            |                        |                   |                        |
 |--cancel--->|                        |                   |                        |
 |            |--set cancelled-------->|                   |                        |
 |            |                        |--notify---------->|                        |
 |            |                        |                   |--save_checkpoint()---->|
 |            |                        |                   |                        |--write
 |            |<--cancelled------------|                   |                        |
```

**Key:** Bridge observes CancellationToken directly. Worker is unaware of checkpointing - stays focused on work.

### Resume From Checkpoint

```
User        Backend              CheckpointService         Worker
 |            |                        |                     |
 |--resume--->|                        |                     |
 |            |--load checkpoint------>|                     |
 |            |<--checkpoint data------|                     |
 |            |--dispatch(operation_id)--------------------->|
 |            |                        |                     |--load artifacts
 |            |                        |                     |--resume training
 |<--new op id|                        |                     |
```

---

## Database Schema

```sql
CREATE TABLE operation_checkpoints (
    operation_id VARCHAR(255) PRIMARY KEY,
    checkpoint_id VARCHAR(255) NOT NULL,
    checkpoint_type VARCHAR(50) NOT NULL,  -- 'periodic', 'cancellation', 'failure'
    created_at TIMESTAMP NOT NULL,

    -- Metadata (small, queryable)
    metadata_json JSONB NOT NULL,

    -- State (medium, JSON)
    state_json JSONB NOT NULL,

    -- Artifact location (path, not bytes)
    artifacts_path VARCHAR(500),

    -- Sizes for monitoring
    state_size_bytes INTEGER,
    artifacts_size_bytes BIGINT
);

-- Index for cleanup queries
CREATE INDEX idx_checkpoints_created_at ON operation_checkpoints(created_at);
```

---

## Artifact Directory Structure

```
data/checkpoints/artifacts/
  {operation_id}/
    model.pt           # Model weights
    optimizer.pt       # Optimizer state
    scheduler.pt       # LR scheduler (if used)
    best_model.pt      # Best model so far
```

---

## Configuration

```yaml
checkpointing:
  # Periodic triggers
  training_checkpoint_epochs: 10
  backtesting_checkpoint_bars: 10000

  # Time-based trigger
  checkpoint_interval_minutes: 5

  # Cleanup
  max_checkpoint_age_days: 5

  # Storage
  artifacts_dir: data/checkpoints/artifacts
```

---

## Error Handling

### Artifact Write Failure

1. Write to temp directory first
2. Rename to final location (atomic)
3. If DB insert fails, delete artifact files
4. If artifact write fails, don't insert to DB

### Checkpoint Load Failure

1. If artifacts missing, return error (don't resume with partial state)
2. If DB row exists but artifacts missing, mark checkpoint as corrupted
3. User must start fresh or use older checkpoint

### Concurrent Access

- UPSERT guarantees only one checkpoint per operation
- File renames are atomic on POSIX
- No locking needed for read access (workers only read)

---

## Gotchas Addressed

| Gotcha | Solution |
|--------|----------|
| G1: Large artifacts | Filesystem storage, not DB |
| G2: Cache continuously | ProgressBridge caches after every epoch |
| G3: Distributed access | Shared Docker volume / NFS |
| G4: Bridge must cache | TrainingProgressBridge.get_state() |

---

## Out of Scope

- Artifact compression (not needed for current sizes)
- Multi-region replication
- Checkpoint versioning/migration
- Encryption at rest
