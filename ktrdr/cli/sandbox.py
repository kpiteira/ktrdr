"""Sandbox management CLI commands.

This module provides commands for managing isolated development sandbox instances.
Each sandbox runs in its own git worktree with isolated Docker containers.
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from ktrdr.cli.sandbox_ports import check_ports_available, get_ports
from ktrdr.cli.sandbox_registry import (
    InstanceInfo,
    add_instance,
    allocate_next_slot,
    get_allocated_slots,
)

sandbox_app = typer.Typer(
    name="sandbox",
    help="Manage isolated development sandbox instances",
    no_args_is_help=True,
)

console = Console()
error_console = Console(stderr=True)


def slugify(name: str) -> str:
    """Convert name to valid Docker/filesystem identifier.

    Args:
        name: The name to slugify.

    Returns:
        Lowercase string with only alphanumeric chars and dashes.
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def derive_instance_id(path: Path) -> str:
    """Derive instance ID from directory path.

    Args:
        path: The path to the instance directory.

    Returns:
        The directory name as the instance ID.
    """
    return path.name


def generate_env_file(path: Path, instance_id: str, slot: int) -> None:
    """Generate .env.sandbox file for instance.

    Args:
        path: Directory to write the file to.
        instance_id: The instance identifier.
        slot: The allocated port slot (1-10).
    """
    allocation = get_ports(slot)
    env_vars = allocation.to_env_dict()

    # Add instance identity
    env_vars["INSTANCE_ID"] = instance_id
    env_vars["COMPOSE_PROJECT_NAME"] = instance_id

    # Add shared data dir
    env_vars["KTRDR_SHARED_DIR"] = str(Path.home() / ".ktrdr" / "shared")

    # Add metadata
    env_vars["CREATED_AT"] = datetime.now(timezone.utc).isoformat()
    env_vars["SANDBOX_VERSION"] = "1"

    # Write file
    env_file = path / ".env.sandbox"
    with open(env_file, "w") as f:
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


def branch_exists(branch: str) -> bool:
    """Check if a git branch exists.

    Args:
        branch: The branch name to check.

    Returns:
        True if the branch exists, False otherwise.
    """
    result = subprocess.run(
        ["git", "branch", "--list", branch], capture_output=True, text=True
    )
    return bool(result.stdout.strip())


@sandbox_app.command()
def create(
    name: str = typer.Argument(
        ..., help="Instance name (will be prefixed with ktrdr--)"
    ),
    branch: str = typer.Option(None, "--branch", "-b", help="Git branch to checkout"),
    slot: int = typer.Option(
        None, "--slot", "-s", help="Force specific port slot (1-10)"
    ),
) -> None:
    """Create a new sandbox instance using git worktree."""
    # Derive paths
    current_repo = Path.cwd()
    instance_name = f"ktrdr--{slugify(name)}"
    worktree_path = current_repo.parent / instance_name

    # Check if already exists
    if worktree_path.exists():
        error_console.print(
            f"[red]Error:[/red] Directory already exists: {worktree_path}"
        )
        raise typer.Exit(1)

    # Validate and allocate slot
    if slot is not None:
        if slot < 1 or slot > 10:
            error_console.print("[red]Error:[/red] Slot must be 1-10")
            raise typer.Exit(1)
        if slot in get_allocated_slots():
            error_console.print(f"[red]Error:[/red] Slot {slot} already in use")
            raise typer.Exit(1)
    else:
        try:
            slot = allocate_next_slot()
        except RuntimeError as e:
            error_console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1) from e

    # Check port conflicts
    conflicts = check_ports_available(slot)
    if conflicts:
        error_console.print(f"[red]Error:[/red] Ports in use: {conflicts}")
        error_console.print("Use a different slot or resolve the conflicts.")
        raise typer.Exit(1)

    # Create worktree
    console.print(f"Creating worktree at {worktree_path}...")
    cmd = ["git", "worktree", "add", str(worktree_path)]
    if branch:
        if branch_exists(branch):
            cmd.append(branch)
        else:
            cmd.extend(["-b", branch])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error creating worktree:[/red] {e.stderr}")
        raise typer.Exit(2) from e

    # Generate .env.sandbox
    instance_id = derive_instance_id(worktree_path)
    generate_env_file(worktree_path, instance_id, slot)

    # Register instance
    add_instance(
        InstanceInfo(
            instance_id=instance_id,
            slot=slot,
            path=str(worktree_path),
            created_at=datetime.now(timezone.utc).isoformat(),
            is_worktree=True,
            parent_repo=str(current_repo),
        )
    )

    # Report success
    ports = get_ports(slot)
    console.print(f"\n[green]Created instance:[/green] {name}")
    console.print(f"  Location: {worktree_path}")
    console.print(f"  Port slot: {slot}")
    console.print(f"  API: http://localhost:{ports.backend}")
    console.print(f"  Grafana: http://localhost:{ports.grafana}")
    console.print(f"\nRun 'cd {worktree_path} && ktrdr sandbox up' to start")
