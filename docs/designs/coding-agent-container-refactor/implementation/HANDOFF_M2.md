# Milestone 2 Handoff: Environment Validation

## Task 2.1 Complete: Create orchestrator/environment.py

**Summary:** Created environment validation module with `validate_environment()` function. Created shared `OrchestratorError` in `errors.py`.

### Key Files Created
- `orchestrator/errors.py` — `OrchestratorError` base exception class
- `orchestrator/environment.py` — `validate_environment()` function
- `orchestrator/tests/test_environment.py` — 6 unit tests

### Implementation Notes
- Checks are sequential: repo root → sandbox init → sandbox running
- Uses `uv run ktrdr sandbox status` for sandbox check (matches project convention)
- Timeout is 10 seconds for subprocess calls
- Error messages are lowercase with actionable commands

### Example Error Messages
- "Not running from repository root. Please cd to the repo root directory (where .git exists)."
- "Sandbox not initialized. Run: ktrdr sandbox init"
- "Sandbox not running. Run: ktrdr sandbox up"

### Next Task Notes (2.2)
- Task 2.2 creates tests — already done as part of TDD for 2.1
- Move to Task 2.3 (wiring into CLI/milestone_runner) or verify test requirements match

---

## Task 2.2 Complete: Create tests for environment validation

**Summary:** Tests were created as part of TDD in Task 2.1. All acceptance criteria met.

### Verification
- 6 tests implemented (4 required + 2 additional)
- All tests pass in 0.05s
- Proper mocking (no real subprocess calls)
- Error message content verified in assertions

---

## Task 2.3 Complete: Wire validation into orchestrator startup

**Summary:** Added `validate_environment()` calls to `_run_task()` in cli.py and `run_milestone()` in milestone_runner.py. Updated all existing tests to mock the new validation call.

### Files Modified
- `orchestrator/cli.py` — Added import and call at start of `_run_task()`
- `orchestrator/milestone_runner.py` — Added import and call at start of `run_milestone()`
- `orchestrator/tests/test_cli.py` — Added `validate_environment` mock to 16 test blocks
- `orchestrator/tests/test_milestone_runner.py` — Added `validate_environment` mock to 29 test blocks

### Implementation Notes
- Result stored in `_code_folder` variable (unused now, M3 will pass to container)
- Validation happens BEFORE any other setup (config loading, telemetry, etc.)
- Error propagates naturally via OrchestratorError exception

### Test Update Pattern
```python
with patch("orchestrator.cli.validate_environment"):
    with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
        # existing test code...
```

---
