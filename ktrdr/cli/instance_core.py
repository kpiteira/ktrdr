"""Core instance lifecycle management for sandbox and local-prod environments.

This module provides the shared implementation for managing KTRDR instances,
whether they are sandboxes (development environments) or local-prod (production-like
environments). CLI modules (sandbox.py, local_prod.py) are thin wrappers that
call these core functions.

The module handles:
- Instance creation (worktree setup, env file generation, registry)
- Instance initialization (existing directory setup)
- Instance start/stop (Docker Compose orchestration)
- Instance destruction (cleanup of worktree, containers, registry)
- Status checking and log viewing
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

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
    get_instance,
    remove_instance,
)

console = Console()
error_console = Console(stderr=True)

# 1Password item for sandbox secrets
SANDBOX_SECRETS_ITEM = "ktrdr-sandbox-dev"

# Mapping from 1Password field labels to environment variable names
SANDBOX_SECRETS_MAPPING = {
    "db_password": "DB_PASSWORD",
    "jwt_secret": "JWT_SECRET",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "grafana_password": "GF_ADMIN_PASSWORD",
}


def fetch_secrets(item_name: Optional[str] = None) -> dict[str, str]:
    """Fetch secrets from 1Password.

    Args:
        item_name: 1Password item name. Defaults to SANDBOX_SECRETS_ITEM.

    Returns:
        Dict mapping environment variable names to secret values.
        Empty dict if 1Password is unavailable or not authenticated.
    """
    if not check_1password_authenticated():
        return {}

    item = item_name or SANDBOX_SECRETS_ITEM

    try:
        secrets = fetch_secrets_from_1password(item)
    except OnePasswordError:
        return {}

    # Map 1Password field labels to env var names
    env_secrets = {}
    for field_label, env_var in SANDBOX_SECRETS_MAPPING.items():
        if field_label in secrets:
            env_secrets[env_var] = secrets[field_label]

    return env_secrets


def fetch_sandbox_secrets() -> dict[str, str]:
    """Fetch sandbox secrets from 1Password (legacy wrapper).

    Returns:
        Dict mapping environment variable names to secret values.
        Empty dict if 1Password is unavailable or not authenticated.
    """
    return fetch_secrets(SANDBOX_SECRETS_ITEM)


def load_env_file(path: Optional[Path] = None) -> dict[str, str]:
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


def generate_env_file(path: Path, instance_id: str, slot: int) -> None:
    """Generate .env.sandbox file for instance.

    Args:
        path: Directory to write the file to.
        instance_id: The instance identifier.
        slot: The allocated port slot (0 for local-prod, 1-10 for sandboxes).
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


