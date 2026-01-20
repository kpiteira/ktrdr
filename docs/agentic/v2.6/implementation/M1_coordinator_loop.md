---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 1: Multi-Research Coordinator Loop

**Branch:** `feature/v2.6-m1-coordinator-loop`
**Goal:** User can trigger multiple research cycles, and all progress concurrently.

---

## Task 1.1: Add `_get_all_active_research_ops()` Method

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Persistence, Cross-Component

**Description:**
Add a method that returns all active AGENT_RESEARCH operations (not just one). This replaces `_get_active_research_op()` for multi-research queries.

**Implementation Notes:**
- Query for RUNNING, RESUMING, and PENDING statuses (same as current method)
- Return a list instead of single operation
- Keep `_get_active_research_op()` for backward compatibility (can delegate to new method)

**Code sketch:**
```python
async def _get_all_active_research_ops(self) -> list[Operation]:
    """Get all active AGENT_RESEARCH operations."""
    result = []
    for status in [OperationStatus.RUNNING, OperationStatus.RESUMING, OperationStatus.PENDING]:
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=status,
        )
        result.extend(ops)
    return result
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Returns empty list when no active researches
- [ ] Returns single operation when one active
- [ ] Returns multiple operations when several active
- [ ] Includes RUNNING, RESUMING, and PENDING statuses

*Integration Tests:*
- [ ] Wiring: Method accessible on AgentService instance

*Smoke Test:*
```bash
# After creating test operations:
uv run python -c "
from ktrdr.api.services.agent_service import get_agent_service
import asyncio
svc = get_agent_service()
ops = asyncio.run(svc._get_all_active_research_ops())
print(f'Active ops: {len(ops)}')
"
```

**Acceptance Criteria:**
- [ ] Method returns list of all active research operations
- [ ] Existing `_get_active_research_op()` still works
- [ ] Unit tests pass

---

## Task 1.2: Add `_get_concurrency_limit()` Method

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration, Cross-Component

**Description:**
Add a method that calculates the maximum concurrent researches from worker pool size. Checks for manual override via environment variable first.

**Implementation Notes:**
- Check `AGENT_MAX_CONCURRENT_RESEARCHES` env var first (non-zero = use it)
- Otherwise: `training_workers + backtest_workers + buffer`
- Buffer from `AGENT_CONCURRENCY_BUFFER` (default 1)
- Use `get_worker_registry().list_workers(worker_type=X)` to count workers

**Code sketch:**
```python
def _get_concurrency_limit(self) -> int:
    """Calculate max concurrent researches from worker pool."""
    import os
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.api.models.workers import WorkerType

    # Check manual override
    override = os.getenv("AGENT_MAX_CONCURRENT_RESEARCHES", "0")
    if override != "0":
        try:
            return int(override)
        except ValueError:
            pass

    # Calculate from workers
    registry = get_worker_registry()
    training = len(registry.list_workers(worker_type=WorkerType.TRAINING))
    backtest = len(registry.list_workers(worker_type=WorkerType.BACKTESTING))
    buffer = int(os.getenv("AGENT_CONCURRENCY_BUFFER", "1"))

    # Minimum of 1 to allow at least one research
    return max(1, training + backtest + buffer)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Returns override value when AGENT_MAX_CONCURRENT_RESEARCHES set
- [ ] Calculates from workers when no override
- [ ] Applies buffer correctly
- [ ] Returns minimum 1 when no workers registered

