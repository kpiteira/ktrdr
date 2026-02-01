---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: CLI Foundation + Quick Wins

**Branch:** `feature/kinfra-cli-foundation`
**Builds on:** None (foundation milestone)

## Goal

Remove the docker-compose.yml symlink and establish the `kinfra` CLI as the new home for infrastructure commands. Add deprecation warnings to `ktrdr` for moved commands.

---

## Task 1.1: Remove docker-compose.yml symlink

**File(s):** `docker-compose.yml` (delete), `.gitignore` (modify)
**Type:** CODING
**Task Categories:** Configuration

**Description:**
Delete the `docker-compose.yml` symlink that causes port conflicts. Add `docker-compose.yml` to `.gitignore` to prevent recreation.

**Implementation Notes:**
- The symlink currently points to `deploy/environments/local/docker-compose.yml`
- This has caused E2E tests to hit wrong backend (port 8000 vs sandbox port)
- After removal, users must use explicit `-f` flag or kinfra commands

**Testing Requirements:**

*Unit Tests:* None needed (file operation)

*Smoke Test:*
```bash
ls -la docker-compose.yml  # Should fail (not exist)
grep "docker-compose.yml" .gitignore  # Should find entry
```

**Acceptance Criteria:**
- [ ] `docker-compose.yml` symlink deleted from repo
- [ ] `.gitignore` contains `docker-compose.yml`
- [ ] Commit explains why this was removed

---

## Task 1.2: Create kinfra CLI package structure

**File(s):**
- `ktrdr/cli/kinfra/__init__.py` (create)
- `ktrdr/cli/kinfra/main.py` (create)
- `pyproject.toml` (modify)

**Type:** CODING
**Task Categories:** Wiring/DI, Configuration

**Description:**
Create the new `kinfra` CLI entry point with Typer app. Register in pyproject.toml so `kinfra` command is available after install.

**Implementation Notes:**
- Follow existing pattern in `ktrdr/cli/main.py`
- Use Typer for CLI framework (matches existing codebase)
- Entry point format: `kinfra = "ktrdr.cli.kinfra.main:app"`

**Code sketch:**
```python
# ktrdr/cli/kinfra/main.py
import typer

app = typer.Typer(
    name="kinfra",
    help="KTRDR Infrastructure CLI - sandbox, deployment, and worktree management",
    no_args_is_help=True,
)

# Subcommands will be added in subsequent tasks
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_kinfra_app_exists` — app is a Typer instance
- [ ] `test_kinfra_help` — `--help` returns without error

*Smoke Test:*
```bash
uv run kinfra --help  # Shows help text
```

**Acceptance Criteria:**
- [ ] `kinfra --help` works after `uv sync`
- [ ] Help text shows "Infrastructure CLI"
- [ ] No subcommands yet (added in next tasks)

---

## Task 1.3: Move sandbox commands to kinfra

**File(s):**
- `ktrdr/cli/kinfra/sandbox.py` (create, based on `ktrdr/cli/sandbox.py`)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** Cross-Component

**Description:**
Move all sandbox commands from `ktrdr/cli/sandbox.py` to `ktrdr/cli/kinfra/sandbox.py`. Register as subcommand of kinfra.

**Implementation Notes:**
- This is mostly lift-and-shift
- Keep original file for now (will add deprecation in Task 1.6)
- Import and register: `app.add_typer(sandbox_app, name="sandbox")`

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing sandbox tests still pass (may need import path updates)

*Integration Tests:*
- [ ] `kinfra sandbox status` returns same output as old command

*Smoke Test:*
```bash
uv run kinfra sandbox status
uv run kinfra sandbox list
```

**Acceptance Criteria:**
- [ ] All sandbox subcommands work under `kinfra sandbox`
- [ ] `up`, `down`, `status`, `list` all functional
- [ ] No behavior changes from original commands

---

## Task 1.4: Move local-prod commands to kinfra

