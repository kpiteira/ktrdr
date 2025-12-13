# Architecture Decision: Anthropic API Direct Integration

**Date:** 2024-12-09
**Status:** APPROVED - Ready to implement
**Decision:** Use Anthropic Python SDK directly instead of Claude Code CLI

---

## Context

During Phase 1 planning, we discovered several architectural issues:

1. **CLI bypassed API layer** (Task 0.6 violation)
2. **Claude Code CLI not available in Docker** (Node.js dependency)
3. **Host service pattern adds complexity** (another service to manage)

We evaluated alternatives and decided on using the Anthropic Python SDK directly.

---

## Decision Summary

### Before (Claude Code CLI)

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ TriggerSvc  │───▶│ Claude CLI   │───▶│ MCP Server  │
│ (host svc)  │    │ (subprocess) │    │ (protocol)  │
└─────────────┘    └──────────────┘    └─────────────┘
     │
     │ Requires: Node.js, host service, MCP protocol
```

### After (Anthropic API)

```
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
```

---

## Key Architectural Points

### 1. Anthropic SDK Integration

```python
# Add via: uv add anthropic

import anthropic

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

response = client.messages.create(
    model="claude-sonnet-4-20250514",  # Or claude-opus-4-20250514
    max_tokens=4096,
    tools=tools,  # Tool definitions with schemas
    messages=messages
)
```

### 2. Agentic Loop Pattern

The agent runs in a loop until Claude is done:

```python
class AnthropicAgentInvoker:
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

            # Track tokens
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Check for tool calls
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if not tool_calls:
                # No more tools - extract final response
                break

            # Execute tools and continue
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

### 3. Tool Definition Format

Tools are defined as Anthropic tool schemas (not MCP):

```python
AGENT_TOOLS = [
    {
        "name": "save_strategy_config",
        "description": "Save a strategy configuration to the strategies directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Strategy name (will be used as filename)"
                },
                "config": {
                    "type": "object",
                    "description": "Full strategy configuration"
                }
            },
            "required": ["name", "config"]
        }
    },
    {
        "name": "get_available_indicators",
        "description": "Get list of available technical indicators",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    # ... etc
]
```

### 4. Tool Execution

Tools are executed locally in Python (no MCP server needed):

```python
class ToolExecutor:
    def __init__(self, db: AgentDatabase):
        self.db = db
        self.handlers = {
            "save_strategy_config": self._save_strategy_config,
            "get_available_indicators": self._get_available_indicators,
            "get_available_symbols": self._get_available_symbols,
            "get_recent_strategies": self._get_recent_strategies,
            "start_training": self._start_training,
            "start_backtest": self._start_backtest,
        }

    async def execute(self, tool_name: str, tool_input: dict) -> dict:
        handler = self.handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        return await handler(**tool_input)

    async def _save_strategy_config(self, name: str, config: dict) -> dict:
        # Reuse existing implementation from mcp/src/tools/strategy_tools.py
        ...
```

### 5. What Happens to MCP?

**MCP server is NO LONGER NEEDED for the agent system.**

The MCP tools (`mcp/src/tools/`) contain the implementation logic. We will:
1. Keep the implementation logic
2. Expose it via the ToolExecutor (not MCP protocol)
3. The MCP server can remain for other uses (Claude Desktop, etc.) but is not required for the autonomous agent

### 6. Background Trigger Loop

The trigger service runs as a background task in the backend:

```python
# In backend startup (ktrdr/api/main.py or similar)

async def start_agent_trigger_loop():
    """Background task that runs the trigger service."""
    trigger_service = TriggerService(
        config=TriggerConfig.from_env(),
        invoker=AnthropicAgentInvoker(),
        db=AgentDatabase(),
        tool_executor=ToolExecutor()
    )
    await trigger_service.start()  # Runs every 5 minutes

# Start on backend boot
@app.on_event("startup")
async def startup():
    if os.getenv("AGENT_ENABLED", "false").lower() == "true":
        asyncio.create_task(start_agent_trigger_loop())
```

---

## Changes Required to Plans

### Phase 1 Changes

**Remove:**
- Task 1.10: Agent Host Service - NO LONGER NEEDED
- Task 1.11: MCP Server Configuration - NO LONGER NEEDED (for agent)

**Update:**
- Task 1.9: Rename to "Agent API & Anthropic Integration"
  - Create API endpoints (`/api/v1/agent/*`)
  - Implement `AnthropicAgentInvoker` class
  - Implement `ToolExecutor` class
  - Fix CLI to use API
  - Add `anthropic` package dependency

**Add:**
- Task 1.10 (new): Background Trigger Loop
  - Integrate trigger service into backend startup
  - Configurable via `AGENT_ENABLED` env var
  - Runs every 5 minutes when enabled

- Task 1.11 (new): Tool Definitions & Executor
  - Define tool schemas for Anthropic API
  - Implement ToolExecutor with all required tools
  - Reuse logic from MCP tool implementations

- Task 1.12: Real E2E Integration Test (keep, update for new architecture)

### Phase 2 Changes

**Update architectural context:**
- Remove agent-host-service references
- TriggerService runs IN backend (not separate service)
- Tools execute in-process (not via MCP)
- Operation status checked directly (same process)

