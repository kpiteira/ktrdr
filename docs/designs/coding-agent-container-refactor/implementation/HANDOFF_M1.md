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

### Next Task Notes (1.2)
- Rename `tests/test_sandbox.py` → `tests/test_coding_agent_container.py`
- Update all imports from `orchestrator.sandbox` to `orchestrator.coding_agent_container`
- Update class names: `TestSandboxManagerStructure` → `TestCodingAgentContainerStructure`
- Search and replace: `SandboxManager` → `CodingAgentContainer`, `SandboxError` → `CodingAgentError`
