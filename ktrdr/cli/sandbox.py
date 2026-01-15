"""Sandbox management CLI commands.

This module provides commands for managing isolated development sandbox instances.
Each sandbox runs in its own git worktree with isolated Docker containers.
"""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.helpers.secrets import (
    OnePasswordError,
    check_1password_authenticated,
    fetch_secrets_from_1password,
)
from ktrdr.cli.sandbox_gate import CheckStatus, run_gate
from ktrdr.cli.sandbox_ports import check_ports_available, get_ports
from ktrdr.cli.sandbox_registry import (
    InstanceInfo,
    add_instance,
    allocate_next_slot,
    clean_stale_entries,
    get_allocated_slots,
    get_instance,
    load_registry,
    remove_instance,
)

sandbox_app = typer.Typer(
    name="sandbox",
    help="Manage isolated development sandbox instances",
    no_args_is_help=True,
)

console = Console()
error_console = Console(stderr=True)

# Shared data directory configuration
SHARED_DIR = Path.home() / ".ktrdr" / "shared"
SHARED_SUBDIRS = ["data", "models", "strategies"]

# 1Password item for sandbox secrets
SANDBOX_SECRETS_ITEM = "ktrdr-sandbox-dev"

# Mapping from 1Password field labels to environment variable names
SANDBOX_SECRETS_MAPPING = {
    "db_password": "DB_PASSWORD",
    "jwt_secret": "JWT_SECRET",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "grafana_password": "GF_ADMIN_PASSWORD",
}


def fetch_sandbox_secrets() -> dict[str, str]:
    """Fetch sandbox secrets from 1Password.

    Returns:
        Dict mapping environment variable names to secret values.
        Empty dict if 1Password is unavailable or not authenticated.
    """
    if not check_1password_authenticated():
        return {}

    try:
        secrets = fetch_secrets_from_1password(SANDBOX_SECRETS_ITEM)
    except OnePasswordError:
        return {}

    # Map 1Password field labels to env var names
    env_secrets = {}
    for field_label, env_var in SANDBOX_SECRETS_MAPPING.items():
        if field_label in secrets:
            env_secrets[env_var] = secrets[field_label]

    return env_secrets