**File(s):**
- `ktrdr/cli/kinfra/local_prod.py` (create, based on `ktrdr/cli/local_prod.py`)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** Cross-Component

**Description:**
Move all local-prod commands from `ktrdr/cli/local_prod.py` to `ktrdr/cli/kinfra/local_prod.py`. Register as subcommand of kinfra.

**Implementation Notes:**
- Same pattern as Task 1.3
- Commands: `up`, `down`, `status`, `logs`, `shell`

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing local-prod tests still pass

*Smoke Test:*
```bash
uv run kinfra local-prod --help
```

**Acceptance Criteria:**
- [ ] All local-prod subcommands work under `kinfra local-prod`
- [ ] No behavior changes from original commands

---

## Task 1.5: Move deploy commands to kinfra

**File(s):**
- `ktrdr/cli/kinfra/deploy.py` (create, based on `ktrdr/cli/deploy.py`)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** Cross-Component

**Description:**
Move all deploy commands from `ktrdr/cli/deploy.py` to `ktrdr/cli/kinfra/deploy.py`. Register as subcommand of kinfra.

**Implementation Notes:**
- Commands: `homelab`, `canary`, `status`

**Testing Requirements:**

*Unit Tests:*
- [ ] Existing deploy tests still pass

*Smoke Test:*
```bash
uv run kinfra deploy --help
```

**Acceptance Criteria:**
- [ ] All deploy subcommands work under `kinfra deploy`
- [ ] No behavior changes from original commands

---

## Task 1.6: Add deprecation warnings to ktrdr

**File(s):**
- `ktrdr/cli/sandbox.py` (modify)
- `ktrdr/cli/local_prod.py` (modify)
- `ktrdr/cli/deploy.py` (modify)

**Type:** CODING
**Task Categories:** API Endpoint

**Description:**
Add deprecation warnings to the old command locations. Commands still work but print warning to stderr suggesting `kinfra` equivalent.

**Implementation Notes:**
```python
import sys
import typer

def deprecation_callback(ctx: typer.Context):
    cmd = ctx.invoked_subcommand or ""
    typer.echo(
        f"Warning: 'ktrdr sandbox {cmd}' is deprecated. "
        f"Use 'kinfra sandbox {cmd}' instead.",
        err=True
    )

# Add callback to app
sandbox_app = typer.Typer(callback=deprecation_callback)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_sandbox_deprecation_warning` — warning appears in stderr
- [ ] `test_command_still_works` — command executes despite warning

*Smoke Test:*
```bash
uv run ktrdr sandbox status 2>&1 | grep -i "deprecated"
```

**Acceptance Criteria:**
- [ ] `ktrdr sandbox *` commands show deprecation warning
- [ ] `ktrdr local-prod *` commands show deprecation warning
- [ ] `ktrdr deploy *` commands show deprecation warning
- [ ] Commands still execute after warning (not breaking change)
- [ ] Warning goes to stderr, output to stdout

---

## Task 1.7: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 15 min

**Description:**
Validate M1 is complete using the E2E agent workflow.

**E2E Test: cli/kinfra-foundation**

This test validates:
1. docker-compose.yml symlink is removed
2. kinfra CLI is installed and shows help
3. kinfra sandbox commands work
4. ktrdr sandbox commands show deprecation warning

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | `ls -la docker-compose.yml` | File not found | Exit code 1 |
| 2 | `uv run kinfra --help` | Shows help with sandbox, local-prod, deploy | Help text |
| 3 | `uv run kinfra sandbox status` | Returns status without error | Exit code 0 |
| 4 | `uv run ktrdr sandbox status 2>&1` | Shows deprecation warning | stderr contains "deprecated" |

**Success Criteria:**
- [ ] Symlink removed
- [ ] kinfra CLI works
- [ ] Commands migrated successfully
- [ ] Deprecation warnings appear

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] No regressions in existing functionality
- [ ] `make quality` passes

---

## Milestone 1 Verification

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
