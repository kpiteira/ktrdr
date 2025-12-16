# Checkpoint & Resilience: Implementation Plan Overview

**Created:** 2024-12-15
**Status:** Ready for implementation
**Source:** [DESIGN.md](DESIGN.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [VALIDATION.md](VALIDATION.md)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Milestones | 8 |
| Estimated Tasks | ~56 |
| Core Milestones (M1-M6) | Unblocked, sequential |
| Blocked Milestone | M7 (depends on agent work) |

---

## Milestone Overview

```
M1: Operations Persistence + Re-Registration
 │
 ├──► M2: Orphan Detection
 │
 ├──► M3: Training Checkpoint Save
 │     │
 │     └──► M4: Training Resume
 │           │
 │           ├──► M5: Backtesting Checkpoint + Resume
 │           │
 │           ├──► M6: Graceful Shutdown (SIGTERM)
 │           │
 │           └──► M7: Backend-Local Operations [BLOCKED: needs agent work]
 │
 └──► M8: Polish + Admin (after M1-M6)
```

---

## Milestones

### M1: Operations Persistence + Worker Re-Registration
**Branch:** `feature/checkpoint-m1-operations-persistence`

**Capability:** Operations persist to database; workers re-register after backend restart; operation status syncs automatically.

**Why First:** This is the foundation. Without persistent operations and re-registration, checkpointing has nothing to attach to.

**E2E Test:** Start training → restart backend → worker re-registers → operation shows correct status.

**Plan:** [PLAN_M1_operations_persistence.md](PLAN_M1_operations_persistence.md)

---

### M2: Orphan Detection
**Branch:** `feature/checkpoint-m2-orphan-detection`

**Capability:** RUNNING operations with no worker are detected and marked FAILED after timeout.

**Why Second:** Completes the resilience story. M1 handles "worker alive, backend restarted"; M2 handles "worker dead".

**E2E Test:** Start training → kill worker → wait 60s → operation marked FAILED.

**Plan:** [PLAN_M2_orphan_detection.md](PLAN_M2_orphan_detection.md)

---

### M3: Training Checkpoint Save
**Branch:** `feature/checkpoint-m3-training-checkpoint-save`

**Capability:** Training saves checkpoints periodically, on cancellation, and on failure.

**Why Third:** Now that operations are persistent and resilient, we can add checkpoint infrastructure.

**E2E Test:** Start training → let it run to epoch 10 → verify checkpoint exists in DB + filesystem.

**Plan:** [PLAN_M3_training_checkpoint_save.md](PLAN_M3_training_checkpoint_save.md)

---

### M4: Training Resume
**Branch:** `feature/checkpoint-m4-training-resume`

**Capability:** User can resume cancelled/failed training from checkpoint.

**Why Fourth:** Proves the checkpoint system works end-to-end.

**E2E Test:** Start training → cancel at epoch 25 → resume → training continues from epoch 25 → completes.

**Plan:** [PLAN_M4_training_resume.md](PLAN_M4_training_resume.md)

---

### M5: Backtesting Checkpoint + Resume
**Branch:** `feature/checkpoint-m5-backtesting-checkpoint`

**Capability:** Backtesting saves/restores portfolio state; indicators recomputed on resume.

**Why Fifth:** Extends checkpoint system to second operation type, validates the abstraction.

**E2E Test:** Start backtest → cancel at bar 5000 → resume → backtest continues → final results match uninterrupted run.

**Plan:** [PLAN_M5_backtesting_checkpoint.md](PLAN_M5_backtesting_checkpoint.md)

---

### M6: Graceful Shutdown (SIGTERM)
**Branch:** `feature/checkpoint-m6-graceful-shutdown`

**Capability:** Workers save checkpoint and update status to CANCELLED on SIGTERM.

**Why Sixth:** Infrastructure resilience for maintenance scenarios.

**E2E Test:** Start training → `docker stop worker` → checkpoint saved → status=CANCELLED → can resume.

**Plan:** [PLAN_M6_graceful_shutdown.md](PLAN_M6_graceful_shutdown.md)

---

### M7: Backend-Local Operations
**Branch:** `feature/checkpoint-m7-backend-local`

**Capability:** Backend-local operations (agent system) marked FAILED on restart, with checkpoint support.

**Blocked:** Depends on agent system work being complete.

**E2E Test:** Start agent design → restart backend → operation marked FAILED → checkpoint available → can resume.

**Plan:** [PLAN_M7_backend_local_ops.md](PLAN_M7_backend_local_ops.md)

---

### M8: Polish + Admin
**Branch:** `feature/checkpoint-m8-polish`

**Capability:** Concurrent resume protection, checkpoint cleanup, CLI enhancements.

**Why Last:** Edge cases and UX polish after core functionality works.

**E2E Test:** Multiple scenarios for edge cases.

**Plan:** [PLAN_M8_polish.md](PLAN_M8_polish.md)

---

## Key Decisions (from Validation)

These decisions shape the implementation:

1. **Layered Truth Model:** Worker=running, DB=terminal states, Checkpoint=resumability
2. **Operations in DB:** Full persistence, not just in-memory
3. **Workers report completed operations:** On re-registration, include what finished
4. **Optimistic locking for resume:** DB-level race protection
5. **PENDING_RECONCILIATION state:** Temporary state during backend restart

See [VALIDATION.md](VALIDATION.md) for full details.

---

## Dependencies

### Internal Dependencies
- M2-M8 all depend on M1
- M4 depends on M3
- M5, M6, M7 depend on M4
- M7 is blocked on agent system work (separate branch)

### External Dependencies
- PostgreSQL (already in use)
- Shared filesystem for checkpoint artifacts (Docker volume or NFS)

---

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M1 | OperationsService refactor touches many files | Careful testing, feature flag if needed |
| M3 | Training state serialization complexity | Research task first, validate with real training |
| M5 | Indicator recomputation on resume | May need strategy-specific logic |
| M7 | Agent system integration | Wait for agent work to stabilize |

---

## How to Use This Plan

1. **Start with M1:** Read [PLAN_M1_operations_persistence.md](PLAN_M1_operations_persistence.md)
2. **Use /ktask:** Each task is structured for `/ktask` command
3. **Run E2E tests:** Each milestone has a verification script
4. **Sequential delivery:** Complete M1 before M2, etc.

---

## File Index

| File | Description |
|------|-------------|
| [DESIGN.md](DESIGN.md) | Problem statement, user journeys, decisions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical design, components, data flow |
| [VALIDATION.md](VALIDATION.md) | Scenario traces, gap analysis, contracts |
| [PLAN_overview.md](PLAN_overview.md) | This file |
| [PLAN_M1_operations_persistence.md](PLAN_M1_operations_persistence.md) | M1 detailed tasks |
| [PLAN_M2_orphan_detection.md](PLAN_M2_orphan_detection.md) | M2 detailed tasks |
| [PLAN_M3_training_checkpoint_save.md](PLAN_M3_training_checkpoint_save.md) | M3 detailed tasks |
| [PLAN_M4_training_resume.md](PLAN_M4_training_resume.md) | M4 detailed tasks |
| [PLAN_M5_backtesting_checkpoint.md](PLAN_M5_backtesting_checkpoint.md) | M5 detailed tasks |
| [PLAN_M6_graceful_shutdown.md](PLAN_M6_graceful_shutdown.md) | M6 detailed tasks |
| [PLAN_M7_backend_local_ops.md](PLAN_M7_backend_local_ops.md) | M7 detailed tasks |
| [PLAN_M8_polish.md](PLAN_M8_polish.md) | M8 detailed tasks |
