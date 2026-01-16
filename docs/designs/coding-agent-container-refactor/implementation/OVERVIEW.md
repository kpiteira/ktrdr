# Coding Agent Container Refactor: Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Rename | 8 | Existing orchestrator tests pass with new names | ⏳ |
| M2 | Environment Validation | 3 | Clear errors when prerequisites missing | ⏳ |
| M3 | Docker Run with Volume Mount | 5 | Claude can curl sandbox API from container | ⏳ |
| M4 | Cleanup | 4 | Full orchestrator flow uses CLI sandbox | ⏳ |

## Dependency Graph

```
M1 (Rename) → M2 (Validation) → M3 (Docker Run) → M4 (Cleanup)
```

Linear progression - each milestone builds on the previous.

## Reference Documents

- Design: [../DESIGN.md](../DESIGN.md)
- Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Validation: [../SCENARIOS.md](../SCENARIOS.md)

## Key Decisions (from validation)

1. **Orchestrator uses `pwd`** - No path discovery, validate repo root with active sandbox
2. **No environment variables** - Claude reads `/workspace/.env.sandbox`
3. **Docker run, not compose** - Direct `docker run -v {pwd}:/workspace`
4. **Remove docker socket** - Container can't control Docker (security)
5. **No health pre-check** - Claude discovers and reports issues

## Files Changed Summary

### Renames (M1)

| Before | After |
|--------|-------|
| `orchestrator/sandbox.py` | `orchestrator/coding_agent_container.py` |
| `orchestrator/tests/test_sandbox.py` | `orchestrator/tests/test_coding_agent_container.py` |
| `scripts/sandbox-*.sh` | `scripts/coding-agent-*.sh` |
| `deploy/environments/sandbox/` | `deploy/environments/coding-agent/` |
| `deploy/docker/sandbox/` | `deploy/docker/coding-agent/` |

### New Code (M2-M3)

| File | Purpose |
|------|---------|
| `orchestrator/environment.py` | `validate_environment()` function |
| `orchestrator/tests/test_environment.py` | Tests for validation |

### Modified (M3)

| File | Change |
|------|--------|
| `orchestrator/coding_agent_container.py` | `start()` uses `docker run`, accepts `code_folder` |
| `orchestrator/milestone_runner.py` | Call `validate_environment()`, pass path to container |
| `orchestrator/cli.py` | Call `validate_environment()` |

### Removed (M3-M4)

| File | Reason |
|------|--------|
| Docker socket mount in container | No longer needs Docker access |
| Named volume for workspace | Now mounts code folder directly |