*Integration Tests:*
- [ ] Wiring: Can access worker registry from agent service

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.api.services.agent_service import get_agent_service
svc = get_agent_service()
print(f'Concurrency limit: {svc._get_concurrency_limit()}')
"
```

**Acceptance Criteria:**
- [ ] Env var override works
- [ ] Worker-based calculation works
- [ ] Unit tests pass

---

## Task 1.3: Modify `trigger()` for Capacity Check

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** State Machine, API Endpoint

**Description:**
Replace the single-research rejection with a capacity check. Multiple researches are allowed up to the concurrency limit.

**Implementation Notes:**
- Remove the "active_cycle_exists" rejection block (lines 206-214)
- Add capacity check: `if len(active_ops) >= limit`
- Return new "at_capacity" rejection with active_count and limit
- Keep budget check (it comes first, unchanged)

**Code sketch:**
```python
# In trigger(), replace:
#   active = await self._get_active_research_op()
#   if active:
#       return {"triggered": False, "reason": "active_cycle_exists", ...}

# With:
active_ops = await self._get_all_active_research_ops()
limit = self._get_concurrency_limit()
if len(active_ops) >= limit:
    return {
        "triggered": False,
        "reason": "at_capacity",
        "active_count": len(active_ops),
        "limit": limit,
        "message": f"At capacity ({len(active_ops)}/{limit} researches active)",
    }
```

**Testing Requirements:**

*Unit Tests:*
- [ ] First trigger succeeds (count 0, limit 5)
- [ ] Second trigger succeeds (count 1, limit 5)
- [ ] Trigger at capacity fails with "at_capacity" reason
- [ ] Response includes active_count and limit

*Integration Tests:*
- [ ] Contract: Response shape matches interface contract in VALIDATION.md

*Smoke Test:*
```bash
# Trigger multiple times via CLI
uv run ktrdr agent trigger --brief "Test 1"
uv run ktrdr agent trigger --brief "Test 2"
# Both should succeed (assuming limit > 2)
```

**Acceptance Criteria:**
- [ ] Multiple triggers succeed up to limit
- [ ] At-capacity rejection has correct response shape
- [ ] Budget check still happens first
- [ ] Unit tests pass

---

## Task 1.4: Refactor `run()` to Multi-Research Loop

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 2-3 hrs

**Task Categories:** State Machine, Background/Async

**Description:**
Refactor the coordinator's `run()` method to iterate over all active researches instead of running one to completion. This is the core architectural change.

**Implementation Notes:**
- Remove `operation_id` parameter from `run()`
- Add `_get_active_research_operations()` method to query OperationsService
- Change while loop: query all active ops, iterate and advance each, sleep, repeat
- Extract current phase logic into `_advance_research(op)` method
- Exit loop when `active_ops` is empty
- Keep all existing phase handler methods unchanged

**Code sketch:**
```python
async def run(self) -> None:
    """Coordinator loop for all active researches."""
    logger.info("Coordinator started")

    while True:
        active_ops = await self._get_active_research_operations()

        if not active_ops:
            logger.info("No active researches, coordinator stopping")
            break

        for op in active_ops:
            await self._advance_research(op)

        await self._cancellable_sleep(self.POLL_INTERVAL)

async def _get_active_research_operations(self) -> list:
    """Query all active AGENT_RESEARCH operations."""
    from ktrdr.api.models.operations import OperationStatus, OperationType

    result = []
    for status in [OperationStatus.RUNNING, OperationStatus.PENDING]:
        ops, _, _ = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=status,
        )
        result.extend(ops)
    return result

async def _advance_research(self, op) -> None:
    """Advance a single research one step."""
    operation_id = op.operation_id
    phase = op.metadata.parameters.get("phase", "idle")
    child_op_id = self._get_child_op_id(op, phase)
    child_op = None
    if child_op_id:
        child_op = await self.ops.get_operation(child_op_id)

    # Existing phase logic moved here
    if phase == "idle":
        await self._start_design(operation_id)
    elif phase == "designing":
        await self._handle_designing_phase(operation_id, child_op)
    elif phase == "training":
        await self._handle_training_phase(operation_id, child_op)
    elif phase == "backtesting":
        await self._handle_backtesting_phase(operation_id, child_op)
    elif phase == "assessing":
        await self._handle_assessing_phase(operation_id, child_op)
