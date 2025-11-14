# Checkpoint Persistence System - Design Document
**Document Version:** 1.0
**Date:** January 2025
**Status:** Proposed
**Authors:** Engineering Team
---
## Executive Summary
This document describes the design of a checkpoint persistence system for KTRDR's long-running operations (training and backtesting). The system provides resilience against interruptions by periodically saving operation state to durable storage, enabling operations to resume from the last checkpoint rather than restart from scratch.
**Key Outcomes:**
- Training operations can resume from any saved epoch if interrupted
- Backtesting operations can resume from any saved bar position if interrupted
- Zero data loss for operations that complete successfully
- Minimal performance overhead (<1% of operation time)
---
## 1. Problem Statement
### 1.1 Current State
KTRDR performs two types of long-running operations:
**Training Operations:**
- Duration: 30 seconds to 8+ hours per operation
- Variability: Epoch times range from 10 seconds to 30 minutes
- Failure modes: Out of memory, network interruption, API restart, user cancellation
- Current behavior: If interrupted, training restarts from epoch 0
**Backtesting Operations:**
- Duration: 10 seconds to 30+ minutes per operation
- Variability: Bar processing speed varies based on computation complexity
- Failure modes: Network interruption, API restart, user cancellation
- Current behavior: If interrupted, backtest restarts from bar 0
**Operations Service:**
- Tracks operation status in-memory only
- All state lost on API restart
- No recovery mechanism for interrupted operations
### 1.2 Pain Points
1. **Lost Work:** A training operation that fails at epoch 95/100 loses 95 epochs of work (potentially hours)
2. **Cost:** Re-running expensive GPU operations wastes computational resources
3. **User Experience:** Users cannot reliably run long operations without babysitting them
4. **Development Friction:** Cannot safely restart API during development without losing all in-progress work
5. **No Observability:** Cannot inspect operation state after API restart
### 1.3 Business Value
**Time Savings:**
- Training: Avoid re-running 1-8 hours of computation
- Backtesting: Avoid re-running 5-30 minutes of simulation
- Development: Faster iteration cycles during debugging
**Reliability:**
- Operations survive API restarts, network hiccups, container crashes
- Graceful degradation: Always recover to last known good state
**User Trust:**
- Users can start long operations and walk away
- Operations can be safely cancelled and resumed later
---
## 2. Design Goals
### 2.1 Functional Goals
1. **Resume Capability:** Any interrupted operation can resume from its last checkpoint
2. **Time-Based Checkpointing:** Checkpoint frequency adapts to operation speed (not fixed intervals)
3. **Ephemeral Checkpoints:** Checkpoints exist only while operation is running; deleted on completion
4. **Final Results Storage:** Completed operations store results in existing result stores (ModelStorage, backtest results)
5. **Clean Resume Semantics:** Resume creates a NEW operation that continues from checkpoint
### 2.2 Non-Functional Goals
1. **Performance:** Checkpoint overhead < 1% of operation time
2. **Durability:** Checkpoints survive API restart, container crash
3. **Simplicity:** Single persistence service (PostgreSQL), no external dependencies beyond database
4. **Testability:** All components testable in isolation
5. **Observability:** Checkpoint status visible via Operations API
### 2.3 Explicit Non-Goals
1. **Real-time Progress Persistence:** Progress updates remain in-memory (current design is fine)
2. **Distributed Checkpointing:** Single-instance only (no multi-API coordination)
3. **Version Migration:** Checkpoints valid only for same KTRDR version
4. **Cross-Operation Sharing:** Checkpoints tied to specific operation instance
---
## 3. Core Concepts
### 3.1 Checkpoint
A **checkpoint** is a snapshot of operation state at a point in time that contains sufficient information to resume the operation from that point.
**Properties:**
- **Temporal:** Captures state at specific epoch/bar
- **Self-Contained:** Includes all data needed to resume
- **Versioned:** Tagged with KTRDR version for compatibility checking
- **Ephemeral:** Automatically deleted when operation completes
**Lifecycle:**
```
[Operation Running] → [Checkpoint Created] → [Checkpoint Stored]
                          ↓
                      [More Progress]
                          ↓
                      [Repeat...]
                          ↓
[Operation Completes] → [Checkpoints Deleted] → [Results Stored in Result Store]
```
### 3.2 Time-Based Checkpoint Policy
Instead of checkpointing at fixed intervals (e.g., every 10 epochs), checkpointing is based on **elapsed wall-clock time** since the last checkpoint.
**Rationale:**
- Fast epochs (10 sec): Don't need checkpoint every epoch → checkpoint every 10 epochs
- Slow epochs (30 min): Need checkpoint every epoch → checkpoint every epoch
- Adaptive behavior requires no manual tuning
**Policy Parameters:**
- `checkpoint_interval_seconds`: Target time between checkpoints (default: 5 minutes)
- `force_checkpoint_every_n`: Safety net to force checkpoint even if time threshold not reached
- `delete_on_completion`: Delete checkpoint when operation completes (default: true)
- `checkpoint_on_failure`: Save checkpoint when operation fails (default: true)
**Example:**
```
Scenario 1: Fast epochs (10 sec/epoch)
- 5 min interval = 30 epochs → checkpoint every 30 epochs
- Prevents excessive checkpointing
 
Scenario 2: Slow epochs (30 min/epoch)
- 5 min interval < epoch time → checkpoint every epoch
- Ensures progress not lost
```
### 3.3 Resume Operation
A **resume operation** creates a NEW operation that loads state from a checkpoint of a previous (failed/cancelled) operation.
**Key Design Decision: New Operation ID**
Resume creates a **new operation with new operation_id** rather than reusing the original operation_id.
**Why?**
- **Clean Audit Trail:** Original operation shows failure reason; new operation shows resume success
- **No State Confusion:** Each operation has single lifecycle (created → running → completed/failed)
- **Simplified Logic:** No need to handle "partial completion" states
- **User Clarity:** Users see two operations: original (failed) and resumed (completed)
**Example:**
```
Original Operation:
  ID: op_training_20250117_100000
  Status: FAILED
  Reason: Out of memory at epoch 45/100
 
Resume Operation:
  ID: op_training_20250117_140000
  Status: RUNNING
  Metadata: resumed_from = op_training_20250117_100000
  Start: Epoch 46/100 (continues from checkpoint)
```
### 3.4 Checkpoint Retention
Checkpoints are **ephemeral** - they exist only to support resume functionality and are deleted when no longer needed.

