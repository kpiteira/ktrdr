# Handoff — M3: Design Agent Worker

## Task 3.1 Complete: Create DesignAgentWorker (WorkerAPIBase)

**Gotcha: `fail_operation` takes `error_message=` not `error=`** — OperationsService.fail_operation signature uses `error_message` parameter name. Easy to get wrong since other error patterns use `error`.

**Gotcha: `prompts.py` exists as a file** — Can't create `prompts/design_sdk.py` package without converting `prompts.py` → `prompts/__init__.py` first. Task 3.1 put the prompt at `ktrdr/agents/design_sdk_prompt.py` instead. Task 3.2 should decide final location.

**Pattern: mock OperationsService via direct assignment** — Don't try to patch `get_operations_service` in the worker module (WorkerAPIBase calls it from `ktrdr.workers.base`). Instead create worker normally, then `worker._operations_service = mock_ops` (same as `tests/unit/workers/test_base.py`).

**Pattern: result extraction uses last save call** — Agent may iterate and call `save_strategy_config` multiple times. `extract_strategy_from_transcript()` uses the last occurrence. Parses both the tool_use input (for strategy_name) and tool_result content (for path and confirmed name).

## Task 3.2 Complete: Write Design Agent System Prompt

**Decision: kept prompt at `ktrdr/agents/design_sdk_prompt.py`** — No prompts package conversion needed. The old `prompts.py` serves the old AnthropicInvoker path; the new `design_sdk_prompt.py` serves the SDK-based worker. Clean separation.

**Prompt structure (60 lines)**: Role → Workflow (5 steps) → Output Contract → Discovery Tools → Filesystem Access → Design Guidelines → Safety Constraints. No YAML templates, no enum lists, no indicator lists.

**Next Task Notes (3.3)**: Wire `design-agent-1` service into docker-compose.sandbox.yml. Use `ktrdr-agent:dev` image from M2. Key env vars: KTRDR_WORKER_TYPE, KTRDR_WORKER_PORT, backend URL. Auth via named volume. Command: uvicorn `ktrdr.agents.workers.design_agent_worker:app`. Port 5010.
