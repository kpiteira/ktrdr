# MVP Design: Autonomous Strategy Designer

## ⚠️ Architecture Update (December 2024)

**This design document describes the original architecture using Claude Code CLI + MCP.**

**We have since decided to use the Anthropic Python SDK directly instead.**

See [ARCHITECTURE_DECISION_anthropic_api.md](ARCHITECTURE_DECISION_anthropic_api.md) for:

- Why we changed (simpler, no Node.js dependency, better observability)
- What changed (AnthropicAgentInvoker + ToolExecutor instead of Claude Code + MCP)
- Updated phase plans with correct implementation details

**The phase plan documents (`PLAN_phase*.md`) have been updated to reflect the new architecture.**

---

## Purpose

This document describes the technical design for the MVP autonomous research system. It explains *what* we're building and *why*, with implementation details in separate reference documents.

**Reference Documents:**
- `ref_database_schema.md` - Table definitions and queries
- `ref_agent_prompt.md` - Full agent prompt and context injection
- `ref_cli_commands.md` - CLI command specifications
- `ref_configuration.md` - Environment variables and settings
- `ref_observability.md` - Metrics, traces, and dashboard specs

---

## Design Goals

1. **Zero-cost polling** - Status checks should not consume LLM tokens
2. **Observable** - Full telemetry via OTEL/Prometheus/Jaeger/Grafana
3. **Recoverable** - Leverage checkpointing; failures don't lose work
4. **Cost-controlled** - Daily budget prevents runaway spending
5. **Simple** - Minimum components to prove the loop works

---

## Project Structure

Agent code lives in `research_agents/` at the repository root (fresh implementation):

```
research_agents/              # New implementation (old folder deleted)
├── database/                 # Schema and queries
├── services/                 # Trigger, invoker, budget, recovery
├── gates/                    # Quality gates (training, backtest)
├── prompts/                  # Agent prompts
├── validation/               # Strategy validation
└── metrics/                  # Aggregation

mcp/src/tools/                # MCP tools (separate from ktrdr)
├── agent_tools.py            # Agent state management
├── strategy_tools.py         # Save/load strategies
└── backtest_tools.py         # Backtest operations (if not existing)

ktrdr/cli/commands/agent.py   # CLI extension

tests/integration/research_agents/  # Integration tests
```

**Note:** An old `research_agents/` folder exists with broken legacy code - it will be deleted before Phase 0.

---

## System Components

### Overview

The system has four main components:

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **Trigger Service** | Poll for work, apply gates, invoke agent | Python async service in KTRDR |
| **Strategy Designer Agent** | Creative strategy design and assessment | Claude Opus via Claude Code + MCP |
| **Agent State Store** | Track sessions, actions, metrics, budget | PostgreSQL (5 new tables) |
| **Agent CLI** | Human visibility into system state | KTRDR CLI extension |

### Component Interactions

```
                    ┌─────────────────────────────────┐
                    │        KTRDR Async Worker       │
                    │                                 │
     Every 5 min    │  ┌─────────────────────────┐   │
    ────────────────┼─▶│    Trigger Service      │   │
                    │  │                         │   │
                    │  │  • Check for work       │   │
                    │  │  • Apply quality gates  │   │
                    │  │  • Check budget         │   │
                    │  │  • Invoke agent (maybe) │   │
                    │  └───────────┬─────────────┘   │
                    │              │                 │
                    └──────────────┼─────────────────┘
                                   │
                    ┌──────────────┼──────────────────┐
                    │              ▼                  │
                    │  ┌─────────────────────────┐   │
                    │  │   Claude Code + MCP     │   │
                    │  │                         │   │
                    │  │  • Receives context     │   │
                    │  │  • Designs strategies   │   │
                    │  │  • Calls KTRDR APIs     │   │
                    │  │  • Updates state        │   │
                    │  └───────────┬─────────────┘   │
                    │              │                 │
                    │              ▼                 │
                    │  ┌─────────────────────────┐   │
                    │  │     PostgreSQL          │   │
                    │  │                         │   │
                    │  │  • Sessions & state     │   │
                    │  │  • Action logs          │   │
                    │  │  • Metrics              │   │
                    │  │  • Budget tracking      │   │
                    │  └─────────────────────────┘   │
                    │                                │
                    │  ┌─────────────────────────┐   │
                    │  │     KTRDR APIs          │   │
                    │  │                         │   │
                    │  │  • Training             │   │
                    │  │  • Backtesting          │   │
                    │  │  • Operations           │   │
                    │  └─────────────────────────┘   │
                    │                                │
                    └────────────────────────────────┘
```

