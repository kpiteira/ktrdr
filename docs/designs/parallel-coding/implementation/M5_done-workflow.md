---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Done Workflow

**Branch:** `feature/kinfra-done-workflow`
**Builds on:** M4 (impl workflow exists)

## Goal

Enable users to complete worktrees cleanly, releasing sandbox slots and removing worktrees. Protect against accidental data loss with dirty state checking.

---

## Task 5.1: Create done command

**File(s):**
- `ktrdr/cli/kinfra/done.py` (create)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** External (git, docker), State Machine, Cross-Component

**Description:**
Implement `kinfra done <name>` command that completes a worktree, releases its slot, and removes the worktree.

**Implementation Notes:**
Per GAP-4 resolution: Check for dirty state, abort unless `--force`.

Order of operations:
1. Find worktree by name
2. Check if spec worktree (no sandbox to release)
3. Check uncommitted changes: `git status --porcelain`
4. Check unpushed commits: `git log @{u}..HEAD`
5. Abort if dirty (unless --force)
6. Stop containers
7. Remove override file
8. Release slot in registry
9. Remove worktree

**Code sketch:**
```python
import subprocess
from pathlib import Path
import typer

from .errors import InvalidOperationError, WorktreeDirtyError
from .override import remove_override
from .slots import stop_slot_containers
from ..sandbox_registry import SandboxRegistry

app = typer.Typer()


def _find_worktree(name: str) -> Path:
    """Find worktree by name (partial match supported)."""
    parent = Path.cwd().parent

    # Try exact match first
    for prefix in ["ktrdr-impl-", "ktrdr-spec-"]:
        path = parent / f"{prefix}{name}"
        if path.exists():
            return path

    # Try partial match
    for path in parent.iterdir():
        if path.is_dir() and name in path.name:
            if path.name.startswith("ktrdr-impl-") or path.name.startswith("ktrdr-spec-"):
                return path

    raise typer.BadParameter(f"No worktree found matching: {name}")


def _has_uncommitted_changes(worktree_path: Path) -> bool:
    """Check for uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=worktree_path
    )
    return bool(result.stdout.strip())


def _has_unpushed_commits(worktree_path: Path) -> bool:
    """Check for unpushed commits."""
    result = subprocess.run(
        ["git", "log", "@{u}..HEAD", "--oneline"],
        capture_output=True, text=True, cwd=worktree_path
    )
    # If no upstream, this will fail - treat as "has unpushed"
    if result.returncode != 0:
        # Check if there's a remote branch
        result2 = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True, text=True, cwd=worktree_path
        )
        if result2.returncode != 0:
            # No upstream tracking - check if there are any commits
            result3 = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True, text=True, cwd=worktree_path
            )
            return bool(result3.stdout.strip())
    return bool(result.stdout.strip())


@app.command()
def done(
    name: str = typer.Argument(..., help="Worktree name (e.g., genome-M1)"),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force cleanup even with uncommitted/unpushed changes"
    ),
):
    """Complete worktree, release sandbox, remove worktree."""
    worktree_path = _find_worktree(name)
    worktree_name = worktree_path.name

    # Check if spec worktree
    if worktree_name.startswith("ktrdr-spec-"):
        raise InvalidOperationError(
            "Spec worktrees don't have sandboxes to release. "
            "Just run: git worktree remove " + str(worktree_path)
        )

    # Check dirty state (GAP-4)
    if not force:
        if _has_uncommitted_changes(worktree_path):
            raise WorktreeDirtyError(
                "Worktree has uncommitted changes. "
                "Commit or stash, then retry. Use --force to proceed anyway."
            )
        if _has_unpushed_commits(worktree_path):
            raise WorktreeDirtyError(
                "Worktree has unpushed commits. "
                "Push first, then retry. Use --force to proceed anyway."
            )

    # Find claimed slot
    registry = SandboxRegistry.load()
    slot = registry.get_slot_for_worktree(worktree_path)

    if slot:
        # Stop containers
        typer.echo(f"Stopping containers for slot {slot.slot_id}...")
        stop_slot_containers(slot)

        # Remove override
        typer.echo("Removing override file...")
        remove_override(slot)

        # Release slot
        registry.release_slot(slot.slot_id)
        typer.echo(f"Released slot {slot.slot_id}")
    else:
        typer.echo("No sandbox slot claimed (already released?)")

    # Remove worktree
    typer.echo(f"Removing worktree {worktree_name}...")
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path)],
        check=True
    )

    typer.echo(f"Done! Completed {worktree_name}")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_done_finds_worktree` — finds by name
