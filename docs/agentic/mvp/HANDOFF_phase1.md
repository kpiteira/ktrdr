# Phase 1: Implementation Learnings

> **Purpose**: Learnings that weren't anticipated by the plan.

## Critical Gotchas

### 1. Read Phase 0 Handoff First

**Problem**: Phase 0 handoff contains a known limitation that Phase 1 should fix
**What to check**: "Session Not Visible During Invocation" section in `HANDOFF_phase0.md`

**Impact on Phase 1**:

- Task 1.1 (prompt builder): Already designed with `session_id` as required parameter
- Task 1.7 (trigger service): Must implement the fix - create session BEFORE invoking agent

The recommended flow from Phase 0:

```text
Trigger creates session → Sets phase=DESIGNING → Invokes Claude with session_id → Claude updates existing session
```

Task 1.7 must implement this pattern, not the Phase 0 pattern where Claude creates the session.

**✅ IMPLEMENTED**: Task 1.7 completed. TriggerService now:

- Creates session BEFORE invoking Claude
- Sets phase to DESIGNING immediately
- Uses strategy designer prompt with full context
- Accepts `context_provider` for testable indicator/symbol fetching
- Falls back to Phase 0 behavior when `context_provider` is None

### 2. Behavioral Acceptance Criteria Require Integration Testing

**Problem**: Task 1.1 acceptance criteria are behavioral ("agent designs coherent strategies") but unit tests only validate prompt mechanics.

**What unit tests validate**: Prompt structure, context injection, trigger reason handling.

**What requires integration**: Agent actually produces coherent designs, understands options, explains choices.

**When to validate**: End of Phase 1, after Task 1.7 (trigger service) is complete. Run manual test: trigger agent → observe strategy output → verify quality.

**✅ VALIDATED (Task 1.8)**: All behavioral acceptance criteria validated via:
- 70 unit tests covering validator, strategy service, prompt builder
- 9 E2E integration tests with MockDesignAgentInvoker
- Manual real agent test available via `AGENT_E2E_REAL_INVOKE=true`

### 3. CLI Bypasses API Layer (Phase 0 Architectural Violation)

**Problem**: Task 0.6 implemented CLI commands that directly call TriggerService instead of going through API.

**What should happen**: `CLI → API → Service` (standard KTRDR pattern)

**What Task 0.6 did**: `CLI → Service (directly)`

**Impact**:
- Cannot test E2E through the production API path
- No API endpoint exists for agent operations
- Frontend/external services can't trigger agent

**Solution**: Task 1.9 added to fix this - creates API endpoints and updates CLI.

### 4. Test File Locations Diverged from Plan

**Problem**: Plan specified `tests/unit/research_agents/` but tests ended up in `tests/unit/config/` and `tests/unit/agent_tests/`.

**Why**: Tests were created alongside implementations in their natural locations rather than in a separate `research_agents` folder.

**Actual test locations**:
- `tests/unit/config/test_strategy_validator_agent.py` - Validator unit tests
- `tests/unit/config/test_strategy_validator_feature_ids.py` - Feature ID validation
- `tests/unit/agent_tests/test_strategy_service.py` - save_strategy_config tests
- `tests/unit/agent_tests/test_get_recent_strategies.py` - Recent strategies tests
- `tests/unit/agent_tests/test_strategy_designer_prompt.py` - Prompt builder tests
- `tests/integration/agent_tests/test_agent_e2e.py` - E2E integration tests

**Impact**: None - comprehensive coverage exists, just in different locations.

## Emergent Patterns

### Prompt Builder Pattern (Task 1.1)

The prompt system uses a two-part structure matching the Phase 0 pattern:

```python
result = {"system": "...", "user": "..."}
```

**System prompt**: Static instructions that define the agent's role, available tools, and behavior guidelines. This is the same regardless of trigger reason.

**User prompt**: Dynamic context that changes based on trigger reason, session state, and available resources (indicators, symbols, recent strategies).

This separation allows:

