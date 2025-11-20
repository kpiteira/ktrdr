# Checkpoint Implementation Plan v2

Based on [Design Spec](checkpoint-simplified-spec.md) and [Architecture](checkpoint-architecture.md).

---

## Phase 0: Research & Prep

### Task 0.1: Analyze Training Checkpoint Data

**Goal:** Determine NECESSARY and SUFFICIENT data for training resume.

**Research:**

- Read ModelTrainer code - what state exists at epoch boundary?
- Read existing PyTorch checkpoint patterns
- List all state that changes during training
- Determine minimum set for successful resume

**Output:** Document in architecture spec - confirmed list of training state + artifacts.

**Validation:** Can manually serialize/deserialize this state and continue training?

### Task 0.2: Analyze Backtesting Checkpoint Data

**Goal:** Determine NECESSARY and SUFFICIENT data for backtesting resume.

**Research:**

- Read BacktestingEngine code - what state exists at bar boundary?
- List all state: positions, trades, equity, indicators
- Determine if indicators need recalculation or can be restored

**Output:** Document in architecture spec - confirmed list of backtesting state.

**Validation:** Can manually serialize/deserialize this state and continue backtest?

### Task 0.3: Review Integration Points

**Goal:** Understand how checkpoint components integrate with existing code.

**Research:**

- How does ProgressBridge currently work?
- How does CancellationToken notify observers?
- Where in ModelTrainer/BacktestingEngine to call update_state()?
- Where does WorkerAPIBase need modification?

**Output:** List of files to modify and integration approach.

---

## Phase 1: Core Checkpoint Service

### Task 1.1: CheckpointService CRUD

**Implement:**

- `save_checkpoint()` - write state to DB, artifacts to filesystem
- `load_checkpoint()` - read from DB + filesystem
- `delete_checkpoint()` - cleanup both
- Atomic writes (temp → rename pattern)

**Test:** Unit tests for CRUD operations, artifact file creation.

**Validation:** Save checkpoint, restart process, load checkpoint - data intact.

### Task 1.2: CheckpointPolicy

**Implement:**

- `should_checkpoint(context)` - evaluate triggers
- Time-based trigger (X minutes since last)
- Unit-based trigger (N epochs/bars since last)
- Default returns false (no checkpointing)

**Test:** Unit tests for trigger logic with various contexts.

### Integration Test: Phase 1

**Test:** Save checkpoint with real DB and filesystem, restart process, load back.

- Verify DB row exists with correct metadata
- Verify artifact files exist on disk
- Verify loaded data matches saved data

---

## Phase 2: ProgressBridge Integration

### Task 2.1: Extend ProgressBridge for Checkpointing

**Implement:**

- Add CheckpointService and CheckpointPolicy to bridge
- `update_state()` - cache state + check if should checkpoint
- Observe CancellationToken for cancellation saves
- `build_checkpoint_data()` abstraction for worker-specific data

**Test:** Unit tests for bridge checkpoint flow.

### Task 2.2: Training ProgressBridge

**Implement:**

- TrainingProgressBridge with checkpoint support
- `build_checkpoint_data()` returns training state + artifact paths
- Write artifacts to filesystem in update_state()
- Integration with ModelTrainer's epoch completion

**Test:** Integration test - training creates checkpoints at configured intervals.

**Validation:** Run training, verify checkpoints created with correct data.

### Task 2.3: Backtesting ProgressBridge

**Implement:**

- BacktestingProgressBridge with checkpoint support
- `build_checkpoint_data()` returns backtesting state
- Integration with BacktestingEngine's bar processing

**Test:** Integration test - backtesting creates checkpoints.

### Integration Test: Phase 2

**Test:** Run actual training/backtesting with checkpoint triggers.

- Start training, run 15 epochs with checkpoint every 10
- Verify checkpoint created at epoch 10
- Start backtest, run 15000 bars with checkpoint every 10000
- Verify checkpoint created at bar 10000
- Cancel mid-operation, verify cancellation checkpoint created

---

## Phase 3: Resume Flow

### Task 3.1: Worker Resume Endpoint

**Implement:**

