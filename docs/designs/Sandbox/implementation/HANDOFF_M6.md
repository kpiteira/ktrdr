# M6 Handoff: Local-Prod Implementation

## CRITICAL BUG WARNING - READ THIS FIRST

### The Disaster That Happened

During the first implementation of M6, a critical bug in `local-prod destroy` caused **complete loss of all M6 work**. The branch `feature/sandbox-m6-local-prod` with ~6 completed tasks was destroyed because it was never pushed to remote.

### What Went Wrong

The `local-prod destroy` command was implemented to operate on `Path.cwd()` (current working directory) instead of looking up the **registered** local-prod instance from the registry.

**The buggy pattern (DO NOT USE):**
```python
@local_prod_app.command()
def destroy(...):
    path = _require_local_prod_context()  # This returned cwd if .env.sandbox existed!
    # ... destruction logic using path (which was the sandbox, not local-prod)
```

**What happened:**
1. E2E test ran `ktrdr local-prod create` from the sandbox directory (`ktrdr--stream-b`)
2. This created a local-prod worktree at `../ktrdr-prod`
3. E2E test then ran `ktrdr local-prod destroy` from the sandbox directory
4. The buggy code saw `.env.sandbox` in the sandbox and thought "this is a valid instance"
5. **It destroyed the sandbox directory (`ktrdr--stream-b`) instead of the local-prod (`ktrdr-prod`)**
6. All uncommitted M6 work was lost because the branch was never pushed

**NOTE:** The spec has changed since this bug. Local-prod now uses `init` (not `create`) and must be a clone (not worktree). However, the destroy bug lesson still applies: **always use registry lookup for destroy**.

### The Correct Implementation

`local-prod destroy` is DIFFERENT from `sandbox destroy`:

| Command | Target | Why |
|---------|--------|-----|
| `sandbox destroy` | Current directory | Sandboxes are contextual - you're "in" one |
| `local-prod destroy` | **Registered** local-prod | Local-prod is a singleton, you may not be in it |

**The correct pattern:**
```python
@local_prod_app.command()
def destroy(...):
    """IMPORTANT: This command operates on the REGISTERED local-prod instance,
    not the current directory. This is different from 'sandbox destroy'."""

    # Get registered local-prod - NOT the current directory
    if not local_prod_exists():
        error_console.print("[red]Error:[/red] No local-prod instance exists")
        raise typer.Exit(1)

    info = get_local_prod()
    if not info:
        error_console.print("[red]Error:[/red] Local-prod registry entry is invalid")
        raise typer.Exit(1)

    local_prod_path = Path(info.path)  # <-- Use registered path, NOT cwd

    # Safety check: warn if current directory is different
    cwd = Path.cwd()
    if cwd.resolve() != local_prod_path.resolve():
        console.print(f"[yellow]Note:[/yellow] Destroying local-prod at {local_prod_path}")
        console.print(f"  (Current directory is {cwd})")

    # ... rest of destruction logic using local_prod_path
```

### Key Differences Between sandbox and local-prod

1. **Sandbox commands** use `_require_sandbox_context()` which validates current directory
2. **Local-prod commands** (except destroy) use `_require_local_prod_context()` which validates current directory
3. **Local-prod destroy** MUST use `get_local_prod()` to find the registered instance

### Checklist When Implementing Task 6.2

**NOTE:** Local-prod uses `init`, NOT `create`. User must manually clone first.

- [ ] **`local-prod create` - DELETE THIS COMMAND** (it creates worktrees, but local-prod must be a clone)
- [ ] `local-prod init` - Validates clone (not worktree), creates `.env.sandbox`, registers in `local_prod` field
- [ ] `local-prod up` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod down` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod status` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod logs` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] **`local-prod destroy` - MUST use `get_local_prod()` registry lookup, NOT current directory!**

### Clone vs Worktree Validation

`local-prod init` must verify the current directory is a **clone**, not a worktree:

```python
def _is_clone_not_worktree(path: Path) -> bool:
    """Worktrees have .git as a FILE. Clones have .git as a DIRECTORY."""
    git_path = path / ".git"
    return git_path.is_dir()  # True = clone, False = worktree
```

### E2E Test Scenarios That Must Pass

The E2E test should verify:
1. Init in a clone → local-prod initialized
2. Init in a worktree → **rejected with clear error**
3. Init when local-prod already exists → **rejected (singleton)**
4. Destroy from any directory → **local-prod destroyed, other directories untouched**
5. Destroy from local-prod directory → local-prod destroyed correctly

---

## Other Implementation Notes

### Port Allocation Bug

Slot 0 needs 8 worker ports (5003-5010) for `--profile local-prod`.
Slots 1-10 must start at 5011+ to avoid conflict with slot 0's port 5010.

```python
# sandbox_ports.py
if slot == 0:
    worker_ports=[5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010]  # 8 ports

# Slots 1-10 shifted to avoid conflict
worker_ports=[
    5011 + (slot - 1) * 10,  # 5011, 5021, 5031, ...
    5011 + (slot - 1) * 10 + 1,
    5011 + (slot - 1) * 10 + 2,
    5011 + (slot - 1) * 10 + 3,
]
```

### Profile Parameter for stop_instance

`instance_core.stop_instance()` needs a `profile` parameter to pass `--profile local-prod` to docker compose down, otherwise extra workers won't be stopped.

```python
def stop_instance(path: Path, remove_volumes: bool = False, profile: Optional[str] = None) -> int:
    cmd = ["docker", "compose", "-f", str(compose_file)]
    if profile:
        cmd.extend(["--profile", profile])
    cmd.append("down")
    # ...
