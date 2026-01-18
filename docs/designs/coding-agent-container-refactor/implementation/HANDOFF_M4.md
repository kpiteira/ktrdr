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

---

## Task 4.2 Complete: Update autonomous-coding documentation

**Summary:** Updated all 9 documentation files in `docs/architecture/autonomous-coding/` to use `CodingAgentContainer` and `ktrdr-coding-agent` terminology.

### Files Changed
- `sandbox-orchestrator-handoff.md` — 3 container name references
- `PLAN_M1_sandbox.md` — Container name references
- `PLAN_M2_single_task.md` — `SandboxManager` → `CodingAgentContainer`, container name, config field
- `PLAN_M3_task_loop.md` — `SandboxManager` → `CodingAgentContainer`
- `PLAN_M4_escalation.md` — `SandboxManager` → `CodingAgentContainer`
- `PLAN_M5_e2e.md` — `SandboxManager` → `CodingAgentContainer`
- `PLAN_v2_M4_consolidated_runner.md` — `SandboxManager` → `CodingAgentContainer`
- `ARCHITECTURE.md` — `SandboxManager` → `CodingAgentContainer`, container name
- `ARCHITECTURE_v2_haiku_brain.md` — Container name reference

---

## Task 4.3 Complete: Clean up unused Docker artifacts

**Summary:** Stripped docker-compose.yml to build-only essentials. Removed all runtime configuration (volumes, networks, environment, restart policy) since the orchestrator uses `docker run` with explicit flags.

### What Changed
- Removed 62 lines of runtime config that's now handled by `CodingAgentContainer.start()`
- Updated header comments to clearly explain the file is for building only
- File now contains only: header comments, `build:` block, and `image:` tag

### Next Task Notes (4.4)
- Task 4.4 adds integration test for full orchestrator flow
- Test should mock `subprocess.run` for sandbox status and `CodingAgentContainer` methods
- Use `pytest.mark.integration` decorator
- File: `orchestrator/tests/test_integration.py`
