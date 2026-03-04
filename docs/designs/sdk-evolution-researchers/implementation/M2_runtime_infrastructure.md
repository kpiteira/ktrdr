---
design: docs/designs/sdk-evolution-researchers/DESIGN.md
architecture: docs/designs/sdk-evolution-researchers/ARCHITECTURE.md
---

# Milestone 2: AgentRuntime Protocol + Container Infrastructure

## User Value

**You have a containerized Claude Code agent that can interact with your full ktrdr system via MCP — a general-purpose "research worker" you can point at any task.**

After M2, a Docker container exists that runs Claude Code with full MCP access to ktrdr (indicators, strategies, data, operations). You can exec into it and run a Claude Code session that explores your trading system. This is the foundation for specialized design/assessment agents (M3/M4), but the container itself is immediately useful as a research environment.

## Reuse from agent-memory

This milestone is a **port, not an experiment**. agent-memory has all of this running in production:

| Component | agent-memory Source | ktrdr Adaptation |
|-----------|-------------------|------------------|
| AgentRuntime Protocol | `src/agent_memory/runtime/protocol.py` | Remove PersistentAgentRuntime (not needed) |
| ClaudeAgentRuntime | `src/agent_memory/runtime/claude.py` | Adapt for container context, remove persistence |
| Dockerfile | `Dockerfile` (multi-stage, Node + Python + Claude CLI) | Adapt base image, add ktrdr MCP server |
| Auth via named Docker volume | `docker-compose.yml` (`claude-config:/root/.claude`) | Same pattern: named volume + `claude login` |
| SDK invocation pattern | `runtime/claude.py:invoke()` | Direct port |
| CLAUDECODE env var handling | `runtime/claude.py:89` | Direct port |
| MCP subprocess config | `mcp/telegram_stdio.py` pattern | Adapt for ktrdr MCP server |

**Do not reinvent any of these.** Read the agent-memory source and port directly.

## E2E Validation

### Test: Claude Code SDK Invocation Inside Container

**Purpose**: Verify the `ktrdr-agent:dev` container can run Claude Code via the SDK, connect to ktrdr MCP, and call a tool successfully.

**Duration**: ~60 seconds

**Prerequisites**: Backend running, Claude auth provisioned (named volume or `ANTHROPIC_API_KEY`), `ktrdr-agent:dev` image built

**Test Steps**:

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Build `ktrdr-agent:dev` Docker image | Image builds without errors | `docker images` shows image |
| 2 | Start container with auth (named volume or API key) and backend network | Container starts, healthcheck passes | `docker ps` shows healthy |
| 3 | From inside container, run Python script that invokes Claude Code SDK with a simple prompt ("List available indicators using the ktrdr MCP tools") | SDK returns structured response, transcript contains MCP tool call | AgentResult with output + transcript |
| 4 | Verify transcript shows `mcp__ktrdr__get_available_indicators` tool call | MCP tool was actually called (not just text response) | ToolUseBlock in transcript |
| 5 | Verify MCP tool returned real indicator data from backend | Indicator list matches what backend serves | Response contains known indicators (RSI, MACD, etc.) |
| 6 | Verify cost tracking works | AgentResult.cost_usd > 0 or turns > 0 | Cost/turn fields populated |

**Success Criteria**:
- [ ] Docker image builds successfully
- [ ] Claude Code SDK invokes inside container without auth errors
- [ ] MCP server starts as stdio subprocess inside container
- [ ] MCP tool call reaches backend and returns real data
- [ ] Structured output (AgentResult) is parseable

---

## Task 2.1: Port AgentRuntime Protocol from agent-memory

**File(s)**: `ktrdr/agents/runtime/__init__.py` (NEW), `ktrdr/agents/runtime/protocol.py` (NEW)
**Type**: CODING
**Architectural Pattern**: D9 (protocol-first provider abstraction)

**Description**:
Create `ktrdr/agents/runtime/` package with the AgentRuntime Protocol, AgentResult dataclass, and AgentRuntimeConfig. Port from agent-memory's `runtime/protocol.py`, adapted for ktrdr:

```python
@runtime_checkable
class AgentRuntime(Protocol):
    async def invoke(
        self, prompt: str, *,
        model: str | None = None,
        max_turns: int = 10,
        max_budget_usd: float = 1.0,
        allowed_tools: list[str] | None = None,
        cwd: str | None = None,
        system_prompt: str | None = None,
        mcp_servers: dict[str, object] | None = None,
    ) -> AgentResult: ...

@dataclass
class AgentResult:
    output: str
    cost_usd: float
    turns: int
    transcript: list[dict]
    session_id: str | None
```

