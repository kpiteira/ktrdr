# Checkpoint & Resilience System: Design Validation

**Date:** 2024-12-15
**Documents Validated:**
- Design: [DESIGN.md](DESIGN.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Scope: Full checkpoint and resilience system

---

## Validation Summary

**Scenarios Validated:** 12 scenarios traced through architecture
**Critical Gaps Found:** 4 (all resolved)
**Interface Contracts:** Defined for DB schema, API endpoints, state machines

---

## Key Decisions Made

These decisions emerged from scenario analysis and gap resolution:

### D1: Layered Truth Model

**Decision:** Different sources of truth for different questions.

| Question | Source of Truth | Rationale |
|----------|-----------------|-----------|
| "Is it running?" | Worker (live process) | Only a live process knows if it's actually executing |
| "What's the final outcome?" | Database | Durable record of terminal states |
| "Can we resume?" | Checkpoint exists | Artifact is proof of resumability |

**Context:** Initial design assumed DB could be single source of truth, but workers can complete/fail without DB knowing (network partition, backend down). This layered model handles all divergence scenarios.

### D2: Operations Persisted to Database

**Decision:** Add `operations` table to persist all operation state.

**Context:** OperationsService was purely in-memory. After backend restart:
- Worker operations could recover via re-registration
- Backend-local operations (agent system) would be lost completely
- OrphanDetector couldn't function (nothing to check against)

**Trade-off accepted:** Additional DB dependency and migration. Worth it for complete resilience story.

### D3: Worker Re-Registration Includes Completed Operations

**Decision:** Workers report both `current_operation_id` AND `completed_operations[]` on registration.

**Context:** Scenario 2 ("Worker completed, DB doesn't know") revealed that a worker could finish while backend was down. On re-registration, worker would report "idle" but DB would show "RUNNING" forever.

**Solution:** Workers track recently completed operations and report them on re-registration:
```json
{
  "current_operation_id": null,
  "completed_operations": [
    {"operation_id": "op_123", "status": "COMPLETED", "result": {...}}
  ]
}
```

### D4: Optimistic Locking for Resume

**Decision:** Use DB-level optimistic locking to prevent concurrent resume race condition.

**Implementation:**
```sql
UPDATE operations
SET status = 'RUNNING'
WHERE operation_id = ? AND status IN ('CANCELLED', 'FAILED')
RETURNING operation_id
```

If no rows returned, another request won the race.

### D5: PENDING_RECONCILIATION State

**Decision:** Add temporary state for operations during backend restart reconciliation.

**Context:** After backend restart, we don't immediately know if workers are alive. Need to wait for re-registration before marking orphans as FAILED.

**Flow:**
1. Backend restarts, finds RUNNING operations in DB
2. Marks worker-based operations as PENDING_RECONCILIATION
3. Waits 60s for workers to re-register and claim operations
4. Unclaimed operations marked FAILED

---

## Scenarios Validated

### Happy Paths

1. **Backend Restart During Training**: Worker detects missed health checks, re-registers with `current_operation_id`, operation status syncs correctly.

2. **Training Cancel and Resume**: User cancels, checkpoint saved, user resumes, training continues from checkpoint epoch.

3. **Periodic Checkpoint Covers Failure**: Worker crashes after periodic checkpoint, user resumes from last checkpoint.

4. **Backtesting Cancel and Resume**: Portfolio state and trade history saved, indicators recomputed on resume, backtest continues.

### Error Paths

5. **Resume Without Checkpoint**: Clear error message with reasons (completed, expired, never saved).

6. **Resume With Corrupted Checkpoint**: Artifact validation detects missing files, returns CHECKPOINT_CORRUPTED.

7. **Worker Crash Before First Checkpoint**: Operation marked FAILED, resume fails with clear message.

### Edge Cases

8. **Backend Restart + Worker Dead**: PENDING_RECONCILIATION → timeout → FAILED.

9. **Graceful Shutdown (SIGTERM)**: Worker saves checkpoint, updates status to CANCELLED, exits cleanly.

10. **Resume Fails, Retry**: New periodic checkpoints overwrite original. Retry resumes from latest (documented behavior).

### Integration Boundaries

11. **DB Write Fails After Artifact Write**: Best-effort cleanup, operation continues without checkpoint.

12. **Concurrent Resume Attempts**: Optimistic locking ensures only one succeeds.

---

## Interface Contracts

### Database Schema

```sql
-- Operations table (source of truth for operation state)
CREATE TABLE operations (
    operation_id VARCHAR(255) PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,

    -- Ownership
    worker_id VARCHAR(255),
    is_backend_local BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Progress snapshot
    progress_percent FLOAT DEFAULT 0,
    progress_message VARCHAR(500),

    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}',

    -- Result/Error
    result JSONB,
    error_message TEXT,

    -- Reconciliation
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    reconciliation_status VARCHAR(50)
);

CREATE INDEX idx_operations_status ON operations(status);
CREATE INDEX idx_operations_worker ON operations(worker_id);

-- Checkpoints table
CREATE TABLE operation_checkpoints (
    operation_id VARCHAR(255) PRIMARY KEY REFERENCES operations(operation_id),
    checkpoint_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    state JSONB NOT NULL,
    artifacts_path VARCHAR(500),
    state_size_bytes INTEGER,
    artifacts_size_bytes BIGINT
);
```

### Worker Registration Request

```json
{
  "worker_id": "training-worker-abc123",
  "worker_type": "training",
  "endpoint_url": "http://192.168.1.201:5004",
  "capabilities": {"gpu": true},
  "current_operation_id": "op_training_123",
  "completed_operations": [
    {
      "operation_id": "op_training_456",
      "status": "COMPLETED",
      "result": {"model_path": "/models/v1/model.pt"},
      "completed_at": "2024-12-13T15:30:00Z"
    }
  ]
}
```

### Resume Endpoint

**Endpoint:** `POST /api/v1/operations/{operation_id}/resume`

**Success Response (200):**
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_123",
    "status": "RUNNING",
    "resumed_from": {
      "checkpoint_type": "cancellation",
      "created_at": "2024-12-13T14:35:00Z",
      "epoch": 29
    }
  }
}
```

**Error Responses:**
- 404: Operation not found / No checkpoint available
- 409: Operation already running / Operation already completed
- 422: Checkpoint corrupted

### State Machine

```
PENDING ──start──► RUNNING ◄──resume───┐
                     │                  │
          ┌─────────┼─────────┐        │
          │         │         │        │
       complete   cancel    fail       │
          │         │         │        │
          ▼         ▼         ▼        │
     COMPLETED  CANCELLED   FAILED ────┘
                     │         │
                     └────┬────┘
                          │
                   (if checkpoint exists)

