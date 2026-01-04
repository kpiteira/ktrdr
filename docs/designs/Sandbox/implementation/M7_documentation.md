---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 7: Documentation & Polish

**Goal:** Complete documentation and handle edge cases for production-ready sandbox system.

**Branch:** `feature/sandbox-m7-docs`

**Builds on:** M6 (Merge)

---

## E2E Test Scenario

**Purpose:** Verify documentation is complete and edge cases are handled.

**Prerequisites:**
- M6 complete (merge done)
- Clean test environment

```bash
# 1. Test edge case: stale registry cleanup
# Create an instance, manually delete the directory, verify list cleans up
ktrdr sandbox create stale-test
rm -rf ../ktrdr--stale-test
ktrdr sandbox list
# Should show: "Cleaned 1 stale entries"
# stale-test should not appear in list

# 2. Test edge case: orphaned containers
# Start instance, corrupt registry, verify graceful handling
ktrdr sandbox create orphan-test
cd ../ktrdr--orphan-test && ktrdr sandbox up --no-wait
rm ~/.ktrdr/sandbox/instances.json
ktrdr sandbox list
# Should show empty (or just warn about orphaned containers)

# 3. Test edge case: slot exhaustion
# Create 10 instances to exhaust slots
for i in {1..10}; do ktrdr sandbox create test-$i; done
ktrdr sandbox create test-11
# Should fail with: "All 10 sandbox slots are in use"

# Cleanup
for i in {1..10}; do
  cd ../ktrdr--test-$i && ktrdr sandbox destroy --force 2>/dev/null || true
done

# 4. Verify README updated
grep -q "sandbox" README.md
# Should find sandbox documentation section

# 5. Verify help text complete
ktrdr sandbox --help
ktrdr sandbox create --help
ktrdr sandbox up --help
# All should have clear, helpful descriptions
```

**Success Criteria:**
- [ ] Stale entries cleaned automatically
- [ ] Orphaned containers detected
- [ ] Slot exhaustion handled gracefully
- [ ] README has sandbox section
- [ ] All commands have complete help text

---

## Tasks

### Task 7.1: Handle Edge Cases

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint (CLI), Configuration

**Description:**
Add handling for edge cases: stale entries, orphaned containers, duplicate instance IDs.

**Implementation Notes:**

```python
# Add to list_instances() - already has stale cleanup, enhance it:

def detect_orphaned_containers() -> list[str]:
    """Find sandbox containers not in registry."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        running = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Find containers matching ktrdr-- pattern not in registry
        registry = load_registry()
        registered_ids = set(registry.instances.keys())

        orphaned = []
        for container in running:
            # Extract instance ID from container name (format: instance_id-service-1)
            if container.startswith("ktrdr--"):
                parts = container.rsplit("-", 2)
                if len(parts) >= 2:
                    instance_id = parts[0]
                    if instance_id not in registered_ids:
                        orphaned.append(instance_id)

        return list(set(orphaned))
    except Exception:
        return []


# Add warning in list command:
orphaned = detect_orphaned_containers()
if orphaned:
    console.print(f"[yellow]Warning:[/yellow] Found orphaned containers: {orphaned}")
    console.print("  These may be from deleted sandbox instances.")
    console.print("  Clean up with: docker compose down (in each orphaned directory)")


# Add to create command - handle duplicate instance ID:
def derive_unique_instance_id(base_id: str) -> str:
    """Ensure instance ID is unique, appending number if needed."""
    from ktrdr.cli.sandbox_registry import get_instance

    if not get_instance(base_id):
        return base_id

    for i in range(2, 100):
        candidate = f"{base_id}-{i}"
        if not get_instance(candidate):
            return candidate

    raise RuntimeError(f"Could not generate unique ID for {base_id}")
```

**Also add slot exhaustion message:**

```python
# In allocate_next_slot() when all slots used:
def allocate_next_slot() -> int:
    """Allocate the next available slot (1-10)."""
    allocated = get_allocated_slots()
    for slot in range(1, 11):
        if slot not in allocated:
            return slot

    # Provide helpful error with current allocations
    registry = load_registry()
    instances = sorted(registry.instances.items(), key=lambda x: x[1].slot)

    msg = "All 10 sandbox slots are in use:\n"
    for instance_id, info in instances:
        msg += f"  Slot {info.slot}: {instance_id}\n"
    msg += "\nDestroy unused instances with: ktrdr sandbox destroy"

    raise RuntimeError(msg)
```

**Testing Requirements:**

