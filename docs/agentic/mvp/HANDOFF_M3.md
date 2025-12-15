# M3 Handoff: Training Integration

## Task 3.1 Completed

Created `TrainingWorkerAdapter` that bridges agent orchestrator to existing TrainingService.

### Files Created

| File | Description |
|------|-------------|
| `ktrdr/agents/workers/training_adapter.py` | TrainingWorkerAdapter class |
| `tests/unit/agent_tests/test_training_adapter.py` | 8 unit tests |

### Implementation

- Loads strategy YAML to extract `symbols`, `timeframes`, `strategy_name`
- Calls `TrainingService.start_training()` with extracted config
- Polls `OperationsService.get_operation()` until COMPLETED/FAILED/CANCELLED
- Returns metrics dict: `{success, training_op_id, accuracy, final_loss, initial_loss, model_path}`
- Propagates cancellation to child training operation

---

## Gotchas for M3 Tasks 3.2-3.4

1. **Circular import avoidance** - TrainingService import causes circular dependency. Solution: Use `Protocol` for type hints and lazy import in property getter.

2. **WorkerRegistry required** - TrainingService requires WorkerRegistry in constructor. Get via `get_worker_registry()` from `ktrdr.api.endpoints.workers`.

3. **result_summary can be None** - OperationInfo.result_summary is Optional. Guard with `result_summary = op.result_summary or {}`.

4. **Protocol type: ignore** - mypy needs `# type: ignore[assignment]` and `# type: ignore[return-value]` when working with Protocol-based injection.

5. **Poll interval** - Default is 10 seconds. For tests, set `adapter.POLL_INTERVAL = 0.01` to speed up.

---

## Next: Task 3.2 (Training Gate)

Wire `check_training_gate()` from `ktrdr/agents/gates.py` into `research_worker.py` after training completes.
