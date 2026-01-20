# v2.6 Multi-Research Coordination: Implementation Plan

## Reference Documents

- Design: [../DESIGN.md](../DESIGN.md)
- Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Validation: [../VALIDATION.md](../VALIDATION.md)

---

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Multi-Research Coordinator Loop | 8 | Trigger two researches, both complete | ⏳ |
| M2 | Error Isolation | 3 | One fails, others continue | ⏳ |
| M3 | Worker Queuing | 3 | Natural queuing when workers busy | ⏳ |
| M4 | Individual Cancel | 4 | Cancel specific research | ⏳ |
| M5 | Status and Observability | 3 | Multi-research status display | ⏳ |
| M6 | Coordinator Restart Recovery | 3 | Resume after backend restart | ⏳ |

**Total Tasks:** 24

---

## Dependency Graph

```
M1 (foundation)
 ├── M2 (error isolation)
 │    └── M6 (restart recovery)
 ├── M3 (worker queuing)
 ├── M4 (individual cancel)
 └── M5 (status/observability)
```

M2-M5 can proceed in parallel after M1. M6 depends on M2's error handling patterns.

---

## Architecture Alignment

### Core Patterns

| Pattern | Implementation |
|---------|----------------|
| Single Coordinator Loop | `run()` iterates over `_get_active_research_operations()` |
| Research as State Object | Phase in `op.metadata.parameters["phase"]`, no per-research task |
| Worker-Based Phases | Unchanged TrainingService/BacktestingService |
| In-Process Phases | Track in `_child_tasks` dict |
| Capacity-Based Limiting | `_get_concurrency_limit()` queries WorkerRegistry |

### Key Decisions (from Validation)

- D1: Loop over state, not tasks
- D2: Stateless phase handlers
- D3: Error isolation at iteration level
- D4: Coordinator lifecycle tied to active count
- D5: No new "waiting" phases
- D6: Budget checked only at trigger time

### Ruled Out

- N asyncio tasks per research
- New "waiting for worker" phases
- Mid-cycle budget enforcement
- New coordinator component class

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_POLL_INTERVAL` | `2` | Seconds between coordinator cycles |
| `AGENT_MAX_CONCURRENT_RESEARCHES` | `0` | Manual limit override (0 = calculate) |
| `AGENT_CONCURRENCY_BUFFER` | `1` | Extra slots above worker count |

---

## Branch Strategy

Each milestone on its own branch:
- `feature/v2.6-m1-coordinator-loop`
- `feature/v2.6-m2-error-isolation`
- `feature/v2.6-m3-worker-queuing`
- `feature/v2.6-m4-individual-cancel`
- `feature/v2.6-m5-status-observability`
- `feature/v2.6-m6-restart-recovery`

---

*Created: 2026-01-20*
