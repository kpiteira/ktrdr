# Parallel Coding Workflow: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M0 | Agent Deck Trial | 4 | Manual validation | ⏳ |
| M1 | CLI Foundation + Quick Wins | 7 | cli/kinfra-foundation | ⏳ |
| M2 | Spec Workflow | 4 | infra/spec-workflow | ⏳ |
| M3 | Slot Pool Infrastructure | 5 | infra/slot-provisioning | ⏳ |
| M4 | Impl Workflow | 6 | infra/impl-workflow | ⏳ |
| M5 | Done Workflow | 3 | infra/done-workflow | ⏳ |
| M6 | Polish | 4 | Full workflow validation | ⏳ |

**Total Tasks:** ~33

## Dependency Graph

```
M0 (parallel - Agent Deck trial)

M1 (CLI foundation)
  ├─→ M2 (spec workflow)
  └─→ M3 (slot infrastructure)
        └─→ M4 (impl workflow)
              └─→ M5 (done workflow)
                    └─→ M6 (polish)
```

**Notes:**
- M0 runs in parallel with M1-M6 (hands-on research, not code)
- M2 and M3 can run in parallel after M1
- M4 requires both M2 (worktree patterns) and M3 (slot pool)

## Architecture Patterns Implemented

| Pattern | Milestone | Tasks |
|---------|-----------|-------|
| CLI Separation (kinfra vs ktrdr) | M1 | 1.2-1.6 |
| Infrastructure/Code Separation | M3, M4 | 3.1-3.4, 4.1-4.4 |
| Docker Compose Override | M4 | 4.2 |
| Fail-Fast Slot Check (GAP-6) | M4 | 4.1 |
| Graceful Rollback (GAP-7) | M4 | 4.1 |
| JSON Registry v2 | M3 | 3.1 |
| Dirty Worktree Protection (GAP-4) | M5 | 5.1 |
| Branch Reuse | M2, M4 | 2.1, 4.1 |

## Reference Documents

- Design: [DESIGN.md](../DESIGN.md)
- Architecture: [ARCHITECTURE.md](../ARCHITECTURE.md)
- Validation: Completed 2026-02-01 (gap resolutions incorporated)

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M4 | Docker integration complexity | Spike task (4.0) to validate approach |
| M3 | Registry migration from v1 | Backward-compatible read, migrate on write |
| M1 | Breaking existing commands | Deprecation warnings, commands still work |

## E2E Test Strategy

All milestones require **new E2E tests** - the existing test catalog covers operational features (training, backtest, data) but not infrastructure tooling (worktrees, slots, kinfra CLI).

Tests will be designed by e2e-test-architect during implementation:
- `cli/kinfra-foundation` — CLI separation, deprecation warnings
- `infra/spec-workflow` — Spec worktree creation
- `infra/slot-provisioning` — Slot pool infrastructure
- `infra/impl-workflow` — Impl worktree + slot claiming
- `infra/done-workflow` — Cleanup and release
