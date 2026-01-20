---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 5: Status and Observability

**Branch:** `feature/v2.6-m5-status-observability`
**Depends on:** M1 (coordinator loop)
**Goal:** User can see all active researches with phases, worker utilization, and budget.

---

## Task 5.1: Update `get_status()` for Multi-Research Response

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** API Endpoint, Cross-Component

**Description:**
Refactor `get_status()` to return information about all active researches, worker utilization, budget status, and capacity.

**Implementation Notes:**
- Get all active researches via `_get_all_active_research_ops()`
- For each, include: operation_id, phase, strategy_name, duration, child_operation_id
- Query worker registry for utilization (busy vs total by type)
- Query budget tracker for remaining/limit
- Include capacity info (active count vs limit)

**Code sketch:**
```python
@trace_service_method("agent.get_status")
async def get_status(self) -> dict[str, Any]:
    """Get status of all active researches."""
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.api.models.workers import WorkerType, WorkerStatus

    active_ops = await self._get_all_active_research_ops()

    if not active_ops:
        # Return idle status with last completed
        last = await self._get_last_research_op()
        return {
            "status": "idle",
            "active_researches": [],
            "last_cycle": self._format_last_cycle(last) if last else None,
            "workers": self._get_worker_status(),
            "budget": self._get_budget_status(),
            "capacity": {
                "active": 0,
                "limit": self._get_concurrency_limit(),
            },
        }

    # Build active research list
    active_researches = []
    for op in active_ops:
        phase = op.metadata.parameters.get("phase", "unknown")
        child_op_id = self._get_child_op_id_for_phase(op, phase)
        started_at = op.started_at or op.created_at

        active_researches.append({
            "operation_id": op.operation_id,
            "phase": phase,
            "strategy_name": op.metadata.parameters.get("strategy_name"),
            "duration_seconds": int((datetime.now(UTC) - started_at).total_seconds()),
            "child_operation_id": child_op_id,
        })

    return {
        "status": "active",
        "active_researches": active_researches,
        "workers": self._get_worker_status(),
        "budget": self._get_budget_status(),
        "capacity": {
            "active": len(active_ops),
            "limit": self._get_concurrency_limit(),
        },
    }

def _get_worker_status(self) -> dict[str, dict[str, int]]:
    """Get worker utilization by type."""
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.api.models.workers import WorkerType, WorkerStatus

    registry = get_worker_registry()
    result = {}

    for worker_type in [WorkerType.TRAINING, WorkerType.BACKTESTING]:
        all_workers = registry.list_workers(worker_type=worker_type)
        busy_workers = [w for w in all_workers if w.status == WorkerStatus.BUSY]
        result[worker_type.value] = {
            "busy": len(busy_workers),
            "total": len(all_workers),
        }

    return result

def _get_budget_status(self) -> dict[str, float]:
    """Get budget remaining and limit."""
    from ktrdr.agents.budget import get_budget_tracker

    budget = get_budget_tracker()
    return {
        "remaining": budget.get_remaining(),
        "daily_limit": budget.get_daily_limit(),
    }
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Returns empty active_researches when idle
- [ ] Returns all active researches with correct fields
- [ ] Worker status shows busy/total counts
- [ ] Budget status shows remaining/limit
- [ ] Capacity shows active/limit

*Integration Tests:*
- [ ] API contract: Response matches VALIDATION.md interface contract

*Smoke Test:*
```bash
# Trigger a few researches, check status
uv run ktrdr agent trigger --brief "test1"
uv run ktrdr agent trigger --brief "test2"
curl http://localhost:8000/api/v1/agent/status | jq
# Should show both researches, workers, budget, capacity
```

**Acceptance Criteria:**
- [ ] All active researches shown
- [ ] Worker utilization accurate
- [ ] Budget status accurate
- [ ] Capacity info included
- [ ] Unit tests pass

---

## Task 5.2: Update CLI Status Display

**File:** `ktrdr/cli/agent.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** API Endpoint

**Description:**
Update the CLI status command to display the new multi-research response format in a user-friendly way.

**Implementation Notes:**
- Parse the new response structure
- Display active researches in a table or list
- Show worker utilization in compact format
- Show budget and capacity

