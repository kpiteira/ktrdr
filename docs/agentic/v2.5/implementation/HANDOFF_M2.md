# Handoff: M2 Gate Rejection → Memory

## Task 2.1: Status Fields Added

### What Was Done

Added two new fields to `ExperimentRecord` in `ktrdr/agents/memory.py`:

```python
status: str = "completed"  # "completed" | "gate_rejected_training" | "gate_rejected_backtest"
gate_rejection_reason: str | None = None  # e.g., "accuracy_too_low (5% < 10%)"
```

### Key Design Decision

Fields use defaults for backward compatibility. Existing experiments without these fields will work - consumers should use `.get("status", "completed")` when reading from YAML.

The `load_experiments()` function returns raw dicts from YAML (not ExperimentRecord instances), so backward compatibility is handled at the consumer level, not in the load function itself.

### For Remaining Tasks

**Task 2.2 (AssessmentWorker):** When calling `ExperimentRecord()`, you can now pass:
- `status="gate_rejected_training"` for training gate rejections
- `status="gate_rejected_backtest"` for backtest gate rejections
- `gate_rejection_reason="<description>"` explaining the rejection

**Task 2.3 (Research Worker):** When gate fails, instead of raising `GateError`, set instance variables and transition to ASSESSING phase with partial results.

### Test Patterns

See `tests/unit/agent_tests/test_memory.py` for examples:
- `TestExperimentRecord.test_experiment_record_gate_rejected_training`
- `TestSaveExperiment.test_save_experiment_with_status_field`