def get_dir_stats(path: Path) -> tuple[int, str]:
    """Get file count and human-readable size for a directory.

    Args:
        path: The directory to analyze.

    Returns:
        Tuple of (file_count, human_readable_size).
    """
    if not path.exists():
        return 0, "0 B"

    total_size = 0
    file_count = 0

    for f in path.rglob("*"):
        if f.is_file():
            try:
                total_size += f.stat().st_size
                file_count += 1
            except (OSError, PermissionError):
                # Skip files that cannot be accessed
                continue

    if file_count == 0:
        return 0, "0 B"

    # Human-readable size
    size = float(total_size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return file_count, f"{size:.1f} {unit}"
        size /= 1024

    return file_count, f"{size:.1f} TB"


def copy_with_progress(src: Path, dst: Path) -> None:
    """Copy directory with progress indication.

    Args:
        src: Source directory to copy from.
        dst: Destination directory to copy to.
    """
    if not src.exists():
        console.print(f"  [dim]Skipping {src.name}/ (not found)[/dim]")
        return

    file_count, size = get_dir_stats(src)
    console.print(f"  Copying {src.name}/ ... {size} ({file_count} files)")

    # Remove existing destination if present
    if dst.exists():
        try:
            shutil.rmtree(dst)
        except OSError as exc:
            error_console.print(
                f"[red]Error:[/red] Failed to remove existing {dst}: {exc}"
            )
            raise typer.Exit(1) from exc

    try:
        shutil.copytree(src, dst)
    except (OSError, shutil.Error) as exc:
        error_console.print(f"[red]Error:[/red] Failed to copy {src} to {dst}: {exc}")
        raise typer.Exit(1) from exc


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

    # Add shared data directories (matches docker-compose.sandbox.yml volume mounts)
    shared_dir = Path.home() / ".ktrdr" / "shared"
    env_vars["KTRDR_SHARED_DIR"] = str(shared_dir)
    env_vars["KTRDR_DATA_DIR"] = str(shared_dir / "data")
    env_vars["KTRDR_MODELS_DIR"] = str(shared_dir / "models")
    env_vars["KTRDR_STRATEGIES_DIR"] = str(shared_dir / "strategies")

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


def is_ktrdr_repo(path: Path) -> bool:
    """Check if path is a KTRDR repository by checking git remote.

    Args:
        path: The path to check.

    Returns:
        True if the git remote contains 'ktrdr', False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=path,
        )
        if result.returncode != 0:
            return False
        # Check if remote contains "ktrdr" (case-insensitive)
        return "ktrdr" in result.stdout.lower()
    except Exception:
        return False


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

    # Copy Claude Code settings if example exists
    claude_settings_example = worktree_path / ".claude" / "settings.local.example.json"
    claude_settings_target = worktree_path / ".claude" / "settings.local.json"
    if claude_settings_example.exists() and not claude_settings_target.exists():
        shutil.copy(claude_settings_example, claude_settings_target)
        console.print("  [dim]Copied .claude/settings.local.json from example[/dim]")

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


@sandbox_app.command()
def init(
    slot: int = typer.Option(
        None, "--slot", "-s", help="Force specific port slot (1-10)"
    ),
    name: str = typer.Option(None, "--name", "-n", help="Override instance name"),
) -> None:
    """Initialize current directory as a sandbox instance.

    This command initializes an existing KTRDR repository (clone or worktree)
    as a sandbox instance. It validates the directory is a KTRDR repo,
    allocates a port slot, and creates the .env.sandbox configuration file.

    Use this when you have an existing clone or worktree that you want to
    run as an isolated sandbox instance.
    """
    cwd = Path.cwd()

    # Check if already initialized
    if (cwd / ".env.sandbox").exists():
        error_console.print("[red]Error:[/red] Already initialized as sandbox")
        error_console.print(f"  .env.sandbox exists at {cwd / '.env.sandbox'}")
        raise typer.Exit(1)

    # Validate this is a KTRDR repo
    if not is_ktrdr_repo(cwd):
        error_console.print("[red]Error:[/red] Not a KTRDR repository")
        error_console.print("  Git remote should contain 'ktrdr'")
        raise typer.Exit(2)

    # Derive instance ID
    instance_id = name if name else derive_instance_id(cwd)

    # Check for ID collision
    if get_instance(instance_id):
        error_console.print(
            f"[red]Error:[/red] Instance ID '{instance_id}' already exists"
        )
        error_console.print("  Use --name to specify a different name")
        raise typer.Exit(1)

    # Allocate slot
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
        raise typer.Exit(3)

    # Generate .env.sandbox
    generate_env_file(cwd, instance_id, slot)

    # Copy Claude Code settings if example exists
    claude_settings_example = cwd / ".claude" / "settings.local.example.json"
    claude_settings_target = cwd / ".claude" / "settings.local.json"
    if claude_settings_example.exists() and not claude_settings_target.exists():
        shutil.copy(claude_settings_example, claude_settings_target)
        console.print("  [dim]Copied .claude/settings.local.json from example[/dim]")

    # Detect if this is a worktree
    is_worktree = (cwd / ".git").is_file()  # Worktrees have .git as file, not dir
    parent_repo = None
    if is_worktree:
        # Read parent from .git file
        with open(cwd / ".git", encoding="utf-8") as f:
            content = f.read()
            # Format: gitdir: /path/to/.git/worktrees/name
            if "gitdir:" in content:
                gitdir_path = Path(content.split("gitdir:")[1].strip())
                # Walk up to find actual repo, but only accept if valid
                candidate_parent = gitdir_path.parent.parent.parent
                if candidate_parent.exists() and (candidate_parent / ".git").exists():
                    parent_repo = str(candidate_parent.resolve())

    # Register instance
    add_instance(
        InstanceInfo(
            instance_id=instance_id,
            slot=slot,
            path=str(cwd),
            created_at=datetime.now(timezone.utc).isoformat(),
            is_worktree=is_worktree,
            parent_repo=parent_repo,
        )
    )

    # Report success
    ports = get_ports(slot)
    console.print(f"\n[green]Initialized sandbox:[/green] {instance_id}")
    console.print(f"  Port slot: {slot}")
    console.print(f"  API: http://localhost:{ports.backend}")
    console.print(f"  Grafana: http://localhost:{ports.grafana}")
    console.print("\nRun 'ktrdr sandbox up' to start")


def load_env_sandbox(path: Optional[Path] = None) -> dict[str, str]:
    """Load .env.sandbox from current or specified directory.

    Args:
        path: Directory containing .env.sandbox. Defaults to cwd.

    Returns:
        Dictionary of environment variables, empty if file doesn't exist.
    """
    if path is None:
        path = Path.cwd()

    env_file = path / ".env.sandbox"
    if not env_file.exists():
        return {}

    env: dict[str, str] = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


def find_compose_file(path: Path) -> Path:
    """Find the sandbox compose file.

    Args:
        path: Directory to search for compose file.

    Returns:
        Path to the compose file.

    Raises:
        FileNotFoundError: If no compose file is found.
    """
    # First check for sandbox-specific file
    sandbox_compose = path / "docker-compose.sandbox.yml"
    if sandbox_compose.exists():
        return sandbox_compose

    # Fall back to main compose (for merged scenario)
    main_compose = path / "docker-compose.yml"
    if main_compose.exists():
        return main_compose

    raise FileNotFoundError("No docker-compose file found")


@sandbox_app.command()
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
    """Start the sandbox stack.

    Secrets are fetched from 1Password item 'ktrdr-sandbox-dev' and injected
    into the Docker environment. Use --no-secrets to skip this and use defaults.
    """
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print(
            "[red]Error:[/red] Not in a sandbox directory (.env.sandbox not found)"
        )
        error_console.print(
            "Run 'ktrdr sandbox create <name>' to create a new sandbox directory."
        )
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")
    slot_str = env.get("SLOT_NUMBER", "0")
    slot = int(slot_str) if slot_str.isdigit() else 0

    console.print(f"Starting instance: {instance_id} (slot {slot})")

    # Check for port conflicts before starting
    conflicts = check_ports_available(slot)
    if conflicts:
        error_console.print(f"[red]Error:[/red] Ports already in use: {conflicts}")
        error_console.print("\nThis could be:")
        error_console.print("  - Another sandbox running on the same slot")
        error_console.print("  - External process using these ports")
        error_console.print("\nUse 'lsof -i :<port>' to identify the process.")
        raise typer.Exit(3)

    # Fetch secrets from 1Password
    secrets_env: dict[str, str] = {}
    if no_secrets:
        console.print("[dim]Skipping 1Password secrets (--no-secrets)[/dim]")
    else:
        console.print("Fetching secrets from 1Password...")
        secrets_env = fetch_sandbox_secrets()
        if secrets_env:
            secret_names = ", ".join(sorted(secrets_env.keys()))
            console.print(f"  [green]✓[/green] Loaded: {secret_names}")
        else:
            error_console.print(
                "[yellow]Warning:[/yellow] Could not fetch secrets from 1Password"
            )
            error_console.print("  Possible causes:")
            error_console.print("    - 1Password CLI (op) not installed")
            error_console.print("    - Not signed in (run: op signin)")
            error_console.print(f"    - Item '{SANDBOX_SECRETS_ITEM}' not found")
            error_console.print("  [dim]Using default/empty values for secrets[/dim]")

    # Build compose command
    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError as e:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1) from e

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    if build:
        cmd.append("--build")

    # Set environment for compose
    # Order matters: os.environ < .env.sandbox < 1Password secrets
    compose_env = os.environ.copy()
    compose_env.update(env)
    compose_env.update(secrets_env)  # Secrets override defaults

    console.print(f"Running: docker compose -f {compose_file.name} up -d")

    try:
        subprocess.run(cmd, check=True, env=compose_env)
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error starting stack:[/red] {e}")
        raise typer.Exit(1) from e

    # Run database migrations
    console.print("\nApplying database migrations...")

    # Wait for backend container to be ready (max 30s)
    backend_ready = False
    for _attempt in range(30):
        try:
            check_cmd = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "backend",
                "echo",
                "ready",
            ]
            check_result = subprocess.run(
                check_cmd,
                env=compose_env,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if check_result.returncode == 0:
                backend_ready = True
                break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # Backend container not ready yet; ignore transient errors and retry
            pass
        time.sleep(1)

    if not backend_ready:
        error_console.print(
            "[yellow]Warning:[/yellow] Backend container not ready, skipping migrations"
        )
        error_console.print(
            "  [dim]Run manually: docker compose exec backend /app/.venv/bin/alembic upgrade head[/dim]"
        )
    else:
        migration_cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "exec",
            "-T",  # Disable TTY allocation for non-interactive execution
            "backend",
            "/app/.venv/bin/alembic",
            "upgrade",
            "head",
        ]

        try:
            migration_result = subprocess.run(
                migration_cmd,
                env=compose_env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if migration_result.returncode == 0:
                console.print("  [green]✓[/green] Database migrations applied")
            else:
                error_console.print("[yellow]Warning:[/yellow] Migration failed")
                error_console.print(f"  {migration_result.stderr}")
                console.print(
                    "  [dim]You may need to run manually: docker compose exec backend /app/.venv/bin/alembic upgrade head[/dim]"
                )
        except subprocess.TimeoutExpired:
            error_console.print(
                "[yellow]Warning:[/yellow] Migration timed out after 60s"
            )

    if no_wait:
        console.print("\nInstance starting... (use 'ktrdr sandbox status' to check)")
        return

    # Run Startability Gate
    console.print("\nRunning Startability Gate...")
    api_port = int(env.get("KTRDR_API_PORT", 8000))
    db_port = int(env.get("KTRDR_DB_PORT", 5432))

    result = run_gate(api_port, db_port, timeout=float(timeout))

    # Display results
    for check in result.checks:
        if check.status == CheckStatus.PASSED:
            console.print(f"  [green]✓[/green] {check.name} ready")
        elif check.status == CheckStatus.SKIPPED:
            console.print(f"  [dim]○[/dim] {check.name} skipped")
        else:
            console.print(f"  [red]✗[/red] {check.name} failed")
            if check.message:
                console.print(f"    → {check.message}")
            if check.details:
                console.print(f"    → {check.details}")

    console.print()

    if result.passed:
        console.print("[green]Startability Gate: PASSED[/green]")
        console.print(f"\nInstance ready ({result.duration_seconds:.1f}s):")
        console.print(f"  API: http://localhost:{api_port}/api/v1/docs")
        console.print(
            f"  Grafana: http://localhost:{env.get('KTRDR_GRAFANA_PORT', 3000)}"
        )
        console.print(
            f"  Jaeger: http://localhost:{env.get('KTRDR_JAEGER_UI_PORT', 16686)}"
        )
    else:
        error_console.print("[red]Startability Gate: FAILED[/red]")
        error_console.print("\nCheck logs with: ktrdr sandbox logs")
        raise typer.Exit(2)


@sandbox_app.command()
def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Also remove volumes"),
) -> None:
    """Stop the sandbox stack."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")
    console.print(f"Stopping instance: {instance_id}")

    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError as e:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1) from e

    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
    if volumes:
        cmd.append("-v")

    compose_env = os.environ.copy()
    compose_env.update(env)

    try:
        subprocess.run(cmd, check=True, env=compose_env)
        console.print("[green]Instance stopped[/green]")
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error stopping stack:[/red] {e}")
        raise typer.Exit(1) from e