Special: PENDING_RECONCILIATION
  - Set on backend restart for worker-based RUNNING operations
  - Transitions to RUNNING (worker re-registers) or FAILED (timeout)
```

### Checkpoint State Shapes

**Training:**
```python
state = {
    "epoch": 29,
    "train_loss": 0.28,
    "val_loss": 0.31,
    "learning_rate": 0.001,
    "best_val_loss": 0.29,
    "training_history": {"loss": [...], "val_loss": [...]},
    "original_request": {"strategy_path": "...", "symbol": "EURUSD", ...}
}
artifacts = ["model.pt", "optimizer.pt", "scheduler.pt", "best_model.pt"]
```

**Backtesting:**
```python
state = {
    "bar_index": 7000,
    "current_date": "2020-07-28",
    "cash": 102456.00,
    "positions": [],
    "trades": [{...}, {...}],
    "equity_samples": [{"bar_index": 0, "equity": 100000}, ...],
    "original_request": {"strategy": "...", "symbol": "EURUSD", ...}
}
artifacts = []  # No filesystem artifacts
```

### Reconciliation Protocol

**On Backend Startup:**
```
For each operation WHERE status = 'RUNNING':
    IF is_backend_local:
        → Mark FAILED (process died)
        → Include checkpoint availability in error message
    ELSE:
        → Mark PENDING_RECONCILIATION
        → Wait for worker re-registration (60s timeout)
```

**On Worker Re-Registration:**
```
1. Process completed_operations[] → Update DB to terminal states
2. If current_operation_id:
   - DB status COMPLETED → Send STOP to worker
   - DB status FAILED/CANCELLED/PENDING_RECONCILIATION → Update to RUNNING
   - DB status RUNNING → Update heartbeat
   - DB has no record → Create record
