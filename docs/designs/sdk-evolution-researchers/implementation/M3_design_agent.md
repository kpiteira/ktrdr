---
design: docs/designs/sdk-evolution-researchers/DESIGN.md
architecture: docs/designs/sdk-evolution-researchers/ARCHITECTURE.md
---

# Milestone 3: Design Agent Worker

## User Value

**You can trigger a design agent that autonomously explores your trading system and creates strategies — using Claude Code's full agentic loop instead of a pre-loaded prompt with 2 tools.**

After M3, you POST a research brief to the design agent container and it:
- Discovers available indicators via MCP (`get_available_indicators`)
- Reads example strategies from the filesystem to learn patterns
- Explores data availability via MCP (`get_data_summary`)
- Designs a strategy based on the brief
- Validates iteratively via MCP (`validate_strategy`) — fixing errors autonomously
- Saves the final strategy atomically via MCP (`save_strategy_config`)

This is fundamentally more capable than the current agent (which gets everything pre-loaded and has 2 tools). The agent can recover from errors, try alternatives, and make informed decisions based on what it discovers. Usable standalone — not just through evolution.

## E2E Validation

### Test: Design Agent Creates Strategy From Brief

**Purpose**: Verify a research brief triggers the design agent's Claude Code agentic loop, which explores via MCP and produces a validated strategy.

**Duration**: ~2-5 minutes (Claude Code multi-turn session)

**Prerequisites**: Backend running, design-agent-1 container running with auth mount, EURUSD data available

**Test Steps**:

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Verify design-agent-1 is healthy | GET `/health` returns 200 | Health response |
| 2 | Verify design-agent-1 registered with backend | GET `/api/v1/workers` includes AGENT_DESIGN type | Worker in list |
| 3 | POST `/designs/start` with brief: "Design a momentum strategy using RSI and MACD for EURUSD 1h" | Returns operation_id, status=started | Response JSON |
| 4 | Poll operation status until complete (timeout: 5 min) | Status transitions: started → running → completed | Status progression |
| 5 | Check operation result_summary | Contains strategy_name and strategy_path | result_summary fields |
| 6 | Read strategy file at returned path | Valid v3 strategy YAML | YAML parses, contains indicators section |
| 7 | Validate strategy mentions RSI and/or MACD | Brief was respected — agent designed what was asked | Indicator names in YAML |
| 8 | Check agent transcript for MCP tool calls | Transcript contains `get_available_indicators` and `save_strategy_config` calls | ToolUseBlock entries |

**Success Criteria**:
- [ ] Design agent container accepts and processes a research brief
- [ ] Claude Code's agentic loop runs (multiple turns with MCP tool calls)
- [ ] Agent discovers indicators via MCP (not pre-loaded)
- [ ] Agent saves strategy via `save_strategy_config` MCP tool (atomic validation)
- [ ] Strategy file is valid v3 format
- [ ] Brief influences the strategy design (not generic output)

---

## Task 3.1: Create DesignAgentWorker (WorkerAPIBase)

**File(s)**: `ktrdr/agents/workers/design_agent_worker.py` (NEW)
**Type**: CODING
**Architectural Pattern**: D2 (containerized workers), WorkerAPIBase contract

**Description**:
Create a new worker that inherits `WorkerAPIBase` with `worker_type=AGENT_DESIGN`. Implements:
- `POST /designs/start` endpoint accepting `{task_id, brief, symbol, timeframe, experiment_context}`
- Background task that invokes `AgentRuntime.invoke()` with the design system prompt + brief
- Result extraction from SDK transcript (find `save_strategy_config` tool call)
- Reports completion via `complete_operation(result_summary={strategy_name, strategy_path, ...})`

**Implementation Notes**:
- Follow the pattern in `ktrdr/backtesting/backtest_worker.py` for WorkerAPIBase usage
- The worker receives an `AgentRuntime` instance (injected, not imported directly) — per D9
- Background task: start Claude Code session, process messages, extract result
- Result extraction: scan transcript for ToolUseBlock with tool name `mcp__ktrdr__save_strategy_config`, extract strategy_name from tool result
- Fallback: if no save tool call found, scan filesystem for recently-created YAML files

**Tests**:
- Unit: `tests/unit/agents/workers/test_design_agent_worker.py`
  - [ ] Start endpoint creates operation and launches background task
  - [ ] Result extraction finds strategy from transcript
  - [ ] Result extraction fallback when no tool call found
  - [ ] Operation marked complete with correct result_summary
  - [ ] Operation marked failed on timeout/error

**Acceptance Criteria**:
- [ ] Worker follows WorkerAPIBase contract (register, accept, execute, report)
- [ ] Invokes AgentRuntime.invoke() with system prompt + brief
- [ ] Extracts strategy_name from SDK transcript
- [ ] Reports completion via operations service

---

## Task 3.2: Write design agent system prompt

**File(s)**: `ktrdr/agents/prompts/design_sdk.py` (NEW)
**Type**: CODING
**Architectural Pattern**: D7 (slim prompt + MCP discovery)

**Description**:
Write the ~60 line system prompt for the design agent. This is fundamentally different from the current ~430 line prompt. It defines:

