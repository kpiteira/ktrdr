# Handoff: M2 - Spec Workflow

## Task 2.1 Complete: Create spec command

**Implementation Notes:**
- `spec_app` uses `@spec_app.callback(invoke_without_command=True)` pattern since it's a single command registered as a Typer app
- For error output that appears in `result.output` during testing, use `typer.secho()` to stdout rather than `typer.echo(err=True)` to stderr
- Path.exists() and Path.mkdir() need to be patched at `ktrdr.cli.kinfra.spec.Path` not `pathlib.Path`

**Gotcha:** The `runner` fixture's `result.output` combines stdout only by default. If you need error messages to appear in test output, write to stdout with red coloring rather than stderr.

**Next Task Notes:**
- Task 2.2 creates the worktrees listing command
- Follow same pattern: create module with Typer app, register in main.py
- Use `git worktree list --porcelain` for parsing
- Use Rich Table for output (follow existing CLI patterns)

## Task 2.2 Complete: Create worktrees listing command

**Implementation Notes:**
- `_parse_worktree_list()` is a standalone function for parsing porcelain output
- The worktrees_app uses `@worktrees_app.callback(invoke_without_command=True)` pattern
- Rich `console.print(table)` outputs to stdout which is captured by test runner

**Next Task Notes:**
- Task 2.3 adds error types for worktree operations
- Error types already exist in `ktrdr/cli/kinfra/errors.py` (created in Task 2.1)
- This task may be mostly done — verify all required error types are present

## Task 2.3 Complete: Add error types for worktree operations

**Implementation Notes:**
- Error types were pre-created in Task 2.1 to avoid import issues
- Task 2.3 adds unit tests to validate the error hierarchy

**Next Task Notes:**
- Task 2.4 is a VALIDATION task — run E2E test for spec workflow
- Use e2e-test-designer → e2e-test-architect → e2e-tester agent workflow

## Task 2.4 Complete: Execute E2E Test (VALIDATION)

**E2E Test Results:** All 8 steps PASSED
- Spec worktree creation at ../ktrdr-spec-<feature>/ ✅
- Design folder docs/designs/<feature>/ created ✅
- Branch spec/<feature> created ✅
- kinfra worktrees lists worktree with type "spec" ✅
- Duplicate creation fails with clear error (idempotency) ✅
- Cleanup successful ✅

**Test Spec:** `.claude/skills/e2e-testing/tests/cli/kinfra-spec-workflow.md`

**M2 Complete — Ready for PR**
