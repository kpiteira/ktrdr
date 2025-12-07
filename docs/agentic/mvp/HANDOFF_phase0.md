# Phase 0: Implementation Learnings

> **Purpose**: Learnings that weren't anticipated by the plan.

## Critical Gotchas

### 1. Test Directory Naming Shadows Packages

**Problem**: `tests/unit/research_agents/` shadows `research_agents/` package
**Symptom**: `import research_agents` resolves to test directory, not actual package
**Solution**: Use different name: `tests/unit/agent_tests/`

### 2. MCP Package Naming Conflict

**Problem**: Local `mcp/` directory conflicts with installed `mcp` package
**Symptom**: Cannot import `mcp.src.tools...` - Python finds local dir first
**Solution**:

- Put testable business logic in `research_agents/services/`
- MCP tools are thin wrappers calling service layer
- Tests import from `research_agents.services.*`, not `mcp.src.tools`

### 3. Async Mock Pattern for asyncpg

When mocking `asyncpg.Pool.acquire()` context manager:

```python
pool = MagicMock()
conn = AsyncMock()

acquire_cm = MagicMock()
acquire_cm.__aenter__ = AsyncMock(return_value=conn)
acquire_cm.__aexit__ = AsyncMock(return_value=None)
pool.acquire.return_value = acquire_cm
```

### 4. Test Timing for Async Services

**Problem**: Async service loop tests hang or are flaky with 1-second intervals
**Solution**: Use very short intervals for tests:

```python
config = TriggerConfig(interval_seconds=0.01, enabled=True)
```

## Emergent Patterns

### Service Layer Separation

Pattern that emerged: **MCP tools → Service layer → Database**

This allows unit testing without MCP server running. MCP tools are thin wrappers that call the service layer.

### AgentInvoker Protocol

Key interface in `trigger.py` that allows swapping implementations:

```python
class AgentInvoker(Protocol):
    async def invoke(self, prompt: str, system_prompt: str | None = None) -> dict:
        ...
```

`ClaudeCodeInvoker` implements this via subprocess. Future implementations could use direct API calls.