1. **Role**: You are a trading strategy designer for the ktrdr system
2. **Workflow**: Discover → Design → Validate → Iterate → Save
3. **Output contract**: "Done" means a saved, validated v3 strategy via `save_strategy_config` MCP tool
4. **Safety constraints**: Only use validated indicators, follow v3 format
5. **Discovery guidance**: Use `get_available_indicators` to see what's available, read example strategies from `/app/strategies/`, use `validate_strategy` to check your work

The prompt does NOT contain: YAML templates, indicator lists, enum values, symbol lists. The agent discovers these via MCP.

**Implementation Notes**:
- The genome-derived brief goes in the user prompt, not the system prompt
- Experiment context (3-5 lines) goes in the user prompt
- Key hypothesis to test (if any) goes in the user prompt
- The system prompt is static — same for all design agents regardless of brief

**Tests**:
- [ ] System prompt is under 100 lines
- [ ] System prompt does NOT contain indicator lists or YAML templates
- [ ] System prompt references MCP tools by name (save_strategy_config, validate_strategy, get_available_indicators)

**Acceptance Criteria**:
- [ ] Slim system prompt (~60 lines)
- [ ] Defines clear workflow and output contract
- [ ] References MCP tools for discovery (not pre-loaded data)
- [ ] Agent knows how to signal "done" (call save_strategy_config)

---

## Task 3.3: Wire design agent into docker-compose

**File(s)**: `docker-compose.sandbox.yml` (or appropriate compose file)
**Type**: CODING

**Description**:
Add `design-agent-1` service to docker-compose using the `ktrdr-agent:dev` image from M2. Configure:
- Worker type environment: `KTRDR_WORKER_TYPE=agent_design`
- Worker port: `KTRDR_WORKER_PORT=5010`
- Backend URL: `KTRDR_API_CLIENT_BASE_URL=http://backend:8000/api/v1`
- MCP backend URL: `KTRDR_MCP_BACKEND_URL=http://backend:8000/api/v1`
- Auth volume: `${HOME}/.claude:/home/agent/.claude:ro`
- Shared volumes: strategies, models, data, memory
- Healthcheck: `curl -f http://localhost:5010/health`
- Depends on: backend

**Implementation Notes**:
- Follow the pattern in ARCHITECTURE.md Docker Compose section
- Use the same Docker network as other workers
- Port 5010 for design agent (training workers use 5001-5003, backtest on 5003)
- The command runs the design agent worker's FastAPI app via uvicorn

**Tests**:
- [ ] `docker compose up design-agent-1` starts without errors
- [ ] Container passes healthcheck
- [ ] Worker registers with backend (appears in `/api/v1/workers`)

**Acceptance Criteria**:
- [ ] Design agent starts as a Docker service
- [ ] Self-registers with backend as AGENT_DESIGN worker
- [ ] Healthcheck passes
- [ ] MCP server accessible inside container

---

## Task 3.4: Unit tests for design agent worker

**File(s)**: `tests/unit/agents/workers/test_design_agent_worker.py`
**Type**: CODING

**Description**:
Comprehensive unit tests with mocked AgentRuntime. Test the worker's logic without requiring a real Claude Code session.

**Tests**:
- [ ] POST /designs/start with valid brief → operation created, background task started
- [ ] POST /designs/start with missing brief → 422 validation error
- [ ] Background task calls runtime.invoke() with correct prompt and MCP config
- [ ] Transcript with save_strategy_config tool call → strategy_name extracted
- [ ] Transcript without save_strategy_config → operation fails with descriptive error
- [ ] Runtime invoke() raises → operation marked failed
- [ ] Runtime invoke() timeout → operation marked failed with timeout message
- [ ] Health endpoint returns 200

**Acceptance Criteria**:
- [ ] All unit tests pass with mocked runtime
- [ ] Tests cover happy path, error cases, and edge cases
- [ ] Tests verify correct prompt composition (system + user)

---

## Task 3.5: Execute E2E Test — Design Agent Creates Strategy From Brief

**Type**: VALIDATION

**Description**:
Validate M3 is complete: POST a research brief to the design agent, watch it explore via MCP, verify it produces a validated strategy.

**⚠️ MANDATORY: Use the E2E Agent System**

1. Invoke `e2e-test-designer` → likely architect handoff (new capability)
2. Invoke `e2e-test-architect` to design test spec
3. Invoke `e2e-tester` to execute

**Key Validation**: The E2E test must verify that the agent actually used MCP tools (not just produced output). Check the transcript for `get_available_indicators` and `save_strategy_config` tool calls. This proves Claude Code's agentic loop is working, not just a single-shot text generation.

**Acceptance Criteria**:
- [ ] Design agent container accepts research brief
- [ ] Claude Code agentic loop runs with MCP tool calls
- [ ] Validated strategy saved via save_strategy_config MCP tool
- [ ] Strategy file is valid v3 format
- [ ] Brief influences strategy content
- [ ] M1 and M2 E2E tests still pass
- [ ] E2E test executed via agent

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (design agent creates strategy from brief)
- [ ] M1 and M2 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Design agent registers and appears in worker list
- [ ] No regressions in existing workers
