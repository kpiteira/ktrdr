"""Worktrees listing command for kinfra.

Lists all active spec and impl worktrees with their type, branch, and sandbox status.
"""

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

worktrees_app = typer.Typer(
    name="worktrees",
    help="List active worktrees with sandbox status",
)

console = Console()


def _parse_worktree_list(output: str) -> list[dict]:
    """Parse git worktree list --porcelain output.

    Args:
        output: Raw output from git worktree list --porcelain

    Returns:
        List of dicts with 'path' and optionally 'branch' keys
    """
    worktrees = []
    current: dict[str, str] = {}

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


@worktrees_app.callback(invoke_without_command=True)
def worktrees() -> None:
    """List active worktrees with sandbox status."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        console.print(
            "[red]Error:[/red] 'git' command not found. "
            "Please ensure Git is installed and available on your PATH."
        )
        raise typer.Exit(code=1) from None
    except subprocess.CalledProcessError:
        console.print(
            "[red]Error:[/red] Failed to list git worktrees. "
            "Make sure you are in a git repository."
        )
        raise typer.Exit(code=1) from None

    wt_list = _parse_worktree_list(result.stdout)

    table = Table(title="Active Worktrees")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Branch")
    table.add_column("Sandbox")

    for wt in wt_list:
        name = Path(wt["path"]).name

        if name.startswith("ktrdr-spec-"):
            wt_type = "spec"
            sandbox = "-"
        elif name.startswith("ktrdr-impl-"):
            wt_type = "impl"
            sandbox = "slot ?"  # Will be filled in M4
        else:
            continue  # Skip main worktree

        table.add_row(name, wt_type, wt.get("branch", ""), sandbox)

    console.print(table)
