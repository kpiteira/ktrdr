# Container Optimization: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Dead Code & Dependency Cleanup | 5 | `make test-unit && make quality` passes | - |
| M2 | Lazy Torch Imports | 4 | Backend starts without torch | - |
| M3 | Split Dockerfiles | 5 | Four images build with correct sizes | - |
| M4 | Canary Validation | 4 | Split images pass canary tests | - |
| M5 | CI/CD Updates | 3 | GitHub Actions builds all images | - |
| M6 | Environment Rollout | 4 | All environments work with split images | - |

## Dependency Graph

```
M1 (cleanup) → M2 (lazy imports) → M3 (dockerfiles) → M4 (canary) → M5 (CI/CD) → M6 (rollout)
```

All milestones are sequential — each builds on the previous.

## Architecture Alignment

### Patterns Implemented

| Pattern | Milestone | Tasks |
|---------|-----------|-------|
| UV Dependency Groups | M1 | 1.3, 1.4 |
| Lazy Imports | M2 | 2.1, 2.2, 2.3 |
| Multi-stage Docker Builds | M3 | 3.1, 3.2, 3.3, 3.4 |
| Worker Startup Validation | M6 | 6.3 |

### Key Decisions (from DESIGN.md)

| Decision | Implemented In |
|----------|----------------|
| D1: Three Container Images | M3, M5 |
| D2: UV Dependency Groups | M1 |
| D3: Lazy Torch Imports | M2 |
| D4: Archive Frontend | M1 |
| D5: Remove Unused Dependencies | M1 |
| D6: Standardize on httpx | M1 |
| D7: CPU-Only Torch for Dev | M3 |
| D8: Worker Startup Validation | M6 |

## Reference Documents

- Design: `../DESIGN.md`
- Architecture: `../ARCHITECTURE.md`
- Validation: `../VALIDATION.md`
- Intent: `../INTENT.md`

## Branch Strategy

All work on a single feature branch: `feature/container-optimization`

Commits after each task, PR after M6 is complete.

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M2 | Import chain not fully broken | Verify with import test before proceeding |
| M3 | UV --frozen with source override | Already tested successfully |
| M4 | Canary environment stale | Task 4.1 audits canary first |
| M5 | Multi-arch build issues | Test locally before CI |
