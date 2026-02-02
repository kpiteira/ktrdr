# Handoff: M5 - Done Workflow

## Task 5.1 Complete: Create done command

**Implementation Notes:**
- `done_app` follows same pattern as `spec_app` and `impl_app`
- Uses `@done_app.callback(invoke_without_command=True)` for command execution
- Dirty state checks via `git status --porcelain` and `git log @{u}..HEAD`
- No upstream handling: if no remote tracking, checks for any local commits

**Gotchas:**
- **Typer option/argument order with `invoke_without_command=True`**: Options MUST come BEFORE arguments in CLI invocation. `kinfra done --force myname` works, but `kinfra done myname --force` may fail to parse the argument. Tests should use `["done", "--force", "name"]` not `["done", "name", "--force"]`.

**Import Pattern:**
- `from ktrdr.cli.kinfra.done import done_app` - the Typer app
- Uses deferred imports for `stop_slot_containers` and `remove_override` to enable mocking

**Testing Notes:**
- Mock at source module: `ktrdr.cli.kinfra.slots.stop_slot_containers`, not import point
- Decorator order must match parameter order (bottom decorator = first parameter)

**Next Task Notes:**
- Task 5.2 adds `get_slot_for_worktree()` to registry
- This method already exists from M4! Verify and add tests if needed

## Task 5.2 Complete: Add registry lookup by worktree

**Status:** Already implemented in M4 (Task 4.4)

The `get_slot_for_worktree()` method and its tests already exist:
- `ktrdr/cli/sandbox_registry.py:176` — method implementation
- `tests/unit/cli/kinfra/test_worktrees.py:380` — 3 tests covering found/not found/different worktree

No additional work needed.

## Task 5.3 Complete: E2E Validation

**E2E Test:** cli/kinfra-done-workflow

**Result:** ✅ PASSED (after bug fix)

**Bug Found and Fixed:**
- Initial E2E run failed: `git worktree remove` didn't receive `--force` flag
- Symptom: `kinfra done --force` crashed when worktree had uncommitted changes
- Fix: Pass `--force` to git worktree remove when force=True
- Added unit test to verify fix

**All Validation Steps Passed:**
1. ✅ Dirty check works (aborts without --force)
2. ✅ Force flag works (--force bypasses dirty check)
3. ✅ Slot released (claimed_by = null, status = stopped)
4. ✅ Containers stopped (health check fails)
5. ✅ Override file removed
6. ✅ Worktree removed (directory gone)
