---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: CLI Auto-Detection + Init

**Goal:** CLI automatically targets the correct sandbox based on current directory.

**Branch:** `feature/sandbox-m4-auto-detect`

**Builds on:** M3 (Startability Gate)

---

## E2E Test Scenario

**Purpose:** Prove CLI auto-detects sandbox and `--port` flag works.

**Prerequisites:**
- M3 complete
- Two sandbox instances running on different slots

```bash
# 1. Setup: create two instances
ktrdr sandbox create feat-a
ktrdr sandbox create feat-b

cd ../ktrdr--feat-a && ktrdr sandbox up --no-wait
cd ../ktrdr--feat-b && ktrdr sandbox up --no-wait
sleep 45

# 2. Test auto-detection
cd ../ktrdr--feat-a
ktrdr operations list
# Should hit port 8001 (auto-detected from .env.sandbox)

cd ../ktrdr--feat-b
ktrdr operations list
# Should hit port 8002 (auto-detected from .env.sandbox)

# 3. Test explicit --port flag (overrides auto-detection)
cd ../ktrdr--feat-a
ktrdr --port 8002 operations list
# Should hit port 8002 despite being in feat-a directory

# 4. Test default behavior (no sandbox, no flag)
cd ~/some-other-dir
ktrdr operations list
# Should hit port 8000 (default)

# 5. Test init on existing clone
git clone git@github.com:kpiteira/ktrdr.git /tmp/ktrdr-clone
cd /tmp/ktrdr-clone
ktrdr sandbox init
# Should create .env.sandbox, allocate slot

ktrdr sandbox up --no-wait
ktrdr operations list
# Should hit the newly allocated port

# Cleanup
ktrdr sandbox destroy --force
cd ../ktrdr--feat-a && ktrdr sandbox destroy --force
cd ../ktrdr--feat-b && ktrdr sandbox destroy --force
```

**Success Criteria:**
- [ ] CLI auto-detects `.env.sandbox` in current directory
- [ ] `--port` flag overrides auto-detection
- [ ] Default is `localhost:8000` when no sandbox
- [ ] `sandbox init` works on existing clones

---

## Tasks

### Task 4.1: Implement URL Resolution Logic

**File:** `ktrdr/cli/sandbox_detect.py` (new)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Implement the URL resolution logic that determines which backend to target based on flags and current directory.

**Implementation Notes:**

```python
"""Sandbox auto-detection for CLI commands."""

from pathlib import Path
from typing import Optional


def parse_dotenv_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary."""
    if not path.exists():
        return {}

    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def find_env_sandbox(start_dir: Path = None) -> Optional[Path]:
    """
    Find .env.sandbox by walking up the directory tree.

    Returns:
        Path to .env.sandbox if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    # Walk up to find .env.sandbox (max 10 levels to avoid infinite loop)
    for _ in range(10):
        env_file = current / ".env.sandbox"
        if env_file.exists():
            return env_file

        parent = current.parent
        if parent == current:
            # Reached root
            break
        current = parent

    return None


def resolve_api_url(
    explicit_url: Optional[str] = None,
    explicit_port: Optional[int] = None,
    cwd: Optional[Path] = None,
) -> str:
    """
    Determine which KTRDR backend to target.

    Priority order (highest to lowest):
    1. explicit_url: Explicit --url flag, always wins
    2. explicit_port: --port flag, convenience for localhost
    3. .env.sandbox file: Auto-detect from current directory tree
    4. Default: http://localhost:8000

    IMPORTANT: We read the .env.sandbox FILE directly, not environment
    variables. This avoids "env var pollution" between terminal sessions.

    Args:
        explicit_url: Value from --url flag
        explicit_port: Value from --port flag
        cwd: Current working directory (defaults to actual cwd)

    Returns:
        Full API URL (e.g., "http://localhost:8001")
    """
    # Priority 1: Explicit --url flag
    if explicit_url:
        return explicit_url.rstrip("/")

    # Priority 2: Explicit --port flag
    if explicit_port:
        return f"http://localhost:{explicit_port}"

    # Priority 3: Auto-detect from .env.sandbox
    if cwd is None:
        cwd = Path.cwd()

    env_file = find_env_sandbox(cwd)
    if env_file:
        config = parse_dotenv_file(env_file)
        if port := config.get("KTRDR_API_PORT"):
            return f"http://localhost:{port}"

    # Priority 4: Default
    return "http://localhost:8000"


def get_sandbox_context(cwd: Optional[Path] = None) -> Optional[dict[str, str]]:
    """
    Get sandbox context if in a sandbox directory.

    Returns:
        Dict of env vars from .env.sandbox, or None if not in sandbox.
    """
    if cwd is None:
        cwd = Path.cwd()

    env_file = find_env_sandbox(cwd)
    if env_file:
        return parse_dotenv_file(env_file)
    return None
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_detect.py`
- [ ] `test_parse_dotenv_file_parses_values` — Key=value parsed correctly
- [ ] `test_parse_dotenv_file_ignores_comments` — Lines starting with # ignored
- [ ] `test_find_env_sandbox_in_current_dir` — Found in cwd
- [ ] `test_find_env_sandbox_in_parent_dir` — Found in parent
- [ ] `test_find_env_sandbox_not_found` — Returns None when absent
- [ ] `test_resolve_url_explicit_url_wins` — Priority 1
- [ ] `test_resolve_url_port_over_auto` — Priority 2
- [ ] `test_resolve_url_auto_from_file` — Priority 3
- [ ] `test_resolve_url_default_fallback` — Priority 4

