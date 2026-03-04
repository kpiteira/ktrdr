# SDK-Based Agent Workers

## Problem Statement

Evolution researchers currently run inside the backend process using direct Anthropic API calls (`AnthropicInvoker`). This creates three problems:

1. **Cost**: API-metered at ~$0.40/researcher. Budget tracker estimates 3x reality, causing fake exhaustion that kills runs and forces expensive restarts from zero.
2. **Capability ceiling**: Researchers get 2-8 hand-crafted tools (thin API wrappers). They can't explore data, try alternatives, or recover from unexpected situations.
3. **Architecture violation**: Agent workers run inside the backend process. All other workers (training, backtest) run in containers. The backend should be a pure dispatcher.

## Goals

- **Eliminate API costs for evolution** by running agent workers on Claude Code subscription
- **Increase researcher capability** by giving design agents MCP access to the full ktrdr system
- **Complete the distributed workers architecture** by moving all agent logic out of the backend into container workers
- **Maintain the worker contract** — new workers follow the same WorkerAPIBase pattern as training/backtest workers

## Non-Goals

- Replacing the research orchestration state machine with an autonomous agent (training is too long-running; the orchestrator works fine)
- Changing training or backtest workers
- Modifying the evolution harness, fitness evaluation, or genome system
- Supporting non-containerized execution (process-based fallback)

## Key Decisions

### D1: Focused agents, not autonomous orchestrators

**Decision**: Each agent worker does ONE thing well. Design agent designs strategies. Assessment agent assesses results. The research orchestrator manages the pipeline.

**Rationale**: Training runs 30+ minutes. A Claude Code session managing the full pipeline would lose context and waste time. The orchestration state machine has never been the problem — the agent quality has.

### D2: All agent workers become container workers

**Decision**: Move all agent logic (design, assessment, research orchestration) out of the backend into container workers following the same WorkerAPIBase contract.

**Rationale**: The backend should be a pure dispatcher. Having agent workers in-process was a shortcut that created coupling. All other workers are already containerized.

### D3: Claude Code SDK + MCP for LLM-powered workers

**Decision**: Design and assessment workers run Claude Code with ktrdr MCP server access. Research orchestrator stays Python-only (no LLM needed).

**Rationale**: Claude Code + MCP gives agents real system access (data exploration, strategy validation, indicator discovery) on subscription pricing. The MCP server already has 20 tools covering the full researcher workflow.

### D4: Container auth via named Docker volume

**Decision**: Use a named Docker volume for Claude auth (`ktrdr-agent-claude-auth:/home/agent/.claude`), provisioned once via `claude login`. Do NOT mount host `~/.claude` — macOS stores OAuth tokens in the Keychain (not filesystem), and host mounts risk interfering with the running CLI session.

**Rationale**: Pattern proven in agent-memory (`agent-memory-claude-auth` named volume). Subscription auth, no API keys, isolated from host. Multiple concurrent sessions on the same subscription are confirmed working.

### D5: stdio MCP inside container

**Decision**: Each Claude Code session spawns its own MCP server subprocess (stdio transport) inside the container. The MCP server connects to the backend via HTTP.

**Rationale**: stdio MCP doesn't work in SDK subprocess mode (bug: stdio gets redirected from main process). Inside a container, Claude Code owns stdio, so MCP works normally. Multiple MCP servers hitting the same backend is fine — it handles concurrent operations already.

### D6: Python SDK, not raw CLI

**Decision**: Use `claude-agent-sdk` Python package for agent invocation, not the raw `claude` CLI.

**Rationale**: The sister project agent-memory has proven the SDK in production. It provides structured output (TextBlock, ToolUseBlock, ToolResultBlock), session lifecycle management, cost tracking, and clean permission mode configuration. Raw CLI requires JSON parsing and loses type information. Critical patterns from agent-memory: remove `CLAUDECODE` env var before spawn (blocks nested calls), MCP server logging to stderr only (preserves stdio protocol), `permission_mode="bypassPermissions"` for unattended execution.

