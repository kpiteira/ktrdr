# Phase 1: Strategy Design Only

**Objective:** Agent can design valid neuro-fuzzy strategy configurations

**Duration:** 2-3 days

**Prerequisites:** Phase 0 complete (plumbing works)

---

## ⚠️ Architecture Update (Anthropic API Direct Integration)

**Decision:** Use Anthropic Python SDK directly instead of Claude Code CLI.

See [ARCHITECTURE_DECISION_anthropic_api.md](ARCHITECTURE_DECISION_anthropic_api.md) for full context.

**Key Changes:**
- ❌ No Claude Code CLI (Node.js dependency, subprocess)
- ❌ No agent-host-service (runs in backend)
- ❌ No MCP protocol for agent (tools execute in-process)
- ✅ Anthropic Python SDK (`uv add anthropic`)
- ✅ Agent runs in backend Docker container
- ✅ Tools execute directly via ToolExecutor

```text
┌─────────────────────────────────────────────────────────────────┐
│ Backend (Docker Container, Port 8000)                          │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Agent API   │───▶│ AnthropicInvoker │───▶│ Tool Executor │  │
│  │ /agent/*    │    │ (Python SDK)     │    │ (internal)    │  │
│  └─────────────┘    └──────────────────┘    └───────────────┘  │
│                                                                 │
│  • No host service needed                                       │
│  • No Node.js/Claude CLI needed                                 │
│  • Tools execute in-process                                     │
│  • Full observability control                                   │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTPS (api.anthropic.com)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Anthropic API                                │
│  • Claude Sonnet/Opus models                                     │
│  • Tool use (function calling)                                  │
│  • Token counting                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Branch Strategy

**Branch:** `feature/agent-mvp`

Continue on the same branch from Phase 0. All MVP phases (0-3) use this single branch.

---

## ⚠️ Implementation Principles

**Check Before Creating:**
For ANY functionality that might already exist in KTRDR:
1. **Search** the codebase for existing implementations
2. **Review** if existing code covers requirements
3. **Enhance** existing code if gaps found
4. **Create new** only if nothing suitable exists

**Why:** KTRDR is a mature codebase with validation, CLI commands, MCP tools. Duplicating functionality creates maintenance burden and inconsistency.

**Known Existing Systems to Check:**
- `ktrdr/validation/` - validation framework
- `ktrdr/cli/commands/strategies.py` - strategy CLI commands
- `mcp/src/tools/` - existing MCP tools
- `ktrdr/indicators/` - indicator registry
- `ktrdr/config/` - configuration parsing

---

## Success Criteria

- [ ] Agent generates valid YAML strategy configurations
- [ ] Strategies use available indicators and symbols
- [ ] Agent avoids repeating recent strategies
- [ ] Generated strategies pass KTRDR validation
- [ ] Strategies saved to `strategies/` folder

---

## Tasks

### 1.1 Implement Full Agent Prompt

**Goal:** Replace Phase 0 test prompt with real strategy design prompt

**Prompt must include:**
- Role: Autonomous neuro-fuzzy strategy researcher
- Available indicators (injected from KTRDR)
- Available symbols and timeframes
- Strategy configuration format
- Instructions for novelty and experimentation

**Context injection:**
- Recent strategies (last 5) to avoid repetition
- Current session state
- Trigger reason

**File:** `research_agents/prompts/strategy_designer.py`

**Reference:** See `ref_agent_prompt.md` for full prompt specification

**Acceptance:**
- Prompt generates coherent strategy designs
- Agent understands available options
- Agent explains its design choices

**Effort:** 3-4 hours

---

### 1.2 Strategy Validation (Check-First)

**⚠️ IMPORTANT:** Check existing code before implementing!

**Step 1: Inventory existing validation**
- [ ] Review `ktrdr/validation/` module
- [ ] Review `ktrdr/cli/commands/strategies.py` (validate command)
- [ ] Check for existing strategy schema/config classes
- [ ] Document what already exists

**Step 2: Gap analysis against requirements**

| Requirement | Check If Exists | If Missing |
|-------------|-----------------|------------|
| YAML syntax validation | ? | Enhance existing |
| Required fields check | ? | Enhance existing |
| Indicators exist in KTRDR | ? | Enhance existing |
| Symbols have available data | ? | Enhance existing |
| Fuzzy membership functions valid | ? | Enhance existing |
| No duplicate strategy names | ? | Enhance existing |

**Step 3: Enhance existing OR create wrapper**
- If 80%+ exists: enhance `ktrdr/validation/`
- If major gaps: create thin wrapper in `research_agents/validation/` that calls existing code + adds missing checks

**DO NOT** create parallel validation system - extend what exists!

**Files to Check:**
- `ktrdr/validation/*.py`
- `ktrdr/cli/commands/strategies.py`
- `ktrdr/config/*.py` (strategy config parsing)

**Files to Modify (if gaps found):**
- Existing `ktrdr/validation/` module (preferred)
- OR wrapper at `research_agents/validation/strategy_validator.py`

**Acceptance:**
- Valid strategies pass
- Invalid strategies return clear error messages
- Error messages help agent fix issues
- **No duplicate code** with existing validation

**Effort:** 3-4 hours (includes investigation)

---

### 1.3 Implement save_strategy_config MCP Tool

**Goal:** Agent can save validated strategy to disk

**Tool signature:**
```python
@mcp.tool()
def save_strategy_config(
    name: str,
    config: dict,
    description: str
) -> dict:
    """
    Validate and save strategy configuration.
    Returns: {success: bool, path: str, errors: list}
    """
```

**Behavior:**
1. Validate config (Task 1.2)
2. If valid, save to `strategies/{name}.yaml`
3. Return result with path or errors

**File:** `mcp/src/tools/strategy_tools.py`

**Acceptance:**
- Tool saves valid strategies
- Tool rejects invalid strategies with clear errors
- Files appear in strategies folder

**Effort:** 2-3 hours

---

### 1.4 Implement get_recent_strategies MCP Tool

**Goal:** Agent can see what it recently tried

**Tool signature:**
```python
@mcp.tool()
def get_recent_strategies(n: int = 5) -> list[dict]:
    """
    Get last N strategies designed by agent.
    Returns: [{name, type, indicators, outcome, created_at}]
    """
```

**Data source:** Query `agent_sessions` table for recent completed sessions

**File:** `mcp/src/tools/strategy_tools.py`

**Acceptance:**
- Returns recent strategies with key details
- Helps agent avoid repetition

**Effort:** 1-2 hours

---

### 1.5 get_available_indicators MCP Tool (Check-First) ✅ DONE

**Status:** Existing tool at `mcp/src/server.py:259` meets all requirements (30 indicators with params).

**⚠️ CHECK FIRST:** This likely exists in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "available_indicators\|get_indicators" mcp/src/tools/
```

**Step 2: If exists, verify it returns:**
- All 26+ indicators
- Parameter specifications (name, type, default, range)
- Category information
- Description

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/indicator_tools.py`

**DO NOT** create duplicate tool if one exists!

**Acceptance:**
- Returns all 26+ indicators
- Includes parameter specifications
- Agent can use this to design valid configs

**Effort:** 0-2 hours (depends on what exists)

---

### 1.6 get_available_symbols MCP Tool (Check-First) ✅ DONE

**Status:** Existing tools meet all requirements:

- `get_available_symbols()` at line 86 (32 symbols with timeframes)
- `get_data_summary()` at line 188 (date ranges for splits)

**⚠️ CHECK FIRST:** This likely exists in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "available_symbols\|get_symbols" mcp/src/tools/
```

**Step 2: If exists, verify it returns:**
- All available symbols (EURUSD, GBPUSD, etc.)
- Available timeframes per symbol
- Data date ranges

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/data_tools.py`

**DO NOT** create duplicate tool if one exists!

**Acceptance:**
- Returns symbols with available timeframes
- Includes date ranges for data
- Agent can plan train/test splits

**Effort:** 0-2 hours (depends on what exists)

---

### 1.7 Update Trigger Service for Design Phase ✅ DONE

**Status:** Implemented "session first" pattern - trigger creates session before invoking Claude.

**Goal:** Trigger invokes agent for strategy design

**Updates:**
- Check if session is in IDLE state
- Invoke agent with design context
- Handle design completion (agent sets phase to DESIGNED)

**State flow:**
```
IDLE → (trigger invokes agent) → DESIGNING → (agent completes) → DESIGNED
```

For Phase 1, we stop at DESIGNED. Phase 2 adds training.

**File:** `research_agents/services/trigger.py`

**Acceptance:**
- Agent invoked when IDLE
- Session transitions to DESIGNING
- Session transitions to DESIGNED when complete

**Effort:** 2-3 hours

---

### 1.8 Strategy Design Tests & Behavioral Validation ✅ DONE

**Status:** All tests exist and pass. Test files at different locations than planned (documented in handoff).

**Goal:** Verify agent designs valid strategies AND validate behavioral acceptance criteria from earlier tasks

**Why this task exists:** Tasks 1.1, 1.3, 1.4 have behavioral acceptance criteria ("agent designs coherent strategies", "agent understands options") that cannot be unit tested - they require actual agent invocation. This task is where those criteria are validated.

**Unit test cases:**

1. Strategy validator rejects invalid YAML
2. Strategy validator rejects missing required fields
3. Strategy validator rejects unknown indicators
4. Strategy validator provides helpful error messages

**Integration/behavioral test cases:**

1. Agent generates valid YAML (Task 1.1 behavioral)
2. Agent uses available indicators correctly (Task 1.1 behavioral)
3. Agent uses available symbols correctly (Task 1.1 behavioral)
4. Agent avoids recent strategy patterns (Task 1.1 behavioral)
5. Agent explains design choices (Task 1.1 behavioral)
6. save_strategy_config saves valid strategies (Task 1.3 behavioral)
7. get_recent_strategies returns useful context (Task 1.4 behavioral)

**Files:**

- `tests/unit/research_agents/test_strategy_validator.py`
- `tests/integration/research_agents/test_strategy_design.py`

**Acceptance:**

- Unit tests for validator pass
- Integration test invokes agent and observes real output
- All behavioral acceptance criteria from Tasks 1.1, 1.3, 1.4 validated
- Agent produces coherent, valid strategy designs

**Effort:** 4-5 hours (increased to account for behavioral validation)

---

### 1.9 Agent API & Anthropic Integration

**Status:** ✅ DONE

**Goal:** Create Agent API endpoints and implement Anthropic SDK integration

**What this replaces:** This task now includes the Anthropic integration work that was previously split across host service tasks. The agent runs entirely within the backend.

**Components:**

1. **Agent API Endpoints** (`ktrdr/api/endpoints/agent.py`):
   - `POST /api/v1/agent/trigger` - Trigger research cycle
   - `GET /api/v1/agent/status` - Get current status
   - `GET /api/v1/agent/sessions` - List recent sessions

2. **AnthropicAgentInvoker** (`ktrdr/agents/invoker.py`):

```python
import anthropic

class AnthropicAgentInvoker:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY
        self.model = model

    async def run(self, prompt: str, tools: list[dict], system_prompt: str) -> AgentResult:
        messages = [{"role": "user", "content": prompt}]
        total_input_tokens = 0
        total_output_tokens = 0

        while True:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                break  # Done - no more tools

            # Execute tools and continue loop
            messages.append({"role": "assistant", "content": response.content})
            tool_results = await self._execute_tools(tool_calls)
            messages.append({"role": "user", "content": tool_results})

        return AgentResult(
            success=True,
            output=self._extract_text(response),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens
        )
```

**Agent API Service** (`ktrdr/api/services/agent_service.py`):

- Wraps TriggerService for API consumption
- Handles context provider injection
- Returns API-friendly responses

**Update CLI** (`ktrdr/cli/agent_commands.py`):

- Remove direct TriggerService instantiation
- Use `AsyncCLIClient` to call API endpoints
- Follow pattern from other CLI commands

**Add Anthropic dependency**:

- `uv add anthropic`

**Files:**

- `ktrdr/agents/__init__.py` - NEW: Agent module
- `ktrdr/agents/invoker.py` - NEW: AnthropicAgentInvoker
- `ktrdr/api/endpoints/agent.py` - NEW: API endpoints
- `ktrdr/api/services/agent_service.py` - NEW: API service layer
- `ktrdr/api/models/agent.py` - NEW: Request/response models
- `ktrdr/cli/agent_commands.py` - MODIFY: Use API instead of direct service
- `ktrdr/api/endpoints/__init__.py` - MODIFY: Register agent router
- `pyproject.toml` - MODIFY: Add anthropic dependency

**Acceptance:**

- `POST /api/v1/agent/trigger` endpoint works
- `GET /api/v1/agent/status` endpoint works
- AnthropicAgentInvoker calls Anthropic API correctly
- Token counts captured from API response
- CLI `ktrdr agent trigger` calls API (not direct service)
- CLI `ktrdr agent status` calls API (not direct service)

**Effort:** 4-5 hours

---

### 1.10 Background Trigger Loop

**Status:** ✅ DONE

**Goal:** Integrate trigger service as a background task in the backend

**Implementation:**

The trigger service runs as a background asyncio task in the backend:

```python
# In backend startup (ktrdr/api/main.py)

async def start_agent_trigger_loop():
    """Background task that runs the trigger service."""
    trigger_service = TriggerService(
        config=TriggerConfig.from_env(),
        invoker=AnthropicAgentInvoker(),
        db=AgentDatabase(),
        tool_executor=ToolExecutor()
    )
    await trigger_service.start()  # Runs every 5 minutes

@app.on_event("startup")
async def startup():
    if os.getenv("AGENT_ENABLED", "false").lower() == "true":
        asyncio.create_task(start_agent_trigger_loop())
```

**Configuration:**

```bash
AGENT_ENABLED=true                    # Enable background trigger loop
AGENT_TRIGGER_INTERVAL_SECONDS=300    # 5 minutes
AGENT_MODEL=claude-sonnet-4-20250514  # Or claude-opus-4-20250514
```

**Components:**

1. **Update TriggerService** to work with new invoker:
   - Accept `AnthropicAgentInvoker` instead of `ClaudeCodeInvoker`
   - Accept `ToolExecutor` for tool execution
   - Remove subprocess/MCP dependencies

2. **Backend startup integration**:
   - Add startup event handler
   - Conditional on `AGENT_ENABLED` env var
   - Graceful shutdown handling

**Files:**

- `ktrdr/api/main.py` - MODIFY: Add startup event for trigger loop
- `research_agents/services/trigger.py` - MODIFY: Update for new invoker pattern

**Acceptance:**

- Background loop starts when `AGENT_ENABLED=true`
- Loop triggers every 5 minutes (configurable)
- Graceful shutdown on backend stop
- Manual trigger via API still works

**Effort:** 2-3 hours

---

### 1.11 Tool Definitions & Executor

**Status:** TODO

**Goal:** Define tool schemas for Anthropic API and implement ToolExecutor

**What this replaces:** MCP tools are no longer used for the agent. Instead, tools are defined as Anthropic tool schemas and executed locally.

**Tool Definitions** (`ktrdr/agents/tools.py`):

```python
AGENT_TOOLS = [
    {
        "name": "save_strategy_config",
        "description": "Save a strategy configuration to the strategies directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Strategy name"},
                "config": {"type": "object", "description": "Strategy configuration"}
            },
            "required": ["name", "config"]
        }
    },
    {
        "name": "get_available_indicators",
        "description": "Get list of available technical indicators with parameters",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_available_symbols",
        "description": "Get list of available trading symbols with timeframes",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_recent_strategies",
        "description": "Get recently designed strategies to avoid repetition",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number of strategies", "default": 5}
            }
        }
    }
]
```

**Tool Executor** (`ktrdr/agents/executor.py`):

```python
class ToolExecutor:
    def __init__(self, db: AgentDatabase):
        self.db = db
        self.handlers = {
            "save_strategy_config": self._save_strategy_config,
            "get_available_indicators": self._get_available_indicators,
            "get_available_symbols": self._get_available_symbols,
            "get_recent_strategies": self._get_recent_strategies,
        }

    async def execute(self, tool_name: str, tool_input: dict) -> dict:
        handler = self.handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        return await handler(**tool_input)
```

**Implementation Notes:**

- Reuse logic from existing MCP tools (`mcp/src/tools/`)
- Tools execute in the same process as the agent (no protocol overhead)
- Direct access to KTRDR services (indicators, data, etc.)

**Files:**

- `ktrdr/agents/tools.py` - NEW: Tool schema definitions
- `ktrdr/agents/executor.py` - NEW: ToolExecutor implementation

**Acceptance:**

- All required tools defined with proper schemas
- ToolExecutor handles all tool calls
- Tools reuse existing KTRDR logic
- Unit tests for tool execution

**Effort:** 3-4 hours

---

### 1.12 End-to-End Integration Test (Real Agent)

**Status:** TODO

**Goal:** Verify the complete agent system works end-to-end with real Anthropic API invocation

**Test Scenario:**

```text
1. Start services:
   - Backend (Docker) with AGENT_ENABLED=true
   - PostgreSQL

2. Trigger via CLI:
   ktrdr agent trigger

3. Verify:
   - Session created in database
   - Anthropic API called with correct prompt
   - Tools executed correctly
   - Strategy YAML saved to disk
   - Session updated to DESIGNED
   - Strategy validates correctly
```

**What This Tests:**

- CLI → API communication
- API → AnthropicAgentInvoker
- Anthropic API → Tool calls
- ToolExecutor → KTRDR services
- Strategy validation
- Full Phase 1 design flow

**Simplified Architecture (vs old plan):**

- No host service to start
- No MCP server needed for agent
- Single service (backend) handles everything

**Files:**

- `tests/integration/agent_tests/test_agent_real_e2e.py` - NEW: Real E2E test
- `docs/testing/AGENT_E2E_TESTING.md` - NEW: E2E testing guide

**Acceptance:**

- E2E test passes with real Anthropic API invocation
- Strategy file created in `strategies/`
- Strategy passes validation
- Session in DESIGNED state with strategy_name
- Token counts captured and logged
- Can run manually with clear instructions

**Effort:** 2-3 hours

---

## Task Summary

| Task | Description | Effort | Dependencies | Status |
|------|-------------|--------|--------------|--------|
| 1.1 | Full agent prompt | 3-4h | Phase 0 | ✅ Done |
| 1.2 | Strategy validation (check-first) | 2-4h | Review existing | ✅ Done |
| 1.3 | save_strategy_config tool | 2-3h | 1.2 | ✅ Done |
| 1.4 | get_recent_strategies tool | 1-2h | Phase 0 | ✅ Done |
| 1.5 | get_available_indicators (check-first) | 0-2h | Check if exists | ✅ Done |
| 1.6 | get_available_symbols (check-first) | 0-2h | Check if exists | ✅ Done |
| 1.7 | Trigger service updates | 2-3h | 1.1, 1.3 | ✅ Done |
| 1.8 | Tests & behavioral validation | 4-5h | All above | ✅ Done |
| 1.9 | Agent API & Anthropic Integration | 4-5h | 1.8 | ✅ Done |
| 1.10 | Background Trigger Loop | 2-3h | 1.9 | ✅ Done |
| 1.11 | Tool Definitions & Executor | 3-4h | 1.9 | **TODO** |
| 1.12 | Real E2E Integration Test | 2-3h | 1.10, 1.11 | **TODO** |

**Total estimated effort:** 26-38 hours (3-4 days)

**Critical Path:** 1.9 → 1.10/1.11 (parallel) → 1.12

*Note: Tasks 1.9-1.12 updated for Anthropic API architecture. See [ARCHITECTURE_DECISION_anthropic_api.md](ARCHITECTURE_DECISION_anthropic_api.md).*

---

## Out of Scope for Phase 1

- Starting training (Phase 2)
- Running backtests (Phase 2)
- Quality gates (Phase 2)
- Cost tracking (Phase 3)
- Observability (Phase 3)

---

## Files to Create/Modify

**Note:** Architecture updated to use Anthropic API directly. MCP tools still exist but are not used by the agent.

```text
ktrdr/
├── agents/                          # NEW: Agent module
│   ├── __init__.py                  # 1.9 - NEW
│   ├── invoker.py                   # 1.9 - NEW: AnthropicAgentInvoker
│   ├── tools.py                     # 1.11 - NEW: Tool schema definitions
│   └── executor.py                  # 1.11 - NEW: ToolExecutor
├── api/
│   ├── endpoints/
│   │   └── agent.py                 # 1.9 - NEW: Agent API endpoints
│   ├── services/
│   │   └── agent_service.py         # 1.9 - NEW: Agent API service
│   ├── models/
│   │   └── agent.py                 # 1.9 - NEW: Request/response models
│   └── main.py                      # 1.10 - MODIFY: Add startup event
└── cli/
    └── agent_commands.py            # 1.9 - MODIFY: Use API

research_agents/
├── prompts/
│   └── strategy_designer.py         # 1.1 - DONE
├── validation/                      # 1.2 - DONE
│   └── strategy_validator.py
└── services/
    └── trigger.py                   # 1.10 - MODIFY: Update for new invoker

tests/
├── unit/
│   └── agents/
│       └── test_tool_executor.py    # 1.11 - NEW
└── integration/
    └── agent_tests/
        └── test_agent_real_e2e.py   # 1.12 - NEW

pyproject.toml                       # 1.9 - MODIFY: Add anthropic dependency
```

**No longer needed (for agent):**

- `agent-host-service/` - Agent runs in backend
- MCP protocol for agent - Tools execute in-process

---

## Example Generated Strategy

After Phase 1, the agent should produce strategies matching KTRDR's actual format.

**Reference:** See `strategies/neuro_mean_reversion.yaml` for the canonical format.

```yaml
# === STRATEGY IDENTITY ===
name: "momentum_crossover_v1"
description: "RSI divergence with MACD confirmation for trend entries on EURUSD"
version: "1.0"
hypothesis: "RSI divergence combined with MACD crossover confirmation
  creates higher-probability trend entry signals"

# === STRATEGY SCOPE ===
scope: "universal"

# === TRAINING APPROACH ===
training_data:
  symbols:
    mode: "single_symbol"
    list:
      - "EURUSD"
  timeframes:
    mode: "single_timeframe"
    list:
      - "1h"
    base_timeframe: "1h"
  history_required: 200

# === DEPLOYMENT TARGETS ===
deployment:
  target_symbols:
    mode: "same_as_training"
  target_timeframes:
    mode: "single_timeframe"
    supported:
      - "1h"

# === TECHNICAL INDICATORS ===
indicators:
  - name: "rsi"
    feature_id: rsi_14
    period: 14
    source: "close"
  - name: "macd"
    feature_id: macd_12_26_9
    fast_period: 12
    slow_period: 26
    signal_period: 9
    source: "close"

# === FUZZY LOGIC CONFIGURATION ===
fuzzy_sets:
  rsi_14:
    oversold:
      type: "triangular"
      parameters: [0, 20, 35]
    neutral:
      type: "triangular"
      parameters: [30, 50, 70]
    overbought:
      type: "triangular"
      parameters: [65, 80, 100]

# === NEURAL NETWORK MODEL ===
model:
  type: "mlp"
  architecture:
    hidden_layers: [32, 16]
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  features:
    include_price_context: false
    lookback_periods: 2
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 50
    optimizer: "adam"

# === DECISION LOGIC ===
decisions:
  output_format: "classification"
  confidence_threshold: 0.6
  position_awareness: true
  filters:
    min_signal_separation: 4
    volume_filter: false

# === TRAINING CONFIGURATION ===
training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.03
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

**Key format requirements:**
- Use `training_data.symbols` not top-level `symbols`
- Use `fuzzy_sets` not `fuzzy_config`
- Use `parameters` not `params` for fuzzy membership
- Include `feature_id` for each indicator
- Include full `model`, `decisions`, and `training` blocks

---

## Definition of Done

Phase 1 is complete when:
1. Agent designs novel strategy configurations
2. Strategies pass validation
3. Strategies save to disk
4. Agent avoids recent patterns
5. Tests pass

Then we move to Phase 2: Full Research Cycle.