**Implementation Notes**:
- **Port directly from** `../agent-memory/src/agent_memory/runtime/protocol.py`
- Strip PersistentAgentRuntime (ktrdr agents are ephemeral per-operation)
- Strip CopilotAgentRuntime (deferred)
- Keep the protocol minimal — only what design/assessment workers need

**Tests**:
- Unit: `tests/unit/agents/runtime/test_protocol.py`
  - [ ] AgentResult serialization
  - [ ] Protocol is runtime_checkable
  - [ ] AgentRuntimeConfig defaults

**Acceptance Criteria**:
- [ ] `AgentRuntime` protocol defined and importable
- [ ] `AgentResult` dataclass works with standard Python
- [ ] No dependency on claude-agent-sdk in protocol.py (protocol is provider-agnostic)

---

## Task 2.2: Port ClaudeAgentRuntime implementation

**File(s)**: `ktrdr/agents/runtime/claude.py` (NEW), `pyproject.toml`
**Type**: CODING
**Architectural Pattern**: D6 (Python SDK), D9 (provider abstraction)

**Description**:
Implement `ClaudeAgentRuntime` that satisfies the `AgentRuntime` protocol using `claude-agent-sdk`. Port from agent-memory's `runtime/claude.py`, adapted for ktrdr container context.

Key behaviors:
1. Build `ClaudeAgentOptions` from invoke() parameters
2. Remove `CLAUDECODE` env var before spawn (blocks nested calls)
3. Iterate through SDK messages, build transcript as list of dicts
4. Extract output text from final message
5. Track cost and turns from SDK response
6. Restore `CLAUDECODE` env var in finally block

**Implementation Notes**:
- **Port directly from** `../agent-memory/src/agent_memory/runtime/claude.py`
- The invoke() method, CLAUDECODE env handling, transcript conversion, and error recovery are all proven — port them, don't rewrite
- Add `claude-agent-sdk>=0.1.41` to pyproject.toml (same version as agent-memory)
- Strip persistent session logic (connect/disconnect/recover) — ktrdr uses ephemeral invoke() only

**Tests**:
- Unit: `tests/unit/agents/runtime/test_claude_runtime.py`
  - [ ] invoke() with mocked SDK returns AgentResult
  - [ ] CLAUDECODE env var removed before spawn, restored after
  - [ ] CLIConnectionError triggers one retry
  - [ ] Transcript conversion from SDK blocks to dicts
  - [ ] Cost and turn tracking

**Acceptance Criteria**:
- [ ] `ClaudeAgentRuntime` satisfies `AgentRuntime` protocol
- [ ] CLAUDECODE env var handling correct
- [ ] Error recovery with single retry
- [ ] `claude-agent-sdk` added to dependencies

---

## Task 2.3: Adapt SafetyGuard for ktrdr context

**File(s)**: `ktrdr/agents/runtime/safety.py` (NEW)
**Type**: CODING

**Description**:
Port SafetyGuard pattern from agent-memory, adapted to integrate with ktrdr's existing `BudgetTracker`. The SafetyGuard checks before each `invoke()` call:
1. Budget cap: cumulative cost hasn't exceeded limit
2. Tool allowlist: only permitted tools are passed to the SDK
3. Turn limit: max_turns is within configured bounds