### D7: Slim prompt + MCP discovery (not pre-loaded context)

**Decision**: Agent system prompts shrink from ~430 lines to ~60 lines. Agents discover context via MCP tools and filesystem access instead of receiving it pre-loaded in the prompt.

**Rationale**: The current approach pre-loads indicator lists, symbol lists, v3 YAML templates, enum values, recent strategies, and experiment history into a ~4,000-token prompt with only 2 tools. In M1 primordial-soup testing, this led to all 3 researchers designing the identical strategy — the massive prompt overwhelmed the genome brief's differentiation signal. With MCP + filesystem access, agents discover context themselves, making the genome-derived brief the dominant signal. System prompt defines role, workflow, output contract, and safety constraints only. User prompt contains the research brief, a 3-5 line experiment digest, and key hypothesis to test (if any).

### D8: Atomic save via MCP tools

**Decision**: Agents save strategies and assessments through MCP tools that validate-then-save atomically. Agents do NOT use Claude Code's built-in Write tool for output artifacts.

**Rationale**: Prevents saving invalid strategies and maintains the "all mutations through validated paths" pattern. The design agent calls `save_strategy_config` MCP tool (validates v3 format, then writes). The assessment agent calls `save_assessment` MCP tool (validates structure, then writes). This matches the current in-process pattern where ToolExecutor validates before saving.

### D9: Protocol-first provider abstraction

**Decision**: Copy the `AgentRuntime` Protocol pattern from agent-memory into ktrdr. Design and assessment workers program against the protocol, not a specific SDK.

**Rationale**: agent-memory already has a production-proven `AgentRuntime` Protocol with `invoke()` and `resume()` methods, returning standardized `AgentResult` (output, cost_usd, turns, transcript, session_id). It has Claude and Copilot provider stubs. Copying ~200 lines of protocol + implementation gives us: (a) provider-agnostic worker code, (b) Copilot CLI as a single-file addition when it ships, (c) independent evolution from agent-memory (different Python versions, deployment models, release cycles). A shared library would create unnecessary coupling between projects at this stage.

### D10: Focused MCP gap-fill, not broad refresh

**Decision**: MCP server update (M0) is a focused gap-fill: register 3 missing tools, add 1 new tool, remove 1 deprecated tool. Broader MCP expansion is separate future work.

**Rationale**: The MCP server is less stale than initially feared — 60 commits in 2 months, 18 tools, full OTEL instrumentation. The gaps are specific to agent workflows: `save_strategy_config` and `get_recent_strategies` are implemented but not registered in server.py, `save_assessment` needs to be added, and `get_training_status` is deprecated. A focused scope unblocks M1 quickly without scope creep into fuzzy logic, IB Gateway, workers, or checkpoint tools.

## What Changes

| Component | Current | New |
|-----------|---------|-----|
| Design phase | AnthropicInvoker + 2 custom tools, runs in backend | Design Agent Worker container, Claude Code + MCP |
| Assessment phase | AnthropicInvoker + 8 custom tools, runs in backend | Assessment Agent Worker container, Claude Code + MCP |
| Research orchestration | AgentResearchWorker in backend process | Research Orchestrator Worker container, Python |
| Cost model | Anthropic API ($0.40/researcher, 3x over-estimated) | Claude Code subscription (included) |
| Budget tracking | BudgetTracker with daily limits | Not needed for evolution |
| Backend role | Runs agent logic + dispatches to other workers | Pure dispatcher for all worker types |

## What Stays the Same

- Evolution harness (trigger, poll, fitness, selection, reproduction)
- Training workers
- Backtest workers
- Worker registration and dispatch protocol (WorkerAPIBase)
- Operation tracking (OperationsService)
- MCP server tools and capabilities
- Genome system and brief translator

## Risks