*Integration Tests:*
- [ ] `test_stale_cleanup_on_list` — Deleted dirs removed from registry
- [ ] `test_orphan_detection` — Orphaned containers detected
- [ ] `test_duplicate_id_handled` — Appends number for uniqueness
- [ ] `test_slot_exhaustion_message` — Shows all instances in error

*Smoke Test:*
```bash
# Create and delete to test stale cleanup
ktrdr sandbox create stale-test
rm -rf ../ktrdr--stale-test
ktrdr sandbox list | grep -i stale
```

**Acceptance Criteria:**
- [ ] Stale entries cleaned with notification
- [ ] Orphaned containers warned about
- [ ] Duplicate IDs get unique suffix
- [ ] Slot exhaustion shows helpful list

---

### Task 7.2: Update README

**File:** `README.md` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Add sandbox documentation section to the main README.

**Implementation Notes:**

Add section after existing development setup:

```markdown
## Parallel Development (Sandboxes)

Run multiple KTRDR stacks in parallel for feature development:

### Quick Start

```bash
# Create a sandbox for your feature
ktrdr sandbox create my-feature
cd ../ktrdr--my-feature
ktrdr sandbox up

# Stack runs on offset ports (8001, 5433, 3001, etc.)
open http://localhost:8001/api/v1/docs
```

### Commands

| Command | Description |
|---------|-------------|
| `ktrdr sandbox create <name>` | Create new sandbox instance |
| `ktrdr sandbox up` | Start the sandbox stack |
| `ktrdr sandbox down` | Stop the stack |
| `ktrdr sandbox destroy` | Remove everything |
| `ktrdr sandbox list` | Show all instances |
| `ktrdr sandbox status` | Detailed status with URLs |

### Shared Data

Sandboxes share data via `~/.ktrdr/shared/`:

```bash
# Initialize shared data from existing environment
ktrdr sandbox init-shared --from ../ktrdr2

# Or create empty structure
ktrdr sandbox init-shared --minimal
```

### CLI Auto-Detection

When in a sandbox directory, CLI commands automatically target that instance:

```bash
cd ../ktrdr--my-feature
ktrdr operations list  # Hits port 8001

# Override with --port
ktrdr --port 8002 operations list
```

See [docs/designs/Sandbox/](docs/designs/Sandbox/) for full documentation.
```

**Testing Requirements:**

*Smoke Test:*
```bash
grep -A 20 "Parallel Development" README.md
```

**Acceptance Criteria:**
- [ ] Quick start section
- [ ] Command reference table
- [ ] Shared data explanation
- [ ] Auto-detection documentation
- [ ] Link to full docs

---

### Task 7.3: Final Polish and Cleanup

**File:** Multiple
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Final cleanup tasks to make sandbox production-ready.

**Implementation Notes:**

1. **Delete `docker-compose.sandbox.yml`** (now merged)

2. **Delete backup files** (if merge verified)
   - `docker-compose.yml.pre-sandbox-backup`

3. **Review and improve help text** for all commands:

```python
# Ensure all commands have clear help strings

@sandbox_app.command()
def create(
    name: str = typer.Argument(
        ...,
        help="Instance name (e.g., 'my-feature' creates ktrdr--my-feature)",
    ),
    branch: str = typer.Option(
        None, "--branch", "-b",
        help="Git branch to checkout (default: current branch)",
    ),
    slot: int = typer.Option(
        None, "--slot", "-s",
        help="Force specific port slot 1-10 (default: auto-allocate)",
    ),
):
    """
    Create a new sandbox instance using git worktree.

    Creates a new directory ../ktrdr--<name> with its own git working
    directory and allocates a unique port slot for running in parallel.

    Examples:
        ktrdr sandbox create my-feature
        ktrdr sandbox create bugfix --branch fix/issue-123
        ktrdr sandbox create test --slot 5
    """
```

4. **Add command examples** to help text where helpful

5. **Verify all error messages are actionable**

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr sandbox create --help
# Should show examples and clear descriptions

ls docker-compose.sandbox.yml
# Should not exist (deleted)
```

**Acceptance Criteria:**
- [ ] Sandbox compose file deleted
- [ ] Backup files deleted
- [ ] All commands have examples in help
- [ ] Error messages suggest fixes
- [ ] No TODOs or FIXMEs in sandbox code

---

## Completion Checklist

- [ ] All 3 tasks complete and committed
- [ ] Edge cases handled gracefully
- [ ] README updated with sandbox docs
- [ ] Temporary files cleaned up
- [ ] Help text polished
- [ ] No FIXMEs or TODOs remaining
- [ ] Full E2E flow tested one more time
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Production-ready | Edge cases handled, docs complete |
| Clear error messages | All errors suggest remediation |
| Clean codebase | Temporary files removed |
