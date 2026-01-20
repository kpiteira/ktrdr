# v2.6 Multi-Research Coordination: Architecture

## Overview

This document describes the architectural changes to support multiple concurrent research cycles. The core change is transforming the research worker from managing one research to managing N researches in a single polling loop.

**Key insight:** The existing phase handlers are already stateless — they take an operation_id, check the operation's state, and advance if ready. The refactor is about loop structure, not phase logic.

---

## Components

### Component 1: AgentResearchWorker (Modified)

**Location:** `ktrdr/agents/workers/research_worker.py`

**Current responsibility:** Run one research cycle via polling loop.

**New responsibility:** Run N research cycles via single polling loop.

**Architectural change:**

The current `run(operation_id)` method contains a `while True` loop that polls one operation and advances it through phases. The phase handlers (`_handle_designing_phase`, `_handle_training_phase`, etc.) are already stateless — they take an operation_id and operate on whatever state they find.

The change: instead of looping on one operation, loop over all active AGENT_RESEARCH operations and advance each one step per cycle.

**What stays the same:**
- All phase handler methods — they already work on any operation_id
- All phase start methods — unchanged
- Gate checks — unchanged
- Metrics recording — unchanged

**What changes:**
- Loop structure: iterate over N operations instead of one
- Cancellation: handle per-operation instead of single operation
- Error isolation: one failing research doesn't stop others

---

### Component 2: AgentService (Modified)

**Location:** `ktrdr/api/services/agent_service.py`

**Current responsibility:** Trigger/cancel/status for single research.

**New responsibility:** Trigger/cancel/status for multiple researches.

**Architectural changes:**

1. **trigger()**: Remove the "active cycle exists" rejection. Replace with a capacity check that compares active count against the concurrency limit.

2. **get_status()**: Return information about all active researches, not just one. Include worker utilization and budget status.

3. **cancel()**: Already accepts operation_id — no architectural change needed. Verify CLI can pass specific operation_id.

4. **Coordinator lifecycle**: The coordinator loop should start on first trigger (if not running) and continue running while any researches are active. When all complete, it can stop until the next trigger.

---

### Component 3: Concurrency Limit

**Responsibility:** Determine maximum concurrent researches.

**Formula:** `training_workers + backtest_workers + buffer`

The buffer (default 1) allows researches in design/assessment phases while workers are fully utilized for training/backtest.

**Discovery:** Query the worker registry for current worker counts. The registry already tracks registered workers by type.

**Override:** Environment variable for manual limit (useful for testing or conservative rollout).

---

## Data Flow

### Multi-Research Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MULTI-RESEARCH FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

User triggers research A
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ AgentService    │────▶│ Create          │
│ trigger()       │     │ AGENT_RESEARCH  │
│                 │     │ operation A     │
│ Check capacity  │     └────────┬────────┘
│ Check budget    │              │
└─────────────────┘              │
         │                       │
         │ Start coordinator     │
         │ (if not running)      │
         ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COORDINATOR LOOP (single task)                          │
│                                                                              │
│    ┌──────────────────────────────────────────────────────────────────┐     │
│    │  while True:                                                      │     │
│    │      active_ops = get_active_research_operations()               │     │
│    │                                                                   │     │
│    │      for op in active_ops:                                       │     │
│    │          advance_research(op)  ◄─── Advances each one step       │     │
│    │                                                                   │     │
│    │      sleep(POLL_INTERVAL)                                        │     │
│    └──────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│    Research A: IDLE ──▶ DESIGNING ──▶ TRAINING ──▶ BACKTESTING ──▶ ...     │
│    Research B: IDLE ──▶ DESIGNING ──▶ TRAINING ──▶ ...                      │
│    Research C: IDLE ──▶ DESIGNING ──▶ ...                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Worker Utilization

```
Time ──────────────────────────────────────────────────────────────────────▶

Research A:  [DESIGN]  [─────TRAINING─────]  [───BACKTEST───]  [ASSESS]
Research B:       [DESIGN]  [─────TRAINING─────]  [───BACKTEST───]  [ASSESS]
Research C:            [DESIGN]  [───TRAINING───]  [──BACKTEST──]  [ASSESS]

Workers:
Training 1:  ░░░░░░░░░░[████████████████████]░░░░░░░░░░░░░░░░░[████████████]
Training 2:  ░░░░░░░░░░░░░░░░░[████████████████████]░░░░░░░░░░[████████]░░░░
Backtest 1:  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[████████████████]░░░░░░░░░░░░░
Backtest 2:  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[████████████████]░░░░░░░

Legend: [████] = busy, ░░░░ = idle
```

---

## State Machine

**No changes to the state machine itself.** Each research follows the same flow:

```
IDLE → DESIGNING → TRAINING → [gate] → BACKTESTING → [gate] → ASSESSING → COMPLETE
                      │                      │
                      └──── gate fail ───────┴──────▶ ASSESSING (partial)
```

The difference is that N researches progress through this flow concurrently, each at its own pace.

---

## API Contracts

### POST /api/v1/agent/trigger

**Request:** Unchanged from current implementation.

**Response changes:**

- Current success/failure responses remain valid
- New rejection reason: `"at_capacity"` when concurrency limit reached
- Include active count and limit in capacity rejection for user feedback

### GET /api/v1/agent/status

**Current:** Returns single active research or last completed.

**New:** Returns list of all active researches with:
- Operation ID and phase for each
- Strategy name (if design complete)
- Duration/timing info
- Worker pool utilization (active/total by type)
- Budget status
- Concurrency status (active/limit)

Study existing response patterns in `agent_service.py` — the new response should be a superset, not a replacement, for backward compatibility where possible.

### DELETE /api/v1/agent/cancel/{operation_id}

**Unchanged.** Already accepts operation_id. Verify CLI correctly passes the ID when user specifies which research to cancel.

---

## Error Handling

### Research-Level Errors

Each research handles errors independently:

| Error Type | Behavior |
|------------|----------|
| Design fails | That research → FAILED, others continue |
| Training fails | That research → FAILED, others continue |
| Gate rejection | That research → ASSESSING (partial), others continue |
| Assessment fails | That research → FAILED, others continue |

**No cascading failures.** One research failing doesn't affect others.

### Coordinator-Level Errors

| Error Type | Behavior |
|------------|----------|
| Database unavailable | Coordinator logs error, retries next cycle |
| Worker registry unavailable | Use cached count or default limit |
| Unhandled exception in phase handler | Log, mark that research FAILED, continue others |

**Key principle:** Catch exceptions per-research, fail that research, but don't let it stop the coordinator from processing other researches. The existing error handling patterns in `research_worker.py` should be adapted for multi-research iteration.

### Coordinator Crash Recovery

When backend restarts:
1. Coordinator loop starts fresh
2. Queries for all RUNNING/PENDING AGENT_RESEARCH operations
3. Resumes advancing each from their current phase
4. Child operations (training/backtest) continue on workers independently

---

## Integration Points

### Worker Registry

- Query `get_worker_registry()` for worker counts
- Used for concurrency limit calculation
- Existing integration, no new coupling

### Operations Service

- Query for all active AGENT_RESEARCH operations (new query pattern)
- Mark operations complete/failed (existing)
- No schema changes

### Budget Tracker

- Check budget before accepting new trigger (existing)
- Allow in-progress to complete even if over budget (new policy, code change)

### CLI

- `ktrdr agent status` — show all researches (presentation change)
- `ktrdr agent cancel <op_id>` — already supports operation_id
- `ktrdr agent trigger` — unchanged interface

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_POLL_INTERVAL` | `2` | Seconds between coordinator cycles (reduced from 5) |
| `AGENT_MAX_CONCURRENT_RESEARCHES` | `0` | Manual limit override (0 = calculate from workers) |
| `AGENT_CONCURRENCY_BUFFER` | `1` | Extra slots above worker count |

---

## Verification Strategy

### Unit Tests

1. **Concurrency limit calculation** — Given N training + M backtest workers, limit is N+M+1
2. **Multiple operations retrieved** — `_get_active_research_operations()` returns all active
3. **Phase handlers unchanged** — Existing phase tests still pass
4. **Error isolation** — One research failing doesn't affect others

### Integration Tests

1. **Two researches progress** — Trigger two, both advance through phases
2. **Capacity limit enforced** — Trigger at limit returns `at_capacity`
3. **Budget enforcement** — Trigger when exhausted returns `budget_exhausted`
4. **Individual cancel** — Cancel one, other continues

### E2E Tests

1. **Parallel training** — Two researches train simultaneously (verify worker logs)
2. **Full lifecycle** — Three researches complete end-to-end
3. **Coordinator restart** — Kill backend mid-research, restart, researches resume

---

## Migration / Rollout

### Backward Compatibility

- Single-research behavior unchanged (just no longer rejected when another is active)
- Existing CLI commands work (status shows more info)
- API responses are supersets of current (new fields added, none removed)

### Rollout Steps

1. Deploy with `AGENT_MAX_CONCURRENT_RESEARCHES=1` (effectively single-research)
2. Test in staging, verify no regressions
3. Increase limit to worker count, monitor
4. Remove limit override, let it calculate from workers

### Rollback

Set `AGENT_MAX_CONCURRENT_RESEARCHES=1` to restore single-research behavior.

---

*Created: 2026-01-19*
*Status: Draft — awaiting review*
