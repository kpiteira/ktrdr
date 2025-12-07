# Phase 0: Plumbing Validation

**Objective:** Prove the basic wiring works: trigger → agent → MCP tool → database

**Duration:** 2-3 days

**Prerequisites:**
- Delete old `research_agents/` folder (contains broken legacy code)
- PostgreSQL database available

---

## Branch Strategy

**Branch:** `feature/agent-mvp`

All MVP phases (0-3) use this single branch. Create from `main` before starting Phase 0.

```bash
git checkout main
git pull
git checkout -b feature/agent-mvp
```

---

## ⚠️ Implementation Principles

**Check Before Creating:**
Before implementing any tool or service, check if similar functionality exists:
1. **Search** the codebase for existing implementations
2. **Reuse** existing patterns and utilities
3. **Enhance** existing code if close but incomplete
4. **Create new** only if nothing suitable exists

**KTRDR has extensive infrastructure:**
- Database utilities: `ktrdr/database/`
- CLI patterns: `ktrdr/cli/commands/`
- MCP tools: `mcp/src/tools/`
- Async patterns: `ktrdr/operations/`

**Leverage existing patterns** even when creating new functionality.

---

## Success Criteria

- [ ] Trigger service runs and invokes agent on schedule
- [ ] Agent can call MCP tools successfully
- [ ] Agent state persists to PostgreSQL
- [ ] End-to-end flow completes without errors
- [ ] Basic logging shows what happened

---

## Tasks

### 0.1 Create Database Tables (Minimal Set)

**Goal:** Create only the tables needed for Phase 0

**Tables to create:**
- `agent_sessions` - Track cycle state
- `agent_actions` - Log tool calls

Skip for now (Phase 3): `agent_triggers`, `agent_metrics`, `agent_budget`

**File:** `research_agents/database/schema.py`

**Acceptance:**
- Tables created via migration
- Can insert/query from Python

**Effort:** 2-3 hours

---

### 0.2 Create Agent State MCP Tools

**Goal:** Agent can read/write its own state

**Tools to implement:**

```python
@mcp.tool()
def get_agent_state(session_id: int) -> dict:
    """Get current session state"""
    
@mcp.tool()
def update_agent_state(
    session_id: int,
    phase: str,
    strategy_name: str | None = None,
    operation_id: str | None = None
) -> dict:
    """Update session state"""

@mcp.tool()
def create_agent_session() -> dict:
    """Create new session, return session_id"""
```

**File:** `mcp/src/tools/agent_tools.py`

**Acceptance:**
- Tools registered in MCP server
- Can call from Claude Code manually
- State persists to database

**Effort:** 3-4 hours

---

### 0.3 Create Basic Trigger Service

**Goal:** Service that runs on interval and invokes agent

**Simplified logic for Phase 0:**
```
every 5 minutes:
    if no active session:
        invoke agent with "start a new cycle"
    else:
        log "session active, skipping"
```

No quality gates, no budget checks yet - just the basic loop.

**File:** `research_agents/services/trigger.py`

**Configuration:**
- `AGENT_TRIGGER_INTERVAL_SECONDS=300` (5 min default)
- `AGENT_ENABLED=true/false`

**Acceptance:**
- Service starts and runs
- Invokes agent when no active session
- Logs actions clearly

**Effort:** 3-4 hours

---

### 0.4 Create Minimal Agent Prompt

**Goal:** Agent that just proves the loop works

**Simplified prompt for Phase 0:**
```
You are a test agent. Your job is to:
1. Call create_agent_session() to start
2. Call update_agent_state() to set phase to "testing"
3. Call update_agent_state() to set phase to "complete"

This proves the plumbing works.
```

No strategy design yet - just tool calling.

**File:** `research_agents/prompts/phase0_test.py`

**Acceptance:**
- Agent completes the 3-step flow
- State changes visible in database

**Effort:** 1-2 hours

---

### 0.5 Implement Agent Invocation

**Goal:** Trigger service can invoke Claude Code with MCP config

**Implementation:**
- Use subprocess to call `claude` CLI
- Pass MCP config path
- Pass prompt via stdin or file
- Capture output and exit code

**File:** `research_agents/services/invoker.py`

**Key decisions:**
- How to pass session context to agent
- How to detect success/failure
- Timeout handling

**Acceptance:**
- Can invoke agent programmatically
- Agent receives MCP tools
- Can detect when agent completes

**Effort:** 3-4 hours

---

### 0.6 Add Basic CLI Commands

**Goal:** Visibility into what's happening

**Commands for Phase 0:**
```bash
ktrdr agent status      # Show current state
ktrdr agent trigger     # Manually trigger (for testing)
```

Full CLI in Phase 3.

**File:** `ktrdr/cli/commands/agent.py` (new file, register in CLI app)

**Acceptance:**
- Commands work
- Shows useful information

**Effort:** 2 hours

---

### 0.7 End-to-End Test

**Goal:** Prove it all works together

**Test scenario:**
1. Start trigger service
2. Wait for trigger
3. Verify agent invoked
4. Verify state changes in database
5. Verify session completes

**File:** `tests/integration/research_agents/test_agent_e2e.py`

**Acceptance:**
- Test passes
- Can run manually and observe behavior

**Effort:** 2-3 hours

---

## Task Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 0.1 | Database tables | 2-3h | None |
| 0.2 | Agent state MCP tools | 3-4h | 0.1 |
| 0.3 | Basic trigger service | 3-4h | None |
| 0.4 | Minimal agent prompt | 1-2h | None |
| 0.5 | Agent invocation | 3-4h | 0.2, 0.3, 0.4 |
| 0.6 | Basic CLI | 2h | 0.1 |
| 0.7 | E2E test | 2-3h | All above |

**Total estimated effort:** 16-22 hours (2-3 days)

---

## Out of Scope for Phase 0

- Strategy generation (Phase 1)
- Training/backtest integration (Phase 2)
- Quality gates (Phase 2)
- Cost tracking (Phase 3)
- Full observability (Phase 3)
- Budget enforcement (Phase 3)

---

## Files to Create

```
research_agents/                    # Fresh start (old folder will be deleted)
├── __init__.py
├── database/
│   ├── __init__.py
│   ├── schema.py                   # 0.1 - Table definitions
│   └── queries.py                  # 0.1 - Query helpers
├── services/
│   ├── __init__.py
│   ├── trigger.py                  # 0.3 - Trigger service
│   └── invoker.py                  # 0.5 - Agent invocation
└── prompts/
    ├── __init__.py
    └── phase0_test.py              # 0.4 - Test prompt

mcp/
└── src/
    └── tools/
        └── agent_tools.py          # 0.2 - Agent state tools (new file)

ktrdr/
└── cli/
    └── commands/
        └── agent.py                # 0.6 - CLI commands (new file)

tests/
├── unit/
│   └── research_agents/            # New directory
│       └── test_agent_db.py
└── integration/
    └── research_agents/            # New directory
        └── test_agent_e2e.py       # 0.7
```

**Note:** The existing `research_agents/` folder contains old broken code and will be deleted before starting Phase 0.

---

## Definition of Done

Phase 0 is complete when:
1. Trigger service runs automatically
2. Agent is invoked and calls MCP tools
3. State persists to database
4. CLI shows current status
5. E2E test passes

Then we move to Phase 1: Strategy Design.