@sandbox_app.command()
def destroy(
    keep_worktree: bool = typer.Option(
        False, "--keep-worktree", help="Don't delete the git worktree"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Completely remove the sandbox instance."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")

    # Get instance info BEFORE removing from registry
    instance_info = get_instance(instance_id)

    # Confirm unless forced
    if not force:
        confirm = typer.confirm(
            f"Destroy instance '{instance_id}'? This cannot be undone."
        )
        if not confirm:
            raise typer.Abort()

    console.print(f"Destroying instance: {instance_id}")

    # Stop containers and remove volumes
    try:
        compose_file = find_compose_file(cwd)
        compose_env = os.environ.copy()
        compose_env.update(env)

        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            check=True,
            env=compose_env,
            capture_output=True,
        )
        console.print("  ✓ Containers stopped and volumes removed")
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("  ⚠ Could not stop containers (may already be stopped)")

    # Remove from registry
    if remove_instance(instance_id):
        console.print("  ✓ Registry updated")
    else:
        console.print("  ⚠ Instance not found in registry")

    # Remove worktree/directory
    if not keep_worktree:
        if instance_info and instance_info.is_worktree and instance_info.parent_repo:
            try:
                # Must run from parent repo to remove worktree
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(cwd)],
                    check=True,
                    capture_output=True,
                    cwd=instance_info.parent_repo,
                )
                console.print("  ✓ Worktree removed")
            except subprocess.CalledProcessError:
                # Fallback: just delete the directory
                shutil.rmtree(cwd, ignore_errors=True)
                console.print("  ✓ Directory removed (worktree cleanup failed)")
        else:
            # Not a worktree or no info, just remove directory
            shutil.rmtree(cwd, ignore_errors=True)
            console.print("  ✓ Directory removed")

    console.print(f"\n[green]Instance '{instance_id}' destroyed[/green]")
    if not keep_worktree:
        console.print("[dim]Note: Run 'cd ..' to leave the deleted directory[/dim]")


