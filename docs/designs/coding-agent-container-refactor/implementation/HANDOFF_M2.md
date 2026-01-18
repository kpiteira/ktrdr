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
