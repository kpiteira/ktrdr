# v2.6 Multi-Research Coordination: Design Validation

**Date:** 2026-01-20
**Documents Validated:**
- Design: DESIGN.md
- Architecture: ARCHITECTURE.md
- Scope: Full implementation

## Validation Summary

**Scenarios Validated:** 6/6 traced
**Critical Gaps Found:** 6 (all resolved)
**Interface Contracts:** Defined for AgentService, AgentResearchWorker, CLI

---

## Key Decisions Made

These decisions came from validation and should inform implementation:

### D1: Single Coordinator Loop Pattern
Research operations are state objects, not tasks. One coordinator loop iterates through all active researches, advancing each one step per cycle. No N-task-per-research pattern.

### D2: Capacity Check Replaces Single-Research Check
`trigger()` checks `len(active_ops) >= limit` instead of rejecting when any research exists. Limit derived from worker pool: `training_workers + backtest_workers + buffer`.

### D3: Phase Transition Requires Worker Availability
Before transitioning from design→training or training→backtest, coordinator checks if a worker is available. If not, research stays in current phase and retries next cycle. No intermediate "waiting" phases needed.

### D4: Error Isolation via Per-Research Exception Handling
`try/except` moves inside the per-research iteration. One research failing marks it FAILED and continues processing others. No cascading failures.

### D5: Coordinator Lifecycle
- Starts on first trigger (if not already running)
- Stops when no active researches remain
- Restarts on backend startup if active researches exist in DB

### D6: Orphaned Task Recovery
Design/assessment tasks run in-process. On backend restart, if child operation is RUNNING but no asyncio task exists, restart the phase. Acceptable to pay for duplicate Claude call.

### D7: Budget as Guard Rail
Budget check happens only at trigger time. Once a research starts, it completes regardless of budget. Assessment overage is acceptable. `can_spend()` returns False when `remaining <= 0`.

### D8: Cancel Accepts Operation ID
`cancel(operation_id)` cancels specific research. Cancelling last research causes coordinator to exit loop and sleep.

---

## Scenarios Validated

### Happy Paths

1. **Two researches progress concurrently** — User triggers A, then B. Both complete successfully with overlapping phases.

2. **Natural queuing within capacity** — 2 training workers, 3 researches. A and B train in parallel. C waits after design until A frees worker.

### Error Paths

3. **One research fails, others continue** — B's design fails. A and C continue unaffected.

4. **Budget exhausted mid-operation** — In-progress researches complete. New triggers rejected.

### Edge Cases

5. **Cancel individual research** — Cancel B by operation_id. A and C continue.

### Infrastructure

6. **Coordinator restart mid-operation** — Backend restarts. Coordinator discovers active researches from DB, resumes each from current phase. Training/backtest on workers survive. Design/assessment in-process tasks restart.

---

## Interface Contracts

### AgentService

```python
# Trigger - capacity check instead of single-research check
async def trigger(
    self,
    model: str | None = None,
    brief: str | None = None,
    bypass_gates: bool = False,
) -> dict[str, Any]:
    """
    Returns on success:
        {"triggered": True, "operation_id": "op_...", "model": "...", "message": "..."}

    Returns on capacity limit:
        {"triggered": False, "reason": "at_capacity", "active_count": 5, "limit": 5, "message": "..."}

    Returns on budget exhausted:
        {"triggered": False, "reason": "budget_exhausted", "message": "..."}
    """

# Cancel - now accepts operation_id
async def cancel(self, operation_id: str) -> dict[str, Any]:
    """
    Returns on success:
        {"success": True, "operation_id": "op_...", "child_cancelled": "op_train_...", "message": "..."}

    Returns if not found:
        {"success": False, "reason": "not_found", "message": "..."}
    """

# Status - returns all active researches
async def get_status(self) -> dict[str, Any]:
    """
    Returns:
        {
            "status": "active" | "idle",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "training",
                    "strategy_name": "rsi_variant_7",
                    "duration_seconds": 135,
                    "child_operation_id": "op_train_xyz",
                },
            ],
            "workers": {
                "training": {"busy": 2, "total": 3},
                "backtest": {"busy": 1, "total": 2},
            },
            "budget": {"remaining": 3.42, "daily_limit": 10.00},
            "capacity": {"active": 3, "limit": 6},
        }
    """

# New - startup hook
async def resume_if_needed(self) -> None:
    """Start coordinator if active researches exist. Called on backend startup."""

# New - concurrency limit calculation
def _get_concurrency_limit(self) -> int:
    """
    Returns AGENT_MAX_CONCURRENT_RESEARCHES if set and non-zero.
    Otherwise: training_workers + backtest_workers + AGENT_CONCURRENCY_BUFFER.
    """
```

### AgentResearchWorker