def get_instance_status(
    instance_id: str, compose_file: Path, env: dict[str, str]
) -> str:
    """Check if instance containers are running.

    Args:
        instance_id: The instance identifier (unused but kept for API consistency).
        compose_file: Path to the compose file.
        env: Environment variables for Docker Compose.

    Returns:
        Status string: "running", "stopped", "partial (x/y)", or "unknown".
    """
    try:
        compose_env = os.environ.copy()
        compose_env.update(env)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
            capture_output=True,
            text=True,
            env=compose_env,
        )
        if result.returncode != 0:
            return "unknown"

        # Parse JSON output - may be array or line-delimited objects
        stdout = result.stdout.strip()
        if not stdout:
            return "stopped"

        # Try parsing as JSON array first
        try:
            containers = json.loads(stdout)
            if not isinstance(containers, list):
                containers = [containers]
        except json.JSONDecodeError:
            # Handle line-delimited JSON (docker compose v2.21+)
            containers = []
            for line in stdout.split("\n"):
                if line.strip():
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip lines that aren't valid JSON (e.g., empty or malformed)
                        pass

        if not containers:
            return "stopped"

        running = sum(1 for c in containers if c.get("State") == "running")
        total = len(containers)

        if running == total:
            return "running"
        elif running > 0:
            return f"partial ({running}/{total})"
        else:
            return "stopped"
    except Exception:
        return "unknown"


