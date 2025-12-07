# MVP: Autonomous Strategy Design Loop

## Document Purpose

This document defines the **scope, architecture, and implementation plan** for the MVP autonomous research system. It focuses exclusively on proving the core loop works.

**Related Documents**:
- `design.md` - Technical design details
- `PLAN_phase*.md` - Implementation plans per phase
- `ref_*.md` - Reference documentation

---

## What MVP Proves

1. A single AI agent can autonomously design valid neuro-fuzzy strategy configurations
2. The trigger → agent → KTRDR pipeline works reliably
3. Quality gates prevent wasted computation on bad strategies
4. We can measure quality, cost, and progress
5. The system operates within budget constraints

## What MVP Explicitly Does NOT Prove

- That the agent generates *winning* strategies (that's icing on the cake)
- That the system learns or improves over time
- That multiple agents can collaborate

---

## Success Criteria

| Metric | Target | How Measured |
|--------|--------|--------------|
| Cycle completion rate | > 80% | Completed cycles / started cycles |
| Valid strategy generation | 100% | All generated YAML passes schema |
| Quality gate effectiveness | > 50% | Strategies passing gates have Sharpe > 0 |
| Daily cost | < $5 | Token usage tracking |
| Unattended operation | 24+ hours | No manual intervention required |

---

## Scope Boundaries

**In MVP**:
- Single agent (Strategy Designer)
- Sequential experiments (one at a time)
- Deterministic trigger layer (zero-cost status checks)
- Quality gates (skip backtest on bad training)
- Basic eval metrics and cost tracking
- Action logging for debugging
- CLI access to understand system state
- Complete creative freedom for agent (no human input on strategy design)

**Deferred to v2+**:

| Feature | Why Deferred | Target Version |
|---------|--------------|----------------|
| Learning/memory | Prove loop works first | v2 |
| Knowledge base | Requires learning foundation | v3 |
| Multiple agents | Single agent must work first | v4 |
| Human approval workflows | Start fully autonomous | v2 |
| Parallel experiments | Sequential is simpler | v2 |
| Nuanced AI quality assessment | Deterministic gates sufficient | v2 |

---

## Core Architecture: The Trigger Pattern

A key insight: **status checking should cost zero tokens**.

### The Problem with Naive Polling

```
Every 5 min: Cron → AI Agent → "Is training done? No? OK bye."
                               (tokens wasted)
```

### The Solution: Deterministic Trigger Layer

```
Every 5 min: Cron → Python Trigger → Check DB/API (free)
                         │
                         ├─ Nothing to do? → Exit (zero cost)
                         │
                         └─ Work needed? → Invoke AI Agent → Do actual work
```

The trigger layer is pure Python. It:
1. Checks operation status (training, backtest) via KTRDR API
2. Applies deterministic quality gates
3. Only invokes the AI agent when there's a decision to make
4. Passes context to agent so it doesn't need to re-fetch
5. Enforces budget caps

---

## State Machine

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
┌──────┐    ┌───────────┐    ┌──────────┐    ┌─────┐      │
│ IDLE │───▶│ DESIGNING │───▶│ TRAINING │───▶│GATE │──────┤
└──────┘    └───────────┘    └──────────┘    └─────┘      │
    ▲                                           │         │
    │                              FAIL ────────┘         │
    │                                                     │
    │       ┌─────────────┐    ┌─────┐                   │
    │       │ BACKTESTING │───▶│GATE │───────────────────┘
    │       └─────────────┘    └─────┘        PASS
    │              ▲               │
    │              │          FAIL │
    │         PASS │               │
    │              └───────────────┘
    │
    └─────────────────────────────────────────────────────┘
                        (cycle complete)
```

---

## Quality Gates

### Training Gate - Skip backtest if:
- Final loss > 0.8 (didn't converge)
- Training accuracy < 45% (worse than random)
- Loss didn't decrease by at least 20%

### Backtest Gate - Mark as failed if:
- Win rate < 45%
- Max drawdown > 40%
- Sharpe ratio < -0.5

These are simple threshold checks - no AI needed.

---

## MVP Phases

### Phase 0: Plumbing Validation (2-3 days)

**Goal**: Prove the trigger → agent → tool → database pipeline works.

**Tasks (7)**: Database tables, MCP tools, trigger service, test prompt, invocation, CLI, E2E test

**Proves**: End-to-end connectivity, MCP tools work, state persists.

**Plan**: `PLAN_phase0_plumbing.md`

---

### Phase 1: Strategy Design Only (2-3 days)

**Goal**: Agent can generate valid strategy YAML configurations.

**Tasks (8)**: Full prompt, validation, save/load tools, indicator/symbol tools, trigger updates, tests

**Proves**: AI can create valid neuro-fuzzy configurations.

**Plan**: `PLAN_phase1_strategy_design.md`

---

### Phase 2: Full Research Cycle (3-4 days)

**Goal**: Complete autonomous design → train → backtest → assess cycle.

**Tasks (9)**: Training/backtest tools, quality gates, full state machine, checkpoint recovery, tests

**Proves**: The full loop runs autonomously with quality gates.

**Plan**: `PLAN_phase2_full_cycle.md`

---

### Phase 3: Eval, Cost & Observability (3-4 days)

**Goal**: We can answer "is this working?" and "what does it cost?"

**Tasks (12)**: Cost tracking, budget enforcement, OTEL instrumentation, Prometheus metrics, Grafana dashboard, alerts, full CLI, tests

**Proves**: System is measurable and operates within budget.

**Plan**: `PLAN_phase3_observability.md`

---

**Total MVP Effort**: ~10-14 days (~80-120 hours)

---

## Database Schema

```sql
-- Agent session state (one row per research cycle)
CREATE TABLE agent_sessions (
    id SERIAL PRIMARY KEY,
    phase VARCHAR(20) NOT NULL DEFAULT 'idle',

    -- Strategy details
    strategy_name VARCHAR(100),
    strategy_config JSONB,

    -- Operation tracking
    training_operation_id VARCHAR(100),
    backtest_operation_id VARCHAR(100),

    -- Results
    training_results JSONB,
    backtest_results JSONB,
    assessment JSONB,

    -- Outcome
    outcome VARCHAR(30),
    failure_reason TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Action log (what did the agent do?)
CREATE TABLE agent_actions (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES agent_sessions(id),
    action_at TIMESTAMPTZ DEFAULT NOW(),
    tool_name VARCHAR(100),
    tool_args JSONB,
    tool_result JSONB,
    tokens_used INT
);

-- Metrics (aggregated per cycle)
CREATE TABLE agent_metrics (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES agent_sessions(id),

    -- Timing
    cycle_started_at TIMESTAMPTZ,
    cycle_completed_at TIMESTAMPTZ,
    cycle_duration_minutes INT,

    -- Quality metrics
    training_accuracy DECIMAL,
    training_loss DECIMAL,
    backtest_sharpe DECIMAL,
    backtest_win_rate DECIMAL,
    backtest_max_drawdown DECIMAL,

    -- Cost
    total_tokens INT,
    estimated_cost_usd DECIMAL,

    -- Outcome
    outcome VARCHAR(30),
    gate_failed VARCHAR(30)
);

-- Trigger log
CREATE TABLE agent_triggers (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES agent_sessions(id),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    trigger_reason VARCHAR(50),
    context JSONB,
    budget_remaining_usd DECIMAL
);
```

---

## Cost Model

### Pricing (Claude Opus 4.5)
- Input: $5 / MTok
- Output: $25 / MTok

### Estimates
- Average invocation: ~3K input, ~2K output ≈ $0.065
- Invocations per successful cycle: ~3 (design, post-training, assessment)
- Cost per cycle: ~$0.20

### Scenarios

| Scenario | Cycles/Day | Daily Cost |
|----------|------------|------------|
| Conservative | 5 | ~$1.00 |
| Moderate | 15 | ~$3.00 |
| Aggressive | 25 | ~$5.00 |

**Budget cap**: $5/day provides significant headroom.

---

## Supported Instruments

MVP focuses on forex pairs with comprehensive data (2005-2025):

| Pair | Timeframes Available |
|------|---------------------|
| EURUSD | 5m, 15m, 30m, 1h, 1d |
| GBPUSD | 5m, 1h, 1d |
| USDJPY | 5m, 1h, 1d |
| AUDUSD | 5m, 1h, 1d |
| EURGBP | 5m, 1h, 1d |
| EURJPY | 5m, 1h, 1d |

Additional: USDCHF, USDCAD, NZDUSD, AUDJPY, EURCHF, GBPJPY

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Early stopping | Include if not complex | Avoid wasting compute |
| Cycle behavior | Immediately start new | Maximize experimentation |
| Assessment output | Structured + text | Machine and human readable |
| Agent context | Include last N strategies | Prevent repetition |
| API failure | Retry 3x then fail cycle | Failures likely semi-permanent |
| Strategy location | `strategies/` folder | Keep with existing |
| CLI focus | Current + recent cycles | Essential visibility |

---

## Agent Freedom

In MVP, the agent has complete creative freedom:
- Chooses strategy type, indicators, fuzzy sets, network architecture
- Chooses training symbol(s) and timeframe(s)
- Chooses backtest symbol/timeframe (must differ from training data)
- Generates creative strategy names
- Writes text explanations for assessments

Multi-symbol and multi-timeframe strategies are allowed.

---

## Data Split Philosophy

Training and backtesting must use different data:
- **Temporal split**: Train on 2005-2018, backtest on 2019+
- **Symbol split**: Train on one symbol, backtest on another

Agent chooses the approach per experiment.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Invalid YAML generated | Medium | Low | Schema validation |
| Training takes too long | Medium | Medium | Small networks, 50 epochs |
| Budget exceeded | Low | Medium | Hard cap in trigger |
| Agent stuck in loop | Medium | Medium | Timeout detection |
| Gates too strict | Medium | Low | Tune based on data |
| Gates too loose | Medium | Medium | Monitor passing Sharpe |
| MCP tools fail | Low | High | Retry logic |

---

## Open Questions

1. **Training duration**: How long does typical training take?
2. **Backtest ranges**: Agent chooses or standard ranges?
3. **Strategy naming**: Auto-generated or agent-chosen?
4. **Concurrency**: When do we need parallel?
5. **Human notification**: When alert a human?

---

*Status: Ready for Implementation*
