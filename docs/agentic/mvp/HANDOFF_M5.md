# M5 Assessment Worker Handoff

## Summary

Milestone 5 implements the Assessment Worker, completing the full agent research cycle. Claude can now analyze training and backtest results to provide verdicts on strategy quality.

## Implementation

### Files Created
- `ktrdr/agents/workers/assessment_worker.py` - AgentAssessmentWorker class
- `tests/unit/agent_tests/test_assessment_prompt.py` - Prompt tests
- `tests/unit/agent_tests/test_assessment_tool.py` - Tool tests
- `tests/unit/agent_tests/test_assessment_worker.py` - Worker tests
- `tests/integration/agent_tests/test_agent_assessment_integration.py` - Integration tests

### Files Modified
- `ktrdr/agents/prompts.py` - Added `AssessmentContext`, `ASSESSMENT_SYSTEM_PROMPT`, `get_assessment_prompt()`
- `ktrdr/agents/tools.py` - Added `save_assessment` tool schema
- `ktrdr/agents/executor.py` - Added `_handle_save_assessment` handler
- `ktrdr/agents/workers/__init__.py` - Export `AgentAssessmentWorker`
- `ktrdr/api/services/agent_service.py` - Wired real assessment worker
- `tests/unit/agent_tests/test_agent_service_new.py` - Updated test for real worker

## Assessment Flow

1. Orchestrator calls `AgentAssessmentWorker.run(parent_op_id, results)`
2. Worker gets strategy info from parent operation metadata
3. Builds prompt with training/backtest metrics via `get_assessment_prompt()`
4. Calls Claude with `ASSESSMENT_SYSTEM_PROMPT` and tools
5. Claude analyzes results and calls `save_assessment` tool
6. Assessment saved to `strategies/{name}/assessment.json`
7. Worker returns verdict, strengths, weaknesses, suggestions

## Key Patterns

### Strategy Name for Tool
The worker sets `executor._current_strategy_name` before calling Claude. This lets the `save_assessment` handler know where to save the file.

### Assessment Context
```python
AssessmentContext(
    operation_id="op_xxx",
    strategy_name="momentum_v1",
    strategy_path="/app/strategies/momentum_v1.yaml",
    training_metrics={"accuracy": 0.65, "final_loss": 0.35},
    backtest_metrics={"sharpe_ratio": 1.2, "win_rate": 0.55},
)
```

### Verdict Values
Three valid verdicts: `"promising"`, `"mediocre"`, `"poor"`

## Full Cycle Now Complete

With M5, the agent MVP is functionally complete:
1. **Design** - Claude creates strategy (real)
2. **Training** - Strategy trained on data (real)
3. **Backtest** - Model backtested (real)
4. **Assessment** - Claude evaluates results (real)

All phases now use real workers (not stubs) by default.

## Test Coverage

- 262 agent tests pass
- 2355 unit tests pass
- Integration tests verify full cycle