```

**Key changes from current code:**
1. `run()` no longer takes operation_id
2. Loop queries ALL active ops, not one
3. Phase handling extracted to `_advance_research()`
4. Loop exits when no active ops (coordinator stops)
5. Metrics recording moves into phase completion (or stays at research completion)

**Testing Requirements:**

*Unit Tests:*
- [ ] `_get_active_research_operations()` returns correct operations
- [ ] `_advance_research()` calls correct phase handler based on phase
- [ ] Loop exits when no active operations
- [ ] Multiple operations are all advanced in one cycle

*Integration Tests:*
- [ ] Lifecycle: Coordinator starts, processes ops, stops when empty
- [ ] State: Each research advances through phases correctly

*Smoke Test:*
```bash
# With USE_STUB_WORKERS=true:
USE_STUB_WORKERS=true uv run ktrdr agent trigger --brief "Test"
# Watch logs for coordinator loop messages
docker compose logs backend --tail 50 | grep -i coordinator
```

**Acceptance Criteria:**
- [ ] Coordinator iterates through all active researches
- [ ] Each research advances independently
- [ ] Coordinator stops when no researches active
- [ ] Existing phase handler behavior unchanged
- [ ] Unit tests pass

---

## Task 1.5: Coordinator Lifecycle Management

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** Background/Async, State Machine

**Description:**
Track the coordinator task lifecycle. Start coordinator on first trigger if not running. The coordinator stops itself when no researches remain.

**Implementation Notes:**
- Add `_coordinator_task: asyncio.Task | None = None` to `__init__`
- In `trigger()`, after creating operation, check if coordinator running
- If not running (`_coordinator_task is None or _coordinator_task.done()`), start it
- Remove per-operation task creation (current `_run_worker` pattern)
- Add `_start_coordinator()` helper method

**Code sketch:**
```python
class AgentService:
    def __init__(self, ...):
        # ... existing
        self._coordinator_task: asyncio.Task | None = None

    async def trigger(self, ...):
        # ... capacity/budget checks, create operation ...

        # Start coordinator if not running
        if self._coordinator_task is None or self._coordinator_task.done():
            self._start_coordinator()

        return {"triggered": True, "operation_id": op.operation_id, ...}

    def _start_coordinator(self) -> None:
        """Start the coordinator loop task."""
        worker = self._get_worker()
        self._coordinator_task = asyncio.create_task(
            self._run_coordinator(worker)
        )
        logger.info("Coordinator task started")

    async def _run_coordinator(self, worker: AgentResearchWorker) -> None:
        """Run coordinator and handle completion."""
        try:
            await worker.run()  # No operation_id - it discovers all
            logger.info("Coordinator completed (no active researches)")
        except Exception as e:
            logger.error(f"Coordinator error: {e}")
            raise
```

**Testing Requirements:**

*Unit Tests:*
- [ ] First trigger starts coordinator
- [ ] Second trigger doesn't start another coordinator
- [ ] Coordinator task is tracked in `_coordinator_task`

*Integration Tests:*
- [ ] Lifecycle: Coordinator starts on trigger, runs until researches complete

*Smoke Test:*
```bash
# Check coordinator task exists after trigger
uv run python -c "
from ktrdr.api.services.agent_service import get_agent_service
import asyncio
svc = get_agent_service()
result = asyncio.run(svc.trigger(brief='test'))
print(f'Triggered: {result}')
print(f'Coordinator running: {svc._coordinator_task is not None}')
"
```

**Acceptance Criteria:**
- [ ] Coordinator starts on first trigger
- [ ] Only one coordinator runs at a time
- [ ] Coordinator stops when no researches remain
- [ ] Unit tests pass

---

## Task 1.6: Add Startup Hook

**File:** `ktrdr/api/services/agent_service.py`, `ktrdr/api/main.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Background/Async, Wiring/DI

