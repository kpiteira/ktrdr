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
