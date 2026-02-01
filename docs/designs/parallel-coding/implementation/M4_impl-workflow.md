---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Impl Workflow

**Branch:** `feature/kinfra-impl-workflow`
**Builds on:** M2 (worktree patterns), M3 (slot pool)

## Goal

Enable users to create impl worktrees with claimed sandbox slots. The full workflow: check slot → create worktree → claim slot → generate override → start containers.

---

## Task 4.0: Spike - Docker Override Validation

**Type:** RESEARCH
**Estimated time:** 1-2 hours

**Description:**
Validate the Docker Compose override strategy works before implementing. This spike reduces risk of the core integration.

**Research Questions:**
1. Does `docker compose -f base.yml -f override.yml up` work as expected?
2. Do volume mounts from override correctly overlay base?
3. How long does container startup take with overlay?
4. What happens if override file has syntax errors?
5. Can we detect container health quickly?

**Steps:**
1. Manually create a test slot directory:
   ```bash
   mkdir -p /tmp/test-slot
   cp deploy/environments/local/docker-compose.yml /tmp/test-slot/
   ```

2. Create a test override file:
   ```yaml
   # /tmp/test-slot/docker-compose.override.yml
   services:
     backend:
       volumes:
         - /path/to/current/worktree/ktrdr:/app/ktrdr
   ```

3. Test startup:
   ```bash
   cd /tmp/test-slot
   docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
   docker compose ps
   curl http://localhost:8000/health
   docker compose down
   ```

4. Document findings

**Deliverables:**
- Confirmation that override strategy works
- Any gotchas discovered
- Startup time measurement
- Health check approach

**Acceptance Criteria:**
- [ ] Override strategy validated
- [ ] Startup time documented
- [ ] Any issues identified and mitigated
- [ ] Go/no-go for proceeding with implementation

---

## Task 4.1: Create impl command (core)

**File(s):**
- `ktrdr/cli/kinfra/impl.py` (create)
- `ktrdr/cli/kinfra/main.py` (modify)

**Type:** CODING
**Task Categories:** External (git), State Machine, Cross-Component

**Description:**
Implement `kinfra impl <feature/milestone>` command that creates an impl worktree and claims a sandbox slot.

**Implementation Notes:**
Per GAP-6 resolution: Check slot availability FIRST, then create worktree.
Per GAP-7 resolution: On Docker failure, release slot but keep worktree.

Order of operations:
1. Parse `<feature/milestone>` into feature and milestone parts
2. Find matching milestone file in `docs/designs/<feature>/implementation/`
3. **Check for available slot (fail fast if none)**
4. Create git worktree
5. Claim slot in registry
6. Generate docker-compose.override.yml
7. Start containers
8. On failure: release slot, keep worktree