**Description:**
Add `resume_if_needed()` method and call it from FastAPI lifespan. If active researches exist in DB on startup, start the coordinator.

**Implementation Notes:**
- Add `resume_if_needed()` method to AgentService
- Check for active operations via `_get_all_active_research_ops()`
- If any exist and coordinator not running, start it
- Call from FastAPI lifespan startup

**Code sketch:**
```python
# In agent_service.py:
async def resume_if_needed(self) -> None:
    """Start coordinator if active researches exist. Called on startup."""
    active_ops = await self._get_all_active_research_ops()
    if active_ops and (self._coordinator_task is None or self._coordinator_task.done()):
        logger.info(f"Resuming coordinator for {len(active_ops)} active researches")
        self._start_coordinator()

# In main.py lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...

    # Resume agent coordinator if needed
    from ktrdr.api.services.agent_service import get_agent_service
    agent_service = get_agent_service()
    await agent_service.resume_if_needed()

    yield

    # ... existing shutdown ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `resume_if_needed()` starts coordinator when active ops exist
- [ ] `resume_if_needed()` does nothing when no active ops
- [ ] `resume_if_needed()` does nothing when coordinator already running

*Integration Tests:*
- [ ] Wiring: AgentService accessible from lifespan context

*Smoke Test:*
```bash
# Create an operation in DB, restart backend, check coordinator starts
docker compose restart backend
docker compose logs backend --tail 20 | grep -i "resuming coordinator"
```

**Acceptance Criteria:**
- [ ] Coordinator resumes on backend startup if researches active
- [ ] No duplicate coordinators created
- [ ] Unit tests pass

---

## Task 1.7: Update Operation Completion Handling

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** State Machine, Persistence

**Description:**
Move operation completion handling inside the coordinator loop. When a research's assessment completes, mark it complete immediately (don't return from run()).

**Implementation Notes:**
- Currently `_handle_assessing_phase` returns result, caller marks complete
- Now: call `complete_operation()` directly in phase handler
- Same for checkpoint save on failure (in error handling)
- Metrics recording per-research, not at coordinator exit

**Code sketch:**
```python
async def _handle_assessing_phase(self, operation_id: str, child_op) -> None:
    """Handle assessing phase. Marks operation complete when done."""
    # ... existing checks for None, PENDING, RUNNING ...

    if child_op.status == OperationStatus.COMPLETED:
        result = child_op.result_summary if isinstance(child_op.result_summary, dict) else {}
        parent_op = await self.ops.get_operation(operation_id)

        # ... existing metric recording ...

        # Mark complete HERE instead of returning
        await self.ops.complete_operation(operation_id, {
            "success": True,
            "strategy_name": parent_op.metadata.parameters.get("strategy_name", "unknown"),
            "verdict": result.get("verdict", "unknown"),
        })

        # Record cycle metrics
        cycle_duration = time.time() - parent_op.created_at.timestamp()
        record_cycle_duration(cycle_duration)
        record_cycle_outcome("completed")

        logger.info(f"Research completed: {operation_id}")
        # Don't return - let loop continue to next research
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Assessment completion marks operation complete
- [ ] Metrics recorded on completion
- [ ] Other researches not affected by one completing

*Integration Tests:*
- [ ] DB verification: Operation status is COMPLETED after assessment

*Smoke Test:*
```bash
# Trigger research with stubs, wait for completion
USE_STUB_WORKERS=true uv run ktrdr agent trigger --brief "test"
sleep 30
uv run ktrdr ops list --type AGENT_RESEARCH | head -5
# Should show COMPLETED
```

**Acceptance Criteria:**
- [ ] Operations marked complete inside loop
- [ ] Metrics recorded per-research
- [ ] Coordinator continues after one research completes
- [ ] Unit tests pass

---

## Task 1.8: Unit and Integration Tests

**File:** `tests/unit/agents/test_research_worker_multi.py`, `tests/integration/test_multi_research.py`
**Type:** CODING
**Estimated time:** 1.5 hrs

