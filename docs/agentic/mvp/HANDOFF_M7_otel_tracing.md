# M7 Task 7.5: OTEL Tracing Handoff

## Summary

Task 7.5 adds OpenTelemetry spans to the research worker for full observability in Jaeger.

## Implementation

### Files Modified

- `ktrdr/agents/workers/research_worker.py` - Added tracer and span instrumentation

### Files Created

- `tests/unit/agent_tests/test_research_worker_telemetry.py` - 13 unit tests for tracing

## Spans Created

| Span Name | Location | Purpose |
|-----------|----------|---------|
| `agent.research_cycle` | Wraps entire `run()` method | Parent span for full cycle |
| `agent.phase.design` | `_handle_designing_phase` on completion | Design phase timing |
| `agent.phase.training` | `_handle_training_phase` on completion | Training phase + gate result |
| `agent.phase.backtest` | `_handle_backtesting_phase` on completion | Backtest phase + gate result |
| `agent.phase.assessment` | `_handle_assessing_phase` on completion | Assessment phase timing |

## Span Attributes

### Parent Span (`agent.research_cycle`)
- `operation.id` - Parent operation ID
- `operation.type` - Always "agent_research"
- `outcome` - "completed", "failed", or "cancelled"
- `error` - Error message on failure

### Design Phase Span
- `operation.id`, `phase` - Standard attributes
- `strategy_name` - Name of designed strategy
- `tokens.input`, `tokens.output`, `tokens.total` - Token usage

### Training/Backtest Phase Spans
- `operation.id`, `phase` - Standard attributes
- `gate.name`, `gate.passed`, `gate.reason` - Gate evaluation
- Additional metrics (accuracy, sharpe_ratio, etc.)

### Assessment Phase Span
- `operation.id`, `phase` - Standard attributes
- `verdict` - Assessment verdict
- `strategy_name` - Strategy being assessed
- `tokens.*` - Token usage

## Test Isolation Note

The telemetry tests require careful fixture management to avoid conflicts with other tests that might manipulate the OTEL trace provider. The fixture directly patches the module's `tracer` variable and restores it after each test.

## Gotcha: Context Detach Warnings

When tests cancel async operations abruptly, you may see warnings like:
```
Failed to detach context
ValueError: <Token ...> was created in a different Context
```

These are harmless - they occur because the span context is being cleaned up across different async contexts during test cancellation. They don't affect production behavior.

## Next Steps

- Task 7.6: Create Grafana Dashboard
