# Configuration System: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Database Settings | 8 | Backend connects to DB with new settings | Pending |
| M2 | API, Auth & Logging | ~10 | Backend serves requests, logs correctly, traces to Jaeger | Pending |
| M3 | IB & Host Services | ~8 | Backend proxies to host services with new settings | Pending |
| M4 | Workers | ~8 | Worker starts, registers, validates config subset | Pending |
| M5 | Agent & Data | ~6 | Agent reads config, data paths correct | Pending |
| M6 | Docker Compose & CLI | ~4 | Full stack with only `KTRDR_*` names | Pending |
| M7 | Cleanup | ~5 | Zero `metadata.get()`, zero scattered `os.getenv()` | Pending |

## Dependency Graph

```
M1 (Database)
    ↓
M2 (API/Auth/Logging) ──→ M6 (Docker/CLI)
    ↓                          ↓
M3 (IB/Host Services)         M7 (Cleanup)
    ↓
M4 (Workers)
    ↓
M5 (Agent/Data)
```

M1 must complete first (proves the pattern). M2-M5 can proceed somewhat in parallel but are ordered by dependency depth. M6 updates infrastructure. M7 is final cleanup.

## Architecture Alignment

Every task traces back to these architectural decisions:

| Decision | What It Means for Tasks |
|----------|------------------------|
| D1: Pure Pydantic | All Settings classes inherit `BaseSettings`, no YAML loading |
| D7: Explicit Validation | Only `main.py` and worker entrypoints call `validate_all()` |
| D9: `deprecated_field()` | Any field with deprecated name MUST use the helper |
| D8: `KTRDR_ENV` | Read via `os.getenv()` in validation module, not a Settings field |

## Reference Documents

- Design: [DESIGN.md](../DESIGN.md)
- Architecture: [ARCHITECTURE.md](../ARCHITECTURE.md)
- Validation: [SCENARIOS.md](../SCENARIOS.md)

## Settings Classes by Milestone

| Milestone | Classes | Count |
|-----------|---------|-------|
| M1 | `DatabaseSettings` | 1 |
| M2 | `APISettings`, `AuthSettings`, `LoggingSettings`, `ObservabilitySettings` | 4 |
| M3 | `IBSettings`, `IBHostServiceSettings`, `TrainingHostServiceSettings` | 3 |
| M4 | `WorkerSettings`, `CheckpointSettings`*, `OrphanDetectorSettings`*, `OperationsSettings` | 4 |
| M5 | `AgentSettings`, `AgentGateSettings`, `DataSettings`, `APIClientSettings` | 4 |
| **Total** | | **16** |

*Already exist, need prefix alignment