**Task Categories:** N/A (testing)

**Description:**
Write comprehensive tests for the multi-research coordinator functionality.

**Unit Tests (new file):**
```python
# tests/unit/agents/test_research_worker_multi.py

class TestMultiResearchCoordinator:
    """Tests for multi-research coordinator loop."""

    async def test_advance_research_calls_correct_phase_handler(self):
        """Each phase routes to correct handler."""

    async def test_loop_processes_all_active_operations(self):
        """All active ops are advanced in one cycle."""

    async def test_loop_exits_when_no_active_ops(self):
        """Coordinator stops when queue empty."""

    async def test_one_research_completing_doesnt_stop_loop(self):
        """Loop continues after one research completes."""


class TestCapacityCheck:
    """Tests for concurrency limit."""

    async def test_trigger_succeeds_under_capacity(self):
        """Triggers allowed when under limit."""

    async def test_trigger_rejected_at_capacity(self):
        """Returns at_capacity when limit reached."""

    async def test_capacity_from_workers(self):
        """Limit calculated from worker pool."""

    async def test_capacity_override_env_var(self):
        """AGENT_MAX_CONCURRENT_RESEARCHES overrides."""


class TestCoordinatorLifecycle:
    """Tests for coordinator start/stop."""

    async def test_first_trigger_starts_coordinator(self):
        """Coordinator starts on first trigger."""

    async def test_second_trigger_reuses_coordinator(self):
        """No duplicate coordinators."""

    async def test_resume_if_needed_starts_coordinator(self):
        """Startup hook starts coordinator when ops exist."""
```

**Integration Tests:**
```python
# tests/integration/test_multi_research.py

async def test_two_researches_progress_concurrently():
    """
    E2E: Trigger two researches, both complete.
    Uses stub workers for speed.
    """
    # Setup
    os.environ["USE_STUB_WORKERS"] = "true"

    # Trigger two
    result1 = await agent_service.trigger(brief="Research 1")
    result2 = await agent_service.trigger(brief="Research 2")

    assert result1["triggered"] == True
    assert result2["triggered"] == True

    # Wait for completion (stub workers are fast)
    await asyncio.sleep(15)

    # Verify both completed
    op1 = await ops_service.get_operation(result1["operation_id"])
    op2 = await ops_service.get_operation(result2["operation_id"])

    assert op1.status == OperationStatus.COMPLETED
    assert op2.status == OperationStatus.COMPLETED
```

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Integration test passes with stub workers
- [ ] No regressions in existing tests

---

## E2E Validation

### Test to Run

| Test | Purpose | Source |
|------|---------|--------|
| Multi-research completion | Verify two researches both complete | New |

### Test Specification

**Test: agent/multi-research-completion**

**Purpose:** Verify multiple researches can be triggered and both complete successfully.

**Duration:** ~60 seconds (with stub workers)

**Prerequisites:**
- Backend running with `USE_STUB_WORKERS=true`
- No active researches

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Clear any active researches | No active ops | `ktrdr agent status` shows idle |
| 2 | Trigger research A | Returns operation_id | CLI output |
| 3 | Trigger research B | Returns operation_id | CLI output |
| 4 | Check status | Shows 2 active researches | `ktrdr agent status` |
| 5 | Wait 60 seconds | Researches progress | - |
| 6 | Check final status | Both completed | `ktrdr ops list` |

**Success Criteria:**
- [ ] Both triggers succeed (not rejected)
- [ ] Status shows both researches with phases
- [ ] Both researches reach COMPLETED status
- [ ] No errors in backend logs

**Sanity Checks:**

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Time to completion | < 120s | Coordinator not advancing |
| Final status | Both COMPLETED | Phase handler issue |
| Backend errors | 0 | Exception in coordinator |

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes (above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in existing agent tests
- [ ] Branch merged to main
