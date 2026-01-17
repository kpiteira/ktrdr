---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Rename (No Behavior Change)

**Branch:** `docs/coding-agent-container-refactor`
**Builds on:** Nothing (first milestone)
**E2E Test:** Existing orchestrator tests pass with new names

## Goal

All "sandbox" references in orchestrator context renamed to "coding-agent". Existing tests pass with new names. No behavior change.

---

## Task 1.1: Rename orchestrator/sandbox.py

**File(s):** `orchestrator/sandbox.py` → `orchestrator/coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI

**Description:**
Rename the file and update class/exception names inside it. Change `SandboxManager` to `CodingAgentContainer` and `SandboxError` to `CodingAgentError`. Update docstrings to reference "coding agent container" instead of "sandbox". Keep `format_tool_call()` helper unchanged.

**Implementation Notes:**
- Use git mv for the rename to preserve history
- Keep `container_name` default as `ktrdr-sandbox` for now (changed in M3)
- The class is a dataclass - ensure decorator is preserved

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing tests pass after import path update

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
python -c "from orchestrator.coding_agent_container import CodingAgentContainer; print('OK')"
```

**Acceptance Criteria:**
- [ ] File renamed to `coding_agent_container.py`
- [ ] Class is `CodingAgentContainer`
- [ ] Exception is `CodingAgentError`
- [ ] Docstrings updated
- [ ] `container_name` default is still `ktrdr-sandbox`

---

## Task 1.2: Rename orchestrator/tests/test_sandbox.py

**File(s):** `orchestrator/tests/test_sandbox.py` → `orchestrator/tests/test_coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI

**Description:**
Rename test file and update all imports from `orchestrator.sandbox` to `orchestrator.coding_agent_container`. Update test class names from `TestSandboxManagerStructure` to `TestCodingAgentContainerStructure`. Update test docstrings.

**Implementation Notes:**
- Use git mv for the rename
- Search and replace all occurrences of `SandboxManager` with `CodingAgentContainer`
- Search and replace all occurrences of `SandboxError` with `CodingAgentError`

**Testing Requirements:**

*Unit Tests:*
- [ ] All renamed tests pass

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
cd orchestrator && uv run pytest tests/test_coding_agent_container.py -v --tb=short
```

