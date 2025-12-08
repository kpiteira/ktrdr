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

### E2E Integration Test Pattern (Task 0.7)

E2E tests for the agent system use a `MockAgentInvoker` that simulates Claude's behavior:

```python
class MockAgentInvoker:
    """Simulates agent behavior for E2E testing."""

    def __init__(self, db: AgentDatabase):
        self.db = db

    async def invoke(self, prompt, system_prompt=None, session_context=None):
        # Simulate agent workflow:
        session = await self.db.create_session()
        await self.db.update_session(session_id=session.id, phase=SessionPhase.DESIGNING)
        await self.db.complete_session(session_id=session.id, outcome=SessionOutcome.SUCCESS)
        return InvocationResult(success=True, ...)
```

This allows testing the full trigger → agent → database flow without invoking Claude.

### Async Fixture Pattern for pytest

Use `@pytest_asyncio.fixture` (not `@pytest.fixture`) for async fixtures:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def agent_db():
    db = AgentDatabase()
    try:
        await db.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")
    yield db
    await db.disconnect()
```

The `pytest.skip()` in fixture setup allows graceful skipping when database is unavailable.

## Known Limitations (Phase 1+ Improvements)

### Session Not Visible During Invocation

**Problem**: In Phase 0, Claude creates the session via MCP tool. During the ~90 second invocation, `agent status` shows "No active session" because no session exists yet.

**Current flow**:

```text
Trigger starts → Invokes Claude (90s) → Claude calls create_agent_session() → Session exists
                 ^                       ^
                 No session visible      Session only created here
```

**Recommended fix for Phase 1**:

```text
Trigger creates session → Sets phase=DESIGNING → Invokes Claude with session_id → Claude updates existing session
```

This requires:

1. Trigger creates session BEFORE invoking Claude
2. Session ID passed to Claude in prompt context
3. Agent prompt updated to use existing session (not create new)
4. Phase immediately set to DESIGNING so `agent status` shows work in progress

**Impact**: Currently minor (Phase 0 is just proving plumbing). Should be addressed when building real workflow in Phase 1.