```python
class AgentResearchWorker:
    def __init__(self, ...):
        # Existing params unchanged
        self._child_tasks: dict[str, asyncio.Task] = {}  # NEW: per-research tracking

    async def run(self) -> None:
        """
        Coordinator loop. No operation_id param - discovers all active ops.

        Loop structure:
            while True:
                active_ops = get_active_research_operations()
                if not active_ops:
                    break
                for op in active_ops:
                    try:
                        advance_research(op)
                    except CancelledError:
                        handle_cancelled(op)
                    except Exception as e:
                        handle_failed(op, e)
                sleep(POLL_INTERVAL)
        """

    async def _advance_research(self, op) -> None:
        """Advance single research one step based on phase."""

    # Phase handlers add worker availability check:
    async def _handle_designing_phase(self, operation_id: str, child_op) -> None:
        """
        On child COMPLETED:
            - Check worker availability via get_worker_registry()
            - If no worker: return (stay in phase, retry next cycle)
            - If worker available: start training
        """
```

### CLI Output

```
$ ktrdr agent status
Active researches: 3

  op_abc123  training     strategy: rsi_variant_7      (2m 15s)
  op_def456  designing    strategy: -                  (0m 30s)
  op_ghi789  backtesting  strategy: mtf_momentum_1     (1m 45s)

Workers: training 2/3, backtest 1/2
Budget: $3.42 remaining today
Capacity: 3/6 researches


$ ktrdr agent cancel op_abc123
Research cancelled: op_abc123


$ ktrdr agent trigger --brief "Another experiment"
Cannot trigger: at capacity (5 active researches, limit is 5)
```

---

## Implementation Milestones

### Milestone 1: Multi-Research Coordinator Loop

**User Story:** User can trigger a second research while one is running, and both progress.

**Scope:**
- `AgentResearchWorker.run()`: Refactor to loop over all active ops
- `AgentService.trigger()`: Replace single-research check with capacity check
- `AgentService`: Track coordinator task lifecycle (start/stop)
- New method: `_get_all_active_research_ops()`
- New method: `_get_concurrency_limit()`

**E2E Test:**
```
Given: No active researches
When: User triggers research A, then triggers research B
Then: Both A and B appear in active list
  And: Both advance through phases
  And: Both eventually complete
```

---

### Milestone 2: Error Isolation

**User Story:** If one research fails, the others continue unaffected.

**Scope:**
- `AgentResearchWorker.run()`: Move try/except inside per-research iteration
- Per-research failure handling with checkpoint save
- Per-research metrics recording

**E2E Test:**
```
Given: Two researches active (A in training, B in designing)
When: B's design fails
Then: B is marked FAILED
  And: A continues to completion
```

---

### Milestone 3: Worker Queuing

**User Story:** When more researches than workers, they naturally queue and proceed when workers free up.

**Scope:**
- Phase handlers: Add worker availability check before transition
- Access `get_worker_registry()` for availability queries

**E2E Test:**
```
Given: 2 training workers, 3 researches triggered
When: A and B enter training (using both workers), C completes design
Then: C waits in designing phase
When: A completes training (frees worker)
Then: C starts training
```

---

### Milestone 4: Individual Cancel

**User Story:** User can cancel a specific research by operation_id while others continue.

**Scope:**
- `AgentService.cancel(operation_id)`: Accept parameter
- `AgentResearchWorker._child_tasks`: Track per-operation for clean cancellation
- CLI: Pass operation_id to cancel endpoint

**E2E Test:**
```
Given: Three researches active (A, B, C)
When: User runs `ktrdr agent cancel op_B`
Then: B is cancelled
  And: A and C continue unaffected
```

---

### Milestone 5: Status and Observability

**User Story:** User can see all active researches with phases, worker utilization, and budget.

**Scope:**
- `AgentService.get_status()`: Return multi-research response
- CLI: Format and display multi-research status

**E2E Test:**
```
Given: Two researches active (A in training, B in backtesting)
When: User runs `ktrdr agent status`
Then: Output shows both researches with phases
  And: Shows worker utilization
  And: Shows budget remaining
```

---

### Milestone 6: Coordinator Restart Recovery

**User Story:** If backend restarts while researches are active, they resume automatically.

**Scope:**
- `AgentService.resume_if_needed()`: Startup hook
- FastAPI lifespan: Call resume hook
- `AgentResearchWorker`: Detect/restart orphaned design/assessment tasks

**E2E Test:**
```
Given: Two researches active (A in training, B in designing)
When: Backend process restarts
Then: Coordinator starts automatically
  And: A continues (training on worker survived)
  And: B's design restarts
  And: Both eventually complete
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_POLL_INTERVAL` | `2` | Seconds between coordinator cycles |
| `AGENT_MAX_CONCURRENT_RESEARCHES` | `0` | Manual limit override (0 = calculate from workers) |
| `AGENT_CONCURRENCY_BUFFER` | `1` | Extra slots above worker count |

---

*Validated: 2026-01-20*
*Status: Ready for implementation planning*