```

---

## Implementation Milestones

### Milestone 1: Operations Persistence + Resume Happy Path

**User Story:** User can resume a cancelled training operation.

**Scope:**
- DB: `operations` + `operation_checkpoints` tables
- OperationsService: DB-backed CRUD
- CheckpointService: Save/load checkpoints
- Training worker: Periodic/cancellation checkpoint, restore
- API: `POST /operations/{id}/resume`
- CLI: `ktrdr operations resume <id>`

**E2E Test:**
```
Given: Training started, cancelled at epoch 25
When: ktrdr operations resume op_123
Then: Training continues from epoch 25, completes successfully
```

---

### Milestone 2: Worker Re-Registration + Reconciliation

**User Story:** Backend restart doesn't lose running operations.

**Scope:**
- Worker: Re-registration monitor (detect missed health checks)
- Worker: `current_operation_id` + `completed_operations` in registration
- Backend: Reconciliation logic on registration
- Backend: Startup reconciliation, PENDING_RECONCILIATION state

**E2E Test:**
```
Given: Training running at epoch 30
When: Backend restarts
Then: Within 60s, operation shows RUNNING with correct progress
```

---

### Milestone 3: Orphan Detection + Backend-Local Operations

**User Story:** Orphan operations get marked FAILED; backend-local ops handle restart.

**Scope:**
- OrphanDetector: Background loop, timeout logic
- Backend startup: Mark backend-local RUNNING → FAILED
- Agent system integration (when ready)

**E2E Test:**
```
Given: Training running, worker dies
When: 60 seconds pass
Then: Operation marked FAILED, checkpoint available for resume
```

---

### Milestone 4: Backtesting Checkpoint + Graceful Shutdown

**User Story:** Backtest can be resumed; SIGTERM saves checkpoint.

**Scope:**
- Backtest worker: Checkpoint state, restore, indicator recomputation
- All workers: SIGTERM handler, status update before exit

**E2E Test:**
```
Given: Backtest at bar 10000
When: Worker receives SIGTERM
Then: Checkpoint saved, status=CANCELLED, resume works
```

---

### Milestone 5: Polish + Edge Cases

**Scope:**
- Concurrent resume protection (optimistic locking verified)
- Checkpoint cleanup (periodic sweep, orphan artifacts)
- Checkpoint corruption detection and reporting
- CLI: `operations list --resumable`
- Documentation updates

---

## Open Questions (To Resolve During Implementation)

1. **Checkpoint interval tuning:** Default 10 epochs / 10,000 bars — validate with real workloads.

2. **Equity curve sampling:** Every 1000 bars? Or compute full curve on resume?

3. **Completed operations retention:** How long should workers remember completed operations for re-registration reporting?

4. **Agent checkpoint scope:** What state needs checkpointing for agent design sessions?

---

## Appendix: Consistency Model

### The Three Sources of Truth

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LAYERED TRUTH MODEL                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   "Is it currently running?"                                        │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  WORKER is source of truth                                   │  │
│   │  - Only a live process knows if it's executing               │  │
│   │  - Worker re-registration is how we learn                    │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   "What's the final outcome?"                                       │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  DATABASE is source of truth                                 │  │
│   │  - Durable record of COMPLETED/FAILED/CANCELLED              │  │
│   │  - Survives all restarts                                     │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   "Can we resume this operation?"                                   │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │  CHECKPOINT EXISTS is source of truth                        │  │
│   │  - Artifact is proof of resumability                         │  │
│   │  - Independent of status                                     │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Divergence Scenarios and Resolution

| DB Status | Worker Status | Resolution |
|-----------|---------------|------------|
| RUNNING | RUNNING | Happy path ✓ |
| RUNNING | COMPLETED | Worker reports on re-registration → DB updated |
| RUNNING | DEAD | OrphanDetector → FAILED after timeout |
| COMPLETED | RUNNING | Trust DB → Send STOP to worker |
| FAILED | RUNNING | Worker wins → Update DB to RUNNING |
| (none) | RUNNING | Create DB record |
| RUNNING (backend-local) | (restart) | Mark FAILED (process died) |
