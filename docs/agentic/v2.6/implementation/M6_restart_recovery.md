---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 6: Coordinator Restart Recovery

**Branch:** `feature/v2.6-m6-restart-recovery`
**Depends on:** M1 (coordinator loop), M2 (error isolation)
**Goal:** If backend restarts while researches are active, they resume automatically.

---

## Task 6.1: Detect Orphaned In-Process Tasks

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** Background/Async, State Machine

**Description:**
After backend restart, design/assessment child operations may show RUNNING but no asyncio task exists. Detect this orphaned state and restart the phase.

**Implementation Notes:**
- In `_advance_research()`, for designing/assessing phases:
- If child op is RUNNING but operation_id not in `_child_tasks` → orphaned
- Restart the phase by calling `_start_design()` or `_start_assessment()` again
- Log that we're restarting an orphaned task
- This is only relevant for in-process phases (design, assessment)
- Training/backtest on workers survive restarts naturally

**Code sketch:**
```python
async def _advance_research(self, op) -> None:
    """Advance a single research, detecting orphaned tasks."""
    operation_id = op.operation_id
    phase = op.metadata.parameters.get("phase", "idle")
    child_op_id = self._get_child_op_id(op, phase)
    child_op = None
    if child_op_id:
        child_op = await self.ops.get_operation(child_op_id)

    # Check for orphaned in-process tasks
    if phase in ["designing", "assessing"]:
        if child_op and child_op.status == OperationStatus.RUNNING:
            if operation_id not in self._child_tasks:
                # Orphaned! Task died with backend restart
                logger.warning(
                    f"Detected orphaned {phase} task for {operation_id}, restarting"
                )
                # Mark old child as failed
                await self.ops.fail_operation(
                    child_op_id, "Orphaned by backend restart"
                )
                # Restart the phase
                if phase == "designing":
                    await self._start_design(operation_id)
                else:
                    await self._start_assessment(operation_id)
                return

    # Normal phase handling
    if phase == "idle":
        await self._start_design(operation_id)
    elif phase == "designing":
        await self._handle_designing_phase(operation_id, child_op)
    # ... etc
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Orphaned design task detected (RUNNING, not in _child_tasks)
- [ ] Orphaned assessment task detected
- [ ] Training/backtest not affected (they're on workers)
- [ ] Orphan detection triggers restart
- [ ] Old child operation marked failed

*Integration Tests:*
- [ ] Simulate restart: clear _child_tasks, verify orphan detected

*Smoke Test:*
```bash
# Difficult to test manually without actually restarting
# But can verify logs after restart show orphan detection
docker compose restart backend
docker compose logs backend --tail 50 | grep -i orphan
```

**Acceptance Criteria:**
- [ ] Orphaned design/assessment tasks detected
- [ ] Phases restart correctly
- [ ] Old child marked failed
- [ ] Unit tests pass

---

## Task 6.2: Verify Training/Backtest Resume Naturally

**File:** N/A (verification task)
**Type:** RESEARCH
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Verify that training/backtest operations on workers survive backend restarts and resume correctly when coordinator polls again.

**Implementation Notes:**
- This should already work because:
  - Workers are separate containers, keep running
  - Operations are in PostgreSQL, survive restart
  - Coordinator queries operations, finds RUNNING training/backtest
  - Polls until complete, then transitions
- Just need to verify this works

**Verification Steps:**
1. Start a research with real (or stubbed) workers
2. Wait until it's in training phase
3. Restart backend: `docker compose restart backend`
4. Check that training continues on worker
5. Check that research eventually completes

**Acceptance Criteria:**
- [ ] Training on worker continues after backend restart
- [ ] Coordinator picks up and resumes polling
- [ ] Research completes successfully

---

## Task 6.3: Unit and Integration Tests for Restart Recovery

**File:** `tests/unit/agents/test_restart_recovery.py`, `tests/integration/test_restart_recovery.py`
**Type:** CODING
**Estimated time:** 1 hr

**Task Categories:** N/A (testing)

**Description:**
Write tests for restart recovery behavior.

**Unit Tests:**
```python
class TestRestartRecovery:
    """Tests for coordinator restart recovery."""

    async def test_orphaned_design_detected(self):
        """Orphaned design task (RUNNING, no task) is detected."""

    async def test_orphaned_assessment_detected(self):
        """Orphaned assessment task is detected."""

    async def test_orphan_restarts_phase(self):
        """Detected orphan triggers phase restart."""

    async def test_training_not_considered_orphan(self):
        """Training on worker is not orphaned (it's on separate process)."""

    async def test_old_child_marked_failed(self):
        """Orphaned child operation marked as failed."""


class TestStartupResume:
    """Tests for startup hook resumption."""

    async def test_resume_starts_coordinator(self):
        """resume_if_needed starts coordinator when ops exist."""

    async def test_resume_noop_when_no_ops(self):
        """resume_if_needed does nothing when no active ops."""

    async def test_resume_detects_orphans(self):
        """Resumed coordinator detects orphaned tasks."""
```

**Integration Test:**
```python
async def test_backend_restart_recovery():
    """
    E2E: Researches resume after backend restart.

    Note: This test simulates restart by clearing coordinator state,
    not actually restarting the backend.
    """
    # Trigger two researches
    # Wait until one is in training, one in designing
    # Clear coordinator state (simulate restart)
    # Call resume_if_needed
    # Verify:
    #   - Training research continues
    #   - Designing research's orphan detected and restarted
    #   - Both eventually complete
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
| Restart recovery | Resume after backend restart | New |

### Test Specification

**Test: agent/restart-recovery**

**Purpose:** Verify researches resume after backend restart.

**Duration:** ~120 seconds (includes restart time)

**Prerequisites:**
- Backend and workers running
- USE_STUB_WORKERS=true (for speed)

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Trigger research A | Success | CLI |
| 2 | Trigger research B | Success | CLI |
| 3 | Wait until A in training, B in designing | Both in progress | Status |
| 4 | Restart backend | Backend restarts | Docker logs |
| 5 | Check coordinator resumed | Log message | `grep "Resuming coordinator"` |
| 6 | Check orphan detected for B | Log message | `grep -i orphan` |
| 7 | Wait for completion | Both complete | Status |
| 8 | Verify final status | Both COMPLETED | `ktrdr ops list` |

**Success Criteria:**
- [ ] Coordinator resumes on startup
- [ ] Orphaned design task detected and restarted
- [ ] Training on worker continues
- [ ] Both researches complete
- [ ] No duplicate operations created

**Sanity Checks:**

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Time to resume | < 10s | Startup hook not called |
| Orphan detection | Within 1 poll cycle | Detection logic issue |
| Final completion | < 120s total | Phase restart failed |

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`
- [ ] M1-M5 E2E tests still pass
- [ ] Branch merged to main
