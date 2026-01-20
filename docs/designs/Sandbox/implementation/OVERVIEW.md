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
| M6 | [Local-Prod](M6_local_prod.md) | 6 | Local-prod `init → up → status` works | ⏳ |
| M7 | [Documentation](M7_documentation.md) | 3 | Setup docs complete, edge cases handled | ⏳ |

**Total Tasks:** 32

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
           └─► M6 (Local-Prod)
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
| Local-Prod Singleton | M6: Tasks 6.1-6.2 | ⏳ |
| Slot 0 Reserved | M6: Task 6.1 | ⏳ |

---

## Key Files Created/Modified

### New Files

| File | Milestone | Purpose |
|------|-----------|---------|
| `docker-compose.sandbox.yml` | M1 | Parameterized compose for sandboxes and local-prod |
| `ktrdr/cli/sandbox.py` | M2 | Sandbox subcommand group |
| `ktrdr/cli/sandbox_ports.py` | M2 | Port allocation logic |
| `ktrdr/cli/sandbox_registry.py` | M2 | Instance registry management |
| `ktrdr/cli/sandbox_gate.py` | M3 | Startability Gate checks |
| `ktrdr/cli/local_prod.py` | M6 | Local-prod subcommand group |
| `ktrdr/cli/instance_core.py` | M6 | Shared instance lifecycle logic |
| `scripts/setup-local-prod.sh` | M6 | Bootstrap script for local-prod setup |

### Modified Files

| File | Milestone | Changes |
|------|-----------|---------|
| `ktrdr/cli/main.py` | M2, M4, M6 | Register sandbox/local-prod subcommands, add `--port` flag |
| `docker-compose.sandbox.yml` | M6 | Comment out extra workers, ensure mcp-local included |

---

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M1 | Compose changes break existing workflow | Two-file strategy, main compose untouched |
| M2 | Git worktree edge cases | Test with both worktrees and clones |
| M3 | Health checks flaky | Configurable timeouts, retry logic |
| M6 | Destroy bug (wrong directory) | Registry lookup, not cwd; thorough testing |
| M6 | Code duplication with sandbox | Thin wrappers over instance_core.py |

---

## Open Questions (to resolve during implementation)

1. **Compose file location:** Root (`docker-compose.sandbox.yml`) vs `deploy/environments/parallel/`?
   - Leaning: Root for simplicity

2. **Worker count per instance:** Fixed at 4 or configurable?
   - Leaning: Fixed for now, configurable later if needed

3. **Registry cleanup frequency:** On every `list` or explicit command?
   - Leaning: On every `list` (auto-cleanup)
