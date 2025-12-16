# Checkpoint & Resilience System: Design

## Problem Statement

Long-running operations (training: hours/days, backtesting: minutes/hours) face two categories of problems:

1. **Progress Loss**: Operations interrupted by user cancellation, system failures, or infrastructure maintenance lose all progress, forcing users to restart from scratch.

2. **State Inconsistency**: When backend restarts, worker registrations are lost (in-memory). Operations can get stuck showing RUNNING when nothing is executing. The system cannot self-heal.

Both problems waste compute time, delay results, and erode user trust.

## Goals

### Resilience Goals
1. **Survive backend restart** — Workers re-register, operations sync to correct state
2. **No stuck operations** — System detects and recovers from RUNNING operations with no worker
3. **Self-healing** — Recovery happens automatically via health checks, no manual intervention

### Checkpoint Goals
4. **Save progress periodically** — Interruptions don't lose all work
5. **Resume from checkpoint** — Continue where left off
6. **Handle all interruption types** — User cancel, failures, graceful shutdown
7. **Simple user experience** — Clear commands, predictable behavior

## Non-Goals (Out of Scope)

- Automatic resume on system startup (user must explicitly resume)
- Multiple checkpoint versions per operation (only latest kept)
- Cloud backup/sync of checkpoints
- Checkpoint migration between KTRDR versions
- Redis caching layer
- Persisting worker registry to database (re-registration is simpler)

---

## User Journeys

### Resilience: Backend Restarts During Operation

**Scenario:** Training is running, backend crashes and restarts.

```
[Before restart]
$ ktrdr operations status op_training_123
Status: RUNNING
Progress: 45%
Worker: training-worker-abc

[Backend crashes and restarts]

[After restart - within 30 seconds]
$ ktrdr operations status op_training_123
Status: RUNNING          # Correctly shows RUNNING
Progress: 47%            # Progress continues (worker kept running)
Worker: training-worker-abc

# What happened behind the scenes:
# 1. Backend restarted with empty worker registry
# 2. Backend's health check loop restarted (calls workers every 10s)
# 3. Worker noticed: "Backend hasn't health-checked me in 30s"
# 4. Worker re-registered: "I'm training-worker-abc, running op_training_123"
# 5. Backend reconciled: op_training_123 is RUNNING on training-worker-abc
```

**Key point:** User sees no disruption. System self-healed.

---

### Resilience: Worker Dies During Operation

**Scenario:** Training is running, worker crashes.

```
[Before crash]
$ ktrdr operations status op_training_123
Status: RUNNING
Progress: 45%
Worker: training-worker-abc

[Worker crashes]

[After ~30 seconds - health checks detect failure]
$ ktrdr operations status op_training_123
Status: FAILED
Progress: 45%
Message: "Worker training-worker-abc became unavailable"
Checkpoint: epoch 45 (if periodic checkpoint was saved)

# What happened:
# 1. Backend health check to worker failed
# 2. After 3 failures, worker marked TEMPORARILY_UNAVAILABLE
# 3. Backend saw op_training_123 was assigned to unavailable worker
# 4. Backend marked op_training_123 as FAILED
```

**If checkpoint exists:** User can resume
```
$ ktrdr operations resume op_training_123
Resuming from checkpoint at epoch 45...
```

---

### Resilience: Operation Stuck After Backend Restart (Edge Case)

**Scenario:** Backend restarted, but worker also died (no one to re-register).

```
[Before restart]
Training running on worker-abc

[Backend restarts, worker-abc is dead]

[After 60 seconds]
$ ktrdr operations status op_training_123
Status: FAILED
Message: "Operation was RUNNING but no worker claimed it"

# What happened:
# 1. Backend restarted, registry empty
# 2. No worker re-registered claiming op_training_123
# 3. After timeout (60s), backend marked orphan operation as FAILED
```

---

### Training: Cancel and Resume

**Step 1: User starts training**
```
$ ktrdr train --strategy strategies/my_strategy.yaml

Training started: op_training_20241213_143022_abc123
Strategy: my_strategy
Epochs: 100

[##########] Epoch 10/100 - loss: 0.45, val_acc: 0.72
[####################] Epoch 20/100 - loss: 0.32, val_acc: 0.78
```

Checkpoints are saved automatically every 10 epochs (configurable).

**Step 2: User cancels**
```
[#############################] Epoch 29/100 - loss: 0.28
^C

Cancelling... saving checkpoint...
Checkpoint saved at epoch 29
Operation cancelled: op_training_20241213_143022_abc123

To resume: ktrdr operations resume op_training_20241213_143022_abc123
```

**Step 3: User checks available operations**
```
$ ktrdr operations list --status cancelled

OPERATION_ID                              STATUS     PROGRESS   CHECKPOINT
op_training_20241213_143022_abc123        CANCELLED  29%        epoch 29
op_training_20241210_091500_def456        CANCELLED  45%        epoch 45
```

