# v2.6 Multi-Research Coordination: Design

## Problem Statement

The current agentic system can only run one research cycle at a time. When a trigger is received while a research is active, it's rejected. In production environments with multiple training and backtest workers, this wastes capacity — workers sit idle while a single research waits in its design or assessment phase (which don't use workers).

We need the system to run multiple concurrent research cycles, utilizing available worker capacity while maintaining simplicity.

---

## Goals

1. **Multiple concurrent researches** — System tracks and advances N research cycles simultaneously
2. **Utilize worker capacity** — If 3 training workers exist, up to 3 researches can train in parallel
3. **Simple coordination** — One polling loop manages all researches (not N separate tasks)
4. **Natural queuing** — When all workers are busy, researches wait; when one frees up, next research proceeds
5. **Preserve existing patterns** — Refactor, don't rebuild; keep operation-based tracking, phase handlers, gates

---

## Non-Goals

1. **Priority scheduling** — All researches are first-come-first-served (future enhancement)
2. **Per-research budget allocation** — Budget remains global and shared
3. **Dynamic worker scaling** — Worker pool is fixed; deploying more is a manual operation
4. **Research isolation** — Researches share memory; no need to isolate in-progress experiments
5. **New coordinator service** — Refactor existing `AgentResearchWorker`, don't create new components

---

## User Experience

### Triggering Multiple Researches

```bash
# First research starts
$ ktrdr agent trigger --brief "Explore RSI variations"
Research triggered: op_abc123

# Second research starts (no longer rejected!)
$ ktrdr agent trigger --brief "Test MACD strategies"
Research triggered: op_def456

# Third research starts
$ ktrdr agent trigger --brief "Multi-timeframe experiment"
Research triggered: op_ghi789
```

### Viewing All Active Researches

```bash
$ ktrdr agent status
Active researches: 3

  op_abc123  training     strategy: rsi_variant_7      (2m 15s)
  op_def456  designing    strategy: -                  (0m 30s)
  op_ghi789  backtesting  strategy: mtf_momentum_1     (1m 45s)

Workers: training 2/3, backtest 1/2
Budget: $3.42 remaining today
```

### Hitting Concurrency Limit

```bash
$ ktrdr agent trigger --brief "Another experiment"
Cannot trigger: at capacity (5 active researches, limit is 5)
Use --force to override limit
```

### Hitting Budget Limit

```bash
$ ktrdr agent trigger --brief "Expensive experiment"
Cannot trigger: daily budget exhausted ($0.12 remaining)
Active researches (2) will complete, but no new triggers accepted.
Use --force to override budget check
```

### Cancelling Individual Research

```bash
$ ktrdr agent cancel op_abc123
Research cancelled: op_abc123

$ ktrdr agent status
Active researches: 2
  op_def456  training     strategy: macd_cross_1       (1m 20s)
  op_ghi789  assessing    strategy: mtf_momentum_1     (2m 30s)
```

---

## Key Decisions

### Decision 1: Single Coordinator Loop

**Choice:** One polling loop iterates through all active researches, advancing each if possible.

**Alternatives considered:**
- Separate asyncio task per research (current pattern, but N tasks)
- Event-driven with message queue (Redis Streams)

**Rationale:**
- Simpler to reason about — one loop, one place to debug
- Lower overhead — no task coordination needed
- Matches Karl's explicit preference for simplicity
- We won't have many researches (likely <10), so polling is fine

### Decision 2: Concurrency Limit from Worker Pool

**Choice:** Max active researches = sum(training_workers + backtest_workers) + 1

**Alternatives considered:**
- Hard-coded limit (e.g., 5)
- No limit (let workers queue naturally)
- Separate limits per phase

**Rationale:**
- Workers are the natural bottleneck
- +1 buffer allows one research in design/assessment while workers are fully utilized
- Derived limit adapts automatically when workers are added/removed

### Decision 3: Shared Budget, Complete In-Progress

**Choice:** Budget is global. When exhausted, reject new triggers but allow active researches to complete (assessment can exceed budget).

**Alternatives considered:**
- Per-research budget allocation
- Hard stop when budget hits zero
- Reserve budget for in-progress researches

**Rationale:**
- Simple — no budget partitioning complexity
- Graceful — researches don't get abandoned mid-cycle
- Assessment is cheap (one LLM call) — acceptable overage

### Decision 4: Refactor AgentResearchWorker, Don't Replace

**Choice:** Modify `AgentResearchWorker.run()` to iterate through multiple operations instead of tracking one.

**Alternatives considered:**
- New `MultiResearchCoordinator` class
- New orchestration layer above `AgentResearchWorker`

**Rationale:**
- Phase handlers are already stateless (take operation_id, check state, advance)
- Operation metadata already holds all state
- Less code, fewer integration points, same patterns

---

## Open Questions

### Q1: Worker Pool Size Discovery

How does the coordinator know how many workers exist?

**Options:**
- Query worker registry at startup and cache
- Query on each poll cycle (more accurate, slightly more overhead)
- Configuration value (simple but manual)

**Recommendation:** Query registry; it's already available via `get_worker_registry()`.

### Q2: Polling Interval with Multiple Researches

Current interval is 5 seconds. With N researches, should we:
- Keep 5 seconds (simple, but N researches means up to 5*N seconds between checks for any one research)
- Reduce interval (more responsive, but more polling overhead)
- Dynamic interval based on active count

**Recommendation:** Reduce to 2 seconds. With <10 researches, this is still low overhead and keeps things responsive.

### Q3: What Happens on Coordinator Restart?

If the backend restarts mid-research:
- Operations are in PostgreSQL (persisted)
- Coordinator loop restarts and picks up all RUNNING/PENDING AGENT_RESEARCH operations
- Child operations (training, backtest) continue on workers

This should "just work" but needs verification.

---

## Success Criteria

1. **Can trigger multiple researches** — No "active_cycle_exists" rejection
2. **Researches progress concurrently** — Training/backtest phases overlap when workers available
3. **Natural queuing** — When workers busy, researches wait without error
4. **Individual cancel** — Can cancel specific research by operation_id
5. **Status shows all** — CLI displays all active researches with phases
6. **Budget respected** — New triggers rejected when exhausted, in-progress complete
7. **Existing tests pass** — No regression in single-research behavior

---

*Created: 2026-01-19*
*Status: Draft — awaiting review*
