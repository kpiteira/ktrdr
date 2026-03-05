# Handoff — M5: Evolution Integration + Cleanup

## Task 5.1 Complete: Update research orchestrator to dispatch to container workers

**New module: `ktrdr/agents/dispatch.py`** — `AgentDispatchService` handles HTTP dispatch to container workers. Pattern: select worker from registry → POST to `/designs/start` or `/assessments/start` → return operation_id for polling.

**Research worker change: `agent_dispatch` parameter** — Optional kwarg on `AgentResearchWorker.__init__()`. When provided, `_start_design()` and `_start_assessment()` dispatch via HTTP instead of creating asyncio tasks. Falls back to stub/in-process workers when None. Backward compatible — all existing tests pass without changes.

**Orphan detection skipped for container workers** — `_check_and_handle_orphan()` returns False immediately when `agent_dispatch` is set. Container workers are separate processes that survive backend restarts — orphan detection is only relevant for in-process asyncio tasks.

**Key integration point for Task 5.2**: `AgentService._get_worker()` needs to create `AgentDispatchService` (using worker registry) and pass it to `AgentResearchWorker`. Currently creates workers without `agent_dispatch`, so container dispatch isn't wired yet.

**Container endpoints**: Design at `/designs/start` (DesignStartRequest: brief, symbol, timeframe, task_id), Assessment at `/assessments/start` (AssessmentStartRequest: strategy_name, training_metrics, backtest_results, task_id). Both return `{"operation_id": ..., "success": true}`.
