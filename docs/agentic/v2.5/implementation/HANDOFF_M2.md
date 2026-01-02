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

## For Task 2.3 (Research Worker)

When training gate rejects:

1. **Don't raise GateError** - instead set instance variables
2. **Skip backtest** - transition directly to ASSESSING
3. **Call assessment with:**

   ```python
   await self.assessment_worker.run(
       parent_operation_id,
       results={"training": training_result, "backtest": None},
       gate_rejection_reason=f"accuracy_too_low ({acc}% < {threshold}%)",
   )
   ```