This is a lightweight wrapper, not a full circuit breaker (ktrdr's BudgetTracker handles daily limits).

**Implementation Notes**:
- **Port pattern from** `../agent-memory/src/agent_memory/runtime/safety.py`
- agent-memory has SafetyGuard with budget cap, circuit breaker, tool allowlists — port the budget cap + tool allowlist parts
- Wire into ktrdr's existing `ktrdr/agents/budget.py` (BudgetTracker) instead of agent-memory's CostTracker
- Design agents: allowed_tools = `["mcp__ktrdr__*", "Read", "Glob", "Grep"]`
- Assessment agents: allowed_tools = `["mcp__ktrdr__*", "Read", "Glob", "Grep"]` (no Write)

**Tests**:
- Unit: `tests/unit/agents/runtime/test_safety.py`
  - [ ] Budget exceeded → raises before invoke
  - [ ] Tool allowlist enforced
  - [ ] Turn limit enforced

**Acceptance Criteria**:
- [ ] SafetyGuard prevents invocation when budget exceeded
- [ ] Tool allowlists configurable per worker type
- [ ] Integrates with existing BudgetTracker

---

## Task 2.4: Add AGENT_DESIGN and AGENT_ASSESSMENT worker types

**File(s)**: `ktrdr/workers/types.py` (or wherever WorkerType enum lives), `ktrdr/api/services/worker_registry.py`
**Type**: CODING

**Description**:
Add `AGENT_DESIGN` and `AGENT_ASSESSMENT` to the WorkerType enum. Update worker registry to accept these types during registration. This is a small change but required before M3/M4 can register their workers.

**Implementation Notes**:
- Find the WorkerType enum definition (likely in `ktrdr/workers/` or `ktrdr/models/`)
- Add the two new types
- Verify worker registry doesn't have hardcoded type checks that would reject new types

**Tests**:
- Unit: Verify new types are valid WorkerType values
  - [ ] AGENT_DESIGN is a valid WorkerType
  - [ ] AGENT_ASSESSMENT is a valid WorkerType
  - [ ] Worker registry accepts registration with new types

**Acceptance Criteria**:
- [ ] New worker types defined
- [ ] Worker registry accepts them
- [ ] No existing functionality broken

---

## Task 2.5: Build ktrdr-agent Docker image

**File(s)**: `docker/Dockerfile.agent` (NEW), `docker-compose.sandbox.yml`
**Type**: CODING
**Architectural Pattern**: Architecture — Docker Image section

**Description**:
Create the `ktrdr-agent:dev` Docker image. Shared base for design and assessment agent workers.

Contents:
- Python 3.12 + Node.js 20 LTS
- Claude Code CLI (`@anthropic-ai/claude-code` via npm)
- `claude-agent-sdk` Python package
- ktrdr MCP server (copy `/mcp/` into image)
- Worker HTTP server (FastAPI + WorkerAPIBase)
- AgentRuntime protocol + Claude implementation

Volumes (configured in docker-compose, not baked in):
- Named Docker volume → `/home/agent/.claude` (subscription auth via `claude login`)
- Shared strategies, models, data, memory directories

**Implementation Notes**:
- **Start from agent-memory's `Dockerfile`** — it already has the multi-stage build with Python + Node.js + Claude Code CLI. Adapt, don't start from scratch.
- Key adaptations from agent-memory Dockerfile:
  - Change Python version to 3.12 (agent-memory uses 3.13)
  - Add ktrdr MCP server (copy `/mcp/` into image)
  - Add WorkerAPIBase dependencies
  - Keep the Claude Code CLI install pattern (`npm install -g @anthropic-ai/claude-code`)
  - Keep the named volume auth pattern (not host mount)
- Also reference `Dockerfile.worker-cpu` for ktrdr-specific patterns (non-root user, uv setup)
- Do NOT add to docker-compose yet (M3 wires it up) — just ensure the image builds

**Tests**:
- [ ] Image builds without errors: `docker build -f docker/Dockerfile.agent -t ktrdr-agent:dev .`
- [ ] Container starts and healthcheck passes
- [ ] `claude --version` works inside container
- [ ] `python -c "from ktrdr.agents.runtime.protocol import AgentRuntime"` works inside container
- [ ] MCP server starts inside container: `python -m src.main` (in /mcp/)

**Acceptance Criteria**:
- [ ] Docker image builds successfully
- [ ] All components accessible inside container (Claude CLI, Python runtime, MCP server)
- [ ] Health endpoint responds

---

## Task 2.6: Execute E2E Test — SDK Invocation Inside Container

**Type**: VALIDATION

**Description**:
Validate M2 is complete: Claude Code SDK invokes inside the container, connects to MCP, calls a real tool, returns structured output.

**⚠️ MANDATORY: Use the E2E Agent System**

This is a new test (no existing catalog match). Steps:
1. Invoke `e2e-test-designer` → will hand off to architect
2. Invoke `e2e-test-architect` to design the test
3. Invoke `e2e-tester` to execute

**Test Focus**: The test verifies the full chain works in ktrdr's context: SDK → MCP subprocess → backend HTTP → real data. The pattern is proven in agent-memory; this validates the ktrdr-specific adaptation (different MCP server, different backend, different container image).

**Acceptance Criteria**:
- [ ] Docker image builds
- [ ] SDK invocation succeeds inside container
- [ ] MCP tool call reaches backend and returns real data
- [ ] AgentResult is structured and parseable
- [ ] Auth works (named volume or API key)
- [ ] E2E test executed via agent

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (SDK invocation inside container with MCP)
- [ ] M1 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Docker image builds cleanly
- [ ] No regressions in existing workers
