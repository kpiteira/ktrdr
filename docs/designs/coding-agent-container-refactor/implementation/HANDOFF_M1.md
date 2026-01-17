# Milestone 1 Handoff: Rename

## Task 1.1 Complete: Rename orchestrator/sandbox.py

**Summary:** File renamed from `sandbox.py` to `coding_agent_container.py`. All internal references updated.

### Key Changes
- `SandboxManager` → `CodingAgentContainer`
- `SandboxError` → `CodingAgentError`
- Module and method docstrings updated to reference "coding agent container"

### Important Notes
- **container_name default remains `ktrdr-sandbox`** - This is intentional per the plan; it will be changed in M3
- Tests in `test_sandbox.py` will fail until Task 1.2 updates them
- Git recognizes rename (history preserved)

---

## Task 1.2 Complete: Rename test file

**Summary:** Test file renamed and all references updated. All 30 tests pass.

### Changes Made
- `tests/test_sandbox.py` → `tests/test_coding_agent_container.py`
- All imports updated to `orchestrator.coding_agent_container`
- Test class names updated: `TestSandboxExec` → `TestCodingAgentContainerExec`, etc.
- All `SandboxManager`/`SandboxError` references updated

---

## Task 1.3 Complete: Update orchestrator/runner.py imports

**Summary:** Updated imports and all parameter/variable names. Also updated test_runner.py to match. 44 tests pass.

### Changes Made
- Import: `orchestrator.sandbox.SandboxManager` → `orchestrator.coding_agent_container.CodingAgentContainer`
- 4 functions updated: `run_task`, `run_task_with_escalation`, `run_e2e_tests`, `apply_e2e_fix`
- Parameter names: `sandbox: SandboxManager` → `container: CodingAgentContainer`
- All `sandbox.invoke_claude*` calls → `container.invoke_claude*`
- Module docstring updated

### Gotcha
- **test_runner.py also needed updates** - the tests use keyword arguments (`sandbox=`) and variable names (`sandbox = MagicMock()`) that needed changing to `container`

### Next Task Notes (1.4)
- Update `orchestrator/milestone_runner.py`
- Similar pattern: import, instantiation, function parameters, usages

---

## Task 1.4 Complete: Update orchestrator/milestone_runner.py imports

**Summary:** Updated imports and all parameter/variable names. Also updated test_milestone_runner.py mocks to match. 32 tests pass.

### Changes Made
- Import: `orchestrator.sandbox.SandboxManager` → `orchestrator.coding_agent_container.CodingAgentContainer`
- Variable: `sandbox = SandboxManager(...)` → `container = CodingAgentContainer(...)`
- Functions updated: `run_milestone`, `_get_current_branch`, `create_milestone_pr`
- Parameter names: `sandbox: SandboxManager` → `container: CodingAgentContainer`
- All `sandbox.` usages → `container.`
- Docstrings updated ("sandbox" → "coding agent container")

### Gotcha
- **test_milestone_runner.py also needed updates** - Many mock patches (`patch("orchestrator.milestone_runner.SandboxManager")`) and variable names (`sandbox: MagicMock`) needed changing
- **Import ordering issues from earlier tasks** - Had to run `ruff --fix` on runner.py and test_coding_agent_container.py to fix import sorting issues introduced in Tasks 1.2 and 1.3

### Next Task Notes (1.5)
- Update `orchestrator/cli.py`
- Similar pattern: import, instantiation, usages
- Line 28 has the import, line 124 and 382 have instantiations

---

## Task 1.5 Complete: Update orchestrator/cli.py imports

**Summary:** Updated imports and all variable names. Also updated 4 mock patches in test_cli.py. 53 tests pass.

### Changes Made
- Import: `orchestrator.sandbox.SandboxManager` → `orchestrator.coding_agent_container.CodingAgentContainer`
- `format_tool_call` import path also changed
- Variable: `sandbox = SandboxManager()` → `container = CodingAgentContainer()`
- Two instantiation sites updated (lines 124 and 382)
- Comment updated: "Create sandbox for PR creation" → "Create container for PR creation"
- 4 mock patches in test_cli.py updated

### Next Task Notes (1.6)
- Task 1.6 is "Update test mocks" but we've already done the mock updates as part of each task
- May be mostly complete; verify no remaining `SandboxManager` patches in test files

---

## Task 1.6 Complete: Update test mocks

**Summary:** Updated remaining test mocks and variable names in test_e2e_runner.py, test_task_runner.py, and test_coding_agent_container.py. Fixed 19 failing tests. All 526 orchestrator tests now pass.

### Changes Made
- **test_e2e_runner.py**: Changed all `sandbox = MagicMock()` to `container = MagicMock()`, updated `sandbox.invoke_claude` to `container.invoke_claude`, changed `sandbox=sandbox` keyword args to `container=container`
- **test_task_runner.py**: Same pattern - variable names, method calls, and positional args updated
- **test_coding_agent_container.py**: Renamed test methods `test_sandbox_manager_*` → `test_coding_agent_container_*` and `test_sandbox_error_*` → `test_coding_agent_error_*`

### Note
Remaining `sandbox` references in test files are intentional:
- `test_config.py`: References to `sandbox_container` config field (unchanged)
- `test_health.py`: References to "sandbox" health check (renamed in later milestone)
- `test_coding_agent_container.py`: Default container_name "ktrdr-sandbox" (changed in M3)

### Next Task Notes (1.7)
- Rename shell scripts: sandbox-*.sh → coding-agent-*.sh
- Update internal container name references from ktrdr-sandbox to ktrdr-coding-agent

---

## Task 1.7 Complete: Rename scripts

**Summary:** Renamed all 4 sandbox scripts and updated all internal references.

### Files Renamed (git mv)
- `sandbox-init.sh` → `coding-agent-init.sh`
- `sandbox-reset.sh` → `coding-agent-reset.sh`
- `sandbox-shell.sh` → `coding-agent-shell.sh`
- `sandbox-claude.sh` → `coding-agent-claude.sh`

### Content Updates
- CONTAINER_NAME: `ktrdr-sandbox` → `ktrdr-coding-agent`
- COMPOSE_FILE path: `sandbox` → `coding-agent`
- Comments: "Sandbox" → "Coding Agent"
- Echo statements: "Sandbox" → "Coding Agent"
- Script references updated to new names

### Next Task Notes (1.8)
- Rename Docker configuration directories
- `deploy/environments/sandbox/` → `deploy/environments/coding-agent/`
- `deploy/docker/sandbox/` → `deploy/docker/coding-agent/`
- Update docker-compose.yml service name, container name, image name, volume names
