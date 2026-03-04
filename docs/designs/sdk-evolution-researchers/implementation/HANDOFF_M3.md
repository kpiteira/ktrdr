# Handoff — M3: Design Agent Worker

## Task 3.1 Complete: Create DesignAgentWorker (WorkerAPIBase)

**Gotcha: `fail_operation` takes `error_message=` not `error=`** — OperationsService.fail_operation signature uses `error_message` parameter name. Easy to get wrong since other error patterns use `error`.

**Gotcha: `prompts.py` exists as a file** — Can't create `prompts/design_sdk.py` package without converting `prompts.py` → `prompts/__init__.py` first. Task 3.1 put the prompt at `ktrdr/agents/design_sdk_prompt.py` instead. Task 3.2 should decide final location.

**Pattern: mock OperationsService via direct assignment** — Don't try to patch `get_operations_service` in the worker module (WorkerAPIBase calls it from `ktrdr.workers.base`). Instead create worker normally, then `worker._operations_service = mock_ops` (same as `tests/unit/workers/test_base.py`).

**Pattern: result extraction uses last save call** — Agent may iterate and call `save_strategy_config` multiple times. `extract_strategy_from_transcript()` uses the last occurrence. Parses both the tool_use input (for strategy_name) and tool_result content (for path and confirmed name).

## Task 3.2 Complete: Write Design Agent System Prompt

**Decision: kept prompt at `ktrdr/agents/design_sdk_prompt.py`** — No prompts package conversion needed. The old `prompts.py` serves the old AnthropicInvoker path; the new `design_sdk_prompt.py` serves the SDK-based worker. Clean separation.

**Prompt structure (60 lines)**: Role → Workflow (5 steps) → Output Contract → Discovery Tools → Filesystem Access → Design Guidelines → Safety Constraints. No YAML templates, no enum lists, no indicator lists.

## Task 3.3 Complete: Wire Design Agent into Docker Compose

**Pattern: conditional module-level app creation** — Worker's module-level `app` is only created when `KTRDR_WORKER_TYPE=agent_design` env var is set (container context). Tests import the module without triggering runtime creation. Uses `_create_default_worker()` factory that reads settings and creates `ClaudeAgentRuntime`.

**Gotcha: port 5010 conflicts with commented-out training-worker-4** — Used `KTRDR_DESIGN_AGENT_PORT` env var (defaults to 5010) to avoid collision.

**Auth volume: `ktrdr-agent-claude-auth` (external: true)** — Must be created before `docker compose up`. One-time setup: `docker volume create ktrdr-agent-claude-auth` then `docker run --rm -it -v ktrdr-agent-claude-auth:/home/agent/.claude ktrdr-agent:dev claude login`.

**Next Task Notes (3.4)**: Unit tests for design agent worker already exist from Task 3.1 (16 tests). Task 3.4 adds comprehensive coverage — mock AgentRuntime, test prompt composition, edge cases. Tests should import from `ktrdr.agents.workers.design_agent_worker` directly (module-level app is None when not in container).

## Task 3.4 Complete: Unit Tests for Design Agent Worker

**Coverage: 28 tests in test_design_agent_worker.py + 11 in test_design_sdk_prompt.py = 39 total.** Task 3.1 created 16 base tests; Task 3.4 added 12 more covering: timeout handling (asyncio.TimeoutError), result_summary field completeness (cost/turns/session_id/path), system prompt identity verification, MCP config validation, prompt composition without context, malformed tool_result parsing, non-save tool filtering, and _build_user_prompt unit tests.

**Pattern: test classes organized by concern** — TestStartEndpoint, TestResultExtraction, TestBackgroundExecution (3.1), then TestBackgroundExecutionExtended, TestResultExtractionExtended, TestPromptComposition (3.4). Extended classes avoid modifying 3.1's tested code.

**Next Task Notes (3.5)**: VALIDATION task — E2E test via e2e agent workflow. Requires sandbox running with design-agent-1 container, Claude auth volume provisioned, and EURUSD data available.
