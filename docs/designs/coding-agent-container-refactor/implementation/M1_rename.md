---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Rename (No Behavior Change)

## Goal

All "sandbox" references in orchestrator context renamed to "coding-agent". Existing tests pass with new names. No behavior change.

## E2E Validation

**Test:** Existing orchestrator tests pass
```bash
cd orchestrator && uv run pytest tests/ -v
```

**Success Criteria:**
- [ ] All tests pass
- [ ] No references to `SandboxManager` or `orchestrator.sandbox` remain
- [ ] Container name in tests is `ktrdr-coding-agent`

---

## Task 1.1: Rename orchestrator/sandbox.py

**File:** `orchestrator/sandbox.py` → `orchestrator/coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Rename the file and update class/exception names inside it.

**Changes:**
- `SandboxManager` → `CodingAgentContainer`
- `SandboxError` → `CodingAgentError`
- Update docstrings to reference "coding agent container" instead of "sandbox"
- Keep `format_tool_call()` helper as-is (it's generic)

**Acceptance Criteria:**
- [ ] File renamed to `coding_agent_container.py`
- [ ] Class is `CodingAgentContainer`
- [ ] Exception is `CodingAgentError`
- [ ] Docstrings updated
- [ ] `container_name` default is still `ktrdr-sandbox` (change in M3)

---

## Task 1.2: Rename orchestrator/tests/test_sandbox.py

**File:** `orchestrator/tests/test_sandbox.py` → `orchestrator/tests/test_coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Rename test file and update all imports and class references.

**Changes:**
- Update all `from orchestrator.sandbox import` → `from orchestrator.coding_agent_container import`
- Update test class names: `TestSandboxManagerStructure` → `TestCodingAgentContainerStructure`
- Update test docstrings

**Acceptance Criteria:**
- [ ] File renamed
- [ ] All imports updated
- [ ] Tests still pass: `uv run pytest orchestrator/tests/test_coding_agent_container.py -v`

---

## Task 1.3: Update orchestrator/runner.py imports

**File:** `orchestrator/runner.py`
**Type:** CODING
**Estimated time:** 15 min

**Description:**
Update imports and type hints to use new names.

**Changes:**
- Line 30: `from orchestrator.sandbox import SandboxManager` → `from orchestrator.coding_agent_container import CodingAgentContainer`
- Update all function signatures: `sandbox: SandboxManager` → `container: CodingAgentContainer`
- Update all usages of `sandbox.` → `container.`

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Parameter names changed from `sandbox` to `container`
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_runner.py -v`

---

## Task 1.4: Update orchestrator/milestone_runner.py imports

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING
**Estimated time:** 15 min

**Description:**
Update imports and usages to new names.

**Changes:**
- Line 35: `from orchestrator.sandbox import SandboxManager` → `from orchestrator.coding_agent_container import CodingAgentContainer`
- Line 145: `sandbox = SandboxManager(` → `container = CodingAgentContainer(`
- Update all function parameters and usages
- Line 496: `_get_current_branch(sandbox:` → `_get_current_branch(container:`

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_milestone_runner.py -v`

---

## Task 1.5: Update orchestrator/cli.py imports

**File:** `orchestrator/cli.py`
**Type:** CODING
**Estimated time:** 15 min

**Description:**
Update imports and usages in CLI module.

**Changes:**
- Line 28: `from orchestrator.sandbox import SandboxManager, format_tool_call` → `from orchestrator.coding_agent_container import CodingAgentContainer, format_tool_call`
- Line 124: `sandbox = SandboxManager()` → `container = CodingAgentContainer()`
- Line 382: Update similar

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_cli.py -v`

---

## Task 1.6: Update test mocks

**File:** `orchestrator/tests/test_milestone_runner.py`, `orchestrator/tests/test_cli.py`
**Type:** CODING
**Estimated time:** 20 min

**Description:**
Update all mock patches to use new module/class names.

**Changes in test_milestone_runner.py:**
- All `patch("orchestrator.milestone_runner.SandboxManager")` → `patch("orchestrator.milestone_runner.CodingAgentContainer")`

**Changes in test_cli.py:**
- All `patch("orchestrator.cli.SandboxManager")` → `patch("orchestrator.cli.CodingAgentContainer")`

**Acceptance Criteria:**
- [ ] All mock patches updated
- [ ] All tests pass

---

## Task 1.7: Rename scripts

**Files:**
- `scripts/sandbox-init.sh` → `scripts/coding-agent-init.sh`
- `scripts/sandbox-reset.sh` → `scripts/coding-agent-reset.sh`
- `scripts/sandbox-shell.sh` → `scripts/coding-agent-shell.sh`
- `scripts/sandbox-claude.sh` → `scripts/coding-agent-claude.sh`

**Type:** CODING
**Estimated time:** 20 min

**Description:**
Rename scripts and update internal references.

**Changes per script:**
- Rename file
- Update any internal comments referencing "sandbox"
- Update container name references: `ktrdr-sandbox` → `ktrdr-coding-agent`
- Update compose file path references if any

**Acceptance Criteria:**
- [ ] All 4 scripts renamed
- [ ] Internal references updated
- [ ] Scripts still work (manual verification)

---

## Task 1.8: Rename Docker configuration

**Files:**
- `deploy/environments/sandbox/` → `deploy/environments/coding-agent/`
- `deploy/docker/sandbox/` → `deploy/docker/coding-agent/`

**Type:** CODING
**Estimated time:** 20 min

**Description:**
Rename directories and update docker-compose.yml and Dockerfile.

**Changes in docker-compose.yml:**
- Service name: `sandbox` → `coding-agent`
- Container name: `ktrdr-sandbox` → `ktrdr-coding-agent`
- Image name: `ktrdr-sandbox:latest` → `ktrdr-coding-agent:latest`
- Volume names: `sandbox-*` → `coding-agent-*`
- Update comments

**Changes in Dockerfile:**
- Update any comments referencing "sandbox"

**Changes in entrypoint.sh:**
- Update any comments referencing "sandbox"

**Acceptance Criteria:**
- [ ] Directories renamed
- [ ] docker-compose.yml updated with new names
- [ ] Can build image: `docker compose -f deploy/environments/coding-agent/docker-compose.yml build`

---

## Milestone 1 Completion Checklist

- [ ] All 8 tasks complete
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] No grep hits for old names: `grep -r "SandboxManager\|orchestrator.sandbox\|ktrdr-sandbox" orchestrator/`
- [ ] Quality gates pass: `make quality`
- [ ] Commit with message: "refactor(orchestrator): rename sandbox to coding-agent-container"