*Smoke Test:*
```python
from ktrdr.cli.sandbox_detect import resolve_api_url
print(resolve_api_url())  # Should detect based on cwd
```

**Acceptance Criteria:**
- [ ] Priority order implemented correctly
- [ ] File-based detection (not env vars)
- [ ] Walks up directory tree
- [ ] All unit tests pass

---

### Task 4.2: Add `--port` Flag to Main CLI

**File:** `ktrdr/cli/commands.py` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint (CLI), Wiring/DI

**Description:**
Add `--port` flag to the main CLI callback and integrate sandbox auto-detection.

**Implementation Notes:**

```python
# In commands.py, modify the main() callback:

from ktrdr.cli.sandbox_detect import resolve_api_url


@cli_app.callback()
def main(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL override (e.g., backend.example.com or http://backend.example.com:8000)",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="API port (shorthand for --url http://localhost:PORT)",
    ),
):
    """KTRDR - Trading analysis and automation tool."""
    # Resolve URL with new priority logic
    resolved_url = resolve_api_url(
        explicit_url=url,
        explicit_port=port,
    )

    # Only set if different from default (to avoid unnecessary reconfiguration)
    if resolved_url != "http://localhost:8000":
        normalized_url = normalize_api_url(resolved_url)
        _cli_state["api_url"] = normalized_url

        # Reconfigure telemetry
        from ktrdr.cli import reconfigure_telemetry_for_url
        reconfigure_telemetry_for_url(normalized_url)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_port_flag_sets_url` — `--port 8001` results in correct URL
- [ ] `test_port_and_url_conflict` — `--url` wins over `--port`
- [ ] `test_auto_detect_works` — In sandbox dir, auto-detects port

*Smoke Test:*
```bash
cd ../ktrdr--feat-a
ktrdr operations list  # Should auto-detect
ktrdr --port 8002 operations list  # Should use 8002
ktrdr --url http://remote:8000 operations list  # Should use remote
```

**Acceptance Criteria:**
- [ ] `--port` flag added to main CLI
- [ ] Auto-detection integrated
- [ ] Existing `--url` behavior preserved
- [ ] Priority order: --url > --port > auto > default

---

### Task 4.3: Implement `ktrdr sandbox init` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint (CLI), Persistence

**Description:**
Implement `init` command that initializes an existing directory as a sandbox instance.

**Implementation Notes:**

