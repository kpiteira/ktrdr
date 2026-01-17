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

### Next Task Notes (1.3)
- Update `orchestrator/runner.py`
- Change import on line ~30
- Update function parameters from `sandbox: SandboxManager` to `container: CodingAgentContainer`
- Update all usages of `sandbox.` to `container.`
