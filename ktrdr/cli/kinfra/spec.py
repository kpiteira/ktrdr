"""Spec worktree command for kinfra.

Creates git worktrees for spec/design work without claiming a sandbox slot.
"""

import subprocess
from pathlib import Path

import typer

spec_app = typer.Typer(
    name="spec",
    help="Create spec worktree for design work",
)


@spec_app.callback(invoke_without_command=True)
def spec(
    feature: str = typer.Argument(..., help="Feature name for spec worktree"),
) -> None:
    """Create a spec worktree for design work (no sandbox).

    Creates a git worktree at ../ktrdr-spec-<feature>/ with a spec/<feature> branch.
    Also creates the design folder at docs/designs/<feature>/.
    """
    repo_root = Path.cwd()
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

    # Create worktree
    if branch_exists:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            check=True,
            cwd=repo_root,
        )
    else:
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            check=True,
            cwd=repo_root,
        )

    # Create design folder if needed
    design_dir = worktree_path / "docs" / "designs" / feature
    design_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Created spec worktree at {worktree_path}")
    typer.echo(f"Design folder: {design_dir}")
