# Phase 1: Design Integration

**Goal**: Replace design stub with real Anthropic/Claude integration

**Prerequisite**: Phase 0 complete (state machine with stubs working)
**Branch**: `feature/agent-mvp`

---

## Overview

Phase 0 created AgentService with stub phases (~30 sec sleeps). Phase 1 replaces the `_run_design_phase()` stub with real Anthropic/Claude integration.

**What's already done (Phase 0)**:

- AGENT_RESEARCH operation type added
- AgentService with state machine
- API endpoints (trigger/status)
- CLI commands (trigger/status/cancel)
- Stub phases that sleep ~30 sec each

**What Phase 1 does**:

- Replace design stub with real Claude invocation
- Use existing prompt builder (moved during cleanup)
- Capture strategy_name from tool_outputs
- Update progress tracking for design phase

---

## Task 1.1: Replace design stub with real implementation

**File**: `ktrdr/api/services/agent_service.py`

Replace the stub `_run_design_phase()` method with real Anthropic integration.

**Current stub** (from Phase 0):

```python
async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
    """Run design phase (STUB - will be replaced in Phase 1)."""
    for i in range(300):  # ~30 seconds
        if await self._check_cancelled(operation_id):
            return {"success": False, "error": "Cancelled"}
        await self._ops.update_progress(
            operation_id,
            percentage=int(i / 3),
            current_step=f"Designing strategy... ({i}%)"
        )
        await asyncio.sleep(0.1)

    return {
        "success": True,
        "strategy_name": f"stub_strategy_{operation_id[-8:]}",
        "strategy_path": f"/tmp/strategies/stub_strategy_{operation_id[-8:]}.yaml",
    }
```

**Replace with**:

```python
async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
    """Run Claude to design a strategy.

    Returns:
        Dict with success, strategy_name, strategy_path, or error
    """
    from ktrdr.agents.executor import create_tool_executor
    from ktrdr.agents.invoker import AnthropicAgentInvoker
    from ktrdr.agents.tools import AGENT_TOOLS
    from ktrdr.agents.prompts import get_strategy_designer_prompt

    # Check cancellation before starting
    if await self._check_cancelled(operation_id):
        return {"success": False, "error": "Cancelled"}

    # Update progress
    await self._ops.update_progress(
        operation_id,
        percentage=10,
        current_step="Invoking Claude to design strategy",
    )

    # Create invoker and executor
    invoker = AnthropicAgentInvoker()
    executor = create_tool_executor()

    # Build prompt (uses prompt builder moved during cleanup)
    prompt = get_strategy_designer_prompt(operation_id=operation_id)

    # System prompt for the agent
    system_prompt = self._get_design_system_prompt()

    try:
        # Run the agent (async Claude invocation)
        result = await invoker.run(
            prompt=prompt,
            tools=AGENT_TOOLS,
            system_prompt=system_prompt,
            tool_executor=executor,
        )
    except Exception as e:
        return {"success": False, "error": f"Claude invocation failed: {e}"}

    if not result.success:
        return {"success": False, "error": result.error}

    # Update progress after Claude finishes
    await self._ops.update_progress(
        operation_id,
        percentage=80,
        current_step="Design complete, extracting strategy info",
    )

    # Extract strategy info from tool_outputs
    # tool_outputs is populated by save_strategy_config tool
    if result.tool_outputs:
        return {
            "success": True,
            "strategy_name": result.tool_outputs.get("strategy_name"),
            "strategy_path": result.tool_outputs.get("strategy_path"),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    # No strategy was saved - this is a failure
    return {
        "success": False,
        "error": "Agent completed but did not save a strategy",
    }


def _get_design_system_prompt(self) -> str:
    """Get the system prompt for strategy design."""
    return """You are a trading strategy designer for the KTRDR neuro-fuzzy system.

You design strategies that use:
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Fuzzy logic membership functions
- Neural networks for decision making

Your goal is to create novel, testable strategies. Each strategy should:
- Have a clear hypothesis about market behavior
- Use 2-4 complementary indicators (avoid redundant indicators)
- Define appropriate fuzzy sets for each indicator
- Configure a reasonable neural network architecture

Always validate your strategy config before saving it.
Always save your strategy when done designing.
"""
```

**Note**: The prompt builder (`get_strategy_designer_prompt`) was moved from `research_agents/prompts/strategy_designer.py` to `ktrdr/agents/prompts.py` during cleanup.

---

## Task 1.2: Capture strategy_name from tool results

**Problem**: The `AnthropicAgentInvoker` doesn't currently capture tool outputs. When `save_strategy_config` is called, we need to capture the strategy_name and path.

**File**: `ktrdr/agents/invoker.py`

**Change 1**: Add `tool_outputs` field to `AgentResult`:

```python
@dataclass
class AgentResult:
    """Result of an agent invocation."""
    success: bool
    output: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    tool_outputs: dict[str, Any] | None = None  # NEW: Captured tool outputs
```

**Change 2**: Modify `_execute_tools` to capture important results:

```python
async def _execute_tools(
    self,
    tool_calls: list[Any],
    tool_executor: ToolExecutor | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute tool calls and return results.

    Returns:
        Tuple of (tool_result_blocks, captured_outputs)
    """
    results = []
    captured_outputs = {}  # NEW: Capture important outputs

    for tool_call in tool_calls:
        tool_name = tool_call.name
        tool_input = tool_call.input
        tool_use_id = tool_call.id

        # ... existing execution code ...

        result_content = await tool_executor(tool_name, tool_input)

        # NEW: Capture strategy info from save_strategy_config
        if tool_name == "save_strategy_config" and isinstance(result_content, dict):
            if result_content.get("success"):
                captured_outputs["strategy_name"] = result_content.get("name")
                captured_outputs["strategy_path"] = result_content.get("path")

        results.append({
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": str(result_content),
        })

    return results, captured_outputs
```

