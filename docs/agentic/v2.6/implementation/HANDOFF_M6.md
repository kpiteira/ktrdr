# Handoff: M6 Restart Recovery

## Task 6.1 Complete: Detect Orphaned In-Process Tasks

### Gotchas

- **Only design and assessment phases can be orphaned**: Training and backtest run on external workers that survive backend restarts. Don't check for orphans in those phases.

- **Orphan detection order matters**: The check must happen BEFORE the normal phase handling. If orphan is detected and handled, return early to avoid double processing.

- **Child task lookup by operation_id**: `_child_tasks` is keyed by the PARENT operation_id, not the child operation_id. Check `operation_id not in self._child_tasks`.

### Implementation Notes

New method added to `AgentResearchWorker`:
- `_check_and_handle_orphan(operation_id, phase, child_op)` - Returns True if orphan was detected and handled

The check logic:
1. Only for designing/assessing phases
2. Child operation must exist and be RUNNING
3. No task in `_child_tasks` for this operation_id
4. If orphaned: fail the child, restart the phase, return True

### Code Location

`ktrdr/agents/workers/research_worker.py`:
- `_advance_research()` lines ~1077-1085: Orphan check before phase handling
- `_check_and_handle_orphan()` lines ~1111-1154: The helper method

### Next Task Notes (Task 6.2)

Task 6.2 is a RESEARCH/verification task - verify that training/backtest operations on workers survive backend restarts. The test `test_training_not_affected_by_orphan_detection` already verifies training is not considered orphaned. Manual verification with real workers may be useful.

---

## Task 6.2 Complete: Verify Training/Backtest Resume Naturally

### Verification Findings

Training and backtest operations naturally survive backend restarts due to architecture:

1. **Workers are separate containers** - They continue running during backend restart
2. **Operations persist in PostgreSQL** - RUNNING status survives restart
3. **Orphan detection excludes worker phases** - Lines 1088-1093 in `research_worker.py` explicitly skip orphan checks for training/backtesting
4. **Coordinator simply polls** - `_handle_training_phase()` and `_handle_backtesting_phase()` just check child operation status

### Key Code Evidence

```python
# From _advance_research() - orphan detection only for in-process phases
if phase in ("designing", "assessing"):
    if await self._check_and_handle_orphan(operation_id, phase, child_op):
        return
# Training and backtesting phases fall through to their handlers
# which simply poll child_op.status
```

### Test Evidence

- `test_training_continues_after_simulated_restart` - Fresh coordinator doesn't disrupt training
- `test_training_not_affected_by_orphan_detection` - Training explicitly not orphaned
- `test_backtesting_not_affected_by_orphan_detection` - Backtest explicitly not orphaned

### Next Task Notes (Task 6.3)

Task 6.3 adds unit and integration tests for restart recovery. The test files already exist from Task 6.1 with good coverage (10 tests). Task 6.3 may need to add any missing tests from the milestone spec.

---

## Task 6.3 Complete: Unit and Integration Tests

### Test Coverage Summary

Added 4 new tests to `TestStartupResume` class testing `AgentService.resume_if_needed()`:
- `test_resume_starts_coordinator_when_active_ops_exist` - Verifies coordinator starts when active researches exist
- `test_resume_noop_when_no_active_ops` - Verifies no-op when operations dict is empty
- `test_resume_noop_when_only_completed_ops` - Verifies no-op when only completed ops exist
- `test_resume_detects_orphans_on_first_cycle` - Verifies orphan detection after resume

### Test File Locations

- **Unit tests**: `tests/unit/agents/test_restart_recovery.py` (11 tests)
- **Integration tests**: `tests/integration/test_restart_recovery.py` (3 tests)

### Gotchas

- **AgentService cleanup**: No `_stop_coordinator()` method exists. To clean up in tests, cancel the task directly: `service._coordinator_task.cancel()` and await it catching CancelledError.

---

## E2E Validation Complete

### Test Results

**Scenario:** Restart backend during training phase

| Criterion | Status | Notes |
|-----------|--------|-------|
| Training continues on worker | ✅ PASS | Worker completed training, model saved |
| Coordinator resumes | ⚠️ PARTIAL | Called but no active ops (reconciliation ran first) |
| Research completes | ❌ FAIL | Marked FAILED by startup reconciliation |

### Key Finding: Worker/Backend Reconnection Gap

Training DID complete on the worker, but backend marked it failed because:
1. Startup reconciliation marks backend-local ops (research parent) as FAILED
2. Orphan detector marks worker-based ops as FAILED after 60s if no worker claims
3. Workers don't re-report running operations when backend reconnects

**This is a system-level gap beyond M6 scope.** The M6 coordinator-level orphan detection works correctly (verified by unit/integration tests), but full system restart involves additional components.

### Recommendations

1. **Worker re-registration should report running operations** to backend on reconnect
2. **Or backend should query workers** for their running operations on startup
3. **Startup reconciliation timing** could be adjusted to run AFTER workers reconnect

### Unit/Integration Test Validity

The M6 tests remain valid because they test the coordinator-level behavior:
- Orphan detection in `_advance_research()` works correctly
- `resume_if_needed()` correctly starts coordinator when ops exist
- Training/backtest phases are correctly excluded from orphan detection

---

## Test Coverage

| Scenario | Unit Test | Integration Test |
|----------|-----------|------------------|
| Orphaned design detected | ✅ test_orphaned_design_detected_running_child_no_task | ✅ test_simulate_restart_orphan_detected |
| Orphaned assessment detected | ✅ test_orphaned_assessment_detected | |
| Training not orphaned | ✅ test_training_not_affected_by_orphan_detection | ✅ test_training_continues_after_simulated_restart |
| Backtest not orphaned | ✅ test_backtesting_not_affected_by_orphan_detection | |
| Active task not orphaned | ✅ test_design_with_task_not_considered_orphan | |
| Old child marked failed | ✅ test_orphan_child_marked_failed_with_clear_message | |
| Orphan logged | ✅ test_orphan_detection_logs_warning | |
| Multiple researches | | ✅ test_multiple_researches_orphan_detection |

---