def get_compose_status(
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


def start_instance(
    path: Path,
    wait: bool = True,
    build: bool = False,
    timeout: int = 120,
    no_secrets: bool = False,
    profile: Optional[str] = None,
    secrets_item: Optional[str] = None,
) -> int:
    """Start the instance Docker Compose stack.

    Args:
        path: Path to the instance directory.
        wait: Whether to wait for Startability Gate.
        build: Whether to force rebuild images.
        timeout: Gate timeout in seconds.
        no_secrets: Skip 1Password secrets.
        profile: Docker Compose profile to use (e.g., "local-prod" for extra workers).
        secrets_item: 1Password item name for secrets. Defaults to sandbox item.

    Returns:
        Exit code (0 for success, 1 for general error, 2 for gate failure, 3 for port conflict).
    """
    env = load_env_file(path)

    if not env:
        error_console.print(
            "[red]Error:[/red] Not in a sandbox directory (.env.sandbox not found)"
        )
        error_console.print(
            "Run 'ktrdr sandbox create <name>' to create a new sandbox directory."
        )
        return 1

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
        return 3

    # Fetch secrets from 1Password
    item_name = secrets_item or SANDBOX_SECRETS_ITEM
    secrets_env: dict[str, str] = {}
    if no_secrets:
        console.print("[dim]Skipping 1Password secrets (--no-secrets)[/dim]")
    else:
        console.print("Fetching secrets from 1Password...")
        secrets_env = fetch_secrets(item_name)
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
            error_console.print(f"    - Item '{item_name}' not found")
            error_console.print("  [dim]Using default/empty values for secrets[/dim]")

    # Build compose command
    try:
        compose_file = find_compose_file(path)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        return 1

    cmd = ["docker", "compose", "-f", str(compose_file)]

    if profile:
        cmd.extend(["--profile", profile])

    cmd.extend(["up", "-d"])

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
        return 1

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

    if not wait:
        console.print("\nInstance starting... (use 'ktrdr sandbox status' to check)")
        return 0

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
        return 0
    else:
        error_console.print("[red]Startability Gate: FAILED[/red]")
        error_console.print("\nCheck logs with: ktrdr sandbox logs")
        return 2


def stop_instance(
    path: Path, remove_volumes: bool = False, profile: Optional[str] = None
) -> int:
    """Stop the instance Docker Compose stack.

    Args:
        path: Path to the instance directory.
        remove_volumes: Whether to also remove volumes.
        profile: Docker Compose profile to stop (e.g., "local-prod" for extra workers).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    env = load_env_file(path)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        return 1

    instance_id = env.get("INSTANCE_ID", "unknown")
    console.print(f"Stopping instance: {instance_id}")

    try:
        compose_file = find_compose_file(path)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        return 1

    cmd = ["docker", "compose", "-f", str(compose_file)]

    if profile:
        cmd.extend(["--profile", profile])

    cmd.append("down")
    if remove_volumes:
        cmd.append("-v")

    compose_env = os.environ.copy()
    compose_env.update(env)

    try:
        subprocess.run(cmd, check=True, env=compose_env)
        console.print("[green]Instance stopped[/green]")
        return 0
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error stopping stack:[/red] {e}")
        return 1


def destroy_instance(
    path: Path,
    keep_worktree: bool = False,
    force: bool = False,
    confirm_func=None,
    profile: Optional[str] = None,
) -> int:
    """Completely remove the instance.

    Args:
        path: Path to the instance directory.
        keep_worktree: Whether to keep the git worktree/directory.
        force: Skip confirmation prompt.
        confirm_func: Function to call for confirmation (receives message, returns bool).
                     If None and not force, returns error.
        profile: Docker Compose profile to stop (e.g., "local-prod" for extra workers).

    Returns:
        Exit code (0 for success, 1 for error, -1 for aborted).
    """
    env = load_env_file(path)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        return 1

    instance_id = env.get("INSTANCE_ID", "unknown")

    # Get instance info BEFORE removing from registry
    instance_info = get_instance(instance_id)

    # Confirm unless forced
    if not force:
        if confirm_func is None:
            error_console.print(
                "[red]Error:[/red] Confirmation required (use --force to skip)"
            )
            return 1
        if not confirm_func(
            f"Destroy instance '{instance_id}'? This cannot be undone."
        ):
            return -1  # Aborted

    console.print(f"Destroying instance: {instance_id}")

    # Stop containers and remove volumes
    try:
        compose_file = find_compose_file(path)
        compose_env = os.environ.copy()
        compose_env.update(env)

        cmd = ["docker", "compose", "-f", str(compose_file)]
        if profile:
            cmd.extend(["--profile", profile])
        cmd.extend(["down", "-v"])

        subprocess.run(
            cmd,
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
                    ["git", "worktree", "remove", "--force", str(path)],
                    check=True,
                    capture_output=True,
                    cwd=instance_info.parent_repo,
                )
                console.print("  ✓ Worktree removed")
            except subprocess.CalledProcessError:
                # Fallback: just delete the directory
                shutil.rmtree(path, ignore_errors=True)
                console.print("  ✓ Directory removed (worktree cleanup failed)")
        else:
            # Not a worktree or no info, just remove directory
            shutil.rmtree(path, ignore_errors=True)
            console.print("  ✓ Directory removed")

    console.print(f"\n[green]Instance '{instance_id}' destroyed[/green]")
    if not keep_worktree:
        console.print("[dim]Note: Run 'cd ..' to leave the deleted directory[/dim]")

    return 0


def show_instance_logs(
    path: Path,
    service: Optional[str] = None,
    follow: bool = False,
    tail: int = 100,
) -> int:
    """View logs for instance services.

    Args:
        path: Path to the instance directory.
        service: Optional service name to filter logs.
        follow: Whether to follow log output.
        tail: Number of lines to show.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    env = load_env_file(path)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        return 1

    try:
        compose_file = find_compose_file(path)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        return 1

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
        return 0
    except KeyboardInterrupt:
        return 0  # Normal exit from follow mode


def open_instance_shell(path: Path, service: str = "backend") -> int:
    """Open an interactive shell in an instance container.

    Args:
        path: Path to the instance directory.
        service: Service name to shell into.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    env = load_env_file(path)

    if not env:
        error_console.print(
            "[red]Error:[/red] Not in a sandbox directory (.env.sandbox not found)"
        )
        error_console.print(
            "Run 'ktrdr sandbox create <name>' or 'ktrdr sandbox init' first."
        )
        return 1

    try:
        compose_file = find_compose_file(path)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        return 1

    compose_env = os.environ.copy()
    compose_env.update(env)

    # Try bash first, fall back to sh if unavailable
    cmd = ["docker", "compose", "-f", str(compose_file), "exec", service, "bash"]

    result = subprocess.run(cmd, env=compose_env)

    # Exit code 126 means command not found/executable - try sh instead
    if result.returncode == 126:
        cmd = ["docker", "compose", "-f", str(compose_file), "exec", service, "sh"]
        sh_result = subprocess.run(cmd, env=compose_env)
        return sh_result.returncode

    return result.returncode


def register_instance(
    instance_id: str,
    slot: int,
    path: Path,
    is_worktree: bool,
    parent_repo: Optional[str] = None,
) -> None:
    """Register an instance in the registry.

    Args:
        instance_id: The instance identifier.
        slot: The allocated port slot.
        path: Path to the instance directory.
        is_worktree: Whether this is a git worktree.
        parent_repo: Path to parent repo if worktree.
    """
    add_instance(
        InstanceInfo(
            instance_id=instance_id,
            slot=slot,
            path=str(path),
            created_at=datetime.now(timezone.utc).isoformat(),
            is_worktree=is_worktree,
            parent_repo=parent_repo,
        )
    )
