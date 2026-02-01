---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Slot Pool Infrastructure

**Branch:** `feature/kinfra-slot-pool`
**Builds on:** M1 (kinfra CLI exists)
**Can run parallel with:** M2

## Goal

Create the sandbox slot pool infrastructure. 6 pre-defined slots with profiles (light/standard/heavy), tracked in a v2 registry schema.

---

## Task 3.1: Update registry to v2 schema

**File(s):**
- `ktrdr/cli/sandbox_registry.py` (modify)

**Type:** CODING
**Task Categories:** Persistence, State Machine

**Description:**
Update the sandbox registry to v2 schema that supports slot pools with claims, profiles, and status tracking.

**Implementation Notes:**
- Add migration from v1 to v2 schema (backward compatible read)
- New fields: `version`, `slots` dict with `profile`, `workers`, `claimed_by`, `claimed_at`, `status`
- Keep backward compatibility for reading v1 (migrate on write)
- Location: `~/.ktrdr/sandboxes/registry.json`

**Code sketch:**
```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

REGISTRY_VERSION = 2

@dataclass
class SlotInfo:
    slot_id: int
    infrastructure_path: Path
    profile: str  # "light", "standard", "heavy"
    workers: dict[str, int]  # {"backtest": 1, "training": 1}
    ports: dict[str, int]  # {"api": 8001, "db": 5433, ...}
    claimed_by: Optional[Path] = None
    claimed_at: Optional[datetime] = None
    status: str = "stopped"  # "stopped", "running"

    def to_dict(self) -> dict:
        return {
            "infrastructure_path": str(self.infrastructure_path),
            "profile": self.profile,
            "workers": self.workers,
            "ports": self.ports,
            "claimed_by": str(self.claimed_by) if self.claimed_by else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "status": self.status,
        }


class SandboxRegistry:
    PROFILE_ORDER = ["light", "standard", "heavy"]

    def __init__(self, path: Path):
        self.path = path
        self._data = self._load()
        self._migrate_if_needed()

    def get_available_slot(self, min_profile: str = "light") -> Optional[SlotInfo]:
        """Find an available slot with at least the requested profile."""
        min_idx = self.PROFILE_ORDER.index(min_profile)

        for slot in self._data["slots"].values():
            if slot.claimed_by is not None:
                continue
            profile_idx = self.PROFILE_ORDER.index(slot.profile)
            if profile_idx >= min_idx:
                return slot

        return None

    def claim_slot(self, slot_id: int, worktree_path: Path) -> None:
        """Claim a slot for a worktree."""
        slot = self._data["slots"][str(slot_id)]
        slot.claimed_by = worktree_path
        slot.claimed_at = datetime.now()
        slot.status = "running"
        self._save()

    def release_slot(self, slot_id: int) -> None:
        """Release a slot."""
        slot = self._data["slots"][str(slot_id)]
        slot.claimed_by = None
        slot.claimed_at = None
        slot.status = "stopped"
        self._save()

    def _migrate_if_needed(self) -> None:
        """Migrate from v1 to v2 if needed."""
        if self._data.get("version", 1) < 2:
            # Migration logic here
            self._data["version"] = 2
            self._save()
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_registry_v2_schema` — new schema structure correct
- [ ] `test_migration_v1_to_v2` — v1 registries migrate cleanly
- [ ] `test_get_available_slot` — finds unclaimed slots
- [ ] `test_get_available_slot_with_profile` — respects profile requirement
- [ ] `test_get_available_slot_prefers_lower_profile` — light preferred over standard
- [ ] `test_claim_slot` — updates claimed_by, claimed_at, status
- [ ] `test_release_slot` — clears claim fields, sets status=stopped

*Integration Tests:*
- [ ] `test_registry_persistence` — changes persist to file

*Smoke Test:*
```bash
cat ~/.ktrdr/sandboxes/registry.json | jq '.version'  # Returns 2
```

**Acceptance Criteria:**
- [ ] Registry uses v2 schema
- [ ] Old v1 registries auto-migrate
- [ ] Slot claiming/releasing works correctly
- [ ] Profile-based slot selection works
- [ ] Prefers lower-profile slots when multiple available

---

## Task 3.2: Create slot provisioning command

**File(s):**
- `ktrdr/cli/kinfra/sandbox.py` (modify — add provision command)

**Type:** CODING
**Task Categories:** External (filesystem), Configuration

**Description:**
Add `kinfra sandbox provision` command that creates the slot directory structure and base compose files.

**Implementation Notes:**
- Creates `~/.ktrdr/sandboxes/slot-{1..6}/`
- Each slot gets: `docker-compose.yml`, `.env.sandbox`
- Profiles: slots 1-4 light, slot 5 standard, slot 6 heavy
- `--dry-run` flag shows what would be created
- Idempotent: skip existing slots
- Port allocation: slot N uses 8000+N for API, etc.

