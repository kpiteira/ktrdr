# Isolated Development Sandbox: Implementation Plan

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md)
- **Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Validation:** [../VALIDATION.md](../VALIDATION.md)

---

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [Compose Setup](M1_compose-setup.md) | 4 | Two stacks on different ports respond | ⏳ |
| M2 | [CLI Core](M2_cli-core.md) | 7 | `create → up → destroy` cycle works | ⏳ |
| M3 | [Startability Gate](M3_startability-gate.md) | 5 | Health checks shown, status displays URLs | ⏳ |
| M4 | [Auto-Detection](M4_auto-detection.md) | 4 | CLI auto-targets correct backend | ⏳ |
| M5 | [Shared Data](M5_shared-data.md) | 3 | `init-shared` populates shared directory | ⏳ |
| M6 | [Merge](M6_merge.md) | 4 | Default ports work after merge | ⏳ |
| M7 | [Documentation](M7_documentation.md) | 3 | Setup docs complete, edge cases handled | ⏳ |

**Total Tasks:** 30

**Parallelization:** M5 can run in parallel with M3/M4 after M2 completes.

---

## Dependency Graph

```
M1 (Compose Setup)
 │
 └─► M2 (CLI Core)
      │
      ├─► M3 (Startability Gate)
      │    │
      │    └─► M4 (Auto-Detection)
      │
      └─► M5 (Shared Data)
           │
           └─► M6 (Merge)
                │
                └─► M7 (Documentation)
```

**Critical Path:** M1 → M2 → M3 → M4 → M6 → M7

M5 (Shared Data) can run in parallel with M3/M4 after M2 is complete.

---

## Architecture Consistency Check

| Pattern (from Architecture) | Implemented In | Verified |
|-----------------------------|----------------|----------|
| CLI Subcommand | M2: Tasks 2.1-2.6 | ⏳ |
| Pool-Based Ports | M2: Task 2.1 | ⏳ |
| Instance Registry | M2: Task 2.2 | ⏳ |
| Startability Gate | M3: Tasks 3.1-3.2 | ⏳ |
| Directory Detection | M4: Tasks 4.1-4.2 | ⏳ |
| Two-File Strategy | M1: Task 1.1, M6: Tasks 6.1-6.3 | ⏳ |

---

## Key Files Created/Modified

### New Files

| File | Milestone | Purpose |
|------|-----------|---------|
| `docker-compose.sandbox.yml` | M1 | Parameterized compose for sandboxes |
| `ktrdr/cli/sandbox.py` | M2 | Sandbox subcommand group |
| `ktrdr/cli/sandbox_ports.py` | M2 | Port allocation logic |
| `ktrdr/cli/sandbox_registry.py` | M2 | Instance registry management |
| `ktrdr/cli/sandbox_gate.py` | M3 | Startability Gate checks |
| `scripts/verify-sandbox-merge.sh` | M6 | Pre-merge verification |
| `scripts/sandbox-rollback.sh` | M6 | Emergency rollback |

### Modified Files

| File | Milestone | Changes |
|------|-----------|---------|
| `ktrdr/cli/main.py` | M2, M4 | Register sandbox subcommand, add `--port` flag |
| `docker-compose.yml` | M6 | Merge parameterized ports (after verification) |

---

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M1 | Compose changes break existing workflow | Two-file strategy, main compose untouched |
| M2 | Git worktree edge cases | Test with both worktrees and clones |
| M3 | Health checks flaky | Configurable timeouts, retry logic |
| M6 | Merge breaks ktrdr2 | Verification script, rollback script, git tag |

---

## Open Questions (to resolve during implementation)

1. **Compose file location:** Root (`docker-compose.sandbox.yml`) vs `deploy/environments/parallel/`?
   - Leaning: Root for simplicity

2. **Worker count per instance:** Fixed at 4 or configurable?
   - Leaning: Fixed for now, configurable later if needed

3. **Registry cleanup frequency:** On every `list` or explicit command?
   - Leaning: On every `list` (auto-cleanup)