- System prompt to be long and detailed (YAML template, design guidelines)
- User prompt to be focused on the current task with injected context
- Easy testing of context injection without testing full prompt

### Context Injection Helpers

Private methods format complex data for display:

- `_format_indicators()` - Formats indicators with descriptions and params
- `_format_symbols()` - Formats symbols with timeframes and date ranges
- `_format_recent_strategies()` - Formats strategies with outcomes for novelty

These could be reused by other prompts if needed.

### Convenience Function Pattern

`get_strategy_designer_prompt()` provides a one-call interface that:

1. Accepts string or enum for trigger_reason (auto-converts)
2. Creates PromptContext internally
3. Builds and returns the prompt dict

This simplifies integration with the trigger service.

### Strategy Validation Pattern (Task 1.2)

The validation system was enhanced (not duplicated) in `ktrdr/config/strategy_validator.py`:

**Key Methods for Agent Use:**

- `validate_strategy_config(config_dict)` - Main entry point for agent-generated configs
- `check_strategy_name_unique(name, strategies_dir)` - Pre-save duplicate check

**Agent-Specific Validations Added:**

- Indicator type existence (checked against `BUILT_IN_INDICATORS`)
- Fuzzy membership param counts (triangular=3, trapezoid=4, etc.)
- Helpful error messages with suggestions (e.g., typo corrections)

**Integration Point for Task 1.3:**

```python
from ktrdr.config.strategy_validator import StrategyValidator

validator = StrategyValidator()
result = validator.validate_strategy_config(config)
if not result.is_valid:
    return {"success": False, "errors": result.errors, "suggestions": result.suggestions}
```

### Strategy Save Pattern (Task 1.3)

The save_strategy_config tool follows the Phase 0 service layer pattern:

```text
MCP Tool (mcp/src/tools/strategy_tools.py)
    ↓
Service Layer (research_agents/services/strategy_service.py)
    ↓
StrategyValidator (ktrdr/config/strategy_validator.py)
```

**Key Design Decisions:**

- Tool uses `strategies_dir` parameter with default `"strategies"` for testability
- Name parameter takes precedence over config's internal name field
- Creates directory if it doesn't exist (agent-friendly)
- Returns absolute path on success for clear feedback

**Integration with Agent:**

Agent uses save_strategy_config after designing:

```yaml
# In strategy_designer.py prompt:
After designing your strategy configuration:
1. Call save_strategy_config(name, config, description)
2. If errors returned, fix the config and retry
3. On success, note the path for training
```

### Existing MCP Tools Found (Tasks 1.5-1.6)

Both indicator and symbol tools already exist in `mcp/src/server.py`:

- `get_available_indicators()` - Line 259, returns 30 indicators with params
- `get_available_symbols()` - Line 86, returns 32 symbols with `available_timeframes`
- `get_data_summary(symbol, timeframe)` - Line 188, returns date ranges for train/test splits

**Agent Data Discovery Workflow:**

```text
1. get_available_symbols() → symbols with available_timeframes
2. get_data_summary(symbol, tf) → start_date, end_date, point_count
```

**No new tools needed** - existing tools provide all required capabilities.

### Trigger Service Design Phase Pattern (Task 1.7)

The trigger service implements a "session first" pattern for the design phase:

```python
# 1. Create session BEFORE invoking Claude
session = await self.db.create_session()

# 2. Set phase to DESIGNING immediately
await self.db.update_session(session_id=session.id, phase=SessionPhase.DESIGNING)

# 3. Fetch context data
indicators = await self.context_provider.get_available_indicators()
symbols = await self.context_provider.get_available_symbols()
recent_sessions = await self.db.get_recent_completed_sessions()

# 4. Build strategy designer prompt with full context
prompts = get_strategy_designer_prompt(
    trigger_reason=TriggerReason.START_NEW_CYCLE,
    session_id=session.id,
    phase="designing",
    available_indicators=indicators,
    available_symbols=symbols,
    recent_strategies=recent_strategies,
)

# 5. Invoke agent
result = await self.invoker.invoke(prompt=prompts["user"], system_prompt=prompts["system"])
```

