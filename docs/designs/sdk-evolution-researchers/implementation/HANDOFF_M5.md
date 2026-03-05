# Handoff — M5: Evolution Integration + Cleanup

## Task 5.1 Complete: Update research orchestrator to dispatch to container workers

**New module: `ktrdr/agents/dispatch.py`** — `AgentDispatchService` handles HTTP dispatch to container workers. Pattern: select worker from registry → POST to `/designs/start` or `/assessments/start` → return operation_id for polling.

**Research worker change: `agent_dispatch` parameter** — Optional kwarg on `AgentResearchWorker.__init__()`. When provided, `_start_design()` and `_start_assessment()` dispatch via HTTP instead of creating asyncio tasks. Falls back to stub/in-process workers when None. Backward compatible — all existing tests pass without changes.

**Orphan detection skipped for container workers** — `_check_and_handle_orphan()` returns False immediately when `agent_dispatch` is set. Container workers are separate processes that survive backend restarts — orphan detection is only relevant for in-process asyncio tasks.

**Key integration point for Task 5.2**: `AgentService._get_worker()` needs to create `AgentDispatchService` (using worker registry) and pass it to `AgentResearchWorker`. Currently creates workers without `agent_dispatch`, so container dispatch isn't wired yet.

**Container endpoints**: Design at `/designs/start` (DesignStartRequest: brief, symbol, timeframe, task_id), Assessment at `/assessments/start` (AssessmentStartRequest: strategy_name, training_metrics, backtest_results, task_id). Both return `{"operation_id": ..., "success": true}`.

## Task 5.2 Complete: Update worker registry and backend dispatch for agent types

**Wiring in `AgentService._get_worker()`** — Non-stub path now creates `AgentDispatchService(worker_registry=registry)` and passes it as `agent_dispatch` kwarg. Stub path unchanged (no dispatch).

**Worker status includes agent types** — `_get_worker_status()` now queries AGENT_DESIGN and AGENT_ASSESSMENT in addition to TRAINING and BACKTESTING.

**Gotcha: lazy import patching** — `get_worker_registry` is imported lazily inside function bodies. Tests must patch `ktrdr.api.endpoints.workers.get_worker_registry`, not `ktrdr.api.services.agent_service.get_worker_registry`.

**Note for Task 5.3**: `resolve_model` is still imported from `ktrdr.agents.invoker` at top of agent_service.py. Will need to be moved before invoker is deleted in Task 5.4.

## Task 5.3 Complete: Adapt BudgetTracker for subscription model

**Constructor fix**: `daily_limit=0.0` was treated as falsy and replaced with default ($20). Changed to `daily_limit if daily_limit is not None else settings.daily_budget`.

**Subscription model**: When `daily_limit == 0`, budget enforcement is disabled: `can_spend()` always returns True, `get_remaining()` returns `float("inf")`, `get_status()` includes `budget_disabled: True`.

**Backward compatible**: All 21 existing budget tests pass unchanged. Non-zero limits enforce budgets as before. `get_status()` adds `budget_disabled` field for all cases (True/False).

## Task 5.4 Complete: Remove old invoker code + update stub workers

**Deleted files**: `invoker.py`, `executor.py`, `tools.py` (old Anthropic API client, tool executor, tool definitions). Also deleted old in-process `design_worker.py` and `assessment_worker.py` — replaced by containerized `design_agent_worker.py`/`assessment_agent_worker.py` (M3/M4).

**Extracted model resolution**: `VALID_MODELS`, `MODEL_ALIASES`, `DEFAULT_MODEL`, `resolve_model()` moved to new `ktrdr/agents/models.py`. Consumers updated: `agent_service.py`, `api/models/agent.py`, `agents/__init__.py`.

**Agent service cleanup**: Non-stub path now uses `StubDesignWorker`/`StubAssessmentWorker` as fallback (instead of old in-process workers). Container dispatch via `agent_dispatch` takes priority.

**Deleted test files**: 8 test files testing old invoker/executor/tools/workers. New `test_invoker_removal.py` with 15 tests verifying extraction and deletion.

**Gotcha**: Tests from Task 5.2 patched `AgentDesignWorker`/`AgentAssessmentWorker` on agent_service module — needed updating after those imports were removed.

## Task 5.5 Complete: E2E Validation — PASSED (Real Agents)

**Test**: Full evolution with containerized Claude Code agents — PASSED

**Full pipeline verified**: design (container) → training → backtest (gate rejected) → assessment (container) → completed. Duration: ~8 minutes per research. Real Claude API calls (claude-haiku-4-5).

**Bugs found and fixed during E2E**:

1. **Operation ID collision** — Container workers reused parent's `task_id` as their own `operation_id`, causing PostgreSQL unique constraint violation. Fix: generate unique `op_design_*`/`op_assessment_*` IDs, store parent reference in metadata.

2. **Orphan detector killing agent ops** — 60s timeout was killing 3-7 minute Claude API calls. Fix: skip `AGENT_DESIGN`/`AGENT_ASSESSMENT` types in orphan detector.

3. **Stale cache (split-brain)** — Backend cached container operations as `running` and never refreshed from DB/container. Coordinator saw stale status indefinitely. Fix: register `OperationServiceProxy` for container-dispatched operations (same pattern as training/backtest workers).

4. **Strategy path null** — Container design agent returns `strategy_name` but `strategy_path=null` (MCP saves via API, path is container-local). Fix: fall back to `strategies/{name}.yaml` when path is missing.

**COMPOSE_PROJECT_NAME fix**: `kinfra sandbox status` used instance ID but containers use `slot-N`. Fixed `generate_env_file` in both `sandbox.py` and `kinfra/sandbox.py`.

**Key architectural pattern**: Container agent workers need `OperationServiceProxy` registration (via `_register_container_proxy`) so the backend can poll their HTTP API for status updates, just like training/backtest workers.
