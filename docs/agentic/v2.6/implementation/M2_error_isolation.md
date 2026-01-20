---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 2: Error Isolation

**Branch:** `feature/v2.6-m2-error-isolation`
**Depends on:** M1 (coordinator loop)
**Goal:** If one research fails, others continue unaffected.

---

## Task 2.1: Move Exception Handling Inside Per-Research Loop

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** State Machine, Background/Async

**Description:**
Wrap each research's advancement in try/except so one failure doesn't stop others. Currently exceptions propagate to the top level and stop everything.

**Implementation Notes:**
- Move try/except from around the while loop to inside the for loop
- Catch `asyncio.CancelledError` → mark that research cancelled
- Catch `WorkerError`, `GateError` → mark that research failed
- Catch `Exception` → mark failed, log unexpected error
- Always continue to next research after handling

**Code sketch:**
```python
async def run(self) -> None:
    """Coordinator loop with error isolation."""
    logger.info("Coordinator started")

    while True:
        active_ops = await self._get_active_research_operations()

        if not active_ops:
            logger.info("No active researches, coordinator stopping")
            break

        for op in active_ops:
            try:
                await self._advance_research(op)
            except asyncio.CancelledError:
                await self._handle_research_cancelled(op)
            except (WorkerError, GateError) as e:
                await self._handle_research_failed(op, e)
            except Exception as e:
                logger.error(f"Unexpected error in research {op.operation_id}: {e}")
                await self._handle_research_failed(op, e)

        await self._cancellable_sleep(self.POLL_INTERVAL)

async def _handle_research_cancelled(self, op) -> None:
    """Handle cancellation for a single research."""
    operation_id = op.operation_id
    logger.info(f"Research cancelled: {operation_id}")

    # Save checkpoint
    await self._save_checkpoint(operation_id, "cancellation")

    # Mark cancelled
    await self.ops.cancel_operation(operation_id, "Cancelled")

    # Record metrics
    record_cycle_outcome("cancelled")

async def _handle_research_failed(self, op, error: Exception) -> None:
    """Handle failure for a single research."""
    operation_id = op.operation_id
    logger.error(f"Research failed: {operation_id}, error={error}")

    # Save checkpoint
    await self._save_checkpoint(operation_id, "failure")

    # Mark failed
    await self.ops.fail_operation(operation_id, str(error))

    # Record metrics
    record_cycle_outcome("failed")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] WorkerError in one research doesn't stop others
- [ ] GateError in one research doesn't stop others
- [ ] Unexpected exception in one research doesn't stop others
- [ ] Failed research is marked FAILED
- [ ] Checkpoint saved on failure

*Integration Tests:*
- [ ] DB verification: Failed research has FAILED status
- [ ] Other researches continue after one fails

*Smoke Test:*
```bash
# Inject failure in one research, verify others continue
# (Requires test hook or error injection mechanism)
```

**Acceptance Criteria:**
- [ ] Exceptions caught per-research
- [ ] Failed research marked appropriately
- [ ] Other researches continue
- [ ] Metrics recorded per-research
- [ ] Unit tests pass

---

## Task 2.2: Add Checkpoint Save Helper

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Persistence, Cross-Component

**Description:**
Add `_save_checkpoint()` method to the worker for saving checkpoints on failure/cancellation. This may already exist in AgentService — if so, make it accessible from worker.

**Implementation Notes:**
- Check if checkpoint logic exists in AgentService
- Either move to worker or call service method
- Use existing `build_agent_checkpoint_state()` helper
- Handle checkpoint service not being available (unit tests)

**Code sketch:**
```python
async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
    """Save checkpoint for research operation."""
    try:
        op = await self.ops.get_operation(operation_id)
        if op is None:
            return

        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state
        from ktrdr.checkpoint import CheckpointService

        checkpoint_state = build_agent_checkpoint_state(op)

        # Get checkpoint service (may not be available in tests)
        checkpoint_service = self._get_checkpoint_service()
        if checkpoint_service:
            await checkpoint_service.save_checkpoint(
                operation_id=operation_id,
                checkpoint_type=checkpoint_type,
                state=checkpoint_state.to_dict(),
                artifacts=None,
            )
            logger.info(f"Checkpoint saved: {operation_id} ({checkpoint_type})")
    except Exception as e:
        logger.warning(f"Failed to save checkpoint: {e}")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Checkpoint saved on failure
- [ ] Checkpoint saved on cancellation
- [ ] Missing checkpoint service doesn't crash

*Integration Tests:*
- [ ] DB verification: Checkpoint record exists after failure

**Acceptance Criteria:**
- [ ] Checkpoints saved on failure/cancellation
- [ ] Graceful handling when checkpoint service unavailable
- [ ] Unit tests pass

---

## Task 2.3: Unit and Integration Tests for Error Isolation

**File:** `tests/unit/agents/test_error_isolation.py`, `tests/integration/test_error_isolation.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** N/A (testing)

**Description:**
Write tests specifically for error isolation behavior.

**Unit Tests:**
```python
class TestErrorIsolation:
    """Tests for per-research error handling."""

    async def test_worker_error_fails_one_research(self):
        """WorkerError marks one research failed, others continue."""

    async def test_gate_error_fails_one_research(self):
        """GateError marks one research failed, others continue."""

    async def test_unexpected_error_fails_one_research(self):
        """Unexpected exception marks one research failed, others continue."""

    async def test_cancelled_error_cancels_one_research(self):
        """CancelledError cancels one research, others continue."""

    async def test_checkpoint_saved_on_failure(self):
        """Checkpoint saved when research fails."""

    async def test_metrics_recorded_per_research(self):
        """Each research records its own outcome metric."""
```

**Integration Test:**
```python
async def test_one_research_fails_others_continue():
    """
    E2E: One research fails, others complete.
    Uses error injection or stub that fails.
    """
    # Setup: Configure one research to fail
    # Trigger three researches
    # Verify: One failed, two completed
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
| Error isolation | One fails, others continue | New |

### Test Specification

**Test: agent/error-isolation**

**Purpose:** Verify one research failing doesn't affect others.

**Duration:** ~60 seconds

**Prerequisites:**
- Backend running
- Error injection mechanism (e.g., stub that fails for specific brief)

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Trigger research A (normal) | Success | CLI output |
| 2 | Trigger research B (will fail) | Success | CLI output |
| 3 | Trigger research C (normal) | Success | CLI output |
| 4 | Wait for B to fail | B marked FAILED | `ktrdr ops list` |
| 5 | Wait for A, C to complete | Both COMPLETED | `ktrdr ops list` |

**Success Criteria:**
- [ ] Research B is FAILED
- [ ] Research A is COMPLETED
- [ ] Research C is COMPLETED
- [ ] Checkpoint exists for B

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`
- [ ] M1 E2E tests still pass (no regression)
- [ ] Branch merged to main
