# Agent Progress Monitoring

**Status**: Validated
**Depends on**: M1 (Orchestrator), M6 (Cancellation)

---

## Problem Statement

The `ktrdr agent trigger` command starts a research cycle and returns immediately, telling users to run `ktrdr agent status` separately. Users want the same experience they get with training and backtesting: a single command that shows real-time progress with a progress bar.

Additionally, agent operations don't report progress in the standard format. Other operations (training, backtesting) call `update_progress()` to populate `progress.percentage` and `progress.current_step`, but the agent research worker only stores phase in metadata. This inconsistency means generic tooling can't display agent progress.

---

## Goals

1. **Consistent API** — Agent operations report progress in the same format as all other operations
2. **CLI parity** — `agent trigger --monitor` works like `model train` or `backtest run`
3. **Rich visibility** — Show both cycle phase AND child operation progress (e.g., training epochs)
4. **Reuse patterns** — Reuse signal handling and HTTP patterns from existing CLI infrastructure

---

## Non-Goals

- Changing the default behavior of `agent trigger` (fire-and-forget stays default)
- Adding WebSocket/streaming (polling is sufficient for MVP)
- Persisting progress history beyond operation lifetime

---

## Design

### Part 1: Backend — Standard Progress Reporting

**Location:** `ktrdr/agents/workers/research_worker.py`

**Change:** Call `ops.update_progress()` when transitioning between phases.

**Phase-to-progress mapping:**

| Phase | Percentage | Rationale |
|-------|------------|-----------|
| idle | 0% | Not started |
| designing | 5% | Design is quick (~30s) |
| training | 20% | Training is longest phase, starts here |
| backtesting | 65% | After training completes |
| assessing | 90% | Assessment is quick |
| completed | 100% | Done |

**Progress context includes:**
- `phase` — Current phase name
- `child_op_id` — Active child operation ID (for nested progress)

**Example API response after this change:**

```json
{
  "success": true,
  "data": {
    "operation_id": "op_abc123",
    "status": "running",
    "progress": {
      "percentage": 20.0,
      "current_step": "Training model..."
    },
    "metadata": {
      "parameters": {
        "phase": "training",
        "training_op_id": "op_training_xyz"
      }
    }
  }
}
```

**Note:** Parent percentage is static per phase (20% throughout training). The CLI polls the child operation separately to get epoch-level progress and renders it as a nested progress bar.

---

### Part 2: CLI — Monitor Flag

**Location:** `ktrdr/cli/agent_commands.py`

**New flags:** `--monitor` (primary), `--follow` and `-f` (aliases)

```bash
ktrdr agent trigger              # Fire and forget (current behavior)
ktrdr agent trigger --monitor    # Wait with progress bar
ktrdr agent trigger --follow     # Same as --monitor
ktrdr agent trigger -f           # Short form
ktrdr agent trigger -m haiku -f  # Model + monitor
```

**Implementation:** Custom polling loop that fetches both parent and child operations in parallel.

---

### Part 3: CLI — Nested Progress Display

When the agent is in training or backtesting phase, the CLI also polls the child operation to show granular progress.

**Display concept:**

```
🔬 Research Cycle [20%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 02:15
   Training model...
   └─ Epoch 45/100 [45%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 01:32
```

**How it works:**
1. CLI polls parent operation: `GET /operations/{parent_id}`
2. Reads `metadata.parameters.training_op_id` (or `backtest_op_id`)
3. Also polls child operation: `GET /operations/{child_id}`
4. Renders both progress bars

**When child progress is shown:**
- `phase == "training"` → show training operation progress
- `phase == "backtesting"` → show backtest operation progress
- Other phases → show only parent progress

---

## User Experience

### Scenario 1: Basic monitoring

```bash
$ ktrdr agent trigger --monitor

🔬 Research Cycle [5%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 00:12
   Phase: Designing strategy...
```

### Scenario 2: During training

```bash
$ ktrdr agent trigger --monitor

🔬 Research Cycle [20%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 03:45
   Training model...
   └─ Epoch 67/100 [67%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 02:15
```

### Scenario 3: Cancellation with Ctrl+C

```bash
$ ktrdr agent trigger --monitor

🔬 Research Cycle [20%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 03:45
   Training model...
   └─ Epoch 67/100 [67%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 02:15
^C
⚠️ Cancelling research cycle...
✓ Cancelled. Training stopped at epoch 67/100.
```

### Scenario 5: Connection lost (retry)

```bash
$ ktrdr agent trigger --monitor

🔬 Research Cycle [20%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 02:15
   ⚠ Connection lost, retrying...
```

### Scenario 4: Completion

```bash
$ ktrdr agent trigger --monitor

🔬 Research Cycle [100%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 08:32
   Phase: Complete

✓ Research cycle complete!
   Strategy: momentum_breakout_20251218
   Verdict: promising
   Sharpe: 1.24 | Win Rate: 58% | Max DD: 12%
```

---

## Architecture

### Backend Components