**Code sketch:**
```python
import subprocess
from pathlib import Path
from datetime import datetime
import typer

from .errors import (
    MilestoneNotFoundError,
    SlotExhaustedError,
    SandboxStartError,
    WorktreeExistsError,
)
from .override import generate_override
from .slots import start_slot_containers
from ..sandbox_registry import SandboxRegistry

app = typer.Typer()


def _parse_feature_milestone(value: str) -> tuple[str, str]:
    """Parse 'feature/milestone' into (feature, milestone)."""
    if "/" not in value:
        raise typer.BadParameter(f"Expected format: feature/milestone, got: {value}")
    parts = value.split("/", 1)
    return parts[0], parts[1]


def _find_milestone_file(feature: str, milestone: str) -> Path | None:
    """Find milestone file in docs/designs/<feature>/implementation/."""
    impl_dir = Path.cwd() / "docs" / "designs" / feature / "implementation"
    if not impl_dir.exists():
        return None

    # Look for M<N>_*.md pattern
    for f in impl_dir.glob(f"{milestone}_*.md"):
        return f
    for f in impl_dir.glob(f"{milestone.upper()}_*.md"):
        return f

    return None


@app.command()
def impl(
    feature_milestone: str = typer.Argument(
        ..., help="Feature/milestone (e.g., genome/M1)"
    ),
    profile: str = typer.Option(
        "light", "--profile", "-p",
        help="Minimum worker profile (light/standard/heavy)"
    ),
):
    """Create impl worktree and claim sandbox slot."""
    feature, milestone = _parse_feature_milestone(feature_milestone)

    # 1. Find milestone file
    milestone_file = _find_milestone_file(feature, milestone)
    if not milestone_file:
        raise MilestoneNotFoundError(
            f"No milestone matching '{milestone}' found in "
            f"docs/designs/{feature}/implementation/"
        )

    # 2. Check slot availability FIRST (GAP-6: fail fast)
    registry = SandboxRegistry.load()
    slot = registry.get_available_slot(min_profile=profile)
    if not slot:
        raise SlotExhaustedError(
            "All 6 slots in use. Run `kinfra worktrees` to see active worktrees."
        )

    # 3. Create worktree
    worktree_name = f"ktrdr-impl-{feature}-{milestone}"
    worktree_path = Path.cwd().parent / worktree_name
    branch_name = f"impl/{feature}-{milestone}"

    if worktree_path.exists():
        raise WorktreeExistsError(f"Worktree {worktree_name} already exists")

    # Check if branch exists
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True, text=True
    )
    branch_exists = bool(result.stdout.strip())

    if branch_exists:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), branch_name],
            check=True
        )
    else:
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            check=True
        )

    typer.echo(f"Created worktree at {worktree_path}")

    # 4. Claim slot and start containers
    try:
        registry.claim_slot(slot.slot_id, worktree_path)
        typer.echo(f"Claimed slot {slot.slot_id} ({slot.profile})")

        generate_override(slot, worktree_path)
        typer.echo("Generated docker-compose.override.yml")

        start_slot_containers(slot)
        typer.echo(f"Started containers (API: http://localhost:{slot.ports['api']})")

    except Exception as e:
        # GAP-7: Release slot, keep worktree
        typer.echo(f"Error starting sandbox: {e}", err=True)
        registry.release_slot(slot.slot_id)
        typer.echo(
            f"Slot released. Worktree kept at {worktree_path}. "
            f"Fix issue and run `kinfra sandbox up`.",
            err=True
        )
        raise SandboxStartError(str(e))

    typer.echo(f"\nReady! cd {worktree_path}")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_impl_parses_feature_milestone` — parses "genome/M1" correctly
- [ ] `test_impl_parses_feature_milestone_error` — rejects invalid format
- [ ] `test_impl_finds_milestone_file` — finds M1_*.md files
- [ ] `test_impl_checks_slot_first` — slot check before worktree creation
- [ ] `test_impl_fails_no_slots` — raises SlotExhaustedError
- [ ] `test_impl_fails_milestone_not_found` — raises MilestoneNotFoundError
- [ ] `test_impl_uses_existing_branch` — reuses impl branch if exists
- [ ] `test_impl_creates_new_branch` — creates impl branch if not exists
- [ ] `test_impl_fails_worktree_exists` — raises WorktreeExistsError

*Integration Tests:*
- [ ] `test_impl_rollback_on_docker_failure` — slot released, worktree kept

*Smoke Test:*
```bash
# Create test milestone
mkdir -p docs/designs/test-impl/implementation/
echo "# M1 Test" > docs/designs/test-impl/implementation/M1_test.md

uv run kinfra impl test-impl/M1
uv run kinfra sandbox slots | grep "test-impl"
# Keep for M5 testing or cleanup:
# uv run kinfra done test-impl-M1 --force
```

**Acceptance Criteria:**
- [ ] Parses feature/milestone argument correctly
- [ ] Checks slot availability before creating worktree (GAP-6)
- [ ] Creates worktree at `../ktrdr-impl-<feature>-<milestone>/`
- [ ] Uses existing branch if `impl/<feature>-<milestone>` exists
- [ ] Claims slot and updates registry
- [ ] Generates override file
- [ ] Starts containers
- [ ] On Docker failure: releases slot, keeps worktree (GAP-7)

---

## Task 4.2: Create override file generator

**File(s):**
- `ktrdr/cli/kinfra/override.py` (create)