**Update Task 2.5:**
- No polling needed - operations service is in same process
- Simpler state machine integration

### Phase 3 Changes

**Update architectural context:**
- Only ONE service to instrument (backend)
- No MCP server metrics needed (for agent)
- No host service metrics needed

**Simplify:**
- Task 3.4: Only instrument backend (not MCP/host service)
- Task 3.5: Only backend metrics
- Remove references to multiple services

---

## New Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Backend (Docker Container, Port 8000)                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent System                          │   │
│  │                                                         │   │
│  │  ┌───────────────┐     ┌──────────────────────────┐    │   │
│  │  │ Agent API     │     │ Background Trigger Loop  │    │   │
│  │  │               │     │                          │    │   │
│  │  │ POST /trigger │     │ Every 5 min:            │    │   │
│  │  │ GET /status   │     │ - Check if should run   │    │   │
│  │  │ GET /sessions │     │ - Invoke agent if yes   │    │   │
│  │  └───────┬───────┘     └────────────┬─────────────┘    │   │
│  │          │                          │                   │   │
│  │          └──────────┬───────────────┘                   │   │
│  │                     ▼                                    │   │
│  │          ┌──────────────────────────┐                   │   │
│  │          │  AnthropicAgentInvoker   │                   │   │
│  │          │                          │                   │   │
│  │          │  • Calls Anthropic API   │                   │   │
│  │          │  • Handles tool calls    │                   │   │
│  │          │  • Tracks tokens/cost    │                   │   │
│  │          └────────────┬─────────────┘                   │   │
│  │                       │                                  │   │
│  │                       ▼                                  │   │
│  │          ┌──────────────────────────┐                   │   │
│  │          │     Tool Executor        │                   │   │
│  │          │                          │                   │   │
│  │          │  • save_strategy_config  │───▶ Strategies/   │   │
│  │          │  • get_available_*       │                   │   │
│  │          │  • get_recent_strategies │───▶ PostgreSQL    │   │
│  │          │  • start_training        │───▶ Training Svc  │   │
│  │          │  • start_backtest        │───▶ Backtest Svc  │   │
│  │          └──────────────────────────┘                   │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Existing KTRDR Services                     │   │
│  │                                                         │   │
│  │  • Training Service (distributed workers)               │   │
│  │  • Backtest Service (distributed workers)               │   │
│  │  • Data Service                                          │   │
│  │  • Operations Service                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTPS (api.anthropic.com)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Anthropic API                                │
│                                                                 │
│  • Claude Sonnet/Opus models                                     │
│  • Tool use (function calling)                                  │
│  • Token counting                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Agent configuration
AGENT_ENABLED=true                    # Enable background trigger loop
AGENT_TRIGGER_INTERVAL_SECONDS=300    # 5 minutes
AGENT_MODEL=claude-sonnet-4-20250514  # Or claude-opus-4-20250514
AGENT_MAX_TOKENS=4096

# Budget (Phase 3)
AGENT_DAILY_BUDGET_USD=5.0
```

---

## Files to Create/Modify

### New Files

```
ktrdr/
├── agents/
│   ├── __init__.py
│   ├── invoker.py              # AnthropicAgentInvoker
│   ├── tools.py                # Tool definitions (schemas)
│   ├── executor.py             # ToolExecutor
│   └── trigger.py              # TriggerService (moved/updated)
```

### Modified Files

```
ktrdr/api/
├── endpoints/
│   └── agent.py                # NEW: Agent API endpoints
├── main.py                     # Add background trigger loop startup

ktrdr/cli/
└── agent_commands.py           # Fix to use API (not direct service)

pyproject.toml                  # Add anthropic dependency
```

### Files No Longer Needed (for agent)

```
agent-host-service/             # Not needed - agent runs in backend
mcp/                            # Still exists but not required for agent
```

---

## Prompt for Updating Plans

Use this prompt in a fresh session:

```
I need to update the agent MVP plans to reflect our new architecture decision.

Please read:
1. docs/agentic/mvp/ARCHITECTURE_DECISION_anthropic_api.md (this file)
2. docs/agentic/mvp/PLAN_phase1_strategy_design.md
3. docs/agentic/mvp/PLAN_phase2_full_cycle.md
4. docs/agentic/mvp/PLAN_phase3_observability.md

Then update all three plans to:
1. Remove host service references (agent runs in backend)
2. Remove MCP server references (tools execute in-process)
3. Update task descriptions for Anthropic API integration
4. Simplify architecture diagrams
5. Update file paths and dependencies
6. Adjust effort estimates

Key changes:
- Phase 1: Replace Tasks 1.10-1.11 with new tasks for Anthropic integration
- Phase 2: Remove host service polling, operations are in same process
- Phase 3: Only instrument backend (not multiple services)

After updating, commit the changes with a clear message.
```

---

## Benefits of This Approach

1. **Simpler architecture** - One service instead of three
2. **Docker-native** - No Node.js or host service needed
3. **Full control** - Observability, cost tracking, error handling
4. **Composable tools** - Claude still chooses which tools to use
5. **Direct token tracking** - From Anthropic API response
6. **Faster iteration** - No subprocess/protocol overhead