**Code sketch:**
```python
SLOT_PROFILES = {
    1: ("light", {"backtest": 1, "training": 1}),
    2: ("light", {"backtest": 1, "training": 1}),
    3: ("light", {"backtest": 1, "training": 1}),
    4: ("light", {"backtest": 1, "training": 1}),
    5: ("standard", {"backtest": 2, "training": 2}),
    6: ("heavy", {"backtest": 4, "training": 4}),
}

def _get_ports(slot_id: int) -> dict[str, int]:
    """Get port allocation for a slot."""
    return {
        "api": 8000 + slot_id,
        "db": 5432 + slot_id,
        "grafana": 3000 + slot_id,
        "jaeger_ui": 16686 + slot_id,
    }


@sandbox_app.command()
def provision(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be created"),
):
    """Create sandbox slot infrastructure."""
    base_path = Path.home() / ".ktrdr" / "sandboxes"
    base_path.mkdir(parents=True, exist_ok=True)

    for slot_id in range(1, 7):
        slot_path = base_path / f"slot-{slot_id}"
        profile, workers = SLOT_PROFILES[slot_id]
        ports = _get_ports(slot_id)

        if slot_path.exists():
            typer.echo(f"Slot {slot_id}: already exists, skipping")
            continue

        if dry_run:
            typer.echo(f"Would create slot {slot_id} ({profile}) at {slot_path}")
            typer.echo(f"  Ports: API={ports['api']}, DB={ports['db']}")
            continue

        _create_slot(slot_path, slot_id, profile, workers, ports)
        typer.echo(f"Created slot {slot_id} ({profile})")

    # Update registry
    if not dry_run:
        _update_registry_with_slots(base_path)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_provision_creates_slots` — 6 slots created
- [ ] `test_provision_idempotent` — existing slots not overwritten
- [ ] `test_provision_dry_run` — no files created in dry run
- [ ] `test_slot_profiles_correct` — correct profile per slot
- [ ] `test_port_allocation` — correct ports per slot

*Smoke Test:*
```bash
uv run kinfra sandbox provision --dry-run
ls ~/.ktrdr/sandboxes/
```

**Acceptance Criteria:**
- [ ] Creates 6 slot directories
- [ ] Each slot has `docker-compose.yml` and `.env.sandbox`
- [ ] Profiles match spec (1-4 light, 5 standard, 6 heavy)
- [ ] Port allocations correct
- [ ] Idempotent (safe to run multiple times)
- [ ] Registry updated with slot info

---

## Task 3.3: Create compose templates

**File(s):**
- `ktrdr/cli/kinfra/templates/docker-compose.base.yml` (create)
- `ktrdr/cli/kinfra/templates/__init__.py` (create)

**Type:** CODING
**Task Categories:** Configuration

**Description:**
Create Docker Compose templates for the slot infrastructure. Templates use variable substitution for port assignments and worker counts.

**Implementation Notes:**
- Base template has all services with `${VARIABLE}` placeholders
- `.env.sandbox` provides values: ports, worker counts
- Template is copied to slot on provisioning
- Use existing compose files as reference (`deploy/environments/local/docker-compose.yml`)
- Worker scaling via `deploy.replicas` or separate service definitions

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_template_valid_yaml` — templates parse as valid YAML
- [ ] `test_template_variables` — all required variables present
- [ ] `test_template_services` — backend, workers defined

**Acceptance Criteria:**
- [ ] Base compose template created
- [ ] Template works with variable substitution
- [ ] Matches existing compose structure
- [ ] Supports different worker counts via env vars

---

## Task 3.4: Create slots listing command

**File(s):**
- `ktrdr/cli/kinfra/sandbox.py` (modify — add slots command)

**Type:** CODING
**Task Categories:** Persistence

**Description:**
Add `kinfra sandbox slots` command that shows all slots with their profile, claim status, and container status.

**Code sketch:**
```python
@sandbox_app.command()
def slots():
    """List all sandbox slots with status."""
    registry = SandboxRegistry.load()

    table = Table(title="Sandbox Slots")
    table.add_column("Slot", justify="center")
    table.add_column("Profile")
    table.add_column("API Port", justify="right")
    table.add_column("Claimed By")
    table.add_column("Status")

    for slot_id, slot in sorted(registry.get_all_slots().items()):
        claimed = slot.claimed_by.name if slot.claimed_by else "-"
        status_style = "green" if slot.status == "running" else "dim"

        table.add_row(
            str(slot_id),
            slot.profile,
            str(slot.ports["api"]),
            claimed,
            f"[{status_style}]{slot.status}[/{status_style}]"
        )

    console.print(table)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_slots_shows_all_slots` — displays 6 slots
- [ ] `test_slots_shows_claims` — claimed slots show worktree name
- [ ] `test_slots_shows_status` — running/stopped status displayed

*Smoke Test:*
```bash
uv run kinfra sandbox slots
```

**Acceptance Criteria:**
- [ ] Shows all 6 slots in table
- [ ] Shows profile per slot
- [ ] Shows claimed worktree name or "-"
- [ ] Shows running/stopped status
- [ ] Status color-coded (green=running, dim=stopped)

---

## Task 3.5: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 15 min

**Description:**
Validate M3 is complete.

**E2E Test: infra/slot-provisioning**

This test validates:
1. Slots can be provisioned
2. Slot directories have correct structure
3. Registry is v2 schema
4. Slots listing works

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | `uv run kinfra sandbox provision --dry-run` | Shows 6 slots | Output lists slots 1-6 |
| 2 | `uv run kinfra sandbox provision` | Creates slots | Exit code 0 |
| 3 | `ls ~/.ktrdr/sandboxes/slot-1/` | Has compose + env files | docker-compose.yml, .env.sandbox |
| 4 | `cat ~/.ktrdr/sandboxes/registry.json \| jq '.version'` | Returns 2 | Output: 2 |
| 5 | `uv run kinfra sandbox slots` | Shows 6 slots | Table with all slots |

**Success Criteria:**
- [ ] All 6 slots created
- [ ] Each slot has required files
- [ ] Registry is v2
- [ ] Slots listing works

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] No regressions from M1
- [ ] `make quality` passes

---

## Milestone 3 Verification

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
