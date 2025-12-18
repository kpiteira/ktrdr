# M7 Task 7.4: Prometheus Metrics Handoff

## Summary

Task 7.4 adds Prometheus metrics for agent research cycle visibility.

## Completed

### Task 7.4: Add Prometheus Metrics

Added `ktrdr/agents/metrics.py` with 6 metrics:

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `agent_cycles_total` | Counter | outcome | Cycle counts (completed/failed/cancelled) |
| `agent_cycle_duration_seconds` | Histogram | - | Full cycle duration |
| `agent_phase_duration_seconds` | Histogram | phase | Per-phase duration |
| `agent_gate_results_total` | Counter | gate, result | Gate pass/fail counts |
| `agent_tokens_total` | Counter | phase | Token usage (design/assessment) |
| `agent_budget_spend_total` | Counter | - | Budget tracking |

## Implementation

### Files Created

- `ktrdr/agents/metrics.py` - Metric definitions and helper functions
- `tests/unit/agent_tests/test_agent_metrics.py` - 20 unit tests

### Files Modified

- `ktrdr/agents/workers/research_worker.py` - Instrumentation added at:
  - Cycle start/completion/failure/cancellation (line 218-283)
  - Phase transitions with timing (phase_start_time in metadata)
  - Gate evaluations (lines 458, 584)
  - Token recording from design/assessment workers

## Key Patterns

### Phase Timing

Phase start times are stored in operation metadata:

```python
parent_op.metadata.parameters["phase_start_time"] = time.time()
```

Duration is calculated when phase completes:

```python
phase_start = parent_op.metadata.parameters.get("phase_start_time")
if phase_start:
    record_phase_duration("designing", time.time() - phase_start)
```

### Token Recording

Tokens are extracted from child operation result_summary:

```python
input_tokens = result.get("input_tokens", 0) or 0
output_tokens = result.get("output_tokens", 0) or 0
if input_tokens or output_tokens:
    record_tokens("design", input_tokens + output_tokens)
```

### Mock Compatibility

Added guards for AsyncMock compatibility in tests:

```python
result = (
    child_op.result_summary
    if isinstance(child_op.result_summary, dict)
    else {}
)
```

## Gotcha: AsyncMock and result_summary

The cancellation tests use `AsyncMock()` for operations. When accessing unset attributes like `result_summary`, AsyncMock returns another AsyncMock (which is truthy). This caused `result.get()` to return coroutines instead of values.

**Fix:** Use `isinstance(result_summary, dict)` guard instead of `or {}`.

## Next Steps

Remaining M7 tasks:
- Task 7.5: Add OTEL Tracing
- Task 7.6: Create Grafana Dashboard
