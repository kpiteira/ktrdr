# Agent MVP: Implementation Plan Overview

**Status**: Ready for Implementation
**Generated**: 2025-12-13
**Source Documents**: [DESIGN.md](../../agentic/mvp/DESIGN.md), [ARCHITECTURE.md](../../agentic/mvp/ARCHITECTURE.md)

---

## Summary

This plan implements the autonomous research agent in 8 milestones (M0-M7). Each milestone is E2E-testable and builds on the previous.

**Key Principle**: Everything is a worker. The orchestrator (AGENT_RESEARCH) is a worker that spawns child workers.

---

## Milestone Summary

| # | Milestone | Tasks | Key Deliverable | Plan File |
|---|-----------|-------|-----------------|-----------|
| M0 | Branch Cleanup | 8 | Clean `ktrdr/agents/` foundation | [M0_branch_cleanup.md](M0_branch_cleanup.md) |
| M1 | Orchestrator Shell | 9 | State machine with stub workers | [M1_orchestrator.md](M1_orchestrator.md) |
| M2 | Design Worker | 5 | Real Claude design → strategy file | [M2_design_worker.md](M2_design_worker.md) |
| M3 | Training Integration | 4 | Real training + gate | [M3_training.md](M3_training.md) |
| M4 | Backtest Integration | 4 | Real backtest + gate | [M4_backtest.md](M4_backtest.md) |
| M5 | Assessment Worker | 5 | Real Claude assessment → file | [M5_assessment.md](M5_assessment.md) |
| M6 | Cancellation & Errors | 5 | Robust error handling | [M6_cancellation.md](M6_cancellation.md) |
| M7 | Budget & Observability | 6 | Cost control, metrics, dashboard | [M7_observability.md](M7_observability.md) |

**Total Tasks**: 46

---

## Dependency Graph

```
M0: Branch Cleanup
 │
 └──► M1: Orchestrator Shell
       │
       └──► M2: Design Worker
             │
             └──► M3: Training Integration
                   │
                   └──► M4: Backtest Integration
                         │
                         └──► M5: Assessment Worker
                               │
                               └──► M6: Cancellation & Errors
                                     │
                                     └──► M7: Budget & Observability
```

Each milestone requires the previous to be complete. No parallel execution between milestones.

---

## External Dependencies

| Milestone | External Dependency | Status |
|-----------|---------------------|--------|
| M0 | None | — |
| M1 | OperationsService | ✅ Exists |
| M2 | AnthropicAgentInvoker | ✅ Exists (cleaned in M0) |
| M3 | TrainingService | ✅ Exists |
| M4 | BacktestService | ✅ Exists |
| M5 | AnthropicAgentInvoker | ✅ Same as M2 |
| M6 | None | — |
| M7 | Prometheus/Grafana | ✅ Exists |

---

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M1 | State machine complexity | Start with simple linear flow, add edge cases |
| M2 | Claude rate limits | Add retry with backoff |
| M3 | Training takes too long | Use short training config for testing |
| M4 | Backtest data requirements | Ensure test data available |
| M5 | Two Claude calls per cycle | Budget tracking in M7 |
| M6 | Cancellation race conditions | Use 100ms polling, test extensively |
| M7 | Metric cardinality | Keep labels minimal |

---

## Testing Strategy

Each milestone includes:

1. **Unit tests** — Test individual components in isolation
2. **Integration test** — Test milestone capability end-to-end
3. **E2E verification script** — Bash script for manual verification

| Milestone | Unit Tests | Integration Test | E2E Script |
|-----------|------------|------------------|------------|
| M0 | N/A (cleanup) | N/A | ✅ |
| M1 | Task 1.8 | Task 1.9 | ✅ |
| M2 | Task 2.1 | Task 2.5 | ✅ |
| M3 | Tasks 3.1, 3.2 | Task 3.4 | ✅ |
| M4 | Tasks 4.1, 4.2 | Task 4.4 | ✅ |
| M5 | Tasks 5.2, 5.3 | Task 5.5 | ✅ |
| M6 | Task 6.2 | Task 6.5 | ✅ |
| M7 | Tasks 7.1, 7.2 | N/A | ✅ |

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Assessment in MVP? | Yes, include assessment phase |
| Auto-start after completion? | No, manual trigger only for MVP |
| History persistence? | Operations lost on restart (accepted) |

---

## How to Use This Plan

1. **Read the milestone file** before starting work
2. **Complete tasks in order** within each milestone
3. **Run the E2E verification script** after each milestone
4. **Do not proceed** to next milestone until verification passes

For executing individual tasks, use `/ktask` with the milestone file and task number.

---

*Last updated: 2025-12-13*
