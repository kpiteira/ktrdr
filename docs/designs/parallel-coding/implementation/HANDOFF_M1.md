# Handoff: M1 - CLI Foundation

## Task 1.1 Complete: Remove docker-compose.yml symlink

**Implementation Notes:**
- Symlink was at repo root pointing to `deploy/environments/local/docker-compose.yml`
- After removal, `docker compose` commands require explicit `-f` flag

**Next Task Notes:**
- Task 1.2 creates the kinfra CLI package structure
- Follow existing pattern in `ktrdr/cli/main.py` for Typer setup

## Task 1.2 Complete: Create kinfra CLI package structure

**Implementation Notes:**
- Typer apps need a `@app.callback()` decorator to be invokable, even with no subcommands
- Entry point format: `kinfra = "ktrdr.cli.kinfra.main:main"` (main function, not app directly)

**Next Task Notes:**
- Task 1.3 moves sandbox commands from `ktrdr/cli/sandbox.py` to `ktrdr/cli/kinfra/sandbox.py`
- Use `app.add_typer(sandbox_app, name="sandbox")` to register subcommand

## Task 1.3 Complete: Move sandbox commands to kinfra

**Implementation Notes:**
- Simple lift-and-shift: copy file, register in main.py
- Original `ktrdr/cli/sandbox.py` kept for now (deprecation in Task 1.6)

**Next Task Notes:**
- Task 1.4 moves local-prod commands using same pattern
- File is `ktrdr/cli/local_prod.py`, register as `local-prod` (hyphen in name)

## Task 1.4 Complete: Move local-prod commands to kinfra

**Implementation Notes:**
- Same lift-and-shift pattern as Task 1.3
- Typer automatically handles hyphenated names (`local-prod`)

**Next Task Notes:**
- Task 1.5 moves deploy commands
- File is `ktrdr/cli/deploy_commands.py`, app is `deploy_app`

## Task 1.5 Complete: Move deploy commands to kinfra

**Implementation Notes:**
- Actual file is `deploy_commands.py` (not `deploy.py` as mentioned in plan)
- Same lift-and-shift pattern as previous tasks

**Next Task Notes:**
- Task 1.6 adds deprecation warnings to original files
- Use Typer callback pattern to show warning before command executes

## Task 1.6 Complete: Add deprecation warnings to ktrdr CLI

**Implementation Notes:**
- Use `@app.callback(invoke_without_command=True)` pattern for deprecation warnings
- Use `typer.secho()` for colored warnings (not `typer.echo(err=True)` which writes to stderr)
- `--help` is processed before callback runs, so tests must use actual subcommands

**Gotcha:** Testing deprecation warnings:
- CliRunner doesn't capture stderr reliably for `typer.echo(err=True)`
- Using `--help` on the app bypasses the callback entirely
- Solution: Test with actual subcommands (`list`, `init --help`, `core --help`)

**Next Task Notes:**
- Task 1.7 is a VALIDATION task - run E2E test to verify CLI works end-to-end

## Task 1.7 Complete: Execute E2E Test (VALIDATION)

**E2E Test Results:** All 8 steps PASSED
- docker-compose.yml symlink removed ✅
- kinfra --help shows sandbox, local-prod, deploy ✅
- kinfra sandbox --help shows all subcommands ✅
- kinfra sandbox status executes successfully ✅
- ktrdr sandbox status shows deprecation warning ✅
- kinfra local-prod --help works ✅
- kinfra deploy --help works ✅
- pyproject.toml has both entry points ✅

**Test Spec:** `.claude/skills/e2e-testing/tests/cli/kinfra-foundation.md`
