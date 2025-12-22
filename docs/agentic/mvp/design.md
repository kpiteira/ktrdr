# MVP Design: Autonomous Strategy Designer

**Status**: Validated
**Last Updated**: 2025-12-13
**Implementation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details

---

## Purpose

Build an autonomous research system that designs, trains, and evaluates trading strategies without human intervention. The system runs continuously, learning from each cycle to improve over time.

---

## Design Goals

1. **Zero-cost polling** — Status checks don't consume LLM tokens
2. **Observable** — Full telemetry via OTEL/Prometheus/Jaeger/Grafana
3. **Recoverable** — Operations can be cancelled cleanly
4. **Cost-controlled** — Daily budget prevents runaway spending
5. **Simple** — Minimum components to prove the loop works
6. **Battle-tested patterns** — Reuse existing KTRDR infrastructure

---

## Core Concept: Research Cycles

The system runs **research cycles**. Each cycle:

1. **Design** — LLM creates a novel strategy configuration
2. **Train** — System trains a neural model on the strategy
3. **Backtest** — System evaluates the trained model on held-out data
4. **Assess** — LLM evaluates results and records learnings

A cycle is a single unit of work. It either completes successfully or fails.

```text
Design ──▶ Train ──▶ Backtest ──▶ Assess ──▶ Complete
```

---

## Key Architectural Decision: Workers All The Way Down

KTRDR already has battle-tested patterns for async operations. Workers report to OperationsService, support progress tracking, cancellation, and status queries.

**We use the same patterns for everything:**

- The orchestrator (state machine) is a worker
- Design (Claude call) is a worker
- Training uses the existing training worker
- Backtesting uses the existing backtest worker
- Assessment (Claude call) is a worker

This gives us consistent patterns, progress tracking, cancellation, and observability for free.

### Why NOT a Separate Database?

The v1 design used PostgreSQL tables for session state. This caused problems:

- Two sources of truth that had to stay in sync
- Orphan sessions when operations disappeared
- Orphan operations when sessions were cancelled
- Complex lifecycle tracking code

By using only OperationsService and the worker pattern, we eliminate these bugs.

---

## Quality Gates

Before proceeding to the next phase, the orchestrator applies threshold checks:

**Training Gate** — Fail cycle if:

- Accuracy below 45%
- Final loss above 0.8
- Loss didn't decrease by at least 20%

**Backtest Gate** — Fail cycle if:

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

- Check operation status (orchestrator does this)
- Apply quality gates (orchestrator does this)
- Decide whether to proceed (orchestrator does this)
- Track its own state (operations do this)

### Agent Tools

| Tool | Purpose |
|------|---------|
| `validate_strategy_config` | Check config before saving |
| `save_strategy_config` | Save strategy YAML to disk |
| `get_available_indicators` | List available indicators |
| `get_available_symbols` | List symbols with data |
| `get_recent_strategies` | See what was tried before |

The agent does NOT call `start_training` or `start_backtest` directly. The orchestrator handles phase transitions.

### Why Claude Opus

1. Strategy design is a creative task requiring high reasoning
2. Invocations are infrequent (2 per cycle: design + assessment)
3. Quality of design directly impacts research value
4. Cost difference is negligible at low frequency

---

## User Interface

### CLI Commands

| Command | Purpose |
|---------|---------|
| `ktrdr agent status` | Current cycle status |
| `ktrdr agent trigger` | Manually start a cycle |
| `ktrdr agent cancel` | Cancel active cycle |
| `ktrdr operations list --type agent_research` | List recent cycles |

Since cycles are operations, we reuse the existing operations CLI where possible.

---

## Observability

### What We Need to See

| Area | Metrics |
|------|---------|
| **Research Cycles** | Duration, outcomes, phase timing |
| **Quality Gates** | Pass/fail rates by gate type |
| **Agent Invocations** | Token usage, latency, success rate |
| **Budget** | Daily spend, cost per cycle |

KTRDR already uses OTEL, Prometheus, Jaeger, and Grafana. Research cycles integrate with this infrastructure.

---

## Cost Model

### Token Estimates (Claude Opus)

- Typical invocation: ~3K input, ~2K output ≈ $0.065
- Invocations per successful cycle: 2 (design + assessment)
- Cost per cycle: ~$0.15

With a $5/day budget: **~33 cycles/day** capacity.

### Budget Enforcement

- Check budget before starting new cycle
- Track tokens per Claude invocation
- Reset daily at midnight UTC

---

## Error Handling Philosophy

| Failure | Recovery |
|---------|----------|
| Any worker fails | Mark cycle failed, start fresh next trigger |
| Gate fails | Mark cycle failed, start fresh |
| Budget exhausted | Reject trigger until tomorrow |
| Cancellation requested | Cancel current work, mark cycle cancelled |
| Backend restart | Cycle lost (accepted for MVP) |

**No partial recovery for MVP.** If something fails, the whole cycle fails and we start fresh. This is simpler and sufficient for proving the concept.

---

## What We're NOT Building (MVP Scope)

- **Learning across cycles** — Agent doesn't remember what worked
- **Multiple concurrent cycles** — One at a time
- **Checkpoint recovery** — Failed cycles restart from scratch
- **Auto-retry** — Manual trigger after failure
- **Budget alerts** — Just hard limits
- **Restart recovery** — Lost cycles on backend restart

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

- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical implementation details
- [SCENARIOS.md](SCENARIOS.md) — Validated scenarios and key decisions
- [MILESTONES.md](MILESTONES.md) — Implementation milestones
