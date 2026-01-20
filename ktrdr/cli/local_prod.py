"""Local-prod CLI commands.

Local-prod is a singleton production-like environment that uses slot 0 (standard ports).
Unlike sandboxes which use git worktrees, local-prod must be a clone of the repository.

Key differences from sandbox:
- Singleton (only one local-prod allowed)
- Must be a clone (not worktree) - user clones manually, then runs `init`
- Uses slot 0 (standard ports: 8000, 5432, 3000, etc.)
- destroy operates via registry lookup (can be run from anywhere)
- Uses different 1Password item: 'ktrdr-local-prod'

Commands are thin wrappers over instance_core.py - no duplicated Docker logic.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ktrdr.cli.instance_core import (
    generate_env_file,
    load_env_file,
    show_instance_logs,
    start_instance,
    stop_instance,
)
from ktrdr.cli.sandbox import is_ktrdr_repo
from ktrdr.cli.sandbox_ports import get_ports
from ktrdr.cli.sandbox_registry import (
    InstanceInfo,
    clear_local_prod,
    get_local_prod,
    local_prod_exists,
    set_local_prod,
)

local_prod_app = typer.Typer(
    name="local-prod",
    help="Manage the local-prod production-like environment",
    no_args_is_help=True,
)

console = Console()
error_console = Console(stderr=True)

# Local-prod specific constants
LOCAL_PROD_NAME = "ktrdr-prod"
LOCAL_PROD_SLOT = 0
LOCAL_PROD_SECRETS_ITEM = "ktrdr-local-prod"  # Different from sandbox!


def _is_clone_not_worktree(path: Path) -> bool:
    """Check if path is a clone (not worktree).

    Worktrees have .git as a FILE pointing to the main repo.
    Clones have .git as a DIRECTORY containing the full git database.

    Args:
        path: Directory to check.

    Returns:
        True if this is a clone, False if worktree or not a git repo.
    """
    git_path = path / ".git"
    return git_path.is_dir()


def _require_local_prod_context() -> dict[str, str]:
    """Require current directory to be the local-prod instance.

    Returns:
        Environment dict from .env.sandbox

    Raises:
        typer.Exit: If not in a local-prod directory.
    """
    cwd = Path.cwd()
    env = load_env_file(cwd)

    if not env:
        error_console.print(
            "[red]Error:[/red] Not in local-prod directory (.env.sandbox not found)"
        )
        error_console.print("Run 'ktrdr local-prod init' to initialize this directory.")
        raise typer.Exit(1)

    return env


@local_prod_app.command()
def init() -> None:
    """Initialize current directory as local-prod.

    This command initializes an existing KTRDR clone as the local-prod
    production-like environment. It validates that:
    - The directory is a clone (not a worktree)
    - No local-prod already exists (singleton)
    - The directory is a KTRDR repository

    Use this after manually cloning the repository:
        git clone https://github.com/kpiteira/ktrdr.git ~/ktrdr-prod
        cd ~/ktrdr-prod
        uv sync
        ktrdr local-prod init
    """
    cwd = Path.cwd()

    # Check if already initialized
    if (cwd / ".env.sandbox").exists():
        error_console.print("[red]Error:[/red] Already initialized")
        error_console.print(f"  .env.sandbox exists at {cwd / '.env.sandbox'}")
        raise typer.Exit(1)

    # Validate this is a clone, not a worktree
    if not _is_clone_not_worktree(cwd):
        error_console.print("[red]Error:[/red] This must be a clone, not a worktree")
        error_console.print("  Worktrees have .git as a file")
        error_console.print("  Clones have .git as a directory")
        error_console.print("")
        error_console.print("Create local-prod by cloning:")
        error_console.print(
            "  git clone https://github.com/kpiteira/ktrdr.git ~/ktrdr-prod"
        )
        raise typer.Exit(2)

    # Validate this is a KTRDR repo
    if not is_ktrdr_repo(cwd):
        error_console.print("[red]Error:[/red] Not a KTRDR repository")
        error_console.print("  Git remote should contain 'ktrdr'")
        raise typer.Exit(2)

    # Check singleton constraint
    if local_prod_exists():
        existing = get_local_prod()
        error_console.print("[red]Error:[/red] Local-prod already exists")
        if existing:
            error_console.print(f"  Existing location: {existing.path}")
        error_console.print("")
        error_console.print("Only one local-prod instance is allowed.")
        error_console.print(
            "Use 'ktrdr local-prod destroy' to remove the existing one first."
        )
        raise typer.Exit(1)

    # Generate .env.sandbox with slot 0
    generate_env_file(cwd, LOCAL_PROD_NAME, LOCAL_PROD_SLOT)

    # Register in registry
    set_local_prod(
        InstanceInfo(
            instance_id=LOCAL_PROD_NAME,
            slot=LOCAL_PROD_SLOT,
            path=str(cwd),
            created_at=datetime.now(timezone.utc).isoformat(),
            is_worktree=False,  # Always false for local-prod
            parent_repo=None,
        )
    )

    # Report success
    ports = get_ports(LOCAL_PROD_SLOT)
    console.print(f"\n[green]Local-prod initialized:[/green] {LOCAL_PROD_NAME}")
    console.print(f"  Location: {cwd}")
    console.print(f"  Port slot: {LOCAL_PROD_SLOT} (standard ports)")
    console.print(f"  API: http://localhost:{ports.backend}")
    console.print(f"  Grafana: http://localhost:{ports.grafana}")
    console.print("\nRun 'ktrdr local-prod up' to start")


@local_prod_app.command()
def up(
    no_wait: bool = typer.Option(
        False, "--no-wait", help="Don't wait for Startability Gate"
    ),
    build: bool = typer.Option(False, "--build", help="Force rebuild images"),
    timeout: int = typer.Option(120, "--timeout", help="Gate timeout in seconds"),
    no_secrets: bool = typer.Option(
        False, "--no-secrets", help="Skip 1Password secrets (use defaults)"
    ),
) -> None:
    """Start the local-prod stack.

    Starts Docker containers with the 'local-prod' profile which includes
    all 4 workers. Secrets are fetched from 1Password item 'ktrdr-local-prod'.
    """
    _require_local_prod_context()
    cwd = Path.cwd()

    exit_code = start_instance(
        path=cwd,
        wait=not no_wait,
        build=build,
        timeout=timeout,
        no_secrets=no_secrets,
        profile="local-prod",
        secrets_item=LOCAL_PROD_SECRETS_ITEM,
    )

    if exit_code != 0:
        raise typer.Exit(exit_code)


@local_prod_app.command()
def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Also remove volumes"),
) -> None:
    """Stop the local-prod stack."""
    _require_local_prod_context()
    cwd = Path.cwd()

    exit_code = stop_instance(path=cwd, remove_volumes=volumes, profile="local-prod")

    if exit_code != 0:
        raise typer.Exit(exit_code)


@local_prod_app.command()
def destroy(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove the local-prod instance.

    IMPORTANT: This command operates on the REGISTERED local-prod instance,
    not the current directory. This is different from 'sandbox destroy'.

    The clone directory is preserved - only containers, volumes, and
    registry entry are removed. You can re-initialize with 'ktrdr local-prod init'.
    """
    # CRITICAL: Use registry lookup, NOT current directory
    if not local_prod_exists():
        error_console.print("[red]Error:[/red] No local-prod instance exists")
        error_console.print("Nothing to destroy.")
        raise typer.Exit(1)

    info = get_local_prod()
    if not info:
        error_console.print("[red]Error:[/red] Local-prod registry entry is invalid")
        raise typer.Exit(1)

    local_prod_path = Path(info.path)

    # Safety check: warn if current directory is different
    cwd = Path.cwd()
    if cwd.resolve() != local_prod_path.resolve():
        console.print(
            f"[yellow]Note:[/yellow] Destroying local-prod at {local_prod_path}"
        )
        console.print(f"  (Current directory is {cwd})")

    # Confirm unless forced
    if not force:
        confirm = typer.confirm(
            f"Destroy local-prod at '{local_prod_path}'? Containers and volumes will be removed."
        )
        if not confirm:
            raise typer.Abort()

    console.print(f"Destroying local-prod: {info.instance_id}")

    # Stop containers and remove volumes (if local-prod path exists and has .env.sandbox)
    if local_prod_path.exists() and (local_prod_path / ".env.sandbox").exists():
        exit_code = stop_instance(
            path=local_prod_path, remove_volumes=True, profile="local-prod"
        )
        if exit_code == 0:
            console.print("  ✓ Containers stopped and volumes removed")
        else:
            console.print("  ⚠ Could not stop containers (may already be stopped)")

        # Remove .env.sandbox (but keep the clone)
        env_file = local_prod_path / ".env.sandbox"
        if env_file.exists():
            env_file.unlink()
            console.print("  ✓ .env.sandbox removed")
    else:
        console.print("  ⚠ Local-prod directory or .env.sandbox not found")

    # Clear from registry
    clear_local_prod()
    console.print("  ✓ Registry cleared")

    console.print("\n[green]Local-prod destroyed[/green]")
    console.print(f"[dim]Clone directory preserved at: {local_prod_path}[/dim]")


