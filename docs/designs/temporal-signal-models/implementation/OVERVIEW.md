---
design: docs/designs/temporal-signal-models/DESIGN.md
---

# Temporal Signal Models — Implementation Plan

## Design Reference
- **Design:** `docs/designs/temporal-signal-models/DESIGN.md`
- **Architecture:** `docs/designs/temporal-signal-models/ARCHITECTURE.md`

## Milestone Summary

| Milestone | Name | Tasks | Dependencies | JTBD |
|-----------|------|-------|-------------|------|
| M1 | LSTM/GRU Models + Training | 4 | None | Train a temporal model end-to-end and verify it produces different predictions than MLP |
| M2 | Backtest Integration | 3 | M1 | Run a trained LSTM model through ensemble backtest and measure trades |
| M3 | Comparison Experiment | 2 | M2 | Direct MLP vs LSTM comparison on identical features/labels to answer H_003 |

**Total:** 9 tasks across 3 milestones

## Dependency Graph

```
M1 (LSTM/GRU + Training)
     │
     ▼
M2 (Backtest Integration)
     │
     ▼
M3 (Comparison Experiment)
```

Linear dependency — each milestone builds on the previous.

## Branch Strategy

Each milestone gets its own branch from `main`:
- M1: `impl/temporal-M1-lstm-training`
- M2: `impl/temporal-M2-backtest`
- M3: `impl/temporal-M3-comparison`
