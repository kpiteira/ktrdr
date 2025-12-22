# M4 Handoff: Backtest Integration

## Architecture Pattern

Orchestrator directly calls BacktestingService and tracks the real backtest operation ID. No adapter, no nested polling. Same pattern as M3 training.

---

## Task 4.1 Completed

Added `_start_backtest()` and `_handle_backtesting_phase()` to orchestrator.

### Implementation

In `research_worker.py`:

- `_start_backtest()` method calls `BacktestingService.run_backtest()` directly
- Stores `backtest_op_id` in parent metadata
- Sets phase to "backtesting"
- Main loop polls the real backtest operation

Key code path:

```python
async def _start_backtest(self, operation_id: str) -> None:
    result = await self.backtest_service.run_backtest(
        symbol=symbol,
        timeframe=timeframe,
        strategy_config_path=strategy_path,
        model_path=model_path,
        start_date=start_date,
        end_date=end_date,
    )
    backtest_op_id = result["operation_id"]
    parent_op.metadata.parameters["phase"] = "backtesting"
    parent_op.metadata.parameters["backtest_op_id"] = backtest_op_id
```

---

## Task 4.2 Completed

No BacktestWorkerAdapter was ever fully merged - it was reverted in commit `2862237` before architecture refactor.

---

## Task 4.3 Completed

Stubs simplified to only Design and Assessment workers.

### Files Modified

| File | Change |
|------|--------|
| `ktrdr/agents/workers/stubs.py` | Only `StubDesignWorker` and `StubAssessmentWorker` remain |
| `ktrdr/agents/workers/__init__.py` | Updated exports |

---

## Task 4.4 Completed

AgentService updated to pass services instead of workers.

### Implementation

```python
class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        return AgentResearchWorker(
            operations_service=self.ops,
            design_worker=...,           # Worker (Claude call)
            assessment_worker=...,       # Worker (Claude call)
            training_service=None,       # Lazy-loaded
            backtest_service=None,       # Lazy-loaded
        )
```

---

## Task 4.5 (Integration Tests)

**Status**: Not yet implemented.

Integration tests for backtest flow need:

1. Full Docker stack with workers running
2. Pre-loaded market data for backtest
3. Trained model from training phase

---

## Backtest Gate (Already in M1)

Backtest gate was implemented in M1 Task 1.11. Located in `research_worker.py::_handle_backtesting_phase()`.

Gate thresholds:

- Win rate < 45% → FAIL
- Max drawdown > 40% → FAIL
- Sharpe ratio < -0.5 → FAIL

---

## M4 Complete (Core)

All core tasks completed. The agent now:

1. Designs strategy via Claude (M2)
2. Calls TrainingService directly (M3)
3. Evaluates training quality gate
4. Calls BacktestingService directly (M4)
5. Evaluates backtest quality gate
6. Continues to assessment if gate passes

---

## Key Implementation Notes

### Backtest Metrics Structure

BacktestingService returns metrics nested under `result_summary.metrics`:

```python
{
    "result_summary": {
        "metrics": {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 15000.0,      # Absolute value in $
            "max_drawdown_pct": 0.15,     # Percentage (use for gate)
            "total_return": 25000.0,
            "total_trades": 42,
        }
    }
}
```

Use `max_drawdown_pct` for gate evaluation, not `max_drawdown`.

### Service Dependencies

Both services require WorkerRegistry:

```python
from ktrdr.api.endpoints.workers import get_worker_registry
registry = get_worker_registry()
service = BacktestingService(worker_registry=registry)
```

### Backtest Date Range

Currently hardcoded to 2024 held-out period. Future enhancement could make this configurable via strategy config.

---

## What's Next: M5 (Assessment)

M5 replaces `StubAssessmentWorker` with `AgentAssessmentWorker` that:

1. Calls Claude to evaluate training and backtest results
2. Saves assessment JSON to disk
3. Returns verdict (promising/mediocre/poor) and suggestions

After M5, the full cycle is complete:
Design → Train → Backtest → Assess → Done