@sandbox_app.command("list")
def list_instances() -> None:
    """List all sandbox instances."""
    # Clean stale entries first
    stale = clean_stale_entries()
    if stale:
        console.print(f"[dim]Cleaned {len(stale)} stale entries[/dim]")

    registry = load_registry()

    if not registry.instances:
        console.print("No sandbox instances found.")
        console.print("Create one with: ktrdr sandbox create <name>")
        return

    table = Table(title="Sandbox Instances")
    table.add_column("Instance", style="cyan")
    table.add_column("Slot", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("API Port", justify="center")
    table.add_column("Path")

    for instance_id, info in sorted(registry.instances.items()):
        path = Path(info.path)
        env = load_env_sandbox(path) if path.exists() else {}

        # Check status
        status = "missing"
        if path.exists():
            try:
                compose_file = find_compose_file(path)
                status = get_instance_status(instance_id, compose_file, env)
            except FileNotFoundError:
                status = "no compose"

        # Color status
        if status == "running":
            status_display = "[green]running[/green]"
        elif status == "stopped":
            status_display = "[yellow]stopped[/yellow]"
        elif status.startswith("partial"):
            status_display = f"[yellow]{status}[/yellow]"
        else:
            status_display = f"[red]{status}[/red]"

        table.add_row(
            instance_id,
            str(info.slot),
            status_display,
            env.get("KTRDR_API_PORT", "?"),
            str(path),
        )

    console.print(table)


@sandbox_app.command()
def status() -> None:
    """Show detailed status of current sandbox instance."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")
    slot = env.get("SLOT_NUMBER", "?")

    console.print(f"[bold]Instance:[/bold] {instance_id} (slot {slot})")

    # Get container status
    try:
        compose_file = find_compose_file(cwd)
        compose_env = os.environ.copy()
        compose_env.update(env)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
            capture_output=True,
            text=True,
            env=compose_env,
        )

        # Parse JSON output - may be array or line-delimited objects
        stdout = result.stdout.strip()
        if not stdout:
            containers: list[dict] = []
        else:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, list):
                    containers = parsed
                else:
                    containers = [parsed]
            except json.JSONDecodeError:
                # Handle line-delimited JSON
                containers = []
                for line in stdout.split("\n"):
                    if line.strip():
                        try:
                            containers.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Intentionally ignore malformed JSON lines from docker compose output
                            pass

        running = sum(1 for c in containers if c.get("State") == "running")
        total = len(containers)

        if running == total and total > 0:
            status_str = "[green]running[/green]"
        elif running > 0:
            status_str = f"[yellow]partial ({running}/{total})[/yellow]"
        elif total > 0:
            status_str = "[red]stopped[/red]"
        else:
            status_str = "[dim]not started[/dim]"

        console.print(f"[bold]Status:[/bold] {status_str}")
        console.print(f"[bold]Containers:[/bold] {running}/{total} healthy")

    except FileNotFoundError:
        console.print("[bold]Status:[/bold] [dim]no compose file[/dim]")
    except Exception as e:
        console.print(f"[bold]Status:[/bold] [red]error ({e})[/red]")

    console.print()

    # Service URLs
    api_port = env.get("KTRDR_API_PORT", "8000")
    db_port = env.get("KTRDR_DB_PORT", "5432")
    grafana_port = env.get("KTRDR_GRAFANA_PORT", "3000")
    jaeger_port = env.get("KTRDR_JAEGER_UI_PORT", "16686")
    prometheus_port = env.get("KTRDR_PROMETHEUS_PORT", "9090")

    console.print("[bold]Services:[/bold]")
    console.print(f"  Backend:    http://localhost:{api_port}")
    console.print(f"  API Docs:   http://localhost:{api_port}/api/v1/docs")
    console.print(f"  Database:   localhost:{db_port}")
    console.print(f"  Grafana:    http://localhost:{grafana_port}")
    console.print(f"  Jaeger:     http://localhost:{jaeger_port}")
    console.print(f"  Prometheus: http://localhost:{prometheus_port}")

    console.print()
    console.print("[bold]Workers:[/bold]")
    for i in range(1, 5):
        port = env.get(f"KTRDR_WORKER_PORT_{i}", "?")
        console.print(f"  Worker {i}:   http://localhost:{port}")

    # Shared data section
    console.print()
    console.print("[bold]Shared Data:[/bold]")
    if SHARED_DIR.exists():
        for subdir in SHARED_SUBDIRS:
            path = SHARED_DIR / subdir
            if path.exists():
                file_count, size = get_dir_stats(path)
                console.print(f"  {subdir}/: {size} ({file_count} files)")
            else:
                console.print(f"  {subdir}/: [dim]not found[/dim]")
    else:
        console.print("  [yellow]Not initialized[/yellow]")
        console.print("  Run: ktrdr sandbox init-shared")


@sandbox_app.command()
def logs(
    service: Optional[str] = typer.Argument(
        None, help="Service name (e.g., backend, db)"
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """View logs for sandbox services."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError as e:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1) from e

    compose_env = os.environ.copy()
    compose_env.update(env)

    cmd = ["docker", "compose", "-f", str(compose_file), "logs"]
    cmd.extend(["--tail", str(tail)])
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)

    try:
        subprocess.run(cmd, env=compose_env)
    except KeyboardInterrupt:
        pass  # Normal exit from follow mode