**Storage Model:**
- **ONE checkpoint per operation** (the latest)
- When a new checkpoint is saved, the old one is deleted
- Checkpoints deleted when operation reaches terminal state

**Retention Rules (in order of precedence):**

1. **Age-Based Cleanup (HIGHEST PRIORITY):**
   - All checkpoints older than 30 days are deleted, regardless of operation status
   - This prevents abandoned operations from consuming disk forever
   - User must resume within 30 days or operation is lost

2. **COMPLETED Operations:**
   - Checkpoint deleted immediately on completion
   - Final results saved to ModelStorage / backtest results
   - No checkpoint remains

3. **FAILED Operations:**
   - Checkpoint preserved for resume
   - Subject to 30-day age limit (rule #1)
   - User can resume or explicitly discard

4. **CANCELLED Operations:**
   - Checkpoint preserved for resume
   - Subject to 30-day age limit (rule #1)
   - User can resume or explicitly discard

5. **RUNNING Operations:**
   - Checkpoint updated periodically (replaces previous)
   - Only 1 checkpoint exists at any time

**Disk Budget:**
```
Max concurrent operations: 5 training + 5 backtesting
Training checkpoint size: ~200 MB
Backtesting checkpoint size: ~5 MB

Worst case (all operations running):
  5 training × 200 MB = 1000 MB
  5 backtest × 5 MB   = 25 MB
  Total: ~1 GB

Abandoned operations (30-day retention):
  10 operations × avg 100 MB = 1 GB

Total budget: ~2 GB
```
---
## 4. Integration with Existing KTRDR System
### 4.1 Operations Service Integration
**Current State:**
- `OperationsService` tracks operations in-memory
- Operations lost on API restart
- No persistent state
**Enhanced State:**
- `OperationsService` persists operation metadata to PostgreSQL
- Operations survive API restart
- Can query historical operations
- **Startup recovery** automatically handles interrupted operations
**Integration Point:**
```
OperationsService
  ├─ create_operation() → Save to PostgreSQL
  ├─ update_progress() → Update in-memory (no persistence)
  ├─ complete_operation() → Mark complete, trigger checkpoint cleanup
  ├─ recover_interrupted_operations() → NEW: Mark RUNNING → FAILED on startup
  └─ resume_operation() → NEW: Load checkpoint, delete original checkpoint, create new operation
```

### 4.1.1 Startup Recovery
**The Problem:**
The primary use case for checkpoints is **API crashes**. When the API crashes or restarts, operations are left in `RUNNING` status in the database. These orphaned operations cannot be resumed because the validation requires status to be `FAILED` or `CANCELLED`.

**The Solution:**
On API startup, automatically mark all `RUNNING` operations as `FAILED`:

```python
@app.on_event("startup")
async def startup_recovery():
    """Recover interrupted operations on API startup."""
    operations_service = get_operations_service()
    recovered = await operations_service.recover_interrupted_operations()
    logger.info(f"Startup recovery: {recovered} operations marked as FAILED")
```

**Why This Works:**
- ✅ Handles the primary use case (API crash/restart)
- ✅ Simple, explicit recovery mechanism
- ✅ Makes interrupted operations immediately resumable
- ✅ Clear semantic: "operation didn't complete = failed"
- ✅ User sees clear history: original operation (FAILED) + resumed operation (COMPLETED)

**Example Flow:**
```
1. Training running at epoch 45/100 (status: RUNNING, checkpoint exists)
2. Docker container crashes
3. User restarts: ./start_ktrdr.sh
4. API startup: recover_interrupted_operations() marks op as FAILED
5. User: ktrdr operations list
   → op_training_001 | FAILED | Epoch 45/100 | 52 MB checkpoint
6. User: ktrdr operations resume op_training_001
7. Training continues from epoch 46/100
```
### 4.2 Training Integration
**Current Flow:**
```
TrainingService → LocalTrainingOrchestrator → TrainingPipeline → ModelTrainer
                                                                      ├─ train() loop
                                                                      └─ save final model
```
**Enhanced Flow:**
```
TrainingService → LocalTrainingOrchestrator → TrainingPipeline → ModelTrainer
                                                                      ├─ train() loop
                                                                      │   ├─ Check checkpoint policy
                                                                      │   └─ Save checkpoint if threshold reached
                                                                      └─ save final model
 
CheckpointService ← Called by ModelTrainer to save/load checkpoints
```
**What Changes:**
- `ModelTrainer.train()`: Add checkpoint checks in epoch loop
- `TrainingService`: Add `resume_training()` method
- No changes to TrainingPipeline or other components
### 4.3 Backtesting Integration
**Current Flow:**
```
BacktestingService → BacktestingEngine → run() loop
                                            ├─ Process bars
                                            └─ Generate results
```
**Enhanced Flow:**
```
BacktestingService → BacktestingEngine → run() loop
                                            ├─ Process bars
                                            │   ├─ Check checkpoint policy
                                            │   └─ Save checkpoint if threshold reached
                                            └─ Generate results
 
CheckpointService ← Called by BacktestingEngine to save/load checkpoints
```
**What Changes:**
- `BacktestingEngine.run()`: Add checkpoint checks in bar loop
- `BacktestingService`: Add `resume_backtest()` method
- Need to add state capture methods to `PositionManager`, `PerformanceTracker`
### 4.4 Result Storage Integration
**Current Result Stores:**
- Training: `ModelStorage` (file-based)
- Backtesting: Results returned in API response, optionally saved to file
**Checkpoint vs Results:**
| Aspect | Checkpoints | Final Results |
|--------|-------------|---------------|
| Purpose | Resume interrupted operations | Record completed work |
| Lifetime | Ephemeral (deleted on completion) | Permanent |
| Storage | PostgreSQL + disk artifacts | ModelStorage / backtest DB |
| Content | Full operation state | Summary metrics + trained model |
| Access | Via CheckpointService | Via ModelStorage / backtest query API |
**No Changes Required:**
- Checkpoints are separate concern from results
- When operation completes, results saved as before
- Checkpoints automatically cleaned up
---
## 5. User Experience
### 5.1 Normal Operation Flow (Success)
```
User: ktrdr models train --strategy config.yaml
 
[Training starts]
✓ Epoch 1/100 complete
✓ Epoch 5/100 complete → Checkpoint saved (5 min elapsed)
✓ Epoch 10/100 complete → Checkpoint saved (5 min elapsed)
...
✓ Epoch 100/100 complete
✓ Model saved to models/strategy/model_v1.0.0
✓ Checkpoints deleted (operation complete)
 
Result: Model saved, checkpoints cleaned up
```
### 5.2 Failure and Resume Flow
```
User: ktrdr models train --strategy config.yaml
 
[Training starts]
✓ Epoch 1/100 complete
✓ Epoch 5/100 complete → Checkpoint saved
...
✓ Epoch 45/100 complete → Checkpoint saved
✗ API crashes (out of memory)
 
[User restarts API]
 
User: ktrdr operations list
  op_training_20250117_100000 | FAILED | Epoch 45/100
 
User: ktrdr operations resume op_training_20250117_100000
✓ Resuming from epoch 45/100
✓ Created new operation: op_training_20250117_140000
✓ Loading checkpoint...
 
[Training continues from epoch 46]
✓ Epoch 46/100 complete
...
✓ Epoch 100/100 complete
✓ Model saved to models/strategy/model_v1.0.0
✓ Checkpoints deleted (operation complete)
 
Result: Training completed, 55 epochs saved
```
### 5.3 User Cancellation and Resume
```
User: ktrdr models train --strategy config.yaml
 
[Training starts]
✓ Epoch 1/100 complete
...
✓ Epoch 30/100 complete → Checkpoint saved
 
User: <Ctrl-C> (cancels operation)
✓ Operation cancelled at epoch 30/100
✓ Checkpoint preserved
 
[Later, user decides to resume]
 
User: ktrdr operations resume op_training_20250117_100000
✓ Resuming from epoch 30/100
✓ Created new operation: op_training_20250117_150000
 
[Training continues from epoch 31]
```
### 5.4 Operations API
**List Operations (Including Historical):**
```bash
GET /api/v1/operations
 
Response:
{
  "data": [
    {
      "operation_id": "op_training_20250117_100000",
      "status": "FAILED",
      "created_at": "2025-01-17T10:00:00Z",
      "progress_percentage": 45.0,
      "has_checkpoint": true,
      "checkpoint_size_mb": 52.3,
      "checkpoint_age_days": 2
    },
    {
      "operation_id": "op_training_20250117_140000",
      "status": "COMPLETED",
      "created_at": "2025-01-17T14:00:00Z",
      "progress_percentage": 100.0,
      "has_checkpoint": false,
      "checkpoint_size_mb": null,
      "checkpoint_age_days": null,
      "resumed_from": "op_training_20250117_100000"
    }
  ]
}
```
**Resume Operation:**
```bash
POST /api/v1/operations/{operation_id}/resume
 
Response:
{
  "success": true,
  "original_operation_id": "op_training_20250117_100000",
  "new_operation_id": "op_training_20250117_140000",
  "resumed_from_checkpoint": "checkpoint_epoch_45",
  "message": "Training will resume from epoch 46/100"
}
```
---
## 6. System Boundaries
### 6.1 What This System Does
✅ **Checkpoint Management:**
- Save operation state at time-based intervals
- Load checkpoints for resume
- Clean up checkpoints on completion
✅ **Resume Operations:**
- Create new operation from checkpoint
- Continue training from saved epoch
- Continue backtesting from saved bar
✅ **Operation Persistence:**
- Persist operation metadata across API restarts
- Query historical operations
### 6.2 What This System Does NOT Do
❌ **Real-Time Replication:**
- Does not persist every progress update (in-memory is fine)
- Does not provide sub-second recovery guarantees
❌ **Distributed Coordination:**
- Does not support multiple API instances sharing checkpoints
- No distributed locking or consensus
❌ **Version Migration:**
- Does not migrate checkpoints between KTRDR versions
- Checkpoints tied to specific version
❌ **Automatic Resume:**
- Does not automatically resume on API restart
- User must explicitly request resume
❌ **Result Archival:**
- Does not replace ModelStorage or backtest result storage
- Checkpoints are temporary, results are permanent
---
## 7. Success Metrics
### 7.1 Functional Metrics
- **Resume Success Rate:** >99% of resume attempts succeed
- **Checkpoint Coverage:** 100% of training/backtesting operations create checkpoints
- **Data Loss:** 0% data loss for completed operations
- **Recovery Time:** <30 seconds to resume from checkpoint
### 7.2 Performance Metrics
- **Checkpoint Overhead:** <1% of total operation time
- **Storage Efficiency:** <2 GB checkpoint storage at peak
- **Cleanup Success:** 100% of completed operations have checkpoints deleted within 1 minute
### 7.3 User Experience Metrics
- **Resume Usage:** Track how often users resume vs restart
- **Time Saved:** Measure epochs/bars saved by resume
- **User Satisfaction:** Qualitative feedback on resume reliability
---
## 8. Future Enhancements
While not in scope for initial release, these enhancements may be considered:
1. **Automatic Resume on API Restart**
   - Detect RUNNING operations on startup
   - Prompt user to resume or mark as failed
2. **Checkpoint Compression**
   - gzip model weights to reduce storage
   - Trade CPU time for disk space
3. **Checkpoint History Viewer**
   - UI to browse checkpoint timeline
   - Visualize metrics at each checkpoint
4. **Multi-Version Support**
   - Migrate checkpoints between KTRDR versions
   - Backwards compatibility for checkpoints
5. **Cloud Backup**
   - Replicate checkpoints to S3/GCS
   - Disaster recovery for long operations
6. **Selective Resume**
   - Resume from specific checkpoint (not just latest)
   - Useful for hyperparameter experiments
---
## 9. Risks and Mitigations
### 9.1 Risk: Checkpoint Corruption
**Scenario:** Power loss during checkpoint write corrupts data
**Mitigation:**
- Use PostgreSQL transactions (ACID guarantees)
- Write model artifacts to temporary location, then atomic rename
- UPSERT ensures atomic replacement of old checkpoint
### 9.2 Risk: Disk Space Exhaustion
**Scenario:** Too many checkpoints fill disk
**Mitigation:**
- Only 1 checkpoint per operation (UPSERT replaces old)
- Age-based deletion (delete >30 days old)
- Disk usage monitoring and alerts
- Configurable retention policies
### 9.3 Risk: Resume Failure
**Scenario:** Checkpoint loads but resume fails (model architecture changed, data missing)
**Mitigation:**
- Version checkpoints with KTRDR version
- Validate checkpoint integrity before resume
- Detailed error messages for debugging
- Keep original operation data for fallback
### 9.4 Risk: Performance Degradation
**Scenario:** Frequent checkpointing slows down training
**Mitigation:**
- Time-based policy prevents over-checkpointing (5 min intervals)
- Synchronous writes acceptable (620ms / 5min = 0.2% overhead)
- Configurable policies per operation type
- Performance monitoring and alerts
**Trade-off Analysis:**
- Synchronous: 0.2% overhead, simple implementation
- Async: ~0.0% overhead, complex implementation (race conditions, error handling)
- Decision: Synchronous preferred (negligible overhead, avoids complexity)
---
## 10. Technology Decisions
### 10.1 PostgreSQL-Only (No Redis)
**Write Load Analysis:**
```
Concurrent operations: 5 training + 5 backtesting = 10 operations
Checkpoint interval: 5 minutes
Write rate: 10 / 300 seconds = 0.033 writes/second
```

**PostgreSQL Capacity:**
- Can handle 1,000+ writes/second easily
- Utilization: 0.003% of capacity

**Why Not Redis?**
- Redis excels at high-frequency writes (1000s/sec) - we have 0.033/sec
- Redis requires additional deployment, monitoring, backup
- PostgreSQL ACID guarantees more important than Redis speed
- Can add Redis later if bottleneck emerges (it won't)

**Conclusion:**
PostgreSQL will not notice this load. Write throughput is **5 orders of magnitude below capacity**. Redis would add deployment complexity for zero performance benefit.

### 10.2 ONE Checkpoint Per Operation
**Rationale:**
- Only need latest checkpoint for resume
- UPSERT pattern simpler than INSERT + cleanup
- 10x disk reduction (10 GB → 1 GB)
- Simpler retention logic
- Faster queries (PK lookup vs range scan)

**Trade-offs:**
- ❌ Cannot resume from earlier checkpoint
- ✅ Simpler implementation
- ✅ Lower disk usage
- ✅ Faster operations

---
## 11. Conclusion
The Checkpoint Persistence System provides essential resilience for KTRDR's long-running operations without sacrificing simplicity or performance. By adapting checkpoint frequency to operation speed and treating checkpoints as ephemeral artifacts, the system delivers reliable resume capability while minimizing storage overhead and operational complexity.
**Key Innovations:**
1. **Time-Based Checkpointing:** Adapts to fast/slow operations automatically
2. **ONE Checkpoint Per Operation:** UPSERT replaces old checkpoint (10x disk reduction)
3. **Ephemeral Design:** Checkpoints deleted on completion, not archived
4. **Clean Resume Semantics:** New operation ID for resumed work
5. **PostgreSQL-Only:** No additional infrastructure dependencies (0.003% utilization)
6. **Startup Recovery:** Automatically recovers interrupted operations on API restart

**Critical Design Decision:**
The system handles the **primary use case (API crashes)** through automatic startup recovery:
- On API startup, all RUNNING operations → FAILED
- Makes crashed operations immediately resumable
- No manual intervention required
- Clear audit trail: original (FAILED) + resumed (COMPLETED)

**Next Steps:**
- Review and approve design document
- Proceed to architecture document for technical details
- Develop implementation plan with phased delivery