---

## Trigger Service

### What It Does

The trigger service is a deterministic Python component that runs every 5 minutes. It checks whether there's work for the agent to do, and if so, invokes the agent with appropriate context.

**Key insight**: By making the trigger deterministic, we ensure that status polling costs zero tokens. The LLM is only invoked when there's an actual decision to make.

### Trigger Events

The trigger service responds to these events:

| Event | Condition | Action |
|-------|-----------|--------|
| **Start new cycle** | No active session + budget available | Invoke agent to design a strategy |
| **Training completed** | Training op finished successfully | Check gate, then invoke or fail |
| **Training failed** | Training op failed | Log failure, reset session |
| **Backtest completed** | Backtest op finished successfully | Check gate, then invoke or fail |
| **Backtest failed** | Backtest op failed | Log failure, reset session |

### Quality Gates

Before invoking the agent after training or backtesting, the trigger applies simple threshold checks:

**Training Gate** - Skip backtest if:
- Accuracy below 45%
- Final loss above 0.8
- Loss didn't decrease by at least 20%

**Backtest Gate** - Mark as failed if:
- Win rate below 45%
- Max drawdown above 40%
- Sharpe ratio below -0.5

These thresholds are configurable and intentionally loose for MVP. We want to gather data on what fails before tightening them.

### Budget Enforcement

Before invoking the agent, the trigger checks if daily budget is exceeded. If so, it logs the skip and waits until the next day.

---

## Strategy Designer Agent

### What It Does

The agent is responsible for creative work:
- Designing novel strategy configurations
- Choosing training/backtest data splits
- Assessing results and writing explanations

It is NOT responsible for:
- Checking operation status (trigger does this)
- Applying quality gates (trigger does this)
- Deciding whether to proceed (trigger does this)

### Why Claude Opus

We use Opus rather than Sonnet for the agent because:
1. Strategy design is a creative task requiring high reasoning capability
2. Invocations are infrequent (a few per cycle, cycles take 30+ minutes)
3. Quality of strategy design directly impacts research value
4. Cost difference is negligible given low invocation frequency

### Agent Context

When invoked, the agent receives:
- **Trigger reason** - Why it's being invoked
- **Session state** - Current session details
- **Recent strategies** - Last 5 strategies tried (names, types, outcomes)
- **Results** - Training or backtest results (if applicable)

This context is injected by the trigger service, so the agent doesn't need to fetch it.

### Agent Outputs

The agent produces:
- **Strategy YAML** - Saved to `strategies/` folder
- **State updates** - Phase transitions, operation IDs
- **Assessment** - Text explanation of results (when assessing)

All outputs go through MCP tools, which log actions and update the database.

---

## State Machine

The system follows a simple state machine:

```
IDLE ──▶ DESIGNING ──▶ TRAINING ──▶ [gate] ──▶ BACKTESTING ──▶ [gate] ──▶ IDLE
                           │                        │
                           ▼                        ▼
                      (gate fail)              (gate fail)
                           │                        │
                           └────────▶ IDLE ◀────────┘
```

### State Transitions

| From | To | Triggered By |
|------|----|--------------|
| IDLE | DESIGNING | Trigger: start_new_cycle |
| DESIGNING | TRAINING | Agent: starts training |
| TRAINING | BACKTESTING | Trigger: training completed + gate passed |
| TRAINING | IDLE | Trigger: training failed or gate failed |
| BACKTESTING | ASSESSING | Trigger: backtest completed + gate passed |
| BACKTESTING | IDLE | Trigger: backtest failed or gate failed |
| ASSESSING | IDLE | Agent: assessment complete |

### Session Outcomes

Each session ends with one of these outcomes:
- `success` - Full cycle completed
- `failed_design` - Agent couldn't create valid strategy
- `failed_training` - Training operation failed
- `failed_training_gate` - Training metrics below threshold
- `failed_backtest` - Backtest operation failed
- `failed_backtest_gate` - Backtest metrics below threshold
- `failed_assessment` - Agent couldn't complete assessment

---

## Data Storage

### Why PostgreSQL

We use PostgreSQL (not SQLite, not files) because:
1. KTRDR already uses PostgreSQL
2. ACID guarantees for state consistency
3. JSONB support for flexible schema
4. Easy querying for metrics and debugging