**Key Design Decisions:**

- `ContextProvider` protocol enables testable context fetching (mock in tests, API client in production)
- Falls back to Phase 0 behavior when `context_provider` is None (backward compatibility)
- Marks session as `FAILED_DESIGN` on invocation errors (clean failure handling)
- Agent is responsible for transitioning to DESIGNED phase when complete

### Get Recent Strategies Pattern (Task 1.4)

The get_recent_strategies tool uses a hybrid data source pattern:

```text
Database (agent_sessions)     Strategy Files (strategies/*.yaml)
       │                              │
       └──────────┬───────────────────┘
                  ▼
      get_recent_strategies()
                  │
                  ▼
    [{name, type, indicators, outcome, created_at}]
```

**Why Hybrid:**

- Database has session metadata (outcome, created_at)
- YAML files have strategy details (model.type, indicators)
- Avoids schema changes to store full config in sessions table

**Key Design Decisions:**

- Graceful degradation: missing/corrupt YAML returns null for type/indicators
- Sessions without strategy_name are filtered out (e.g., failed_design)
- Order preserved from database (most recent first)
- `strategies_dir` parameter for testability (same pattern as save)

### E2E Testing Pattern (After Task 1.7)

The Phase 1 E2E tests use `MockDesignAgentInvoker` to simulate Claude designing a strategy:

```python
class MockDesignAgentInvoker:
    """Simulates Claude designing a strategy."""

    async def invoke(self, prompt, system_prompt):
        # 1. Extract session_id from prompt
        session_id = int(re.search(r"Session ID:\s*(\d+)", prompt).group(1))

        # 2. Create valid strategy config
        strategy_config = {...}

        # 3. Save via strategy service
        await save_strategy_config(name, strategy_config, description, strategies_dir)

        # 4. Update session to DESIGNED
        await db.update_session(session_id, phase=SessionPhase.DESIGNED, strategy_name=name)
```

**Schema Addition:**

Added `SessionPhase.DESIGNED` to mark design completion (Phase 1 end state):

```python
class SessionPhase(str, Enum):
    IDLE = "idle"
    DESIGNING = "designing"
    DESIGNED = "designed"  # NEW: Design complete, ready for training
    TRAINING = "training"
    ...
```

**Database Credentials (Local):**

```bash
DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr"
```

**Running E2E Tests:**

```bash
export DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr"
uv run pytest tests/integration/agent_tests/test_agent_e2e.py::TestAgentDesignPhaseE2E -v
```

### Agent API & Anthropic Integration Pattern (Task 1.9)

The Agent API follows standard KTRDR patterns with API-based CLI:

```text
CLI (agent_commands.py)
    ↓ AsyncCLIClient
API Endpoints (agent.py)
    ↓
Agent Service (agent_service.py)
    ↓
TriggerService / AgentDatabase
```

**CLI to API Migration:**

The CLI now uses `AsyncCLIClient` instead of direct service calls:

```python
async with AsyncCLIClient() as client:
    result = await client._make_request("POST", "/agent/trigger", params={"dry_run": dry_run})
```

**AnthropicAgentInvoker Pattern:**

The invoker implements an agentic loop with tool support:

```python
class AnthropicAgentInvoker:
    async def run(self, prompt, tools, system_prompt, tool_executor):
        while True:
            response = await asyncio.to_thread(self._create_message, ...)
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                return AgentResult(output=self._extract_text(response.content), ...)
            # Execute tools and continue loop
            tool_results = await self._execute_tools(tool_calls, tool_executor)
            messages.append({"role": "user", "content": tool_results})
```

**Token Tracking:**

Tokens are accumulated across all API calls in the loop:

```python
total_input_tokens += response.usage.input_tokens
total_output_tokens += response.usage.output_tokens
```

**API Context Provider:**

`AgentMCPContextProvider` fetches indicators/symbols from local API (not MCP):

```python
async def get_available_indicators(self):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{self.base_url}/indicators/available")
        return response.json().get("indicators", [])
```

This enables testability via mock API responses.