**Step 4: User resumes**
```
$ ktrdr operations resume op_training_20241213_143022_abc123

Resuming training from checkpoint...
Loading checkpoint: epoch 29
Loading model weights...
Loading optimizer state...

Training resumed: op_training_20241213_143022_abc123
Continuing from epoch 30/100

[##############################] Epoch 30/100 - loss: 0.27, val_acc: 0.81
...
[##################################################] Epoch 100/100

Training complete!
Model saved: models/my_strategy/v1/model.pt
```

Checkpoint is deleted after successful completion.

---

### Training: Resume After Failure

**Step 1: Training fails mid-run**
```
$ ktrdr train --strategy strategies/my_strategy.yaml

Training started: op_training_20241213_143022_abc123
[####################] Epoch 20/100 - loss: 0.32

ERROR: CUDA out of memory
Saving checkpoint before exit...
Checkpoint saved at epoch 20
Operation failed: op_training_20241213_143022_abc123
```

**Step 2: User fixes issue and resumes**
```
$ ktrdr operations resume op_training_20241213_143022_abc123

Resuming training from checkpoint...
Training resumed from epoch 21/100
...
```

---

### Training: Worker Graceful Shutdown

**Scenario:** Admin shuts down worker for maintenance while training is running.

```
[Worker receives SIGTERM]
Graceful shutdown initiated...
Saving checkpoint at epoch 45...
Checkpoint saved
Worker shutdown complete

[User sees]
$ ktrdr operations status op_training_20241213_143022_abc123

Status: CANCELLED
Progress: 45%
Checkpoint: epoch 45
Message: "Graceful shutdown - checkpoint saved"
```

User can resume when worker is back online.

---

### Backtesting: Cancel and Resume

**Step 1: User starts long backtest**
```
$ ktrdr backtest --strategy my_strategy --symbol EURUSD --start 2020-01-01 --end 2024-01-01

Backtest started: op_backtesting_20241213_150000_xyz789
Processing 4 years of 1h data (~35,000 bars)

[##########] Bar 3500/35000 - 2020-04-15 - PnL: $1,234
[####################] Bar 7000/35000 - 2020-07-28 - PnL: $2,456
^C

Cancelling... saving checkpoint...
Checkpoint saved at bar 7000 (2020-07-28)
Operation cancelled

To resume: ktrdr operations resume op_backtesting_20241213_150000_xyz789
```

**Step 2: User resumes**
```
$ ktrdr operations resume op_backtesting_20241213_150000_xyz789

Resuming backtest from checkpoint...
Loading checkpoint: bar 7000 (2020-07-28)
Restoring portfolio: $102,456 cash, 0 positions
Restoring trade history: 23 trades

Recomputing indicators for continuation...
[####] Loading data and computing indicators...

Backtest resumed from bar 7000/35000

[#####################] Bar 7100/35000 - 2020-07-30 - PnL: $2,501
...
[##################################################] Bar 35000/35000

Backtest complete!
```

Note: Indicators are recomputed on resume (fast), but bars 0-6999 are not re-backtested.

---

### Error Cases

**No checkpoint available:**
```
$ ktrdr operations resume op_training_20241213_143022_abc123

ERROR: No checkpoint available for this operation

This can happen if:
  - Operation completed successfully (checkpoint deleted)
  - Checkpoint expired (older than 30 days)
  - Operation failed before first checkpoint was saved
```

**Checkpoint corrupted:**
```
$ ktrdr operations resume op_training_20241213_143022_abc123

ERROR: Checkpoint corrupted - model.pt missing or invalid

Options:
  1. Start fresh: ktrdr train --strategy strategies/my_strategy.yaml
  2. Delete checkpoint: ktrdr checkpoints delete op_training_20241213_143022_abc123
```

**Resume fails, try again:**
```
$ ktrdr operations resume op_training_20241213_143022_abc123

Resuming from epoch 29...
[##############################] Epoch 30/100
ERROR: Connection lost

Checkpoint preserved - you can retry resume.

$ ktrdr operations resume op_training_20241213_143022_abc123

Resuming from epoch 29...  # Same checkpoint, idempotent
```

---

## Key Decisions

### D1: Worker Re-Registration Triggered by Missed Health Checks

**Choice:** Workers detect backend restart by noticing missed health checks, then re-register.

**Mechanism:**
- Backend health-checks each worker every 10 seconds (existing infrastructure)
- Worker tracks "last time backend checked on me"
- If >30 seconds pass with no health check → backend probably restarted
- Worker attempts to re-register, including current operation (if any)

**Alternatives considered:**
- Worker polls backend every 30s to verify registration (wasteful)
- Persist worker registry to database (complex)

**Rationale:**
- Uses existing health check infrastructure (no new traffic)
- Worker only acts when something is actually wrong
- Distributed system principle: detect failure, then recover

---

### D2: Operations Sync via Re-Registration

**Choice:** When worker re-registers, backend reconciles operation status.

