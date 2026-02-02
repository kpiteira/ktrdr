"""Spec worktree command for kinfra.

Creates git worktrees for spec/design work without claiming a sandbox slot.
"""

import re
import subprocess
from pathlib import Path

import typer

spec_app = typer.Typer(
    name="spec",
    help="Create spec worktree for design work",
)

# Valid feature name pattern: alphanumeric, hyphens, underscores only
FEATURE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        cwd=path,
    )
    return result.returncode == 0


def _validate_feature_name(feature: str) -> bool:
    """Validate feature name contains only safe characters.

    Prevents path traversal and command injection by allowing only
    alphanumeric characters, hyphens, and underscores.
    """
    return bool(FEATURE_NAME_PATTERN.match(feature))


@spec_app.callback(invoke_without_command=True)
def spec(
    feature: str = typer.Argument(..., help="Feature name for spec worktree"),
) -> None:
    """Create a spec worktree for design work (no sandbox).

    Creates a git worktree at ../ktrdr-spec-<feature>/ with a spec/<feature> branch.
    Also creates the design folder at docs/designs/<feature>/.
    """
    repo_root = Path.cwd()

    # Validate we're in a git repository
    if not _is_git_repo(repo_root):
        typer.secho(
            "Error: Not in a git repository. Run this command from the repo root.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Validate feature name
    if not _validate_feature_name(feature):
        typer.secho(
            f"Error: Invalid feature name '{feature}'. "
            "Use only alphanumeric characters, hyphens, and underscores.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    worktree_path = repo_root.parent / f"ktrdr-spec-{feature}"
    branch_name = f"spec/{feature}"

    # Check if worktree already exists
    if worktree_path.exists():
        typer.secho(
            f"Error: Worktree {worktree_path.name} already exists",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Check if branch exists
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    branch_exists = bool(result.stdout.strip())

    # Fetch latest from origin (so worktree starts from latest remote)
    typer.echo("Fetching latest from origin...")
    fetch_result = subprocess.run(
        ["git", "fetch", "origin", "main"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if fetch_result.returncode != 0:
        typer.secho(
            "Warning: Could not fetch from origin. Worktree will start from local HEAD.",
            fg=typer.colors.YELLOW,
        )
        start_point = None
    else:
        start_point = "origin/main"

    # Create worktree
    try:
        if branch_exists:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch_name],
                check=True,
                cwd=repo_root,
            )
        else:
            # Create new branch from origin/main (or local HEAD if fetch failed)
            cmd = ["git", "worktree", "add", "-b", branch_name, str(worktree_path)]
            if start_point:
                cmd.append(start_point)
            subprocess.run(
                cmd,
                check=True,
                cwd=repo_root,
            )
    except subprocess.CalledProcessError:
        typer.secho(
            "Error: Failed to create git worktree.",
            fg=typer.colors.RED,
        )
        typer.secho(
            "Hint: Ensure the branch is not already checked out in another worktree "
            "and that your git repository is in a valid state.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1) from None

    # Create design folder if needed
    design_dir = worktree_path / "docs" / "designs" / feature
    design_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Created spec worktree at {worktree_path}")
    typer.echo(f"Design folder: {design_dir}")
