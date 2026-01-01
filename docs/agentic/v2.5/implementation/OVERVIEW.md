# v2.5 Agent Reliability: Implementation Plan

## Reference Documents

- Design: [DESIGN.md](../DESIGN.md)
- Architecture: [ARCHITECTURE.md](../ARCHITECTURE.md)

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [Fail Loudly](M1_fail_loudly.md) | 4 | Infrastructure errors → operation FAILED | ⏳ |
| M2 | [Gate Rejection → Memory](M2_gate_rejection_memory.md) | 5 | Gate reject → experiment in memory | ⏳ |
| M3 | [Baby Gates + Brief](M3_baby_gates_brief.md) | 4 | Brief guides design, lax gates pass | ⏳ |
| M4 | [Fix Multi-Symbol](M4_fix_multi_symbol.md) | 3 | Multi-symbol research completes | ⏳ |
| M5 | [Fix Multi-Timeframe](M5_fix_multi_timeframe.md) | 3 | Multi-TF research completes | ⏳ |
| M6 | [Combined Multi](M6_combined_multi.md) | 2 | Multi-symbol + multi-TF together | ⏳ |

## Dependency Graph

```text
M1 (fail loudly)
  ↓
M2 (gate rejection → memory)
  ↓
M3 (baby gates + brief)
  ↓
M4 (multi-symbol) ──┐
  ↓                 │
M5 (multi-TF) ──────┼──→ M6 (combined)
```

## Architecture Alignment

### Core Patterns

| Pattern | Implementation |
|---------|----------------|
| State Machine | Explicit phase transitions in research_worker.py |
| Polling Orchestration | Parent polls child operation status, advances phase when complete |
| Two Failure Types | Infra errors → FAILED (no memory). Gate rejections → ASSESSING (memory) |

### Key Constraints

- Gate rejection transitions to ASSESSING, not FAILED
- Infrastructure errors do NOT record to memory
- AssessmentWorker handles partial results (backtest_result=None)
- Brief is prompt guidance only, no enforcement

---

*Created: 2026-01-01*