**Mechanism:**
- Re-registration payload includes `current_operation_id` if worker is busy
- Backend updates operation status based on this:
  - Worker says "running op_123" → op_123 status set to RUNNING
  - Backend associates operation with this worker
- OrphanOperationDetector handles the inverse (RUNNING ops with no worker)

**Rationale:**
- Single source of truth: worker knows what it's running
- Self-healing: no manual intervention needed
- Re-registration is the natural place to sync state

---

### D3: Orphan Operation Timeout

**Choice:** RUNNING operations with no worker are marked FAILED after 60 seconds.

**Rationale:**
- Gives workers time to re-register after backend restart
- Long enough to survive transient issues
- Short enough that users don't wait forever

---

### D4: Reuse Same Operation ID on Resume

**Choice:** Resume continues the same operation (no new operation ID created)

**Alternatives considered:**
- Create new operation linked to original via `parent_operation_id`

**Rationale:**
- Simpler mental model for users ("continuing my training")
- No need to track operation chains
- Status flow is clear: CANCELLED → RUNNING → COMPLETED

---

### D5: Keep Only Latest Checkpoint

**Choice:** Each checkpoint overwrites the previous one (UPSERT behavior)

**Alternatives considered:**
- Keep multiple checkpoints per operation (versioned)

**Rationale:**
- Simpler storage management
- Users rarely need to resume from an earlier point
- Reduces storage requirements

---

### D6: Resume is Idempotent

**Choice:** Checkpoint is preserved until operation completes successfully

**Deletion policy:**
- On successful completion: DELETE checkpoint
- On resume start: KEEP checkpoint (in case resume fails)
- On resume completion: DELETE checkpoint

**Rationale:**
- If resume fails at epoch 35, user can retry from original checkpoint (epoch 29)
- No risk of losing checkpoint due to transient failures

---

### D7: Restart Partial Unit on Resume

**Choice:**
- Training: Resume from start of current epoch (may redo partial epoch)
- Backtesting: Resume from last checkpointed bar (may redo partial batch)

**Alternatives considered:**
- Resume mid-batch (requires saving RNG state, data loader position)

**Rationale:**
- Simpler state management
- Reproducible results
- Small performance cost (< 1 epoch or < checkpoint interval)

---

### D8: Backtesting Recomputes Indicators on Resume

**Choice:** On backtest resume, reload data and recompute indicators before continuing

**Rationale:**
- Indicators depend on recent bars (lookback windows)
- Recomputation is fast compared to full backtest
- Avoids complex indicator state serialization
- Checkpoint only stores: bar index, portfolio state, trade history

---

### D9: Graceful Shutdown Saves Checkpoint

**Choice:** Workers save checkpoint on SIGTERM before exiting

**Rationale:**
- Infrastructure maintenance shouldn't lose user progress
- Docker/Kubernetes send SIGTERM before SIGKILL
- Gives worker time to save (typically 10-30 seconds)

---

### D10: Best-Effort Artifact Cleanup

**Choice:** If DB write fails after artifact write, try to delete artifacts. Run periodic sweep for orphans.

**Rationale:**
- Orphan artifacts are a disk space issue, not a correctness issue
- Best-effort cleanup handles most cases
- Periodic sweep catches edge cases
- Simpler than two-phase commit

---

## What "Done" Looks Like

### Resilience
- [ ] Workers re-register after backend restart (within 30 seconds)
- [ ] Operations sync to correct status via health checks
- [ ] Orphan RUNNING operations marked FAILED after timeout
- [ ] No manual intervention needed for recovery

### Checkpoint Save
- [ ] Periodic checkpoints saved during training (every N epochs)
- [ ] Periodic checkpoints saved during backtesting (every N bars)
- [ ] Checkpoint saved on cancellation
- [ ] Checkpoint saved on failure
- [ ] Checkpoint saved on SIGTERM (graceful shutdown)

### Training Resume
- [ ] `ktrdr operations resume <id>` continues cancelled training
- [ ] Training continues from checkpoint epoch
- [ ] Final model is equivalent to uninterrupted training
- [ ] Checkpoint deleted after successful completion

### Backtesting Resume
- [ ] `ktrdr operations resume <id>` continues cancelled backtest
- [ ] Indicators recomputed, backtest continues from checkpoint bar
- [ ] Portfolio state (cash, positions, trades) correctly restored
- [ ] Final results match uninterrupted run

### User Experience
- [ ] `operations list` shows checkpoint availability
- [ ] Clear error messages for missing/corrupted checkpoints
- [ ] Resume command shown after cancellation
- [ ] Idempotent: failed resume can be retried

---

## Open Questions

1. **Checkpoint interval tuning:** Default 10 epochs / 10,000 bars — is this right for typical workloads?
2. **Cleanup notification:** Should users be warned before old checkpoints are deleted?
3. **Re-registration interval:** 30 seconds feels right, but should it be configurable?