@sandbox_app.command()
def shell(
    service: str = typer.Argument(
        "backend", help="Service name to shell into (e.g., backend, db)"
    ),
) -> None:
    """Open an interactive shell in a sandbox container.

    Opens a bash shell (or falls back to sh) in the specified container.
    Defaults to the backend container if no service is specified.
    """
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print(
            "[red]Error:[/red] Not in a sandbox directory (.env.sandbox not found)"
        )
        error_console.print(
            "Run 'ktrdr sandbox create <name>' or 'ktrdr sandbox init' first."
        )
        raise typer.Exit(1)

    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError as e:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1) from e

    compose_env = os.environ.copy()
    compose_env.update(env)

    # Try bash first, fall back to sh if unavailable
    cmd = ["docker", "compose", "-f", str(compose_file), "exec", service, "bash"]

    result = subprocess.run(cmd, env=compose_env)

    # Exit code 126 means command not found/executable - try sh instead
    if result.returncode == 126:
        cmd = ["docker", "compose", "-f", str(compose_file), "exec", service, "sh"]
        subprocess.run(cmd, env=compose_env)


@sandbox_app.command("init-shared")
def init_shared(
    from_path: Optional[Path] = typer.Option(
        None,
        "--from",
        "-f",
        help="Copy data from existing KTRDR environment",
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        "-m",
        help="Create empty structure only (no data copied)",
    ),
) -> None:
    """Initialize the shared data directory (~/.ktrdr/shared/).

    This sets up the shared data directory used by all sandbox instances.
    Use --minimal for empty structure or --from to copy from an existing environment.
    """
    console.print(f"Initializing shared data directory: {SHARED_DIR}")

    # Create base directory
    SHARED_DIR.mkdir(parents=True, exist_ok=True)

    if minimal:
        # Just create empty directories
        console.print("  Creating empty structure...")
        for subdir in SHARED_SUBDIRS:
            (SHARED_DIR / subdir).mkdir(exist_ok=True)

        console.print("\n[green]Shared data initialized (minimal):[/green]")
        for subdir in SHARED_SUBDIRS:
            console.print(f"  {SHARED_DIR / subdir}/")
        console.print(
            "\n[dim]Note: No data copied. Download data after starting sandbox.[/dim]"
        )
        return

    if from_path:
        # Validate source
        if not from_path.exists():
            error_console.print(f"[red]Error:[/red] Source not found: {from_path}")
            raise typer.Exit(1)

        # Copy each subdirectory
        for subdir in SHARED_SUBDIRS:
            src = from_path / subdir
            dst = SHARED_DIR / subdir
            copy_with_progress(src, dst)

        console.print("\n[green]Shared data initialized:[/green]")
        for subdir in SHARED_SUBDIRS:
            path = SHARED_DIR / subdir
            if path.exists():
                file_count, size = get_dir_stats(path)
                console.print(f"  {path}/ ({size}, {file_count} files)")
            else:
                console.print(f"  {path}/ (empty)")
        return

    # No --from and no --minimal: check if shared dir already has content
    def has_content(path: Path) -> bool:
        if not path.exists():
            return False
        try:
            return any(path.iterdir())
        except (PermissionError, OSError):
            # If unreadable, assume it has content to avoid overwriting
            return True

    existing_content = any(
        has_content(SHARED_DIR / subdir) for subdir in SHARED_SUBDIRS
    )

    if existing_content:
        console.print("\n[yellow]Shared data already exists:[/yellow]")
        for subdir in SHARED_SUBDIRS:
            path = SHARED_DIR / subdir
            if path.exists():
                file_count, size = get_dir_stats(path)
                console.print(f"  {path}/ ({size}, {file_count} files)")
        console.print("\nUse --from to overwrite or --minimal to reset to empty.")
        return

    # Empty and no flags: create minimal structure
    console.print("  Creating empty structure...")
    for subdir in SHARED_SUBDIRS:
        (SHARED_DIR / subdir).mkdir(exist_ok=True)

    console.print("\n[green]Shared data initialized (empty):[/green]")
    for subdir in SHARED_SUBDIRS:
        console.print(f"  {SHARED_DIR / subdir}/")
    console.print("\nPopulate with:")
    console.print("  ktrdr sandbox init-shared --from /path/to/existing/ktrdr")
