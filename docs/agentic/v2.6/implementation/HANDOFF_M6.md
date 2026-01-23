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
