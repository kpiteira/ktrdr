# Checkpoint & Resilience System

The checkpoint system enables KTRDR to save progress during long-running operations and resume them after interruptions.

## Quick Links

| Document | Description |
|----------|-------------|
| [DESIGN.md](DESIGN.md) | Problem statement, goals, user journeys |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture, component details |
| [User Guide](../../user-guides/checkpoint-resume.md) | End-user documentation |

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         KTRDR System                             │
├─────────────────────────────────────────────────────────────────┤
│  Backend                                                         │
│   ├─ CheckpointService      - Save/load/delete checkpoints     │
│   ├─ CleanupService         - Automatic old checkpoint cleanup  │
│   ├─ OrphanDetector         - Mark stuck operations as FAILED   │
│   └─ Resume API             - Restore operations from checkpoint│
├─────────────────────────────────────────────────────────────────┤
│  Workers (Training, Backtest, Agent)                            │
│   ├─ CheckpointPolicy       - When to save checkpoints          │
│   ├─ ProgressBridge         - Progress tracking with checkpoints│
│   └─ ReregistrationLoop     - Re-register after backend restart │
├─────────────────────────────────────────────────────────────────┤
│  Storage                                                         │
│   ├─ PostgreSQL             - Checkpoint metadata & state       │
│   └─ Filesystem             - Large artifacts (model weights)   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### Resilience
- **Self-healing**: Workers re-register after backend restart
- **Orphan detection**: Stuck RUNNING operations marked as FAILED
- **Health monitoring**: Continuous backend-worker communication

### Checkpoints
- **Automatic saving**: Progress saved periodically and on interruption
- **Resume support**: Continue from saved checkpoint
- **Hybrid storage**: PostgreSQL for state, filesystem for large artifacts

## Components

### CheckpointService
**Location**: `ktrdr/checkpointing/checkpoint_service.py`

Core service for checkpoint operations:
- `save_checkpoint()` - Save operation state and artifacts
- `load_checkpoint()` - Retrieve checkpoint for resume
- `delete_checkpoint()` - Remove checkpoint (after success or manually)
- `list_checkpoints()` - Query available checkpoints
- `cleanup_old_checkpoints()` - Remove stale checkpoints

### CleanupService
**Location**: `ktrdr/checkpointing/cleanup_service.py`

Background task for automatic maintenance:
- Runs daily (configurable)
- Deletes checkpoints older than 30 days (configurable)
- Cleans orphan artifact directories

### Resume API
**Location**: `ktrdr/api/endpoints/operations.py`

Endpoint: `POST /operations/{id}/resume`

Resume flow:
1. Validate operation is CANCELLED or FAILED
2. Load checkpoint from database
3. Dispatch to appropriate worker with checkpoint data
4. Worker restores state and continues

## Checkpoint Data Model

```python
class CheckpointRecord(Base):
    operation_id: str           # Primary key
    checkpoint_type: str        # 'periodic', 'cancellation', 'failure'
    state: dict                 # JSON - operation-specific state
    artifacts_path: str         # Filesystem path for large files
    created_at: datetime
    updated_at: datetime
```

### State by Operation Type

**Training**:
```json
{
  "epoch": 45,
  "total_epochs": 100,
  "train_loss": 0.28,
  "val_loss": 0.31,
  "best_val_loss": 0.29,
  "learning_rate": 0.001
}
```

**Backtesting**:
```json
{
  "bar_index": 7500,
  "total_bars": 10000,
  "trades": [...],
  "portfolio_value": 105000.0
}
```

**Agent Research**:
```json
{
  "phase": "training",
  "strategy_name": "rsi_momentum_v1",
  "training_operation_id": "op_training_xyz",
  "training_checkpoint_epoch": 45
}
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CHECKPOINT_MAX_AGE_DAYS` | 30 | Days before auto-cleanup |
| `CHECKPOINT_CLEANUP_INTERVAL_HOURS` | 24 | Cleanup task frequency |
| `CHECKPOINT_ARTIFACTS_PATH` | `/app/data/checkpoints` | Artifact storage location |

## Milestones

The checkpoint system was built incrementally:

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ Complete | Operations persistence (database) |
| M2 | ✅ Complete | Orphan detection (stuck operation recovery) |
| M3 | ✅ Complete | Training checkpoint save |
| M4 | ✅ Complete | Training resume |
| M5 | ✅ Complete | Backtesting checkpoints |
| M6 | ✅ Complete | Graceful shutdown |
| M7 | ✅ Complete | Agent (backend-local) checkpoints |
| M7.5 | ✅ Complete | Re-registration reliability |
| M8 | ✅ Complete | Polish & Admin (cleanup, CLI, docs) |

See individual `PLAN_M*.md` files for implementation details.

## CLI Commands

```bash
# View checkpoint details
ktrdr checkpoints show <operation_id>

# Delete a checkpoint
ktrdr checkpoints delete <operation_id>
ktrdr checkpoints delete <operation_id> --force

# Resume an operation
ktrdr operations resume <operation_id>

# List resumable operations
ktrdr operations list --resumable
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/checkpoints/{id}` | GET | Get checkpoint details |
| `/checkpoints/{id}` | DELETE | Delete a checkpoint |
| `/checkpoints` | GET | List all checkpoints |
| `/checkpoints/stats` | GET | Storage statistics |
| `/checkpoints/cleanup` | POST | Trigger manual cleanup |
| `/operations/{id}/resume` | POST | Resume from checkpoint |

## Testing

```bash
# Unit tests
uv run pytest tests/unit/checkpointing/ -v

# Integration tests
uv run pytest tests/integration/test_checkpoint*.py -v

# M8 concurrent resume test
uv run pytest tests/integration/test_concurrent_resume.py -v
```

## Troubleshooting

### Checkpoint not created
- Check operation logs for errors during checkpoint save
- Verify filesystem permissions on artifacts directory
- Ensure database connection is available

### Resume fails
- Verify operation is in CANCELLED or FAILED state
- Check checkpoint exists: `ktrdr checkpoints show <id>`
- Look for version mismatch in worker logs

### Disk space issues
- Check stats: `curl http://localhost:8000/api/v1/checkpoints/stats`
- Trigger cleanup: `curl -X POST http://localhost:8000/api/v1/checkpoints/cleanup`
- Reduce `CHECKPOINT_MAX_AGE_DAYS` setting
