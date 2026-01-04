---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: CLI Core Commands

**Goal:** Developer can create and manage sandbox instances with simple commands.

**Branch:** `feature/sandbox-m2-cli-core`

**Builds on:** M1 (Compose Setup)

---

## E2E Test Scenario

**Purpose:** Prove the full create → up → health check → destroy cycle works.

**Prerequisites:**
- M1 complete (`docker-compose.sandbox.yml` exists)
- `~/.ktrdr/shared/` initialized
- No sandbox instances running

```bash
# 1. Create a new sandbox instance
ktrdr sandbox create test-feature

# Expected output:
# Created instance: test-feature
#   Location: /Users/karl/Documents/dev/ktrdr--test-feature
#   Port slot: 1
#   API: http://localhost:8001
#   Grafana: http://localhost:3001
#
# Run 'cd ../ktrdr--test-feature && ktrdr sandbox up' to start

# 2. Navigate and start
cd ../ktrdr--test-feature
ktrdr sandbox up --no-wait  # Skip Startability Gate for now (M3)

# Expected output:
# Starting instance: test-feature (slot 1)
# Running: docker compose -f docker-compose.sandbox.yml up -d
# Instance starting... (use 'ktrdr sandbox status' to check)

# 3. Wait and verify health
sleep 45
curl -f http://localhost:8001/api/v1/health  # Should return 200

# 4. Check list shows instance
ktrdr sandbox list

# Expected output:
# INSTANCE       SLOT  STATUS   API PORT
# test-feature   1     running  8001

# 5. Stop instance
ktrdr sandbox down

# 6. Verify stopped
curl http://localhost:8001/api/v1/health  # Should fail (connection refused)

# 7. Destroy completely
ktrdr sandbox destroy

# Expected output:
# Destroying instance: test-feature
#   ✓ Containers stopped
#   ✓ Volumes removed
#   ✓ Worktree removed
#   ✓ Registry updated

# 8. Verify gone
ls ../ktrdr--test-feature  # Should not exist
ktrdr sandbox list         # Should show empty or no test-feature
```

**Success Criteria:**
- [ ] `ktrdr sandbox create` creates worktree + `.env.sandbox`
- [ ] `ktrdr sandbox up` starts containers
- [ ] `ktrdr sandbox down` stops containers
- [ ] `ktrdr sandbox destroy` removes everything
- [ ] `ktrdr sandbox list` shows instances correctly
- [ ] Port slot allocation works (auto-assigns slot 1)

---

## Tasks

### Task 2.1: Create Port Allocator Module

**File:** `ktrdr/cli/sandbox_ports.py` (new)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration, Wiring/DI

**Description:**
Implement the port allocation logic that maps slot numbers (0-10) to port assignments. This is a pure function module with no external dependencies.

**Implementation Notes:**

