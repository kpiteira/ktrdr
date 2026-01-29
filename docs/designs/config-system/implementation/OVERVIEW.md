# Configuration System: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Database Settings | 8 | Backend connects to DB with new settings | Pending |
| M2 | API, Auth & Logging | 12 | Backend serves requests, logs correctly, traces to Jaeger | Pending |
| M3 | IB & Host Services | 9 | Backend proxies to host services with new settings | Pending |
| M4 | Workers | 10 | Worker starts, registers, validates config subset | Pending |
| M5 | Agent & Data | 10 | Agent reads config, data paths correct | Pending |
| M6 | Docker Compose & CLI | 5 | Full stack with only `KTRDR_*` names | Pending |
| M7 | Cleanup | 8 | Zero `metadata.get()`, zero scattered `os.getenv()` | Pending |

## Dependency Graph

```
M1 (Database)
    ↓
M2 (API/Auth/Logging)
    ↓
M3 (IB/Host Services)
    ↓
M4 (Workers)
    ↓
M5 (Agent/Data)
    ↓
M6 (Docker/CLI)
    ↓
M7 (Cleanup)
```

M1 must complete first (proves the pattern). M2-M5 build on each other. M6 updates docker-compose after all Settings classes are defined. M7 is final cleanup and validation.

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