- [ ] `test_done_finds_worktree_partial` — finds by partial name
- [ ] `test_done_checks_uncommitted` — aborts with uncommitted changes
- [ ] `test_done_checks_unpushed` — aborts with unpushed commits
- [ ] `test_done_force_ignores_dirty` — proceeds with --force
- [ ] `test_done_stops_containers` — containers stopped
- [ ] `test_done_releases_slot` — slot released in registry
- [ ] `test_done_removes_override` — override file removed
- [ ] `test_done_removes_worktree` — worktree removed
- [ ] `test_done_fails_on_spec` — raises InvalidOperationError

*Integration Tests:*
- [ ] `test_done_full_cleanup` — containers stopped, slot released, worktree gone

*Smoke Test:*
```bash
# Assumes impl worktree exists from M4
uv run kinfra done test-impl-M1 --force
uv run kinfra sandbox slots  # Should show slot available
ls ../ktrdr-impl-test-impl-M1 2>&1  # Should not exist
```

**Acceptance Criteria:**
- [ ] Finds worktree by name (exact or partial match)
- [ ] Checks for uncommitted/unpushed changes
- [ ] Aborts if dirty (unless --force)
- [ ] Stops containers
- [ ] Removes override file
- [ ] Releases slot in registry
- [ ] Removes worktree
- [ ] Fails gracefully on spec worktrees

---

## Task 5.2: Add registry lookup by worktree

**File(s):**
- `ktrdr/cli/sandbox_registry.py` (modify)

**Type:** CODING
**Task Categories:** Persistence

**Description:**
Add method to find which slot is claimed by a given worktree path.

**Code sketch:**
```python
def get_slot_for_worktree(self, worktree_path: Path) -> Optional[SlotInfo]:
    """Find the slot claimed by a worktree.

    Args:
        worktree_path: Path to the worktree directory

    Returns:
        SlotInfo if found, None if worktree has no claimed slot
    """
    worktree_path = Path(worktree_path).resolve()

    for slot_id, slot in self._data["slots"].items():
        if slot.claimed_by and Path(slot.claimed_by).resolve() == worktree_path:
            return slot

    return None
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_get_slot_for_worktree_found` — returns slot when claimed
- [ ] `test_get_slot_for_worktree_not_found` — returns None when not claimed
- [ ] `test_get_slot_for_worktree_resolves_paths` — handles relative/absolute paths

**Acceptance Criteria:**
- [ ] Can look up slot by worktree path
- [ ] Returns None if worktree has no slot
- [ ] Handles path resolution correctly

---

## Task 5.3: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 15 min

**Description:**
Validate M5 is complete.

**E2E Test: infra/done-workflow**

This test validates:
1. Dirty check works (aborts with uncommitted changes)
2. Force flag bypasses dirty check
3. Containers are stopped
4. Slot is released
5. Worktree is removed

**Prerequisites:**
- Impl worktree exists from M4 (or create new one)

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Create impl worktree if needed | Worktree exists | `ls ../ktrdr-impl-test-impl-M1/` |
| 2 | Create dirty state: `echo "dirty" > ../ktrdr-impl-test-impl-M1/dirty.txt` | File created | Exit code 0 |
| 3 | `uv run kinfra done test-impl-M1` | Aborts with error | Exit code != 0, "uncommitted" in output |
| 4 | `uv run kinfra done test-impl-M1 --force` | Succeeds | Exit code 0 |
| 5 | `uv run kinfra sandbox slots` | Slot available | No "test-impl-M1" in output |
| 6 | `docker ps` | Containers stopped | No slot containers running |
| 7 | `ls ../ktrdr-impl-test-impl-M1` | Worktree gone | Exit code != 0 |

**Cleanup:**
```bash
# Remove test design folder
rm -rf docs/designs/test-impl/
```

**Success Criteria:**
- [ ] Dirty check works (aborts without --force)
- [ ] Force flag works
- [ ] Slot released
- [ ] Containers stopped
- [ ] Worktree removed

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] No regressions from M1-M4
- [ ] `make quality` passes

---

## Milestone 5 Verification

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
