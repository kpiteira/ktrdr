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