```python
"""Port allocation for sandbox instances."""

import socket
from dataclasses import dataclass


@dataclass
class PortAllocation:
    """Port assignments for a sandbox slot."""
    slot: int
    backend: int
    db: int
    grafana: int
    jaeger_ui: int
    jaeger_otlp_grpc: int
    jaeger_otlp_http: int
    prometheus: int
    worker_ports: list[int]  # 4 worker ports

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dict for .env.sandbox."""
        return {
            "SLOT_NUMBER": str(self.slot),
            "KTRDR_API_PORT": str(self.backend),
            "KTRDR_DB_PORT": str(self.db),
            "KTRDR_GRAFANA_PORT": str(self.grafana),
            "KTRDR_JAEGER_UI_PORT": str(self.jaeger_ui),
            "KTRDR_JAEGER_OTLP_GRPC_PORT": str(self.jaeger_otlp_grpc),
            "KTRDR_JAEGER_OTLP_HTTP_PORT": str(self.jaeger_otlp_http),
            "KTRDR_PROMETHEUS_PORT": str(self.prometheus),
            "KTRDR_WORKER_PORT_1": str(self.worker_ports[0]),
            "KTRDR_WORKER_PORT_2": str(self.worker_ports[1]),
            "KTRDR_WORKER_PORT_3": str(self.worker_ports[2]),
            "KTRDR_WORKER_PORT_4": str(self.worker_ports[3]),
        }

    def all_ports(self) -> list[int]:
        """Return all ports for conflict checking."""
        return [
            self.backend, self.db, self.grafana, self.jaeger_ui,
            self.jaeger_otlp_grpc, self.jaeger_otlp_http, self.prometheus,
            *self.worker_ports
        ]


def get_ports(slot: int) -> PortAllocation:
    """
    Get port allocation for a slot.

    Slot 0: Standard ports (main dev environment)
    Slot 1-10: Offset ports for sandbox instances
    """
    if slot < 0 or slot > 10:
        raise ValueError(f"Slot must be 0-10, got {slot}")

    if slot == 0:
        return PortAllocation(
            slot=0,
            backend=8000,
            db=5432,
            grafana=3000,
            jaeger_ui=16686,
            jaeger_otlp_grpc=4317,
            jaeger_otlp_http=4318,
            prometheus=9090,
            worker_ports=[5003, 5004, 5005, 5006],
        )

    return PortAllocation(
        slot=slot,
        backend=8000 + slot,
        db=5432 + slot,
        grafana=3000 + slot,
        jaeger_ui=16686 + slot,
        jaeger_otlp_grpc=4317 + slot * 10,  # 4327, 4337, ... (10-slot offset)
        jaeger_otlp_http=4318 + slot * 10,  # 4328, 4338, ...
        prometheus=9090 + slot,
        worker_ports=[
            5010 + (slot - 1) * 10,      # 5010, 5020, 5030, ...
            5010 + (slot - 1) * 10 + 1,  # 5011, 5021, 5031, ...
            5010 + (slot - 1) * 10 + 2,  # 5012, 5022, 5032, ...
            5010 + (slot - 1) * 10 + 3,  # 5013, 5023, 5033, ...
        ],
    )


def is_port_free(port: int) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def check_ports_available(slot: int) -> list[int]:
    """
    Check which ports in a slot are in use.

    Returns:
        List of ports that are already in use (empty if all available)
    """
    allocation = get_ports(slot)
    return [p for p in allocation.all_ports() if not is_port_free(p)]
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_ports.py`
- [ ] `test_slot_0_returns_standard_ports` — Verify slot 0 matches current docker-compose
- [ ] `test_slot_1_returns_offset_ports` — Verify slot 1 has +1 offsets
- [ ] `test_slot_2_worker_ports` — Verify worker port ranges (5020-5023)
- [ ] `test_invalid_slot_raises` — Slot -1 and 11 raise ValueError
- [ ] `test_to_env_dict_format` — Verify env var names and values

*Integration Tests:*
- [ ] `test_is_port_free_on_unbound_port` — Returns True for unused port
- [ ] `test_is_port_free_on_bound_port` — Bind a socket, verify returns False

*Smoke Test:*
```python
from ktrdr.cli.sandbox_ports import get_ports
print(get_ports(1).to_env_dict())
```

**Acceptance Criteria:**
- [ ] `get_ports(0)` returns standard ports matching current compose
- [ ] `get_ports(1-10)` returns correctly offset ports
- [ ] `check_ports_available()` detects bound ports
- [ ] `to_env_dict()` produces correct env var format
- [ ] All unit tests pass

---

### Task 2.2: Create Instance Registry Module

**File:** `ktrdr/cli/sandbox_registry.py` (new)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Persistence, Configuration

**Description:**
Implement the instance registry that tracks sandbox instances in `~/.ktrdr/sandbox/instances.json`.

**Implementation Notes:**

