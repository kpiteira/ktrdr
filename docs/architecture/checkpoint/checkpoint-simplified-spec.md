# Checkpoint System - Design Spec

**Goal:** Save operation state so training/backtesting can resume after interruption.

---

## Core Requirements

### R1: Save Training State

- Model weights, optimizer state, training history
- Large binary artifacts (model.pt) separate from metadata

### R2: Save Backtesting State

- Bar index, positions, trades, equity curve
- Small state, no large artifacts

### R3: Checkpoint Triggers

- **Periodic:** Every N epochs or N minutes (configurable)
- **Time-based:** Every X minutes regardless of progress
- **On Failure:** Save state when operation fails
- **On Cancellation:** Save state when user cancels

### R4: Resume From Checkpoint

- Load state and continue from where left off
- Resume point TBD: restart partial unit or continue mid-unit?
- Creates NEW operation (linked to original)

### R5: Cleanup

- Delete checkpoint when operation completes successfully
- Keep checkpoint when operation fails/cancelled (for resume)
- Age-based cleanup: delete checkpoints > 30 days old

### R6: Handle Interruptions

- API crash: startup recovery marks RUNNING -> FAILED
- User cancel: save checkpoint before marking CANCELLED
- Worker shutdown: save checkpoint on SIGTERM

---

## Critical Gotchas

### G1: Large Artifacts Need Special Handling

Don't store 100-500MB model weights in JSON/DB columns. Architecture must address this.

### G2: Cache State Continuously

Only caching at checkpoint time means early cancellation loses progress. Must cache after every epoch.

### G3: Distributed Access

Backend and workers need to access same checkpoint data. Architecture must address shared storage.

### G4: Progress Bridge Must Cache State

When cancelling, need to retrieve current state from running operation. Bridge must cache it.

---

## What "Done" Looks Like

### Checkpoint Save

- [ ] Can save checkpoint with large artifacts
- [ ] Artifacts accessible after API restart
- [ ] UPSERT replaces old checkpoint

### Training Resume

- [ ] Start training, cancel at epoch 10
- [ ] Resume, training continues from epoch 11
- [ ] Final model trained for all 100 epochs

### Backtesting Resume

- [ ] Start backtest, cancel at bar 5000
- [ ] Resume, backtest continues from bar 5001
- [ ] Final results match uninterrupted run

### Cancellation Checkpoint

- [ ] Cancel training before any periodic checkpoint
- [ ] Checkpoint still created with current state
- [ ] Can resume from cancellation checkpoint

### Distributed Resume

- [ ] Backend sends only operation_id to worker
- [ ] Worker loads checkpoint from shared storage
- [ ] No large data sent over HTTP

---

## Out of Scope (For Now)

- Redis caching
- Multi-version checkpoint migration
- Automatic resume on startup
- Cloud backup of checkpoints
- Selective resume from earlier checkpoint

---

**Answer to your question:** Yes, DB and filesystem details should go in the **architecture** document, not here. This spec defines WHAT we need (save state, resume, triggers), architecture defines HOW (PostgreSQL + filesystem, shared volumes, etc.).
