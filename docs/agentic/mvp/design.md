# MVP Design: Autonomous Strategy Designer

**Status**: v2 - Operations-Only Architecture
**Last Updated**: 2025-12-12

---

## Purpose

Build an autonomous research system that designs, trains, and evaluates trading strategies without human intervention. The system runs continuously, learning from each cycle to improve over time.

**This document describes *what* we're building and *why*. For implementation details, see [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md).**

---

## Design Goals

1. **Zero-cost polling** - Status checks should not consume LLM tokens
2. **Observable** - Full telemetry via OTEL/Prometheus/Jaeger/Grafana
3. **Recoverable** - Failures don't lose work; operations can be cancelled cleanly
4. **Cost-controlled** - Daily budget prevents runaway spending
5. **Simple** - Minimum components to prove the loop works
6. **Battle-tested patterns** - Reuse existing KTRDR infrastructure (OperationsService)

---

## Core Concept: Research Cycles

The system runs **research cycles**. Each cycle:

1. **Design** - LLM creates a novel strategy configuration
2. **Train** - System trains a neural model on the strategy
3. **Backtest** - System evaluates the trained model on held-out data
4. **Assess** - LLM evaluates results and records learnings

A cycle is a single unit of work. It either completes successfully or fails. There's no partial state to manage.

```
┌─────────────────────────────────────────────────────────────┐
│                     Research Cycle                          │
│                                                             │
│   Design ──▶ Train ──▶ Backtest ──▶ Assess ──▶ Complete    │
│                                                             │
│   Any step can fail, cancelling the entire cycle            │
└─────────────────────────────────────────────────────────────┘
```

---

## State Management: Operations Only

### The Key Insight

KTRDR already has a battle-tested system for tracking async operations: `OperationsService`. Training, backtesting, and data loading all use it. It handles:

- Progress tracking
- Cancellation
- Status queries
- Error handling

**We use the same system for research cycles.** One operation per cycle. No separate database. No synchronization bugs.

### State Machine

```
IDLE ──▶ DESIGNING ──▶ TRAINING ──▶ BACKTESTING ──▶ ASSESSING ──▶ COMPLETE
              │            │              │              │
              └────────────┴──────────────┴──────────────┴──▶ FAILED
```

- **IDLE**: No active operation. Ready to start a new cycle.
- **DESIGNING**: LLM is creating a strategy. Operation is RUNNING.
- **TRAINING**: Model training in progress. Same operation, phase updated.
- **BACKTESTING**: Backtest running. Same operation, phase updated.
- **ASSESSING**: LLM evaluating results. Same operation, phase updated.
- **COMPLETE**: Cycle finished successfully. Operation COMPLETED.
- **FAILED**: Something went wrong. Operation FAILED with reason.

**Phase is metadata on the operation, not a separate state store.**

### Cancellation

Cancel a cycle = cancel the operation. Standard `cancel_operation()` call. The running task gets `CancelledError`, cleans up, done. No orphans. No sync issues.

---

## System Components

### Overview

| Component | Responsibility |
|-----------|---------------|
| **AgentService** | Orchestrates research cycles using OperationsService |
| **AnthropicAgentInvoker** | Calls Claude API for design and assessment phases |
| **ToolExecutor** | Executes tools (save_strategy, start_training, etc.) |
| **OperationsService** | Tracks operation status, progress, cancellation |

### Why NOT a Separate Database?

The original design used PostgreSQL tables for session state. This caused problems:

1. **Two sources of truth** - Session DB and OperationsService had to stay in sync
2. **Orphan sessions** - Operation disappears, session stuck
3. **Orphan operations** - Session cancelled, operations keep running
4. **Complex code** - Parent/child relationships, lifecycle trackers

By using only OperationsService, we eliminate an entire class of bugs.

---

## Trigger Service

### What It Does

The trigger service is a deterministic Python component. It checks whether there's work to do and if so, starts a research cycle.

**Key insight**: By making the trigger deterministic, we ensure that status polling costs zero tokens. The LLM is only invoked when there's actual work.

### Trigger Logic

```python
async def check_and_trigger():
    # Is there an active cycle?
    active = get_active_research_operation()
    if active:
        return {"triggered": False, "reason": "cycle_in_progress"}

    # Is budget available?
    if not budget_available():
        return {"triggered": False, "reason": "budget_exhausted"}

    # Start a new cycle
    operation_id = await start_research_cycle()
    return {"triggered": True, "operation_id": operation_id}
```

### Quality Gates

Before proceeding to the next phase, simple threshold checks:

