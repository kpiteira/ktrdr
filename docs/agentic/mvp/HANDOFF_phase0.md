# Phase 0 Implementation Handoff

## Session Summary

**Date:** 2024-12-07
**Branch:** `feature/agent-mvp`
**Commits:** 5 commits made

## Completed Tasks

### Task 0.1: Database Tables ✅
- Created `research_agents/` package structure
- Implemented `AgentSession` and `AgentAction` dataclasses in `schema.py`
- Implemented `AgentDatabase` class with asyncpg in `queries.py`
- Full CRUD operations: create_session, get_session, update_session, complete_session, log_action
- **18 unit tests passing**

### Task 0.2: Agent State MCP Tools ✅

- Created service layer in `research_agents/services/agent_state.py` (testable business logic)
- Created MCP tool wrappers in `mcp/src/tools/agent_tools.py`
- Registered tools via `register_agent_tools(mcp)` in `mcp/src/server.py`
- Tools implemented:
  - `create_agent_session()` - Creates new session, returns session_id
  - `get_agent_state(session_id)` - Returns current session state
  - `update_agent_state(session_id, phase, strategy_name?, operation_id?)` - Updates session
- **12 unit tests passing**

### Task 0.3: Basic Trigger Service ✅
- Implemented `TriggerConfig` with env var loading
- Implemented `TriggerService` with interval-based check loop
- Checks for active sessions before triggering agent
- **8 unit tests passing**

### Task 0.4: Minimal Agent Prompt ✅
- Created Phase 0 test prompt in `prompts/phase0_test.py`
- System and user prompts for 3-step validation flow
- `get_phase0_prompt()` function for prompt retrieval
- **5 unit tests passing**

### Task 0.5: Agent Invocation ✅

- Created `ClaudeCodeInvoker` class in `research_agents/services/invoker.py`
- Uses subprocess to invoke Claude CLI with MCP config
- Configuration via `InvokerConfig` with env var support:
  - `AGENT_INVOKER_TIMEOUT_SECONDS` (default: 300)
  - `CLAUDE_PATH` (default: "claude")
  - `AGENT_MCP_CONFIG_PATH` (default: mcp/claude_mcp_config.json)
- Features implemented:
  - Subprocess invocation with `asyncio.create_subprocess_exec`
  - JSON output parsing with raw output fallback
  - Timeout handling with process kill
  - Success/failure detection via exit code
  - Session context injection into prompt
- **16 unit tests passing**

## Remaining Tasks

### Task 0.6: Basic CLI Commands (Next)

- Add `ktrdr agent` command group
- Commands: `status`, `trigger`
- File: `ktrdr/cli/commands/agent.py`

### Task 0.7: E2E Test

- Full cycle validation
- File: `tests/integration/research_agents/test_agent_e2e.py`

## Key Learnings for Next Implementer

### 1. Test Directory Naming
**CRITICAL:** Do NOT name test directories the same as package names!
- ❌ `tests/unit/research_agents/` shadows `research_agents/` package
- ✅ `tests/unit/agent_tests/` works correctly

The import `import research_agents` was resolving to the test directory instead of the actual package.

### 2. MCP Package Naming Conflict

**CRITICAL:** The `mcp/` directory conflicts with the installed `mcp` package!

- The local `mcp/` directory cannot be imported as `mcp.src.tools...`
- Solution: Put testable business logic in `research_agents/services/`
- MCP tools are thin wrappers that call the service layer
- Tests import from `research_agents.services.agent_state`, not from `mcp.src.tools`

### 3. Async Mock Pattern for asyncpg
When mocking `asyncpg.Pool.acquire()` context manager:

```python
pool = MagicMock()
conn = AsyncMock()

# Create async context manager mock
acquire_cm = MagicMock()
acquire_cm.__aenter__ = AsyncMock(return_value=conn)
acquire_cm.__aexit__ = AsyncMock(return_value=None)
pool.acquire.return_value = acquire_cm
```

### 4. Test Timing for Async Services
For trigger service loop tests, use very short intervals:
```python
config = TriggerConfig(interval_seconds=0.01, enabled=True)  # Not 1 second!
```

### 5. Package Configuration
`research_agents` was added to:
- `pyproject.toml`: `[tool.hatch.build.targets.wheel] packages = ["ktrdr", "research_agents"]`
- `pyproject.toml`: `dependencies` includes `asyncpg>=0.30.0`
- `pytest.ini`: `pythonpath = .`

### 6. File Structure Created

```
research_agents/
├── __init__.py
├── database/
│   ├── __init__.py
│   ├── schema.py          # AgentSession, AgentAction, SessionPhase, SessionOutcome
│   └── queries.py         # AgentDatabase class
├── prompts/
│   ├── __init__.py
│   └── phase0_test.py     # PHASE0_SYSTEM_PROMPT, PHASE0_TEST_PROMPT
└── services/
    ├── __init__.py
    ├── trigger.py         # TriggerConfig, TriggerService
    ├── agent_state.py     # create_agent_session, get_agent_state, update_agent_state
    └── invoker.py         # InvokerConfig, ClaudeCodeInvoker, InvocationResult

mcp/src/tools/
└── agent_tools.py         # MCP tool wrappers, register_agent_tools()

tests/unit/agent_tests/
├── __init__.py
├── conftest.py
├── test_agent_db.py       # 18 tests
├── test_agent_tools.py    # 12 tests
├── test_invoker.py        # 16 tests
├── test_prompts.py        # 5 tests
└── test_trigger.py        # 8 tests
```

## Running Tests

```bash
# All agent tests (59 tests, ~0.5s)
uv run pytest tests/unit/agent_tests/ -v --no-cov

# Quality checks
make quality
```

## Git Status

```bash
git log --oneline -5
# feat(agents): Add agent invoker for Claude CLI (Task 0.5)
# 36c2ce6 feat(agents): Add agent state MCP tools (Task 0.2)
# 3df0b9a docs(agents): Add Phase 0 implementation handoff document
# d3d4112 feat(agents): Add trigger service and Phase 0 test prompt (Tasks 0.3, 0.4)
# 5b73606 feat(agents): Add database schema for research agents (Task 0.1)
```

Ready to continue with Task 0.6 (Basic CLI Commands).