@local_prod_app.command()
def status() -> None:
    """Show status of the local-prod instance."""
    env = _require_local_prod_context()

    instance_id = env.get("INSTANCE_ID", "unknown")
    slot = env.get("SLOT_NUMBER", "0")

    console.print(f"[bold]Instance:[/bold] {instance_id} (slot {slot})")

    # Service URLs
    api_port = env.get("KTRDR_API_PORT", "8000")
    db_port = env.get("KTRDR_DB_PORT", "5432")
    grafana_port = env.get("KTRDR_GRAFANA_PORT", "3000")
    jaeger_port = env.get("KTRDR_JAEGER_UI_PORT", "16686")

    console.print()
    console.print("[bold]Services:[/bold]")
    console.print(f"  Backend:    http://localhost:{api_port}")
    console.print(f"  API Docs:   http://localhost:{api_port}/api/v1/docs")
    console.print(f"  Database:   localhost:{db_port}")
    console.print(f"  Grafana:    http://localhost:{grafana_port}")
    console.print(f"  Jaeger:     http://localhost:{jaeger_port}")

    console.print()
    console.print("[bold]Workers:[/bold]")
    for i in range(1, 5):
        port = env.get(f"KTRDR_WORKER_PORT_{i}", "?")
        console.print(f"  Worker {i}:   http://localhost:{port}")


@local_prod_app.command()
def logs(
    service: Optional[str] = typer.Argument(
        None, help="Service name (e.g., backend, db)"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """View logs for local-prod services."""
    _require_local_prod_context()
    cwd = Path.cwd()

    exit_code = show_instance_logs(path=cwd, service=service, follow=follow, tail=tail)

    if exit_code != 0:
        raise typer.Exit(exit_code)