1. **Claude Code session reliability**: Sessions may fail, hang, or produce malformed output. Mitigation: timeout per session, structured output contract, retry logic in orchestrator.
2. **Container startup time**: Claude Code + MCP initialization adds latency vs direct API calls. Mitigation: long-running containers with context clearing between operations.
3. **MCP server availability**: If backend is slow, MCP tools timeout. Mitigation: health check before accepting operations, MCP timeout configuration.
4. **Auth token expiry**: Mounted credentials may expire during long runs. Mitigation: monitor auth failures, refresh protocol TBD.

## MCP Server Assessment

The MCP server is less stale than initially expected: 60 commits in 2 months (Jan-Feb 2026), last updated Feb 25, 18 tools registered, full OpenTelemetry instrumentation, modular client architecture (7 domain clients), 56+ unit tests passing.

**Real gaps for agent workflows:**

| Gap | Priority | Resolution |
|-----|----------|------------|
| `save_strategy_config` not registered | CRITICAL | Code exists in strategy_service.py, not wired into server.py |
| `save_assessment` missing | CRITICAL | New MCP tool needed for structured assessment output |
| `get_recent_strategies` not registered | HIGH | Code exists, not wired, needs limit/sort parameters |
| `get_training_status` deprecated | LOW | Remove, replaced by `get_operation_status` |
| Experiment memory access | MEDIUM | Not needed as MCP tool — Claude Code reads filesystem directly |

Agents do NOT need MCP tools for experiment memory. Claude Code's built-in Read/Glob tools access the mounted filesystem (`/app/memory/hypotheses.yaml`, `/app/memory/experiments/*.yaml`). Adding MCP tools for filesystem reads would be redundant.

## Provider Abstraction Strategy

**Approach: Copy pattern from agent-memory (independent evolution)**