```python
"""Instance registry for sandbox management."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


REGISTRY_DIR = Path.home() / ".ktrdr" / "sandbox"
REGISTRY_FILE = REGISTRY_DIR / "instances.json"


@dataclass
class InstanceInfo:
    """Information about a sandbox instance."""
    instance_id: str
    slot: int
    path: str
    created_at: str  # ISO format
    is_worktree: bool
    parent_repo: Optional[str] = None


@dataclass
class Registry:
    """Sandbox instance registry."""
    version: int = 1
    instances: dict[str, InstanceInfo] = None

    def __post_init__(self):
        if self.instances is None:
            self.instances = {}


def _ensure_registry_dir() -> None:
    """Create registry directory if it doesn't exist."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_registry() -> Registry:
    """Load registry from disk, creating if needed."""
    _ensure_registry_dir()
    if not REGISTRY_FILE.exists():
        return Registry()

    try:
        with open(REGISTRY_FILE) as f:
            data = json.load(f)
        instances = {
            k: InstanceInfo(**v) for k, v in data.get("instances", {}).items()
        }
        return Registry(version=data.get("version", 1), instances=instances)
    except (json.JSONDecodeError, TypeError):
        # Corrupted file, start fresh
        return Registry()


def save_registry(registry: Registry) -> None:
    """Save registry to disk."""
    _ensure_registry_dir()
    data = {
        "version": registry.version,
        "instances": {k: asdict(v) for k, v in registry.instances.items()},
    }
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_instance(info: InstanceInfo) -> None:
    """Add an instance to the registry."""
    registry = load_registry()
    registry.instances[info.instance_id] = info
    save_registry(registry)


def remove_instance(instance_id: str) -> bool:
    """Remove an instance from the registry. Returns True if found."""
    registry = load_registry()
    if instance_id in registry.instances:
        del registry.instances[instance_id]
        save_registry(registry)
        return True
    return False


def get_instance(instance_id: str) -> Optional[InstanceInfo]:
    """Get instance info by ID."""
    registry = load_registry()
    return registry.instances.get(instance_id)


def get_allocated_slots() -> set[int]:
    """Get set of currently allocated slots."""
    registry = load_registry()
    return {info.slot for info in registry.instances.values()}


def allocate_next_slot() -> int:
    """Allocate the next available slot (1-10)."""
    allocated = get_allocated_slots()
    for slot in range(1, 11):
        if slot not in allocated:
            return slot
    raise RuntimeError("All 10 sandbox slots are in use")


def clean_stale_entries() -> list[str]:
    """Remove entries where the directory no longer exists. Returns removed IDs."""
    registry = load_registry()
    stale = [
        instance_id for instance_id, info in registry.instances.items()
        if not Path(info.path).exists()
    ]
    for instance_id in stale:
        del registry.instances[instance_id]
    if stale:
        save_registry(registry)
    return stale
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_registry.py`
- [ ] `test_load_empty_registry` — Returns empty registry when file doesn't exist
- [ ] `test_add_and_get_instance` — Add instance, retrieve it
- [ ] `test_remove_instance` — Remove instance, verify gone
- [ ] `test_allocate_next_slot_sequential` — Allocates 1, 2, 3...
- [ ] `test_allocate_next_slot_fills_gaps` — If 1 removed, next allocation is 1
- [ ] `test_all_slots_exhausted` — Raises after 10 allocations

*Integration Tests:*
- [ ] `test_registry_persists_across_load` — Save, reload, verify data intact
- [ ] `test_clean_stale_removes_missing_dirs` — Create entry, delete dir, clean removes it

*Smoke Test:*
```bash
cat ~/.ktrdr/sandbox/instances.json | jq
```

**Acceptance Criteria:**
- [ ] Registry created at `~/.ktrdr/sandbox/instances.json`
- [ ] Add/remove/get operations work correctly
- [ ] Slot allocation fills gaps
- [ ] Stale entry cleanup works
- [ ] All unit tests pass

---

### Task 2.3: Create Sandbox CLI Subcommand Module

**File:** `ktrdr/cli/sandbox.py` (new)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint (CLI), Wiring/DI

**Description:**
Create the main sandbox CLI module with the Typer app structure. Individual commands will be implemented in subsequent tasks.

**Implementation Notes:**

```python
"""Sandbox management CLI commands."""

import typer
from rich.console import Console

sandbox_app = typer.Typer(
    name="sandbox",
    help="Manage isolated development sandbox instances",
    no_args_is_help=True,
)

console = Console()
error_console = Console(stderr=True)


# Commands will be added here:
# - create
# - init
# - up
# - down
# - destroy
# - list
# - status
# - logs
```

Also modify `ktrdr/cli/__init__.py` to register the sandbox app:

```python
# Add import
from ktrdr.cli.sandbox import sandbox_app  # noqa: E402

# Add registration (after other add_typer calls)
cli_app.add_typer(
    sandbox_app, name="sandbox", help="Manage isolated development sandbox instances"
)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_sandbox_help_displays` — `ktrdr sandbox --help` shows help text

*Smoke Test:*
```bash
ktrdr sandbox --help
```

**Acceptance Criteria:**
- [ ] `ktrdr sandbox --help` shows sandbox subcommand
- [ ] `ktrdr sandbox` with no args shows help (no_args_is_help=True)
- [ ] Module imports without errors

