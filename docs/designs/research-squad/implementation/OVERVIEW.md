---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# Research Squad — Implementation Plan

## Design Reference
- **Design:** `docs/designs/research-squad/DESIGN.md`
- **Architecture:** `docs/designs/research-squad/ARCHITECTURE.md`

## Milestone Summary

| Milestone | Name | Tasks | Dependencies | JTBD |
|-----------|------|-------|-------------|------|
| M1 | Squad Bootstrap + First Cycle | 6 | None | Prove the squad mechanism works: 8 agents discuss, produce an experiment spec, execute it, evaluate results |
| M2 | Autonomous Loop | 4 | M1 | Run N cycles unattended with disk-based state, Ralph loop pattern |
| M3 | Scout + External Research | 3 | M2 | Scout searches the web for papers/techniques and brings actionable insights to the squad |
| M4 | Architect + Capability Pipeline | 3 | M2 | Architect identifies gaps, files GitHub issues, squad gets notified when capabilities are built |
| M5 | Synthesis + Long-Run Evaluation | 3 | M2 | Scribe produces macro synthesis, context management for 50+ experiments, evaluate whether the squad compounds knowledge |

**Total:** 19 tasks across 5 milestones

## Dependency Graph

```
M1 (Bootstrap + First Cycle)
     │
     ▼
M2 (Autonomous Loop)
     │
     ├──────────┬──────────┐
     ▼          ▼          ▼
M3 (Scout)  M4 (Arch)  M5 (Synthesis)
```

M1 → M2 is strictly sequential. M3, M4, M5 can be parallelized after M2.

## Branch Strategy

Each milestone gets its own branch from `main`:
- M1: `impl/research-squad-M1-bootstrap`
- M2: `impl/research-squad-M2-loop`
- M3: `impl/research-squad-M3-scout`
- M4: `impl/research-squad-M4-architect`
- M5: `impl/research-squad-M5-synthesis`

## Key Architectural Constraints

Every task must respect:
1. **Separate agent sessions** — each agent spawned via Agent tool with targeted context, never shared session
2. **Disk-based state** — all knowledge in `.squad/` markdown, no in-memory-only state
3. **Selective context routing** — each agent sees only what it needs (see architecture table)
4. **Best model for all agents** — Opus for every squad member, no downgrades
5. **Coordinator hub** — agents never talk to each other directly, all through Coordinator
6. **Backpressure from reality** — experiments validated by real ktrdr train + backtest, not self-assessment