**Change 3**: Update `run()` method to collect and return captured outputs:

```python
async def run(self, ...) -> AgentResult:
    # ... existing code ...
    all_captured_outputs = {}  # Collect across all iterations

    while True:
        # ... API call ...

        if not tool_calls:
            # Return with captured outputs
            return AgentResult(
                success=True,
                output=output_text,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                error=None,
                tool_outputs=all_captured_outputs if all_captured_outputs else None,
            )

        # Execute tools and capture outputs
        tool_results, captured = await self._execute_tools(tool_calls, tool_executor)
        all_captured_outputs.update(captured)

        # ... continue loop ...
```

**Test**:

```python
@pytest.mark.asyncio
async def test_invoker_captures_strategy_from_save_tool():
    """Invoker should capture strategy_name when save_strategy_config succeeds."""
    # Setup mock that returns save result
    mock_executor = AsyncMock(return_value={
        "success": True,
        "name": "test_strategy_v1",
        "path": "/app/strategies/test_strategy_v1.yaml",
    })

    # ... run invoker with mock ...

    assert result.tool_outputs is not None
    assert result.tool_outputs["strategy_name"] == "test_strategy_v1"
```

---

## Task 1.3: Update progress tracking for design phase

**File**: `ktrdr/api/services/agent_service.py`

Update progress during design to give user visibility into the Claude interaction.

**Add progress updates at key points**:

```python
async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
    """Run Claude to design a strategy."""
    # ... imports ...

    # Progress: Starting
    await self._ops.update_progress(
        operation_id,
        percentage=5,
        current_step="Preparing design prompt",
    )

    # Build prompt
    prompt = get_strategy_designer_prompt(operation_id=operation_id)

    # Progress: Prompt ready
    await self._ops.update_progress(
        operation_id,
        percentage=10,
        current_step="Invoking Claude to design strategy",
    )

    # Run agent (this is the long part)
    result = await invoker.run(...)

    # Progress: Claude finished
    await self._ops.update_progress(
        operation_id,
        percentage=80,
        current_step="Design complete, validating strategy",
    )

    # ... extract and validate ...

    # Progress: Done
    await self._ops.update_progress(
        operation_id,
        percentage=95,
        current_step="Strategy saved successfully",
    )

    return {"success": True, ...}
```

---

## Phase 1 Verification

### Integration Test Sequence (MANDATORY)

**Focus**: Verify real Claude integration works without breaking the state machine from Phase 0.

```bash
# 1. Start services
docker compose up -d
docker compose ps  # Verify healthy
```

```bash
# 2. Trigger and verify REAL Claude invocation
ktrdr agent trigger
# ✅ Expected: "Research cycle started!"
# Watch the designing phase - should take 30-60 sec (not 30 sec stub)
watch -n 2 "ktrdr agent status"
```

```bash
# 3. Verify strategy file created
ls strategies/
# ✅ Expected: New YAML file (e.g., strategies/momentum_v1_20251213.yaml)
cat strategies/<newest_file>.yaml
# ✅ Expected: Valid strategy YAML with indicators, fuzzy sets, neural config
```

```bash
# 4. Verify state consistency after design completes
# Wait for training phase to start, then check:
ktrdr agent status
# ✅ Expected: Phase shows "training" (not stuck on "designing")
# ✅ Expected: strategy_name field populated
```

```bash
# 5. Test cancellation during Claude invocation
ktrdr agent trigger
sleep 10  # Let Claude start
ktrdr agent cancel <op_id>
# ✅ Expected: Clean cancellation (Claude stops, no orphaned state)
ktrdr agent status
# ✅ Expected: Shows "idle"
```

```bash
# 6. Check logs for errors
docker compose logs backend --since 10m | grep -i error
# ✅ Expected: No errors (Claude errors should be handled gracefully)
```

### State Consistency Checks

After Phase 1, verify Phase 0's state machine still works:

- [ ] Full cycle still completes (real design → stub training → stub backtest → stub assess)
- [ ] Cancellation at each phase still works
- [ ] State consistency maintained (no orphaned operations)

### Acceptance Criteria

**Unit tests**:

- [ ] All unit tests pass (`make test-unit`)

**Integration tests**:

- [ ] Real Claude is invoked (takes 30-60s, not 30s stub)
- [ ] Strategy file saved to `strategies/` folder
- [ ] Strategy YAML is valid and contains all sections
- [ ] `strategy_name` captured from tool output and shown in status
- [ ] Token usage tracked (check operation metadata)
- [ ] Progress updates visible during Claude invocation
- [ ] Cancellation during Claude call works cleanly
- [ ] Other phases still use stubs (training ~30s, backtest ~30s, assess ~30s)
- [ ] No errors in logs
- [ ] State consistent after completion and cancellation

**If ANY checkbox is unchecked**: Fix before proceeding to Phase 2.

---

## Files Modified Summary

| File | Action |
|------|--------|
| `ktrdr/api/services/agent_service.py` | Modify - replace `_run_design_phase()` stub |
| `ktrdr/agents/invoker.py` | Modify - add tool_outputs capture |
| `tests/unit/api/services/test_agent_service.py` | Add tests for design phase |
| `tests/unit/agents/test_invoker.py` | Add tests for tool_outputs capture |
