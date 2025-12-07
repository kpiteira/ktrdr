# Phase 0 Implementation Handoff

## Session Summary

**Date:** 2024-12-07
**Branch:** `feature/agent-mvp`
**Commits:** 2 commits made

## Completed Tasks

### Task 0.1: Database Tables ✅
- Created `research_agents/` package structure
- Implemented `AgentSession` and `AgentAction` dataclasses in `schema.py`
- Implemented `AgentDatabase` class with asyncpg in `queries.py`
- Full CRUD operations: create_session, get_session, update_session, complete_session, log_action
- **18 unit tests passing**

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

## Remaining Tasks

### Task 0.2: Agent State MCP Tools (Next)
- Need to add tools to `mcp/src/server.py`:
  - `create_agent_session()` - Creates new session, returns session_id
  - `get_agent_state(session_id)` - Returns current session state
  - `update_agent_state(session_id, phase, strategy_name?, operation_id?)` - Updates session
- Should connect to database via `research_agents.database.AgentDatabase`
- Follow existing MCP tool patterns with `@mcp.tool()` and `@trace_mcp_tool()`

### Task 0.5: Agent Invocation
- Trigger service needs to invoke Claude CLI via subprocess
- Pass MCP config and prompts

### Task 0.6: Basic CLI Commands
- Add `ktrdr agent` command group
- Commands: `status`, `start`, `stop`

### Task 0.7: E2E Test
- Full cycle validation

## Key Learnings for Next Implementer

### 1. Test Directory Naming
**CRITICAL:** Do NOT name test directories the same as package names!
- ❌ `tests/unit/research_agents/` shadows `research_agents/` package
- ✅ `tests/unit/agent_tests/` works correctly

The import `import research_agents` was resolving to the test directory instead of the actual package.

### 2. Async Mock Pattern for asyncpg
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

### 3. Test Timing for Async Services
For trigger service loop tests, use very short intervals:
```python
config = TriggerConfig(interval_seconds=0.01, enabled=True)  # Not 1 second!
```

### 4. Package Configuration
`research_agents` was added to:
- `pyproject.toml`: `[tool.hatch.build.targets.wheel] packages = ["ktrdr", "research_agents"]`
- `pyproject.toml`: `dependencies` includes `asyncpg>=0.30.0`
- `pytest.ini`: `pythonpath = .`

### 5. File Structure Created

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
    └── trigger.py         # TriggerConfig, TriggerService

tests/unit/agent_tests/
├── __init__.py
├── conftest.py
├── test_agent_db.py       # 18 tests
├── test_prompts.py        # 5 tests
└── test_trigger.py        # 8 tests
```

## Running Tests

```bash
# All agent tests (31 tests, ~0.3s)
uv run pytest tests/unit/agent_tests/ -v --no-cov

# Quality checks
make quality
```

## Git Status

```bash
git log --oneline -3
# d3d4112 feat(agents): Add trigger service and Phase 0 test prompt (Tasks 0.3, 0.4)
# 5b73606 feat(agents): Add database schema for research agents (Task 0.1)
```

Ready to continue with Task 0.2 (MCP tools).
