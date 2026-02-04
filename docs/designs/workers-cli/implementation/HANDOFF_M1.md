# M1 Handoff: Workers CLI Command

## Task 1.1 Complete: Implement workers command

**Pattern established:** The workers command follows the exact same structure as `status.py`:
- `@trace_cli_command("workers")` decorator
- Lazy imports inside function body
- `AsyncCLIClient` for API call to `/workers`
- `state.json_mode` check for JSON vs table output
- Rich Table for default output

**API response format:** Workers endpoint returns a list directly (not wrapped in `{"data": [...]}` like operations).

**Next Task Notes:**
- Task 1.2 adds unit tests - tests are already created as part of TDD in Task 1.1
- Task 1.3 is E2E validation requiring Docker containers running

## Task 1.2 Complete: Add unit tests

**Already done:** Tests were created during Task 1.1's TDD cycle. This task validated they meet requirements.

**Test coverage:**
- Table output rendering
- JSON mode output
- Empty workers handling
- GPU capability display
- Error handling (exit code 1)

**Next Task Notes:**
- Task 1.3 requires Docker sandbox running (`uv run kinfra sandbox up`)
- Compare CLI output with direct API call to `/api/v1/workers`

## Task 1.3 Complete: E2E Validation

**E2E Test:** `cli/workers-command` — ✅ PASSED (6 steps)

**Validated:**
- Table output displays 5 workers with TYPE, STATUS, GPU, ENDPOINT, OPERATION columns
- JSON output is valid array matching API response exactly
- Worker count and IDs match between CLI and direct API call
- Both commands exit with code 0

**New test added to catalog:** `.claude/skills/e2e-testing/tests/cli/workers-command.md`
