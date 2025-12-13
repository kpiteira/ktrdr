# M0 Handoff: Branch Cleanup Complete

## What Was Done

Consolidated agent code from `research_agents/` into `ktrdr/agents/`:

1. **Moved prompts.py** - `session_id` → `operation_id` adaptation complete
2. **Merged gates** - Training and backtest gates in single file with env configuration
3. **Moved strategy_utils** - Database dependency removed, now scans files directly
4. **Fixed invoker** - Added `CancelledError` propagation
5. **Updated executor imports** - Now uses `ktrdr.agents.strategy_utils`
6. **Stubbed API services** - `agent_service.py` and `startup.py` return pending messages
7. **Deleted `research_agents/`** - All code consolidated

## Gotchas for M1+

1. **API endpoints are stubbed** - `/api/v1/agents/*` endpoints return "pending MVP" messages
2. **No session database** - Use `OperationsService` for state tracking instead
3. **Strategy utils are async** - `get_recent_strategies()` etc. need `await`
4. **Gate functions renamed** - `check_training_gate()` not `evaluate_training_gate()`

## Files Changed

| File | Change |
|------|--------|
| `ktrdr/agents/__init__.py` | Updated exports |
| `ktrdr/agents/prompts.py` | Created (from `research_agents/prompts/strategy_designer.py`) |
| `ktrdr/agents/gates.py` | Created (merged training + backtest gates) |
| `ktrdr/agents/strategy_utils.py` | Created (from `research_agents/services/strategy_service.py`) |
| `ktrdr/agents/invoker.py` | Added `CancelledError` handling |
| `ktrdr/agents/executor.py` | Updated imports |
| `ktrdr/api/services/agent_service.py` | Stubbed |
| `ktrdr/api/startup.py` | Removed trigger loop |

## Entry Points for M1

The M1 orchestrator needs to integrate with:

- `OperationsService` - for creating/tracking operations
- `ktrdr.agents.invoker.AnthropicAgentInvoker` - for LLM calls
- `ktrdr.agents.executor.ToolExecutor` - for tool execution
- `ktrdr.agents.prompts.get_strategy_designer_prompt()` - for prompts
- `ktrdr.agents.gates.check_training_gate()` / `check_backtest_gate()` - for quality gates