---

### Task 2.4: Implement `ktrdr sandbox create` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** API Endpoint (CLI), Wiring/DI, Persistence

**Description:**
Implement the `create` command that creates a git worktree and initializes a sandbox instance.

**Implementation Notes:**

```python
import subprocess
from datetime import datetime
from pathlib import Path


def slugify(name: str) -> str:
    """Convert name to valid Docker/filesystem identifier."""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def derive_instance_id(path: Path) -> str:
    """Derive instance ID from directory path."""
    return slugify(path.name)


def generate_env_file(path: Path, instance_id: str, slot: int) -> None:
    """Generate .env.sandbox file for instance."""
    from ktrdr.cli.sandbox_ports import get_ports

    allocation = get_ports(slot)
    env_vars = allocation.to_env_dict()

    # Add instance identity
    env_vars["INSTANCE_ID"] = instance_id
    env_vars["COMPOSE_PROJECT_NAME"] = instance_id

    # Add shared data dir
    env_vars["KTRDR_SHARED_DIR"] = str(Path.home() / ".ktrdr" / "shared")

    # Add metadata
    env_vars["CREATED_AT"] = datetime.utcnow().isoformat() + "Z"
    env_vars["SANDBOX_VERSION"] = "1"

    # Write file
    env_file = path / ".env.sandbox"
    with open(env_file, "w") as f:
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


@sandbox_app.command()
def create(
    name: str = typer.Argument(..., help="Instance name (will be prefixed with ktrdr--)"),
    branch: str = typer.Option(None, "--branch", "-b", help="Git branch to checkout"),
    slot: int = typer.Option(None, "--slot", "-s", help="Force specific port slot (1-10)"),
):
    """Create a new sandbox instance using git worktree."""
    from ktrdr.cli.sandbox_ports import get_ports, check_ports_available
    from ktrdr.cli.sandbox_registry import (
        add_instance, allocate_next_slot, get_allocated_slots, InstanceInfo
    )

    # Derive paths
    current_repo = Path.cwd()
    instance_name = f"ktrdr--{slugify(name)}"
    worktree_path = current_repo.parent / instance_name

    # Check if already exists
    if worktree_path.exists():
        error_console.print(f"[red]Error:[/red] Directory already exists: {worktree_path}")
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
            raise typer.Exit(1)

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
        cmd.extend(["-b", branch] if not branch_exists(branch) else [branch])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error creating worktree:[/red] {e.stderr}")
        raise typer.Exit(2)

    # Generate .env.sandbox
    instance_id = derive_instance_id(worktree_path)
    generate_env_file(worktree_path, instance_id, slot)

    # Register instance
    add_instance(InstanceInfo(
        instance_id=instance_id,
        slot=slot,
        path=str(worktree_path),
        created_at=datetime.utcnow().isoformat() + "Z",
        is_worktree=True,
        parent_repo=str(current_repo),
    ))

    # Report success
    ports = get_ports(slot)
    console.print(f"\n[green]Created instance:[/green] {name}")
    console.print(f"  Location: {worktree_path}")
    console.print(f"  Port slot: {slot}")
    console.print(f"  API: http://localhost:{ports.backend}")
    console.print(f"  Grafana: http://localhost:{ports.grafana}")
    console.print(f"\nRun 'cd {worktree_path} && ktrdr sandbox up' to start")


def branch_exists(branch: str) -> bool:
    """Check if a git branch exists."""
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_create.py`
- [ ] `test_slugify_removes_special_chars`
- [ ] `test_derive_instance_id_from_path`
- [ ] `test_generate_env_file_content` — Verify all required env vars present

*Integration Tests:*
- [ ] `test_create_makes_worktree` — Worktree directory exists after create
- [ ] `test_create_generates_env_sandbox` — `.env.sandbox` exists with correct content
- [ ] `test_create_registers_instance` — Instance appears in registry
- [ ] `test_create_rejects_existing_dir` — Returns exit code 3 if dir exists
- [ ] `test_create_rejects_slot_conflict` — Returns exit code 1 if slot taken

*Smoke Test:*
```bash
ktrdr sandbox create test-smoke
ls ../ktrdr--test-smoke/.env.sandbox
cat ../ktrdr--test-smoke/.env.sandbox
```

