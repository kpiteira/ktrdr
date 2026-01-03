# CLI Client Consolidation: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Create Client Module | 6 | Unit tests pass | ⏳ |
| M2 | Migrate Sync Commands | 6 | `ktrdr indicators list` works | ⏳ |
| M3 | Migrate Async Commands | 4 | `ktrdr agent status` works | ⏳ |
| M4 | Migrate Operation Commands | 2 | `ktrdr model train` works | ⏳ |
| M5 | Cleanup | 3 | Old clients deleted | ⏳ |

## Dependency Graph

```
M1 → M2 → M5
  ↘ M3 ↗
     ↘ M4 ↗
```

M2, M3, M4 can run in parallel after M1. M5 requires all migrations complete.

## Reference Documents

- Design: [../DESIGN.md](../DESIGN.md)
- Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md)
