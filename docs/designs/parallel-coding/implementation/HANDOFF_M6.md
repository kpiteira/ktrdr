# Handoff: M6 - Polish

## Task 6.1 Complete: Add command aliases

**Implementation Notes:**
- Used `app.add_typer()` with `hidden=True` to register aliases
- Both `finish` and `complete` reuse the same `done_app` Typer instance
- Aliases execute identical logic to `done` command

**Testing Notes:**
- Test for "aliases hidden" needed adjustment — word "complete" appears in "--install-completion"
- Fixed by checking for command lines starting with alias names, not substring search

**Next Task Notes:**
- Task 6.3 updates sandbox skill with kinfra commands

## Task 6.2 Complete: Update CLAUDE.md

**Implementation Notes:**
- Updated Sandbox Commands section to use `kinfra` instead of `ktrdr sandbox`
- Added kinfra commands to Essential Commands section
- Added Docker Compose Warning section
- Added Worktree Workflow section

## Task 6.3 Complete: Update sandbox skill

**Implementation Notes:**
- Updated all `ktrdr sandbox` commands to `kinfra sandbox`
- Added Slot Pool section explaining how slots 1-2 are pre-provisioned
- Added Worktree Workflow section with spec/impl/done commands
- Updated naming conventions to include `ktrdr-impl-` and `ktrdr-spec-` patterns
- All examples now use `uv run kinfra`

## Task 6.4 Complete: E2E Validation

**E2E Test:** cli/kinfra-done-workflow

**Result:** ✅ PASSED

**All Validation Steps Passed:**
1. ✅ Dirty check works (aborts without --force)
2. ✅ Force flag works (--force bypasses dirty check)
3. ✅ Containers stopped
4. ✅ Slot released (claimed_by = null, status = stopped)
5. ✅ Override file removed
6. ✅ Worktree removed
7. ✅ Idempotent behavior (second done fails with clear error)
8. ✅ Aliases work (finish, complete)
9. ✅ Documentation updated (CLAUDE.md, sandbox skill)
