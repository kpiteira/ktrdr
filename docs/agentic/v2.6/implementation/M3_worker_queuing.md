---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 3: Worker Queuing

**Branch:** `feature/v2.6-m3-worker-queuing`
**Depends on:** M1 (coordinator loop)
**Goal:** When more researches than workers, they naturally queue and proceed when workers free up.

---

## Task 3.1: Add Worker Availability Check to Design→Training Transition

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** Cross-Component, State Machine

**Description:**
Before transitioning from design to training, check if a training worker is available. If not, stay in designing phase and retry next poll cycle.

**Implementation Notes:**
- In `_handle_designing_phase()`, after child completes successfully
- Check `get_worker_registry().get_available_workers(WorkerType.TRAINING)`
- If empty list, return early (don't call `_start_training`)
- Log that we're waiting for a worker
- Research stays in "designing" phase until worker available

**Code sketch:**
```python
async def _handle_designing_phase(self, operation_id: str, child_op: Any) -> None:
    """Handle designing phase with worker availability check."""
    if child_op is None:
        await self._start_design(operation_id)
        return

    if child_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING):
        return

    if child_op.status == OperationStatus.COMPLETED:
        # NEW: Check worker availability before transitioning
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerType

        registry = get_worker_registry()
        available = registry.get_available_workers(WorkerType.TRAINING)

        if not available:
            logger.debug(
                f"Research {operation_id}: design complete, waiting for training worker"
            )
            return  # Stay in designing, retry next cycle

        # ... existing logic: store results, start training ...
        result = child_op.result_summary if isinstance(child_op.result_summary, dict) else {}
        parent_op = await self.ops.get_operation(operation_id)
        # ... store strategy_name, strategy_path ...

        await self._start_training(operation_id)

    elif child_op.status == OperationStatus.FAILED:
        raise WorkerError(f"Design failed: {child_op.error_message}")

    elif child_op.status == OperationStatus.CANCELLED:
        raise asyncio.CancelledError("Design was cancelled")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Transition happens when worker available
- [ ] Transition blocked when no workers available
- [ ] Blocked research stays in "designing" phase
- [ ] Retry succeeds when worker becomes available

*Integration Tests:*
- [ ] With 0 training workers, research waits after design
- [ ] With 1 training worker, research proceeds

*Smoke Test:*
```bash
# Scale down training workers, trigger research, verify it waits
docker compose stop training-worker
uv run ktrdr agent trigger --brief "test"
# Wait for design to complete
uv run ktrdr agent status
# Should show: "designing" phase even though design is done
docker compose start training-worker
# Now it should proceed
```

**Acceptance Criteria:**
- [ ] Research waits for training worker
- [ ] Proceeds immediately when worker available
- [ ] No error or failure state when waiting
- [ ] Unit tests pass

---

## Task 3.2: Add Worker Availability Check to Training→Backtest Transition

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Cross-Component, State Machine

**Description:**
Same pattern as Task 3.1, but for training→backtest transition. Check for backtest worker availability before starting backtest.

**Implementation Notes:**
- In `_handle_training_phase()`, after training completes and gate passes
- Check `get_worker_registry().get_available_workers(WorkerType.BACKTESTING)`
- If empty, return early (don't call `_start_backtest`)
- Research stays in "training" phase until worker available

**Code sketch:**
```python
async def _handle_training_phase(self, operation_id: str, child_op: Any) -> None:
    """Handle training phase with worker availability check."""
    # ... existing status checks ...

    if child_op.status == OperationStatus.COMPLETED:
        # ... gate check ...

        if not passed:
            # Gate rejection - go to assessment (no worker needed)
            await self._start_assessment(operation_id, gate_rejection_reason=...)
            return

        # NEW: Check backtest worker availability
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.models.workers import WorkerType

        registry = get_worker_registry()
        available = registry.get_available_workers(WorkerType.BACKTESTING)

        if not available:
            logger.debug(
                f"Research {operation_id}: training complete, waiting for backtest worker"
            )
            return  # Stay in training, retry next cycle

        await self._start_backtest(operation_id)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Transition happens when backtest worker available
- [ ] Transition blocked when no workers available
- [ ] Gate rejection bypasses worker check (goes to assessment)

*Integration Tests:*
- [ ] With 0 backtest workers, research waits after training

**Acceptance Criteria:**
- [ ] Research waits for backtest worker
- [ ] Gate rejection path unchanged (goes to assessment)
- [ ] Unit tests pass

---

## Task 3.3: Unit and Integration Tests for Worker Queuing

**File:** `tests/unit/agents/test_worker_queuing.py`, `tests/integration/test_worker_queuing.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** N/A (testing)

**Description:**
Write tests for worker queuing behavior.

**Unit Tests:**
```python
class TestWorkerQueuing:
    """Tests for natural worker queuing."""

    async def test_design_waits_for_training_worker(self):
        """Design complete but no training worker → stays in designing."""

    async def test_design_proceeds_when_worker_available(self):
        """Design complete and worker available → starts training."""

    async def test_training_waits_for_backtest_worker(self):
        """Training complete but no backtest worker → stays in training."""

    async def test_gate_rejection_skips_worker_check(self):
        """Gate rejection goes to assessment without checking workers."""

    async def test_multiple_researches_queue_for_workers(self):
        """With 1 worker and 3 researches, they take turns."""
```

**Integration Test:**
```python
async def test_natural_queuing_with_limited_workers():
    """
    E2E: 2 training workers, 3 researches.
    A and B train in parallel, C waits, then proceeds when A finishes.
    """
    # Setup: Ensure only 2 training workers registered
    # Trigger 3 researches
    # Verify: A, B in training; C in designing (waiting)
    # Wait for A to complete training
    # Verify: C starts training
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
| Worker queuing | Natural queue when workers busy | New |

### Test Specification

**Test: agent/worker-queuing**

**Purpose:** Verify researches queue naturally when workers are busy.

**Duration:** ~90 seconds

**Prerequisites:**
- Exactly 2 training workers registered
- USE_STUB_WORKERS=true for speed

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Verify 2 training workers | 2 workers shown | `curl /api/v1/workers` |
| 2 | Trigger research A | Success | CLI |
| 3 | Trigger research B | Success | CLI |
| 4 | Trigger research C | Success | CLI |
| 5 | Wait for all to finish design | All in training or waiting | Status check |
| 6 | Check status | A, B training; C designing | `ktrdr agent status` |
| 7 | Wait for A to finish training | A in backtesting | Status check |
| 8 | Check status | C now training | `ktrdr agent status` |

**Success Criteria:**
- [ ] At most 2 researches in training simultaneously
- [ ] C waits until worker frees up
- [ ] All 3 eventually complete
- [ ] No errors or failures

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`
- [ ] M1 E2E tests still pass
- [ ] Branch merged to main