```python
import subprocess


def is_ktrdr_repo(path: Path) -> bool:
    """Check if path is a KTRDR repository by checking git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=path
        )
        if result.returncode != 0:
            return False
        # Check if remote contains "ktrdr"
        return "ktrdr" in result.stdout.lower()
    except Exception:
        return False


@sandbox_app.command()
def init(
    slot: int = typer.Option(None, "--slot", "-s", help="Force specific port slot (1-10)"),
    name: str = typer.Option(None, "--name", "-n", help="Override instance name"),
):
    """Initialize current directory as a sandbox instance."""
    from datetime import datetime
    from ktrdr.cli.sandbox_ports import get_ports, check_ports_available
    from ktrdr.cli.sandbox_registry import (
        add_instance, allocate_next_slot, get_allocated_slots,
        get_instance, InstanceInfo
    )

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
        error_console.print(f"[red]Error:[/red] Instance ID '{instance_id}' already exists")
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
            raise typer.Exit(1)

    # Check port conflicts
    conflicts = check_ports_available(slot)
    if conflicts:
        error_console.print(f"[red]Error:[/red] Ports in use: {conflicts}")
        raise typer.Exit(3)

    # Generate .env.sandbox
    generate_env_file(cwd, instance_id, slot)

    # Detect if this is a worktree
    is_worktree = (cwd / ".git").is_file()  # Worktrees have .git as file, not dir
    parent_repo = None
    if is_worktree:
        # Read parent from .git file
        with open(cwd / ".git") as f:
            content = f.read()
            # Format: gitdir: /path/to/.git/worktrees/name
            if "gitdir:" in content:
                gitdir = content.split("gitdir:")[1].strip()
                # Walk up to find actual repo
                parent_repo = str(Path(gitdir).parent.parent.parent)

    # Register instance
    add_instance(InstanceInfo(
        instance_id=instance_id,
        slot=slot,
        path=str(cwd),
        created_at=datetime.utcnow().isoformat() + "Z",
        is_worktree=is_worktree,
        parent_repo=parent_repo,
    ))

    # Report success
    ports = get_ports(slot)
    console.print(f"\n[green]Initialized sandbox:[/green] {instance_id}")
    console.print(f"  Port slot: {slot}")
    console.print(f"  API: http://localhost:{ports.backend}")
    console.print(f"  Grafana: http://localhost:{ports.grafana}")
    console.print(f"\nRun 'ktrdr sandbox up' to start")
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_init_creates_env_sandbox` — `.env.sandbox` created
- [ ] `test_init_registers_instance` — Instance in registry
- [ ] `test_init_rejects_non_ktrdr_repo` — Exit 2 on non-ktrdr repo
- [ ] `test_init_rejects_already_initialized` — Exit 1 if already init
- [ ] `test_init_name_override` — `--name` sets custom ID

*Smoke Test:*
```bash
cd /path/to/ktrdr-clone
ktrdr sandbox init
cat .env.sandbox
ktrdr sandbox list  # Should show new instance
```

**Acceptance Criteria:**
- [ ] Creates `.env.sandbox` in current directory
- [ ] Validates this is a KTRDR repo
- [ ] Detects worktree vs clone
- [ ] Registers in registry
- [ ] `--name` allows custom ID

---

### Task 4.4: Update CLI Help Text

**File:** `ktrdr/cli/commands.py` (modify)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Update CLI help text to document the new `--port` flag and auto-detection behavior.

**Implementation Notes:**

```python
# Update help text in main callback docstring and option help

@cli_app.callback()
def main(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL (e.g., http://backend.example.com:8000). Overrides auto-detection.",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="API port on localhost. Overrides auto-detection. (e.g., -p 8001)",
    ),
):
    """
    KTRDR - Trading analysis and automation tool.

    Target API Resolution (highest to lowest priority):
      1. --url flag: Explicit full URL
      2. --port flag: Localhost with specified port
      3. .env.sandbox: Auto-detected in current directory
      4. Default: http://localhost:8000
    """
```

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr --help
# Should show --port option and resolution priority
```

**Acceptance Criteria:**
- [ ] `--port` documented in help
- [ ] Priority order explained in docstring
- [ ] Auto-detection mentioned

---

## Completion Checklist

- [ ] All 4 tasks complete and committed
- [ ] `sandbox_detect.py` created with resolution logic
- [ ] `--port` flag added to main CLI
- [ ] `sandbox init` command works
- [ ] Auto-detection works in sandbox directories
- [ ] E2E test passes
- [ ] Unit tests pass
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| File-based detection (not env vars) | `parse_dotenv_file()` reads file directly |
| Priority: --url > --port > file > default | `resolve_api_url()` implements order |
| Repo validation via git remote | `is_ktrdr_repo()` checks remote URL |
