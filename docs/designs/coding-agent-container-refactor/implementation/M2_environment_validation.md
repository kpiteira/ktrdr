---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Environment Validation

**Branch:** `docs/coding-agent-container-refactor`
**Builds on:** Milestone 1 (Rename)
**E2E Test:** Clear errors when prerequisites missing

## Goal

Orchestrator validates prerequisites on startup with clear errors. Users see actionable messages when running from wrong context.

---

## Task 2.1: Create orchestrator/environment.py

**File(s):** `orchestrator/environment.py` (NEW)
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** Configuration, Cross-Component

**Description:**
Create the environment validation module with `validate_environment()` function. The function checks three prerequisites: (1) running from repo root (.git exists), (2) sandbox initialized (.env.sandbox exists), (3) sandbox running (ktrdr sandbox status). Returns the code folder path on success, raises `OrchestratorError` with clear message on failure.

**Implementation Notes:**
- Use `Path.cwd()` to get current directory
- Check for `.git` directory (not file, for worktrees)
- Check for `.env.sandbox` file
- Run `uv run ktrdr sandbox status` via subprocess
- Parse output for "running" (case-insensitive)
- Import or create `OrchestratorError` in orchestrator/errors.py if needed

**Testing Requirements:**

*Unit Tests:*
- [ ] Returns cwd when all checks pass
- [ ] Raises with "repo root" message when .git missing
- [ ] Raises with "sandbox init" message when .env.sandbox missing
- [ ] Raises with "sandbox up" message when status check fails

*Integration Tests:*
- [ ] N/A (subprocess is mocked in unit tests)

*Smoke Test:*
```bash
# From repo root with sandbox running:
python -c "from orchestrator.environment import validate_environment; print(validate_environment())"
# Should print current directory path
```

**Acceptance Criteria:**
- [ ] File created at `orchestrator/environment.py`
- [ ] Three checks implemented with clear error messages
- [ ] Returns `Path` on success
- [ ] Uses `OrchestratorError` for failures
- [ ] Error messages include actionable fix (e.g., "Run: ktrdr sandbox init")

---

## Task 2.2: Create tests for environment validation

**File(s):** `orchestrator/tests/test_environment.py` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Create unit tests for environment validation using pytest fixtures and mocking. Test all four scenarios: valid environment, missing .git, missing .env.sandbox, sandbox not running.

**Implementation Notes:**
- Use `tmp_path` fixture for isolated test directories
- Use `monkeypatch.chdir()` to change working directory
- Use `unittest.mock.patch` for subprocess.run
- Follow existing test patterns in orchestrator/tests/

**Testing Requirements:**

*Unit Tests:*
- [ ] test_returns_cwd_when_valid
- [ ] test_raises_when_not_repo_root
- [ ] test_raises_when_sandbox_not_initialized
- [ ] test_raises_when_sandbox_not_running

*Integration Tests:*
- [ ] N/A

*Smoke Test:*
```bash
cd orchestrator && uv run pytest tests/test_environment.py -v
```

**Acceptance Criteria:**
- [ ] All 4 test cases implemented and passing
- [ ] Tests use proper mocking (no real subprocess calls)
- [ ] Tests run fast (<1s total)
- [ ] Error message content verified in assertions

---

## Task 2.3: Wire validation into orchestrator startup

**File(s):** `orchestrator/cli.py`, `orchestrator/milestone_runner.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI, Cross-Component

**Description:**
Call `validate_environment()` at the start of orchestrator commands before creating CodingAgentContainer. Store the returned path for later use (M3 will pass it to container.start()). Update tests to mock the new validation call.

**Implementation Notes:**
- Add import: `from orchestrator.environment import validate_environment`
- Call early in command handlers, before any container operations
- For now, just validate and store result (M3 will use it)
- Update test mocks to patch `validate_environment`

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing tests updated with validate_environment mock
- [ ] Tests verify validation is called

*Integration Tests:*
- [ ] Wiring test: validate_environment is called before container creation

*Smoke Test:*
```bash
# From wrong directory:
cd /tmp && uv run python -m orchestrator.cli run --help 2>&1 | head -5
# Should show error about repo root (or help if --help bypasses validation)
```

**Acceptance Criteria:**
- [ ] `validate_environment()` called before creating container in cli.py
- [ ] `validate_environment()` called before creating container in milestone_runner.py
- [ ] Orchestrator refuses to proceed if validation fails
- [ ] Error messages displayed to user
- [ ] Existing tests updated to mock `validate_environment`

---

## Milestone 2 Verification

### E2E Test Scenario

**Purpose:** Verify orchestrator rejects invalid environments with clear messages
**Duration:** ~30 seconds
**Prerequisites:** orchestrator package installed, one valid sandbox available

**Test Steps:**

```bash
# 1. Test: Not in repo root
cd /tmp
python -c "from orchestrator.environment import validate_environment; validate_environment()" 2>&1
# Expected: OrchestratorError with "repo root" in message

# 2. Test: No sandbox initialized (need a repo without .env.sandbox)
cd /path/to/repo/without/sandbox
python -c "from orchestrator.environment import validate_environment; validate_environment()" 2>&1
# Expected: OrchestratorError with "sandbox init" in message

# 3. Test: Sandbox not running
cd ~/ktrdr--orchestrator-1
ktrdr sandbox down
python -c "from orchestrator.environment import validate_environment; validate_environment()" 2>&1
# Expected: OrchestratorError with "sandbox up" in message

# 4. Test: Valid context
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up
python -c "from orchestrator.environment import validate_environment; print(validate_environment())"
# Expected: Prints path to current directory
```

**Success Criteria:**
- [ ] Each prerequisite failure gives clear, actionable error
- [ ] Valid context returns code folder path
- [ ] Error messages include the fix command

### Completion Checklist

- [ ] All 3 tasks complete and committed
- [ ] Unit tests pass: `cd orchestrator && uv run pytest tests/test_environment.py -v`
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Commit with message: "feat(orchestrator): add environment validation on startup"
