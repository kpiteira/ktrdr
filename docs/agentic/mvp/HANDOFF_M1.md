# M1 Handoff: Orchestrator Shell Complete

## What Was Done

Built the orchestrator shell with stub workers:

1. **Operation Types** - Added `AGENT_RESEARCH`, `AGENT_DESIGN`, `AGENT_ASSESSMENT` to `OperationType`
2. **Stub Workers** - Created `StubDesignWorker`, `StubTrainingWorker`, `StubBacktestWorker`, `StubAssessmentWorker`
3. **AgentResearchWorker** - Main orchestrator with phase transitions (designing → training → backtesting → assessing)
4. **AgentService** - Operations-only service (no session database)
5. **Simplified API** - `POST /trigger` (202/409) and `GET /status` only
6. **Simplified CLI** - `ktrdr agent trigger` and `ktrdr agent status` only
7. **Cleaned startup.py** - Removed legacy trigger loop stubs

## E2E Test Results

All tests pass:
- Trigger creates operation and starts worker (~2s with stubs)
- Status shows active cycle during operation, last_cycle when idle
- Duplicate trigger returns 409 with `active_cycle_exists`
- CLI commands work correctly

## Architecture

```
API: POST /agent/trigger
    ↓
AgentService.trigger()
    ↓
OperationsService.create_operation(AGENT_RESEARCH)
    ↓
asyncio.create_task(AgentResearchWorker.run())
    ↓
AgentResearchWorker orchestrates:
    ├── StubDesignWorker.run()      → designing phase
    ├── StubTrainingWorker.run()    → training phase
    ├── StubBacktestWorker.run()    → backtesting phase
    └── StubAssessmentWorker.run()  → assessing phase
    ↓
OperationsService.complete_operation()
```

## Gotchas for M2+

1. **Stubs are fast** - Real workers will take much longer (~30s design, ~5min training, ~1min backtest)
2. **No Claude integration yet** - Design and Assessment workers are stubs
3. **No real training/backtest** - Workers just return mock results
4. **Phase metadata** - Use `OperationMetadata.parameters["phase"]` to track current phase

## Files Changed

| File | Change |
|------|--------|
| `ktrdr/api/models/operations.py` | Added operation types |
| `ktrdr/agents/workers/stubs.py` | Created stub workers |
| `ktrdr/agents/workers/research_worker.py` | Created orchestrator |
| `ktrdr/api/services/agent_service.py` | Rewritten for operations-only |
| `ktrdr/api/endpoints/agent.py` | Simplified to trigger/status |
| `ktrdr/cli/agent_commands.py` | Simplified to trigger/status |
| `ktrdr/api/startup.py` | Removed legacy stubs |

## Entry Points for M2

The M2 design worker needs to integrate with:

- `ktrdr.agents.invoker.AnthropicAgentInvoker` - for Claude API calls
- `ktrdr.agents.prompts.get_strategy_designer_prompt()` - for design prompt
- `ktrdr.agents.executor.ToolExecutor` - for tool execution
- `OperationsService` - for creating child operations (AGENT_DESIGN)

Replace `StubDesignWorker` with real implementation that:
1. Creates child operation (AGENT_DESIGN)
2. Calls Claude with design prompt
3. Handles tool calls via ToolExecutor
4. Writes strategy YAML to disk
5. Returns strategy path for training
