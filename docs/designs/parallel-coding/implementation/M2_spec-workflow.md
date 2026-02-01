---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Spec Workflow

**Branch:** `feature/kinfra-spec-workflow`
**Builds on:** M1 (kinfra CLI exists)

## Goal

Enable users to quickly create spec worktrees for design work. No sandbox overhead - just git worktree with design folder structure.

---

## Task 2.1: Create spec command

**File(s):**
- `ktrdr/cli/kinfra/spec.py` (create)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** External (git), Configuration

**Description:**
Implement `kinfra spec <feature>` command that creates a git worktree for spec/design work. No sandbox is claimed.

**Implementation Notes:**
- Worktree location: `../ktrdr-spec-<feature>/`
- Branch name: `spec/<feature>`
- If branch exists, use it; otherwise create new from current HEAD
- Create `docs/designs/<feature>/` directory if it doesn't exist
- Use `subprocess` to run git commands (follow existing patterns in codebase)

**Code sketch:**
```python
import subprocess
from pathlib import Path
import typer

from .errors import WorktreeExistsError

app = typer.Typer()

@app.command()
def spec(
    feature: str = typer.Argument(..., help="Feature name for spec worktree"),
):
    """Create a spec worktree for design work (no sandbox)."""
    repo_root = Path.cwd()
    worktree_path = repo_root.parent / f"ktrdr-spec-{feature}"
    branch_name = f"spec/{feature}"

    # Check if worktree already exists
    if worktree_path.exists():
        raise WorktreeExistsError(f"Worktree {worktree_path.name} already exists")

    # Check if branch exists
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True, text=True, cwd=repo_root
    )
    branch_exists = bool(result.stdout.strip())

    # Create worktree
    if branch_exists:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            check=True, cwd=repo_root
        )
    else:
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            check=True, cwd=repo_root
        )

    # Create design folder if needed
    design_dir = worktree_path / "docs" / "designs" / feature
    design_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Created spec worktree at {worktree_path}")
    typer.echo(f"Design folder: {design_dir}")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_spec_creates_worktree` — worktree directory created
- [ ] `test_spec_creates_design_folder` — design folder created
- [ ] `test_spec_uses_existing_branch` — reuses branch if exists
- [ ] `test_spec_creates_new_branch` — creates branch if not exists
- [ ] `test_spec_fails_if_worktree_exists` — raises WorktreeExistsError

*Integration Tests:*
- [ ] `test_spec_git_worktree_valid` — `git worktree list` shows new worktree

*Smoke Test:*
```bash
uv run kinfra spec test-feature
ls ../ktrdr-spec-test-feature/
git worktree list | grep test-feature
# Cleanup
git worktree remove ../ktrdr-spec-test-feature
git branch -d spec/test-feature
```

**Acceptance Criteria:**
- [ ] `kinfra spec <feature>` creates worktree at `../ktrdr-spec-<feature>/`
- [ ] Design folder `docs/designs/<feature>/` created in worktree
- [ ] Uses existing `spec/<feature>` branch if it exists
- [ ] Creates new `spec/<feature>` branch if it doesn't exist
- [ ] Fails gracefully if worktree already exists

---

## Task 2.2: Create worktrees listing command

**File(s):**
- `ktrdr/cli/kinfra/worktrees.py` (create)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** External (git)

**Description:**
Implement `kinfra worktrees` command that lists all active worktrees with their type (spec/impl) and sandbox status.

**Implementation Notes:**
- Parse output of `git worktree list --porcelain`
- Identify type from directory name: `ktrdr-spec-*` vs `ktrdr-impl-*`
- For impl worktrees, show claimed slot (will integrate with registry in M4)
- Use Rich for table output (matches existing CLI patterns)