Copy ~200 lines into `ktrdr/agents/runtime/`:
- `AgentRuntime` Protocol (invoke/resume interface, ~50 lines)
- `AgentResult` dataclass (output, cost_usd, turns, transcript, session_id)
- `AgentRuntimeConfig` dataclass (provider, model, max_budget_usd, max_turns)
- `ClaudeAgentRuntime` implementation (adapted for ktrdr container context)
- `SafetyGuard` basics (budget cap, tool allowlist — adapted to use ktrdr's BudgetTracker)

**Not copied**: `PersistentAgentRuntime` (ktrdr agents are ephemeral per-operation, not persistent sessions), `CopilotAgentRuntime` (not ready; copy when it ships in agent-memory and proves stable), cost tracker / circuit breaker (ktrdr has BudgetTracker already).

**Why not shared library**: Different Python versions (ktrdr 3.12-3.13, agent-memory 3.13+), different deployment models (Docker containers vs bare metal), different release cycles. The protocol is stable; implementations diverge.

**Future Copilot path**: When Copilot CLI ships in agent-memory and stabilizes, add `CopilotAgentRuntime` to ktrdr as a new file implementing the same `AgentRuntime` Protocol. Worker code stays identical — only `AgentRuntimeConfig.provider` changes.

## Model Selection

Default to `claude-sonnet-4-6` for both design and assessment workers. Configurable per evolution run.

```yaml
# In evolution config
design_model: claude-sonnet-4-6      # Multi-turn exploratory work
assessment_model: claude-sonnet-4-6   # Structured analysis
max_turns_design: 25                  # More room for exploration
max_turns_assessment: 10              # Assessment is focused
```

On subscription pricing, model choice is about quality/speed — not cost. Sonnet is the sweet spot: fast enough for 20+ turn tool-use loops, capable enough for strategy design. Opus is overkill for iterative design work (slower per turn; design quality comes from exploration depth, not single-shot reasoning power).

The model string flows through `AgentRuntime.invoke()` — each provider maps it to its equivalent. Copilot may not expose model choice at all, which is fine; the runtime handles the mapping.

## Milestones

### M0: MCP Server Agent Gap-Fill
Register 3 missing tools, add 1 new tool, remove 1 deprecated tool. Focused scope — only what agent workers need. Unblocks M1.

### M1: AgentRuntime Protocol + Container Infrastructure
Port AgentRuntime protocol from agent-memory. Build `ktrdr-agent:dev` Docker image (Python 3.12 + Node 20 + Claude Code CLI + MCP server). Verify SDK invocation inside container with auth mount and MCP access. This milestone proves the foundation before building workers on top of it.

### M2: Design Agent Worker
Containerized design agent that receives a brief, runs Claude Code with MCP, and returns a validated strategy. Follows WorkerAPIBase contract. Slim system prompt (~60 lines). Result extraction from SDK transcript (find `save_strategy_config` tool call).

### M3: Assessment Agent Worker
Same container base image, assessment-focused prompt. Receives strategy + metrics, returns structured assessment via `save_assessment` MCP tool. Includes memory integration (save experiment record, update hypotheses).

### M4: Evolution Integration + Cleanup
Wire evolution harness to use containerized agent workers. Update the in-backend research orchestrator to dispatch to design/assessment containers via HTTP instead of calling AnthropicInvoker directly. Remove old invoker-based agent code. Full evolution run validation (3 researchers, 1 generation). Adapt BudgetTracker for subscription model (track turns instead of API cost).

### Deferred: Research Orchestrator Worker
Moving the research orchestrator out of the backend into its own container is architecturally clean but the orchestrator works well as-is. Defer until there's a concrete reason to extract it (scaling, isolation, etc.).

### Deferred: Copilot CLI Integration
Port `CopilotAgentRuntime` from agent-memory when it ships and proves stable. The `AgentRuntime` Protocol ensures worker code is provider-agnostic — adding Copilot is a single-file addition.

```
Dependency graph:

M0 (MCP Gap-Fill) → M1 (Runtime + Infra) → M2 (Design Agent)  → M4 (Integration)
                                           → M3 (Assessment Agent) ↗

M2 and M3 can run in parallel after M1.
```

## Open Questions — Resolved

### OQ1: Prompt engineering → D7 (Slim prompt + MCP discovery)

The agent's system prompt shrinks to ~60 lines defining role, workflow, output contract, and safety constraints. Context discovery happens via MCP tools and filesystem. See D7 rationale for why this is expected to improve quality (current massive prompt overwhelmed genome differentiation in M1 testing).

### OQ2: Model selection → Sonnet default, configurable

`claude-sonnet-4-6` for both workers. Configurable per evolution run. Quality comes from exploration depth (more turns) not single-shot reasoning (larger model). See Model Selection section.

### OQ3: Invocation pattern → D6 (Python SDK)

Use `claude-agent-sdk` Python package, proven in production by agent-memory. Provides structured output, session lifecycle, cost tracking. Critical patterns: remove CLAUDECODE env var before spawn, MCP logging to stderr, `permission_mode="bypassPermissions"`. See D6.

## Cross-Pollination: agent-memory

The sister project `agent-memory` has production-proven patterns for Claude Code SDK usage that inform this design:

| Pattern | agent-memory Location | ktrdr Usage |
|---------|----------------------|-------------|
| AgentRuntime Protocol | `runtime/protocol.py` | Copy to `ktrdr/agents/runtime/protocol.py` |
| ClaudeAgentRuntime | `runtime/claude.py` | Adapt for container context |
| CopilotAgentRuntime stub | `runtime/copilot.py` | Deferred — port when stable |
| Safety guards (budget, tools) | `runtime/safety.py` | Adapt to use ktrdr BudgetTracker |
| Stdio MCP subprocess | `mcp/telegram_stdio.py` | Same pattern for ktrdr MCP in container |
| CLAUDECODE env var handling | `runtime/claude.py:89` | Required — blocks nested SDK calls |
| Auth via named Docker volumes | `docker-compose.yml` | Named volume + `claude login` (same pattern) |
| Transcript → structured output | `runtime/claude.py` | Parse ToolUseBlock for strategy/assessment results |