**Type:** CODING
**Task Categories:** Configuration

**Description:**
Generate `docker-compose.override.yml` that mounts worktree code into slot containers.

**Implementation Notes:**
- Template with worktree path substitution
- Mounts: `ktrdr/`, `research_agents/`, `tests/`, `config/`
- Shared data dirs use env vars: `${KTRDR_DATA_DIR}`, etc.
- Comment header with generation info

**Code sketch:**
```python
from pathlib import Path
from datetime import datetime

from ..sandbox_registry import SlotInfo


OVERRIDE_TEMPLATE = """\
# Generated by: kinfra impl
# Claimed by: {worktree_path}
# Generated at: {timestamp}
# Do not edit manually - regenerated on each claim

services:
  backend:
    volumes:
      - {worktree_path}/ktrdr:/app/ktrdr
      - {worktree_path}/research_agents:/app/research_agents
      - {worktree_path}/tests:/app/tests
      - {worktree_path}/config:/app/config:ro
      - ${{KTRDR_DATA_DIR}}:/app/data
      - ${{KTRDR_MODELS_DIR}}:/app/models
      - ${{KTRDR_STRATEGIES_DIR}}:/app/strategies

  backtest-worker-1:
    volumes:
      - {worktree_path}/ktrdr:/app/ktrdr
      - {worktree_path}/research_agents:/app/research_agents
      - ${{KTRDR_DATA_DIR}}:/app/data
      - ${{KTRDR_MODELS_DIR}}:/app/models
      - ${{KTRDR_STRATEGIES_DIR}}:/app/strategies

  training-worker-1:
    volumes:
      - {worktree_path}/ktrdr:/app/ktrdr
      - {worktree_path}/research_agents:/app/research_agents
      - ${{KTRDR_DATA_DIR}}:/app/data
      - ${{KTRDR_MODELS_DIR}}:/app/models
      - ${{KTRDR_STRATEGIES_DIR}}:/app/strategies
"""


def generate_override(slot: SlotInfo, worktree_path: Path) -> None:
    """Generate docker-compose.override.yml for a claimed slot."""
    content = OVERRIDE_TEMPLATE.format(
        worktree_path=worktree_path,
        timestamp=datetime.now().isoformat(),
    )

    override_path = slot.infrastructure_path / "docker-compose.override.yml"
    override_path.write_text(content)


def remove_override(slot: SlotInfo) -> None:
    """Remove docker-compose.override.yml."""
    override_path = slot.infrastructure_path / "docker-compose.override.yml"
    override_path.unlink(missing_ok=True)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_override_contains_worktree_path` — worktree path in volumes
- [ ] `test_override_valid_yaml` — generates valid YAML
- [ ] `test_override_all_services` — includes backend and workers
- [ ] `test_override_has_timestamp` — timestamp in header
- [ ] `test_remove_override` — file deleted

**Acceptance Criteria:**
- [ ] Override file generated at slot path
- [ ] Contains correct worktree mounts
- [ ] Valid docker-compose syntax
- [ ] Can be removed cleanly

---

## Task 4.3: Create slot container management

**File(s):**
- `ktrdr/cli/kinfra/slots.py` (create)

**Type:** CODING
**Task Categories:** External (docker), Cross-Component

**Description:**
Create slot management utilities for starting/stopping containers with override file.

**Implementation Notes:**
- Start: `docker compose -f docker-compose.yml -f docker-compose.override.yml up -d`
- Stop: `docker compose down` (keeps volumes)
- Run from slot directory
- Wait for health check after start

