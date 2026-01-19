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

- [ ] `local-prod create` - Creates at `../ktrdr-prod`, registers in `local_prod` field
- [ ] `local-prod up` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod down` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod status` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] `local-prod logs` - Requires being in local-prod directory (uses `_require_local_prod_context`)
- [ ] **`local-prod destroy` - MUST use `get_local_prod()` registry lookup, NOT current directory!**

### E2E Test Scenarios That Must Pass

The E2E test should verify:
1. Create local-prod from sandbox directory → local-prod created at `../ktrdr-prod`
2. Destroy local-prod from sandbox directory → **local-prod destroyed, sandbox untouched**
3. Destroy local-prod from local-prod directory → local-prod destroyed correctly

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