**Target output format (from VALIDATION.md):**
```
Active researches: 3

  op_abc123  training     strategy: rsi_variant_7      (2m 15s)
  op_def456  designing    strategy: -                  (0m 30s)
  op_ghi789  backtesting  strategy: mtf_momentum_1     (1m 45s)

Workers: training 2/3, backtest 1/2
Budget: $3.42 remaining today
Capacity: 3/6 researches
```

**Code sketch:**
```python
@agent_app.command("status")
def status():
    """Show status of all active researches."""
    response = httpx.get(f"{API_BASE}/agent/status")
    data = response.json()

    if data["status"] == "idle":
        console.print("Status: [dim]idle[/dim]")
        if data.get("last_cycle"):
            last = data["last_cycle"]
            console.print(f"Last cycle: {last['operation_id']} ({last['outcome']})")
    else:
        active = data["active_researches"]
        console.print(f"Active researches: {len(active)}\n")

        for r in active:
            strategy = r.get("strategy_name") or "-"
            duration = format_duration(r["duration_seconds"])
            console.print(
                f"  {r['operation_id']}  {r['phase']:<12} "
                f"strategy: {strategy:<20} ({duration})"
            )

        console.print()

    # Workers
    workers = data.get("workers", {})
    training = workers.get("training", {})
    backtest = workers.get("backtesting", {})
    console.print(
        f"Workers: training {training.get('busy', 0)}/{training.get('total', 0)}, "
        f"backtest {backtest.get('busy', 0)}/{backtest.get('total', 0)}"
    )

    # Budget
    budget = data.get("budget", {})
    remaining = budget.get("remaining", 0)
    console.print(f"Budget: ${remaining:.2f} remaining today")

    # Capacity
    capacity = data.get("capacity", {})
    console.print(f"Capacity: {capacity.get('active', 0)}/{capacity.get('limit', 0)} researches")


def format_duration(seconds: int) -> str:
    """Format seconds as Xm Ys."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs:02d}s"
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Displays idle status correctly
- [ ] Displays active researches in table format
- [ ] Shows worker utilization
- [ ] Shows budget remaining
- [ ] Shows capacity

*Smoke Test:*
```bash
uv run ktrdr agent status
# Verify output matches expected format
```

**Acceptance Criteria:**
- [ ] Output matches design spec
- [ ] All info displayed clearly
- [ ] Works with 0, 1, or many researches

---

## Task 5.3: Unit and Integration Tests for Status

**File:** `tests/unit/cli/test_agent_status.py`, `tests/integration/test_agent_status.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** N/A (testing)

**Description:**
Write tests for the new status response and CLI display.

**Unit Tests:**
```python
class TestAgentStatus:
    """Tests for multi-research status."""

    async def test_status_with_no_active(self):
        """Returns idle status when no researches."""

    async def test_status_with_one_active(self):
        """Returns one research in list."""

    async def test_status_with_multiple_active(self):
        """Returns all active researches."""

    async def test_worker_status_counts(self):
        """Worker busy/total counts are accurate."""

    async def test_budget_status(self):
        """Budget remaining and limit returned."""

    async def test_capacity_status(self):
        """Capacity active and limit returned."""
```

**Integration Test:**
```python
async def test_status_shows_all_active_researches():
    """
    E2E: Trigger two, status shows both.
    """
    # Trigger two researches
    # Call status
    # Verify both appear with correct phases
```

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Integration test passes
- [ ] No regressions

---

## E2E Validation

### Test to Run

| Test | Purpose | Source |
|------|---------|--------|
| Multi-research status | Status shows all researches | New |

### Test Specification

**Test: agent/multi-research-status**

**Purpose:** Verify status displays all active researches correctly.

**Duration:** ~30 seconds

**Prerequisites:**
- Backend running
- USE_STUB_WORKERS=true

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Trigger research A | Success | CLI |
| 2 | Trigger research B | Success | CLI |
| 3 | Run status | Shows both A and B | CLI output |
| 4 | Verify phases shown | Each has phase | Output check |
| 5 | Verify workers shown | Shows busy/total | Output check |
| 6 | Verify budget shown | Shows remaining | Output check |
| 7 | Verify capacity shown | Shows active/limit | Output check |

**Success Criteria:**
- [ ] Both researches appear in status
- [ ] Phases are correct
- [ ] Worker utilization shown
- [ ] Budget shown
- [ ] Capacity shown (2/N)

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`
- [ ] M1 E2E tests still pass
- [ ] Branch merged to main