```
AgentResearchWorker (ktrdr/agents/workers/research_worker.py)
    │
    ├── On phase transition:
    │   └── calls ops.update_progress(operation_id, progress)
    │
    └── OperationsService stores progress in standard format
```

### CLI Components

```
agent_commands.py
    │
    ├── trigger_agent() with --monitor flag
    │   └── If --monitor: custom polling loop
    │
    └── _monitor_agent_cycle() (new function)
        ├── Polls parent operation: GET /operations/{parent_id}
        ├── Polls child operation: GET /operations/{child_id} (when in training/backtest)
        ├── Renders nested Rich progress display
        ├── Handles Ctrl+C → DELETE /operations/{parent_id}
        └── Shows completion summary
```

### Data Flow

```
1. CLI calls POST /agent/trigger
2. Backend starts research cycle, returns operation_id
3. CLI polls GET /operations/{parent_id} every 300ms
4. Backend returns progress.percentage, progress.current_step, metadata
5. CLI reads child_op_id from metadata, polls GET /operations/{child_id} in parallel
6. CLI renders nested progress display (parent + child)
7. On Ctrl+C: CLI calls DELETE /operations/{parent_id}
8. On completion: CLI shows results summary
```

---

## Implementation

This is **one milestone** with four tasks (~170 lines across 2 files).

### Task 1: Backend Progress Updates (~20 lines)

**File:** `ktrdr/agents/workers/research_worker.py`

- Call `update_progress()` on phase transitions
- Include phase name in `current_step`
- Ensure `training_op_id` / `backtest_op_id` in metadata

### Task 2: CLI Monitor Flag + Polling (~80 lines)

**File:** `ktrdr/cli/agent_commands.py`

- Add `--monitor`/`--follow`/`-f` flags to `trigger_agent`
- Create `_monitor_agent_cycle()` with single-operation polling
- Signal handler for Ctrl+C → DELETE /operations/{id}
- Basic Rich progress display

### Task 3: Nested Child Progress (~40 lines)

**File:** `ktrdr/cli/agent_commands.py`

- Extract `training_op_id` / `backtest_op_id` from parent metadata
- Poll child operation in parallel
- Render nested progress bars

### Task 4: Error Handling + Polish (~30 lines)

**File:** `ktrdr/cli/agent_commands.py`

- Connection error retry with backoff
- 404 handling (operation lost after restart)
- Cancellation summary with child state

---

## Testing

### Unit Tests
- `AgentResearchWorker` calls `update_progress()` on phase transitions
- Progress percentages are correct for each phase
- CLI correctly parses operation responses

### Integration Tests
- `ktrdr agent trigger --monitor` shows progress and completes
- Ctrl+C cancels cleanly with summary
- Nested progress displays correctly during training phase

---

## Key Decisions (from validation)

1. **Custom polling loop instead of AsyncOperationExecutor**
   - Agent monitoring needs to poll two operations (parent + child) in parallel
   - The generic executor only supports single-operation polling
   - Custom loop is ~50 lines and simpler than extending the executor

2. **Use DELETE /operations/{id} for cancellation (not /agent/cancel)**
   - Consistent with how all other operations handle cancellation
   - If `/agent/cancel` ever diverges from operation cancellation, that's a bug to fix in the agent

3. **CLI polls child operations directly (same pattern as train/backtest)**
   - Worker exposes child_op_id in metadata
   - CLI reads child progress and composes the nested display
   - Follows existing patterns in AsyncOperationExecutor

4. **Parent percentage is static per phase (not interpolated from child)**
   - Parent stays at 20% throughout training phase
   - Child progress bar shows epoch-level detail
   - Simpler implementation, clearer UX

5. **Connection errors: retry with backoff**
   - Show "Connection lost, retrying..." message
   - Exponential backoff up to 5 seconds
   - Handles transient network issues gracefully

6. **Operation 404 after restart: clean exit**
   - Show "Operation not found — may have been lost due to restart"
   - Acceptable for MVP (operations are in-memory)

---

## Success Criteria

1. `GET /operations/{agent_op_id}` returns standard `progress` object
2. `ktrdr agent trigger --monitor` shows real-time progress
3. Nested child progress displays during training/backtesting phases
4. Ctrl+C cancels cleanly via `DELETE /operations/{id}`
5. Completion shows cycle summary with key metrics

---

## Validation Summary

**Date:** 2025-12-20

**Scenarios Validated:**

- Full cycle with monitoring (happy path)
- Ctrl+C during training (cancellation)
- Child operation progress passthrough (nested display)
- Backend restart during monitoring (error handling)
- Connection lost and retry (resilience)

**Critical Gaps Resolved:**

1. Who composes current_step? → CLI polls child directly (same as train/backtest)
2. Parent progress during child phases? → Static per phase (20% during training)

**E2E Acceptance Test:**

```gherkin
Given: No active cycle
When: ktrdr agent trigger --monitor
Then: Shows nested progress bars, handles Ctrl+C cleanly, displays completion summary
```

**Ready for implementation.**