**Acceptance Criteria:**
- [ ] Creates git worktree in parent directory
- [ ] Generates `.env.sandbox` with all required variables
- [ ] Registers instance in registry
- [ ] Reports success with URLs
- [ ] Handles errors gracefully

---

### Task 2.5: Implement `ktrdr sandbox up` and `down` Commands

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint (CLI), Background/Async

**Description:**
Implement `up` and `down` commands that start/stop Docker Compose for the current sandbox.

**Implementation Notes:**

```python
def load_env_sandbox(path: Path = None) -> dict[str, str]:
    """Load .env.sandbox from current or specified directory."""
    if path is None:
        path = Path.cwd()

    env_file = path / ".env.sandbox"
    if not env_file.exists():
        return {}

    env = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


def find_compose_file(path: Path) -> Path:
    """Find the sandbox compose file."""
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
    no_wait: bool = typer.Option(False, "--no-wait", help="Don't wait for Startability Gate"),
    build: bool = typer.Option(False, "--build", help="Force rebuild images"),
):
    """Start the sandbox stack."""
    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory (.env.sandbox not found)")
        error_console.print("Run 'ktrdr sandbox create <name>' to create one, or 'ktrdr sandbox init' to initialize this directory.")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")
    slot = env.get("SLOT_NUMBER", "?")

    console.print(f"Starting instance: {instance_id} (slot {slot})")

    # Build compose command
    try:
        compose_file = find_compose_file(cwd)
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose.sandbox.yml found")
        raise typer.Exit(1)

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    if build:
        cmd.append("--build")

    # Set environment for compose
    import os
    compose_env = os.environ.copy()
    compose_env.update(env)

    console.print(f"Running: docker compose -f {compose_file.name} up -d")

    try:
        subprocess.run(cmd, check=True, env=compose_env)
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error starting stack:[/red] {e}")
        raise typer.Exit(1)

    if no_wait:
        console.print("\nInstance starting... (use 'ktrdr sandbox status' to check)")
    else:
        # Startability Gate will be added in M3
        console.print("\nInstance starting... (Startability Gate coming in M3)")


@sandbox_app.command()
def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Also remove volumes"),
):
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
    except FileNotFoundError:
        error_console.print("[red]Error:[/red] No docker-compose file found")
        raise typer.Exit(1)

    cmd = ["docker", "compose", "-f", str(compose_file), "down"]
    if volumes:
        cmd.append("-v")

    import os
    compose_env = os.environ.copy()
    compose_env.update(env)

    try:
        subprocess.run(cmd, check=True, env=compose_env)
        console.print("[green]Instance stopped[/green]")
    except subprocess.CalledProcessError as e:
        error_console.print(f"[red]Error stopping stack:[/red] {e}")
        raise typer.Exit(1)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_up_starts_containers` — After `up`, containers are running
- [ ] `test_up_requires_env_sandbox` — Returns error if not in sandbox dir
- [ ] `test_down_stops_containers` — After `down`, containers stopped
- [ ] `test_down_volumes_removes_data` — With `--volumes`, volumes removed

*Smoke Test:*
```bash
cd ../ktrdr--test-feature
ktrdr sandbox up --no-wait
docker ps | grep test-feature
ktrdr sandbox down
```

**Acceptance Criteria:**
- [ ] `up` starts Docker Compose with correct env vars
- [ ] `down` stops containers
- [ ] `down --volumes` also removes volumes
- [ ] Both commands check for `.env.sandbox`
- [ ] Clear error messages when not in sandbox directory

---

### Task 2.6: Implement `ktrdr sandbox destroy` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint (CLI), Persistence

**Description:**
Implement `destroy` command that completely removes a sandbox instance.

**Implementation Notes:**

