"""Done command for kinfra.

Completes a worktree, releases its sandbox slot, and removes the worktree
with dirty state protection.
"""

import subprocess
from pathlib import Path

import typer

from ktrdr.cli.sandbox_registry import load_registry

done_app = typer.Typer(
    name="done",
    help="Complete worktree, release sandbox slot, remove worktree",
)


def _find_worktree(name: str, parent_path: Path | None = None) -> Path:
    """Find worktree by name (partial match supported).

    Args:
        name: Worktree name or partial match
        parent_path: Parent directory to search (defaults to cwd parent)

    Returns:
        Path to the worktree directory

    Raises:
        typer.BadParameter: If no worktree matches
    """
    if parent_path is None:
        parent_path = Path.cwd().parent

    # Try exact match first
    for prefix in ["ktrdr-impl-", "ktrdr-spec-"]:
        path = parent_path / f"{prefix}{name}"
        if path.exists():
            return path

    # Try partial match
    for path in parent_path.iterdir():
        if path.is_dir() and name in path.name:
            if path.name.startswith("ktrdr-impl-") or path.name.startswith(
                "ktrdr-spec-"
            ):
                return path

    raise typer.BadParameter(f"No worktree found matching: {name}")


def _has_uncommitted_changes(worktree_path: Path) -> bool:
    """Check for uncommitted changes.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if there are uncommitted changes
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
    )
    return bool(result.stdout.strip())


def _has_unpushed_commits(worktree_path: Path) -> bool:
    """Check for unpushed commits.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if there are unpushed commits or no upstream
    """
    result = subprocess.run(
        ["git", "log", "@{u}..HEAD", "--oneline"],
        capture_output=True,
        text=True,
        cwd=worktree_path,
    )
    # If no upstream, this will fail - treat as "has unpushed"
    if result.returncode != 0:
        # Check if there's a remote branch
        result2 = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )
        if result2.returncode != 0:
            # No upstream tracking - check if there are any commits
            result3 = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True,
                text=True,
                cwd=worktree_path,
            )
            return bool(result3.stdout.strip())
    return bool(result.stdout.strip())


@done_app.callback(invoke_without_command=True)
def done(
    name: str = typer.Argument(..., help="Worktree name (e.g., genome-M1)"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cleanup even with uncommitted/unpushed changes",
    ),
) -> None:
    """Complete worktree, release sandbox, remove worktree."""
    # Import here to allow mocking
    from ktrdr.cli.kinfra.override import remove_override
    from ktrdr.cli.kinfra.slots import stop_slot_containers

    worktree_path = _find_worktree(name)
    worktree_name = worktree_path.name

    # Check if spec worktree
    if worktree_name.startswith("ktrdr-spec-"):
        typer.secho(
            "Spec worktrees don't have sandboxes to release. "
            f"Just run: git worktree remove {worktree_path}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Check dirty state (GAP-4)
    if not force:
        if _has_uncommitted_changes(worktree_path):
            typer.secho(
                "Worktree has uncommitted changes. "
                "Commit or stash, then retry. Use --force to proceed anyway.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        if _has_unpushed_commits(worktree_path):
            typer.secho(
                "Worktree has unpushed commits. "
                "Push first, then retry. Use --force to proceed anyway.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    # Find claimed slot
    registry = load_registry()
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
    remove_cmd = ["git", "worktree", "remove", str(worktree_path)]
    if force:
        remove_cmd.append("--force")
    subprocess.run(remove_cmd, check=True)

    typer.echo(f"Done! Completed {worktree_name}")