**Acceptance Criteria:**
- [ ] File renamed
- [ ] All imports updated
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_coding_agent_container.py -v`

---

## Task 1.3: Update orchestrator/runner.py imports

**File(s):** `orchestrator/runner.py`
**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Wiring/DI

**Description:**
Update imports from `orchestrator.sandbox` to `orchestrator.coding_agent_container`. Change all function signatures from `sandbox: SandboxManager` to `container: CodingAgentContainer`. Update all usages of `sandbox.` to `container.`.

**Implementation Notes:**
- Line 30 has the import
- Multiple functions use `sandbox` parameter - update all of them
- Parameter rename is for clarity, not just the type hint

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing runner tests pass

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
grep -c "SandboxManager\|orchestrator.sandbox" orchestrator/runner.py  # Should return 0
```

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Parameter names changed from `sandbox` to `container`
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_runner.py -v`

---

## Task 1.4: Update orchestrator/milestone_runner.py imports

**File(s):** `orchestrator/milestone_runner.py`
**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Wiring/DI

**Description:**
Update imports and all usages to new names. Change import on line 35, update instantiation on line 145, and update all function parameters and usages throughout the file.

**Implementation Notes:**
- Line 35: import statement
- Line 145: `sandbox = SandboxManager(` instantiation
- Line 496: `_get_current_branch(sandbox:` parameter
- Multiple other function signatures use `sandbox` parameter

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing milestone_runner tests pass

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
grep -c "SandboxManager\|orchestrator.sandbox" orchestrator/milestone_runner.py  # Should return 0
```

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_milestone_runner.py -v`

---

## Task 1.5: Update orchestrator/cli.py imports

**File(s):** `orchestrator/cli.py`
**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Wiring/DI

**Description:**
Update imports and usages in CLI module. Change import on line 28, update instantiations on lines 124 and 382.

**Implementation Notes:**
- Line 28: `from orchestrator.sandbox import SandboxManager, format_tool_call`
- Line 124: `sandbox = SandboxManager()`
- Line 382: similar instantiation
- `format_tool_call` import path also changes

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing CLI tests pass

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
grep -c "SandboxManager\|orchestrator.sandbox" orchestrator/cli.py  # Should return 0
```

**Acceptance Criteria:**
- [ ] No references to `SandboxManager` in file
- [ ] Tests pass: `uv run pytest orchestrator/tests/test_cli.py -v`

---

## Task 1.6: Update test mocks

**File(s):** `orchestrator/tests/test_milestone_runner.py`, `orchestrator/tests/test_cli.py`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Wiring/DI

**Description:**
Update all mock patches to use new module/class names. In test_milestone_runner.py, change all `patch("orchestrator.milestone_runner.SandboxManager")` to `patch("orchestrator.milestone_runner.CodingAgentContainer")`. In test_cli.py, change all `patch("orchestrator.cli.SandboxManager")` to `patch("orchestrator.cli.CodingAgentContainer")`.

**Implementation Notes:**
- test_milestone_runner.py has ~30 patches to update
- test_cli.py has ~4 patches to update
- Use search and replace carefully

**Testing Requirements:**

*Unit Tests:*
- [ ] All mocked tests pass

*Integration Tests:*
- [ ] N/A for rename

*Smoke Test:*
```bash
cd orchestrator && uv run pytest tests/test_milestone_runner.py tests/test_cli.py -v --tb=short
```

**Acceptance Criteria:**
- [ ] All mock patches updated
- [ ] All tests pass

---

## Task 1.7: Rename scripts

**File(s):**
- `scripts/sandbox-init.sh` → `scripts/coding-agent-init.sh`
- `scripts/sandbox-reset.sh` → `scripts/coding-agent-reset.sh`
- `scripts/sandbox-shell.sh` → `scripts/coding-agent-shell.sh`
- `scripts/sandbox-claude.sh` → `scripts/coding-agent-claude.sh`

**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Rename all 4 scripts and update internal references. Update container name references from `ktrdr-sandbox` to `ktrdr-coding-agent`. Update compose file path references. Update comments.

**Implementation Notes:**
- Use git mv for renames
- Each script references `CONTAINER_NAME="ktrdr-sandbox"` - update to `ktrdr-coding-agent`
- Update COMPOSE_FILE paths from `sandbox` to `coding-agent`
- Update echo/comments that mention "sandbox"

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A for scripts

*Integration Tests:*
- [ ] N/A for scripts

*Smoke Test:*
```bash
ls scripts/coding-agent-*.sh | wc -l  # Should return 4
grep -l "ktrdr-sandbox" scripts/coding-agent-*.sh | wc -l  # Should return 0
```

**Acceptance Criteria:**
- [ ] All 4 scripts renamed
- [ ] Internal references updated to `ktrdr-coding-agent`
- [ ] Compose file paths updated

---

## Task 1.8: Rename Docker configuration

**File(s):**
- `deploy/environments/sandbox/` → `deploy/environments/coding-agent/`
- `deploy/docker/sandbox/` → `deploy/docker/coding-agent/`

**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Rename directories and update docker-compose.yml and Dockerfile. Update service name, container name, image name, and volume names.

**Implementation Notes:**
- Use git mv for directory renames
- In docker-compose.yml update:
  - Service name: `sandbox` → `coding-agent`
  - Container name: `ktrdr-sandbox` → `ktrdr-coding-agent`
  - Image name: `ktrdr-sandbox:latest` → `ktrdr-coding-agent:latest`
  - Volume names: `sandbox-*` → `coding-agent-*`
- Update Dockerfile comments
- Update entrypoint.sh comments

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A for Docker config

*Integration Tests:*
- [ ] Image builds successfully

*Smoke Test:*
```bash
docker compose -f deploy/environments/coding-agent/docker-compose.yml config | grep container_name
# Should show: ktrdr-coding-agent
```

**Acceptance Criteria:**
- [ ] Directories renamed
- [ ] docker-compose.yml updated with new names
- [ ] Can build image: `docker compose -f deploy/environments/coding-agent/docker-compose.yml build`

---

## Milestone 1 Verification

### E2E Test Scenario

**Purpose:** Verify all renames completed without breaking existing functionality
**Duration:** ~2 minutes
**Prerequisites:** orchestrator package installed

**Test Steps:**

```bash
# 1. Verify no old references remain
grep -r "SandboxManager\|orchestrator\.sandbox\|ktrdr-sandbox" orchestrator/ scripts/ deploy/environments/coding-agent/ deploy/docker/coding-agent/
# Expected: No matches (exit code 1)

# 2. Run all orchestrator tests
cd orchestrator && uv run pytest tests/ -v
# Expected: All tests pass

# 3. Verify imports work
python -c "from orchestrator.coding_agent_container import CodingAgentContainer, CodingAgentError, format_tool_call; print('Imports OK')"
# Expected: "Imports OK"

# 4. Verify Docker config is valid
docker compose -f deploy/environments/coding-agent/docker-compose.yml config > /dev/null && echo "Docker config OK"
# Expected: "Docker config OK"
```

**Success Criteria:**
- [ ] No grep matches for old names
- [ ] All orchestrator tests pass
- [ ] Imports work correctly
- [ ] Docker compose config is valid

### Completion Checklist

- [ ] All 8 tasks complete and committed
- [ ] Unit tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] E2E test passes (above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Commit with message: "refactor(orchestrator): rename sandbox to coding-agent-container"