**Code sketch:**
```python
import subprocess
import time
from pathlib import Path

from ..sandbox_registry import SlotInfo


def start_slot_containers(slot: SlotInfo, timeout: int = 120) -> None:
    """Start containers for a slot with override.

    Args:
        slot: Slot to start
        timeout: Max seconds to wait for health
    """
    cmd = [
        "docker", "compose",
        "-f", "docker-compose.yml",
        "-f", "docker-compose.override.yml",
        "up", "-d"
    ]
    subprocess.run(cmd, cwd=slot.infrastructure_path, check=True)

    # Wait for health
    _wait_for_health(slot, timeout)


def stop_slot_containers(slot: SlotInfo) -> None:
    """Stop containers for a slot (keeps volumes)."""
    cmd = ["docker", "compose", "down"]
    subprocess.run(cmd, cwd=slot.infrastructure_path, check=True)


def _wait_for_health(slot: SlotInfo, timeout: int) -> None:
    """Wait for backend to be healthy."""
    import httpx

    url = f"http://localhost:{slot.ports['api']}/health"
    start = time.time()

    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(2)

    raise RuntimeError(f"Backend not healthy after {timeout}s")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_start_command_correct` — correct docker command built
- [ ] `test_stop_command_correct` — correct docker command built

*Integration Tests:*
- [ ] `test_containers_start` — containers actually start
- [ ] `test_health_check` — health check passes

**Acceptance Criteria:**
- [ ] Containers start with override file
- [ ] Waits for health check
- [ ] Containers stop cleanly
- [ ] Volumes preserved on stop

---

## Task 4.4: Update worktrees command for impl slots

**File(s):**
- `ktrdr/cli/kinfra/worktrees.py` (modify)

**Type:** CODING
**Task Categories:** Persistence, Cross-Component

**Description:**
Update worktrees command to show slot information for impl worktrees.

**Implementation Notes:**
- Query registry for each impl worktree
- Show slot number and status
- Show API port for easy access

**Code sketch:**
```python
# In worktrees.py, update the loop:

from ..sandbox_registry import SandboxRegistry

def worktrees():
    """List active worktrees with sandbox status."""
    # ... parse worktree list ...

    registry = SandboxRegistry.load()

    for wt in worktrees:
        name = Path(wt["path"]).name

        if "ktrdr-spec-" in name:
            wt_type = "spec"
            sandbox = "-"
        elif "ktrdr-impl-" in name:
            wt_type = "impl"
            # Look up slot
            slot = registry.get_slot_for_worktree(Path(wt["path"]))
            if slot:
                sandbox = f"slot {slot.slot_id} ({slot.status}, :{slot.ports['api']})"
            else:
                sandbox = "no slot"
        else:
            continue

        table.add_row(name, wt_type, wt.get("branch", ""), sandbox)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_worktrees_shows_slot_for_impl` — slot number displayed
- [ ] `test_worktrees_shows_port` — API port displayed
- [ ] `test_worktrees_shows_status` — running/stopped status

**Acceptance Criteria:**
- [ ] Impl worktrees show claimed slot number
- [ ] Shows container status (running/stopped)
- [ ] Shows API port

---

## Task 4.5: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 20 min

**Description:**
Validate M4 is complete.

**E2E Test: infra/impl-workflow**

This test validates:
1. `kinfra impl` creates worktree
2. Slot is claimed
3. Override file generated
4. Containers start
5. Fail-fast works (slot check before worktree)

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Create test milestone file | File exists | `ls docs/designs/test-impl/implementation/M1_*.md` |
| 2 | `uv run kinfra impl test-impl/M1` | Success | Exit code 0, output shows slot claimed |
| 3 | `ls ../ktrdr-impl-test-impl-M1/` | Worktree exists | Exit code 0 |
| 4 | `uv run kinfra sandbox slots` | Slot claimed | Shows "test-impl-M1" |
| 5 | `cat ~/.ktrdr/sandboxes/slot-*/docker-compose.override.yml` | Override exists | Contains worktree path |
| 6 | `docker ps` | Containers running | Shows slot containers |
| 7 | `uv run kinfra worktrees` | Shows impl with slot | Table shows slot info |

**Success Criteria:**
- [ ] Worktree created
- [ ] Slot claimed in registry
- [ ] Override file generated with correct mounts
- [ ] Containers running
- [ ] Worktrees list shows slot info

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] No regressions from M1-M3
- [ ] `make quality` passes
- [ ] Keep worktree for M5 testing

---

## Milestone 4 Verification

### Completion Checklist

- [ ] Spike completed and documented (Task 4.0)
- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