- `POST /resume` endpoint on workers
- Load checkpoint via CheckpointService
- Call `restore_from_checkpoint()` on worker
- Continue operation from restored state

**Test:** Unit test for resume endpoint.

### Task 3.2: Training Resume

**Implement:**

- `restore_from_checkpoint()` in TrainingWorker
- Load model weights, optimizer state, epoch counter
- Resume training loop from restored epoch

**Test:** Integration test - cancel training, resume, verify continues correctly.

**Validation:** Full cycle - train to epoch 10, cancel, resume, train to epoch 100.

### Task 3.3: Backtesting Resume

**Implement:**

- `restore_from_checkpoint()` in BacktestingWorker
- Load portfolio state, bar index, trade history
- Resume backtest from restored bar

**Test:** Integration test - cancel backtest, resume, verify results match.

**Validation:** Full cycle - backtest to bar 5000, cancel, resume, complete.

### Integration Test: Phase 3

**Test:** Full resume cycle for both operation types.

- Training: Start → Cancel at epoch 10 → Resume → Verify continues from epoch 10
- Backtesting: Start → Cancel at bar 5000 → Resume → Verify continues from bar 5000
- Verify resumed operation produces correct final results

---

## Phase 4: Backend Orchestration

### Task 4.1: Resume API Endpoint

**Implement:**

- `POST /operations/{id}/resume` in backend
- Load checkpoint metadata from DB
- Dispatch to available worker
- Create new operation linked to original

**Test:** API test for resume endpoint.

### Task 4.2: Checkpoint List/Cleanup API

**Implement:**

- `GET /checkpoints` - list checkpoints with filters
- `DELETE /checkpoints/{id}` - manual cleanup
- Age-based cleanup job (configurable max age)

**Test:** API tests for list/cleanup endpoints.

### Integration Test: Phase 4

**Test:** Backend orchestration with real workers.

- Call resume API endpoint, verify worker receives dispatch
- List checkpoints API returns correct data
- Cleanup removes old checkpoints from both DB and filesystem

---

## Phase 5: End-to-End Validation

### Task 5.1: Training E2E Test

**Test scenario:**

1. Start training (100 epochs)
2. Cancel at epoch 30
3. Verify checkpoint exists with artifacts
4. Resume operation
5. Verify training continues from epoch 30
6. Complete to epoch 100
7. Verify final model quality matches uninterrupted run

### Task 5.2: Backtesting E2E Test

**Test scenario:**

1. Start backtest (10000 bars)
2. Cancel at bar 5000
3. Verify checkpoint exists
4. Resume operation
5. Verify backtest continues from bar 5000
6. Complete to bar 10000
7. Verify results match uninterrupted run

### Task 5.3: Edge Cases

**Test:**

- Cancel before first periodic checkpoint (uses cached state)
- Resume with missing artifacts (error handling)
- Concurrent resume attempts (should fail)
- Cleanup while operation running (should skip)

---

## Validation Gates

**After Phase 0:** Research complete, architecture spec updated with confirmed data lists.

**After Phase 1:** CheckpointService works standalone - can save/load checkpoints.

**After Phase 2:** Training/backtesting create checkpoints during execution.

**After Phase 3:** Can resume from checkpoint - full training/backtesting cycle works.

**After Phase 4:** Backend can orchestrate resume via API.

**After Phase 5:** All E2E tests pass, edge cases handled.

---

## Estimated Effort

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Phase 0 | Research & prep | 1 day |
| Phase 1 | Core service | 1 day |
| Phase 2 | Bridge integration | 2 days |
| Phase 3 | Resume flow | 2 days |
| Phase 4 | Backend orchestration | 1 day |
| Phase 5 | E2E validation | 1 day |

**Total: ~8 days**

---

## Key Lessons from v1

1. **Research first** - Phase 0 ensures we know what data to save BEFORE coding
2. **Validate after each phase** - Don't proceed until current phase works
3. **Bridge owns checkpointing** - ModelTrainer/BacktestingEngine stay pure
4. **Artifacts on filesystem** - Don't forget to actually write them
5. **Test resume cycle** - Save → Cancel → Resume → Complete must work
