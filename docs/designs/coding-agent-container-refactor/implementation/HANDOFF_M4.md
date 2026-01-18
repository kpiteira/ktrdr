# Milestone 4 Handoff: Cleanup

## Task 4.1 Complete: Remove orphaned sandbox references

**Summary:** Renamed config field `sandbox_container` to `coding_agent_container` and updated the default value from `ktrdr-sandbox` to `ktrdr-coding-agent`. Updated all usages across orchestrator code.

### Files Changed
- `orchestrator/config.py` — Field renamed and default updated
- `orchestrator/health.py` — 3 usages updated
- `orchestrator/cli.py` — 1 usage updated
- `orchestrator/milestone_runner.py` — 1 usage updated
- `orchestrator/tests/test_config.py` — Test and annotation list updated

### Gotchas
- The `htmlcov/` directory may contain stale references in coverage reports — these are generated files and will be regenerated on next coverage run
- The `__pycache__` directories may also contain stale `.pyc` files — these regenerate automatically

### Next Task Notes (4.2)
- Task 4.2 updates autonomous-coding documentation
- Check `docs/architecture/autonomous-coding/` for files needing updates
- Look for `SandboxManager` → `CodingAgentContainer` and `ktrdr-sandbox` → `ktrdr-coding-agent` updates needed