**Training Gate** - Skip backtest if:
- Accuracy below 45%
- Final loss above 0.8
- Loss didn't decrease by at least 20%

**Backtest Gate** - Mark as failed if:
- Win rate below 45%
- Max drawdown above 40%
- Sharpe ratio below -0.5

These are configurable and intentionally loose for MVP.

---

## Strategy Designer Agent

### What It Does

The agent (Claude via Anthropic API) handles creative work:
- Designing novel strategy configurations
- Choosing indicators, fuzzy sets, model architecture
- Assessing results and recording learnings

### What It Does NOT Do

- Check operation status (trigger does this)
- Apply quality gates (trigger does this)
- Decide whether to proceed (trigger does this)
- Track its own state (operations do this)

### Agent Tools

The agent has access to these tools:

| Tool | Purpose |
|------|---------|
| `validate_strategy_config` | Check config before saving |
| `save_strategy_config` | Save strategy YAML to disk |
| `get_available_indicators` | List available indicators |
| `get_available_symbols` | List symbols with data |
| `get_recent_strategies` | See what was tried before |
| `start_training` | Kick off model training |
| `start_backtest` | Kick off backtesting |

### Why Claude Opus

We use Opus rather than Sonnet because:
1. Strategy design is a creative task requiring high reasoning
2. Invocations are infrequent (a few per cycle)
3. Quality of design directly impacts research value
4. Cost difference is negligible at low frequency

---

## CLI Interface

### Commands

| Command | Purpose |
|---------|---------|
| `ktrdr agent status` | Current cycle status |
| `ktrdr agent trigger` | Manually start a cycle |
| `ktrdr agent cancel <op_id>` | Cancel active cycle |
| `ktrdr operations list --type AGENT_RESEARCH` | List recent cycles |
| `ktrdr operations status <op_id>` | Detailed cycle info |

### Design Philosophy

The CLI provides visibility for debugging and monitoring. Since cycles are just operations, we reuse the existing operations CLI where possible.

---

## Observability

### What We Need to Observe

| Component | Key Metrics |
|-----------|-------------|
| **Research Cycles** | Cycle duration, outcomes, phase timing |
| **Quality Gates** | Pass/fail rates by gate type |
| **Agent Invocations** | Token usage, latency, success rate |
| **Budget** | Daily spend, cost per cycle |

### Integration

KTRDR already uses OTEL, Prometheus, Jaeger, and Grafana. Research cycles integrate with this:

- Traces: Full cycle from trigger to completion
- Metrics: Cycle counts, durations, outcomes
- Dashboards: Agent-specific Grafana dashboard

---

## Cost Model

### Token Estimates (Claude Opus)

- Typical invocation: ~3K input, ~2K output ≈ $0.065
- Invocations per successful cycle: ~3 (design, training check, assessment)
- Cost per cycle: ~$0.20

With a $5/day budget: **~25 cycles/day** capacity.

### Budget Enforcement

- Check budget before invoking agent
- Track tokens per invocation
- Reset daily at midnight UTC

---

## Error Handling

### Failure Modes

| Failure | Recovery |
|---------|----------|
| Agent invocation fails | Mark cycle failed, start fresh next trigger |
| Training fails | Mark cycle failed, start fresh |
| Backtest fails | Mark cycle failed, start fresh |
| Budget exhausted | Wait until tomorrow |
| Cancellation requested | Clean shutdown, mark cancelled |

### No Partial Recovery

For MVP, we don't checkpoint within cycles. If something fails, the whole cycle fails and we start fresh. This is simpler and sufficient for proving the concept.

---

## What We're NOT Building (MVP Scope)

- **Learning across cycles**: Agent doesn't remember what worked (future feature)
- **Multiple concurrent cycles**: One at a time
- **Checkpoint recovery**: Failed cycles restart from scratch
- **Auto-retry**: Manual trigger after failure
- **Budget alerts**: Just hard limits

These can be added after the basic loop works.

---

## Success Criteria

The MVP is successful when:

1. System can run a complete cycle autonomously (design → train → backtest → assess)
2. Cycles appear in operations list with correct status
3. Cancellation works cleanly
4. Budget enforcement prevents overspending
5. Grafana dashboard shows cycle metrics
6. CLI provides visibility into system state

---

## Reference Documents

- [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md) - Technical implementation details
- [ref_agent_prompt.md](ref_agent_prompt.md) - Agent system prompt
- [ref_cli_commands.md](ref_cli_commands.md) - CLI specifications
- [ref_observability.md](ref_observability.md) - Metrics and dashboard specs

---

*Status: Ready for Implementation*
