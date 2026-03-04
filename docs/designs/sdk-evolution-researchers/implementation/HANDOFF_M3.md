# Handoff — M3: Design Agent Worker

## Task 3.1 Complete: Create DesignAgentWorker (WorkerAPIBase)

**Gotcha: `fail_operation` takes `error_message=` not `error=`** — OperationsService.fail_operation signature uses `error_message` parameter name. Easy to get wrong since other error patterns use `error`.

**Gotcha: `prompts.py` exists as a file** — Can't create `prompts/design_sdk.py` package without converting `prompts.py` → `prompts/__init__.py` first. Task 3.1 put the prompt at `ktrdr/agents/design_sdk_prompt.py` instead. Task 3.2 should decide final location.

**Pattern: mock OperationsService via direct assignment** — Don't try to patch `get_operations_service` in the worker module (WorkerAPIBase calls it from `ktrdr.workers.base`). Instead create worker normally, then `worker._operations_service = mock_ops` (same as `tests/unit/workers/test_base.py`).

**Pattern: result extraction uses last save call** — Agent may iterate and call `save_strategy_config` multiple times. `extract_strategy_from_transcript()` uses the last occurrence. Parses both the tool_use input (for strategy_name) and tool_result content (for path and confirmed name).

**Next Task Notes (3.2)**: System prompt placeholder exists at `ktrdr/agents/design_sdk_prompt.py`. Replace with full ~60 line prompt. Import path: `from ktrdr.agents.design_sdk_prompt import DESIGN_SYSTEM_PROMPT`. Consider whether to relocate (prompts package conversion) or keep as-is.
