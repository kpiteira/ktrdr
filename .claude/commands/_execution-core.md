# Shared Execution Core

This file contains the shared implementation logic used by both `ktask` and `kissue` commands.

**Note:** This file is referenced by other commands. Read it when implementing tasks.

---

## Implementation (TDD Cycle)

Follow the TDD cycle: **RED → GREEN → REFACTOR**

### RED: Write Failing Tests

Before any implementation:

1. Create test file(s) following project conventions
2. Write tests covering:
   - Happy path (normal operation)
   - Error cases (failures, exceptions)
   - Edge cases (boundaries, null values)
3. Run tests: `make test-unit`
4. Verify tests fail meaningfully (not import errors)

Show output: "Tests written and failing as expected"

If you catch yourself writing implementation before tests, stop, delete the implementation code, and return to this phase.

### GREEN: Minimal Implementation

1. Write just enough code to make tests pass
2. Follow existing patterns in the codebase
3. Run tests frequently during implementation
4. Don't over-engineer or add untested features

Show output: "All tests passing"

### REFACTOR: Improve Quality

1. Improve code clarity and maintainability
2. Extract common patterns
3. Add documentation and type hints
4. Run tests after each refactoring: `make test-unit`
5. Run quality checks: `make quality`

Show output: "Tests and quality checks passing"

---

## Verification

### Unit Test Verification

All unit tests must pass:

```bash
make test-unit
make quality
```

### Integration Smoke Test

Unit tests verify components in isolation. Integration tests verify they work together.

After unit tests pass (for changes affecting system behavior):

1. **Start system**: `docker compose up -d`
2. **Execute modified flow**: Use CLI commands or curl/API calls
3. **Verify end-to-end**: Does the operation complete? Is state consistent?
4. **Check logs**: `docker compose logs backend --since 5m | grep -i error`
5. **Report**: "Integration test passed" or "Issue found: [description]"

**Skip integration testing for:**
- Pure refactoring with no behavior change
- Documentation-only changes
- Test-only changes

### E2E Test Verification

For changes affecting core workflows (training, backtesting, data loading):

1. **Determine relevant E2E tests** using e2e-test-designer agent
2. **Run selected E2E tests** using e2e-tester agent
3. **All E2E tests must pass** before PR creation

If E2E tests fail, investigate and fix before proceeding.

### Acceptance Criteria Validation

For each acceptance criterion from the task/issue:

1. Identify the type (feature, unit test, integration test, documentation)
2. Validate it appropriately
3. Check it off with status

```markdown
- [x] Acceptance criterion 1 — VALIDATED
- [x] Acceptance criterion 2 — VALIDATED
- [ ] Acceptance criterion 3 — NOT MET (needs: ...)
```

If any criterion is not met, continue working before proceeding.

---

## Quality Gates

All must pass before completion:

- [ ] All unit tests pass: `make test-unit`
- [ ] Quality checks pass: `make quality`
- [ ] Relevant E2E tests pass (if applicable)
- [ ] Code is documented (docstrings explaining "why")
- [ ] All work is committed with clear messages
- [ ] No security vulnerabilities introduced
- [ ] Acceptance criteria validated

---

## Task Summary Format

Provide a summary of what was accomplished:

```markdown
## Task Complete: [Task/Issue ID]

**What was implemented:**
- [Brief description of the change]

**Files changed:**
- [List of files created/modified/deleted]

**Key decisions made:**
- [Any non-obvious choices and why]

**Tests:**
- Unit: [count] tests added/modified
- E2E: [tests run and results]

**Issues encountered:**
- [Problems hit and how they were resolved, or "None"]
```

---

## CLI Test Patterns

When writing tests for CLI commands (`tests/unit/cli/`):

**ALWAYS use the `runner` fixture** for tests that check command output:

```python
# CORRECT - uses fixture that strips ANSI codes
def test_help_shows_flags(self, runner) -> None:
    result = runner.invoke(app, ["--help"])
    assert "--json" in result.output

# WRONG - creates raw CliRunner, ANSI codes will break assertions in CI
def test_help_shows_flags(self) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert "--json" in result.output
```

See `tests/unit/cli/CLAUDE.md` for full CLI testing guidelines.

---

## Error Handling

If you encounter blockers:

- Do not mark task as complete
- Document the blocker clearly
- Ask for guidance on how to proceed