**Code sketch:**
```python
import subprocess
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

console = Console()

@app.command()
def worktrees():
    """List active worktrees with sandbox status."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True
    )

    worktrees = _parse_worktree_list(result.stdout)

    table = Table(title="Active Worktrees")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Branch")
    table.add_column("Sandbox")

    for wt in worktrees:
        name = Path(wt["path"]).name

        if "ktrdr-spec-" in name:
            wt_type = "spec"
            sandbox = "-"
        elif "ktrdr-impl-" in name:
            wt_type = "impl"
            sandbox = "slot ?"  # Will be filled in M4
        else:
            continue  # Skip main worktree

        table.add_row(name, wt_type, wt.get("branch", ""), sandbox)

    console.print(table)


def _parse_worktree_list(output: str) -> list[dict]:
    """Parse git worktree list --porcelain output."""
    worktrees = []
    current = {}

    for line in output.strip().split("\n"):
        if not line:
            if current:
                worktrees.append(current)
                current = {}
        elif line.startswith("worktree "):
            current["path"] = line[9:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")

    if current:
        worktrees.append(current)

    return worktrees
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_parse_worktree_list` — correctly parses git output
- [ ] `test_identifies_spec_worktrees` — spec type detected
- [ ] `test_identifies_impl_worktrees` — impl type detected
- [ ] `test_excludes_main_worktree` — main repo not in list

*Smoke Test:*
```bash
uv run kinfra worktrees
```

**Acceptance Criteria:**
- [ ] Lists all spec and impl worktrees
- [ ] Shows worktree type (spec/impl)
- [ ] Shows branch name
- [ ] Excludes main worktree from list
- [ ] Clean table output with Rich

---

## Task 2.3: Add error types for worktree operations

**File(s):**
- `ktrdr/cli/kinfra/errors.py` (create)

**Type:** CODING
**Task Categories:** Cross-Component

**Description:**
Create error types for worktree and slot operations. These will be used across kinfra commands.

**Implementation Notes:**
From architecture doc error table:
- `WorktreeExistsError` — worktree already exists
- `WorktreeDirtyError` — uncommitted/unpushed changes (used in M5)
- `SlotExhaustedError` — no slots available (used in M4)
- `SlotClaimedError` — slot already claimed (used in M4)
- `MilestoneNotFoundError` — milestone file not found (used in M4)
- `SandboxStartError` — docker compose failed (used in M4)
- `InvalidOperationError` — invalid operation (e.g., done on spec)

**Code sketch:**
```python
"""Error types for kinfra commands."""


class KinfraError(Exception):
    """Base exception for kinfra commands."""
    pass


class WorktreeExistsError(KinfraError):
    """Worktree already exists."""
    pass


class WorktreeDirtyError(KinfraError):
    """Worktree has uncommitted or unpushed changes."""
    pass


class SlotExhaustedError(KinfraError):
    """All sandbox slots are in use."""
    pass


class SlotClaimedError(KinfraError):
    """Slot is already claimed by another worktree."""
    pass


class MilestoneNotFoundError(KinfraError):
    """Milestone file not found in design folder."""
    pass


class SandboxStartError(KinfraError):
    """Failed to start sandbox containers."""
    pass


class InvalidOperationError(KinfraError):
    """Operation not valid for this worktree type."""
    pass
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_error_hierarchy` — all errors inherit from KinfraError
- [ ] `test_error_messages` — errors have descriptive messages

**Acceptance Criteria:**
- [ ] All error types from architecture doc defined
- [ ] Errors inherit from common base class
- [ ] Error messages match architecture doc

---

## Task 2.4: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 15 min

**Description:**
Validate M2 is complete using the E2E agent workflow.

**E2E Test: infra/spec-workflow**

This test validates:
1. `kinfra spec` creates a git worktree
2. Design folder is created
3. Branch is created/reused
4. `kinfra worktrees` lists the spec worktree

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | `uv run kinfra spec e2e-test` | Success message | Exit code 0 |
| 2 | `ls ../ktrdr-spec-e2e-test/` | Directory exists | Exit code 0 |
| 3 | `ls ../ktrdr-spec-e2e-test/docs/designs/e2e-test/` | Design folder exists | Exit code 0 |
| 4 | `git branch --list spec/e2e-test` | Branch exists | Non-empty output |
| 5 | `uv run kinfra worktrees` | Shows e2e-test worktree | Table contains "e2e-test" |
| 6 | Cleanup: `git worktree remove ../ktrdr-spec-e2e-test && git branch -d spec/e2e-test` | Clean removal | Exit code 0 |

**Success Criteria:**
- [ ] Worktree created at correct location
- [ ] Design folder created
- [ ] Branch created
- [ ] Appears in worktrees list
- [ ] Cleanup successful

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] No regressions from M1
- [ ] `make quality` passes

---

## Milestone 2 Verification

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