```python
@sandbox_app.command()
def destroy(
    keep_worktree: bool = typer.Option(False, "--keep-worktree", help="Don't delete the git worktree"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Completely remove the sandbox instance."""
    from ktrdr.cli.sandbox_registry import remove_instance, get_instance

    cwd = Path.cwd()
    env = load_env_sandbox(cwd)

    if not env:
        error_console.print("[red]Error:[/red] Not in a sandbox directory")
        raise typer.Exit(1)

    instance_id = env.get("INSTANCE_ID", "unknown")

    # Confirm unless forced
    if not force:
        confirm = typer.confirm(f"Destroy instance '{instance_id}'? This cannot be undone.")
        if not confirm:
            raise typer.Abort()

    console.print(f"Destroying instance: {instance_id}")

    # Stop containers and remove volumes
    try:
        compose_file = find_compose_file(cwd)
        import os
        compose_env = os.environ.copy()
        compose_env.update(env)

        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "-v"],
            check=True, env=compose_env, capture_output=True
        )
        console.print("  ✓ Containers stopped and volumes removed")
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("  ⚠ Could not stop containers (may already be stopped)")

    # Remove from registry
    if remove_instance(instance_id):
        console.print("  ✓ Registry updated")
    else:
        console.print("  ⚠ Instance not found in registry")

    # Remove worktree
    if not keep_worktree:
        instance_info = get_instance(instance_id)
        if instance_info and instance_info.is_worktree and instance_info.parent_repo:
            try:
                # Must run from parent repo
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(cwd)],
                    check=True, capture_output=True,
                    cwd=instance_info.parent_repo
                )
                console.print("  ✓ Worktree removed")
            except subprocess.CalledProcessError:
                # Fallback: just delete the directory
                import shutil
                shutil.rmtree(cwd, ignore_errors=True)
                console.print("  ✓ Directory removed (worktree cleanup failed)")
        else:
            # Not a worktree, just remove directory
            import shutil
            shutil.rmtree(cwd, ignore_errors=True)
            console.print("  ✓ Directory removed")

    console.print(f"\n[green]Instance '{instance_id}' destroyed[/green]")
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_destroy_removes_containers` — No containers after destroy
- [ ] `test_destroy_removes_volumes` — Volumes gone after destroy
- [ ] `test_destroy_updates_registry` — Instance removed from registry
- [ ] `test_destroy_removes_worktree` — Worktree directory gone
- [ ] `test_destroy_keep_worktree` — With flag, directory remains

*Smoke Test:*
```bash
ktrdr sandbox create destroy-test
cd ../ktrdr--destroy-test
ktrdr sandbox destroy --force
ls ../ktrdr--destroy-test  # Should not exist
```

**Acceptance Criteria:**
- [ ] Stops containers and removes volumes
- [ ] Removes instance from registry
- [ ] Removes worktree/directory (unless `--keep-worktree`)
- [ ] Requires confirmation (unless `--force`)
- [ ] Handles missing containers gracefully

---

### Task 2.7: Implement `ktrdr sandbox list` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint (CLI)

**Description:**
Implement `list` command that shows all sandbox instances with their status.

**Implementation Notes:**

```python
from rich.table import Table


def get_instance_status(instance_id: str, compose_file: Path, env: dict) -> str:
    """Check if instance containers are running."""
    try:
        import os
        compose_env = os.environ.copy()
        compose_env.update(env)

        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
            capture_output=True, text=True, env=compose_env
        )
        if result.returncode != 0:
            return "unknown"

        import json
        containers = json.loads(result.stdout) if result.stdout else []
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
def list_instances():
    """List all sandbox instances."""
    from ktrdr.cli.sandbox_registry import load_registry, clean_stale_entries

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
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_list_shows_instances` — Created instances appear in list
- [ ] `test_list_shows_status` — Running vs stopped shown correctly
- [ ] `test_list_cleans_stale` — Missing directories removed

*Smoke Test:*
```bash
ktrdr sandbox list
```

**Acceptance Criteria:**
- [ ] Lists all registered instances
- [ ] Shows slot, status, API port, path
- [ ] Cleans stale entries automatically
- [ ] Status reflects actual container state

---

## Completion Checklist

- [ ] All 7 tasks complete and committed
- [ ] `sandbox_ports.py` created with correct port mapping
- [ ] `sandbox_registry.py` created with persistence
- [ ] `sandbox.py` has create, up, down, destroy, list commands
- [ ] E2E test passes (full create → up → destroy cycle)
- [ ] Unit tests pass: `pytest tests/unit/cli/test_sandbox*.py`
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| CLI as Typer subcommand | `sandbox_app` registered via `add_typer()` |
| Pool-based port allocation | `sandbox_ports.py` with `get_ports(slot)` |
| Instance registry at `~/.ktrdr/sandbox/` | `sandbox_registry.py` manages JSON file |
| Instance ID from directory name | `derive_instance_id()` uses slugified basename |
| Two-file strategy | Commands use `docker-compose.sandbox.yml` |
