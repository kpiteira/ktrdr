# Handoff: M2 Gate Rejection → Memory

## Task 2.1: Status Fields Added

Added two new fields to `ExperimentRecord` in `ktrdr/agents/memory.py`:

```python
status: str = "completed"  # "completed" | "gate_rejected_training" | "gate_rejected_backtest"
gate_rejection_reason: str | None = None  # e.g., "accuracy_too_low (5% < 10%)"
```

Fields use defaults for backward compatibility.

---

## Task 2.2: AssessmentWorker Updated

Updated `AgentAssessmentWorker` to handle gate rejections:

### API Changes

```python
# run() now accepts gate_rejection_reason
await worker.run(
    parent_operation_id,
    results={"training": {...}, "backtest": None},  # backtest can be None
    gate_rejection_reason="accuracy_too_low (5% < 10%)",
)

# _save_to_memory() now accepts status and gate_rejection_reason
await self._save_to_memory(
    ...,
    status="gate_rejected_training",
    gate_rejection_reason="accuracy_too_low (5% < 10%)",
)
```

### Key Implementation Details

1. **None handling:** Use `results.get("backtest") or {}` instead of `results.get("backtest", {})` because `.get()` returns `None` (not default) when key exists with `None` value.

2. **Status logic in run():**

   ```python
   if gate_rejection_reason:
       if results.get("backtest") is None:
           status = "gate_rejected_training"
       else:
           status = "gate_rejected_backtest"
   else:
       status = "completed"
   ```

---

## Tasks 2.3 & 2.4: Research Worker State Machine Updated

Gate rejections now route to ASSESSING instead of raising GateError:

### Training Gate Rejection

```python
# In _handle_training_phase():
if not passed:
    # Skip backtest, go directly to assessment with partial results
    await self._start_assessment(
        operation_id,
        gate_rejection_reason=f"Training gate: {reason}",
    )
    return
```

### Backtest Gate Rejection

```python
# In _handle_backtesting_phase():
if not passed:
    await self._start_assessment(
        operation_id,
        gate_rejection_reason=f"Backtest gate: {reason}",
    )
    return
```

### `_start_assessment` Signature

```python
async def _start_assessment(
    self,
    operation_id: str,
    gate_rejection_reason: str | None = None,
) -> None:
```

Builds results dict with `backtest: None` for training gate rejection.

---

## Task 2.5: E2E Test Created

E2E test file: `tests/e2e/agent/test_gate_rejection_e2e.py`

### Running the E2E Test

```bash
# Start backend with stub workers and forced gate rejection
USE_STUB_WORKERS=true TRAINING_GATE_MIN_ACCURACY=0.99 docker compose up -d

# Run the E2E test
pytest tests/e2e/agent/test_gate_rejection_e2e.py -v -m "e2e" --no-cov
```

### Test Coverage

- `test_training_gate_rejection_records_experiment`: Full flow validation
- `test_experiment_has_required_fields`: Verifies ExperimentRecord structure
- `test_gate_rejection_reason_includes_threshold`: Verifies reason format

### Configuration

| Environment Variable | Purpose | Required Value |
| -------------------- | ------- | -------------- |
| `USE_STUB_WORKERS` | Use stubs for Design/Assessment | `true` |
| `TRAINING_GATE_MIN_ACCURACY` | Force gate rejection | `0.99` |
| `STUB_WORKER_FAST` | Speed up stub delays | `true` (optional) |

---

## M2 Milestone Complete

All tasks verified:

- ✅ Task 2.1: ExperimentRecord has status fields
- ✅ Task 2.2: AssessmentWorker accepts partial results
- ✅ Task 2.3: State machine routes gate rejection → ASSESSING
- ✅ Task 2.4: _start_assessment method updated
- ✅ Task 2.5: E2E test created
