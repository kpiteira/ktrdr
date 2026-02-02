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

Host services (training-host, ib-host) run natively on the host machine with GPU access.
They require secrets from 1Password to connect to the database.
"""

import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.helpers import (
    OnePasswordError,
    check_1password_authenticated,
    fetch_secrets_from_1password,
    is_ktrdr_repo,
)
from ktrdr.cli.instance_core import (
    generate_env_file,
    load_env_file,
    show_instance_logs,
    start_instance,
    stop_instance,
)
from ktrdr.cli.sandbox_ports import get_ports
from ktrdr.cli.sandbox_registry import (
    InstanceInfo,
    clear_local_prod,
    get_local_prod,
    local_prod_exists,
    set_local_prod,
)


class HostServiceConfig(TypedDict):
    """Type definition for host service configuration."""

    name: str
    subdir: str
    main: str
    port: int
    pid_file: str
    log_file: str


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
        ktrdr_env="production",  # Production mode requires secure credentials
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


# =============================================================================
# Host Services Management
# =============================================================================
# Host services run natively on the host machine (not in Docker) for GPU access.
# They need secrets from 1Password to connect to the database.

# Mapping from 1Password field labels to environment variable names
# Note: Uses KTRDR_* names for KTRDR settings (M6 migration)
HOST_SERVICE_SECRETS_MAP = {
    "db_password": "KTRDR_DB_PASSWORD",
    "anthropic_api_key": "ANTHROPIC_API_KEY",  # Third-party, keep original name
}

# Host service configurations
HOST_SERVICES: dict[str, HostServiceConfig] = {
    "training-host": {
        "name": "Training Host Service",
        "subdir": "training-host-service",
        "main": "main.py",
        "port": 5002,
        "pid_file": ".training-host.pid",
        "log_file": "logs/training-host-service.log",
    },
    "ib-host": {
        "name": "IB Host Service",
        "subdir": "ib-host-service",
        "main": "main.py",
        "port": 5001,
        "pid_file": ".ib-host.pid",
        "log_file": "logs/ib-host-service.log",
    },
}


def _get_host_service_env(cwd: Path) -> dict[str, str]:
    """Get environment variables for host services from 1Password.

    Fetches secrets from 1Password and maps them to environment variables.
    Also includes database connection settings and shared directories for local-prod.

    Args:
        cwd: Local-prod directory (ktrdr-prod root)

    Returns:
        Dict of environment variable name -> value

    Raises:
        typer.Exit: If 1Password authentication fails
    """
    if not check_1password_authenticated():
        error_console.print("[red]Error:[/red] Not authenticated to 1Password")
        error_console.print("Run: op signin")
        raise typer.Exit(1)

    try:
        secrets = fetch_secrets_from_1password(LOCAL_PROD_SECRETS_ITEM)
    except OnePasswordError as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Build environment with secrets
    env = os.environ.copy()

    # Map secrets to environment variables
    for secret_key, env_var in HOST_SERVICE_SECRETS_MAP.items():
        if secret_key in secrets:
            env[env_var] = secrets[secret_key]

    # Validate required secrets are present
    required_secrets = [
        "db_password"
    ]  # KTRDR_DB_PASSWORD is required for database connection
    missing = [s for s in required_secrets if s not in secrets]
    if missing:
        error_console.print("[red]Error:[/red] Missing required secrets in 1Password:")
        for secret in missing:
            env_var = HOST_SERVICE_SECRETS_MAP.get(secret, secret.upper())
            error_console.print(f"  - {secret} (for {env_var})")
        error_console.print(
            f"\nAdd these fields to the '{LOCAL_PROD_SECRETS_ITEM}' item in 1Password."
        )
        raise typer.Exit(1)

    # Add database connection settings for local-prod (slot 0)
    # Uses KTRDR_* naming convention (M6 migration)
    env["KTRDR_DB_HOST"] = "localhost"
    env["KTRDR_DB_PORT"] = "5432"
    env["KTRDR_DB_NAME"] = "ktrdr"
    env["KTRDR_DB_USER"] = "ktrdr"

    # Read shared directory paths from .env.sandbox
    # (These are set by instance_core.py to point to ~/.ktrdr/shared/)
    sandbox_env = load_env_file(cwd)
    if sandbox_env:
        shared_fallback = Path.home() / ".ktrdr" / "shared"
        env["KTRDR_DATA_DIR"] = sandbox_env.get(
            "KTRDR_DATA_DIR", str(shared_fallback / "data")
        )
        env["KTRDR_MODELS_DIR"] = sandbox_env.get(
            "KTRDR_MODELS_DIR", str(shared_fallback / "models")
        )
        env["KTRDR_STRATEGIES_DIR"] = sandbox_env.get(
            "KTRDR_STRATEGIES_DIR", str(shared_fallback / "strategies")
        )
    else:
        # Fallback to canonical shared directory if .env.sandbox missing
        shared_dir = Path.home() / ".ktrdr" / "shared"
        env["KTRDR_DATA_DIR"] = str(shared_dir / "data")
        env["KTRDR_MODELS_DIR"] = str(shared_dir / "models")
        env["KTRDR_STRATEGIES_DIR"] = str(shared_dir / "strategies")

    return env


def _get_host_service_pid(cwd: Path, service_id: str) -> Optional[int]:
    """Get PID of running host service.

    Args:
        cwd: Local-prod directory
        service_id: Service identifier (e.g., 'training-host')

    Returns:
        PID if service is running, None otherwise
    """
    config = HOST_SERVICES.get(service_id)
    if not config:
        return None

    pid_file = cwd / config["pid_file"]
    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file exists but process is not running - clean up
        pid_file.unlink(missing_ok=True)
        return None


def _start_host_service(cwd: Path, service_id: str, env: dict[str, str]) -> int:
    """Start a host service as a background process.

    Args:
        cwd: Local-prod directory
        service_id: Service identifier (e.g., 'training-host')
        env: Environment variables including secrets

    Returns:
        PID of started process, or 0 if failed
    """
    config = HOST_SERVICES.get(service_id)
    if not config:
        error_console.print(f"[red]Error:[/red] Unknown service: {service_id}")
        return 0

    service_dir = cwd / config["subdir"]
    if not service_dir.exists():
        error_console.print(
            f"[red]Error:[/red] Service directory not found: {service_dir}"
        )
        return 0

    main_file = service_dir / config["main"]
    if not main_file.exists():
        error_console.print(f"[red]Error:[/red] Main file not found: {main_file}")
        return 0

    # Create logs directory
    logs_dir = cwd / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = cwd / config["log_file"]
    pid_file = cwd / config["pid_file"]

    # Set PYTHONPATH to include the repo root for ktrdr imports
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join([str(cwd), existing_pythonpath])
    else:
        env["PYTHONPATH"] = str(cwd)

    # Start the service
    with open(log_file, "w") as log:
        process = subprocess.Popen(
            ["uv", "run", "python", str(main_file)],
            cwd=str(service_dir),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from terminal
        )

    # Save PID
    pid_file.write_text(str(process.pid))

    return process.pid


def _stop_host_service(cwd: Path, service_id: str) -> bool:
    """Stop a running host service.

    Args:
        cwd: Local-prod directory
        service_id: Service identifier (e.g., 'training-host')

    Returns:
        True if stopped successfully, False otherwise
    """
    pid = _get_host_service_pid(cwd, service_id)
    if pid is None:
        return False

    config = HOST_SERVICES[service_id]
    pid_file = cwd / config["pid_file"]

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        return True
    except ProcessLookupError:
        # Process already dead
        pid_file.unlink(missing_ok=True)
        return True
    except PermissionError:
        error_console.print(f"[red]Error:[/red] Permission denied stopping PID {pid}")
        return False


@local_prod_app.command("start-training-host")
def start_training_host() -> None:
    """Start the training host service with GPU access.

    The training host service runs natively (not in Docker) to access GPU.
    Secrets are fetched from 1Password item 'ktrdr-local-prod'.

    The service will be available at http://localhost:5002
    """
    _require_local_prod_context()
    cwd = Path.cwd()

    # Check if already running
    if _get_host_service_pid(cwd, "training-host"):
        error_console.print(
            "[yellow]Warning:[/yellow] Training host service already running"
        )
        error_console.print("Use 'ktrdr local-prod stop-hosts' to stop it first")
        raise typer.Exit(1)

    console.print("Starting training host service...")
    console.print("  Fetching secrets from 1Password...")

    env = _get_host_service_env(cwd)

    console.print("  Launching service...")
    pid = _start_host_service(cwd, "training-host", env)

    if pid:
        config = HOST_SERVICES["training-host"]
        console.print("\n[green]Training host service started[/green]")
        console.print(f"  PID: {pid}")
        console.print(f"  URL: http://localhost:{config['port']}")
        console.print(f"  Logs: {cwd / config['log_file']}")
    else:
        error_console.print("[red]Failed to start training host service[/red]")
        raise typer.Exit(1)


@local_prod_app.command("start-ib-host")
def start_ib_host() -> None:
    """Start the IB host service for Interactive Brokers access.

    The IB host service runs natively (not in Docker) to connect to IB Gateway.
    Secrets are fetched from 1Password item 'ktrdr-local-prod'.

    The service will be available at http://localhost:5001
    """
    _require_local_prod_context()
    cwd = Path.cwd()

    # Check if already running
    if _get_host_service_pid(cwd, "ib-host"):
        error_console.print("[yellow]Warning:[/yellow] IB host service already running")
        error_console.print("Use 'ktrdr local-prod stop-hosts' to stop it first")
        raise typer.Exit(1)

    console.print("Starting IB host service...")
    console.print("  Fetching secrets from 1Password...")

    env = _get_host_service_env(cwd)

    console.print("  Launching service...")
    pid = _start_host_service(cwd, "ib-host", env)

    if pid:
        config = HOST_SERVICES["ib-host"]
        console.print("\n[green]IB host service started[/green]")
        console.print(f"  PID: {pid}")
        console.print(f"  URL: http://localhost:{config['port']}")
        console.print(f"  Logs: {cwd / config['log_file']}")
    else:
        error_console.print("[red]Failed to start IB host service[/red]")
        raise typer.Exit(1)


@local_prod_app.command("host-status")
def host_status() -> None:
    """Show status of host services (training-host, ib-host)."""
    _require_local_prod_context()
    cwd = Path.cwd()

    table = Table(title="Host Services Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("PID")
    table.add_column("URL")

    for service_id, config in HOST_SERVICES.items():
        pid = _get_host_service_pid(cwd, service_id)

        if pid:
            status = "[green]Running[/green]"
            pid_str = str(pid)
        else:
            status = "[dim]Stopped[/dim]"
            pid_str = "-"

        table.add_row(
            config["name"],
            status,
            pid_str,
            f"http://localhost:{config['port']}",
        )

    console.print(table)


@local_prod_app.command("stop-hosts")
def stop_hosts(
    service: Optional[str] = typer.Argument(
        None, help="Specific service to stop (training-host or ib-host)"
    ),
) -> None:
    """Stop host services.

    Without arguments, stops all running host services.
    Specify a service name to stop only that service.
    """
    _require_local_prod_context()
    cwd = Path.cwd()

    services_to_stop = [service] if service else list(HOST_SERVICES.keys())

    stopped_any = False
    for service_id in services_to_stop:
        if service_id not in HOST_SERVICES:
            error_console.print(f"[red]Error:[/red] Unknown service: {service_id}")
            continue

        config = HOST_SERVICES[service_id]
        pid = _get_host_service_pid(cwd, service_id)

        if pid:
            if _stop_host_service(cwd, service_id):
                console.print(f"  ✓ Stopped {config['name']} (PID {pid})")
                stopped_any = True
            else:
                error_console.print(f"  ✗ Failed to stop {config['name']}")
        else:
            console.print(f"  - {config['name']} not running")

    if stopped_any:
        console.print("\n[green]Host services stopped[/green]")
    else:
        console.print("\n[dim]No running host services to stop[/dim]")
