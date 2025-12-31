# Checkpoint & Resume Guide

This guide explains how to use KTRDR's checkpoint system to resume interrupted operations without losing progress.

## Overview

Long-running operations like training (hours/days) and backtesting (minutes/hours) can be interrupted by:
- User cancellation (`Ctrl+C` or cancel command)
- System failures or crashes
- Infrastructure maintenance

The checkpoint system automatically saves progress so you can resume from where you left off.

## How Checkpoints Work

### Automatic Saving

KTRDR automatically saves checkpoints at key moments:

| Operation Type | When Checkpoints Are Saved |
|---------------|---------------------------|
| Training | Every 5 epochs (configurable), on cancellation, on failure |
| Backtesting | Every 1000 bars (configurable), on cancellation, on failure |
| Agent Research | At phase transitions, on cancellation, on failure |

### What Gets Saved

- **Training**: Current epoch, model weights, optimizer state, best validation loss
- **Backtesting**: Current bar index, accumulated trades, portfolio state
- **Agent Research**: Current phase, strategy config, child operation references

## Resuming Operations

### Check Resumable Operations

List cancelled or failed operations that have checkpoints:

```bash
# List all cancelled operations
ktrdr operations list --status cancelled

# Show operations with checkpoint info
ktrdr operations list --resumable
```

Example output:
```
OPERATION_ID                              STATUS     PROGRESS   CHECKPOINT   AGE
op_training_20241213_143022_abc123        CANCELLED  29%        epoch 29     2d
op_training_20241210_091500_def456        CANCELLED  45%        epoch 45     5d

Total: 2 operations (2 resumable)
```

### View Checkpoint Details

Before resuming, you can inspect what's saved:

```bash
ktrdr checkpoints show op_training_20241213_143022_abc123
```

Example output:
```
Checkpoint Details
==================
Operation ID:    op_training_20241213_143022_abc123
Checkpoint Type: cancellation
Created At:      2024-12-13 14:35:00 UTC
Age:             2 days

State:
  Epoch:         29 / 100
  Train Loss:    0.28
  Val Loss:      0.31
  Best Val Loss: 0.29
  Learning Rate: 0.001

Artifacts: /app/data/checkpoints/op_training_20241213_143022_abc123

To resume: ktrdr operations resume op_training_20241213_143022_abc123
```

### Resume an Operation

```bash
ktrdr operations resume op_training_20241213_143022_abc123
```

The operation will:
1. Load the saved checkpoint
2. Restore model weights and optimizer state
3. Continue from the saved epoch/bar
4. Show progress updates as it continues

## Managing Checkpoints

### View Checkpoint Statistics

```bash
# Via API
curl http://localhost:8000/api/v1/checkpoints/stats
```

Response:
```json
{
  "success": true,
  "total_checkpoints": 60,
  "total_size_bytes": 2231647,
  "oldest_checkpoint": "2024-12-27T01:38:17Z"
}
```

### Delete a Checkpoint

If you no longer need a checkpoint (e.g., the operation completed elsewhere):

```bash
# Interactive deletion with confirmation
ktrdr checkpoints delete op_training_20241213_143022_abc123

# Skip confirmation prompt
ktrdr checkpoints delete op_training_20241213_143022_abc123 --force
```

> **Warning**: Deleting a checkpoint means the operation cannot be resumed. This action cannot be undone.

### Automatic Cleanup

The system automatically cleans up old checkpoints:
- Checkpoints older than 30 days are deleted daily
- Orphan artifacts (directories without database records) are cleaned up

To trigger manual cleanup:
```bash
curl -X POST "http://localhost:8000/api/v1/checkpoints/cleanup?max_age_days=30"
```

## Common Scenarios

### Scenario 1: Training Cancelled by User

```bash
# Start training
ktrdr models train strategies/neuro_mean_reversion.yaml AAPL 1h \
  --start-date 2024-01-01 --end-date 2024-06-01 --epochs 100

# ... training reaches epoch 45, user presses Ctrl+C ...
# Checkpoint automatically saved

# Later, resume from checkpoint
ktrdr operations resume op_training_20241213_143022_abc123
# Continues from epoch 45
```

### Scenario 2: Worker Crashes During Training

```bash
# Training running on worker, worker crashes at epoch 60
# Backend detects failure, operation marked FAILED

# Check status
ktrdr operations status op_training_20241213_143022_abc123
# Shows: FAILED, Checkpoint: epoch 60

# Resume on another worker
ktrdr operations resume op_training_20241213_143022_abc123
# Continues from epoch 60
```

### Scenario 3: Backend Restarts

```bash
# Training running, backend restarts
# Workers automatically re-register within 30 seconds
# Operation continues without interruption

# Check status
ktrdr operations status op_training_20241213_143022_abc123
# Shows: RUNNING (operation continued automatically)
```

## Troubleshooting

### "No checkpoint found for operation"

The operation doesn't have a saved checkpoint. This can happen if:
- The operation completed successfully (checkpoint deleted on completion)
- The operation failed before any checkpoint was saved
- The checkpoint was manually deleted or cleaned up

### "Operation is not in a resumable state"

Only CANCELLED or FAILED operations can be resumed. Check the operation status:

```bash
ktrdr operations status op_training_20241213_143022_abc123
```

### "Checkpoint version mismatch"

The checkpoint was created with a different KTRDR version. Unfortunately, cross-version checkpoint restoration is not supported. You'll need to restart the operation from scratch.

### Checkpoint taking up too much space

Check checkpoint stats and clean up old ones:

```bash
# Check total size
curl http://localhost:8000/api/v1/checkpoints/stats

# Cleanup checkpoints older than 7 days
curl -X POST "http://localhost:8000/api/v1/checkpoints/cleanup?max_age_days=7"

# Or delete specific checkpoints
ktrdr checkpoints delete op_old_training_xyz --force
```

## Configuration

Checkpoint behavior can be configured in the operation request:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `checkpoint_frequency` | 5 (training), 1000 (backtest) | How often to save periodic checkpoints |
| `checkpoint_enabled` | true | Whether to save checkpoints at all |

Example API request with custom settings:
```bash
curl -X POST http://localhost:8000/api/v1/training/train \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_path": "strategies/my_strategy.yaml",
    "symbol": "AAPL",
    "timeframe": "1h",
    "epochs": 100,
    "checkpoint_frequency": 10
  }'
```

## See Also

- [Operations Management](cli-reference.md#operations-commands) - Managing long-running operations
- [Training Guide](neural-networks.md) - Training neural network models
- [Architecture Overview](../architecture/checkpoint/README.md) - Technical details of the checkpoint system