### Tables Overview

| Table | Purpose |
|-------|---------|
| `agent_sessions` | One row per research cycle |
| `agent_actions` | Log of every tool call |
| `agent_triggers` | Log of every trigger check |
| `agent_metrics` | Aggregated metrics per cycle |
| `agent_budget` | Daily budget tracking |

See `ref_database_schema.md` for full definitions.

### Data Flow

1. **Trigger fires** → Row in `agent_triggers`
2. **Session starts** → Row in `agent_sessions`
3. **Agent acts** → Rows in `agent_actions`
4. **Session ends** → Row in `agent_metrics`, session updated
5. **Budget updated** → Row in `agent_budget` updated

---

## MCP Tools

### Existing Tools (from KTRDR)

The agent uses these existing MCP tools:
- `get_available_indicators()` - List indicators
- `get_available_symbols()` - List symbols with data
- `start_training(...)` - Start training operation
- `start_backtest(...)` - Start backtest operation (needs to be added)
- `get_operation_status(...)` - Check operation status

### New Tools (for agent system)

We need to add these MCP tools:
- `get_agent_state(session_id)` - Get session state
- `update_agent_state(...)` - Update session state
- `save_strategy_config(name, config)` - Save strategy YAML
- `get_recent_strategies(n)` - Get recent strategy summaries

### Tool Logging

All MCP tool calls are logged to `agent_actions` with:
- Tool name and arguments
- Result (success/failure)
- Token counts for cost tracking

---

## CLI Interface

### Design Philosophy

The CLI provides visibility into the agent system for:
- **Debugging** - What went wrong?
- **Monitoring** - Is it working?
- **Control** - Pause/resume operation

### Key Commands

| Command | Purpose |
|---------|---------|
| `ktrdr agent status` | Current cycle + recent history + budget |
| `ktrdr agent history` | Detailed cycle history |
| `ktrdr agent session <id>` | Full details for one session |
| `ktrdr agent budget` | Budget status and history |
| `ktrdr agent trigger` | Manually trigger a check |
| `ktrdr agent pause/resume` | Control automatic triggering |

See `ref_cli_commands.md` for full specifications.

---

## Observability

### Context

KTRDR already uses OTEL, Prometheus, Jaeger, and Grafana for telemetry. The agent system must integrate with this existing infrastructure.

**Current gap**: The MCP server is not instrumented for telemetry. This needs to be addressed as part of the agent work.

### What We Need to Observe

| Component | Key Metrics | Traces |
|-----------|-------------|--------|
| **Trigger Service** | Trigger rate, skip reasons, gate pass/fail | Trigger → gate → invocation |
| **MCP Server** | Tool latency, success/error rates, tokens | Full request lifecycle |
| **Agent Workflow** | Cycle duration, outcomes, phase timing | End-to-end cycle |
| **Quality Gates** | Pass/fail rates by gate type | Gate evaluation |
| **Budget** | Daily spend, cost per cycle | N/A |

### Dashboard Requirements

The Grafana dashboard should show:
- Current cycle status (phase, duration)
- Recent outcomes (success/failure breakdown)
- Quality gate effectiveness
- Cost tracking (daily spend, trend)
- System health (error rates, latencies)

### Implementation Scope

1. **Instrument MCP server** - Add OTEL spans and Prometheus metrics
2. **Instrument trigger service** - Spans and metrics for trigger loop
3. **Create dashboard** - Agent-specific Grafana dashboard
4. **Add alerts** - Critical alerts for stuck agent, budget exhaustion

See `ref_observability.md` for detailed metrics definitions, span structures, and dashboard specifications.

---

## Recoverability

### Checkpointing Integration

KTRDR has checkpointing for training and backtesting operations. The agent system should leverage this:

- **Training checkpoints** - If training is interrupted, can resume from last checkpoint
- **Backtest checkpoints** - If backtest is interrupted, can resume

The trigger service should detect checkpoint-resumable operations and continue them rather than failing the cycle.

### State Recovery

All agent state is in PostgreSQL:
- Sessions table tracks current phase
- Operation IDs link to KTRDR async operations
- No in-memory state to lose

If the trigger service restarts:
1. Query for active sessions
2. Check operation status for each
3. Resume normal trigger loop

### Failure Modes