```

### Bootstrap Script (Task 6.3)

A new `scripts/setup-local-prod.sh` script guides users through first-time setup:
1. Checks prerequisites (git, docker, uv, op)
2. Explains 1Password requirements (`ktrdr-local-prod` item)
3. Clones repo to user-specified path
4. Runs `uv sync` and `ktrdr local-prod init`
5. Offers shared data initialization

This solves the chicken-and-egg problem: you need the CLI to setup, but you need a clone to have the CLI.

### Code Reuse Warning

**Local-prod commands are THIN WRAPPERS over `instance_core.py`.**

Do NOT re-implement Docker/Compose logic. Call existing functions:
- `instance_core.start_instance(profile="local-prod")`
- `instance_core.stop_instance(profile="local-prod")`
- `instance_core.generate_env_file(slot=0)`
- etc.

See M6_local_prod.md Task 6.2 for the full reuse table.

---

## Task 6.1 Complete: Update Registry for Local-Prod

### Implementation Status

The registry already had full local-prod support implemented. Task 6.1 was primarily verification through tests.

### Tests Added

7 new tests in `TestLocalProdRegistry` class:
- `test_local_prod_not_exists_initially` - Empty registry state
- `test_set_and_get_local_prod` - Basic CRUD round-trip
- `test_clear_local_prod` - Remove singleton
- `test_local_prod_is_worktree_false_for_clones` - Verify clone flag
- `test_local_prod_singleton_overwrite` - Singleton behavior
- `test_local_prod_persists_across_load` - Persistence validation
- `test_local_prod_independent_of_sandboxes` - Isolation from sandbox instances

### Next Task Notes

Task 6.3 implements the bootstrap setup script. Key points:
- Script solves chicken-and-egg problem (need CLI to setup, need clone to have CLI)
- Should check prerequisites, clone, run uv sync, run init, offer shared data setup

---

## Task 6.2 Complete: Implement Local-Prod CLI Commands

### Implementation

Created `ktrdr/cli/local_prod.py` with commands:
- `init` - Validates clone (not worktree), enforces singleton, creates .env.sandbox with slot 0
- `up` - Thin wrapper over `start_instance(profile="local-prod", secrets_item="ktrdr-local-prod")`
- `down` - Thin wrapper over `stop_instance(profile="local-prod")`
- `destroy` - Uses registry lookup (`get_local_prod()`) to find path, NOT cwd
- `status` - Shows service URLs
- `logs` - Shows container logs

### Key Gotchas

1. **No `create` command** - Local-prod uses `init`, not `create`. User must manually clone first.

2. **destroy uses registry lookup** - The critical bug fix is implemented:
   ```python
   info = get_local_prod()
   local_prod_path = Path(info.path)  # Use registered path, NOT cwd
   ```

3. **Different 1Password item** - Added `secrets_item` parameter to `instance_core.start_instance()`:
   - Sandbox uses: `ktrdr-sandbox-dev`
   - Local-prod uses: `ktrdr-local-prod`

4. **Clone validation** - `_is_clone_not_worktree()` checks if `.git` is a directory (clone) vs file (worktree)

### Tests Added

14 tests in `tests/unit/cli/test_local_prod.py`:
- Init validation (worktree rejection, singleton, clone success)
- Destroy registry lookup (critical bug prevention)
- Profile passing to instance_core functions

---

## Task 6.3 Complete: Create Bootstrap Setup Script

### Implementation

Created `scripts/setup-local-prod.sh` - an interactive setup script that solves the chicken-and-egg problem.

**Script features:**
- `--help` - Shows usage information
- `--check-only` - Only validates prerequisites, doesn't install
- `--non-interactive --path=PATH` - For CI/scripted mode
- Interactive mode with prompts for path and shared data setup

**What the script does:**
1. Checks prerequisites (git, docker, uv, op) with color-coded status
2. Explains 1Password requirements (item: `ktrdr-local-prod`)
3. Clones repository to user-specified path
4. Runs `uv sync` for dependencies
5. Runs `ktrdr local-prod init`
6. Offers shared data initialization (copy from existing or minimal)
7. Offers to start local-prod
8. Shows next steps summary

### Tests Added

12 tests in `tests/unit/scripts/test_setup_local_prod.py`:
- Script exists and is executable
- `--check-only` validates prerequisites
- Reports status for git, docker, uv, 1Password
- Explains 1Password item requirements
- `--help` shows usage
- Fails if destination already exists
- Shows banner/title
- Uses color codes for status

### Next Task Notes

Task 6.4 updates the Docker Compose file:
- Comment out extra workers (5-8) but keep profile structure
- Ensure `mcp-local` service is included

---

## Task 6.4 Complete: Update Compose for Local-Prod

### Implementation

The extra workers (5-8) were already commented out with proper profile structure preserved. Added `mcp-local` service.

**Changes to `docker-compose.sandbox.yml`:**
- Added `mcp-local` service (copied from `deploy/environments/local/docker-compose.yml`)
- Adapted paths for sandbox context (e.g., `./mcp:/mcp:ro` instead of `../../../mcp:/mcp:ro`)
- `mcp-local` has no profile restriction - starts with regular `up`

**Key configuration for mcp-local:**
- Mounts `./mcp` at `/mcp` (not `/app/mcp`) to avoid shadowing pip mcp package
- Sets `PYTHONPATH=/app:/mcp` for both ktrdr and mcp imports
- `working_dir: /mcp` for correct execution context
- `stdin_open: true` for stdio MCP transport
- `command: ["sleep", "infinity"]` - Claude exec's into the container

### Next Task Notes

Task 6.5 creates documentation:
- `docs/designs/Sandbox/LOCAL_PROD_SETUP.md` - Complete setup guide
- Document 1Password item requirements
- Document host service connections