| Failure | Recovery |
|---------|----------|
| Agent invocation fails | Log error, mark session failed, start fresh |
| Training operation fails | Check if checkpoint exists; if yes, retry; if no, fail session |
| Backtest operation fails | Check if checkpoint exists; if yes, retry; if no, fail session |
| MCP tool fails | Retry 3x with backoff, then fail |
| Database unavailable | Trigger service waits and retries |

---

## Cost Model

### Token Estimates

Using Claude Opus 4.5 pricing ($5/MTok input, $25/MTok output):
- Typical invocation: ~3K input, ~2K output ≈ $0.065
- Invocations per successful cycle: ~3 (design, post-training, assessment)
- Cost per cycle: ~$0.20

With a $5/day budget, we can run **~25 cycles/day** - plenty of headroom for experimentation.

### Cost Tracking

- Each agent invocation logs tokens to `agent_actions`
- Trigger service updates `agent_budget` after each invocation
- CLI shows budget status (`ktrdr agent budget`)

### Budget Enforcement

- Trigger checks budget before invoking agent
- Keeps $0.10 buffer (don't spend the last bit)
- Resets daily at midnight UTC

---

## Error Handling

### Retry Policy

| Operation | Retries | Backoff |
|-----------|---------|---------|
| MCP tool calls | 3 | Exponential (2s base) |
| KTRDR API calls | 3 | Exponential (2s base) |
| Agent invocation | 1 | None |

### Failure Recovery

If something fails:
1. Error is logged with full context
2. Check if operation has checkpoint (for training/backtest)
3. If checkpoint exists, retry from checkpoint
4. If no checkpoint or retry fails, mark session with appropriate outcome
5. Session resets to IDLE
6. Next trigger starts a fresh cycle

### Checkpoint-Aware Recovery

The trigger service should check for resumable checkpoints:
- Query KTRDR for operation checkpoint status
- If checkpoint exists and operation was interrupted, resume it
- Track retry count to avoid infinite retry loops

---

## Requirements for KTRDR

### Existing Capabilities (confirmed via MCP_TOOLS.md)

- ✅ `start_training` - Start training operation
- ✅ `get_operation_status` - Check operation status
- ✅ `get_operation_results` - Get results
- ✅ `get_available_indicators` - List indicators
- ✅ `get_available_symbols` - List symbols

### Needed Additions

| Need | Description | Complexity |
|------|-------------|------------|
| `start_backtest` MCP tool | Start backtest operation via MCP (may already exist) | Low - MCP tools are proxies to APIs |
| Early stopping config | Training API should support early stopping parameters | Unknown - may already exist |
| Backtest date ranges | Need to specify start/end dates for backtest | Low |
| **MCP server telemetry** | OTEL instrumentation for all MCP tool handlers | Medium |

### MCP Server Instrumentation

The MCP server currently has no telemetry. We need to add:
- OTEL spans for each tool call
- Prometheus metrics for tool usage
- Error tracking and logging
- Trace context propagation to backend

This is a prerequisite for proper observability of the agent system.

---

## Security Considerations

### Budget Protection

- Hard limit enforced at trigger level
- Can't be bypassed by agent

### Strategy Validation

- Schema validation before saving
- Invalid YAML rejected, cycle failed

### No Credential Access

- Agent doesn't have direct database access
- All access through MCP tools
- Tools only expose necessary operations

---

## Testing Strategy

### Unit Tests

- Quality gate functions (threshold checks)
- Budget calculations
- State transition logic

### Integration Tests

- Trigger → Agent → MCP → KTRDR flow
- Full cycle completion
- Failure handling

### Manual Validation

- Run a complete cycle manually
- Verify CLI shows correct state
- Check all tables are populated correctly

---

## Summary

The MVP design prioritizes simplicity while integrating with KTRDR's existing infrastructure:

1. **Deterministic trigger** handles polling (zero LLM cost)
2. **Single agent** handles creative work (Opus 4.5 for quality)
3. **Quality gates** prevent wasted compute
4. **Budget enforcement** prevents cost overruns (~25 cycles/day capacity)
5. **Full observability** via OTEL/Prometheus/Jaeger/Grafana
6. **Checkpointing** enables recovery from interrupted operations
7. **CLI visibility** for debugging and monitoring

**Key integration work:**
- Instrument MCP server with OTEL (currently uninstrumented)
- Leverage existing checkpointing for training/backtesting
- Add agent-specific Grafana dashboard

This proves the core loop works before adding learning, memory, or multiple agents.

---

*Status: Ready for Review*
